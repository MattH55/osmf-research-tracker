#!/usr/bin/env python3
"""Render a biomarkers.schema.json atlas file into a root-level
{slug}-biomarkers.html page, using the same tracker.css / js/biomarker-*.js
assets and nav/footer chrome as the 5 existing atlas pages (PACVS, ME/CFS,
Long COVID, Lyme, Gulf War Illness).

Deliberately does NOT hand-author a "Category Deep Dives" or narrative
"Literature Overview" section the way the 5 original pages do — those were
manually written per-condition and aren't something this pipeline curates.
The References section IS generated, from the unique citations already
present in the exported marker data, so it stays honest about what was
actually sourced.

JSON-LD is intentionally omitted here; run scripts/build-atlases.js after
generating the page (with the slug added to its HTML_MAP) to inject it,
exactly as done for the 5 existing pages.

Usage (from research-tracker/):
    python -m biomarker_pipeline.generate_atlas_html --slug asthma
"""
import argparse
import json
import logging
from pathlib import Path

from disease_pipeline.adapters.remission.db100 import db100_row_for_page
from disease_pipeline.adapters.remission.hero import HERO_REMISSION_CSS, hero_remission_html
from disease_pipeline.site_nav import GOOGLE_ANALYTICS_SNIPPET

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "biomarkers"
OUT_DIR  = Path(__file__).parent.parent


def _escape(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _references_html(markers: list[dict]) -> str:
    seen = {}
    for m in markers:
        ref = m.get("reference", {})
        doi = ref.get("doi")
        if doi and doi not in seen:
            seen[doi] = ref.get("citation", "")
    cards = []
    for doi, citation in seen.items():
        cards.append(
            f'<div class="ref-card"><div class="ref-type">Peer-Reviewed Literature</div>'
            f'<h4>{_escape(citation)}</h4>'
            f'<a href="https://doi.org/{_escape(doi)}" target="_blank" rel="noopener">DOI: {_escape(doi)} →</a></div>'
        )
    return "\n".join(cards) if cards else '<p>No references yet — curation in progress.</p>'


def render_atlas_html(atlas: dict) -> str:
    slug = atlas["slug"]
    condition_name = atlas["condition"]["name"]
    page = atlas["page"]
    markers = atlas["markers"]
    n_markers = len(markers)
    n_categories = len(atlas.get("categories", {}))

    title = _escape(page["title"])
    description = _escape(page["description"])
    keywords = _escape(", ".join(page.get("keywords", [])))
    canonical = page["canonical"]
    hero = _escape(page["hero"])
    rem_row = db100_row_for_page(slug)
    hero_remission = hero_remission_html(
        rem_row,
        detail_anchor=f"chronic-disease-interventions/{slug}.html#remission",
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{GOOGLE_ANALYTICS_SNIPPET}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <meta name="keywords" content="{keywords}">
  <link rel="canonical" href="{canonical}">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Open Source Medicine Foundation">
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{description}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:locale" content="en_US">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title}">
  <meta name="twitter:description" content="{description}">
  <link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
  <link rel="icon" href="favicon.png" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="tracker.css">
  <link rel="stylesheet" href="css/biomarker-atlas-tracker.css">
  <style>{HERO_REMISSION_CSS}</style>
</head>
<body class="biomarker-page" data-atlas="{slug}">
<nav>
  <div class="nav-container">
    <a href="https://opensourcemed.info" class="nav-brand">
      Open Source <span>Medicine</span>
      <span class="nav-brand-sub">Research Tracker</span>
    </a>
    <ul class="nav-links">
      <li><a href="index.html">All Conditions</a></li>
      <li><a href="biomarker-atlas.html" class="nav-active">Biomarkers</a></li>
      <li><a href="clinical_trials.html">Clinical Trials</a></li>
      <li><a href="agents.html">Agents</a></li>
      <li><a href="chronic-disease-interventions/index.html">Chronic Diseases</a></li>
      <li><a href="https://www.paypal.com/ncp/payment/A2MK3BCVE4X7C" class="nav-support">Support Our Work</a></li>
    </ul>
  </div>
</nav>

<section class="page-hero">
  <div class="hero-eyebrow">Peer-Reviewed Literature Synthesis</div>
  <h1>{_escape(condition_name)} Biomarker Atlas</h1>
  <p>{hero}</p>
  {hero_remission}
</section>

<main class="main-section">
  <div class="section-inner">
    <div class="tracker-crosslink">
      <a href="chronic-disease-interventions/{slug}.html">← {_escape(condition_name)} Gene Targets &amp; Interventions</a>
      <a href="biomarker-atlas.html">All Biomarker Atlases</a>
      <a href="index.html">Research Tracker Home</a>
    </div>
  </div>

  <section class="overview-section" id="biomarker-database">
    <div class="container">
      <div class="section-header">
        <h2>Literature <span class="highlight">Overview</span></h2>
        <p>Biomarkers below are included only where peer-reviewed literature explicitly reports the marker's direction in {_escape(condition_name)} patients relative to a named comparison population — not inferred.</p>
      </div>
      <div class="stats-grid">
        <div class="stat-card"><div class="number">{n_markers}</div><div class="label">Curated markers</div></div>
        <div class="stat-card"><div class="number">{n_categories}</div><div class="label">Categories</div></div>
      </div>
    </div>
  </section>

  <article>
    <section>
      <div class="container">
        <div class="section-header"><h2>Searchable <span class="highlight">Alterations Database</span></h2><p>Comparison populations are quoted as reported in the source literature (e.g. healthy controls, disease-matched patients).</p></div>
        <div class="controls-bar">
          <div class="search-box"><input type="search" id="searchInput" placeholder="Search markers, tests, or symptoms..." aria-label="Search biomarkers"></div>
          <div class="filter-group" id="categoryFilters"></div>
        </div>
        <div class="results-count" id="resultsCount" aria-live="polite"></div>
        <div class="table-wrapper">
          <table><thead><tr><th>Marker / Test</th><th>Direction</th><th>Category</th><th>vs. Comparison</th><th>Clinical Context</th><th>Key Reference</th></tr></thead><tbody id="tableBody"></tbody></table>
        </div>
      </div>
    </section>
  </article>

  <section class="refs-section">
    <div class="container">
      <div class="section-header"><h2>Key <span class="highlight">References</span></h2></div>
      <div class="refs-grid">
        {_references_html(markers)}
      </div>
      <div class="disclaimer"><strong>Disclaimer:</strong> Educational synthesis of peer-reviewed literature only — not medical advice. Markers are drawn from published disease-vs-comparison-population studies; inclusion here does not imply diagnostic or clinical validation. Consult a qualified healthcare professional for interpretation.</div>
    </div>
  </section>
</main>

<footer>
  <div class="footer-brand">Open Source Medicine Foundation</div>
  <div class="footer-links">
    <a href="https://opensourcemed.info">opensourcemed.info</a>
    <a href="index.html">Research Tracker</a>
    <a href="biomarker-atlas.html">Biomarker Atlases</a>
    <a href="clinical_trials.html">Clinical Trials</a>
    <a href="agents.html">Therapeutic Agents</a>
    <a href="chronic-disease-interventions/{slug}.html">{_escape(condition_name)} Interventions</a>
  </div>
  <div class="footer-note">Educational synthesis of peer-reviewed research. Not medical advice.</div>
</footer>
<script src="js/biomarker-data-loader.js" defer></script>
<script src="js/biomarker-atlas.js" defer></script>
</body>
</html>
"""


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Render an atlas JSON into a {slug}-biomarkers.html page")
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    atlas = json.loads((DATA_DIR / f"{args.slug}.json").read_text(encoding="utf-8"))
    html = render_atlas_html(atlas)
    out_path = OUT_DIR / f"{args.slug}-biomarkers.html"
    out_path.write_text(html, encoding="utf-8")
    log.info("Wrote %s (%d markers)", out_path, len(atlas["markers"]))


if __name__ == "__main__":
    main()
