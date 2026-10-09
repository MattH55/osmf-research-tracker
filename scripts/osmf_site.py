"""
Shared helpers for the OSMF research-tracker static builders
(scripts/build_digest.py and scripts/build_reports.py).

Pure standard library. Import from a script run at the repo root:

    sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
    from osmf_site import *
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional

SITE = "https://research.opensourcemed.info"
ORG_NAME = "Open Source Medicine Foundation"
ORG_URL = "https://opensourcemed.info"
ORG_LOGO = "https://opensourcemed.info/favicon.png"
GA_ID = "G-202S9N21TE"
SUBSTACK = "https://opensourcemed.substack.com/subscribe?utm_source=digest"
SUBSTACK_HOME = "https://opensourcemed.substack.com"

# Literature feed keys in display order.  post-viral-illness.json is a
# treatment-options document (no studies[]), so it is tolerated but skipped.
FEED_KEYS = [
    "long-covid", "me-cfs", "pacvs", "lyme", "gulf-war-illness",
    "pots", "mcas", "other-post-viral", "post-viral-illness",
]

# Condition metadata.  `trial_labels` are exact values found in
# trials[].mapped_conditions; `trial_keywords` are case-insensitive regexes
# applied to title + conditions_raw when no mapped label exists.
# `cohort_pathogens` / `cohort_case_defs` select cohorts from
# data/pais-cohorts-index.json.  `agent_labels` match
# therapeutic_agents.json "Primary Conditions".
CONDITIONS: Dict[str, Dict[str, Any]] = {
    "long-covid": {
        "name": "Long COVID (PASC)", "short": "Long COVID",
        "tracker": "/long-covid.html", "biomarkers": "long-covid",
        "trial_labels": ["Long COVID / PASC"], "trial_keywords": [],
        "cohort_pathogens": ["sars-cov-2"], "cohort_case_defs": [],
        "agent_labels": ["Long COVID"],
    },
    "me-cfs": {
        "name": "ME/CFS", "short": "ME/CFS",
        "tracker": "/me-cfs.html", "biomarkers": "me-cfs",
        "trial_labels": ["ME/CFS"], "trial_keywords": [],
        "cohort_pathogens": ["unknown-trigger"],
        "cohort_case_defs": ["fukuda_1994", "canadian_consensus", "iom_nam_2015", "icc_2011", "ccc_2003"],
        "agent_labels": ["ME/CFS"],
    },
    "pacvs": {
        "name": "Post-Acute COVID-19 Vaccination Syndrome (PACVS)", "short": "PACVS",
        "tracker": "/pacvs.html", "biomarkers": "pacvs",
        "trial_labels": [], "trial_keywords": [r"\bpacvs\b", r"post[- ]?vac", r"vaccin\w*\s+(injur|syndrome|adverse|sequel)", r"post-vaccination"],
        "cohort_pathogens": ["covid-19-vaccine"], "cohort_case_defs": [],
        "agent_labels": ["PACVS"],
    },
    "lyme": {
        "name": "Chronic Lyme / Post-Treatment Lyme Disease Syndrome", "short": "Lyme / PTLDS",
        "tracker": "/lyme.html", "biomarkers": "lyme",
        "trial_labels": [], "trial_keywords": [r"\blyme\b", r"borreli", r"\bptlds\b"],
        "cohort_pathogens": ["borrelia-burgdorferi"], "cohort_case_defs": [],
        "agent_labels": ["Lyme"],
    },
    "gulf-war-illness": {
        "name": "Gulf War Illness", "short": "Gulf War Illness",
        "tracker": "/gulf-war-illness.html", "biomarkers": "gulf-war-illness",
        "trial_labels": [], "trial_keywords": [r"gulf[- ]war"],
        "cohort_pathogens": ["gulf-war-exposures"], "cohort_case_defs": [],
        "agent_labels": ["Gulf War Illness"],
    },
    "pots": {
        "name": "Postural Orthostatic Tachycardia Syndrome (POTS)", "short": "POTS",
        "tracker": "/pots.html", "biomarkers": None,
        "trial_labels": [], "trial_keywords": [r"\bpots\b", r"postural orthostatic"],
        "cohort_pathogens": [], "cohort_case_defs": [], "agent_labels": ["POTS"],
    },
    "mcas": {
        "name": "Mast Cell Activation Syndrome (MCAS)", "short": "MCAS",
        "tracker": "/mcas.html", "biomarkers": None,
        "trial_labels": [], "trial_keywords": [r"\bmcas\b", r"mast cell activation"],
        "cohort_pathogens": [], "cohort_case_defs": [], "agent_labels": ["MCAS"],
    },
    "other-post-viral": {
        "name": "Other post-viral and post-infectious syndromes", "short": "Other post-viral",
        "tracker": "/other-post-viral.html", "biomarkers": None,
        "trial_labels": ["Unspecified / Overlap"], "trial_keywords": [],
        "cohort_pathogens": [], "cohort_case_defs": [], "agent_labels": [],
    },
    "post-viral-illness": {
        "name": "Post-viral illness (treatment overview)", "short": "Post-viral illness",
        "tracker": "/post-viral-illness.html", "biomarkers": None,
        "trial_labels": [], "trial_keywords": [],
        "cohort_pathogens": [], "cohort_case_defs": [], "agent_labels": [],
    },
}

# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------

def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def esc(s: Any) -> str:
    """HTML-escape, treating None/NaN as empty string."""
    if s is None:
        return ""
    if isinstance(s, float) and s != s:  # NaN
        return ""
    s = str(s)
    if s.strip().lower() in ("none", "nan", "null"):
        return ""
    return html.escape(s, quote=True)


def clean(s: Any) -> str:
    """Return a plain string with None/NaN/'None' collapsed to ''."""
    if s is None:
        return ""
    if isinstance(s, float) and s != s:
        return ""
    s = str(s).strip()
    if s.lower() in ("none", "nan", "null"):
        return ""
    return s


def load_json(path: str, default: Any = None) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def write_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def parse_date(value: Any) -> Optional[dt.date]:
    """Parse 'YYYY-MM-DD', 'YYYY-MM', 'YYYY' or an ISO datetime. Returns None when unparseable."""
    s = clean(value)
    if not s:
        return None
    s = s[:10]
    for fmt, pad in (("%Y-%m-%d", ""), ("%Y-%m", "-01"), ("%Y", "-01-01")):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    try:
        return dt.datetime.strptime(s + pad, "%Y-%m-%d").date()
    except ValueError:
        return None


def as_list(value: Any) -> List[str]:
    """Trial fields are sometimes real lists and sometimes Python-repr strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [clean(v) for v in value if clean(v)]
    s = clean(value)
    if not s:
        return []
    if s.startswith("["):
        try:
            import ast
            parsed = ast.literal_eval(s)
            if isinstance(parsed, (list, tuple)):
                return [clean(v) for v in parsed if clean(v)]
        except (ValueError, SyntaxError):
            pass
    return [s]


def iso_week_id(d: dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_bounds(year: int, week: int):
    """Monday and Sunday of an ISO week."""
    monday = dt.date.fromisocalendar(year, week, 1)
    return monday, monday + dt.timedelta(days=6)


def fmt_date(d: Optional[dt.date]) -> str:
    return d.strftime("%d %B %Y").lstrip("0") if d else ""


def fmt_int(n: Any) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


def excerpt_sentences(text: Any, n: int = 2, max_chars: int = 420) -> str:
    """First n sentences of an abstract, trimmed to max_chars."""
    t = re.sub(r"\s+", " ", clean(text)).strip()
    if not t:
        return ""
    # Strip structured-abstract labels like "BACKGROUND:" at the start of sentences.
    t = re.sub(r"\b([A-Z][A-Z /&-]{2,30}):\s*", "", t)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])", t)
    out = " ".join(parts[:n]).strip()
    if len(out) > max_chars:
        out = out[:max_chars].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    elif len(parts) > n and not out.endswith((".", "!", "?")):
        out = out.rstrip(",;:") + "..."
    return out


def trim_authors(authors: Any, max_chars: int = 110) -> str:
    a = re.sub(r"\s+", " ", clean(authors)).strip()
    if not a:
        return ""
    if len(a) <= max_chars:
        return a
    cut = a[:max_chars].rsplit(",", 1)[0].rstrip(", ")
    return cut + " et al."


def status_label(s: Any) -> str:
    s = clean(s)
    if not s:
        return "Unknown"
    return "Not applicable" if s.upper() == "NA" else s.replace("_", " ").title()


def phase_label(p: Any) -> str:
    p = clean(p).upper()
    return {
        "NA": "Not applicable", "": "Not stated", "EARLY_PHASE1": "Early phase 1",
        "PHASE1": "Phase 1", "PHASE2": "Phase 2", "PHASE3": "Phase 3", "PHASE4": "Phase 4",
        "PHASE1/PHASE2": "Phase 1/2", "PHASE2/PHASE3": "Phase 2/3",
    }.get(p, p.replace("_", " ").title())


def sponsor_label(s: Any) -> str:
    s = clean(s).upper()
    return {
        "OTHER": "Academic / other", "INDUSTRY": "Industry", "NIH": "NIH", "FED": "US federal (non-NIH)",
        "OTHER_GOV": "Other government", "NETWORK": "Research network", "INDIV": "Individual", "": "Not stated",
    }.get(s, s.replace("_", " ").title())


def trial_matches(trial: Dict[str, Any], key: str) -> Optional[str]:
    """Return 'mapped', 'keyword' or None for whether a trial belongs to a condition."""
    meta = CONDITIONS[key]
    mapped = as_list(trial.get("mapped_conditions"))
    if any(lbl in mapped for lbl in meta["trial_labels"]):
        return "mapped"
    if meta["trial_keywords"]:
        hay = " ".join([clean(trial.get("title")), " ".join(as_list(trial.get("conditions_raw")))])
        for pat in meta["trial_keywords"]:
            if re.search(pat, hay, re.I):
                return "keyword"
    return None


def cohort_matches(cohort: Dict[str, Any], key: str) -> bool:
    meta = CONDITIONS[key]
    if clean(cohort.get("pathogen_id")) in meta["cohort_pathogens"]:
        return True
    if clean(cohort.get("case_definition")) in meta["cohort_case_defs"]:
        return True
    return False


def jsonld_script(obj: Any) -> str:
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/") + "</script>"


# --------------------------------------------------------------------------
# Page shell
# --------------------------------------------------------------------------

NAV_ITEMS = [
    ("/index.html", "Research Tracker"),
    ("/digest/", "Weekly Digest"),
    ("/reports/", "Annual Reports"),
    ("/biomarker-atlas.html", "Biomarkers"),
    ("/clinical_trials.html", "Clinical Trials"),
    ("/agents.html", "Agents"),
    (ORG_URL, "OSMF Home"),
]

CSS = """
:root{--blue:#2f45c4;--blue-dark:#1b2a8f;--orange:#ff9800;--text:#3d4466;--ink:#0e1444;--muted:#6b7194;--bg:#f7f8fc;--white:#fff;--border:#e6e8f2;--up:#c2410c;--down:#1d4ed8;--mixed:#a16207;--green:#047857}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.65;color:var(--text);background:var(--white);font-size:16px}
a{color:var(--blue)}a:hover{color:var(--blue-dark)}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:#fff;padding:.5rem;z-index:999}
nav.osmf{background:var(--ink)}
nav.osmf .wrap{max-width:1200px;margin:0 auto;padding:.6rem 1rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.4rem 1rem}
nav.osmf .brand{color:#fff;text-decoration:none;font-weight:700}
nav.osmf ul{list-style:none;display:flex;flex-wrap:wrap;gap:.1rem .9rem}
nav.osmf li a{color:rgba(255,255,255,.85);text-decoration:none;font-size:.86rem}
main{max-width:1200px;margin:0 auto;padding:8px var(--ui-gutter,24px) 24px}
.hero{padding:clamp(48px,7vw,84px) 0 clamp(44px,6vw,72px)}
.hero .wrap{max-width:1200px;margin:0 auto;padding:0 var(--ui-gutter,24px)}
.hero .badge{display:inline-flex;align-items:center;font-size:11.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:#ffcf8a;background:rgba(255,152,0,.12);border:1px solid rgba(255,152,0,.32);padding:6px 12px;border-radius:999px;margin-bottom:20px}
.hero h1{font-size:clamp(2rem,4.6vw,3.35rem);margin:0 0 16px;max-width:22ch}
.hero p{max-width:66ch;font-size:clamp(1rem,1.4vw,1.12rem);line-height:1.65;margin:0}
.hero a{color:#ffd08a}
.crumbs{font-size:13px;color:var(--muted);padding:22px 0 4px;margin-bottom:22px}
.crumbs a{color:var(--muted)!important;text-decoration:none!important}.crumbs a:hover{color:var(--ink)!important}
.crumbs ol{list-style:none;display:flex;flex-wrap:wrap;gap:.35rem}
.crumbs li+li::before{content:"\\203A";margin-right:.35rem;color:#9aa0bd}
.crumbs li[aria-current]{color:var(--ink);font-weight:500}
h2{font-size:clamp(1.4rem,2.2vw,1.75rem);font-weight:700;color:var(--ink);margin:56px 0 14px;letter-spacing:-.015em;line-height:1.25;scroll-margin-top:84px}
h3{font-size:1.12rem;font-weight:650;color:var(--ink);margin:28px 0 10px;letter-spacing:-.01em}
p{margin-bottom:.95rem;max-width:75ch}
main li{max-width:75ch}
.lede{font-size:1.08rem;color:#2a3160}
.numbers{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:20px 0 26px}
.num{background:#fff;border:1px solid var(--border);border-radius:14px;padding:18px 18px 16px;box-shadow:0 1px 2px rgba(14,20,68,.05),0 2px 8px rgba(14,20,68,.04);display:grid;gap:8px;align-content:start}
.num b{display:block;font-family:"Fraunces",Georgia,serif;font-weight:500;font-size:2.1rem;color:var(--ink);line-height:1;letter-spacing:-.02em}
.num span{font-size:12px;line-height:1.45;color:var(--muted);font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.note{background:#fffaf2;border:1px solid #f5dcb0;border-radius:12px;padding:14px 16px;font-size:.93rem;line-height:1.6;color:#6b4a12;margin:18px 0;max-width:none}
.note strong{color:#5a3a06}
.box{background:var(--bg);border:1px solid var(--border);border-radius:14px;padding:22px 24px;margin:28px 0}
.box h3{margin-top:0}
.cite{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.84rem;line-height:1.6;background:#fff;border:1px solid var(--border);border-radius:10px;padding:12px 14px;overflow-wrap:anywhere;color:#2a3160}
.study{border-bottom:1px solid var(--border);padding:18px 0}
.study:last-child{border-bottom:0}
.study h4{font-size:1.03rem;font-weight:650;line-height:1.4;margin-bottom:6px;color:var(--ink)}
main .study h4 a{text-decoration:none;color:var(--ink)}main .study h4 a:hover{color:var(--blue);text-decoration:underline;text-underline-offset:3px}
.study .meta{font-size:.83rem;color:var(--muted);margin-bottom:6px}
.study .meta b{color:#2a3160;font-weight:600}
.study p{font-size:.94rem;color:var(--text);margin:0}
.tag{display:inline-flex;align-items:center;font-size:11.5px;font-weight:650;padding:2px 9px;border-radius:999px;background:var(--bg);color:#2a3160;border:1px solid var(--border);margin-left:.35rem;vertical-align:middle;letter-spacing:0}
.tag.alt{background:#fff;color:var(--muted)}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:14px;margin:0;background:#fff}
th,td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--border);vertical-align:top}
td{color:#2a3160}
tr:last-child td{border-bottom:0}
th{background:var(--bg);font-weight:700;font-size:11.5px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);white-space:nowrap}
tbody tr:hover td{background:#fafbff}
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border);border-radius:14px;box-shadow:0 1px 2px rgba(14,20,68,.05),0 2px 8px rgba(14,20,68,.04);margin:14px 0 22px;background:#fff}
.st{display:inline-flex;align-items:center;font-size:12px;font-weight:650;padding:2px 9px;border-radius:999px;background:var(--bg);color:#2a3160;border:1px solid var(--border);white-space:nowrap}
.st.RECRUITING,.st.ENROLLING_BY_INVITATION{background:#e7f7f0;color:#047857;border-color:#bfe9d6}
.st.COMPLETED{background:#eaf0ff;color:#1d4ed8;border-color:#cfdcff}
.st.ACTIVE_NOT_RECRUITING,.st.NOT_YET_RECRUITING{background:#fff7df;color:#a16207;border-color:#f5e0a3}
.st.TERMINATED,.st.WITHDRAWN,.st.SUSPENDED{background:#fff1e8;color:#c2410c;border-color:#ffd9c2}
.chart{margin:14px 0 28px;background:#fff;border:1px solid var(--border);border-radius:14px;padding:20px 20px 14px;box-shadow:0 1px 2px rgba(14,20,68,.05),0 2px 8px rgba(14,20,68,.04)}
.chart svg{width:100%;height:auto;display:block;font-family:inherit}
.chart figcaption{font-size:.82rem;color:var(--muted);margin-top:10px;padding-top:10px;border-top:1px solid var(--border)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:10px;font-size:.82rem;color:var(--muted)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:20px}
.subscribe{background:#fff;border:1px solid var(--border);border-left:4px solid var(--orange);border-radius:14px;padding:24px 26px;margin:32px 0;box-shadow:0 1px 2px rgba(14,20,68,.05),0 2px 8px rgba(14,20,68,.04)}
.subscribe h3{margin-top:0;font-size:1.2rem}
.subscribe p{color:var(--muted)}
.btn{display:inline-flex;align-items:center;background:linear-gradient(180deg,#ffa31a,#f2711c);color:#fff!important;text-decoration:none!important;font-weight:650;padding:10px 18px;border-radius:999px;font-size:.92rem;margin:.3rem .5rem .3rem 0;box-shadow:0 6px 16px rgba(242,113,28,.28);border:0}
.btn:hover{filter:brightness(1.04)}
.btn.ghost{background:#fff;color:var(--ink)!important;border:1px solid #d5d9ea;box-shadow:none}
.btn.ghost:hover{background:var(--bg)}
.pager{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin:48px 0 0;padding-top:20px;border-top:1px solid var(--border);font-size:.94rem;font-weight:600}
.pager a{text-decoration:none!important}
.issue-list{list-style:none;display:grid;gap:12px;margin:18px 0}
.issue-list li{padding:18px 22px;border:1px solid var(--border);border-radius:14px;background:#fff;box-shadow:0 1px 2px rgba(14,20,68,.05),0 2px 8px rgba(14,20,68,.04);max-width:none;transition:border-color .2s,box-shadow .2s,transform .2s}
.issue-list li:hover{border-color:#d5d9ea;box-shadow:0 2px 6px rgba(14,20,68,.05),0 14px 34px rgba(14,20,68,.08);transform:translateY(-1px)}
.issue-list a{font-weight:650;text-decoration:none!important;font-size:1.05rem;color:var(--ink)!important}
.issue-list a:hover{color:var(--blue)!important}
.issue-list .meta{font-size:.85rem;color:var(--muted);margin-top:4px}
.disclaimer{font-size:.85rem;line-height:1.6;color:#6b4a12;background:#fffaf2;border:1px solid #f5dcb0;border-radius:12px;padding:14px 16px;margin-top:48px}
.toc{font-size:.9rem;background:#fff;border:1px solid var(--border);border-radius:14px;padding:14px 18px;margin:20px 0 8px;display:flex;flex-wrap:wrap;align-items:center;gap:8px 14px;box-shadow:0 1px 2px rgba(14,20,68,.05)}
.toc>strong{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.toc ul{list-style:none;display:flex;flex-wrap:wrap;gap:6px}
.toc li a{display:inline-block;padding:5px 12px;border-radius:999px;background:var(--bg);border:1px solid var(--border);color:#2a3160!important;text-decoration:none!important;font-weight:500;font-size:.86rem}
.toc li a:hover{border-color:#d5d9ea;color:var(--ink)!important;background:#fff}
.small{font-size:.86rem;color:var(--muted)}
ul.plain,ol.plain{padding-left:1.25rem;margin-bottom:1.1rem}ul.plain li,ol.plain li{margin-bottom:.4rem}
ul.plain li::marker{color:var(--orange)}
footer.osmf{background:var(--ink);color:#c9cde6;padding:2rem 1rem;margin-top:3rem;font-size:.86rem}
footer.osmf .wrap{max-width:1200px;margin:0 auto}
footer.osmf a{color:#e7e9f7}
@media (max-width:640px){.hero h1{font-size:clamp(1.75rem,8vw,2.2rem)}h2{margin-top:40px}th,td{padding:10px 12px}.box,.subscribe{padding:18px}.num b{font-size:1.75rem}}
@media print{nav.osmf,footer.osmf,.subscribe,.pager{display:none}}
"""


def nav_html(active: str = "") -> str:
    items = []
    for href, label in NAV_ITEMS:
        cls = ' class="active"' if href == active else ""
        ext = ' rel="noopener"' if href.startswith("http") else ""
        items.append(f'<li><a href="{href}"{cls}{ext}>{label}</a></li>')
    return (
        '<nav class="osmf" aria-label="Main navigation"><div class="wrap">'
        f'<a class="brand" href="{ORG_URL}">Open Source <span>Medicine</span></a>'
        '<ul>' + "".join(items) + '</ul></div></nav>'
    )


def footer_html(note: str) -> str:
    return (
        '<footer class="osmf"><div class="wrap">'
        f'<div class="fb">{ORG_NAME}</div>'
        '<div class="links">'
        f'<a href="{ORG_URL}">OSMF Home</a>'
        f'<a href="{SITE}/">Research Tracker</a>'
        f'<a href="{SITE}/digest/">Weekly Digest</a>'
        f'<a href="{SITE}/digest/feed.xml">RSS</a>'
        f'<a href="{SITE}/reports/">Annual Reports</a>'
        f'<a href="{SITE}/biomarker-atlas.html">Biomarker Atlas</a>'
        f'<a href="{SITE}/clinical_trials.html">Clinical Trials</a>'
        f'<a href="{SUBSTACK_HOME}">Substack</a>'
        f'<a href="{ORG_URL}/#contact">Contact</a>'
        '</div>'
        f'<div class="note-f">{esc(note)} Data from PubMed (NLM) and ClinicalTrials.gov. Not medical advice.</div>'
        '</div></footer>'
    )


def breadcrumb_jsonld(items: List[tuple]) -> Dict[str, Any]:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": name, "item": url}
            for i, (name, url) in enumerate(items)
        ],
    }


def breadcrumb_html(items: List[tuple]) -> str:
    lis = []
    for i, (name, url) in enumerate(items):
        if i == len(items) - 1:
            lis.append(f'<li aria-current="page">{esc(name)}</li>')
        else:
            lis.append(f'<li><a href="{esc(url)}">{esc(name)}</a></li>')
    return '<div class="crumbs" aria-label="Breadcrumb"><ol>' + "".join(lis) + "</ol></div>"


def page(
    *,
    title: str,
    description: str,
    canonical: str,
    body: str,
    jsonld: Iterable[Dict[str, Any]] = (),
    og_type: str = "article",
    nav_active: str = "",
    extra_head: str = "",
    footer_note: str = "",
    published: str = "",
    modified: str = "",
) -> str:
    ld = "\n".join(jsonld_script(o) for o in jsonld)
    pub_meta = ""
    if published:
        pub_meta += f'\n<meta property="article:published_time" content="{esc(published)}">'
    if modified:
        pub_meta += f'\n<meta property="article:modified_time" content="{esc(modified)}">'
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA_ID}');
</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="index, follow, max-image-preview:large">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="{ORG_NAME}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{ORG_LOGO}">{pub_meta}
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<link rel="alternate" type="application/rss+xml" title="Post-viral research digest (RSS)" href="{SITE}/digest/feed.xml">
<link rel="alternate" type="application/feed+json" title="Post-viral research digest (JSON Feed)" href="{SITE}/digest/feed.json">
<link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
<link rel="icon" href="{ORG_LOGO}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
{extra_head}
{ld}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{nav_html(nav_active)}
{body}
{footer_html(footer_note)}
</body>
</html>
"""
