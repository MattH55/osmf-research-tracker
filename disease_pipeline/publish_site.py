#!/usr/bin/env python3
"""Rebuild all static site pages from data/disease-intelligence JSON."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.output.generate_html import build_index_html, write_page

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"
SITEMAP_PATH = _ROOT / "sitemap.xml"
SITE_BASE = "https://research.opensourcemed.info"

log = logging.getLogger(__name__)


def _append_sitemap_urls(root: Element, paths: list[str], *, priority: str, changefreq: str) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for path in paths:
        url = SubElement(root, "url")
        SubElement(url, "loc").text = f"{SITE_BASE}/{path}"
        SubElement(url, "lastmod").text = today
        SubElement(url, "changefreq").text = changefreq
        SubElement(url, "priority").text = priority


def rebuild_sitemap(pages: list[dict]) -> None:
    """Append disease-intelligence URLs to sitemap (preserve existing entries)."""
    if not SITEMAP_PATH.exists():
        log.warning("No sitemap.xml found — skipping")
        return

    text = SITEMAP_PATH.read_text(encoding="utf-8")
    if "disease-intelligence/index.html" in text:
        # Strip old DI entries and rebuild block
        lines = text.splitlines()
        out = [ln for ln in lines if "disease-intelligence/" not in ln and "</urlset>" not in ln]
        text = "\n".join(out) + "\n"
    else:
        text = text.replace("</urlset>", "")

    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    # Re-parse would lose existing; instead append new block manually
    di_paths = ["disease-intelligence/index.html"]
    di_paths.extend(f"disease-intelligence/{p['slug']}.html" for p in pages)

    block = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for i, path in enumerate(di_paths):
        pri = "0.88" if i == 0 else "0.82"
        block.append(f"""  <url>
    <loc>{SITE_BASE}/{path}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>{pri}</priority>
  </url>""")

    if "</urlset>" in SITEMAP_PATH.read_text(encoding="utf-8"):
        new_text = SITEMAP_PATH.read_text(encoding="utf-8").replace(
            "</urlset>", "\n".join(block) + "\n</urlset>"
        )
        # Deduplicate if run twice
        while new_text.count("disease-intelligence/index.html") > 1:
            idx = new_text.find("disease-intelligence/index.html")
            start = new_text.rfind("<url>", 0, idx)
            end = new_text.find("</url>", idx) + len("</url>")
            new_text = new_text[:start] + new_text[end:]
        SITEMAP_PATH.write_text(new_text, encoding="utf-8")
        log.info("Updated sitemap with %d disease-intelligence URLs", len(di_paths))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    paths = sorted(DATA_DIR.glob("*.json"))
    if not paths:
        log.error("No JSON in %s", DATA_DIR)
        return 1

    pages: list[dict] = []
    for p in paths:
        data = json.loads(p.read_text(encoding="utf-8"))
        write_page(data, HTML_DIR)
        pages.append(data)
        log.info("HTML %s", p.stem)

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    index_path = HTML_DIR / "index.html"
    index_path.write_text(build_index_html(pages), encoding="utf-8")
    log.info("Wrote %s (%d diseases)", index_path, len(pages))

    rebuild_sitemap(pages)
    log.info("Site publish complete — upload the repo root folder to deploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())