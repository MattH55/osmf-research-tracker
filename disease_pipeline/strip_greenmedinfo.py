#!/usr/bin/env python3
"""Remove GreenMedInfo references from disease-intelligence JSON and regenerate HTML."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.output.generate_html import build_index_html, write_page

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"


def _is_gmi_label(label: object) -> bool:
    text = str(label or "")
    lowered = text.lower()
    return (
        lowered == "greenmedinfo"
        or text == "GreenMedInfo"
        or text.startswith("GreenMedInfo (")
    )


def _is_gmi_url(url: object) -> bool:
    return "greenmedinfo" in str(url or "").lower()


def _clean_publication(pub: dict) -> dict | None:
    url = str(pub.get("pubmed_url") or pub.get("url") or "")
    if _is_gmi_url(url) and not pub.get("pubmed_url") and not pub.get("pmid"):
        return None
    if _is_gmi_label(pub.get("source")):
        pub = dict(pub)
        pub["source"] = pub.get("study_type") or pub.get("publication_type_label") or "Literature"
    if _is_gmi_url(pub.get("url")) and pub.get("pubmed_url"):
        pub = dict(pub)
        pub["url"] = pub["pubmed_url"]
    return pub


def _clean_evidence(ev: dict | None) -> None:
    if not isinstance(ev, dict):
        return
    if isinstance(ev.get("search_links"), dict):
        ev["search_links"] = {
            k: v for k, v in ev["search_links"].items() if not _is_gmi_label(k)
        }
    literature = ev.get("literature")
    if isinstance(literature, list):
        cleaned: list[dict] = []
        for lit in literature:
            if not isinstance(lit, dict):
                continue
            row = _clean_publication(lit)
            if row and not _is_gmi_url(row.get("url")):
                if _is_gmi_label(row.get("publication_type_label")):
                    row = dict(row)
                    row.pop("publication_type_label", None)
                cleaned.append(row)
        ev["literature"] = cleaned


def _clean_item(item: dict) -> None:
    if isinstance(item.get("sources"), list):
        item["sources"] = [s for s in item["sources"] if not _is_gmi_label(s)]
    if isinstance(item.get("source_links"), dict):
        item["source_links"] = {
            k: v for k, v in item["source_links"].items() if not _is_gmi_label(k)
        }
    if isinstance(item.get("external_links"), list):
        item["external_links"] = [
            link
            for link in item["external_links"]
            if not _is_gmi_label(link.get("label")) and not _is_gmi_url(link.get("url"))
        ]
    if isinstance(item.get("supporting_publications"), list):
        item["supporting_publications"] = [
            row for row in (_clean_publication(pub) for pub in item["supporting_publications"])
            if row and not _is_gmi_url(row.get("url"))
        ]
    _clean_evidence(item.get("clinical_evidence"))
    if isinstance(item.get("key_findings"), str):
        item["key_findings"] = re.sub(r"\d+\s+GMI studies?;?\s*", "", item["key_findings"])


def _clean_data(data: dict) -> None:
    summary = data.get("summary") or {}
    if isinstance(summary.get("sources_queried"), list):
        summary["sources_queried"] = [
            s for s in summary["sources_queried"] if not _is_gmi_label(s)
        ]
    if isinstance(summary.get("np_lookup_links"), dict):
        summary["np_lookup_links"] = {
            k: v for k, v in summary["np_lookup_links"].items() if not _is_gmi_label(k)
        }
    summary.pop("gmi_articles", None)
    if isinstance(summary.get("np_source_counts"), dict):
        summary["np_source_counts"].pop("gmi", None)
    data["summary"] = summary

    for key in ("natural_products", "alterations"):
        for item in data.get(key, []) or []:
            _clean_item(item)

    ther = data.get("therapeutics") or {}
    for section in ("direct", "via_biomarker", "merged", "natural"):
        for item in ther.get(section, []) or []:
            _clean_item(item)

    for ev in data.get("natural_product_evidence", {}).values():
        _clean_evidence(ev)


def main() -> int:
    pages: list[dict] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        _clean_data(data)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        write_page(data, HTML_DIR)
        pages.append(data)

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    (HTML_DIR / "index.html").write_text(build_index_html(pages), encoding="utf-8")
    print(f"Cleaned and regenerated {len(pages)} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())