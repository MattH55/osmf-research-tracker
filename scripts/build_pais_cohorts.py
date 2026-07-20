#!/usr/bin/env python3
"""
Build + validate the PAIS cohort database.

Reads:  data/pais-cohort.schema.json, data/ref/*.json, data/cohorts/*.json
Writes: data/pais-cohorts-index.json     (compiled static index the frontend loads)
        data/pais-cohorts.csv            (one-click bulk cohort CSV, works with JS disabled)
        data/pais-symptom-findings.csv   (denormalised symptom-finding CSV, one row per finding)
        pais-cohorts.html                (cohort table + symptom matrix + gap matrices, pre-rendered)
        pais-cohorts/<id>.html           (pre-rendered cohort detail pages with symptom profile)

Validation is part of the build: schema (Draft 2020-12) + cross-reference checks.
Exit code is non-zero on any failure so CI can block a merge.

Usage:
    python scripts/build_pais_cohorts.py            # validate + build
    python scripts/build_pais_cohorts.py --check    # validate only (CI)
"""
from __future__ import annotations
import json, glob, os, sys, html, csv, io

# Deterministic build label (do NOT use a wall-clock date: the CI "artifacts in
# sync" check rebuilds and diffs, so output must be reproducible across days).
BUILD_VERSION = "1.1.0-seed"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA = os.path.join(ROOT, "data", "pais-cohort.schema.json")
COHORT_GLOB = os.path.join(ROOT, "data", "cohorts", "*.json")
PATHOGENS = os.path.join(ROOT, "data", "ref", "pathogens.json")
INSTRUMENTS = os.path.join(ROOT, "data", "ref", "instruments.json")
SYMPTOMS = os.path.join(ROOT, "data", "ref", "symptoms.json")

INDEX_OUT = os.path.join(ROOT, "data", "pais-cohorts-index.json")
CSV_OUT = os.path.join(ROOT, "data", "pais-cohorts.csv")
SYMPTOM_CSV_OUT = os.path.join(ROOT, "data", "pais-symptom-findings.csv")
HTML_OUT = os.path.join(ROOT, "pais-cohorts.html")
DETAIL_DIR = os.path.join(ROOT, "pais-cohorts")

# symptom domains, in display order for the matrices
DOMAIN_ORDER = ["fatigue_pem", "neurocognitive", "autonomic", "musculoskeletal", "sleep",
                "sensory", "gastrointestinal", "respiratory", "cardiovascular", "dermatologic",
                "neuropathic", "psychiatric", "reproductive", "constitutional", "other"]
# the four axes a comparability check compares two cohorts on (spec sec 5)
COMPARABILITY_AXES = ["ascertainment", "reference_period", "denominator_basis"]

# ---- human-readable labels for enum values -------------------------------
LABELS = {
    "prospective_inception": "Prospective (inception)",
    "prospective_non_inception": "Prospective (non-inception)",
    "retrospective_cohort": "Retrospective cohort",
    "cross_sectional": "Cross-sectional",
    "case_control": "Case-control",
    "registry_linkage": "Registry linkage",
    "self_controlled": "Self-controlled",
    "survey": "Survey",
    "none": "None", "unexposed_matched": "Unexposed (matched)",
    "unexposed_unmatched": "Unexposed (unmatched)",
    "seronegative_contacts": "Seronegative contacts",
    "household_contacts": "Household contacts", "other_disease": "Other-disease",
    "self_control": "Self-control", "healthy_convenience": "Healthy convenience",
    "yes": "Yes", "partial": "Partial", "no": "No", "unclear": "Unclear",
    "virus": "Virus", "bacterium": "Bacterium", "protozoan": "Protozoan",
    "vaccine": "Vaccine", "mixed": "Mixed", "unknown": "Unknown",
    "not_reported": "Not reported", "not_applicable": "N/A",
    "yes_validated_instrument": "Yes (validated instrument)",
    "yes_single_item": "Yes (single item)",
    # symptom-inventory scope
    "comprehensive_inventory": "Comprehensive inventory", "targeted_panel": "Targeted panel",
    "single_domain": "Single domain", "incidental": "Incidental",
    # symptom ascertainment
    "validated_instrument_threshold": "Validated instrument (threshold)",
    "structured_checklist": "Structured checklist", "open_ended_report": "Open-ended report",
    "clinician_assessed": "Clinician-assessed", "medical_record_code": "Medical-record code",
    "physical_exam": "Physical exam",
    # reference period
    "current": "Current", "past_7d": "Past 7 days", "past_30d": "Past 30 days",
    "past_3mo": "Past 3 months", "since_infection": "Since infection",
    "ever_since_onset": "Ever since onset",
    # denominator basis
    "enrolled": "Enrolled", "assessed_at_timepoint": "Assessed at timepoint",
    "symptomatic_subset": "Symptomatic subset", "responders": "Responders",
    # value precision
    "exact": "Exact", "approximate": "Approximate", "derived": "Derived",
    "digitised_from_figure": "Digitised from figure",
    # symptom domains
    "fatigue_pem": "Fatigue / PEM", "neurocognitive": "Neurocognitive", "autonomic": "Autonomic",
    "musculoskeletal": "Musculoskeletal", "sleep": "Sleep", "sensory": "Sensory",
    "gastrointestinal": "Gastrointestinal", "respiratory": "Respiratory",
    "cardiovascular": "Cardiovascular", "dermatologic": "Dermatologic", "neuropathic": "Neuropathic",
    "psychiatric": "Psychiatric", "reproductive": "Reproductive", "constitutional": "Constitutional",
    "other": "Other",
    # relation
    "sibling_analysis": "Sibling analysis", "overlapping_population": "Overlapping population",
    "parent": "Parent cohort", "child": "Child cohort",
}
# design columns for the gap matrix, in quality order (strongest first)
DESIGN_ORDER = ["prospective_inception", "prospective_non_inception", "retrospective_cohort",
                "registry_linkage", "self_controlled", "case_control", "cross_sectional", "survey"]
ACUTE_ORDER = ["yes", "no", "unclear", "not_applicable"]


def lab(v):
    if v is None:
        return "not reported"
    return LABELS.get(v, str(v).replace("_", " "))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def validate(cohorts, pathogens, instruments, symptoms):
    """Schema + cross-reference validation. Returns list of error strings."""
    from jsonschema import Draft202012Validator
    schema = load_json(SCHEMA)
    v = Draft202012Validator(schema)
    errors = []
    pathogen_ids = {p["id"] for p in pathogens["pathogens"]}
    instrument_ids = {i["id"] for i in instruments["instruments"]}
    symptom_ids = {s["id"] for s in symptoms["symptoms"]}
    seen_ids = set()
    for path, d in cohorts:
        name = os.path.basename(path)
        for e in sorted(v.iter_errors(d), key=lambda e: list(e.path)):
            errors.append(f"{name}: schema: {'/'.join(map(str, e.path))}: {e.message}")
        cid = d.get("id")
        if cid in seen_ids:
            errors.append(f"{name}: duplicate cohort id '{cid}'")
        seen_ids.add(cid)
        if d.get("pathogen_id") not in pathogen_ids:
            errors.append(f"{name}: pathogen_id '{d.get('pathogen_id')}' not in pathogens.json")
        for iid in d.get("instruments", []):
            if iid not in instrument_ids:
                errors.append(f"{name}: instrument '{iid}' not in instruments.json")
        pub_ids = {p["id"] for p in d.get("publications", [])}
        for fnd in d.get("findings", []):
            if fnd.get("publication_id") not in pub_ids:
                errors.append(f"{name}: finding '{fnd.get('id')}' publication_id "
                              f"'{fnd.get('publication_id')}' not among this cohort's publications")
            iid = fnd.get("instrument_id")
            if iid is not None and iid not in instrument_ids:
                errors.append(f"{name}: finding '{fnd.get('id')}' instrument_id '{iid}' not in instruments.json")
        # ---- SymptomFinding cross-references + v1.1 validation rules ----
        has_control = d.get("control_group") != "none"
        for sf in d.get("symptom_findings", []):
            sid = sf.get("id")
            if sf.get("publication_id") not in pub_ids:
                errors.append(f"{name}: symptom_finding '{sid}' publication_id "
                              f"'{sf.get('publication_id')}' not among this cohort's publications")
            if sf.get("symptom_id") not in symptom_ids:
                errors.append(f"{name}: symptom_finding '{sid}' symptom_id '{sf.get('symptom_id')}' not in symptoms.json")
            iid = sf.get("instrument_id")
            if iid is not None and iid not in instrument_ids:
                errors.append(f"{name}: symptom_finding '{sid}' instrument_id '{iid}' not in instruments.json")
            # Rule 1: mapping_note required when mapping_confidence != exact
            if sf.get("mapping_confidence") != "exact" and not sf.get("mapping_note"):
                errors.append(f"{name}: symptom_finding '{sid}' mapping_confidence is "
                              f"'{sf.get('mapping_confidence')}' but mapping_note is missing (rule 1)")
            # Rule 2: comparator_percent must be set (number or sentinel) when the cohort has controls
            if has_control and sf.get("comparator_percent") is None:
                errors.append(f"{name}: symptom_finding '{sid}': cohort has a control group, so "
                              f"comparator_percent must be a number or the sentinel 'not_reported', never null (rule 2)")
            # Rule 4: instrument_id required when ascertainment = validated_instrument_threshold
            if sf.get("ascertainment") == "validated_instrument_threshold" and not sf.get("instrument_id"):
                errors.append(f"{name}: symptom_finding '{sid}' ascertainment is validated_instrument_threshold "
                              f"but instrument_id is missing (rule 4)")
            # Rule 3: n_with_symptom / n_assessed must match percent to within rounding,
            # unless explicitly acknowledged via value_precision: approximate
            nw, na_, pct = sf.get("n_with_symptom"), sf.get("n_assessed"), sf.get("percent")
            if nw is not None and na_ and pct is not None and sf.get("value_precision") != "approximate":
                implied = 100.0 * nw / na_
                if abs(implied - pct) > 1.0:
                    errors.append(f"{name}: symptom_finding '{sid}': percent {pct} is inconsistent with "
                                  f"{nw}/{na_} ({implied:.1f}%); reconcile or set value_precision:approximate (rule 3)")
        # related_cohorts must point at real cohort ids (checked after all ids seen -> second pass)
    all_ids = {d["id"] for _, d in cohorts}
    for path, d in cohorts:
        for rel in d.get("related_cohorts", []):
            if rel.get("id") not in all_ids:
                errors.append(f"{os.path.basename(path)}: related_cohorts references unknown cohort id '{rel.get('id')}'")
    return errors


# ---- HTML helpers --------------------------------------------------------
def esc(s):
    return html.escape("" if s is None else str(s))


def na(v):
    """Render a value, marking not-reported/None distinctly for the UI."""
    if v is None:
        return '<span class="na">not reported</span>'
    return esc(lab(v))


CSS = """
:root{--bg:#fff;--fg:#1a1f26;--muted:#6b7480;--line:#e3e7ec;--card:#f7f9fb;
--accent:#0b6bcb;--warn:#b26a00;--good:#1a7f4b;--chip:#eef2f6;--zero:#faeaea;--zerofg:#a33}
@media (prefers-color-scheme:dark){:root{--bg:#0f1216;--fg:#e6e9ee;--muted:#9aa4b0;
--line:#252b33;--card:#161b21;--accent:#5aa2ea;--warn:#e0a24a;--good:#5cc68d;
--chip:#1c232b;--zero:#2a1c1c;--zerofg:#e08a8a}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
background:var(--bg);color:var(--fg)}
.wrap{max-width:1180px;margin:0 auto;padding:24px 18px 80px}
a{color:var(--accent)}h1{font-size:1.7rem;margin:.2em 0}
h2{font-size:1.2rem;margin:1.8em 0 .5em;border-bottom:1px solid var(--line);padding-bottom:.3em}
h3{font-size:1rem;margin:1.4em 0 .3em}
.lede{color:var(--muted);max-width:70ch}
.meta{font-size:.82rem;color:var(--muted);margin:.4em 0}
.chip{display:inline-block;background:var(--chip);border:1px solid var(--line);border-radius:999px;
padding:1px 9px;font-size:.78rem;margin:2px 3px 2px 0;white-space:nowrap}
.na{color:var(--muted);font-style:italic;font-size:.92em}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:end;margin:14px 0;padding:12px;
background:var(--card);border:1px solid var(--line);border-radius:10px}
.toolbar label{display:flex;flex-direction:column;font-size:.72rem;color:var(--muted);gap:2px}
.toolbar select,.toolbar input{font-size:.86rem;padding:4px 6px;background:var(--bg);color:var(--fg);
border:1px solid var(--line);border-radius:6px}
.btn{cursor:pointer;background:var(--accent);color:#fff;border:0;border-radius:6px;padding:6px 12px;font-size:.84rem}
.btn.sec{background:var(--chip);color:var(--fg);border:1px solid var(--line)}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:.86rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--card);position:sticky;top:0;cursor:pointer;white-space:nowrap}
tbody tr:hover{background:var(--card)}
.matrix td,.matrix th{text-align:center;padding:6px 8px}
.matrix th.row,.matrix td.row{text-align:left;font-weight:600}
.cell0{background:var(--zero);color:var(--zerofg)}
.cellN{font-weight:700}
.count{color:var(--muted);font-size:.85rem}
.back{font-size:.85rem}
.grid2{display:grid;grid-template-columns:180px 1fr;gap:2px 14px;font-size:.9rem}
.grid2 dt{color:var(--muted)}.grid2 dd{margin:0}
.warnbox{background:var(--zero);border:1px solid var(--line);border-left:3px solid var(--warn);
padding:10px 12px;border-radius:6px;margin:10px 0;font-size:.9rem}
footer{margin-top:40px;border-top:1px solid var(--line);padding-top:14px;font-size:.8rem;color:var(--muted)}
.pill{font-size:.72rem;padding:1px 7px;border-radius:999px;border:1px solid var(--line)}
.pill.good{color:var(--good)}.pill.no{color:var(--muted)}
.badge{font-size:.66rem;padding:0 5px;border-radius:4px;border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.nav{display:flex;flex-wrap:wrap;gap:6px;margin:12px 0}
.nav a{font-size:.82rem;padding:4px 10px;border:1px solid var(--line);border-radius:999px;background:var(--card);text-decoration:none}
.smx td,.smx th{text-align:center;padding:5px 7px;font-size:.8rem}
.smx th.row,.smx td.row{text-align:left}
.smx .dom{background:var(--card);font-weight:600;text-align:left}
.sv{color:#fff;border-radius:3px;padding:1px 4px;font-size:.76rem;display:inline-block;min-width:34px}
.cell-nm{color:var(--muted);opacity:.45}
.cell-nr{color:var(--warn)}
.legend{display:flex;flex-wrap:wrap;gap:12px;font-size:.76rem;color:var(--muted);margin:8px 0}
.legend span{display:inline-flex;align-items:center;gap:5px}
.legend i{width:14px;height:14px;border-radius:3px;display:inline-block;border:1px solid var(--line)}
.barrow{display:grid;grid-template-columns:230px 1fr;gap:8px;align-items:center;margin:3px 0;font-size:.82rem}
.barrow .lab{color:var(--fg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.barwrap{position:relative;background:var(--chip);border-radius:4px;height:18px}
.bar{position:absolute;left:0;top:0;height:18px;border-radius:4px;background:var(--accent)}
.bar.cmp{background:var(--muted);opacity:.55;height:8px;top:5px}
.barnum{position:relative;font-size:.72rem;padding-left:5px;line-height:18px}
.axis{color:var(--warn);font-style:normal}
"""


def attrition_html(d):
    """n_analysed / n_enrolled as a retention %, so selection bias is visible in the table."""
    ne, na_ = d.get("n_enrolled"), d.get("n_analysed")
    if not ne or na_ is None:
        return '<span class="na">n/r</span>', ""
    pct = round(100.0 * na_ / ne)
    cls = ' style="color:var(--warn)"' if pct < 70 else ""
    return f'<span{cls}>{na_}/{ne} ({pct}%)</span>', str(pct)


def cohort_row_cells(d, pmap):
    pth = pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"])
    n = d.get("n_analysed") or d.get("n_enrolled")
    spec = "banked" if d.get("specimens_collected") else "none"
    acute = d.get("acute_phase_specimens")
    spec_html = (f'<span class="pill good">banked</span>' if d.get("specimens_collected")
                 else '<span class="pill no">none</span>')
    if d.get("specimens_collected") and acute == "yes":
        spec_html += ' <span class="chip">acute-phase</span>'
    retention_html, retention_val = attrition_html(d)
    return {
        "name": f'<a href="pais-cohorts/{esc(d["id"])}.html">{esc(d["name"])}</a>',
        "pathogen": esc(pth), "pclass": lab(d["pathogen_class"]),
        "design": lab(d["design"]),
        "n": esc(n) if n is not None else '<span class="na">n/r</span>',
        "retention": retention_html,
        "fu": esc(d.get("max_followup_months")) if d.get("max_followup_months") is not None else '<span class="na">n/r</span>',
        "control": lab(d["control_group"]),
        "denom": lab(d["denominator_defined"]),
        "spec": spec_html,
        # data-* for JS filtering
        "attrs": (f'data-pclass="{esc(d["pathogen_class"])}" data-design="{esc(d["design"])}" '
                  f'data-control="{esc(d["control_group"])}" data-denom="{esc(d["denominator_defined"])}" '
                  f'data-spec="{esc(spec)}" data-acute="{esc(acute)}" '
                  f'data-n="{esc(n if n is not None else "")}" data-fu="{esc(d.get("max_followup_months") if d.get("max_followup_months") is not None else "")}" '
                  f'data-ret="{esc(retention_val)}" '
                  f'data-name="{esc(d["name"].lower())}"'),
    }


def build_table(cohorts, pmap):
    cols = [("name", "Cohort"), ("pathogen", "Pathogen"), ("design", "Design"),
            ("n", "N"), ("retention", "Analysed/Enrolled"), ("fu", "Max follow-up (mo)"),
            ("control", "Control group"), ("denom", "Denominator"), ("spec", "Specimens")]
    head = "".join(f'<th data-sort="{k}">{esc(t)}</th>' for k, t in cols)
    rows = []
    for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()):
        c = cohort_row_cells(d, pmap)
        tds = "".join(f"<td>{c[k]}</td>" for k, _ in cols)
        rows.append(f'<tr {c["attrs"]}>{tds}</tr>')
    return (f'<div class="tablewrap"><table id="cohorts"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def build_matrix(cohorts, pmap, col_order, col_key, title, desc):
    # rows = pathogens present, cols = col_order values
    used_pathogens = []
    for _, d in cohorts:
        if d["pathogen_id"] not in used_pathogens:
            used_pathogens.append(d["pathogen_id"])
    counts = {}
    for _, d in cohorts:
        counts.setdefault(d["pathogen_id"], {})
        key = d.get(col_key)
        counts[d["pathogen_id"]][key] = counts[d["pathogen_id"]].get(key, 0) + 1
    head = '<th class="row"></th>' + "".join(f"<th>{esc(lab(c))}</th>" for c in col_order)
    body = []
    for pid in used_pathogens:
        pname = pmap.get(pid, {}).get("name", pid)
        cells = [f'<td class="row">{esc(pname)}</td>']
        for c in col_order:
            n = counts.get(pid, {}).get(c, 0)
            cls = "cell0" if n == 0 else "cellN"
            cells.append(f'<td class="{cls}">{n if n else ""}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<h3>{esc(title)}</h3><p class="meta">{esc(desc)}</p>'
            f'<div class="tablewrap"><table class="matrix"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def facet_select(name, label, values):
    opts = '<option value="">all</option>' + "".join(
        f'<option value="{esc(v)}">{esc(lab(v))}</option>' for v in values)
    return f'<label>{esc(label)}<select data-facet="{esc(name)}">{opts}</select></label>'


# ---- symptom-frequency views (v1.1) --------------------------------------
def _shade(pct):
    """Background style for a symptom-prevalence cell, shaded by magnitude."""
    a = 0.30 + 0.65 * (max(0.0, min(100.0, pct)) / 100.0)
    return f'background:rgba(37,99,235,{a:.2f});color:#fff'


def _short(name):
    """Short cohort label: text before the first parenthesis, else the whole name."""
    return name.split(" (")[0].strip()


def _sf_latest(sfs):
    """Pick the symptom-finding at the latest timepoint (the most chronic estimate)."""
    return sorted(sfs, key=lambda s: s.get("timepoint_months") or 0)[-1]


def _cmp_str(sf):
    cp = sf.get("comparator_percent")
    if cp is None:
        return ""
    if cp == "not_reported":
        return ' <span class="axis" title="controls exist but this symptom was not reported in them">(vs controls: n/r)</span>'
    grp = f" {lab(sf['comparator_group'])}" if sf.get("comparator_group") else ""
    return f' <span class="na">(vs{grp}: {cp}%)</span>'


def build_symptom_matrix(cohorts, smap):
    """4.1 Symptom (rows, grouped by domain) x cohort (cols). Three empty states."""
    # columns = cohorts that reported at least one symptom finding
    cols = [d for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()) if d.get("symptom_findings")]
    if not cols:
        return ""
    # index findings by (cohort_id, symptom_id)
    by = {}
    used_symptoms = set()
    for d in cols:
        for sf in d["symptom_findings"]:
            by.setdefault((d["id"], sf["symptom_id"]), []).append(sf)
            used_symptoms.add(sf["symptom_id"])
    head = '<th class="row">Symptom</th>' + "".join(
        f'<th>{esc(_short(d["name"]))}<br><span class="badge">{esc(lab(smap["_pathogen"].get(d["id"],"")))}</span> '
        f'<span class="badge">{esc(lab(d["symptom_inventory_scope"]))}</span></th>' for d in cols)
    body = []
    for dom in DOMAIN_ORDER:
        dom_syms = [s for s in smap["_by_domain"].get(dom, []) if s["id"] in used_symptoms]
        if not dom_syms:
            continue
        body.append(f'<tr><td class="dom" colspan="{len(cols)+1}">{esc(lab(dom))}</td></tr>')
        for s in dom_syms:
            cells = [f'<td class="row">{esc(s["label"])}</td>']
            for d in cols:
                sfs = by.get((d["id"], s["id"]))
                if sfs:
                    sf = _sf_latest(sfs)
                    tt = f'{sf["percent"]}% at {sf.get("timepoint_months")}mo; {lab(sf["ascertainment"])}'
                    cells.append(f'<td><span class="sv" style="{_shade(sf["percent"])}" title="{esc(tt)}">{sf["percent"]}%</span></td>')
                elif d["symptom_inventory_scope"] == "comprehensive_inventory":
                    cells.append('<td class="cell-nr" title="comprehensive inventory: measured but not tabulated here / reported absent">·</td>')
                else:
                    cells.append('<td class="cell-nm" title="not measured in this cohort">–</td>')
            body.append("<tr>" + "".join(cells) + "</tr>")
    legend = ('<div class="legend">'
              '<span><i style="background:rgba(37,99,235,.7)"></i> value = reported prevalence (shaded by magnitude)</span>'
              '<span><i style="background:transparent;border-color:var(--warn)"></i> <span class="cell-nr">·</span> measured (comprehensive inventory) but not reported here</span>'
              '<span><i style="background:transparent"></i> <span class="cell-nm">–</span> not measured in this cohort</span>'
              '</div>')
    return (f'<p class="meta">Cells show the reported prevalence at the latest available timepoint for that '
            f'symptom; hover for timepoint and ascertainment. Timepoints differ between cells — use the '
            f'cross-pathogen view below to compare like with like. Column badges show pathogen and symptom-inventory scope.</p>'
            f'{legend}<div class="tablewrap"><table class="matrix smx"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def _comparability_warning(findings):
    """Inline, specific warning naming any axis on which the compared findings differ (spec sec 5)."""
    diffs = []
    for axis in COMPARABILITY_AXES:
        vals = sorted({f.get(axis) for f in findings})
        if len(vals) > 1:
            diffs.append(f"{axis.replace('_',' ')}: " + " vs ".join(lab(v) for v in vals))
    scopes = sorted({f["_scope"] for f in findings})
    if len(scopes) > 1:
        diffs.append("symptom-inventory scope: " + " vs ".join(lab(v) for v in scopes))
    if not diffs:
        return ""
    items = "".join(f"<li>{esc(x)}</li>" for x in diffs)
    return (f'<div class="warnbox"><strong>Not directly comparable.</strong> The cohorts below differ on: '
            f'<ul style="margin:.3em 0 0 1.1em">{items}</ul></div>')


def build_single_symptom_views(cohorts, pmap, smap):
    """4.2 One block per symptom measured in >=2 cohorts: point estimates + comparator, grouped by pathogen."""
    rows_by_symptom = {}
    for _, d in cohorts:
        for sf in d.get("symptom_findings", []):
            rec = dict(sf)
            rec["_cohort"] = d
            rec["_scope"] = d["symptom_inventory_scope"]
            rows_by_symptom.setdefault(sf["symptom_id"], []).append(rec)
    blocks = []
    toc = []
    for sid in [s["id"] for s in smap["symptoms"]]:
        recs = rows_by_symptom.get(sid, [])
        if len(recs) < 2:
            continue
        s = smap["_by_id"][sid]
        recs.sort(key=lambda r: (pmap.get(r["_cohort"]["pathogen_id"], {}).get("name", ""), r.get("timepoint_months") or 0))
        toc.append(f'<a href="#sym-{esc(sid)}">{esc(s["label"])}</a>')
        bars = []
        for r in recs:
            d = r["_cohort"]
            pth = pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"])
            label = f'{_short(d["name"])} · {esc(pth)} · {r.get("timepoint_months")}mo'
            cmpbar = ""
            cp = r.get("comparator_percent")
            if isinstance(cp, (int, float)):
                cmpbar = f'<div class="bar cmp" style="width:{min(100.0,float(cp)):.1f}%"></div>'
            bars.append(
                f'<div class="barrow"><div class="lab" title="{esc(d["name"])}">{label}</div>'
                f'<div class="barwrap"><div class="bar" style="width:{min(100.0,float(r["percent"])):.1f}%"></div>{cmpbar}'
                f'<span class="barnum">{r["percent"]}%{_cmp_str(r)}</span></div></div>')
        warn = _comparability_warning(recs)
        blocks.append(f'<h3 id="sym-{esc(sid)}">{esc(s["label"])}'
                      f' <span class="badge">{esc(lab(s["domain"]))}</span></h3>{warn}{"".join(bars)}')
    if not blocks:
        return ""
    toc_html = '<p class="meta">Jump to symptom: ' + " · ".join(toc) + "</p>"
    return (toc_html + '<p class="meta">Solid bar = prevalence in the affected cohort; faint bar = the '
            'control-group comparator where one was reported. No pooling — each estimate stands alone.</p>'
            + "".join(blocks))


def build_symptom_gap_matrices(cohorts, pmap, smap):
    """4.4 domain x pathogen (cohorts measuring anything in domain) and 4.5 pem_assessed x pathogen."""
    used_pathogens = []
    for _, d in cohorts:
        if d["pathogen_id"] not in used_pathogens:
            used_pathogens.append(d["pathogen_id"])
    # domain x pathogen
    domains_present = [dm for dm in DOMAIN_ORDER
                       if any(smap["_by_id"].get(sf["symptom_id"], {}).get("domain") == dm
                              for _, d in cohorts for sf in d.get("symptom_findings", []))]
    dom_counts = {}
    for _, d in cohorts:
        doms = {smap["_by_id"].get(sf["symptom_id"], {}).get("domain") for sf in d.get("symptom_findings", [])}
        for dm in doms:
            dom_counts.setdefault((d["pathogen_id"], dm), set()).add(d["id"])
    head = '<th class="row"></th>' + "".join(f"<th>{esc(lab(dm))}</th>" for dm in domains_present)
    body = []
    for pid in used_pathogens:
        cells = [f'<td class="row">{esc(pmap.get(pid,{}).get("name",pid))}</td>']
        for dm in domains_present:
            n = len(dom_counts.get((pid, dm), set()))
            cells.append(f'<td class="{"cell0" if n==0 else "cellN"}">{n if n else ""}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    m3 = (f'<h3>Gap matrix 3 — symptom domain × pathogen</h3>'
          f'<p class="meta">Cell = number of cohorts that measured <em>anything</em> in that domain for that pathogen. '
          f'The empty cells are the point: outside SARS-CoV-2, whole domains (autonomic, PEM) are barely measured.</p>'
          f'<div class="tablewrap"><table class="matrix"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')
    # pem_assessed x pathogen
    pem_order = ["yes_validated_instrument", "yes_single_item", "no", "unclear"]
    pem_counts = {}
    for _, d in cohorts:
        pem_counts.setdefault((d["pathogen_id"], d["pem_assessed"]), 0)
        pem_counts[(d["pathogen_id"], d["pem_assessed"])] += 1
    head2 = '<th class="row"></th>' + "".join(f"<th>{esc(lab(x))}</th>" for x in pem_order)
    body2 = []
    for pid in used_pathogens:
        cells = [f'<td class="row">{esc(pmap.get(pid,{}).get("name",pid))}</td>']
        for x in pem_order:
            n = pem_counts.get((pid, x), 0)
            cells.append(f'<td class="{"cell0" if n==0 else "cellN"}">{n if n else ""}</td>')
        body2.append("<tr>" + "".join(cells) + "</tr>")
    m4 = (f'<h3>Gap matrix 4 — post-exertional malaise assessment × pathogen</h3>'
          f'<p class="meta">Whether each cohort assessed PEM at all. That the field\'s landmark inception cohort '
          f'(Dubbo) never measured PEM is itself a finding, visible here rather than buried.</p>'
          f'<div class="tablewrap"><table class="matrix"><thead><tr>{head2}</tr></thead><tbody>{"".join(body2)}</tbody></table></div>')
    return m3 + m4


def build_cohort_symptom_profile(d, smap):
    """4.3 sorted horizontal bars of a cohort's symptom findings, grouped by domain."""
    sfs = d.get("symptom_findings", [])
    if not sfs:
        return '<p class="na">No symptom-frequency findings recorded for this cohort yet.</p>'
    by_dom = {}
    for sf in sfs:
        dom = smap["_by_id"].get(sf["symptom_id"], {}).get("domain", "other")
        by_dom.setdefault(dom, []).append(sf)
    out = []
    for dom in DOMAIN_ORDER:
        group = by_dom.get(dom)
        if not group:
            continue
        out.append(f'<h3>{esc(lab(dom))}</h3>')
        for sf in sorted(group, key=lambda x: -x["percent"]):
            s = smap["_by_id"].get(sf["symptom_id"], {})
            cp = sf.get("comparator_percent")
            cmpbar = f'<div class="bar cmp" style="width:{min(100.0,float(cp)):.1f}%"></div>' if isinstance(cp, (int, float)) else ""
            label = f'{esc(s.get("label", sf["symptom_id"]))} · {sf.get("timepoint_months")}mo'
            verbatim = f' <span class="badge" title="verbatim in source">“{esc(sf["symptom_verbatim"])}”</span>'
            out.append(
                f'<div class="barrow"><div class="lab">{label}{verbatim}</div>'
                f'<div class="barwrap"><div class="bar" style="width:{min(100.0,float(sf["percent"])):.1f}%"></div>{cmpbar}'
                f'<span class="barnum">{sf["percent"]}%{_cmp_str(sf)}</span></div></div>')
    return ("".join(out) + '<p class="meta">Bars show reported prevalence; the verbatim wording from each paper is '
            'preserved (hover) and never normalised. Faint bar = control comparator where reported.</p>')


def symptom_finding_csv_rows(cohorts, pmap, smap):
    header = ["cohort_id", "cohort_name", "pathogen", "symptom_id", "symptom_domain", "symptom_verbatim",
              "mapping_confidence", "ascertainment", "instrument_id", "severity_threshold", "reference_period",
              "timepoint_months", "denominator_basis", "n_with_symptom", "n_assessed", "percent",
              "ci_low", "ci_high", "value_precision", "comparator_percent", "comparator_n", "comparator_group",
              "effect_estimate", "effect_type", "p_value", "publication_id", "source_locator", "last_verified"]
    rows = [header]
    for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()):
        for sf in d.get("symptom_findings", []):
            dom = smap["_by_id"].get(sf["symptom_id"], {}).get("domain", "")
            rows.append([
                d["id"], d["name"], pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"]),
                sf["symptom_id"], dom, sf["symptom_verbatim"], sf["mapping_confidence"], sf["ascertainment"],
                sf.get("instrument_id"), sf.get("severity_threshold"), sf["reference_period"],
                sf["timepoint_months"], sf["denominator_basis"], sf.get("n_with_symptom"), sf["n_assessed"],
                sf["percent"], sf.get("ci_low"), sf.get("ci_high"), sf["value_precision"],
                sf.get("comparator_percent"), sf.get("comparator_n"), sf.get("comparator_group"),
                sf.get("effect_estimate"), sf.get("effect_type"), sf.get("p_value"),
                sf["publication_id"], sf["source_locator"], sf["last_verified"]])
    return rows


PAGE_JS = r"""
<script>
(function(){
 var tb=document.getElementById('cohorts'); if(!tb) return;
 var rows=[].slice.call(tb.tBodies[0].rows);
 var facets=[].slice.call(document.querySelectorAll('[data-facet]'));
 var q=document.getElementById('q');
 function apply(){
   var f={}; facets.forEach(function(s){ if(s.value) f[s.dataset.facet]=s.value; });
   var term=(q&&q.value||'').toLowerCase();
   var shown=0;
   rows.forEach(function(r){
     var ok=true;
     for(var k in f){ if(r.getAttribute('data-'+k)!==f[k]){ ok=false; break; } }
     if(ok&&term){ ok=r.getAttribute('data-name').indexOf(term)>-1; }
     r.style.display=ok?'':'none'; if(ok)shown++;
   });
   var c=document.getElementById('count'); if(c)c.textContent=shown+' of '+rows.length+' cohorts';
 }
 facets.forEach(function(s){s.addEventListener('change',apply);});
 if(q)q.addEventListener('input',apply);
 // sorting
 var ths=[].slice.call(tb.tHead.rows[0].cells); var dir={};
 ths.forEach(function(th){ th.addEventListener('click',function(){
   var key=th.dataset.sort, num=(key==='n'||key==='fu');
   dir[key]=!dir[key]; var s=dir[key]?1:-1;
   var vis=rows.slice();
   vis.sort(function(a,b){
     var av=a.getAttribute('data-'+ (key==='name'?'name':key))||'';
     var bv=b.getAttribute('data-'+ (key==='name'?'name':key))||'';
     if(key==='n'||key==='fu'){ av=parseFloat(a.getAttribute('data-'+key)); bv=parseFloat(b.getAttribute('data-'+key));
       if(isNaN(av))av=-1; if(isNaN(bv))bv=-1; return (av-bv)*s; }
     if(key==='pathogen'||key==='design'||key==='control'||key==='denom'){ av=a.cells[0].textContent; bv=b.cells[0].textContent; }
     return av<bv?-s:av>bv?s:0;
   });
   var body=tb.tBodies[0]; vis.forEach(function(r){body.appendChild(r);});
 });});
 // export
 function dl(name,txt,type){ var b=new Blob([txt],{type:type}); var u=URL.createObjectURL(b);
   var a=document.createElement('a'); a.href=u; a.download=name; a.click(); URL.revokeObjectURL(u); }
 var ej=document.getElementById('exp-json'), ec=document.getElementById('exp-csv'), es=document.getElementById('exp-scsv');
 if(ej)ej.addEventListener('click',function(){ fetch('data/pais-cohorts-index.json').then(function(r){return r.text();}).then(function(t){dl('pais-cohorts-index.json',t,'application/json');}); });
 if(ec)ec.addEventListener('click',function(){ fetch('data/pais-cohorts.csv').then(function(r){return r.text();}).then(function(t){dl('pais-cohorts.csv',t,'text/csv');}); });
 if(es)es.addEventListener('click',function(){ fetch('data/pais-symptom-findings.csv').then(function(r){return r.text();}).then(function(t){dl('pais-symptom-findings.csv',t,'text/csv');}); });
 apply();
})();
</script>
"""


def build_main_page(cohorts, pmap, smap, generated):
    pclasses = sorted({d["pathogen_class"] for _, d in cohorts})
    designs = [x for x in DESIGN_ORDER if x in {d["design"] for _, d in cohorts}]
    controls = sorted({d["control_group"] for _, d in cohorts})
    denoms = ["yes", "partial", "no", "unclear"]
    toolbar = (
        '<div class="toolbar">'
        '<label>Search<input id="q" type="search" placeholder="cohort name…"></label>'
        + facet_select("pclass", "Pathogen class", pclasses)
        + facet_select("design", "Design", designs)
        + facet_select("control", "Control group", controls)
        + facet_select("denom", "Denominator", denoms)
        + facet_select("spec", "Specimens", ["banked", "none"])
        + facet_select("acute", "Acute-phase spec.", ["yes", "no", "unclear", "not_applicable"])
        + '<span style="flex:1"></span>'
        '<button class="btn sec" id="exp-json">Export JSON</button>'
        '<button class="btn sec" id="exp-csv">Export cohorts CSV</button>'
        '<button class="btn sec" id="exp-scsv">Export symptom CSV</button>'
        '</div>'
    )
    nav = ('<div class="nav">'
           '<a href="#cohort-table">Cohort table</a>'
           '<a href="#symptom-matrix">Symptom × cohort</a>'
           '<a href="#symptom-compare">Cross-pathogen symptoms</a>'
           '<a href="#gap-matrices">Gap matrices</a></div>')
    table = build_table(cohorts, pmap)
    n_sf = sum(len(d.get("symptom_findings", [])) for _, d in cohorts)
    smx = build_symptom_matrix(cohorts, smap)
    ssv = build_single_symptom_views(cohorts, pmap, smap)
    sgm = build_symptom_gap_matrices(cohorts, pmap, smap)
    m1 = build_matrix(cohorts, pmap, designs, "design",
                      "Gap matrix — pathogen × study design",
                      "Cell = number of cohorts. Red (empty) cells mark pathogen/design combinations where no cohort yet exists — the evidence gaps this database exists to expose.")
    m2 = build_matrix(cohorts, pmap, ACUTE_ORDER, "acute_phase_specimens",
                      "Gap matrix — pathogen × acute-phase specimens banked",
                      "Cell = number of cohorts. Acute-phase specimens (drawn during infection, before the outcome is known) are what make a cohort useful for mechanism studies; empty cells show where they are missing.")
    body = f"""<div class="wrap">
<p class="back"><a href="index.html">← Research tracker</a></p>
<h1>PAIS Cohort Database</h1>
<p class="lede">A catalogue of <strong>cohorts</strong> (study populations followed for post-acute infection syndrome outcomes), not patients and not publications. The unit of record is the cohort, so that one cohort's many papers do not overstate how much independent evidence exists. The point of the database is to make the <em>design</em> of each study — denominator, controls, timepoints, specimens — machine-readable, so the incomparability of the literature and its gaps become visible.</p>
<p class="meta">{len(cohorts)} cohorts · seed release · every field human-verified against source · data licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a> · <a href="data/pais-cohort.schema.json">schema</a> · <a href="pais-cohort-database-spec.md">spec</a></p>
<div class="warnbox">This is a <strong>seed</strong> of {len(cohorts)} design-verified cohorts ({n_sf} symptom-frequency findings), not a complete census. It deliberately mixes strong designs (prospective inception cohorts with unexposed controls) and weak ones (self-selected online surveys) so the gap matrices below are honest. Contributions are made as pull requests; schema validation runs in CI and blocks merges that break it. No pooled estimates or quality scores are computed — filter the design fields and judge for yourself.</div>
{nav}
{toolbar}
<h2 id="cohort-table">Cohort table</h2>
<p class="count" id="count">{len(cohorts)} cohorts</p>
{table}
<h2 id="symptom-matrix">Symptom × cohort matrix</h2>
<p class="lede">Symptom prevalence is the field's most-quoted and least-comparable number. Each cell carries its own ascertainment method, reference period and denominator basis (see the symptom CSV); the columns are not interchangeable.</p>
{smx}
<h2 id="symptom-compare">Cross-pathogen symptom comparison</h2>
<p class="lede">One symptom at a time, every cohort that measured it, with its control comparator — the empirical version of the shared-core-versus-pathogen-specific question. Each block flags the axes on which the cohorts are not directly comparable.</p>
{ssv}
<h2 id="gap-matrices">Gap matrices</h2>
{m1}
{m2}
{sgm}
<footer>
<p>Build {generated}, compiled by <code>scripts/build_pais_cohorts.py</code>. Cohort table, detail pages and all matrices are pre-rendered and work with JavaScript disabled; filtering, sorting and export are progressive enhancements. No analytics, no third-party fonts or scripts.</p>
<p>Bulk export: cohorts <a href="data/pais-cohorts-index.json">JSON</a> · <a href="data/pais-cohorts.csv">CSV</a> · symptom findings <a href="data/pais-symptom-findings.csv">CSV</a>. Reference tables: <a href="data/ref/symptoms.json">symptoms</a>, <a href="data/ref/pathogens.json">pathogens</a>, <a href="data/ref/instruments.json">instruments</a>. Per-cohort permalinks under <code>pais-cohorts/&lt;id&gt;.html</code>.</p>
</footer>
</div>{PAGE_JS}"""
    return html_doc("PAIS Cohort Database", body)


def html_doc(title, body):
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>{body}</body></html>")


def dl_list(items):
    return "<dl class=grid2>" + "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in items) + "</dl>"


def build_detail(d, pmap, imap, smap):
    pth = pmap.get(d["pathogen_id"], {})
    identity = dl_list([
        ("Cohort id", f"<code>{esc(d['id'])}</code>"),
        ("Aliases", ", ".join(map(esc, d.get("aliases", []))) or '<span class="na">none</span>'),
        ("Outbreak / event", na(d.get("outbreak_event"))),
        ("Pathogen", f"{esc(pth.get('name', d['pathogen_id']))} ({lab(d['pathogen_class'])})"),
        ("Exposure ascertainment", na(d.get("exposure_ascertainment"))),
    ])
    design = dl_list([
        ("Design", lab(d["design"])),
        ("Denominator defined", lab(d["denominator_defined"])),
        ("Denominator method", na(d.get("denominator_method"))),
        ("Recruitment source", lab(d["recruitment_source"])),
        ("Time zero", esc(d.get("time_zero_definition")) + f' ({lab(d.get("time_zero_precision"))})'),
        ("Control group", lab(d["control_group"])),
        ("Matching variables", ", ".join(map(esc, d.get("control_matching_variables", []))) or '<span class="na">none</span>'),
    ])
    size = dl_list([
        ("Source population", na(d.get("n_source_population"))),
        ("Enrolled", na(d.get("n_enrolled"))),
        ("Analysed", na(d.get("n_analysed"))),
        ("Max follow-up (months)", na(d.get("max_followup_months"))),
        ("Follow-up points", ", ".join(f"{f['months']}mo" for f in d.get("followups", [])) or '<span class="na">not reported</span>'),
    ])
    instruments = ", ".join(imap.get(i, {}).get("name", i) for i in d.get("instruments", [])) or '<span class="na">none listed</span>'
    measure = dl_list([
        ("Instruments", instruments),
        ("Case definition", lab(d["case_definition"])),
        ("PEM assessed", lab(d["pem_assessed"])),
        ("Objective measures", ", ".join(lab(x) for x in d.get("objective_measures", [])) or '<span class="na">none</span>'),
    ])
    spec = dl_list([
        ("Specimens collected", "Yes" if d.get("specimens_collected") else "No"),
        ("Specimen types", ", ".join(map(esc, d.get("specimen_types", []))) or '<span class="na">none</span>'),
        ("Acute-phase specimens", lab(d["acute_phase_specimens"])),
        ("Storage", na(d.get("storage"))),
        ("Biobank status", lab(d["biobank_status"])),
        ("Consent for future use", lab(d.get("consent_future_use"))),
        ("External access", lab(d.get("external_access"))),
    ])
    related = d.get("related_cohorts", [])
    related_html = (", ".join(f'<a href="{esc(r["id"])}.html">{esc(r["id"])}</a> ({lab(r["relation"])})' for r in related)
                    if related else '<span class="na">none recorded</span>')
    prov = dl_list([
        ("Registration", na(d.get("registration_id"))),
        ("Funders", ", ".join(map(esc, d.get("funders", []))) or '<span class="na">not reported</span>'),
        ("Conflicts", na(d.get("conflicts"))),
        ("Data availability", na(d.get("data_availability"))),
        ("Related cohorts", related_html),
        ("Symptom-inventory scope", lab(d.get("symptom_inventory_scope"))
            + (f' ({d["n_symptoms_queried"]} symptoms queried)' if d.get("n_symptoms_queried") else "")),
        ("Last verified", f'{esc(d.get("last_verified"))} — {esc(d.get("verified_by"))}'),
    ])
    # findings table
    if d.get("findings"):
        fh = "".join(f"<th>{esc(h)}</th>" for h in
                     ["Outcome", "Timepoint (mo)", "n/N", "%", "95% CI", "Effect", "As worded", "Source"])
        frows = []
        for f in d["findings"]:
            if f.get("n_with_outcome") is not None and f.get("n_assessed") is not None:
                nN = f"{f['n_with_outcome']}/{f['n_assessed']}"
            elif f.get("n_assessed") is not None:
                nN = f"N={f['n_assessed']}"
            else:
                nN = '<span class="na">n/r</span>'
            if f.get("percent") is not None:
                pct = f"{f['percent']}%"
                if f.get("n_with_outcome") is None and f.get("n_assessed") is not None:
                    pct += ' <span class="na">(numerator not reported)</span>'
            else:
                pct = '<span class="na">n/r</span>'
            ci = (f"{f['ci_low']}–{f['ci_high']}" if f.get("ci_low") is not None and f.get("ci_high") is not None else "")
            eff = (f"{lab(f['effect_type'])} {f['effect_estimate']}" if f.get("effect_estimate") is not None and f.get("effect_type") != "none" else "")
            frows.append("<tr>" + "".join(f"<td>{c}</td>" for c in [
                lab(f["outcome"]), na(f.get("timepoint_months")), nN, pct, esc(ci) or "—",
                esc(eff) or "—", esc(f.get("outcome_verbatim")), esc(f.get("source_locator"))]) + "</tr>")
        findings = (f'<div class="tablewrap"><table><thead><tr>{fh}</tr></thead>'
                    f'<tbody>{"".join(frows)}</tbody></table></div>')
    else:
        findings = '<p class="na">No (non-symptom) findings extracted yet — contributions welcome via pull request.</p>'
    symptom_profile = build_cohort_symptom_profile(d, smap)
    # publications
    pubs = []
    for p in d.get("publications", []):
        ident = (f'PMID <a href="https://pubmed.ncbi.nlm.nih.gov/{esc(p["pmid"])}/">{esc(p["pmid"])}</a>' if p.get("pmid") else "")
        if p.get("doi"):
            ident += (" · " if ident else "") + f'DOI <a href="https://doi.org/{esc(p["doi"])}">{esc(p["doi"])}</a>'
        primary = ' <span class="chip">primary cohort paper</span>' if p.get("is_primary_cohort_paper") else ""
        oa = ' <span class="pill good">open access</span>' if p.get("open_access") else ""
        pubs.append(f'<li>{esc(p.get("authors"))} ({esc(p["year"])}). <strong>{esc(p["title"])}</strong>. '
                    f'<em>{esc(p.get("journal"))}</em>. {ident}{primary}{oa}</li>')
    pubs_html = "<ul>" + "".join(pubs) + "</ul>"
    notes = f'<div class="warnbox"><strong>Design notes & limitations.</strong> {esc(d.get("notes"))}</div>' if d.get("notes") else ""
    body = f"""<div class="wrap">
<p class="back"><a href="../pais-cohorts.html">← All cohorts</a></p>
<h1>{esc(d['name'])}</h1>
<p class="meta"><a href="../data/cohorts/{esc(d['id'])}.json">source record (JSON)</a> · licensed <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a></p>
{notes}
<h2>Identity & trigger</h2>{identity}
<h2>Design</h2>{design}
<h2>Size & attrition</h2>{size}
<h2>Measurement</h2>{measure}
<h2>Biospecimens</h2>{spec}
<h2>Symptom profile</h2>{symptom_profile}
<h2>Other findings</h2>{findings}
<h2>Publications</h2>{pubs_html}
<h2>Provenance &amp; verification</h2>{prov}
<footer><p>PAIS Cohort Database · <a href="../pais-cohorts.html">back to table</a></p></footer>
</div>"""
    return html_doc(f"{d['name']} — PAIS Cohort", body)


def cohort_to_csv_rows(cohorts, pmap):
    header = ["id", "name", "pathogen", "pathogen_class", "design", "denominator_defined",
              "control_group", "recruitment_source", "n_enrolled", "n_analysed",
              "max_followup_months", "case_definition", "pem_assessed", "specimens_collected",
              "acute_phase_specimens", "biobank_status", "external_access", "n_publications", "n_findings"]
    rows = [header]
    for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower()):
        rows.append([
            d["id"], d["name"], pmap.get(d["pathogen_id"], {}).get("name", d["pathogen_id"]),
            d["pathogen_class"], d["design"], d["denominator_defined"], d["control_group"],
            d["recruitment_source"], d.get("n_enrolled"), d.get("n_analysed"),
            d.get("max_followup_months"), d["case_definition"], d["pem_assessed"],
            d["specimens_collected"], d["acute_phase_specimens"], d["biobank_status"],
            d.get("external_access"), len(d.get("publications", [])), len(d.get("findings", []))])
    return rows


def build_symptom_index(symptoms, cohorts):
    by_domain = {}
    for s in symptoms["symptoms"]:
        by_domain.setdefault(s["domain"], []).append(s)
    return {
        "symptoms": symptoms["symptoms"],
        "_by_id": {s["id"]: s for s in symptoms["symptoms"]},
        "_by_domain": by_domain,
        "_pathogen": {d["id"]: d["pathogen_class"] for _, d in cohorts},
    }


def main():
    check_only = "--check" in sys.argv
    pathogens = load_json(PATHOGENS)
    instruments = load_json(INSTRUMENTS)
    symptoms = load_json(SYMPTOMS)
    cohorts = [(p, load_json(p)) for p in sorted(glob.glob(COHORT_GLOB))]
    if not cohorts:
        print("No cohort files found.", file=sys.stderr); sys.exit(1)

    errors = validate(cohorts, pathogens, instruments, symptoms)
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} error(s)):", file=sys.stderr)
        for e in errors:
            print("  - " + e, file=sys.stderr)
        sys.exit(1)
    n_sf = sum(len(d.get('symptom_findings', [])) for _, d in cohorts)
    print(f"Validation OK: {len(cohorts)} cohorts, "
          f"{sum(len(d.get('publications', [])) for _, d in cohorts)} publications, "
          f"{sum(len(d.get('findings', [])) for _, d in cohorts)} findings, "
          f"{n_sf} symptom findings.")
    if check_only:
        return

    pmap = {p["id"]: p for p in pathogens["pathogens"]}
    imap = {i["id"]: i for i in instruments["instruments"]}
    smap = build_symptom_index(symptoms, cohorts)
    generated = BUILD_VERSION

    # compiled index
    index = {
        "schema_version": "1.1.0",
        "generated": generated,
        "license": "CC BY 4.0",
        "pathogens": pathogens["pathogens"],
        "instruments": instruments["instruments"],
        "symptoms": symptoms["symptoms"],
        "cohorts": [d for _, d in sorted(cohorts, key=lambda c: c[1]["name"].lower())],
    }
    with open(INDEX_OUT, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # bulk CSVs (cohorts + denormalised symptom findings)
    def write_csv(path, rows):
        buf = io.StringIO()
        w = csv.writer(buf)
        for r in rows:
            w.writerow(r)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(buf.getvalue())
    write_csv(CSV_OUT, cohort_to_csv_rows(cohorts, pmap))
    write_csv(SYMPTOM_CSV_OUT, symptom_finding_csv_rows(cohorts, pmap, smap))

    # main page
    with open(HTML_OUT, "w", encoding="utf-8") as f:
        f.write(build_main_page(cohorts, pmap, smap, generated))

    # detail pages
    os.makedirs(DETAIL_DIR, exist_ok=True)
    for _, d in cohorts:
        with open(os.path.join(DETAIL_DIR, f"{d['id']}.html"), "w", encoding="utf-8") as f:
            f.write(build_detail(d, pmap, imap, smap))

    print(f"Built: {os.path.relpath(INDEX_OUT, ROOT)}, {os.path.relpath(CSV_OUT, ROOT)}, "
          f"{os.path.relpath(SYMPTOM_CSV_OUT, ROOT)}, {os.path.relpath(HTML_OUT, ROOT)}, "
          f"{len(cohorts)} detail pages in {os.path.relpath(DETAIL_DIR, ROOT)}/")


if __name__ == "__main__":
    main()
