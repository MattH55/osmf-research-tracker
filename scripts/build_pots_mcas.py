#!/usr/bin/env python3
"""Build RepurpOS disease-intelligence pages for POTS and MCAS."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.options import options_for_phase
from disease_pipeline.output.generate_html import build_index_html, write_page
from disease_pipeline.output.web_export import to_web_json
from disease_pipeline.pipeline import build_disease_page
from disease_pipeline.published_conditions import is_publishable

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"

TARGETS = [
    {
        "query": "Postural Orthostatic Tachycardia Syndrome",
        "slug": "pots",
        "short": "POTS (Postural Orthostatic Tachycardia Syndrome)",
        "full": "Postural Orthostatic Tachycardia Syndrome",
    },
    {
        "query": "Mast Cell Activation Syndrome",
        "slug": "mcas",
        "short": "MCAS (Mast Cell Activation Syndrome)",
        "full": "Mast Cell Activation Syndrome",
    },
]


async def build_one(target: dict, phase: int, timeout: float) -> dict | None:
    opts = options_for_phase(
        phase,
        use_cache=True,
        skip_hmdb=True,
        disease_timeout_sec=timeout,
        max_evidence_drugs=25,
    )
    page = await build_disease_page(target["query"], opts)
    web = to_web_json(page, cap_display=False, slug=target["slug"])
    web["condition"]["shortName"] = target["short"]
    web["condition"]["name"] = target["full"]
    web["page"]["title"] = f"{target['short']} — RepurpOS | OpenSourceMedicine"
    web["page"]["breadcrumbName"] = f"{target['short']} Intelligence"
    web["page"]["canonical"] = (
        f"https://research.opensourcemed.info/disease-intelligence/{target['slug']}.html"
    )
    web["page"]["hero"] = (
        f"Disease intelligence for {target['full']}: "
        f"{web['summary']['alteration_count']} alterations and "
        f"{web['summary']['therapeutic_counts']['merged']} ranked therapeutics "
        f"from curated public databases."
    )
    if web["summary"]["alteration_count"] <= 0:
        return None
    out = DATA_DIR / f"{target['slug']}.json"
    out.write_text(json.dumps(web, indent=2, ensure_ascii=False), encoding="utf-8")
    write_page(web, HTML_DIR)
    return web


async def main(phase: int = 6, timeout: float = 180.0) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    built = []
    for target in TARGETS:
        try:
            web = await build_one(target, phase, timeout)
            if web:
                built.append(web)
                logging.info(
                    "Built %s (%d alterations, %d therapeutics)",
                    target["slug"],
                    web["summary"]["alteration_count"],
                    web["summary"]["therapeutic_counts"]["merged"],
                )
            else:
                logging.error("No biomarkers for %s", target["slug"])
        except Exception as exc:
            logging.error("Failed %s: %s", target["slug"], exc)

    if not built:
        return 1

    pages = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if is_publishable(data):
            pages.append(data)
    index_html = build_index_html(pages)
    (HTML_DIR / "index.html").write_text(index_html, encoding="utf-8")
    logging.info("Rebuilt index with %d publishable conditions", len(pages))
    return 0


if __name__ == "__main__":
    phase = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    raise SystemExit(asyncio.run(main(phase=phase)))