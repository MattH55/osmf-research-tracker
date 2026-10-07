#!/usr/bin/env python3
"""
Programmatic SEO: one indexable page per (condition, biomarker) pair plus
cross-condition marker hub pages, a biomarkers index, and an injected
per-marker link block on every root <condition>-biomarkers.html atlas page.

Usage (from repo root):
    python scripts/build_marker_pages.py            # build everything
    python scripts/build_marker_pages.py --check    # build + verify internal links
    python scripts/build_marker_pages.py --only long-covid --no-inject   # one condition (testing)

Idempotent: re-running overwrites generated files and replaces (never
duplicates) the <!-- MARKER_PAGES_START/END --> block on atlas pages.

Outputs:
    biomarkers/<condition-slug>/<marker-slug>.html
    biomarkers/markers/<marker-slug>.html
    biomarkers/index.html
    js/generated/marker-pages-index.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "biomarkers"
OUT = ROOT / "biomarkers"
SITE = "https://research.opensourcemed.info"
GA_ID = "G-202S9N21TE"
SUBSTACK = "https://opensourcemed.substack.com/subscribe?utm_source=tracker"
TODAY = _dt.date.today()
BUILD_DATE = TODAY.isoformat()
ACCESSED = f"{TODAY.strftime('%B')} {TODAY.day}, {TODAY.year}"

ENRICH_FILES = {
    "interventions": ("intervention-links.json", "markerInterventions"),
    "trials": ("trial-links.json", "markerTrials"),
    "commercial": ("commercial-links.json", "markerCommercial"),
    "consumable": ("consumable-links.json", "markerConsumable"),
    "agents": ("agent-discovery.json", "markerAgents"),
}

GREEK = {
    "α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "ζ": "zeta",
    "η": "eta", "θ": "theta", "ι": "iota", "κ": "kappa", "λ": "lambda", "μ": "mu",
    "ν": "nu", "ξ": "xi", "ο": "omicron", "π": "pi", "ρ": "rho", "σ": "sigma",
    "τ": "tau", "υ": "upsilon", "φ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega",
    "Α": "alpha", "Β": "beta", "Γ": "gamma", "Δ": "delta", "Ω": "omega",
    "₂": "2", "₁": "1", "₃": "3", "²": "2", "≥": "ge", "↔": "-", "→": "-", "±": "pm", "µ": "mu",
}

COMPARISON_ABBR = {
    "HC": "healthy controls",
    "R": "recovered individuals without persistent symptoms",
    "HGV": "healthy Gulf War veteran controls",
    "LC": "long COVID",
    "NB": "neuroborreliosis",
    "PTLDS": "post-treatment Lyme disease syndrome",
    "EM": "erythema migrans",
    "PEM": "post-exertional malaise challenge",
    "CMI": "chronic multisymptom illness",
    "PCVS": "post-COVID-vaccination syndrome",
    "PACVS": "post-acute COVID-19 vaccination syndrome",
}

TEST_TYPE_LABEL = {
    "BloodTest": "Blood test (serum / plasma / whole blood)",
    "MedicalTest": "Clinical or physiological test",
    "PathologyTest": "Tissue / pathology test",
    "ImagingTest": "Imaging test",
}

DIRECTION_WORD = {"up": "elevated", "down": "reduced", "mixed": "inconsistent"}
DIRECTION_ARROW = {"up": "↑", "down": "↓", "mixed": "↕"}
DIRECTION_LONG = {
    "up": "higher than in the comparison group",
    "down": "lower than in the comparison group",
    "mixed": "reported as both higher and lower across studies, with no consistent direction",
}


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def clean(v) -> str:
    """Return a trimmed string, or '' for None/nan/'None'."""
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("none", "nan", "null", "undefined", "n/a"):
        return ""
    return s


def ascii_fold(s: str) -> str:
    s = "".join(GREEK.get(ch, ch) for ch in s)
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def slugify(s: str) -> str:
    s = ascii_fold(s).lower()
    s = re.sub(r"[()\[\]]", "", s)          # strip parentheses/brackets
    s = s.replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "marker"


def js_style_id(s: str) -> str:
    """Mimic the id scheme used by search-index.json / enrichment files
    (lowercase, non-alphanumerics -> hyphen, Greek letters dropped)."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


QUALIFIER_ABBR = {"PTLDS", "PEM", "CSF", "HC", "LC", "PASC", "GWI", "OA", "RA", "MS", "AD", "AF", "CKD", "COPD", "IBD", "MDD", "PACVS", "PCVS"}


def base_key(name: str) -> str:
    """Folded full name with any trailing parenthetical removed."""
    return slugify(re.sub(r"\s*\([^()]*\)\s*$", "", clean(name)))


def normalized_key(name: str) -> str:
    """Cross-condition matching key. Prefers a short abbreviation in
    parentheses ('Interleukin-6 (IL-6)' -> 'il-6', 'CRP' -> 'crp'), else the
    folded full name. Lower-case qualifiers such as '(plasma)' and study
    qualifiers such as '(PTLDS)' are ignored."""
    name = clean(name)
    m = re.search(r"\(([^()]{1,14})\)\s*$", name)
    if m:
        abbr = m.group(1).split("/")[0].strip()
        if re.search(r"[A-Z0-9]", abbr) and " " not in abbr and len(abbr) <= 12 and abbr.upper() not in QUALIFIER_ABBR:
            return slugify(abbr)
    return base_key(name)


def truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    cut = s[: n - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(",;:") + "…"


def expand_comparison(comp: str) -> str:
    comp = clean(comp)
    if not comp:
        return ""

    def sub(m):
        tok = m.group(0)
        return COMPARISON_ABBR.get(tok, tok)

    out = re.sub(r"\b[A-Z]{1,5}\b", sub, comp)
    out = out.replace(" — ", "; ").replace("—", "-")
    return out


def stable_pick(seed: str, options: list):
    h = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16)
    return options[h % len(options)]


def doi_url(doi: str) -> str:
    doi = clean(doi)
    if not doi:
        return ""
    if doi.startswith("http"):
        return doi
    return "https://doi.org/" + doi


def rel(depth: int) -> str:
    return "../" * depth


def dominant_newline(text: str) -> str:
    return "\r\n" if text.count("\r\n") > text.count("\n") / 2 else "\n"


# ----------------------------------------------------------------------------
# data loading
# ----------------------------------------------------------------------------
def load_json(p: Path):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def load_conditions(only: str | None):
    conds = []
    for p in sorted(DATA.glob("*.json")):
        d = load_json(p)
        if not isinstance(d, dict) or "slug" not in d or "markers" not in d:
            continue
        if only and d["slug"] != only:
            continue
        conds.append(d)
    return conds


def load_enrichment():
    out = {}
    for key, (fname, field) in ENRICH_FILES.items():
        p = DATA / fname
        out[key] = load_json(p).get(field, {}) if p.exists() else {}
    oo = DATA / "outcome-ontology.json"
    out["outcome"] = {}
    if oo.exists():
        for t in load_json(oo).get("terms", []):
            out["outcome"][t.get("markerId")] = t
    si = DATA / "search-index.json"
    out["search_ids"] = {}
    if si.exists():
        for m in load_json(si).get("markers", []):
            out["search_ids"][(m.get("slug"), clean(m.get("name")))] = m.get("id")
    lk = ROOT / "biomarker_pipeline" / "loinc_lookup.json"
    out["loinc"] = load_json(lk) if lk.exists() else {}
    return out


# ----------------------------------------------------------------------------
# model building
# ----------------------------------------------------------------------------
class M:  # a rendered marker record / hub
    pass


def build_records(conds, enr):
    records = []
    skipped = []
    for d in conds:
        slug = d["slug"]
        cond = d["condition"]
        cats = d.get("categories", {})
        used = {}
        for raw in d["markers"]:
            name = clean(raw.get("name"))
            if not name:
                skipped.append((slug, raw))
                continue
            r = M()
            r.cond_slug = slug
            r.cond_name = clean(cond.get("name")) or slug
            r.cond_short = clean(cond.get("shortName")) or r.cond_name
            r.cond_alt = [clean(a) for a in cond.get("alternateNames", []) if clean(a)]
            r.cond_page = f"{slug}-biomarkers.html"
            r.cond_date = clean(d.get("page", {}).get("dateModified")) or BUILD_DATE
            r.name = name
            r.alt = clean(raw.get("alternateName"))
            if r.alt.lower() == name.lower():
                r.alt = ""
            r.direction = clean(raw.get("direction")).lower() or "mixed"
            if r.direction not in DIRECTION_WORD:
                r.direction = "mixed"
            r.category = clean(raw.get("category"))
            r.category_label = clean(cats.get(r.category)) or (r.category.replace("-", " ").title() if r.category else "")
            r.comparison = clean(raw.get("comparison"))
            r.comparison_long = expand_comparison(r.comparison)
            r.symptoms = clean(raw.get("symptoms"))
            ref = raw.get("reference") or {}
            r.citation = clean(ref.get("citation"))
            r.doi = clean(ref.get("doi"))
            r.test_type = clean(raw.get("testType"))
            r.loinc = clean(raw.get("loinc"))
            if not r.loinc:
                lk = enr["loinc"].get(name.lower())
                if lk and clean(lk.get("loinc")):
                    r.loinc = clean(lk["loinc"])
                    r.test_type = r.test_type or clean(lk.get("testType"))
            base = slugify(name)
            s = base
            n = 1
            while s in used:
                n += 1
                s = f"{base}-{n}"
            used[s] = True
            r.slug = s
            r.key = normalized_key(name)
            r.enrich_id = enr["search_ids"].get((slug, name)) or f"{slug}:{js_style_id(name)}"
            r.interventions = (enr["interventions"].get(r.enrich_id) or {}).get("interventions", [])
            r.trials = enr["trials"].get(r.enrich_id, [])
            r.commercial = enr["commercial"].get(r.enrich_id)
            r.consumable = enr["consumable"].get(r.enrich_id)
            r.agents = enr["agents"].get(r.enrich_id)
            r.outcome = enr["outcome"].get(r.enrich_id)
            r.url_path = f"biomarkers/{slug}/{s}.html"
            r.url = f"{SITE}/{r.url_path}"
            records.append(r)
    return records, skipped


def group_markers(records):
    """Union-find: group by normalized name key, then merge groups sharing a LOINC."""
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_loinc = defaultdict(list)
    for r in records:
        find(r.key)
        union(r.key, base_key(r.name))
        if r.loinc:
            by_loinc[r.loinc].append(r.key)
    for keys in by_loinc.values():
        for k in keys[1:]:
            union(keys[0], k)
    groups = defaultdict(list)
    for r in records:
        groups[find(r.key)].append(r)
    hubs = {}
    taken = set()
    for root in sorted(groups):
        members = groups[root]
        counts = defaultdict(int)
        for m in members:
            counts[m.name] += 1
        disp = sorted(counts.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))[0][0]
        base = slugify(disp)
        hslug = base
        n = 1
        while hslug in taken:
            n += 1
            hslug = f"{base}-{n}"
        taken.add(hslug)
        hub = M()
        hub.slug = hslug
        hub.name = disp
        hub.members = sorted(members, key=lambda m: (m.cond_short.lower(), m.name))
        hub.loincs = sorted({m.loinc for m in members if m.loinc})
        hub.alts = sorted({m.alt for m in members if m.alt} | {m.name for m in members if m.name != disp})
        hub.url_path = f"biomarkers/markers/{hslug}.html"
        hub.url = f"{SITE}/{hub.url_path}"
        hubs[hslug] = hub
        for m in members:
            m.hub = hub
    return hubs


# ----------------------------------------------------------------------------
# chrome
# ----------------------------------------------------------------------------
CSS = """
:root{--brand-blue:#0068f8;--brand-blue-dark:#0052c7;--brand-orange:#ff9800;--text-dark:#1f2937;--text-light:#6b7280;--bg-light:#f8fafc;--bg-white:#fff;--border:#e5e7eb;--up-bg:#fef2f2;--up-text:#dc2626;--down-bg:#eff6ff;--down-text:#2563eb;--mixed-bg:#fffbeb;--mixed-text:#d97706}
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:var(--text-dark);background:var(--bg-light);line-height:1.6;overflow-x:hidden}
a{color:var(--brand-blue)}
.nav{background:#fff;border-bottom:1px solid var(--border);position:sticky;top:0;z-index:20}
.nav-in{max-width:1100px;margin:0 auto;padding:.6rem 1rem;display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.nav .brand{font-weight:700;color:var(--brand-blue);text-decoration:none;font-size:1.05rem;white-space:nowrap}
.nav .links{display:flex;gap:.25rem .9rem;flex-wrap:wrap;font-size:.86rem}
.nav .links a{color:var(--text-light);text-decoration:none;font-weight:500}
.nav .links a:hover,.nav .links a.active{color:var(--brand-blue)}
.hero{background:linear-gradient(135deg,#0068f8 0%,#0052c7 100%);color:#fff;padding:2.2rem 1rem 2rem}
.hero-in{max-width:1100px;margin:0 auto}
.crumbs{font-size:.8rem;margin-bottom:.8rem;opacity:.92}
.crumbs a{color:#fff;text-decoration:none}
.crumbs span{opacity:.7;margin:0 .35rem}
.hero h1{font-size:1.75rem;line-height:1.25;font-weight:700;margin-bottom:.6rem;overflow-wrap:anywhere}
.hero p{max-width:760px;opacity:.95;font-size:1rem}
.pill{display:inline-block;padding:.15rem .6rem;border-radius:999px;font-size:.78rem;font-weight:600;margin-right:.4rem;margin-top:.6rem;background:rgba(255,255,255,.18)}
main{max-width:1100px;margin:0 auto;padding:1.5rem 1rem 3rem}
.card{background:#fff;border:1px solid var(--border);border-radius:12px;padding:1.25rem;margin-bottom:1.25rem}
.card h2{font-size:1.2rem;margin-bottom:.75rem;color:var(--brand-blue-dark)}
.card h3{font-size:1rem;margin:.9rem 0 .4rem}
.card p{margin-bottom:.7rem}
.card ul{padding-left:1.2rem;margin-bottom:.6rem}
.card li{margin-bottom:.35rem}
.tbl{width:100%;border-collapse:collapse;font-size:.93rem}
.tbl th,.tbl td{text-align:left;padding:.55rem .6rem;border-bottom:1px solid var(--border);vertical-align:top;overflow-wrap:anywhere}
.tbl th{width:32%;color:var(--text-light);font-weight:600}
.tbl thead th{width:auto}
.tbl-wrap{overflow-x:auto}
.dir{display:inline-block;padding:.1rem .55rem;border-radius:6px;font-weight:600;font-size:.85rem}
.dir-up{background:var(--up-bg);color:var(--up-text)}
.dir-down{background:var(--down-bg);color:var(--down-text)}
.dir-mixed{background:var(--mixed-bg);color:var(--mixed-text)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.5rem .9rem;padding:0 !important;list-style:none}
.grid li{margin:0}
.faq details{border-top:1px solid var(--border);padding:.6rem 0}
.faq summary{cursor:pointer;font-weight:600}
.faq details p{margin:.5rem 0 0}
.cite{background:var(--bg-light);border-left:4px solid var(--brand-blue);padding:.8rem 1rem;font-size:.9rem;overflow-wrap:anywhere}
.muted{color:var(--text-light);font-size:.86rem}
.cta{background:#fff7ed;border:1px solid #fed7aa;border-radius:12px;padding:1rem 1.25rem;margin-bottom:1.25rem}
.cta a.btn{display:inline-block;background:var(--brand-orange);color:#fff;text-decoration:none;font-weight:600;padding:.5rem 1rem;border-radius:8px;margin-top:.4rem}
.disc{font-size:.85rem;color:var(--text-light);border-top:1px solid var(--border);padding-top:1rem}
footer{background:#1f2937;color:#9ca3af;padding:1.5rem 1rem;font-size:.85rem}
footer .in{max-width:1100px;margin:0 auto;display:flex;flex-wrap:wrap;gap:.5rem 1.2rem;justify-content:space-between}
footer a{color:#d1d5db}
.search{width:100%;padding:.7rem .9rem;border:1px solid var(--border);border-radius:8px;font-size:1rem;font-family:inherit}
.cond-list{list-style:none;padding:0 !important;display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.6rem}
.cond-list li{border:1px solid var(--border);border-radius:10px;padding:.7rem .9rem;background:#fff}
.cond-list .n{color:var(--text-light);font-size:.82rem}
@media (max-width:640px){.hero h1{font-size:1.4rem}.tbl th{width:38%}.card{padding:1rem}}
"""

NAV_ITEMS = [
    ("index.html", "Research Tracker"),
    ("biomarker-atlas.html", "Biomarker Atlas"),
    ("biomarker-index.html", "Biomarker Index"),
    ("biomarkers/index.html", "Marker Pages"),
    ("clinical_trials.html", "Clinical Trials"),
    ("agents.html", "Therapeutic Agents"),
]


def head(title, desc, canonical, jsonld, robots="index, follow, max-image-preview:large"):
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
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Open Source Medicine Foundation">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{esc(canonical)}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
<script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>
</head>
"""


def nav(depth: int, active: str = "") -> str:
    p = rel(depth)
    links = "".join(
        f'<a href="{p}{href}"{" class=\"active\"" if href == active else ""}>{esc(label)}</a>'
        for href, label in NAV_ITEMS
    ) + '<a href="https://opensourcemed.info" rel="noopener">opensourcemed.info</a>'
    return f"""<nav class="nav" aria-label="Main navigation"><div class="nav-in">
<a class="brand" href="{p}index.html">OSMF Research Tracker</a>
<div class="links">{links}</div>
</div></nav>
"""


def footer(depth: int) -> str:
    p = rel(depth)
    return f"""<footer><div class="in">
<span>© {TODAY.year} Open Source Medicine Foundation · Educational synthesis, not medical advice.</span>
<span><a href="{p}biomarker-atlas.html">Biomarker Atlas</a> · <a href="{p}biomarkers/index.html">All marker pages</a> · <a href="https://opensourcemed.info" rel="noopener">opensourcemed.info</a> · <a href="{SUBSTACK}" rel="noopener">Subscribe</a></span>
</div></footer>
</body>
</html>
"""


def crumbs(items):
    """items: list of (href|None, label)"""
    parts = []
    for href, label in items:
        if href:
            parts.append(f'<a href="{esc(href)}">{esc(label)}</a>')
        else:
            parts.append(f"<strong>{esc(label)}</strong>")
    return '<div class="crumbs">' + "<span>›</span>".join(parts) + "</div>"


def breadcrumb_ld(items):
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i + 1, "name": label, "item": url}
            for i, (url, label) in enumerate(items)
        ],
    }


def faq_ld(qas):
    return {
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in qas
        ],
    }


def faq_html(qas):
    return '<div class="faq">' + "".join(
        f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in qas
    ) + "</div>"


def cta_box():
    return f"""<div class="cta"><strong>Get OSMF research updates.</strong> New biomarker, trial and treatment evidence summaries by email.<br>
<a class="btn" href="{SUBSTACK}" rel="noopener">Subscribe on Substack</a></div>"""


# ----------------------------------------------------------------------------
# per-marker (condition) page
# ----------------------------------------------------------------------------
def comparison_phrase(r: M, default: str = "a comparison group") -> str:
    """Comparison group as a noun phrase usable after 'than in' / 'relative to'."""
    comp = r.comparison_long or default
    if " vs " in comp.lower() or " versus " in comp.lower():
        return f"the reference group of the cited comparison ({comp})"
    return comp


def intro_paragraph(r: M) -> str:
    seed = f"{r.cond_slug}|{r.slug}"
    d = r.direction
    cond = r.cond_short
    alt = f" ({', '.join(r.cond_alt[:2])})" if r.cond_alt else ""
    comp = comparison_phrase(r)
    cat = r.category_label.lower() if r.category_label else "biomarker"
    marker_alt = f", also described as {r.alt}," if r.alt else ""

    s1_opts = {
        "up": [
            f"{r.name}{marker_alt} is a {cat} marker reported as elevated in {cond}{alt} when patients are compared with {comp}.",
            f"In {cond}{alt}, published studies report higher levels of {r.name}{marker_alt} than in {comp}.",
            f"{r.name}{marker_alt} belongs to the {cat} group of {cond}{alt} markers and is reported to be raised relative to {comp}.",
        ],
        "down": [
            f"{r.name}{marker_alt} is a {cat} marker reported as reduced in {cond}{alt} when patients are compared with {comp}.",
            f"In {cond}{alt}, published studies report lower levels of {r.name}{marker_alt} than in {comp}.",
            f"{r.name}{marker_alt} belongs to the {cat} group of {cond}{alt} markers and is reported to be decreased relative to {comp}.",
        ],
        "mixed": [
            f"{r.name}{marker_alt} is a {cat} marker with mixed findings in {cond}{alt}: studies comparing patients with {comp} report both increases and decreases.",
            f"In {cond}{alt}, the direction of change for {r.name}{marker_alt} is inconsistent across studies that used {comp} as the reference group.",
            f"{r.name}{marker_alt} belongs to the {cat} group of {cond}{alt} markers, but reports against {comp} point in different directions.",
        ],
    }
    s1 = stable_pick(seed + "1", s1_opts[d])
    if r.symptoms:
        sym = r.symptoms.rstrip(".")
        sym = sym[0].lower() + sym[1:] if sym and not sym[:2].isupper() else sym
        s2 = stable_pick(seed + "2", [
            f" The cited literature links this alteration to {sym}.",
            f" Clinically, it has been associated with {sym}.",
            f" Symptom domains tied to this marker in the source include {sym}.",
        ])
    else:
        s2 = " The source does not tie this marker to a specific symptom cluster, so it is best read as a biological signal rather than a symptom predictor."
    src = r.citation or "the cited review"
    s3 = stable_pick(seed + "3", [
        f" The finding is drawn from {src}; it describes group-level differences, not a threshold that classifies an individual.",
        f" This entry summarises {src}. Group-level associations like this do not translate into an individual diagnostic cut-off.",
        f" The evidence summarised here comes from {src} and reflects averages across cohorts rather than any single patient's result.",
    ])
    return s1 + s2 + s3


def summary_table(r: M, depth: int) -> str:
    rows = []
    rows.append(("Direction in " + r.cond_short,
                 f'<span class="dir dir-{r.direction}">{DIRECTION_ARROW[r.direction]} {DIRECTION_WORD[r.direction].capitalize()}</span> — {esc(DIRECTION_LONG[r.direction])}'))
    if r.category_label:
        rows.append(("Category", esc(r.category_label)))
    if r.alt:
        rows.append(("Also described as", esc(r.alt)))
    if r.comparison:
        c = esc(r.comparison)
        if r.comparison_long and r.comparison_long != r.comparison:
            c += f' <span class="muted">({esc(r.comparison_long)})</span>'
        rows.append(("Compared against", c))
    if r.symptoms:
        rows.append(("Associated symptoms", esc(r.symptoms)))
    if r.test_type:
        rows.append(("Test type", esc(TEST_TYPE_LABEL.get(r.test_type, r.test_type))))
    if r.loinc:
        rows.append(("LOINC code", f'<a href="https://loinc.org/{esc(r.loinc)}" rel="noopener">{esc(r.loinc)}</a>'))
    if r.citation or r.doi:
        c = esc(r.citation)
        if r.doi:
            c += f' — <a href="{esc(doi_url(r.doi))}" rel="noopener">doi:{esc(r.doi)}</a>'
        rows.append(("Source", c))
    rows.append(("Condition atlas", f'<a href="{rel(depth)}{r.cond_page}">{esc(r.cond_short)} Biomarker Atlas</a>'))
    body = "".join(f'<tr><th scope="row">{esc(k)}</th><td>{v}</td></tr>' for k, v in rows)
    return f'<div class="tbl-wrap"><table class="tbl"><tbody>{body}</tbody></table></div>'


def other_conditions_section(r: M, depth: int) -> str:
    sibs = [m for m in r.hub.members if m is not r]
    if not sibs:
        return ""
    items = "".join(
        f'<li><a href="{rel(depth)}{m.url_path}">{esc(m.name)} in {esc(m.cond_short)}</a> — '
        f'<span class="dir dir-{m.direction}">{DIRECTION_ARROW[m.direction]} {esc(DIRECTION_WORD[m.direction])}</span>'
        + (f" vs {esc(m.comparison)}" if m.comparison else "") + "</li>"
        for m in sibs
    )
    return f"""<section class="card"><h2>Other conditions where {esc(r.hub.name)} is reported</h2>
<ul>{items}</ul>
<p class="muted">See the cross-condition hub: <a href="{rel(depth)}{r.hub.url_path}">{esc(r.hub.name)} across conditions</a>.</p></section>"""


def enrichment_sections(r: M) -> str:
    out = []
    if r.outcome:
        o = r.outcome
        pt = clean(o.get("preferredTerm"))
        tc = o.get("trialCount") or 0
        if pt:
            out.append(f'<p class="muted">In clinical-trial registrations this marker maps to the outcome term <strong>{esc(pt)}</strong>'
                       + (f" ({tc} registered trials use a matching outcome measure)" if tc else "") + ".</p>")
    if r.trials:
        li = []
        for t in r.trials[:8]:
            om = clean(t.get("outcomeMeasure"))
            st = clean(t.get("status")).replace("_", " ").title()
            li.append(f'<li><a href="{esc(t.get("link"))}" rel="noopener">{esc(t.get("nct_id"))}</a>: {esc(t.get("title"))}'
                      + (f' <span class="muted">({esc(st)})</span>' if st else "")
                      + (f'<br><span class="muted">Outcome measure: {esc(om)}</span>' if om else "") + "</li>")
        more = f'<p class="muted">{len(r.trials) - 8} more trials reference this marker.</p>' if len(r.trials) > 8 else ""
        out.append(f"<h3>Clinical trials using {esc(r.name)} as an outcome</h3><ul>{''.join(li)}</ul>{more}")
    if r.interventions:
        li = []
        for iv in r.interventions[:8]:
            lit = iv.get("literature") or {}
            arts = lit.get("topArticles") or []
            ncts = iv.get("nctIds") or []
            bits = []
            if ncts:
                bits.append(f"{len(ncts)} trial{'s' if len(ncts) != 1 else ''}")
            if lit.get("pmidCount"):
                bits.append(f"{lit['pmidCount']} PubMed co-citations")
            art = ""
            if arts:
                a = arts[0]
                art = f'<br><span class="muted">e.g. <a href="{esc(a.get("url"))}" rel="noopener">{esc(truncate(clean(a.get("title")), 110))}</a></span>'
            li.append(f"<li><strong>{esc(iv.get('preferredTerm'))}</strong>" + (f" — {esc(', '.join(bits))}" if bits else "") + art + "</li>")
        out.append(f'<h3>Interventions studied alongside this marker</h3><p class="muted">Hypothesis-generating links from trial outcome usage and literature co-occurrence. Not treatment recommendations.</p><ul>{"".join(li)}</ul>')
    if r.commercial and r.commercial.get("vendors"):
        v = "".join(f'<li><a href="{esc(x.get("url"))}" rel="noopener nofollow">{esc(x.get("vendor"))}</a></li>' for x in r.commercial["vendors"])
        note = clean(r.commercial.get("note"))
        out.append(f"<h3>Commercial test availability</h3><p>{esc(clean(r.commercial.get('testName')) or r.name)} — {esc(clean(r.commercial.get('availability')) or 'available')} laboratory test."
                   + (f" {esc(note)}" if note else "") + f'</p><ul>{v}</ul><p class="muted">Links are for reference only; availability, specimen requirements and coverage vary by location.</p>')
    if r.consumable and r.consumable.get("consumable"):
        c = r.consumable
        ptype = clean(c.get("productType")).replace("_", " ")
        out.append(f"<h3>Also sold as a nutrient or supplement</h3><p>{esc(clean(c.get('productName')) or r.name)}"
                   + (f" ({esc(ptype)})" if ptype else "")
                   + (f". {esc(clean(c.get('note')))}" if clean(c.get('note')) else "")
                   + " This tag means the analyte is also available orally; it is not a product endorsement and a low or high level does not by itself justify supplementation.</p>")
    if r.agents and isinstance(r.agents, list):
        names = [clean(a if isinstance(a, str) else (a.get("name") or a.get("preferredTerm"))) for a in r.agents[:8]]
        names = [n for n in names if n]
        if names:
            out.append("<h3>Therapeutic agents linked by discovery pipeline</h3><ul>" + "".join(f"<li>{esc(n)}</li>" for n in names) + "</ul>")
    if not out:
        return ""
    return '<section class="card"><h2>Trials, interventions and tests</h2>' + "".join(out) + "</section>"


def related_section(r: M, all_in_cond: list, depth: int) -> str:
    same = [m for m in all_in_cond if m is not r and m.category == r.category]
    if not same:
        same = [m for m in all_in_cond if m is not r]
    if not same:
        return ""
    idx = all_in_cond.index(r)
    same.sort(key=lambda m: abs(all_in_cond.index(m) - idx))
    pick = same[:8]
    li = "".join(
        f'<li><a href="{rel(depth)}{m.url_path}">{esc(m.name)}</a> <span class="dir dir-{m.direction}">{DIRECTION_ARROW[m.direction]}</span></li>'
        for m in pick
    )
    label = f"{r.category_label} markers" if r.category_label else "markers"
    return f'<section class="card"><h2>Related {esc(label)} in {esc(r.cond_short)}</h2><ul class="grid">{li}</ul><p class="muted">Full list: <a href="{rel(depth)}{r.cond_page}">{esc(r.cond_short)} Biomarker Atlas</a>.</p></section>'


def marker_faq(r: M):
    qas = []
    d = r.direction
    comp = comparison_phrase(r, default="controls")
    if d == "up":
        a = f"Elevated. Studies summarised in the OSMF atlas report higher {r.name} in {r.cond_short} than in {comp}."
    elif d == "down":
        a = f"Reduced. Studies summarised in the OSMF atlas report lower {r.name} in {r.cond_short} than in {comp}."
    else:
        a = f"Mixed. Some studies report higher and others lower {r.name} in {r.cond_short} compared with {comp}, so no single direction is established."
    a += f" Source: {r.citation}." if r.citation else ""
    qas.append((f"Is {r.name} high or low in {r.cond_short}?", a))
    if r.symptoms:
        qas.append((f"What symptoms is {r.name} associated with in {r.cond_short}?",
                    f"The cited literature associates this marker with {r.symptoms.rstrip('.')}. These are population-level associations and do not mean the marker causes the symptoms."))
    if r.loinc or r.test_type or (r.commercial and r.commercial.get("vendors")):
        bits = []
        if r.test_type:
            bits.append(f"It is measured as a {TEST_TYPE_LABEL.get(r.test_type, r.test_type).lower()}.")
        if r.loinc:
            bits.append(f"The standard laboratory code is LOINC {r.loinc}.")
        if r.commercial and r.commercial.get("vendors"):
            bits.append("Commercial laboratories such as " + ", ".join(clean(v.get("vendor")) for v in r.commercial["vendors"][:3]) + " list an orderable assay.")
        else:
            bits.append("Many of the cited studies used research-grade assays, so clinical availability may vary.")
        qas.append((f"Which test measures {r.name}?", " ".join(bits)))
    else:
        qas.append((f"Which test measures {r.name}?",
                    f"The atlas record does not list a standardised clinical test code (LOINC) for {r.name}, which usually means it was measured with research assays or study-specific protocols rather than a routine clinical panel. Check the cited source for the exact method."))
    qas.append((f"Is one abnormal {r.name} result diagnostic of {r.cond_short}?",
                f"No. No single biomarker is diagnostic of {r.cond_short}. {r.name} findings come from group comparisons, overlap considerably between patients and controls, and vary with study design, timing and comparison group. A result should be interpreted by a clinician alongside symptoms, history and other tests."))
    if len(r.hub.members) > 1:
        others = sorted({m.cond_short for m in r.hub.members if m is not r})
        qas.append((f"Is {r.name} specific to {r.cond_short}?",
                    f"No. The same marker is also reported in {', '.join(others)} in this atlas, so it reflects shared biology (for example inflammation or vascular stress) rather than a condition-specific signature."))
    return qas[:5]


def cite_box(title: str, url: str, year: str) -> str:
    apa = f"Open Source Medicine Foundation. ({year}). {title}. OSMF Research Tracker. Retrieved {ACCESSED}, from {url}"
    return f'<section class="card"><h2>Cite this page</h2><div class="cite">{esc(apa)}</div></section>'


def marker_jsonld(r: M, qas, desc):
    test = {
        "@type": "MedicalTest",
        "name": r.name,
        "url": r.url,
        "description": desc,
        "mainEntityOfPage": r.url,
        "about": {"@type": "MedicalCondition", "name": r.cond_name, **({"alternateName": r.cond_alt} if r.cond_alt else {})},
        "sourceOrganization": {"@type": "Organization", "name": "Open Source Medicine Foundation", "url": "https://opensourcemed.info"},
        "lastReviewed": r.cond_date,
    }
    if r.alt:
        test["alternateName"] = r.alt
    if r.loinc:
        test["code"] = {"@type": "MedicalCode", "codeValue": r.loinc, "codingSystem": "LOINC"}
    if r.citation or r.doi:
        cit = {"@type": "ScholarlyArticle", "name": r.citation or r.doi}
        if r.doi:
            cit["identifier"] = f"doi:{r.doi}"
            cit["url"] = doi_url(r.doi)
        test["citation"] = cit
    dataset = {
        "@type": "Dataset",
        "name": f"{r.cond_name} biomarker atlas (OSMF)",
        "description": f"Structured JSON record of biomarkers reported in {r.cond_name}, including {r.name}, with direction of change, comparison group, symptoms and source DOI.",
        "url": f"{SITE}/{r.cond_page}",
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "creator": {"@type": "Organization", "name": "Open Source Medicine Foundation"},
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE}/data/biomarkers/{r.cond_slug}.json"}],
        "variableMeasured": r.name,
        "dateModified": r.cond_date,
    }
    bc = breadcrumb_ld([
        (f"{SITE}/index.html", "Research Tracker"),
        (f"{SITE}/biomarker-atlas.html", "Biomarker Atlas"),
        (f"{SITE}/{r.cond_page}", r.cond_short),
        (r.url, r.name),
    ])
    return {"@context": "https://schema.org", "@graph": [bc, faq_ld(qas), test, dataset]}


def render_marker_page(r: M, cond_records: list) -> str:
    depth = 2
    p = rel(depth)
    title = f"{r.name} in {r.cond_short}: direction, evidence and what it means | OSMF"
    if len(title) > 60:
        title = f"{r.name} in {r.cond_short}: evidence & meaning | OSMF"
    if len(title) > 60:
        title = f"{r.name} in {r.cond_short} | OSMF"
    dw = DIRECTION_WORD[r.direction]
    desc = f"{r.name} is {dw} in {r.cond_short}" + (f" vs {r.comparison_long}" if r.comparison_long else "") + "."
    if r.symptoms:
        desc += f" Linked to {r.symptoms.rstrip('.')}."
    desc += f" Source: {r.citation}." if r.citation else ""
    desc += " Direction, test, FAQ."
    desc = truncate(desc, 158)
    qas = marker_faq(r)
    ld = marker_jsonld(r, qas, desc)
    h = head(title, desc, r.url, ld)
    crumb = crumbs([
        (p + "index.html", "Research Tracker"),
        (p + "biomarker-atlas.html", "Biomarker Atlas"),
        (p + r.cond_page, r.cond_short),
        (None, r.name),
    ])
    pills = f'<span class="pill">{DIRECTION_ARROW[r.direction]} {esc(dw.capitalize())}</span>'
    if r.category_label:
        pills += f'<span class="pill">{esc(r.category_label)}</span>'
    if r.loinc:
        pills += f'<span class="pill">LOINC {esc(r.loinc)}</span>'
    body = f"""<body>
{nav(depth, "biomarker-atlas.html")}
<header class="hero"><div class="hero-in">
{crumb}
<h1>{esc(r.name)} in {esc(r.cond_short)}</h1>
<p>{esc(intro_paragraph(r))}</p>
{pills}
</div></header>
<main>
<section class="card"><h2>Summary</h2>{summary_table(r, depth)}</section>
{other_conditions_section(r, depth)}
{enrichment_sections(r)}
{related_section(r, cond_records, depth)}
<section class="card"><h2>Frequently asked questions</h2>{faq_html(qas)}</section>
{cite_box(f"{r.name} in {r.cond_short}: direction, evidence and what it means", r.url, r.cond_date[:4])}
{cta_box()}
<p class="muted">Last reviewed: {esc(r.cond_date)} · Page generated from <a href="{p}data/biomarkers/{esc(r.cond_slug)}.json">{esc(r.cond_slug)}.json</a> · Browse: <a href="{p}{r.cond_page}">{esc(r.cond_short)} atlas</a> · <a href="{p}biomarker-index.html">Biomarker Index</a> · <a href="{p}biomarkers/index.html">All marker pages</a></p>
<p class="disc"><strong>Disclaimer:</strong> This page is an educational synthesis of published, peer-reviewed research and is not medical advice. Biomarker findings vary across studies with case definitions, comparison groups, timing and assay methods. Direction of change reflects the predominant finding in the cited source and does not establish a diagnostic threshold. Discuss any test result with a qualified clinician.</p>
</main>
{footer(depth)}"""
    return h + body


# ----------------------------------------------------------------------------
# hub page
# ----------------------------------------------------------------------------
def render_hub_page(hub: M) -> str:
    depth = 2
    p = rel(depth)
    conds = sorted({m.cond_short for m in hub.members})
    n = len(conds)
    if n > 1:
        title = f"{hub.name} across {n} conditions: biomarker evidence | OSMF"
        if len(title) > 60:
            title = f"{hub.name}: evidence across {n} conditions | OSMF"
    else:
        title = f"{hub.name}: biomarker evidence | OSMF"
    if len(title) > 60:
        title = f"{hub.name} biomarker hub | OSMF"
    ups = sum(1 for m in hub.members if m.direction == "up")
    downs = sum(1 for m in hub.members if m.direction == "down")
    mixed = sum(1 for m in hub.members if m.direction == "mixed")
    dir_summary = ", ".join(x for x in [f"elevated in {ups}" if ups else "", f"reduced in {downs}" if downs else "", f"mixed in {mixed}" if mixed else ""] if x)
    desc = truncate(f"{hub.name} reported in {', '.join(conds)}: {dir_summary} of {len(hub.members)} atlas entries, with comparison groups, LOINC codes and source DOIs.", 158)
    intro = (f"{hub.name} appears in {len(hub.members)} entr{'y' if len(hub.members) == 1 else 'ies'} of the OSMF biomarker atlas, covering {', '.join(conds)}. "
             f"Across those entries it is {dir_summary}. "
             + ("Because the same marker shifts in several unrelated conditions, it is best understood as a signal of shared biology such as inflammation, vascular or metabolic stress rather than as a condition-specific test. "
                if n > 1 else "It is currently reported in a single condition in this atlas; cross-condition comparison will be added as the dataset grows. ")
             + "Each row below links to a page with the comparison group, associated symptoms, test details and primary citation.")
    rows = ""
    for m in hub.members:
        src = f'<a href="{esc(doi_url(m.doi))}" rel="noopener">{esc(m.citation or m.doi)}</a>' if m.doi else esc(m.citation or "—")
        rows += (f'<tr><td><a href="{p}{m.url_path}">{esc(m.cond_short)}</a></td>'
                 f'<td><span class="dir dir-{m.direction}">{DIRECTION_ARROW[m.direction]} {esc(DIRECTION_WORD[m.direction])}</span></td>'
                 f'<td>{esc(m.comparison_long or m.comparison or "—")}</td>'
                 f'<td>{esc(m.symptoms or "—")}</td>'
                 f"<td>{src}</td></tr>")
    qas = []
    qas.append((f"In which conditions is {hub.name} altered?",
                f"In the OSMF atlas {hub.name} is reported in {', '.join(conds)}. It is {dir_summary} across {len(hub.members)} entries."))
    if n > 1:
        qas.append((f"Does {hub.name} point to one specific diagnosis?",
                    f"No. Because {hub.name} changes in several conditions ({', '.join(conds)}), an abnormal result cannot identify which condition, if any, is present. It must be interpreted with symptoms, history and other tests."))
    if hub.loincs:
        qas.append((f"What is the LOINC code for {hub.name}?",
                    f"Entries in this atlas use LOINC {', '.join(hub.loincs)}. LOINC codes identify the laboratory observation so results can be compared across systems."))
    else:
        qas.append((f"Is there a standard clinical test for {hub.name}?",
                    f"The atlas entries for {hub.name} do not carry a LOINC code, which usually means the marker was measured with research assays or study-specific methods rather than a routine clinical panel."))
    qas.append((f"Is one abnormal {hub.name} result diagnostic?",
                "No single biomarker result is diagnostic of any of these conditions. Findings reflect group averages from published cohorts with substantial overlap between patients and controls."))
    bc = breadcrumb_ld([
        (f"{SITE}/index.html", "Research Tracker"),
        (f"{SITE}/biomarker-atlas.html", "Biomarker Atlas"),
        (f"{SITE}/biomarkers/index.html", "Marker Pages"),
        (hub.url, hub.name),
    ])
    last = max(m.cond_date for m in hub.members)
    entity = {
        "@type": "MedicalTest",
        "name": hub.name,
        "url": hub.url,
        "description": desc,
        "about": [{"@type": "MedicalCondition", "name": c} for c in sorted({m.cond_name for m in hub.members})],
        "sourceOrganization": {"@type": "Organization", "name": "Open Source Medicine Foundation", "url": "https://opensourcemed.info"},
        "lastReviewed": last,
    }
    if hub.alts:
        entity["alternateName"] = hub.alts
    if hub.loincs:
        entity["code"] = [{"@type": "MedicalCode", "codeValue": c, "codingSystem": "LOINC"} for c in hub.loincs]
    cits = [{"@type": "ScholarlyArticle", "name": m.citation or m.doi, "identifier": f"doi:{m.doi}", "url": doi_url(m.doi)} for m in hub.members if m.doi]
    if cits:
        entity["citation"] = cits
    dataset = {
        "@type": "Dataset",
        "name": "OSMF biomarker atlas: " + hub.name,
        "description": f"Cross-condition records for {hub.name} drawn from {len(hub.members)} OSMF biomarker atlas entries ({', '.join(conds)}), each with direction, comparison group and source DOI.",
        "url": hub.url,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "creator": {"@type": "Organization", "name": "Open Source Medicine Foundation"},
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": f"{SITE}/data/biomarkers/{s}.json"} for s in sorted({m.cond_slug for m in hub.members})],
        "variableMeasured": hub.name,
    }
    ld = {"@context": "https://schema.org", "@graph": [bc, faq_ld(qas), entity, dataset]}
    robots = "index, follow, max-image-preview:large" if n > 1 else "noindex, follow"
    h = head(title, desc, hub.url, ld, robots=robots)
    crumb = crumbs([
        (p + "index.html", "Research Tracker"),
        (p + "biomarker-atlas.html", "Biomarker Atlas"),
        (p + "biomarkers/index.html", "Marker Pages"),
        (None, hub.name),
    ])
    alts = f'<p class="muted">Also listed as: {esc("; ".join(hub.alts))}</p>' if hub.alts else ""
    body = f"""<body>
{nav(depth, "biomarker-atlas.html")}
<header class="hero"><div class="hero-in">
{crumb}
<h1>{esc(hub.name)}{" across conditions" if n > 1 else ": biomarker evidence"}</h1>
<p>{esc(intro)}</p>
{''.join(f'<span class="pill">{esc(c)}</span>' for c in conds)}
</div></header>
<main>
<section class="card"><h2>Where {esc(hub.name)} is reported</h2>{alts}
<div class="tbl-wrap"><table class="tbl"><thead><tr><th>Condition</th><th>Direction</th><th>Compared against</th><th>Associated symptoms</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<section class="card"><h2>Frequently asked questions</h2>{faq_html(qas)}</section>
{cite_box(f"{hub.name} across conditions: biomarker evidence", hub.url, last[:4])}
{cta_box()}
<p class="muted">Last reviewed: {esc(last)} · Browse: <a href="{p}biomarker-index.html">Biomarker Index</a> · <a href="{p}biomarkers/index.html">All marker pages</a> · <a href="{p}biomarker-atlas.html">Biomarker Atlas</a></p>
<p class="disc"><strong>Disclaimer:</strong> Educational synthesis of peer-reviewed research; not medical advice. Findings are group-level and vary with study design. Discuss any result with a qualified clinician.</p>
</main>
{footer(depth)}"""
    return h + body


# ----------------------------------------------------------------------------
# index page
# ----------------------------------------------------------------------------
SEARCH_JS = """
(function(){
  var box=document.getElementById('q'),out=document.getElementById('results'),data=null;
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  function render(q){
    if(!data){return;}
    q=q.trim().toLowerCase();
    if(q.length<2){out.innerHTML='';return;}
    var hits=data.pages.filter(function(x){return (x.name+' '+(x.alt||'')+' '+x.condition+' '+(x.loinc||'')).toLowerCase().indexOf(q)>-1;}).slice(0,60);
    if(!hits.length){out.innerHTML='<p class="muted">No matches.</p>';return;}
    out.innerHTML='<ul class="grid">'+hits.map(function(x){return '<li><a href="'+esc(x.path)+'">'+esc(x.name)+'</a> <span class="muted">'+esc(x.condition)+' '+esc(x.arrow)+'</span></li>';}).join('')+'</ul>';
  }
  box.addEventListener('input',function(){render(box.value);});
  fetch('../js/generated/marker-pages-index.json').then(function(r){return r.json();}).then(function(j){data=j;if(box.value){render(box.value);}}).catch(function(){out.innerHTML='<p class="muted">Search index unavailable; use the lists below.</p>';});
})();
"""


def render_index(conds, records, hubs) -> str:
    depth = 1
    p = rel(depth)
    url = f"{SITE}/biomarkers/index.html"
    multi = sum(1 for h in hubs.values() if len({m.cond_slug for m in h.members}) > 1)
    title = "Biomarker pages by condition and marker | OSMF"
    desc = truncate(f"{len(records)} biomarker pages across {len(conds)} conditions and {len(hubs)} cross-condition marker hubs ({multi} markers shared by two or more conditions). Search by marker or condition.", 158)
    by_cond = defaultdict(list)
    for r in records:
        by_cond[r.cond_slug].append(r)

    def short(d):
        return d["condition"].get("shortName") or d["condition"].get("name")

    cond_items = []
    for d in conds:
        rs = by_cond.get(d["slug"], [])
        up = sum(1 for r in rs if r.direction == "up")
        down = sum(1 for r in rs if r.direction == "down")
        mixed = sum(1 for r in rs if r.direction == "mixed")
        cond_items.append(
            f'<li><a href="{p}{d["slug"]}-biomarkers.html"><strong>{esc(short(d))}</strong></a>'
            f'<div class="n">{len(rs)} markers · ↑{up} ↓{down} ↕{mixed} · <a href="#c-{esc(d["slug"])}">jump to list</a></div></li>')
    sections = []
    for d in conds:
        rs = by_cond.get(d["slug"], [])
        cats = defaultdict(list)
        for r in rs:
            cats[r.category_label or "Other"].append(r)
        inner = ""
        for cat in sorted(cats):
            li = "".join(f'<li><a href="{p}{r.url_path}">{esc(r.name)}</a> <span class="dir dir-{r.direction}">{DIRECTION_ARROW[r.direction]}</span></li>' for r in cats[cat])
            inner += f'<h3>{esc(cat)}</h3><ul class="grid">{li}</ul>'
        sections.append(f'<section class="card" id="c-{esc(d["slug"])}"><h2>{esc(short(d))} <span class="muted">({len(rs)} markers)</span></h2>'
                        f'<p class="muted"><a href="{p}{d["slug"]}-biomarkers.html">Open the {esc(short(d))} atlas</a></p>{inner}</section>')
    hub_sorted = sorted(hubs.values(), key=lambda h: (-len({m.cond_slug for m in h.members}), h.name.lower()))
    hub_li = ""
    for h in hub_sorted:
        nc = len({m.cond_slug for m in h.members})
        hub_li += f'<li><a href="{p}{h.url_path}">{esc(h.name)}</a> <span class="muted">({nc} condition{"s" if nc != 1 else ""})</span></li>'
    bc = breadcrumb_ld([
        (f"{SITE}/index.html", "Research Tracker"),
        (f"{SITE}/biomarker-atlas.html", "Biomarker Atlas"),
        (url, "Marker Pages"),
    ])
    ld = {"@context": "https://schema.org", "@graph": [bc, {
        "@type": "CollectionPage", "name": title, "url": url, "description": desc,
        "isPartOf": {"@type": "WebSite", "name": "OSMF Research Tracker", "url": SITE + "/"},
    }]}
    hd = head(title, desc, url, ld)
    crumb = crumbs([(p + "index.html", "Research Tracker"), (p + "biomarker-atlas.html", "Biomarker Atlas"), (None, "Marker Pages")])
    body = f"""<body>
{nav(depth, "biomarkers/index.html")}
<header class="hero"><div class="hero-in">
{crumb}
<h1>Biomarker pages by condition and marker</h1>
<p>{esc(desc)}</p>
</div></header>
<main>
<section class="card"><h2>Search markers</h2>
<label for="q" class="muted">Type a marker name, abbreviation, LOINC code or condition</label>
<input class="search" id="q" type="search" placeholder="e.g. IL-6, D-dimer, 26881-5, Lyme" autocomplete="off">
<div id="results"></div>
<script>{SEARCH_JS}</script></section>
<section class="card"><h2>Conditions</h2><ul class="cond-list">{''.join(cond_items)}</ul></section>
<section class="card"><h2>Cross-condition marker hubs <span class="muted">({len(hubs)})</span></h2><ul class="grid">{hub_li}</ul></section>
{''.join(sections)}
{cta_box()}
<p class="muted">Generated {BUILD_DATE} from the atlas JSON files. See also the <a href="{p}biomarker-index.html">cross-condition Biomarker Index</a> and the <a href="{p}biomarker-atlas.html">Biomarker Atlas hub</a>.</p>
</main>
{footer(depth)}"""
    return hd + body


# ----------------------------------------------------------------------------
# atlas injection
# ----------------------------------------------------------------------------
START = "<!-- MARKER_PAGES_START -->"
END = "<!-- MARKER_PAGES_END -->"


def inject_atlas(d, rs):
    path = ROOT / f"{d['slug']}-biomarkers.html"
    if not path.exists():
        return False, "missing atlas page"
    raw = path.read_bytes().decode("utf-8")
    nl = dominant_newline(raw)
    cats = defaultdict(list)
    for r in rs:
        cats[r.category_label or "Other"].append(r)
    short = d["condition"].get("shortName") or d["condition"].get("name")
    parts = [START,
             '<section class="section" id="marker-pages" style="max-width:1200px;margin:0 auto;padding:2rem 1.5rem;">',
             f'<h2 style="font-size:1.4rem;margin-bottom:.5rem;">Individual {html.escape(short)} biomarker pages</h2>',
             f'<p style="color:#6b7280;margin-bottom:1rem;">Each {html.escape(short)} marker has its own page with direction, comparison group, symptoms, test details, citation and FAQ. '
             '<a href="biomarkers/index.html">Browse all marker pages</a>.</p>']
    for cat in sorted(cats):
        li = "".join(f'<li style="margin:.25rem 0;"><a href="{r.url_path}">{html.escape(r.name)}</a> {DIRECTION_ARROW[r.direction]}</li>' for r in cats[cat])
        parts.append(f'<h3 style="font-size:1rem;margin:.9rem 0 .3rem;">{html.escape(cat)}</h3>'
                     f'<ul style="list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:.1rem 1rem;">{li}</ul>')
    parts.append("</section>")
    parts.append(END)
    block = nl.join(parts)
    pat = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if pat.search(raw):
        new = pat.sub(lambda _m: block, raw, count=1)
        action = "replaced"
    else:
        idx = raw.find("<footer")
        if idx < 0:
            return False, "no <footer> found"
        ls = raw.rfind("\n", 0, idx) + 1
        indent = raw[ls:idx]
        new = raw[:ls] + block + nl + indent + raw[idx:]
        action = "inserted"
    if new != raw:
        path.write_bytes(new.encode("utf-8"))
    return True, action


# ----------------------------------------------------------------------------
# link check
# ----------------------------------------------------------------------------
def check_links(paths):
    bad = []
    for pth in paths:
        txt = pth.read_text(encoding="utf-8")
        for href in re.findall(r'href="([^"]+)"', txt):
            if href.startswith(("http", "mailto:", "#", "/sitemap")) or "'" in href:
                continue
            target = href.split("#")[0]
            if not target:
                continue
            t = (pth.parent / target).resolve()
            if t.is_dir():
                continue
            if not t.exists():
                bad.append((str(pth.relative_to(ROOT)), href))
    return bad


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="condition slug to build (testing)")
    ap.add_argument("--check", action="store_true", help="verify internal links after build")
    ap.add_argument("--no-inject", action="store_true", help="skip atlas page injection")
    args = ap.parse_args()

    conds = load_conditions(args.only)
    if not conds:
        print("no condition files found", file=sys.stderr)
        sys.exit(1)
    enr = load_enrichment()
    records, skipped = build_records(conds, enr)
    hubs = group_markers(records)
    by_cond = defaultdict(list)
    for r in records:
        by_cond[r.cond_slug].append(r)

    written = []
    for r in records:
        out = OUT / r.cond_slug / f"{r.slug}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_marker_page(r, by_cond[r.cond_slug]), encoding="utf-8", newline="\n")
        written.append(out)
    for hub in hubs.values():
        out = OUT / "markers" / f"{hub.slug}.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_hub_page(hub), encoding="utf-8", newline="\n")
        written.append(out)
    if not args.only:
        keep = {p.resolve() for p in written}
        for old in OUT.rglob("*.html"):
            if old.name == "index.html" and old.parent == OUT:
                continue
            if old.resolve() not in keep:
                old.unlink()
                print("removed stale", old.relative_to(ROOT))
    idx = OUT / "index.html"
    idx.write_text(render_index(conds, records, hubs), encoding="utf-8", newline="\n")
    written.append(idx)

    gen = ROOT / "js" / "generated"
    gen.mkdir(parents=True, exist_ok=True)
    pages = [{
        "name": r.name, "alt": r.alt, "condition": r.cond_short, "slug": r.cond_slug,
        "direction": r.direction, "arrow": DIRECTION_ARROW[r.direction], "category": r.category_label,
        "loinc": r.loinc, "path": r.url_path.replace("biomarkers/", "", 1), "hub": r.hub.url_path.replace("biomarkers/", "", 1),
    } for r in records]
    hubs_out = [{"name": h.name, "slug": h.slug, "path": h.url_path.replace("biomarkers/", "", 1),
                 "conditions": sorted({m.cond_short for m in h.members}), "loinc": h.loincs} for h in hubs.values()]
    (gen / "marker-pages-index.json").write_text(
        json.dumps({"generated": BUILD_DATE, "pageCount": len(pages), "hubCount": len(hubs_out), "pages": pages, "hubs": hubs_out}, ensure_ascii=False),
        encoding="utf-8", newline="\n")

    inj = {}
    if not args.no_inject:
        for d in conds:
            ok, msg = inject_atlas(d, by_cond[d["slug"]])
            inj[msg] = inj.get(msg, 0) + 1

    multi = sum(1 for h in hubs.values() if len({m.cond_slug for m in h.members}) > 1)
    print(f"conditions: {len(conds)}")
    print(f"marker pages: {len(records)}")
    print(f"hub pages: {len(hubs)} ({multi} multi-condition/indexable, {len(hubs) - multi} single-condition/noindex)")
    print(f"skipped (no name): {len(skipped)}")
    print(f"atlas injection: {inj}")
    print(f"index: {idx.relative_to(ROOT)}; search index: js/generated/marker-pages-index.json")
    enriched = sum(1 for r in records if r.trials or r.interventions or r.commercial or r.consumable)
    print(f"records with enrichment links: {enriched}")
    sparse = [f"{r.cond_slug}/{r.slug}" for r in records if not r.symptoms and not r.loinc and not r.test_type]
    print(f"sparse records (no symptoms, no LOINC, no test type): {len(sparse)}")
    for s in sparse[:40]:
        print("  sparse:", s)

    if args.check:
        bad = check_links(written)
        print(f"link check: {len(written)} pages, {len(bad)} broken internal links")
        for b in bad[:30]:
            print("  BROKEN", b)
        if bad:
            sys.exit(2)


if __name__ == "__main__":
    main()
