"""Shared site navigation snippets for static HTML pages."""
from __future__ import annotations

import html
import json
from pathlib import Path

SITE_LINKS_PATH = Path(__file__).parent / "seeds" / "site_links.json"
FAVICON_URL = "https://opensourcemed.info/favicon.png"
REPURPOS_BRAND = "RepurpOS"
REPURPOS_TAGLINE = "by OpenSourceMedicine"
REPURPOS_FULL = f"{REPURPOS_BRAND} {REPURPOS_TAGLINE}"
GOOGLE_ANALYTICS_ID = "G-XRCGK1QTB5"
GOOGLE_ANALYTICS_SNIPPET = f"""  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GOOGLE_ANALYTICS_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());

    gtag('config', '{GOOGLE_ANALYTICS_ID}');
  </script>"""

SITE_NAV_LINKS = [
    ("../index.html", "Research Tracker"),
    ("index.html", REPURPOS_BRAND, "di"),
    ("../biomarker-atlas.html", "Biomarkers"),
    ("../chronic-disease-interventions/index.html", "Interventions"),
    ("../clinical_trials.html", "Clinical Trials"),
    ("../agents.html", "Agents"),
]

ROOT_NAV_LINKS = [
    ("index.html", "Research Tracker"),
    ("disease-intelligence/index.html", REPURPOS_BRAND),
    ("biomarker-atlas.html", "Biomarkers"),
    ("chronic-disease-interventions/index.html", "Interventions"),
    ("clinical_trials.html", "Clinical Trials"),
    ("agents.html", "Agents"),
]


def load_site_links() -> dict[str, dict]:
    if SITE_LINKS_PATH.exists():
        return json.loads(SITE_LINKS_PATH.read_text(encoding="utf-8"))
    return {}


def _esc(text: str) -> str:
    return html.escape(text)


def render_nav(
    *,
    depth: str = "di",
    active: str | None = None,
    brand: str = "Open Source Medicine",
    brand_span: str = "Foundation",
) -> str:
    """depth: 'root' for site root pages, 'di' for disease-intelligence pages."""
    links = ROOT_NAV_LINKS if depth == "root" else SITE_NAV_LINKS
    items = []
    for entry in links:
        href, label = entry[0], entry[1]
        key = entry[2] if len(entry) > 2 else label.lower().replace(" ", "-")
        cls = ' class="active"' if active and key == active else ""
        items.append(f'<li><a href="{_esc(href)}"{cls}>{_esc(label)}</a></li>')
    brand_href = "../index.html" if depth == "di" else "index.html"
    return f"""
  <nav>
    <div class="nav-container">
      <a href="{brand_href}" class="nav-brand">{_esc(brand)} <span>{_esc(brand_span)}</span></a>
      <ul class="nav-links">{''.join(items)}</ul>
    </div>
  </nav>"""


def related_links(slug: str) -> str:
    links = load_site_links().get(slug, {})
    bits = []
    if links.get("biomarker_html"):
        bits.append(f'<a href="{_esc(links["biomarker_html"])}">Biomarker atlas</a>')
    if links.get("interventions_html"):
        bits.append(f'<a href="{_esc(links["interventions_html"])}">Intervention atlas</a>')
    if not bits:
        return ""
    return f'<p class="related-links">Related: {" · ".join(bits)}</p>'