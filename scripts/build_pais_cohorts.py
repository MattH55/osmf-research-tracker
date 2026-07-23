#!/usr/bin/env python3
"""
Build + validate the PAIS cohort database (v2, Observation model).

Reads:  data/pais-cohort.schema.json, data/ref/*.json, data/cohorts/*.json,
        schema/ext/*.schema.json
Writes: data/pais-cohorts-index.json      (compiled static index the frontend loads)
        data/pais-cohorts.csv             (cohort-level bulk CSV)
        data/pais-observations.csv        (one row per Observation, with comparability signature)
        pais-cohorts.html                 (cohort table + measure matrix + comparable-set views + gap matrices)
        pais-cohorts/<id>.html            (detail pages: observations grouped by measure, provenance, extensions)

Validation is part of the build: schema (Draft 2020-12) + cross-references + the
comparability signature + Layer-3 extension validation (validated if a namespace schema
exists, else preserved and flagged 'unvalidated', never rejected). Non-zero exit on failure.

Usage: python scripts/build_pais_cohorts.py [--check]
"""
from __future__ import annotations
import json, glob, os, sys, html, csv, io, hashlib, subprocess

BUILD_VERSION = "2.0.0-seed"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Ticket 3 integration: JSON-LD + thin-content gate
sys.path.insert(0, ROOT)
from scripts.lib.dataset_jsonld import build_dataset_jsonld, to_jsonld_script, build_corpus_jsonld
try:
    from scripts.lib.thin_content_gate import gate as thin_content_gate
except ImportError:
    thin_content_gate = None
SCHEMA = os.path.join(ROOT, "data", "pais-cohort.schema.json")
COHORT_GLOB = os.path.join(ROOT, "data", "cohorts", "*.json")
PATHOGENS = os.path.join(ROOT, "data", "ref", "pathogens.json")
INSTRUMENTS = os.path.join(ROOT, "data", "ref", "instruments.json")
MEASURES = os.path.join(ROOT, "data", "ref", "measures.json")
FACTORS = os.path.join(ROOT, "data", "ref", "factors.json")
EXT_SCHEMA_GLOB = os.path.join(ROOT, "schema", "ext", "*.schema.json")
SEVERITY_RULESET = "pais-severity-harmony-v1"

INDEX_OUT = os.path.join(ROOT, "data", "pais-cohorts-index.json")
CSV_OUT = os.path.join(ROOT, "data", "pais-cohorts.csv")
OBS_CSV_OUT = os.path.join(ROOT, "data", "pais-observations.csv")
PRED_CSV_OUT = os.path.join(ROOT, "data", "pais-predictors.csv")

# a predictor is temporality-valid only when the window precedes/coincides with infection
# AND the cohort design supports prospective attribution (spec v2.1 sec 1)
TEMPORAL_WINDOWS_OK = {"pre_infection", "acute_phase", "genetic_fixed"}
TEMPORAL_DESIGNS_OK = {"prospective_inception", "registry_linkage"}
QUESTION_ORDER = ["conversion", "persistence", "susceptibility_acute_severity", "susceptibility_infection"]
ESTIMATE_BUILD = os.path.join(ROOT, "scripts", "build_estimates.py")
HTML_OUT = os.path.join(ROOT, "pais-cohorts.html")
DETAIL_DIR = os.path.join(ROOT, "pais-cohorts")

DESIGN_ORDER = ["prospective_inception", "prospective_non_inception", "retrospective_cohort",
                "registry_linkage", "self_controlled", "case_control", "cross_sectional", "survey"]
ACUTE_ORDER = ["yes", "no", "unclear", "not_applicable"]
DOMAIN_ORDER = ["fatigue_pem", "neurocognitive", "autonomic", "musculoskeletal", "sleep",
                "sensory", "gastrointestinal", "respiratory", "cardiovascular", "dermatologic",
                "neuropathic", "psychiatric", "reproductive", "constitutional", "other"]
KIND_ORDER = ["symptom", "case_definition", "functional", "event", "physiologic", "lab", "instrument_score"]
MISSING_STATES = ["not_measured", "measured_not_reported", "reported_as_zero", "not_applicable", "unknown"]

LABELS = {
    "prospective_inception": "Prospective (inception)", "prospective_non_inception": "Prospective (non-inception)",
    "retrospective_cohort": "Retrospective cohort", "cross_sectional": "Cross-sectional", "case_control": "Case-control",
    "registry_linkage": "Registry linkage", "self_controlled": "Self-controlled", "survey": "Survey",
    "none": "None", "unexposed_matched": "Unexposed (matched)", "unexposed_unmatched": "Unexposed (unmatched)",
    "seronegative_contacts": "Seronegative contacts", "household_contacts": "Household contacts",
    "other_disease": "Other-disease", "self_control": "Self-control", "healthy_convenience": "Healthy convenience",
    "population_norm": "Population norm", "not_reported": "Not reported",
    "yes": "Yes", "partial": "Partial", "no": "No", "unclear": "Unclear",
    "virus": "Virus", "bacterium": "Bacterium", "protozoan": "Protozoan", "vaccine": "Vaccine",
    "environmental": "Environmental / exposure", "mixed": "Mixed",
    "unknown": "Unknown", "not_applicable": "N/A",
    "yes_validated_instrument": "Yes (validated instrument)", "yes_single_item": "Yes (single item)",
    "comprehensive_inventory": "Comprehensive inventory", "targeted_panel": "Targeted panel",
    "single_domain": "Single domain", "incidental": "Incidental",
    "validated_instrument_threshold": "Validated instrument", "structured_checklist": "Structured checklist",
    "open_ended_report": "Open-ended report", "clinician_assessed": "Clinician-assessed",
    "medical_record_code": "Medical-record code", "physical_exam": "Physical exam", "lab_assay": "Lab assay",
    "physiologic_test": "Physiologic test", "registry_linkage": "Registry linkage",
    "current": "Current", "past_7d": "Past 7 days", "past_30d": "Past 30 days", "past_3mo": "Past 3 months",
    "since_infection": "Since infection", "ever_since_onset": "Ever since onset",
    "enrolled": "Enrolled", "assessed_at_timepoint": "Assessed at timepoint", "symptomatic_subset": "Symptomatic subset",
    "responders": "Responders", "person_time": "Person-time",
    "exact": "Exact", "approximate": "Approximate", "derived": "Derived", "digitised_from_figure": "Digitised from figure",
    "fatigue_pem": "Fatigue / PEM", "neurocognitive": "Neurocognitive", "autonomic": "Autonomic",
    "musculoskeletal": "Musculoskeletal", "sleep": "Sleep", "sensory": "Sensory", "gastrointestinal": "Gastrointestinal",
    "respiratory": "Respiratory", "cardiovascular": "Cardiovascular", "dermatologic": "Dermatologic",
    "neuropathic": "Neuropathic", "psychiatric": "Psychiatric", "reproductive": "Reproductive",
    "constitutional": "Constitutional", "other": "Other",
    "symptom": "Symptoms", "case_definition": "Case definitions", "functional": "Functional outcomes",
    "event": "Events", "physiologic": "Physiologic / tissue", "lab": "Laboratory", "instrument_score": "Instrument scores",
    "acute": "Acute", "0-3mo": "0-3 mo", "3-6mo": "3-6 mo", "6-12mo": "6-12 mo", "12-24mo": "12-24 mo",
    "24mo+": "24 mo+", "unspecified": "Unspecified",
    "proportion": "Proportion", "count": "Count", "rate": "Rate", "mean_sd": "Mean (SD)", "median_iqr": "Median (IQR)",
    "geometric_mean": "Geometric mean", "categorical_distribution": "Categorical", "time_to_event": "Time-to-event",
    "effect_only": "Effect only", "paired_change": "Paired change", "presence": "Presence", "qualitative": "Qualitative",
    "not_measured": "not measured", "measured_not_reported": "measured, not reported",
    "reported_as_zero": "reported as zero", "unknown_status": "unknown",
    "sibling_analysis": "Sibling analysis", "overlapping_population": "Overlapping population",
    "parent": "Parent", "child": "Child",
    "rr": "RR", "or": "OR", "hr": "HR", "pr": "PR", "rd": "RD", "smd": "SMD", "beta": "β",
    "manual": "Manual", "assisted_verified": "Assisted (verified)",
    # predictor question types
    "conversion": "Conversion (given infection → syndrome)", "persistence": "Persistence (non-recovery)",
    "susceptibility_acute_severity": "Susceptibility to severe acute disease",
    "susceptibility_infection": "Susceptibility to infection",
    # measurement windows
    "pre_infection": "Pre-infection", "acute_phase": "Acute phase",
    "early_convalescent": "Early convalescent (≤3mo)", "post_outcome": "Post-outcome",
    "genetic_fixed": "Genetic / fixed",
    # estimate direction
    "increases_risk": "↑ increases risk", "decreases_risk": "↓ decreases risk",
    "null_result": "null result", "not_reported": "not reported",
    # factor domains
    "host_demographic": "Host demographic", "host_genetic": "Host genetic",
    "host_prior_health": "Host prior health", "acute_clinical": "Acute clinical",
    "acute_laboratory": "Acute laboratory", "acute_pathogen": "Acute pathogen",
    "acute_treatment": "Acute treatment", "acute_immune": "Acute immune",
    "psychosocial": "Psychosocial", "healthcare_access": "Healthcare access",
    # harmonised constructs
    "acute_severity": "Acute severity", "viral_burden": "Viral burden", "inflammatory_burden": "Inflammatory burden",
    "preprint": "preprint", "grey_literature": "grey literature", "patient_reported": "patient-reported",
    "not_peer_reviewed": "not peer-reviewed", "self_selected": "self-selected", "small_sample": "small sample",
    "author_conflict": "author conflict", "unverified_source": "unverified source",
    "single_timepoint": "single timepoint", "no_control": "no control",
    "journal": "Journal", "registry": "Registry", "dataset": "Dataset", "report": "Report",
}


def lab(v):
    if v is None:
        return "not reported"
    return LABELS.get(v, str(v).replace("_", " "))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def esc(s):
    return html.escape("" if s is None else str(s))


def fmtnum(x):
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def is_missing(x):
    return isinstance(x, dict) and "status" in x


# ---------------------------------------------------------------- validation
def load_ext_schemas():
    from jsonschema import Draft202012Validator
    out = {}
    for p in sorted(glob.glob(EXT_SCHEMA_GLOB)):
        ns = os.path.basename(p).replace(".schema.json", "")
        out[ns] = Draft202012Validator(load_json(p))
    return out


def validate(cohorts, pathogens, instruments, measures, ext_schemas, factors):
    from jsonschema import Draft202012Validator
    v = Draft202012Validator(load_json(SCHEMA))
    errors, warnings = [], []
    pathogen_ids = {p["id"] for p in pathogens["pathogens"]}
    instrument_ids = {i["id"] for i in instruments["instruments"]}
    measure_ids = {m["id"] for m in measures["measures"]}
    factor_ids = {f["id"] for f in factors["factors"]}
    all_ids = {d["id"] for _, d in cohorts}
    seen = set()
    for path, d in cohorts:
        name = os.path.basename(path)
        for e in sorted(v.iter_errors(d), key=lambda e: list(e.path)):
            errors.append(f"{name}: schema: {'/'.join(map(str, e.path))}: {e.message}")
        cid = d["id"]
        if cid in seen:
            errors.append(f"{name}: duplicate cohort id '{cid}'")
        seen.add(cid)
        if d["pathogen_id"] not in pathogen_ids:
            errors.append(f"{name}: pathogen_id '{d['pathogen_id']}' not in pathogens.json")
        for iid in d.get("instruments", []):
            if iid not in instrument_ids:
                errors.append(f"{name}: instrument '{iid}' not in instruments.json")
        for rel in d.get("related_cohorts", []):
            if rel["id"] not in all_ids:
                errors.append(f"{name}: related_cohorts references unknown cohort '{rel['id']}'")
        pub_ids = {p["id"] for p in d["publications"]}
        obs_ids = set()
        for o in d.get("observations", []):
            oid = o["id"]
            if oid in obs_ids:
                errors.append(f"{name}: duplicate observation id '{oid}'")
            obs_ids.add(oid)
            if o["cohort_id"] != cid:
                errors.append(f"{name}: observation '{oid}' cohort_id '{o['cohort_id']}' != '{cid}'")
            if o["publication_id"] not in pub_ids:
                errors.append(f"{name}: observation '{oid}' publication_id '{o['publication_id']}' unknown")
            if o["measure_id"] not in measure_ids:
                errors.append(f"{name}: observation '{oid}' measure_id '{o['measure_id']}' not in measures.json")
            iid = o["method"].get("instrument_id")
            if iid and iid not in instrument_ids:
                errors.append(f"{name}: observation '{oid}' instrument_id '{iid}' not in instruments.json")
        # Predictors (v2.1 susceptibility/conversion layer): cross-reference checks.
        pred_ids = set()
        for p in d.get("predictors", []):
            pid_ = p["id"]
            if pid_ in pred_ids:
                errors.append(f"{name}: duplicate predictor id '{pid_}'")
            pred_ids.add(pid_)
            if p["cohort_id"] != cid:
                errors.append(f"{name}: predictor '{pid_}' cohort_id '{p['cohort_id']}' != '{cid}'")
            if p["publication_id"] not in pub_ids:
                errors.append(f"{name}: predictor '{pid_}' publication_id '{p['publication_id']}' unknown")
            if p["factor_id"] not in factor_ids:
                errors.append(f"{name}: predictor '{pid_}' factor_id '{p['factor_id']}' not in factors.json")
            if p["outcome_measure_id"] not in measure_ids:
                errors.append(f"{name}: predictor '{pid_}' outcome_measure_id '{p['outcome_measure_id']}' not in measures.json")
            h = p.get("harmonised")
            if h and h.get("ruleset") != SEVERITY_RULESET:
                warnings.append(f"{name}: predictor '{pid_}' harmonised.ruleset '{h.get('ruleset')}' is not the current {SEVERITY_RULESET}")
        # Layer-3 extensions: validate namespaces with a schema; flag the rest (never reject)
        for scope_obj, where in [(d.get("extensions", {}), "cohort")] + \
                [(o.get("extensions", {}), f"obs {o['id']}") for o in d.get("observations", [])]:
            for ns, payload in (scope_obj or {}).items():
                if ns in ext_schemas:
                    for e in ext_schemas[ns].iter_errors(payload):
                        errors.append(f"{name}: extension '{ns}' ({where}): {e.message}")
                else:
                    warnings.append(f"{name}: extension namespace '{ns}' ({where}) has no schema — preserved as unvalidated")
    return errors, warnings


# ---------------------------------------------------------- comparability
SIG_FIELDS = ("measure_id", "ascertainment", "reference_period", "denominator_basis", "timepoint_band", "value_type")


def sig_components(o):
    return {
        "measure_id": o["measure_id"],
        "ascertainment": o["method"]["ascertainment"],
        "reference_period": o["timing"]["reference_period"],
        "denominator_basis": o["population"]["denominator_basis"],
        "timepoint_band": o["timing"]["timepoint_band"],
        "value_type": o["value"]["type"],
    }


def comparability_signature(o):
    c = sig_components(o)
    raw = "|".join(c[k] for k in SIG_FIELDS)
    return hashlib.blake2b(raw.encode(), digest_size=5).hexdigest()


# ---------------------------------------------------------- value rendering
def render_missing(m):
    st = m.get("status", "unknown")
    key = "unknown_status" if st == "unknown" else st
    return f'<span class="miss miss-{esc(st)}" title="{esc(lab(key))}">{esc(lab(key))}</span>'


def slot(x, fmt):
    return render_missing(x) if is_missing(x) else fmt(x)


def render_value(v, short=False):
    t = v["type"]
    if t == "proportion":
        return slot(v.get("percent"), lambda x: f"{fmtnum(x)}%")
    if t == "count":
        return slot(v.get("n"), lambda x: f"n={x}")
    if t == "rate":
        unit = esc(v.get("person_time_unit", ""))
        return slot(v.get("rate"), lambda x: f"{fmtnum(x)} <span class='na'>{unit}</span>")
    if t == "mean_sd":
        m = slot(v.get("mean"), fmtnum)
        sd = "" if is_missing(v.get("sd")) or v.get("sd") is None else f" ± {fmtnum(v['sd'])}"
        u = f" {esc(v['unit'])}" if v.get("unit") else ""
        return f"{m}{sd}{u}"
    if t == "median_iqr":
        return slot(v.get("median"), lambda x: f"median {fmtnum(x)}")
    if t == "geometric_mean":
        return slot(v.get("gm"), lambda x: f"GM {fmtnum(x)}")
    if t == "effect_only":
        est = slot(v.get("estimate"), fmtnum)
        return f"{lab(v.get('effect_type'))} {est}"
    if t == "paired_change":
        return slot(v.get("delta"), lambda x: f"Δ {fmtnum(x)}")
    if t == "presence":
        return "present" if v.get("boolean") else "absent"
    if t == "categorical_distribution":
        return ", ".join(f"{esc(c['label'])} {slot(c.get('percent'), lambda x: str(x) + '%')}" for c in v.get("categories", []))
    if t == "time_to_event":
        return slot(v.get("median_time"), lambda x: f"median {fmtnum(x)} {esc(v.get('unit',''))}")
    if t == "qualitative":
        txt = v.get("text", "")
        return esc(txt[:80] + "…") if short and len(txt) > 80 else esc(txt)
    return esc(t)


def value_ci(v):
    ci = v.get("ci")
    if isinstance(ci, list) and len(ci) == 2:
        return f' <span class="na">({fmtnum(ci[0])}–{fmtnum(ci[1])})</span>'
    return ""


CSS = """
:root{--bg:#fff;--fg:#1a1f26;--muted:#6b7480;--line:#e3e7ec;--card:#f7f9fb;--accent:#0b6bcb;
--warn:#b26a00;--good:#1a7f4b;--chip:#eef2f6;--zero:#faeaea;--zerofg:#a33}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--fg:#e6e9ee;--muted:#9aa4b0;--line:#252b33;
--card:#161b21;--accent:#5aa2ea;--warn:#e0a24a;--good:#5cc68d;--chip:#1c232b;--zero:#2a1c1c;--zerofg:#e08a8a}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--fg)}
.wrap{max-width:1200px;margin:0 auto;padding:24px 18px 80px}
a{color:var(--accent)}h1{font-size:1.7rem;margin:.2em 0}
h2{font-size:1.2rem;margin:1.8em 0 .5em;border-bottom:1px solid var(--line);padding-bottom:.3em}
h3{font-size:1rem;margin:1.4em 0 .3em}
.lede{color:var(--muted);max-width:74ch}.meta{font-size:.82rem;color:var(--muted);margin:.4em 0}
.chip{display:inline-block;background:var(--chip);border:1px solid var(--line);border-radius:999px;padding:1px 9px;font-size:.78rem;margin:2px 3px 2px 0;white-space:nowrap}
.badge{font-size:.66rem;padding:0 5px;border-radius:4px;border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.na{color:var(--muted);font-style:italic;font-size:.92em}
.nav{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}
.nav a{font-size:.82rem;padding:4px 10px;border:1px solid var(--line);border-radius:999px;background:var(--card);text-decoration:none}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin:14px 0;padding:12px;background:var(--card);border:1px solid var(--line);border-radius:10px}
.toolbar label{display:flex;flex-direction:column;font-size:.72rem;color:var(--muted);gap:2px}
.toolbar select,.toolbar input{font-size:.86rem;padding:4px 6px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px}
.btn{cursor:pointer;background:var(--accent);color:#fff;border:0;border-radius:6px;padding:6px 12px;font-size:.84rem}
.btn.sec{background:var(--chip);color:var(--fg);border:1px solid var(--line)}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--card);position:sticky;top:0;cursor:pointer;white-space:nowrap}
tbody tr:hover{background:var(--card)}
.matrix td,.matrix th{text-align:center;padding:5px 7px}.matrix th.row,.matrix td.row{text-align:left;font-weight:600}
.matrix .dom{background:var(--card);text-align:left;font-weight:600}
.cell0{background:var(--zero);color:var(--zerofg)}.cellN{font-weight:700}
.sv{color:#fff;border-radius:3px;padding:1px 4px;font-size:.76rem;display:inline-block;min-width:34px}
.cell-nm{color:var(--muted);opacity:.45}.cell-nr{color:var(--warn)}
.count{color:var(--muted);font-size:.85rem}.back{font-size:.85rem}
.grid2{display:grid;grid-template-columns:190px 1fr;gap:2px 14px;font-size:.9rem}.grid2 dt{color:var(--muted)}.grid2 dd{margin:0}
.warnbox{background:var(--zero);border:1px solid var(--line);border-left:3px solid var(--warn);padding:10px 12px;border-radius:6px;margin:10px 0;font-size:.9rem}
.okbox{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--good);padding:8px 12px;border-radius:6px;margin:8px 0;font-size:.86rem}
footer{margin-top:40px;border-top:1px solid var(--line);padding-top:14px;font-size:.8rem;color:var(--muted)}
.pill{font-size:.72rem;padding:1px 7px;border-radius:999px;border:1px solid var(--line)}.pill.good{color:var(--good)}.pill.no{color:var(--muted)}
.pred-up{color:var(--warn);font-weight:600}.pred-down{color:var(--good);font-weight:600}
.pred-null{color:var(--muted)}.pred-nr{color:var(--muted);font-style:italic}
.cell-sig{background:rgba(178,106,0,.28);font-weight:700;text-align:center}
.cell-null{background:var(--chip);text-align:center}
.cell-conflict{background:rgba(163,51,51,.30);font-weight:700;text-align:center}
.cell-never{color:var(--muted);opacity:.4;text-align:center}
.legend i.cell-sig{background:rgba(178,106,0,.28)}.legend i.cell-null{background:var(--chip)}
.legend i.cell-conflict{background:rgba(163,51,51,.30)}.legend i.cell-never{background:transparent}
.flag{display:inline-block;font-size:.66rem;padding:0 6px;border-radius:4px;border:1px solid var(--warn);color:var(--warn);background:transparent;margin:1px 3px 1px 0;white-space:nowrap}
.flagbox{background:var(--zero);border:1px solid var(--line);border-left:3px solid var(--warn);padding:8px 12px;border-radius:6px;margin:8px 0;font-size:.85rem}
.disease h3{margin-top:1.2em}
.miss{font-size:.78rem;font-style:italic}.miss-not_measured{color:var(--muted);opacity:.6}
.miss-measured_not_reported{color:var(--warn)}.miss-reported_as_zero{color:var(--good)}
.miss-not_applicable{color:var(--muted)}.miss-unknown{color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:.76rem;color:var(--muted);margin:8px 0}
.legend span{display:inline-flex;align-items:center;gap:5px}.legend i{width:12px;height:12px;border-radius:3px;display:inline-block;border:1px solid var(--line)}
.obs{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0;background:var(--card)}
.obs .big{font-size:1.05rem;font-weight:700}
.sig{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:.72rem;color:var(--muted)}
.cset{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0}
.cset h4{margin:.2em 0;font-size:.9rem}
.barrow{display:grid;grid-template-columns:250px 1fr;gap:8px;align-items:center;margin:3px 0;font-size:.82rem}
.barrow .lab{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.barwrap{position:relative;background:var(--chip);border-radius:4px;height:18px}
.bar{position:absolute;left:0;top:0;height:18px;border-radius:4px;background:var(--accent)}
.bar.cmp{background:var(--muted);opacity:.55;height:8px;top:5px}
.barnum{position:relative;font-size:.72rem;padding-left:5px;line-height:18px}
"""


def html_doc(title, body, extra_head=""):
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title>"
            f"<link href=\"https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap\" rel=\"stylesheet\">"
            f"<link rel=stylesheet href=\"tracker.css\">"
            f"<style>{CSS}</style>{extra_head}</head>"
            f"<body>"
            f"<nav><div class=nav-container>"
            f"<a href=https://opensourcemed.info class=nav-brand>Open Source <span>Medicine</span><span class=nav-brand-sub>Research Tracker</span></a>"
            f"<ul class=nav-links>"
            f"<li><a href=index.html>All Conditions</a></li>"
            f"<li><a href=pais-cohorts.html class=nav-active>PAIS Cohorts</a></li>"
            f"<li><a href=biomarker-atlas.html>Biomarkers</a></li>"
            f"<li><a href=therapeutics-atlas.html>Therapeutics</a></li>"
            f"<li><a href=clinical_trials.html>Clinical Trials</a></li>"
            f"</ul></div></nav>"
            f"{body}"
            f"<footer class=osmf-network-footer><div class=osmf-network-inner>"
            f"<div class=footer-brand>Open Source Medicine Foundation</div>"
            f"<div class=footer-links>"
            f"<a href=https://opensourcemed.info>OSMF</a>"
            f"<a href=https://research.opensourcemed.info/>Research Platform</a>"
            f"<a href=https://spikeprotein.site>SpikeProtein.site</a>"
            f"<a href=https://vaccinedatanavigator.org>Vaccine Data Navigator</a>"
            f"<a href=https://pacvssummit.org>PACVS Research Summit</a>"
            f"</div><div class=footer-note>Automated daily via GitHub Actions. Data from PubMed (NLM). Not medical advice.</div>"
            f"</div></footer>"
            f"<button class=back-to-top aria-label=\"Back to top\">↑</button>"
            f"<script src=\"js/site-universal.js\" defer></script>"
            f"</body></html>")


def dl_list(items):
    return "<dl class=grid2>" + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in items) + "</dl>"


def shade(pct):
    a = 0.30 + 0.65 * (max(0.0, min(100.0, pct)) / 100.0)
    return f"background:rgba(37,99,235,{a:.2f});color:#fff"


def short(name):
    return name.split(" (")[0].strip()


def flags_html(d, sep=" "):
    return sep.join(f'<span class="flag" title="evidentiary caveat">{esc(lab(f))}</span>' for f in d.get("flags", []))


def disease_href(pid, prefix=""):
    return f'{prefix}pais-cohorts/disease/{esc(pid)}.html'


def cohort_facts(d, pmap):
    n = d.get("n_analysed") or d.get("n_enrolled")
    return (f'{lab(d["design"])} · N={esc(n) if n is not None else "n/r"} · '
            f'control {lab(d["control_group"])} · {len(d.get("observations", []))} obs')


# ---------------------------------------------------------------- cohort table
def attrition(d):
    ne, na_ = d.get("n_enrolled"), d.get("n_analysed")
    if not ne or na_ is None:
        return '<span class="na">n/r</span>', ""
    pct = round(100.0 * na_ / ne)
    c = ' style="color:var(--warn)"' if pct < 70 else ""
    return f'<span{c}>{na_}/{ne} ({pct}%)</span>', str(pct)


def build_table(cohorts, pmap):
    cols = [("name", "Cohort"), ("pathogen", "Pathogen"), ("design", "Design"), ("n", "N"),
            ("ret", "Analysed/Enrolled"), ("fu", "Max f/u (mo)"), ("control", "Control"),
            ("denom", "Denominator"), ("obs", "Observations")]
    head = "".join(f'<th data-sort="{k}">{esc(t)}</th>' for k, t in cols)
    rows = []
    for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()):
        n = d.get("n_analysed") or d.get("n_enrolled")
        ret_html, ret_val = attrition(d)
        pth = pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"])
        fl = flags_html(d)
        name_cell = f'<a href="pais-cohorts/{esc(d["id"])}.html">{esc(d["name"])}</a>'
        if fl:
            name_cell += f'<br>{fl}'
        cells = {
            "name": name_cell,
            "pathogen": f'<a href="{disease_href(d["pathogen_id"])}">{esc(pth)}</a>', "design": lab(d["design"]),
            "n": esc(n) if n is not None else '<span class="na">n/r</span>',
            "ret": ret_html,
            "fu": esc(d.get("max_followup_months")) if d.get("max_followup_months") is not None else '<span class="na">n/r</span>',
            "control": lab(d["control_group"]), "denom": lab(d["denominator_defined"]),
            "obs": str(len(d.get("observations", []))),
        }
        attrs = (f'data-pclass="{esc(d["pathogen_class"])}" data-design="{esc(d["design"])}" '
                 f'data-control="{esc(d["control_group"])}" data-denom="{esc(d["denominator_defined"])}" '
                 f'data-n="{esc(n if n is not None else "")}" data-ret="{esc(ret_val)}" '
                 f'data-fu="{esc(d.get("max_followup_months") if d.get("max_followup_months") is not None else "")}" '
                 f'data-name="{esc(d["name"].lower())}"')
        rows.append(f'<tr {attrs}>' + "".join(f"<td>{cells[k]}</td>" for k, _ in cols) + "</tr>")
    return (f'<div class="tablewrap"><table id="cohorts"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def build_gap_matrix(cohorts, pmap, col_order, col_key, title, desc):
    used = []
    for _, d in cohorts:
        if d["pathogen_id"] not in used:
            used.append(d["pathogen_id"])
    counts = {}
    for _, d in cohorts:
        counts.setdefault(d["pathogen_id"], {}).setdefault(d.get(col_key), 0)
        counts[d["pathogen_id"]][d.get(col_key)] += 1
    head = '<th class="row"></th>' + "".join(f"<th>{esc(lab(c))}</th>" for c in col_order)
    body = []
    for pid in used:
        cells = [f'<td class="row">{esc(pmap.get(pid,{}).get("name",pid))}</td>']
        for c in col_order:
            n = counts.get(pid, {}).get(c, 0)
            cells.append(f'<td class="{"cell0" if n==0 else "cellN"}">{n if n else ""}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<h3>{esc(title)}</h3><p class="meta">{esc(desc)}</p><div class="tablewrap">'
            f'<table class="matrix"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


# ------------------------------------------------ observation-driven helpers
def all_observations(cohorts):
    """List of (cohort_dict, observation) for every observation."""
    return [(d, o) for _, d in cohorts for o in d.get("observations", [])]


def build_measure_matrix(cohorts, mmap):
    cols = [d for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()) if d.get("observations")]
    if not cols:
        return ""
    by = {}
    used_measures = set()
    for d in cols:
        for o in d["observations"]:
            by.setdefault((d["id"], o["measure_id"]), []).append(o)
            used_measures.add(o["measure_id"])
    head = '<th class="row">Measure</th>' + "".join(
        f'<th>{esc(short(d["name"]))}<br><span class="badge">{esc(lab(d["pathogen_class"]))}</span> '
        f'<span class="badge">{esc(lab(d["symptom_inventory_scope"]))}</span></th>' for d in cols)
    body = []
    for kind in KIND_ORDER:
        kmeasures = [m for m in mmap["_ordered"] if m["kind"] == kind and m["id"] in used_measures]
        if not kmeasures:
            continue
        body.append(f'<tr><td class="dom" colspan="{len(cols)+1}">{esc(lab(kind))}</td></tr>')
        for m in kmeasures:
            cells = [f'<td class="row" title="{esc(m["id"])}">{esc(m["label"])}</td>']
            for d in cols:
                obs = by.get((d["id"], m["id"]))
                if obs:
                    o = sorted(obs, key=lambda x: x["timing"].get("timepoint_months") or 0)[-1]
                    v = o["value"]
                    if v["type"] == "proportion" and not is_missing(v.get("percent")):
                        p = v["percent"]
                        tt = f'{p}% at {o["timing"].get("timepoint_months")}mo · {lab(o["method"]["ascertainment"])}'
                        cells.append(f'<td><span class="sv" style="{shade(p)}" title="{esc(tt)}">{fmtnum(p)}%</span></td>')
                    else:
                        cells.append(f'<td title="{esc(lab(v["type"]))}"><span class="badge">{render_value(v, short=True)}</span></td>')
                elif d["symptom_inventory_scope"] == "comprehensive_inventory" and m["kind"] == "symptom":
                    cells.append('<td class="cell-nr" title="comprehensive inventory: measured but not tabulated / reported absent">·</td>')
                else:
                    cells.append('<td class="cell-nm" title="not measured in this cohort">–</td>')
            body.append("<tr>" + "".join(cells) + "</tr>")
    legend = ('<div class="legend">'
              '<span><i style="background:rgba(37,99,235,.7)"></i> proportion (shaded)</span>'
              '<span><i style="border-color:var(--warn);background:transparent"></i> <span class="cell-nr">·</span> comprehensive inventory, not tabulated</span>'
              '<span><i style="background:transparent"></i> <span class="cell-nm">–</span> not measured</span>'
              '<span>other value types shown as a badge</span></div>')
    return (f'<p class="meta">One row per Measure (grouped by kind), one column per cohort. Proportions are '
            f'shaded; rates, qualitative and other value types render as badges. Timepoints differ between cells — '
            f'use the comparable-set view for like-with-like.</p>{legend}'
            f'<div class="tablewrap"><table class="matrix"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def sig_explainer(o):
    c = sig_components(o)
    return (f'measure {c["measure_id"]} · {lab(c["ascertainment"])} · ref {lab(c["reference_period"])} · '
            f'denom {lab(c["denominator_basis"])} · {lab(c["timepoint_band"])} · {lab(c["value_type"])}')


def build_comparable_views(cohorts, pmap, mmap):
    obs_by_measure = {}
    for d, o in all_observations(cohorts):
        obs_by_measure.setdefault(o["measure_id"], []).append((d, o))
    blocks, toc, summary_rows = [], [], []
    for m in mmap["_ordered"]:
        recs = obs_by_measure.get(m["id"], [])
        if len(recs) < 2:
            continue
        # group by comparability signature
        groups = {}
        for d, o in recs:
            groups.setdefault(comparability_signature(o), []).append((d, o))
        largest = max(len(g) for g in groups.values())
        summary_rows.append((m, len(recs), len(groups), largest))
        toc.append(f'<a href="#m-{esc(m["id"].replace(":","-"))}">{esc(m["label"])}</a>')
        gblocks = []
        for sig, grp in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            _, o0 = grp[0]
            bars = []
            for d, o in sorted(grp, key=lambda r: (pmap.get(r[0]["pathogen_id"], {}).get("name", ""), r[1]["timing"].get("timepoint_months") or 0)):
                v = o["value"]
                pth = pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"])
                label = f'{short(d["name"])} · {esc(pth)} · {o["timing"].get("timepoint_months")}mo'
                if v["type"] == "proportion" and not is_missing(v.get("percent")):
                    p = float(v["percent"])
                    cmp = o["comparator"]
                    cmpbar = ""
                    cv = cmp.get("value")
                    if isinstance(cv, dict) and cv.get("type") == "proportion" and not is_missing(cv.get("percent")):
                        cmpbar = f'<div class="bar cmp" style="width:{min(100.0,float(cv["percent"])):.1f}%"></div>'
                        cmptxt = f' <span class="na">(vs {lab(cmp["group"])}: {fmtnum(cv["percent"])}%)</span>'
                    elif is_missing(cv) and cmp.get("group") not in ("none",):
                        cmptxt = f' <span class="na">(vs {lab(cmp["group"])}: {render_missing(cv)})</span>'
                    else:
                        cmptxt = ""
                    bars.append(f'<div class="barrow"><div class="lab" title="{esc(d["name"])}">{label}</div>'
                                f'<div class="barwrap"><div class="bar" style="width:{min(100.0,p):.1f}%"></div>{cmpbar}'
                                f'<span class="barnum">{fmtnum(p)}%{value_ci(v)}{cmptxt}</span></div></div>')
                else:
                    bars.append(f'<div class="barrow"><div class="lab" title="{esc(d["name"])}">{label}</div>'
                                f'<div>{render_value(v, short=True)}{value_ci(v)}</div></div>')
            note = "directly comparable" if len(grp) > 1 else "single observation"
            gblocks.append(f'<div class="cset"><h4>Comparable set · {len(grp)} obs '
                           f'<span class="badge" title="{esc(sig_explainer(o0))}">sig {esc(sig)}</span></h4>'
                           f'<p class="sig">{esc(sig_explainer(o0))} — {note}</p>{"".join(bars)}</div>')
        warn = ""
        if len(groups) > 1:
            warn = (f'<div class="warnbox"><strong>{len(groups)} non-comparable sets.</strong> These observations of '
                    f'{esc(m["label"])} do not share a comparability signature — they differ on ascertainment, reference '
                    f'period, denominator basis, timepoint band, or value type, so the sets below must not be pooled or '
                    f'ranked against each other.</div>')
        blocks.append(f'<h3 id="m-{esc(m["id"].replace(":","-"))}">{esc(m["label"])} '
                      f'<span class="badge">{esc(lab(m["domain"]))}</span></h3>{warn}{"".join(gblocks)}')
    # "directly comparable" summary table
    srows = "".join(
        f'<tr><td>{esc(m["label"])}</td><td>{n}</td><td>{g}</td><td class="{"cellN" if lg>1 else "cell0"}">{lg}</td></tr>'
        for m, n, g, lg in sorted(summary_rows, key=lambda r: -r[3]))
    summary = ('<h3>How many cohorts measured each thing in a directly comparable way?</h3>'
               '<p class="meta">Largest comparable set = the most cohorts sharing one comparability signature for that '
               'measure. This is normally unanswerable in this literature; the signature makes it a number.</p>'
               '<div class="tablewrap"><table><thead><tr><th>Measure</th><th>Observations</th>'
               '<th>Distinct signatures</th><th>Largest comparable set</th></tr></thead>'
               f'<tbody>{srows}</tbody></table></div>')
    toc_html = '<p class="meta">Jump to measure: ' + " · ".join(toc) + "</p>" if toc else ""
    return summary + toc_html + "".join(blocks)


def build_measure_domain_gap(cohorts, pmap, mmap):
    used = []
    for _, d in cohorts:
        if d["pathogen_id"] not in used:
            used.append(d["pathogen_id"])
    doms = [dm for dm in DOMAIN_ORDER if any(mmap["_by_id"].get(o["measure_id"], {}).get("domain") == dm
            for _, d in cohorts for o in d.get("observations", []))]
    counts = {}
    for _, d in cohorts:
        ds = {mmap["_by_id"].get(o["measure_id"], {}).get("domain") for o in d.get("observations", [])}
        for dm in ds:
            counts.setdefault((d["pathogen_id"], dm), set()).add(d["id"])
    head = '<th class="row"></th>' + "".join(f"<th>{esc(lab(dm))}</th>" for dm in doms)
    body = []
    for pid in used:
        cells = [f'<td class="row">{esc(pmap.get(pid,{}).get("name",pid))}</td>']
        for dm in doms:
            n = len(counts.get((pid, dm), set()))
            cells.append(f'<td class="{"cell0" if n==0 else "cellN"}">{n if n else ""}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<h3>Gap matrix — measure domain × pathogen</h3><p class="meta">Cohorts that measured anything in that '
            f'domain for that pathogen. Empty cells = whole domains never measured for a pathogen.</p>'
            f'<div class="tablewrap"><table class="matrix"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


# ---------------------------------------------------------------- detail page
def obs_card(o, mmap, imap):
    m = mmap["_by_id"].get(o["measure_id"], {})
    v = o["value"]
    header = f'<span class="big">{render_value(v)}{value_ci(v)}</span> <span class="badge">{esc(lab(v["type"]))}</span>'
    cmp = o["comparator"]
    cmp_html = "no comparator"
    cv = cmp.get("value")
    if cmp.get("group") != "none":
        if isinstance(cv, dict) and cv.get("type"):
            cmp_html = f'{lab(cmp["group"])}: {render_value(cv)}'
        elif is_missing(cv):
            cmp_html = f'{lab(cmp["group"])}: {render_missing(cv)}'
        eff = cmp.get("effect")
        if eff:
            ci = f' ({fmtnum(eff["ci"][0])}–{fmtnum(eff["ci"][1])})' if isinstance(eff.get("ci"), list) else ""
            cmp_html += f' · {lab(eff["effect_type"])} {render_value({"type":"effect_only","estimate":eff["estimate"],"effect_type":eff["effect_type"]})}{ci}'
    prov = o["provenance"]
    verified = f'{esc(prov.get("verified_by") or "?")}' + (f' on {esc(prov["verified_on"])}' if prov.get("verified_on") else "")
    rows = dl_list([
        ("Measure", f'{esc(m.get("label", o["measure_id"]))} <span class="badge">{esc(o["measure_id"])}</span>'),
        ("As worded", f'“{esc(o.get("measure_verbatim"))}”' if o.get("measure_verbatim") else '<span class="na">n/r</span>'),
        ("Population", f'{lab(o["population"]["scope"])} · denominator {lab(o["population"]["denominator_basis"])} · '
                       f'N={render_value({"type":"count","n":o["population"]["n_assessed"]}) if not is_missing(o["population"]["n_assessed"]) else render_missing(o["population"]["n_assessed"])}'),
        ("Timing", f'{o["timing"].get("timepoint_months")} mo ({lab(o["timing"]["timepoint_band"])}) · ref {lab(o["timing"]["reference_period"])}'),
        ("Method", f'{lab(o["method"]["ascertainment"])}'
                   + (f' · {esc(imap.get(o["method"]["instrument_id"],{}).get("name", o["method"]["instrument_id"]))}' if o["method"].get("instrument_id") else "")
                   + (f' · threshold {esc(o["method"]["severity_threshold"])}' if o["method"].get("severity_threshold") else "")),
        ("Comparator", cmp_html),
        ("Comparability signature", f'<span class="sig">{comparability_signature(o)}</span> — {esc(sig_explainer(o))}'),
        ("Provenance", f'{esc(prov["source_locator"])} · {lab(prov["extraction_method"])} · verified {verified}'),
    ])
    harm = ""
    if o.get("harmonised"):
        h = o["harmonised"]
        harm = (f'<p class="meta">Harmonised ({esc(h["ruleset"])}, {esc(h["confidence"])}): '
                f'{esc(h["measure_id"])} = {render_value(h["value"])} · '
                f'{esc(", ".join(h.get("transformations", [])))}</p>')
    return f'<div class="obs"><p>{header}</p>{rows}{harm}</div>'


def build_detail(d, pmap, imap, mmap, ext_schemas):
    pth = pmap.get(d["pathogen_id"], {})
    identity = dl_list([
        ("Cohort id", f"<code>{esc(d['id'])}</code>"),
        ("Aliases", ", ".join(map(esc, d.get("aliases", []))) or '<span class="na">none</span>'),
        ("Outbreak / event", esc(d.get("outbreak_event")) if d.get("outbreak_event") else '<span class="na">n/r</span>'),
        ("Pathogen", f"{esc(pth.get('name', d['pathogen_id']))} ({lab(d['pathogen_class'])})"),
        ("Exposure ascertainment", lab(d.get("exposure_ascertainment"))),
    ])
    design = dl_list([
        ("Design", lab(d["design"])), ("Denominator defined", lab(d["denominator_defined"])),
        ("Denominator method", esc(d.get("denominator_method")) if d.get("denominator_method") else '<span class="na">n/r</span>'),
        ("Recruitment", lab(d["recruitment_source"])),
        ("Time zero", esc(d.get("time_zero_definition")) + f' ({lab(d.get("time_zero_precision"))})'),
        ("Control group", lab(d["control_group"])),
    ])
    ret_html, _ = attrition(d)
    size = dl_list([
        ("Enrolled", esc(d.get("n_enrolled")) if d.get("n_enrolled") is not None else '<span class="na">n/r</span>'),
        ("Analysed / enrolled", ret_html),
        ("Max follow-up (months)", esc(d.get("max_followup_months")) if d.get("max_followup_months") is not None else '<span class="na">n/r</span>'),
    ])
    spec = dl_list([
        ("Specimens", "Yes" if d.get("specimens_collected") else "No"),
        ("Types", ", ".join(map(esc, d.get("specimen_types", []))) or '<span class="na">none</span>'),
        ("Acute-phase specimens", lab(d["acute_phase_specimens"])), ("Biobank", lab(d["biobank_status"])),
        ("External access", lab(d.get("external_access"))),
    ])
    related = d.get("related_cohorts", [])
    related_html = (", ".join(f'<a href="{esc(r["id"])}.html">{esc(r["id"])}</a> ({lab(r["relation"])})' for r in related)
                    if related else '<span class="na">none</span>')
    prov = dl_list([
        ("Registration", esc(d.get("registration_id")) if d.get("registration_id") else '<span class="na">n/r</span>'),
        ("Funders", ", ".join(map(esc, d.get("funders", []))) or '<span class="na">n/r</span>'),
        ("Related cohorts", related_html),
        ("Symptom-inventory scope", lab(d.get("symptom_inventory_scope"))),
        ("Last verified", f'{esc(d.get("last_verified"))} — {esc(d.get("verified_by"))}'),
    ])
    # observations grouped by measure kind
    obs = d.get("observations", [])
    if obs:
        by_kind = {}
        for o in obs:
            by_kind.setdefault(mmap["_by_id"].get(o["measure_id"], {}).get("kind", "other"), []).append(o)
        parts = []
        for kind in KIND_ORDER + ["other"]:
            grp = by_kind.get(kind)
            if not grp:
                continue
            parts.append(f'<h3>{esc(lab(kind))}</h3>' + "".join(obs_card(o, mmap, imap) for o in grp))
        obs_html = "".join(parts)
    else:
        obs_html = '<p class="na">No observations recorded yet — contributions welcome via pull request.</p>'
    # extensions
    ext_html = ""
    if d.get("extensions"):
        rows = []
        for ns, payload in d["extensions"].items():
            status = '<span class="pill good">validated</span>' if ns in ext_schemas else '<span class="pill no">unvalidated (no schema)</span>'
            rows.append(f'<p><strong>{esc(ns)}</strong> {status}<br><code>{esc(json.dumps(payload, ensure_ascii=False))}</code></p>')
        ext_html = f'<h2>Extensions (Layer 3)</h2>{"".join(rows)}'
    pubs = []
    for p in d["publications"]:
        ident = (f'PMID <a href="https://pubmed.ncbi.nlm.nih.gov/{esc(p["pmid"])}/">{esc(p["pmid"])}</a>' if p.get("pmid") else "")
        if p.get("doi"):
            ident += (" · " if ident else "") + f'DOI <a href="https://doi.org/{esc(p["doi"])}">{esc(p["doi"])}</a>'
        primary = ' <span class="chip">primary</span>' if p.get("is_primary_cohort_paper") else ""
        ptype = f' <span class="flag">{esc(lab(p["type"]))}</span>' if p.get("type") and p["type"] != "journal" else ""
        if not p.get("pmid") and not p.get("doi") and p.get("url"):
            ident = f'<a href="{esc(p["url"])}">source</a>'
        pubs.append(f'<li>{esc(p.get("authors"))} ({esc(p["year"])}). <strong>{esc(p["title"])}</strong>. <em>{esc(p.get("journal"))}</em>. {ident}{ptype}{primary}</li>')
    notes = f'<div class="warnbox"><strong>Design notes & limitations.</strong> {esc(d.get("notes"))}</div>' if d.get("notes") else ""
    flagbox = (f'<div class="flagbox"><strong>Flags:</strong> {flags_html(d)} — read the observations and design fields with these caveats in mind.</div>'
               if d.get("flags") else "")
    body = f"""<div class="wrap">
<p class="back"><a href="../pais-cohorts.html">← All cohorts</a> · <a href="{disease_href(d['pathogen_id'], '../')}">{esc(pmap.get(d['pathogen_id'],{}).get('name', d['pathogen_id']))} cohorts</a></p>
<h1>{esc(d['name'])}</h1>
<p class="meta"><a href="../data/cohorts/{esc(d['id'])}.json">source record (JSON)</a> · schema v2.0.0 · CC BY 4.0</p>
{flagbox}
{notes}
<h2>Identity &amp; trigger</h2>{identity}
<h2>Design</h2>{design}
<h2>Size &amp; attrition</h2>{size}
<h2>Biospecimens</h2>{spec}
<h2>Harmonized estimate layer</h2><p class="meta">Curation status: <strong>{esc(d.get('estimates_status', 'none'))}</strong> · {len(d.get('estimates', []))} estimate(s). <a href="../data/pais-estimates.csv">Download core estimates</a></p>
<h2>Observations ({len(obs)})</h2>{obs_html}
{ext_html}
<h2>Publications</h2><ul>{"".join(pubs)}</ul>
<h2>Provenance &amp; verification</h2>{prov}
<footer><p>PAIS Cohort Database v2 · <a href="../pais-cohorts.html">back to table</a></p></footer>
</div>"""
    return html_doc(f"{d['name']} — PAIS Cohort", body)


PAGE_JS = r"""
<script>
(function(){
 var tb=document.getElementById('cohorts'); if(!tb) return;
 var rows=[].slice.call(tb.tBodies[0].rows), facets=[].slice.call(document.querySelectorAll('[data-facet]')), q=document.getElementById('q');
 function apply(){var f={};facets.forEach(function(s){if(s.value)f[s.dataset.facet]=s.value;});var term=(q&&q.value||'').toLowerCase();var shown=0;
  rows.forEach(function(r){var ok=true;for(var k in f){if(r.getAttribute('data-'+k)!==f[k]){ok=false;break;}}if(ok&&term)ok=r.getAttribute('data-name').indexOf(term)>-1;r.style.display=ok?'':'none';if(ok)shown++;});
  var c=document.getElementById('count');if(c)c.textContent=shown+' of '+rows.length+' cohorts';}
 facets.forEach(function(s){s.addEventListener('change',apply);});if(q)q.addEventListener('input',apply);
 var ths=[].slice.call(tb.tHead.rows[0].cells),dir={};
 ths.forEach(function(th){th.addEventListener('click',function(){var key=th.dataset.sort;dir[key]=!dir[key];var s=dir[key]?1:-1;var vis=rows.slice();
  vis.sort(function(a,b){if(key==='n'||key==='fu'||key==='ret'||key==='obs'){var av=parseFloat(a.getAttribute('data-'+key)),bv=parseFloat(b.getAttribute('data-'+key));if(isNaN(av))av=-1;if(isNaN(bv))bv=-1;return (av-bv)*s;}
   var x=a.cells[0].textContent,y=b.cells[0].textContent;return x<y?-s:x>y?s:0;});
  var body=tb.tBodies[0];vis.forEach(function(r){body.appendChild(r);});});});
 function dl(n,t,ty){var b=new Blob([t],{type:ty}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=n;a.click();URL.revokeObjectURL(u);}
 function wire(id,url,ty){var el=document.getElementById(id);if(el)el.addEventListener('click',function(){fetch(url).then(function(r){return r.text();}).then(function(t){dl(url.split('/').pop(),t,ty);});});}
 wire('exp-json','data/pais-cohorts-index.json','application/json');wire('exp-csv','data/pais-cohorts.csv','text/csv');wire('exp-obs','data/pais-observations.csv','text/csv');wire('exp-pred','data/pais-predictors.csv','text/csv');
 apply();
})();
</script>"""


def facet_select(name, label, values):
    opts = '<option value="">all</option>' + "".join(f'<option value="{esc(v)}">{esc(lab(v))}</option>' for v in values)
    return f'<label>{esc(label)}<select data-facet="{esc(name)}">{opts}</select></label>'


def cohorts_by_pathogen(cohorts):
    """Ordered list of (pathogen_id, [cohort,...]), grouped by pathogen class then name."""
    groups = {}
    for _, d in cohorts:
        groups.setdefault(d["pathogen_id"], []).append(d)
    order = {c: i for i, c in enumerate(["virus", "bacterium", "protozoan", "vaccine", "environmental", "mixed", "unknown"])}

    def keyf(pid):
        cls = groups[pid][0]["pathogen_class"]
        return (order.get(cls, 99), pid)
    return [(pid, sorted(groups[pid], key=lambda d: d["name"].lower())) for pid in sorted(groups, key=keyf)]


def build_by_disease(cohorts, pmap, prefix=""):
    """Grouped view: one block per disease/pathogen (class-ordered) listing its cohorts."""
    blocks = []
    for pid, ds in cohorts_by_pathogen(cohorts):
        pth = pmap.get(pid, {})
        items = []
        for d in ds:
            items.append(f'<li><a href="{prefix}pais-cohorts/{esc(d["id"])}.html">{esc(d["name"])}</a> '
                         f'<span class="na">— {cohort_facts(d, pmap)}</span> {flags_html(d)}</li>')
        blocks.append(f'<div class="disease"><h3 id="d-{esc(pid)}"><a href="{disease_href(pid, prefix)}">{esc(pth.get("name", pid))}</a> '
                      f'<span class="badge">{esc(lab(pth.get("class", "")))}</span> <span class="count">{len(ds)} cohort'
                      f'{"s" if len(ds)!=1 else ""}</span></h3><ul>{"".join(items)}</ul></div>')
    return "".join(blocks)


# ------------------------------------------------ predictors (v2.1 susceptibility)
ACUTE_DOMAINS = ["acute_clinical", "acute_laboratory", "acute_pathogen", "acute_treatment", "acute_immune"]
FACTOR_DOMAIN_ORDER = ["host_demographic", "host_genetic", "host_prior_health", "acute_clinical",
                       "acute_laboratory", "acute_pathogen", "acute_treatment", "acute_immune",
                       "psychosocial", "healthcare_access", "environmental"]


def all_predictors(cohorts):
    return [(d, p) for _, d in cohorts for p in d.get("predictors", [])]


def temporality_valid(cohort, pred):
    return pred["measurement_window"] in TEMPORAL_WINDOWS_OK and cohort["design"] in TEMPORAL_DESIGNS_OK


def _construct_key(pred, fmap):
    f = fmap.get(pred["factor_id"], {})
    return f.get("harmonised_construct") or pred["factor_id"]


def _construct_label(key, fmap):
    if key in ("acute_severity", "viral_burden", "inflammatory_burden"):
        return lab(key) + " (harmonised)"
    return fmap.get(key, {}).get("label", key)


def _dir_html(pred):
    d = pred["estimate"]["direction"]
    cls = {"increases_risk": "pred-up", "decreases_risk": "pred-down",
           "null_result": "pred-null", "not_reported": "pred-nr"}.get(d, "")
    return f'<span class="{cls}">{lab(d)}</span>'


def _sig(pred):
    return pred["estimate"]["direction"] in ("increases_risk", "decreases_risk") and pred["estimate"].get("significant") is True


def _median(xs):
    xs = sorted(x for x in xs if isinstance(x, (int, float)))
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def build_replication_table(cohorts, pmap, fmap, mmap):
    groups = {}
    for d, p in all_predictors(cohorts):
        key = (_construct_key(p, fmap), p["outcome_measure_id"], p["question_type"])
        groups.setdefault(key, []).append((d, p))
    rows = []
    for (ckey, outcome, qtype), recs in groups.items():
        cohorts_tested = {d["id"] for d, _ in recs}
        pathogens_tested = {d["pathogen_id"] for d, _ in recs}
        sigs = [(d, p) for d, p in recs if _sig(p)]
        nnull = sum(1 for _, p in recs if p["estimate"]["direction"] == "null_result")
        dirs = [p["estimate"]["direction"] for _, p in sigs]
        concordance = "—"
        if dirs:
            top = max(set(dirs), key=dirs.count)
            concordance = f"{dirs.count(top)}/{len(dirs)}"
        tvalid = sum(1 for d, p in recs if temporality_valid(d, p))
        med = _median([p["model"].get("n_predictors_tested") for _, p in recs])
        rows.append({
            "label": _construct_label(ckey, fmap), "outcome": mmap["_by_id"].get(outcome, {}).get("label", outcome),
            "qtype": qtype, "n_cohorts": len(cohorts_tested), "n_pathogens": len(pathogens_tested),
            "n_sig": len(sigs), "n_null": nnull, "concord": concordance,
            "tvalid": f"{tvalid}/{len(recs)}", "median_tested": med if med is not None else "n/r",
            "sort": (len(cohorts_tested), len(sigs)),
        })
    rows.sort(key=lambda r: r["sort"], reverse=True)
    head = "".join(f"<th>{esc(h)}</th>" for h in
                   ["Factor / construct", "Outcome", "Question", "Cohorts", "Pathogens",
                    "Significant", "Null", "Sign concordance", "Temporality-valid", "Median predictors tested"])
    body = "".join(
        f'<tr><td>{esc(r["label"])}</td><td>{esc(r["outcome"])}</td><td><span class="badge">{esc(lab(r["qtype"]))}</span></td>'
        f'<td class="cellN">{r["n_cohorts"]}</td><td>{r["n_pathogens"]}</td>'
        f'<td class="pred-up">{r["n_sig"]}</td><td class="pred-null">{r["n_null"]}</td>'
        f'<td>{esc(r["concord"])}</td><td>{esc(r["tvalid"])}</td><td>{esc(r["median_tested"])}</td></tr>'
        for r in rows)
    return (f'<p class="meta">One row per (factor/harmonised-construct × outcome × question). '
            f'Sorted by replication (cohorts tested), showing null results alongside significant ones. '
            f'No pooled effect is computed — different contrasts and adjustment sets are not poolable.</p>'
            f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def build_factor_pathogen_matrix(cohorts, pmap, fmap):
    # rows = factors (by domain), cols = pathogens with cohorts; temporality-valid predictors only
    used_pathogens = []
    for _, d in cohorts:
        if d["pathogen_id"] not in used_pathogens:
            used_pathogens.append(d["pathogen_id"])
    cell = {}
    for d, p in all_predictors(cohorts):
        if not temporality_valid(d, p):
            continue
        cell.setdefault((p["factor_id"], d["pathogen_id"]), []).append(p)
    tested_factor_ids = {fid for (fid, _) in cell}
    head = '<th class="row">Factor</th>' + "".join(f'<th>{esc(pmap.get(pid,{}).get("name",pid))}</th>' for pid in used_pathogens)
    body = []
    for dom in FACTOR_DOMAIN_ORDER:
        dfactors = [f for f in fmap["_ordered"] if f["domain"] == dom]
        # only show domains that have at least one tested factor, to keep the matrix legible
        if not any(f["id"] in tested_factor_ids for f in dfactors):
            continue
        body.append(f'<tr><td class="dom" colspan="{len(used_pathogens)+1}">{esc(lab(dom))}</td></tr>')
        for f in dfactors:
            cells = [f'<td class="row" title="{esc(f["id"])}">{esc(f["label"])}</td>']
            for pid in used_pathogens:
                preds = cell.get((f["id"], pid))
                if not preds:
                    cells.append('<td class="cell-never" title="never tested (temporality-valid)">·</td>')
                    continue
                sigs = [x for x in preds if _sig(x)]
                nulls = [x for x in preds if x["estimate"]["direction"] == "null_result"]
                if sigs and nulls:
                    st, txt = "cell-conflict", "conflict"
                elif sigs and len({x["estimate"]["direction"] for x in sigs}) > 1:
                    st, txt = "cell-conflict", "conflict"
                elif sigs:
                    st, txt = "cell-sig", "sig"
                else:
                    st, txt = "cell-null", "null"
                cells.append(f'<td class="{st}" title="{len(preds)} estimate(s)">{txt}</td>')
            body.append("<tr>" + "".join(cells) + "</tr>")
    legend = ('<div class="legend">'
              '<span><i class="cell-sig"></i> tested, significant</span>'
              '<span><i class="cell-null"></i> tested, null</span>'
              '<span><i class="cell-conflict"></i> tested, conflicting</span>'
              '<span><i class="cell-never"></i> <span class="cell-never">·</span> never tested</span></div>')
    return (f'<p class="meta">Temporality-valid predictors only (pre-infection / acute-phase / genetic, in prospective-inception '
            f'or registry cohorts). Only domains with at least one tested factor are shown; the empty cells within them are '
            f'the point — most acute-laboratory factors are never tested against the chronic outcome.</p>{legend}'
            f'<div class="tablewrap"><table class="matrix"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def build_acute_coverage_matrix(cohorts, fmap):
    cov = {}
    for d, p in all_predictors(cohorts):
        dom = fmap["_by_id"].get(p["factor_id"], {}).get("domain")
        if dom in ACUTE_DOMAINS:
            prev = cov.get((d["id"], dom))
            status = "collected_not_analysed" if p.get("analysis_status") == "collected_not_analysed" else "analysed"
            if prev != "analysed":
                cov[(d["id"], dom)] = status
    rowcohorts = [d for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()) if any((d["id"], dm) in cov for dm in ACUTE_DOMAINS)]
    if not rowcohorts:
        return ""
    head = '<th class="row">Cohort</th>' + "".join(f'<th>{esc(lab(dm))}</th>' for dm in ACUTE_DOMAINS)
    body = []
    for d in rowcohorts:
        cells = [f'<td class="row">{esc(short(d["name"]))}</td>']
        for dm in ACUTE_DOMAINS:
            s = cov.get((d["id"], dm))
            if s == "analysed":
                cells.append('<td class="cell-sig" title="analysed against the chronic outcome">✓</td>')
            elif s == "collected_not_analysed":
                cells.append('<td class="cell-null" title="collected but not analysed against the chronic outcome">c</td>')
            else:
                cells.append('<td class="cell-never">·</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<p class="meta">Which cohorts analysed any acute-phase factor against the chronic outcome (✓), '
            f'collected but did not analyse it (c), or neither (·). The "c" cells are recoverable through collaboration.</p>'
            f'<div class="tablewrap"><table class="matrix"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def build_single_factor_detail(cohorts, pmap, fmap, mmap):
    by_factor = {}
    for d, p in all_predictors(cohorts):
        by_factor.setdefault(p["factor_id"], []).append((d, p))
    blocks = []
    for f in fmap["_ordered"]:
        recs = by_factor.get(f["id"])
        if not recs:
            continue
        rows = "".join(
            f'<tr><td><a href="pais-cohorts/{esc(d["id"])}.html">{esc(short(d["name"]))}</a></td>'
            f'<td>{esc(pmap.get(d["pathogen_id"],{}).get("name",d["pathogen_id"]))}</td>'
            f'<td>{esc(p["contrast"])}</td><td>{esc(lab(p["measurement_window"]))}</td>'
            f'<td>{_dir_html(p)}</td><td>{esc(lab(p["model"]["type"]))}</td>'
            f'<td>{esc(", ".join(p["model"].get("adjusted_for", [])) or "—")}</td>'
            f'<td>{"valid" if temporality_valid(d, p) else "<span class=pred-nr>invalid</span>"}</td></tr>'
            for d, p in recs)
        blocks.append(f'<h4 id="f-{esc(f["id"].replace(":","-"))}">{esc(f["label"])} '
                      f'<span class="badge">{esc(lab(f["domain"]))}</span>'
                      + (f' <span class="badge">→ {esc(lab(f["harmonised_construct"]))}</span>' if f.get("harmonised_construct") else "")
                      + '</h4><div class="tablewrap"><table><thead><tr>'
                      + "".join(f"<th>{esc(h)}</th>" for h in ["Cohort", "Pathogen", "Contrast", "Window", "Direction", "Model", "Adjusted for", "Temporality"])
                      + f'</tr></thead><tbody>{rows}</tbody></table></div>')
    return "".join(blocks)


def build_disease_predictors(ds, pmap, fmap, mmap):
    recs = [(d, p) for d in ds for p in d.get("predictors", [])]
    if not recs:
        return ""
    rows = "".join(
        f'<tr><td>{esc(fmap["_by_id"].get(p["factor_id"],{}).get("label",p["factor_id"]))}</td>'
        f'<td>{esc(p["contrast"])}</td><td>{esc(lab(p["measurement_window"]))}</td>'
        f'<td>{esc(mmap["_by_id"].get(p["outcome_measure_id"],{}).get("label",p["outcome_measure_id"]))}</td>'
        f'<td>{_dir_html(p)}</td><td>{esc(lab(p["question_type"]))}</td>'
        f'<td>{"valid" if temporality_valid(d, p) else "<span class=pred-nr>invalid</span>"}</td>'
        f'<td><a href="../{esc(d["id"])}.html">{esc(short(d["name"]))}</a></td></tr>'
        for d, p in recs)
    return ('<h2>Susceptibility &amp; conversion predictors</h2>'
            '<div class="tablewrap"><table><thead><tr>'
            + "".join(f"<th>{esc(h)}</th>" for h in ["Factor", "Contrast", "Window", "Outcome", "Direction", "Question", "Temporality", "Cohort"])
            + f'</tr></thead><tbody>{rows}</tbody></table></div>')


def build_disease_page(pid, ds, pmap, mmap, fmap):
    pth = pmap.get(pid, {})
    obs_total = sum(len(d.get("observations", [])) for d in ds)
    cards = []
    for d in ds:
        obs_summary = ", ".join(sorted({mmap["_by_id"].get(o["measure_id"], {}).get("label", o["measure_id"])
                                        for o in d.get("observations", [])})) or "no observations yet"
        cards.append(
            f'<div class="obs"><p><a href="../{esc(d["id"])}.html"><strong>{esc(d["name"])}</strong></a> {flags_html(d)}</p>'
            f'<p class="meta">{cohort_facts(d, pmap)} · max follow-up '
            f'{esc(d.get("max_followup_months")) if d.get("max_followup_months") is not None else "n/r"} mo</p>'
            f'<p class="meta">Measures: {esc(obs_summary)}</p>'
            + (f'<div class="flagbox">Flags: {flags_html(d)}</div>' if d.get("flags") else "")
            + (f'<p class="meta">{esc(d.get("notes"))}</p>' if d.get("notes") else "") + '</div>')
    body = f"""<div class="wrap">
<p class="back"><a href="../../pais-cohorts.html">← All cohorts</a> · <a href="../../pais-cohorts.html#by-disease">All diseases</a></p>
<h1>{esc(pth.get("name", pid))}</h1>
<p class="meta">{lab(pth.get("class",""))} · {esc(pth.get("vector",""))} · {len(ds)} cohort{"s" if len(ds)!=1 else ""} · {obs_total} observations · CC BY 4.0</p>
<p class="lede">All PAIS cohorts in this database triggered by {esc(pth.get("name", pid))}. Flags mark evidentiary caveats (preprint, grey literature, patient-reported, uncontrolled, etc.).</p>
{"".join(cards)}
{build_disease_predictors(ds, pmap, fmap, mmap)}
<footer><p>PAIS Cohort Database v2 · <a href="../../pais-cohorts.html">back to table</a></p></footer>
</div>"""
    return html_doc(f"{pth.get('name', pid)} — PAIS cohorts", body)


def build_estimate_matrix(cohorts):
    """Triangular estimate-layer joinability matrix; empty cells are evidence gaps."""
    ds = [d for _, d in sorted(cohorts, key=lambda x: x[1]["name"].lower())]
    def grade(a, b):
        for x in a.get("estimates", []):
            for y in b.get("estimates", []):
                if (x["construct"], x["instrument"], x["scoring"], x.get("threshold"), x["t_bin"], x["t_anchor"]) == (y["construct"], y["instrument"], y["scoring"], y.get("threshold"), y["t_bin"], y["t_anchor"]): return "exact"
                if (x["construct"], x["instrument"], x["t_bin"], x["t_anchor"]) == (y["construct"], y["instrument"], y["t_bin"], y["t_anchor"]): return "instrument match"
                if (x["construct"], x["t_bin"], x["t_anchor"]) == (y["construct"], y["t_bin"], y["t_anchor"]): return "construct match"
        return ""
    head="<tr><th>cohort</th>"+"".join(f"<th title='{esc(d['name'])}'>{esc(d['id'])}</th>" for d in ds)+"</tr>"
    rows=[]
    for i,a in enumerate(ds):
        cells=[f"<th>{esc(a['id'])}</th>"]
        for j,b in enumerate(ds): cells.append("<td>—</td>" if j>=i else f"<td>{esc(grade(a,b))}</td>")
        rows.append("<tr>"+"".join(cells)+"</tr>")
    return "<div style='overflow:auto'><table class='matrix'><thead>"+head+"</thead><tbody>"+"".join(rows)+"</tbody></table></div>"


def _predictor_table(recs, pmap, fmap, mmap, cohort_href):
    head = "".join(f"<th>{esc(h)}</th>" for h in
                   ["Factor", "Contrast", "Window", "Outcome", "Direction", "Question", "Model", "Temporality", "Cohort"])
    rows = "".join(
        f'<tr><td>{esc(fmap["_by_id"].get(p["factor_id"],{}).get("label",p["factor_id"]))}'
        + (f' <span class="badge">→ {esc(lab(fmap["_by_id"][p["factor_id"]]["harmonised_construct"]))}</span>'
           if fmap["_by_id"].get(p["factor_id"], {}).get("harmonised_construct") else "")
        + f'</td><td>{esc(p["contrast"])}</td><td>{esc(lab(p["measurement_window"]))}</td>'
        f'<td>{esc(mmap["_by_id"].get(p["outcome_measure_id"],{}).get("label",p["outcome_measure_id"]))}'
        + (f' @ {p["outcome_timepoint_months"]}mo' if p.get("outcome_timepoint_months") is not None else "") + '</td>'
        f'<td>{_dir_html(p)}</td><td>{esc(lab(p["question_type"]))}</td>'
        f'<td>{esc(lab(p["model"]["type"]))}</td>'
        f'<td>{"valid" if temporality_valid(d, p) else "<span class=pred-nr>invalid</span>"}</td>'
        f'<td><a href="{cohort_href(d)}">{esc(short(d["name"]))}</a></td></tr>'
        for d, p in recs)
    return f'<div class="tablewrap"><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>'


def build_susceptibility_by_disease(cohorts, pmap, fmap, mmap):
    """One subsection per disease/trigger, listing that disease's predictors."""
    groups = [(pid, ds) for pid, ds in cohorts_by_pathogen(cohorts)
              if any(d.get("predictors") for d in ds)]
    if not groups:
        return ""
    toc = " · ".join(f'<a href="#s-{esc(pid)}">{esc(pmap.get(pid,{}).get("name",pid))}</a>' for pid, _ in groups)
    blocks = []
    for pid, ds in groups:
        pth = pmap.get(pid, {})
        recs = [(d, p) for d in ds for p in d.get("predictors", [])]
        nsig = sum(1 for _, p in recs if _sig(p))
        nnull = sum(1 for _, p in recs if p["estimate"]["direction"] == "null_result")
        nvalid = sum(1 for d, p in recs if temporality_valid(d, p))
        ncohorts = len({d["id"] for d, _ in recs})
        blocks.append(
            f'<h3 id="s-{esc(pid)}"><a href="pais-cohorts/disease/{esc(pid)}.html">{esc(pth.get("name", pid))}</a> '
            f'<span class="badge">{esc(lab(pth.get("class","")))}</span> '
            f'<span class="count">{len(recs)} predictor{"s" if len(recs)!=1 else ""}</span></h3>'
            f'<p class="meta">{nsig} significant · {nnull} null · {nvalid} temporality-valid · '
            f'from {ncohorts} cohort{"s" if ncohorts!=1 else ""}</p>'
            + _predictor_table(recs, pmap, fmap, mmap, lambda d: f'pais-cohorts/{esc(d["id"])}.html'))
    return f'<p class="meta">Jump to disease: {toc}</p>' + "".join(blocks)


def build_susceptibility_page(cohorts, pmap, mmap, fmap):
    """Standalone susceptibility/conversion-predictor analysis page (spec v2.1)."""
    n_pred = sum(len(d.get("predictors", [])) for _, d in cohorts)
    n_null = sum(1 for _, p in all_predictors(cohorts) if p["estimate"]["direction"] == "null_result")
    n_valid = sum(1 for d, p in all_predictors(cohorts) if temporality_valid(d, p))
    npct = round(100 * n_null / n_pred) if n_pred else 0
    body = f"""<div class="wrap">
<p class="back"><a href="pais-cohorts.html">← PAIS Cohort Database</a></p>
<h1>Susceptibility &amp; conversion predictors</h1>
<p class="lede">What predicts <em>who develops the chronic syndrome given infection</em> (conversion), with
emphasis on variables measured during the acute phase. Four causal questions — susceptibility to
infection, to severe acute disease, to conversion, and to non-recovery — are kept strictly separate
and never aggregated. A predictor measured after the outcome began is not counted as temporality-valid,
which excludes most of what the literature calls a "risk factor". No effect is pooled across pathogens:
different contrasts and adjustment sets are not comparable numbers.</p>
<p class="meta">{n_pred} predictors · {n_null} null results ({npct}%) · {n_valid} temporality-valid ·
harmonisation ruleset <a href="pais-severity-harmony-v1.md">{SEVERITY_RULESET}</a> ·
<a href="data/ref/factors.json">factor registry</a> · <a href="data/pais-predictors.csv">predictors CSV</a> ·
<a href="pais-susceptibility-factors-spec.md">spec</a> · CC BY 4.0</p>
<div class="warnbox">Null results are recorded, not dropped — they are {npct}% of this table and the reason to build
this rather than read a review. Factors are ranked by replication and temporality validity, never by
effect size.</div>
<div class="nav"><a href="#replication">Replication table</a><a href="#by-disease">By disease</a>
<a href="#factor-matrix">Factor × pathogen</a><a href="#acute-coverage">Acute-phase coverage</a>
<a href="#by-factor">By factor</a></div>

<h2 id="replication">Replication table</h2>
<p class="meta">One row per (factor or harmonised construct × outcome × question), sorted by how many
cohorts tested it. The two rows that stand out — acute severity (replicated) and the long tail tested
exactly once — are the finding.</p>
{build_replication_table(cohorts, pmap, fmap, mmap)}

<h2 id="by-disease">Predictors by disease</h2>
<p class="lede">A separate subsection for each disease/trigger — everything tested in that syndrome's cohorts,
significant and null, with contrast, measurement window and temporality per row.</p>
{build_susceptibility_by_disease(cohorts, pmap, fmap, mmap)}

<h2 id="factor-matrix">Factor × pathogen matrix</h2>
{build_factor_pathogen_matrix(cohorts, pmap, fmap)}

<h2 id="acute-coverage">Acute-phase coverage</h2>
{build_acute_coverage_matrix(cohorts, fmap)}

<h2 id="by-factor">Every estimate, by factor</h2>
<p class="meta">All estimates for each factor across cohorts, with contrast, measurement window, adjustment
set and temporality shown per row.</p>
{build_single_factor_detail(cohorts, pmap, fmap, mmap)}

<footer>
<p>Build {BUILD_VERSION}. Pre-rendered; works with JavaScript disabled. No pooled effect estimate appears
anywhere on this page or in the export, by design.</p>
<p><a href="pais-cohorts.html">← back to the cohort database</a> · per-syndrome predictors also appear on
each disease page.</p>
</footer>
</div>"""
    return html_doc("Susceptibility & conversion predictors — PAIS", body)


def build_main_page(cohorts, pmap, mmap, fmap, n_obs, warnings):
    n_pred = sum(len(d.get("predictors", [])) for _, d in cohorts)
    pclasses = sorted({d["pathogen_class"] for _, d in cohorts})
    designs = [x for x in DESIGN_ORDER if x in {d["design"] for _, d in cohorts}]
    controls = sorted({d["control_group"] for _, d in cohorts})
    toolbar = ('<div class="toolbar"><label>Search<input id="q" type="search" placeholder="cohort name…"></label>'
               + facet_select("pclass", "Pathogen class", pclasses) + facet_select("design", "Design", designs)
               + facet_select("control", "Control group", controls)
               + facet_select("denom", "Denominator", ["yes", "partial", "no", "unclear"])
               + '<span style="flex:1"></span><button class="btn sec" id="exp-json">Export JSON</button>'
               '<button class="btn sec" id="exp-csv">Cohorts CSV</button><button class="btn sec" id="exp-obs">Observations CSV</button>'
               '<button class="btn sec" id="exp-pred">Predictors CSV</button></div>')
    nav = ('<div class="nav"><a href="#cohort-table">Cohorts</a><a href="#by-disease">By disease</a>'
           '<a href="#measure-matrix">Measure × cohort</a>'
           '<a href="#comparable">Comparable sets</a><a href="pais-susceptibility.html">Predictors</a><a href="#gaps">Gap matrices</a></div>')
    m1 = build_gap_matrix(cohorts, pmap, designs, "design", "Gap matrix — pathogen × study design",
                          "Cell = number of cohorts. Red cells mark pathogen/design combinations with no cohort yet.")
    m2 = build_gap_matrix(cohorts, pmap, ACUTE_ORDER, "acute_phase_specimens", "Gap matrix — pathogen × acute-phase specimens",
                          "Acute-phase specimens are what make a cohort useful for mechanism studies.")
    m3 = build_measure_domain_gap(cohorts, pmap, mmap)
    m4 = build_gap_matrix(cohorts, pmap, ["yes_validated_instrument", "yes_single_item", "no", "unclear"], "pem_assessed",
                          "Gap matrix — PEM assessment × pathogen", "Whether each cohort assessed post-exertional malaise at all.")
    warn_html = ""
    if warnings:
        warn_html = ('<div class="okbox"><strong>Extension notes.</strong> ' +
                     "; ".join(esc(w) for w in warnings[:6]) + '</div>')
    body = f"""<div class="wrap">
<p class="back"><a href="index.html">← Research tracker</a></p>
<h1>PAIS Cohort Database</h1>
<p class="lede">A catalogue of post-acute infection syndrome <strong>cohorts</strong>, not patients. v2 stores every reported result — proportions, rates, means, paired tissue measurements, incidence, qualitative findings — as one polymorphic <em>Observation</em> keyed to a Measure registry, so structurally different cohorts sit in one queryable table. Comparability is a property of the data: two observations are directly comparable only if they share a comparability signature.</p>
<p class="meta">{len(cohorts)} cohorts · {n_obs} observations · schema v2.0.0 · <a href="data/pais-cohort.schema.json">schema</a> · <a href="data/ref/measures.json">measure registry</a> · <a href="pais-cohort-db-v2-heterogeneous-schema.md">spec</a> · <a href="pais-cohort-db-expansion-guide.md">how to expand</a> · <a href="data/v1/">v1 snapshot</a> · CC BY 4.0</p>
<div class="warnbox">Seed of {len(cohorts)} design-verified cohorts. Missingness is typed (not measured vs measured-not-reported vs reported-as-zero are different facts). No pooled estimates, no quality score: the comparability signature says comparable or not, and shows why.</div>
{warn_html}
{nav}{toolbar}
<h2 id="cohort-table">Cohort table</h2>
<p class="count" id="count">{len(cohorts)} cohorts</p>
{build_table(cohorts, pmap)}
<h2 id="by-disease">Cohorts by disease</h2>
<p class="lede">The same cohorts grouped by trigger (pathogen or vaccine), ordered by class. Each disease also has its own page. Flags mark evidentiary caveats.</p>
{build_by_disease(cohorts, pmap)}
<h2 id="measure-matrix">Measure × cohort matrix</h2>
{build_measure_matrix(cohorts, mmap)}
<h2 id="comparable">Comparable sets (one measure at a time)</h2>
<p class="lede">Every cohort that measured a given thing, grouped by comparability signature. Within a set the estimates are directly comparable; different sets are shown but never pooled, and the signature diff is the reason why.</p>
{build_comparable_views(cohorts, pmap, mmap)}
<h2 id="predictors">Susceptibility &amp; conversion predictors</h2>
<p class="lede">What predicts <em>who develops the chronic syndrome given infection</em> — with the acute-phase
emphasis, temporality rules, replication table and factor × pathogen matrix — is now a dedicated page.</p>
<p><a class="btn" href="pais-susceptibility.html">Open the susceptibility &amp; conversion analysis →</a>
<span class="meta">{n_pred} predictors · acute severity replicates across pathogens; sex and age conflict.</span></p>
<h2 id="estimate-comparability">Estimate-layer comparability</h2>
<p class="lede">Triangular matrix of joinable harmonized estimates: exact, instrument match, construct match, or an empty cell for no joinable evidence.</p>
{build_estimate_matrix(cohorts)}
<h2 id="gaps">Gap matrices</h2>
{m1}{m2}{m3}{m4}
<footer>
<p>Build {BUILD_VERSION}, compiled by <code>scripts/build_pais_cohorts.py</code>. All tables pre-rendered; work with JavaScript disabled. No analytics, no third-party assets.</p>
<p>Export: cohorts <a href="data/pais-cohorts-index.json">JSON</a> · <a href="data/pais-cohorts.csv">CSV</a> · observations <a href="data/pais-observations.csv">CSV</a> · predictors <a href="data/pais-predictors.csv">CSV</a>. v1.x preserved under <a href="data/v1/">/data/v1/</a>.</p>
</footer>
</div>{PAGE_JS}"""
    return html_doc("PAIS Cohort Database", body)


# ---------------------------------------------------------------- CSV
def cohort_csv_rows(cohorts, pmap):
    header = ["id", "name", "pathogen", "pathogen_class", "design", "denominator_defined", "control_group",
              "recruitment_source", "n_enrolled", "n_analysed", "max_followup_months", "pem_assessed",
              "specimens_collected", "acute_phase_specimens", "biobank_status", "n_publications", "n_observations"]
    rows = [header]
    for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()):
        rows.append([d["id"], d["name"], pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"]),
                     d["pathogen_class"], d["design"], d["denominator_defined"], d["control_group"],
                     d["recruitment_source"], d.get("n_enrolled"), d.get("n_analysed"), d.get("max_followup_months"),
                     d["pem_assessed"], d["specimens_collected"], d["acute_phase_specimens"], d["biobank_status"],
                     len(d["publications"]), len(d.get("observations", []))])
    return rows


def _slotval(x):
    return x.get("status") if is_missing(x) else x


def obs_csv_rows(cohorts, pmap, mmap):
    header = ["cohort_id", "pathogen", "observation_id", "measure_id", "measure_kind", "measure_domain",
              "measure_verbatim", "value_type", "percent_or_value", "ci_low", "ci_high", "n_assessed",
              "denominator_basis", "timepoint_months", "timepoint_band", "reference_period", "ascertainment",
              "comparator_group", "comparator_value", "effect_type", "effect_estimate", "comparability_signature",
              "publication_id", "source_locator", "extraction_method", "verified_on"]
    rows = [header]
    for d, o in all_observations(cohorts):
        m = mmap["_by_id"].get(o["measure_id"], {})
        v = o["value"]
        primary = {"proportion": v.get("percent"), "rate": v.get("rate"), "count": v.get("n"),
                   "mean_sd": v.get("mean"), "effect_only": v.get("estimate"), "qualitative": v.get("text"),
                   "paired_change": v.get("delta")}.get(v["type"])
        ci = v.get("ci") if isinstance(v.get("ci"), list) else [None, None]
        cmp = o["comparator"]
        cv = cmp.get("value")
        cval = (cv.get("percent") if isinstance(cv, dict) and cv.get("type") == "proportion" else
                (cv.get("rate") if isinstance(cv, dict) and cv.get("type") == "rate" else _slotval(cv) if is_missing(cv) else None))
        eff = cmp.get("effect") or {}
        rows.append([d["id"], pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"]), o["id"], o["measure_id"],
                     m.get("kind"), m.get("domain"), o.get("measure_verbatim"), v["type"],
                     _slotval(primary) if is_missing(primary) else primary, ci[0], ci[1],
                     _slotval(o["population"]["n_assessed"]), o["population"]["denominator_basis"],
                     o["timing"].get("timepoint_months"), o["timing"]["timepoint_band"], o["timing"]["reference_period"],
                     o["method"]["ascertainment"], cmp.get("group"), cval, eff.get("effect_type"), eff.get("estimate"),
                     comparability_signature(o), o["publication_id"], o["provenance"]["source_locator"],
                     o["provenance"]["extraction_method"], o["provenance"].get("verified_on")])
    return rows


def pred_csv_rows(cohorts, pmap, fmap, mmap):
    header = ["cohort_id", "pathogen", "predictor_id", "question_type", "factor_id", "factor_domain",
              "harmonised_construct", "factor_verbatim", "measurement_window", "temporality_valid",
              "factor_value_type", "contrast", "outcome_measure_id", "outcome_timepoint_months",
              "estimate_type", "estimate_value", "ci_low", "ci_high", "p_value", "direction", "significant",
              "model_type", "adjusted_for", "n_predictors_tested", "multiplicity_correction", "n_analysed",
              "analysis_status", "publication_id", "source_locator", "verified_on"]
    rows = [header]
    for d, p in all_predictors(cohorts):
        f = fmap["_by_id"].get(p["factor_id"], {})
        e = p["estimate"]
        rows.append([d["id"], pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"]), p["id"],
                     p["question_type"], p["factor_id"], f.get("domain"), f.get("harmonised_construct"),
                     p["factor_verbatim"], p["measurement_window"], temporality_valid(d, p),
                     p["factor_value_type"], p["contrast"], p["outcome_measure_id"], p.get("outcome_timepoint_months"),
                     e["type"], e.get("value"), e.get("ci_low"), e.get("ci_high"), e.get("p_value"),
                     e["direction"], e.get("significant"), p["model"]["type"],
                     "; ".join(p["model"].get("adjusted_for", [])), p["model"].get("n_predictors_tested"),
                     p["model"].get("multiplicity_correction"), p.get("n_analysed"), p.get("analysis_status"),
                     p["publication_id"], p["provenance"]["source_locator"], p["provenance"].get("verified_on")])
    return rows


def main():
    check_only = "--check" in sys.argv
    pathogens, instruments, measures = load_json(PATHOGENS), load_json(INSTRUMENTS), load_json(MEASURES)
    factors = load_json(FACTORS)
    ext_schemas = load_ext_schemas()
    cohorts = [(p, load_json(p)) for p in sorted(glob.glob(COHORT_GLOB))]
    if not cohorts:
        print("No cohort files found.", file=sys.stderr); sys.exit(1)

    errors, warnings = validate(cohorts, pathogens, instruments, measures, ext_schemas, factors)
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} error(s)):", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)
    n_obs = sum(len(d.get("observations", [])) for _, d in cohorts)
    n_pred = sum(len(d.get("predictors", [])) for _, d in cohorts)
    print(f"Validation OK: {len(cohorts)} cohorts, {n_obs} observations, {n_pred} predictors, "
          f"{sum(len(d['publications']) for _, d in cohorts)} publications. {len(warnings)} extension note(s).")
    for w in warnings:
        print("  note: " + w)
    # The additive estimate layer has its own schema and vocabulary resolution gate.
    subprocess.run([sys.executable, ESTIMATE_BUILD, "--check"], check=True)
    if check_only:
        return

    subprocess.run([sys.executable, ESTIMATE_BUILD], check=True)

    pmap = {p["id"]: p for p in pathogens["pathogens"]}
    imap = {i["id"]: i for i in instruments["instruments"]}
    mmap = {"_by_id": {m["id"]: m for m in measures["measures"]}, "_ordered": measures["measures"]}
    fmap = {"_by_id": {f["id"]: f for f in factors["factors"]}, "_ordered": factors["factors"]}

    index = {"schema_version": "2.0.0", "generated": BUILD_VERSION, "license": "CC BY 4.0",
             "harmonisation_ruleset": "pais-harmony-v1", "severity_ruleset": SEVERITY_RULESET,
             "pathogens": pathogens["pathogens"], "instruments": instruments["instruments"],
             "measures": measures["measures"], "factors": factors["factors"],
             "cohorts": [d for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower())]}
    with open(INDEX_OUT, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    def write_csv(path, rows):
        buf = io.StringIO(); w = csv.writer(buf)
        for r in rows:
            w.writerow(r)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(buf.getvalue())
    write_csv(CSV_OUT, cohort_csv_rows(cohorts, pmap))
    write_csv(OBS_CSV_OUT, obs_csv_rows(cohorts, pmap, mmap))
    write_csv(PRED_CSV_OUT, pred_csv_rows(cohorts, pmap, fmap, mmap))

    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(build_main_page(cohorts, pmap, mmap, fmap, n_obs, warnings))
    with open(os.path.join(ROOT, "pais-susceptibility.html"), "w", encoding="utf-8") as f:
        f.write(build_susceptibility_page(cohorts, pmap, mmap, fmap))
    os.makedirs(DETAIL_DIR, exist_ok=True)
    for _, d in cohorts:
        with open(os.path.join(DETAIL_DIR, f"{d['id']}.html"), "w", encoding="utf-8") as f:
            f.write(build_detail(d, pmap, imap, mmap, ext_schemas))
    disease_dir = os.path.join(DETAIL_DIR, "disease")
    os.makedirs(disease_dir, exist_ok=True)
    diseases = cohorts_by_pathogen(cohorts)
    for pid, ds in diseases:
        with open(os.path.join(disease_dir, f"{pid}.html"), "w", encoding="utf-8") as f:
            f.write(build_disease_page(pid, ds, pmap, mmap, fmap))
    print(f"Built: index, cohorts.csv, observations.csv, predictors.csv, pais-cohorts.html, "
          f"{len(cohorts)} detail pages, {len(diseases)} disease pages.")
    # The renderer writes complete HTML documents, so refresh the shared metadata
    # and sitemap only after every PAIS page has been emitted.
    seo = os.path.join(ROOT, "scripts", "build_site_seo.py")
    subprocess.run([sys.executable, seo], check=True)


if __name__ == "__main__":
    main()
