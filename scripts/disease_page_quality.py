#!/usr/bin/env python3
"""Data-quality pass for chronic-disease-interventions/*.html.

Search Console showed these pages ranking with visible errors: trial lists
full of studies about other conditions (mitral valves on the GERD page),
placebo and device arms ranked as "medicines" ("Vehicle solution", "Scalp
cooling"), and code names shown as investigational after the drug was
approved (CTP-543 is deuruxolitinib, FDA-approved 2024). This script fixes
the three causes in place:

  1. Trials: the Clinical Trials section is rebuilt from ClinicalTrials.gov
     with drug / biologic / supplement treatment or prevention trials only,
     and each trial's first-listed (main) condition must match the page's
     condition. Observational studies, device, behavioural and diagnostic
     studies are left out.
  2. Medicines: disease-level agent rows that are placebo, vehicle, sham,
     devices, procedures or measurements are removed (NON_DRUG below).
  3. Code names: development codes are mapped to their INN using
     data/drug_code_aliases.json (built from ChEMBL synonyms with
     --resolve-aliases), and marked Approved when ChEMBL max_phase is 4.

The counts in the section subtitles are recomputed; run
scripts/seo_disease_pages.py afterwards so titles and descriptions use them.

    python scripts/disease_page_quality.py --resolve-aliases   # refresh the alias file (network: ChEMBL)
    python scripts/disease_page_quality.py                     # all pages (network: ClinicalTrials.gov)
    python scripts/disease_page_quality.py --only gerd-gastroesophageal-reflux-disease.html
    python scripts/disease_page_quality.py --no-trials         # agents + aliases only, no network

The trial filter is also used by biomarker_pipeline/generate_disease_pages.py.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ROOT / "chronic-disease-interventions"
ALIASES_PATH = ROOT / "data" / "drug_code_aliases.json"
CT_API = "https://clinicaltrials.gov/api/v2/studies"
CHEMBL_SEARCH = "https://www.ebi.ac.uk/chembl/api/data/molecule/search.json"
UA = {"User-Agent": "OSMF-ResearchTracker/1.0 (research@opensourcemed.info)"}

# Trial arms that are not medicines: placebo / vehicle / sham comparators,
# devices, procedures, behavioural programmes, diagnostics and measurements.
# Shared with the main site's research-note generator.
NON_DRUG = re.compile(
    r"placebo|vehicle|sham|dummy|\bsaline\b|active comparator|device|system\b|stimulat|\bTMS\b|rTMS|tDCS|\bTENS\b"
    r"|neuromodulat|neurofeedback|questionnaire|nutricosmetic|cosmetic|scalp cooling|cooling|cold cap|cryotherap"
    r"|microneedl|\bREVIAN\b|red light|low[- ]level light"
    r"|usual care|standard of care|best medical care|primary care|conservative treatment|^\W|^no intervention"
    r"|masking|counsel|program|session|booster|education|video|dashboard|\bapp\b|application|implant|hearing aid"
    r"|laser|light therapy|photobiomod|acupunct|acupress|massage|yoga|exercise|training|rehabilit|physiotherap"
    r"|fasciatherap|manual therapy|surgery|surgical|fusion|stent|ablation|catheter|transplant|radiotherapy|radiation"
    r"|scale\b|score\b|assessment|interview|survey|otoscopy|tympanometr|audiometr|emission|pure tone|loudness"
    r"|measurement|imaging|\bMRI\b|\bPET\b|x-ray|ultrasound|biopsy|collection|sample|sampling|analy[sz]er|\btest\b|testing"
    r"|screening|diet\b|lifestyle|behavio|cognitive|mindfulness|psychotherap|support group|coaching|\btele(?:health|medicine|phone|monitor|rehab)|ehealth"
    r"|fitbit|wearable|sensor|monitoring|home visit|intention|expectation|chronotype|facilitation|wipe\b"
    r"|halotherapy|salt therapy|endotoxin|hemodialysis|haemodialysis|hemoperfusion|filter\b|lenire|bimodal|applicator",
    re.I)

# A row that names a recognisable drug is kept even when it also mentions a
# placebo, implant or test product ("Rabeprazole, placebo", "Goserelin
# implant", "Test Product (tiotropium ...)").
DRUG_HINT = re.compile(
    r"[a-z](?:prazole|prazan|mab|tinib|ciclib|parib|rafenib|gliflozin|gliptin|glutide|tide|relin|relix|tropium|terol|sone|olone"
    r"|statin|sartan|pril|olol|dipine|semide|thiazide|xaban|gatran|parin|mycin|cillin|cycline|floxacin|azole|conazole|vir"
    r"|caine|profen|coxib|lukast|setron|pitant|triptan|gepant|lizumab|ximab|zumab|umab|cept|kinra|nercept|dronate|calcet"
    r"|lutamide|tamide|platin|taxel|rubicin|trexate|imus|olimus|fenib|zomib)\b", re.I)


def is_non_drug(name: str) -> bool:
    return bool(NON_DRUG.search(name)) and not DRUG_HINT.search(name)


CODE_NAME = re.compile(r"^[A-Z]{1,6}[- ]?\d{2,7}[A-Z]?$")

# Extra wording for the main-condition check, keyed by the page H1. Terms are
# matched as substrings of the trial's first-listed condition after
# normalisation (lower case, punctuation -> space).
CONDITION_SYNONYMS = {
    "GERD (Gastroesophageal Reflux Disease)": [
        "gerd", "gastroesophageal reflux", "gastro esophageal reflux", "gastro oesophageal reflux",
        "gastrooesophageal reflux", "reflux disease", "reflux esophagitis", "reflux oesophagitis",
        "erosive esophagitis", "erosive oesophagitis", "nerd"],
    "Alzheimer's Disease and Other Dementias": [
        "alzheimer", "dementia", "mild cognitive impairment", "cognitive decline", "frontotemporal"],
    "Alopecia Areata": ["alopecia areata"],
    "Inflammatory Bowel Disease (Crohn's/UC)": ["crohn", "ulcerative colitis", "inflammatory bowel", "ibd", "pouchitis"],
    "Inflammatory Bowel Disease (Crohn's / UC)": ["crohn", "ulcerative colitis", "inflammatory bowel", "ibd", "pouchitis"],
    "NAFLD / MASH (Metabolic-Associated Steatohepatitis)": [
        "nafld", "nash", "mash", "masld", "steatohepatitis", "fatty liver", "hepatic steatosis"],
    "Chronic Kidney Disease": ["chronic kidney", "ckd", "renal insufficiency, chronic", "chronic renal", "diabetic kidney",
                               "diabetic nephropathy", "kidney failure, chronic", "end stage renal", "esrd"],
    "Lyme Disease / Post-Treatment Lyme Disease Syndrome (PTLDS)": ["lyme", "borreli", "ptlds"],
    "Long COVID / Post-Acute Sequelae of COVID-19 (PASC)": ["long covid", "post covid", "post-covid", "pasc",
                                                            "post acute covid", "post-acute sequelae"],
    "Hyperlipidemia / Dyslipidemia": ["lipid", "cholesterol", "lipoprotein", "dyslipid", "hyperlipid"],
    "Obesity (Severe / Morbid)": ["obesity", "overweight"],
    "Obesity": ["obesity", "overweight"],
    "Type 2 Diabetes": ["type 2 diabetes", "t2d", "diabetes mellitus, type 2", "type ii diabetes", "type 2 diabetes mellitus"],
    "Type 1 Diabetes": ["type 1 diabetes", "t1d", "diabetes mellitus, type 1", "type i diabetes"],
    "Hypertension": ["hypertension", "high blood pressure"],
    "COPD": ["copd", "chronic obstructive"],
    "Heart Failure": ["heart failure", "cardiac failure", "hfref", "hfpef"],
    "Major Depressive Disorder": ["depress"],
    "Multiple Sclerosis": ["multiple sclerosis"],
    "Rheumatoid Arthritis": ["rheumatoid arthritis"],
    "Migraine": ["migraine"],
    "Anxiety Disorders": ["anxiety", "panic disorder", "social phobia", "phobic"],
    "HIV/AIDS": ["hiv", "aids", "human immunodeficiency"],
    "Cervical Cancer": ["cervical cancer", "cervical carcinoma", "cervix", "cervical neoplasm", "cervical squamous"],
    "Age-Related Hearing Loss (Presbycusis)": ["hearing loss", "presbycusis", "presbyacusis"],
    "Metabolic Syndrome": ["metabolic syndrome", "insulin resistance"],
    "Huntington's Disease": ["huntington"],
    "Tension Headache / Chronic Daily Headache": ["tension type headache", "tension headache", "chronic daily headache",
                                                  "medication overuse headache", "chronic headache"],
    "Chronic Venous Insufficiency / Venous Leg Ulcers": ["venous insufficiency", "venous ulcer", "venous leg ulcer",
                                                         "varicose", "venous disease"],
}


# Trials that list the condition but treat a symptom of it (psychosis,
# agitation, sleep) rather than the disease itself. Matched against the
# trial title and main condition, only on the pages listed.
CONDITION_EXCLUDE = {
    "Alzheimer's Disease and Other Dementias": re.compile(
        r"psychos|agitation|aggress|behaviou?r|neuropsychiatric|apathy|sleep|insomnia|depress|delirium|anxiety"
        r"|caregiver|pain|imaging|\bPET\b|tracer|diagnos", re.I),
}
# Trials started before this year only fill the list when too few recent ones exist.
RECENT_FROM = date.today().year - 10
MIN_RECENT = 8


def norm(s: str) -> str:
    s = html.unescape(s or "").lower().replace("’", "'").replace("'s ", "s ").replace("'", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return f" {s.strip()} "


def condition_terms(name: str) -> list[str]:
    """Terms a trial's main condition must contain to count for this page."""
    terms = list(CONDITION_SYNONYMS.get(name, []))
    base = re.split(r"\s+and other\s+", name, flags=re.I)[0]
    bare = re.sub(r"\s*\([^)]*\)", "", base).strip()
    terms += [base, bare]
    terms += [p.strip() for p in bare.split(" / ")]
    for inner in re.findall(r"\(([^)]*)\)", name):
        terms += [t.strip() for t in re.split(r"\s*/\s*", inner)]
    # British spellings rarely match the registry
    terms += [t.replace("oe", "e").replace("ae", "e") for t in list(terms)]
    out, seen = [], set()
    for t in terms:
        n = norm(t).strip()
        if len(n) >= 3 and n not in seen and n not in {"other", "chronic", "severe", "refractory", "morbid"}:
            seen.add(n)
            out.append(n)
    return out


def main_condition_matches(conditions: list[str], terms: list[str]) -> bool:
    if not conditions:
        return False
    first = norm(conditions[0])
    # short acronyms (GERD, CKD, MASH) must match as whole words
    return any((f" {t} " in first) if len(t) <= 5 else (t in first) for t in terms)


def _get_json(url: str, timeout: int = 60, tries: int = 3):
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.loads(r.read())
        except Exception as e:  # network hiccup: back off and retry
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def fetch_drug_trials(name: str, max_results: int = 15, query_terms: list[str] | None = None) -> list[dict]:
    """Drug / biologic / supplement treatment or prevention trials whose main
    condition matches the page, most recently updated first."""
    terms = condition_terms(name)
    exclude = CONDITION_EXCLUDE.get(name)
    queries = query_terms or [name, re.sub(r"\s*\([^)]*\)", "", re.split(r"\s+and other\s+", name, flags=re.I)[0]).strip()]
    queries += [q for q in re.findall(r"\(([^)]*)\)", name) if "/" not in q]
    queries += [part.strip() for part in queries[1].split(" / ")] if " / " in queries[1] else []
    seen, out = set(), []

    def finish(rows: list[dict]) -> list[dict]:
        def year(r: dict) -> int:
            m = re.match(r"(\d{4})", r.get("start") or "")
            return int(m.group(1)) if m else 0
        recent = [r for r in rows if year(r) >= RECENT_FROM]
        older = [r for r in rows if year(r) < RECENT_FROM]
        keep = recent if len(recent) >= MIN_RECENT else recent + older
        return keep[:max_results]

    for q in dict.fromkeys(q for q in queries if q):
        params = {
            "query.cond": q,
            "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING,COMPLETED",
            "filter.advanced": ("AREA[StudyType]INTERVENTIONAL AND AREA[InterventionType](DRUG OR BIOLOGICAL OR DIETARY_SUPPLEMENT) "
                                "AND AREA[DesignPrimaryPurpose](TREATMENT OR PREVENTION)"),
            "format": "json", "pageSize": "100", "sort": "LastUpdatePostDate:desc",
            "fields": "NCTId,BriefTitle,OverallStatus,Phase,StartDate,BriefSummary,Condition,InterventionType,InterventionName",
        }
        try:
            data = _get_json(CT_API + "?" + urllib.parse.urlencode(params))
        except Exception as e:
            print(f"  ClinicalTrials.gov query failed for {q!r}: {e}", file=sys.stderr)
            continue
        for s in data.get("studies", []):
            p = s.get("protocolSection", {})
            ident, status = p.get("identificationModule", {}), p.get("statusModule", {})
            nct = ident.get("nctId", "")
            conds = p.get("conditionsModule", {}).get("conditions", [])
            ivs = p.get("armsInterventionsModule", {}).get("interventions", [])
            drug_ivs = [i for i in ivs if i.get("type") in ("DRUG", "BIOLOGICAL", "DIETARY_SUPPLEMENT")
                        and not is_non_drug(i.get("name", ""))]
            if not nct or nct in seen or not drug_ivs or not main_condition_matches(conds, terms):
                continue
            if exclude and (exclude.search(ident.get("briefTitle", "")) or exclude.search(conds[0])):
                continue
            seen.add(nct)
            out.append({
                "nct_id": nct, "title": ident.get("briefTitle", ""), "status": status.get("overallStatus", ""),
                "phase": ", ".join(p.get("designModule", {}).get("phases", [])) or "N/A",
                "start": (status.get("startDateStruct") or {}).get("date", ""),
                "summary": re.sub(r"\s+", " ", p.get("descriptionModule", {}).get("briefSummary", "") or "")[:300],
                "condition": conds[0],
            })
        if len(finish(out)) >= max_results and sum(1 for r in out if (r["start"] or "0")[:4] >= str(RECENT_FROM)) >= max_results:
            break
    return finish(out)


# ── rendering (matches the restyled light-theme markup) ─────────────────────

STATUS_STYLE = {
    "RECRUITING": "background:#e7f7f0;color:#047857;border:1px solid #bfe9d6",
    "ACTIVE_NOT_RECRUITING": "background:#eaf0ff;color:#1d4ed8;border:1px solid #cfdcff",
}
DEFAULT_STYLE = "background:#f7f8fc;color:#6b7194;border:1px solid #e6e8f2"


def esc(s: str) -> str:
    return html.escape(s or "", quote=True)


def phase_label(raw: str) -> str:
    """'PHASE2, PHASE3' -> '2/3'; 'EARLY_PHASE1' -> 'Early 1'; 'NA' -> 'N/A'."""
    parts = [p.strip().upper() for p in (raw or "").split(",") if p.strip()]
    out = []
    for p in parts:
        if p in ("NA", "N/A"):
            continue
        m = re.fullmatch(r"(EARLY_)?PHASE_?(\d)", p)
        out.append(("Early " if m and m.group(1) else "") + m.group(2) if m else p.title())
    return "/".join(out) or "N/A"


def relabel_phases(markup: str) -> str:
    return re.sub(r'(class="trial-phase">Phase: )([^<]*)(<)', lambda m: m.group(1) + phase_label(m.group(2)) + m.group(3), markup)


def render_trials(trials: list[dict], name: str, today: str) -> str:
    sub = (f'\n  <p class="section-sub">\n    Drug, biologic and supplement trials (treatment or prevention) from '
           f'<a href="https://clinicaltrials.gov" target="_blank" rel="noopener">ClinicalTrials.gov</a> whose main condition is '
           f'{esc(name)}: recruiting, active or completed, most recently updated first. Data retrieved {today}.\n  </p>\n  ')
    if not trials:
        return sub + '<p class="no-data">No recruiting, active or completed drug trials with this main condition were found on ClinicalTrials.gov.</p>'
    cards = []
    for t in trials:
        nct, summ = esc(t["nct_id"]), esc(t.get("summary", ""))
        label = t.get("status", "").replace("_", " ").title()
        style = STATUS_STYLE.get(t.get("status", "").upper(), DEFAULT_STYLE)
        cards.append(f"""<div class="trial-card">
          <div class="trial-header">
            <a href="https://clinicaltrials.gov/study/{nct}" target="_blank" rel="noopener" class="trial-title">{esc(t["title"])}</a>
            <span style="{style};padding:2px 10px;border-radius:999px;font-size:11.5px;font-weight:650;white-space:nowrap;flex:none">{esc(label)}</span>
          </div>
          <div class="trial-meta">
            <span class="trial-nct">{nct}</span>
            <span class="trial-phase">Phase: {esc(phase_label(t["phase"]))}</span>
            {f'<span class="trial-start">Started: {esc(t["start"])}</span>' if t.get("start") else ""}
          </div>
          {f'<p class="trial-summary">{summ}{"..." if len(t.get("summary", "")) >= 300 else ""}</p>' if summ else ""}
        </div>""")
    return sub + '\n        <div class="trial-list">' + "\n        ".join(cards) + "\n  </div>"


# ── code-name aliases (ChEMBL) ──────────────────────────────────────────────

def load_aliases() -> dict:
    try:
        return json.loads(ALIASES_PATH.read_text(encoding="utf-8")).get("aliases", {})
    except Exception:
        return {}


def code_key(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", s.upper())


SALT_WORDS = {"sulfate", "sulphate", "hydrochloride", "dihydrochloride", "phosphate", "mesylate", "dimesylate", "maleate",
              "sodium", "potassium", "calcium", "tosylate", "citrate", "fumarate", "hemifumarate", "tartrate", "bitartrate",
              "besylate", "succinate", "acetate", "hydrobromide", "monohydrate", "dihydrate", "hydrate", "anhydrous",
              "magnesium", "meglumine", "trihydrate", "malate", "lactate", "bromide", "chloride", "edisylate"}
CHEMBL_MOLECULE = "https://www.ebi.ac.uk/chembl/api/data/molecule.json"


def strip_salt(name: str) -> str:
    words = name.split()
    while len(words) > 1 and words[-1].lower() in SALT_WORDS:
        words.pop()
    return " ".join(words)


def resolve_aliases(codes: list[str]) -> dict:
    """code -> {inn, chembl_id, approved, first_approval, source}.

    A code is mapped only when it is an exact ChEMBL synonym of molecules
    that share one INN (salt forms folded together) and that INN is not
    itself a code. approved = ChEMBL max_phase 4 for the INN or any of its
    salt forms (e.g. CTP-543 -> DEURUXOLITINIB, max_phase 4 via
    DEURUXOLITINIB PHOSPHATE, first approval 2024). Unresolved codes are omitted."""
    out = {}
    fields = "molecule_chembl_id,pref_name,max_phase,first_approval"
    for i, code in enumerate(sorted(set(codes))):
        spaced = re.sub(r"^([A-Z]+)-?(?=\d)", lambda m: m.group(1) + " ", code)
        dashed = re.sub(r"^([A-Z]+)-?(?=\d)", lambda m: m.group(1) + "-", code)
        variants = dict.fromkeys([code, code.replace("-", ""), dashed, spaced])
        hits = []
        try:
            for v in variants:
                d = _get_json(CHEMBL_MOLECULE + "?" + urllib.parse.urlencode(
                    {"molecule_synonyms__molecule_synonym__iexact": v, "only": fields}), timeout=60)
                hits += [m for m in d.get("molecules", []) if m.get("pref_name")]
                if hits:
                    break
        except Exception as e:
            print(f"  ChEMBL lookup failed for {code}: {e}", file=sys.stderr)
            continue
        inns = {strip_salt(h["pref_name"]).upper() for h in hits}
        if len(inns) != 1:
            continue  # none, or ambiguous: leave the code as is
        inn = inns.pop()
        if code_key(inn) == code_key(code) or CODE_NAME.match(inn) or re.search(r"\d", inn):
            continue  # ChEMBL only knows it by a code
        try:
            forms = _get_json(CHEMBL_MOLECULE + "?" + urllib.parse.urlencode(
                {"pref_name__istartswith": inn, "only": fields, "limit": 50}), timeout=60).get("molecules", [])
        except Exception:
            forms = []
        forms = [f for f in forms if f.get("pref_name") and strip_salt(f["pref_name"]).upper() == inn] or hits
        phase = max(float(f.get("max_phase") or 0) for f in forms + hits)
        approvals = [f.get("first_approval") for f in forms + hits if f.get("first_approval")]
        parent = min(hits, key=lambda h: len(h["pref_name"]))
        out[code] = {"inn": inn.lower(), "chembl_id": parent["molecule_chembl_id"], "approved": phase >= 4,
                     "first_approval": min(approvals) if approvals else None}
        if (i + 1) % 25 == 0:
            print(f"  {i + 1} codes checked, {len(out)} resolved", flush=True)
        time.sleep(0.1)
    return out


# ── page processing ─────────────────────────────────────────────────────────

AGENT_CARD = re.compile(
    r'[ \t]*<div class="gene-card agent-card">\s*<div class="agent-head">\s*<p class="agent-name">(.*?)</p>\s*</div>'
    r'\s*<p class="agent-meta">(.*?)</p>\s*</div>\n?', re.S)
APPROVED_SPAN = '<span class="osmf-pill osmf-pill--ok">Approved</span>'


def h1_of(markup: str) -> str:
    m = re.search(r"<h1[^>]*>(.*?)</h1>", markup, re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def clean_agents(markup: str, aliases: dict) -> tuple[str, int, int]:
    removed = renamed = 0

    def fix(m: re.Match) -> str:
        nonlocal removed, renamed
        name_html, meta = m.group(1), m.group(2)
        label = html.unescape(re.sub(r"<span.*?</span>", "", name_html, flags=re.S)).strip()
        if is_non_drug(label):
            removed += 1
            return ""
        a = aliases.get(label)
        if a and CODE_NAME.match(label):
            renamed += 1
            name_html = name_html.replace(label, f"{esc(a['inn'])} ({esc(label)})", 1)
            if a.get("approved") and "Approved</span>" not in meta:
                # meta starts with the phase label (or nothing) before the first &middot;
                meta = re.sub(r"^\s*([^&<]*?)\s*&middot;", lambda _m: f"\n            {APPROVED_SPAN} &middot;", meta, count=1)
        return m.group(0).replace(m.group(1), name_html, 1).replace(m.group(2), meta, 1)

    markup = AGENT_CARD.sub(fix, markup)
    return markup, removed, renamed


def recount(markup: str) -> str:
    """Refresh '<n> agents shown … — <k> not found by the gene-target search above.'"""
    i = markup.find("Agents Found By Disease-Level Search")
    if i < 0:
        return markup
    section = markup[i:]
    cards = AGENT_CARD.findall(section)
    n = len(cards)
    k = sum(1 for name, _ in cards if "NOT in gene-target list" in name)
    section = re.sub(r"\d+ agents shown \(approved or with trial evidence\)( &mdash; \d+ not found by the gene-target search above\.)?",
                     f"{n} agents shown (approved or with trial evidence)" + (f" &mdash; {k} not found by the gene-target search above." if k else ""),
                     section, count=1)
    return markup[:i] + section


def process(page: Path, aliases: dict, trials: bool, today: str) -> str:
    markup = page.read_text(encoding="utf-8")
    original = markup
    name = h1_of(markup)
    notes = []
    markup, removed, renamed = clean_agents(markup, aliases)
    if removed or renamed:
        markup = recount(markup)
        notes.append(f"{removed} non-drug rows removed, {renamed} code names mapped")
    if trials:
        markup = markup.replace('<h2 class="section-title">Clinical Trials</h2>', '<h2 class="section-title" id="trials">Clinical Trials</h2>', 1)
        m = re.search(r'(<h2 class="section-title" id="trials">Clinical Trials</h2>)(.*?)(\s*<hr class="section-divider">)', markup, re.S)
        if m:
            found = fetch_drug_trials(name)
            markup = markup[:m.start(2)] + render_trials(found, name, today) + markup[m.end(2):]
            notes.append(f"{len(found)} matching drug trials")
    markup = relabel_phases(markup)
    if markup != original:
        page.write_text(markup, encoding="utf-8")
    return "; ".join(notes) or ("phases relabelled" if markup != original else "unchanged")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="file names inside chronic-disease-interventions/")
    ap.add_argument("--no-trials", action="store_true", help="skip the ClinicalTrials.gov refresh")
    ap.add_argument("--resolve-aliases", action="store_true", help="rebuild data/drug_code_aliases.json from ChEMBL")
    args = ap.parse_args()
    pages = [p for p in sorted(PAGES.glob("*.html")) if p.name != "index.html"]
    if args.only:
        pages = [p for p in pages if p.name in set(args.only)]
    pages = [p for p in pages if 'content="noindex' not in p.read_text(encoding="utf-8")]
    if args.resolve_aliases:
        codes = set()
        for p in sorted(PAGES.glob("*.html")):
            for name_html, _ in AGENT_CARD.findall(p.read_text(encoding="utf-8")):
                label = html.unescape(re.sub(r"<span.*?</span>", "", name_html, flags=re.S)).strip()
                if CODE_NAME.match(label):
                    codes.add(label)
        print(f"resolving {len(codes)} code names via ChEMBL")
        aliases = resolve_aliases(sorted(codes))
        ALIASES_PATH.write_text(json.dumps({
            "source": "ChEMBL molecule synonyms (https://www.ebi.ac.uk/chembl/); approved = ChEMBL max_phase 4",
            "retrieved": date.today().isoformat(), "aliases": dict(sorted(aliases.items()))}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"wrote {ALIASES_PATH.relative_to(ROOT)}: {len(aliases)} of {len(codes)} codes resolved")
    aliases = load_aliases()
    today = date.today().isoformat()
    for p in pages:
        print(f"{p.name}: {process(p, aliases, not args.no_trials, today)}")


if __name__ == "__main__":
    main()
