#!/usr/bin/env python3
"""Site-wide chrome pass for the public research tracker (idempotent).

1. Replace the VitalScan4PACVS nav that was mirrored onto ~20 tracker pages
   (links to the-science.html / the-protocol.html / vitalscan-01.jpg, none of
   which exist on this host) with the OSMF tracker nav, and drop the
   VitalScan "Status: In preparation" banner that came with it.
2. Add a "Cite this page" + Substack block before the footer of every
   public root-level page that lacks one (marked OSMF_CITE_START/END).
3. Add Dataset JSON-LD to the hub pages that expose JSON data
   (marked OSMF_DATASET_START/END).

Run from repo root:  python scripts/apply_osmf_chrome.py [--check]
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://research.opensourcemed.info"
EXCLUDED_NAMES = {"agents-local.html", "clinical_trials-local.html"}

OSMF_NAV = """<nav class="nav-minimal" aria-label="Main navigation">
    <div class="nav-container">
        <a href="https://opensourcemed.info" class="logo" style="color:#fff;text-decoration:none;font-weight:700;font-size:1.05rem;">Open Source <span style="font-weight:400;">Medicine</span> <span style="opacity:.8;font-weight:400;font-size:.85rem;">Research Tracker</span></a>
        <div class="nav-links">
            <a href="index.html" class="nav-link">Research Tracker</a>
            <a href="biomarker-atlas.html" class="nav-link">Biomarker Atlases</a>
            <a href="biomarkers/index.html" class="nav-link">Marker Pages</a>
            <a href="clinical_trials.html" class="nav-link">Clinical Trials</a>
            <a href="agents.html" class="nav-link">Therapeutic Agents</a>
            <a href="tools/index.html" class="nav-link">Tools</a>
            <a href="digest/index.html" class="nav-link">Digest</a>
            <a href="https://opensourcemed.info" class="nav-link">OSMF</a>
        </div>
    </div>
</nav>"""

NAV_RE = re.compile(
    r'<nav class="nav-minimal" aria-label="Main navigation">.*?</nav>', re.S
)
BANNER_RE = re.compile(
    r'\s*<div style="background:#fef3c7;[^"]*">Status: In preparation\.[^<]*</div>', re.S
)

DANGLING = {
    'href="the-science.html"': 'href="https://vitalscan4pacvs.study/" rel="noopener"',
    'href="the-protocol.html"': 'href="https://vitalscan4pacvs.study/" rel="noopener"',
    'href="vitalscan-logo.svg"': 'href="favicon.png"',
}

CITE_START, CITE_END = "<!-- OSMF_CITE_START -->", "<!-- OSMF_CITE_END -->"
DS_START, DS_END = "<!-- OSMF_DATASET_START -->", "<!-- OSMF_DATASET_END -->"

CITE_CSS = (
    "<style>.osmf-cite-wrap{max-width:1200px;margin:2.5rem auto 2rem;padding:0 1.5rem;"
    "display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));font-family:Inter,system-ui,sans-serif}"
    ".osmf-cite,.osmf-sub{border:1px solid #e5e7eb;border-radius:12px;padding:1.1rem 1.25rem;background:#f8fafc;color:#1f2937}"
    ".osmf-cite h3,.osmf-sub h3{font-size:1rem;margin:0 0 .5rem;color:#0052c7}"
    ".osmf-cite p,.osmf-sub p{font-size:.9rem;line-height:1.55;margin:0 0 .6rem}"
    ".osmf-cite code{display:block;white-space:normal;font-size:.82rem;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:.6rem .75rem;margin-bottom:.6rem}"
    ".osmf-cite button,.osmf-sub a.btn{display:inline-block;background:#0068f8;color:#fff;border:0;border-radius:8px;padding:.5rem .9rem;font-size:.85rem;font-weight:600;cursor:pointer;text-decoration:none}"
    ".osmf-cite button:hover,.osmf-sub a.btn:hover{background:#0052c7}</style>"
)


def public_pages() -> list[Path]:
    return sorted(p for p in ROOT.glob("*.html") if p.name not in EXCLUDED_NAMES)


def is_redirect_or_noindex(markup: str) -> bool:
    return bool(
        re.search(r"<meta\b[^>]*http-equiv\s*=\s*['\"]?refresh", markup, re.I)
        or re.search(r"<meta\b[^>]*name\s*=\s*['\"]robots['\"][^>]*noindex", markup, re.I)
    )


def page_title(markup: str) -> str:
    m = re.search(r"<title>(.*?)</title>", markup, re.S | re.I)
    t = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else "Research Tracker"
    return t.split("|")[0].split(" — ")[0].strip()


def cite_block(page: Path, markup: str) -> str:
    url = ORIGIN + "/" + ("" if page.name == "index.html" else page.name)
    title = html.escape(page_title(markup))
    year = date.today().year
    return f"""{CITE_START}
{CITE_CSS}
<section class="osmf-cite-wrap" aria-label="Cite and subscribe">
  <div class="osmf-cite">
    <h3>Cite this page</h3>
    <p>Reusing these data? Please cite the tracker so others can find the source.</p>
    <code id="osmf-cite-text">Open Source Medicine Foundation. ({year}). {title}. Research Tracker. {url} (accessed <span class="osmf-cite-date"></span>)</code>
    <button type="button" onclick="(function(b){{var t=document.getElementById('osmf-cite-text').innerText;if(navigator.clipboard){{navigator.clipboard.writeText(t).then(function(){{b.textContent='Copied';setTimeout(function(){{b.textContent='Copy citation'}},1500)}})}}}})(this)">Copy citation</button>
    <script>(function(){{var d=new Date();var s=document.querySelectorAll('.osmf-cite-date');for(var i=0;i<s.length;i++){{s[i].textContent=d.toISOString().slice(0,10)}}}})();</script>
  </div>
  <div class="osmf-sub">
    <h3>Weekly post-viral research digest</h3>
    <p>New peer-reviewed studies and trial activity across Long COVID, ME/CFS, PACVS, Lyme and Gulf War Illness, every week. Free, no spam.</p>
    <a class="btn" href="https://opensourcemed.substack.com/subscribe?utm_source=tracker&amp;utm_medium=cite_box" rel="noopener">Subscribe on Substack</a>
    &nbsp; <a href="digest/index.html" style="font-size:.85rem;color:#0052c7;">Browse the digest archive</a> · <a href="digest/feed.xml" style="font-size:.85rem;color:#0052c7;">RSS</a>
  </div>
</section>
{CITE_END}"""


def inject_before_footer(markup: str, block: str, start: str, end: str) -> str:
    if start in markup and end in markup:
        pre, rest = markup.split(start, 1)
        _, post = rest.split(end, 1)
        return pre + block + post
    idx = markup.rfind("<footer")
    if idx == -1:
        idx = markup.rfind("</body>")
    if idx == -1:
        return markup
    return markup[:idx] + block + "\n" + markup[idx:]


DATASETS = {
    "index.html": [
        ("Post-viral literature feeds (PubMed)", "Daily-updated JSON feeds of peer-reviewed studies per condition.",
         [f"{ORIGIN}/data/{k}.json" for k in ("long-covid", "me-cfs", "pacvs", "lyme", "gulf-war-illness", "pots", "mcas", "other-post-viral")]),
    ],
    "biomarker-atlas.html": [
        ("OSMF Biomarker Atlas data", "Machine-readable biomarker alterations per condition with direction, comparison group, LOINC codes and DOI citations.",
         [f"{ORIGIN}/data/biomarkers/{k}.json" for k in ("long-covid", "me-cfs", "pacvs", "lyme", "gulf-war-illness")] + [f"{ORIGIN}/biomarkers.schema.json"]),
    ],
    "clinical_trials.html": [
        ("Post-viral clinical trials registry snapshot", "ClinicalTrials.gov records mapped to Long COVID, ME/CFS and overlapping post-viral conditions, refreshed daily.",
         [f"{ORIGIN}/data/clinical_trials/clinical_trials_current.json"]),
    ],
    "agents.html": [
        ("Therapeutic agents under investigation for post-viral conditions", "Aggregated therapeutic agents with trial and literature links.",
         [f"{ORIGIN}/data/therapeutic_agents.json"]),
    ],
}


def dataset_block(name: str) -> str:
    graph = []
    for title, desc, urls in DATASETS[name]:
        graph.append({
            "@type": "Dataset",
            "name": title,
            "description": desc,
            "url": f"{ORIGIN}/{'' if name == 'index.html' else name}",
            "license": "https://creativecommons.org/licenses/by/4.0/",
            "isAccessibleForFree": True,
            "creator": {"@type": "Organization", "name": "Open Source Medicine Foundation", "url": "https://opensourcemed.info"},
            "keywords": ["long COVID", "ME/CFS", "PACVS", "post-viral syndrome", "biomarkers", "clinical trials"],
            "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": u} for u in urls],
        })
    data = {"@context": "https://schema.org", "@graph": graph}
    return f'{DS_START}\n<script type="application/ld+json">{json.dumps(data, ensure_ascii=False)}</script>\n{DS_END}'


def inject_in_head(markup: str, block: str, start: str, end: str) -> str:
    if start in markup and end in markup:
        pre, rest = markup.split(start, 1)
        _, post = rest.split(end, 1)
        return pre + block + post
    idx = markup.find("</head>")
    return markup if idx == -1 else markup[:idx] + block + "\n" + markup[idx:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    nav_fixed = cite_added = ds_added = 0
    for page in public_pages():
        original = page.read_text(encoding="utf-8")
        markup = original
        if is_redirect_or_noindex(markup):
            continue
        nav_match = NAV_RE.search(markup)
        if nav_match and "vitalscan" in nav_match.group(0):
            markup = NAV_RE.sub(OSMF_NAV, markup, count=1)
            markup = BANNER_RE.sub("", markup)
            nav_fixed += 1
        # Dangling relative links left over from the VitalScan mirror.
        for dangling, target in DANGLING.items():
            if dangling in markup:
                markup = markup.replace(dangling, target)
                nav_fixed += 1
        if "Cite this page" not in markup or CITE_START in markup:
            new = inject_before_footer(markup, cite_block(page, markup), CITE_START, CITE_END)
            if new != markup:
                cite_added += 1
            markup = new
        if page.name in DATASETS:
            new = inject_in_head(markup, dataset_block(page.name), DS_START, DS_END)
            if new != markup:
                ds_added += 1
            markup = new
        if markup != original and not args.check:
            page.write_text(markup, encoding="utf-8")
    print(f"nav fixed: {nav_fixed}; cite blocks written: {cite_added}; dataset blocks written: {ds_added}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
