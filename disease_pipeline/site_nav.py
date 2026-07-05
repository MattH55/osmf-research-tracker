"""Shared site navigation snippets for static HTML pages."""
from __future__ import annotations

import html
import json
from pathlib import Path

SITE_LINKS_PATH = Path(__file__).parent / "seeds" / "site_links.json"
FAVICON_URL = "https://opensourcemed.info/favicon.png"

SITE_NAV_LINKS = [
    ("../index.html", "Research Tracker"),
    ("index.html", "Disease Intelligence", "di"),
    ("../biomarker-atlas.html", "Biomarkers"),
    ("../chronic-disease-interventions/index.html", "Interventions"),
    ("../clinical_trials.html", "Clinical Trials"),
    ("../agents.html", "Agents"),
]

ROOT_NAV_LINKS = [
    ("index.html", "Research Tracker"),
    ("disease-intelligence/index.html", "Disease Intelligence"),
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


def render_nav(*, depth: str = "di", active: str | None = None) -> str:
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
      <a href="{brand_href}" class="nav-brand">Open Source Medicine <span>Foundation</span></a>
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