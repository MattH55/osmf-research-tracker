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
:root{--blue:#0068f8;--blue-dark:#0052c7;--orange:#ff9800;--text:#1f2937;--muted:#6b7280;--bg:#f8fafc;--white:#fff;--border:#e5e7eb;--up:#dc2626;--down:#2563eb;--mixed:#d97706;--green:#10b981}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;line-height:1.6;color:var(--text);background:var(--white);font-size:16px}
a{color:var(--blue)}a:hover{color:var(--blue-dark)}
.skip{position:absolute;left:-999px}.skip:focus{left:8px;top:8px;background:#fff;padding:.5rem;z-index:999}
nav.osmf{background:var(--blue);position:sticky;top:0;z-index:100}
nav.osmf .wrap{max-width:1100px;margin:0 auto;padding:.6rem 1rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.4rem 1rem}
nav.osmf .brand{color:#fff;text-decoration:none;font-weight:700;font-size:1.05rem;letter-spacing:-.01em}
nav.osmf .brand span{color:var(--orange)}
nav.osmf ul{list-style:none;display:flex;flex-wrap:wrap;gap:.1rem .9rem}
nav.osmf li a{color:rgba(255,255,255,.85);text-decoration:none;font-size:.86rem;font-weight:500;padding:.25rem 0;border-bottom:2px solid transparent}
nav.osmf li a:hover,nav.osmf li a.active{color:#fff;border-bottom-color:var(--orange)}
main{max-width:1100px;margin:0 auto;padding:0 1rem 3rem}
.hero{background:linear-gradient(135deg,var(--blue) 0%,var(--blue-dark) 100%);color:#fff;padding:2.5rem 0 2rem}
.hero .wrap{max-width:1100px;margin:0 auto;padding:0 1rem}
.hero .badge{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.35);border-radius:999px;padding:.2rem .8rem;font-size:.78rem;font-weight:600;letter-spacing:.03em;text-transform:uppercase;margin-bottom:.9rem}
.hero h1{font-size:clamp(1.5rem,3.5vw,2.3rem);line-height:1.2;font-weight:700;margin-bottom:.6rem;letter-spacing:-.02em}
.hero p{max-width:760px;opacity:.95;font-size:1.02rem}
.hero a{color:#fff}
.crumbs{font-size:.82rem;color:var(--muted);padding:.8rem 0 0}
.crumbs a{color:var(--muted)}
.crumbs ol{list-style:none;display:flex;flex-wrap:wrap;gap:.3rem}
.crumbs li+li::before{content:"/";margin-right:.3rem;color:#cbd5e1}
h2{font-size:1.45rem;margin:2.2rem 0 .8rem;letter-spacing:-.01em;scroll-margin-top:4rem}
h3{font-size:1.12rem;margin:1.4rem 0 .6rem}
p{margin-bottom:.9rem}
.lede{font-size:1.05rem;color:#374151}
.numbers{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem;margin:1.4rem 0}
.num{background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:.9rem 1rem}
.num b{display:block;font-size:1.6rem;color:var(--blue);line-height:1.1;font-weight:700}
.num span{font-size:.8rem;color:var(--muted)}
.note{background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;padding:.8rem 1rem;font-size:.92rem;margin:1rem 0}
.box{background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:1.1rem 1.2rem;margin:1.2rem 0}
.box h3{margin-top:0}
.cite{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.84rem;background:#fff;border:1px solid var(--border);border-radius:6px;padding:.7rem .9rem;overflow-wrap:anywhere}
.study{border-bottom:1px solid var(--border);padding:1rem 0}
.study:last-child{border-bottom:0}
.study h4{font-size:1.02rem;font-weight:600;line-height:1.35;margin-bottom:.3rem}
.study h4 a{text-decoration:none}.study h4 a:hover{text-decoration:underline}
.study .meta{font-size:.82rem;color:var(--muted);margin-bottom:.4rem}
.study .meta b{color:#374151;font-weight:600}
.study p{font-size:.94rem;color:#374151;margin:0}
.tag{display:inline-block;font-size:.72rem;font-weight:600;padding:.1rem .5rem;border-radius:999px;background:#eff6ff;color:var(--blue);margin-left:.3rem;vertical-align:middle}
.tag.alt{background:#f3f4f6;color:#4b5563}
table{width:100%;border-collapse:collapse;font-size:.9rem;margin:.8rem 0 1.2rem}
th,td{text-align:left;padding:.5rem .6rem;border-bottom:1px solid var(--border);vertical-align:top}
th{background:var(--bg);font-weight:600;font-size:.82rem;text-transform:uppercase;letter-spacing:.03em;color:#4b5563}
.tbl-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
.st{display:inline-block;font-size:.74rem;font-weight:600;padding:.1rem .5rem;border-radius:4px;background:#f3f4f6;color:#374151;white-space:nowrap}
.st.RECRUITING,.st.ENROLLING_BY_INVITATION{background:#ecfdf5;color:#047857}
.st.COMPLETED{background:#eff6ff;color:#1d4ed8}
.st.ACTIVE_NOT_RECRUITING,.st.NOT_YET_RECRUITING{background:#fffbeb;color:#b45309}
.st.TERMINATED,.st.WITHDRAWN,.st.SUSPENDED{background:#fef2f2;color:#b91c1c}
.chart{margin:.6rem 0 1.4rem}
.chart svg{width:100%;height:auto;display:block;font-family:inherit}
.chart figcaption{font-size:.8rem;color:var(--muted);margin-top:.3rem}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.2rem}
.subscribe{background:linear-gradient(135deg,#eff6ff,#f8fafc);border:1px solid #bfdbfe;border-radius:12px;padding:1.4rem;margin:1.5rem 0}
.subscribe h3{margin-top:0}
.btn{display:inline-block;background:var(--blue);color:#fff!important;text-decoration:none;font-weight:600;padding:.6rem 1.1rem;border-radius:8px;font-size:.92rem;margin:.3rem .5rem .3rem 0}
.btn:hover{background:var(--blue-dark)}
.btn.ghost{background:#fff;color:var(--blue)!important;border:1px solid var(--blue)}
.pager{display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;margin:2rem 0 0;padding-top:1rem;border-top:1px solid var(--border);font-size:.92rem}
.issue-list{list-style:none}
.issue-list li{padding:.9rem 0;border-bottom:1px solid var(--border)}
.issue-list a{font-weight:600;text-decoration:none;font-size:1.02rem}
.issue-list .meta{font-size:.84rem;color:var(--muted)}
.disclaimer{font-size:.84rem;color:var(--muted);border-top:1px solid var(--border);padding-top:1rem;margin-top:2rem}
.toc{font-size:.9rem;background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:.8rem 1rem;margin:1rem 0}
.toc ul{list-style:none;display:flex;flex-wrap:wrap;gap:.2rem 1rem}
.small{font-size:.86rem;color:var(--muted)}
ul.plain{padding-left:1.2rem;margin-bottom:1rem}ul.plain li{margin-bottom:.3rem}
footer.osmf{background:#111827;color:#9ca3af;padding:2rem 1rem;margin-top:3rem;font-size:.86rem}
footer.osmf .wrap{max-width:1100px;margin:0 auto}
footer.osmf .fb{color:#fff;font-weight:700;margin-bottom:.6rem}
footer.osmf .links{display:flex;flex-wrap:wrap;gap:.3rem 1.2rem;margin-bottom:.8rem}
footer.osmf a{color:#d1d5db;text-decoration:none}footer.osmf a:hover{color:#fff}
@media (max-width:640px){nav.osmf .wrap{padding:.5rem .8rem}nav.osmf li a{font-size:.8rem}.hero{padding:1.8rem 0 1.4rem}h2{font-size:1.25rem}table{font-size:.84rem}}
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
