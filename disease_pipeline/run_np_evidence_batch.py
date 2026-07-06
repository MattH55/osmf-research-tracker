#!/usr/bin/env python3
"""Attach trial/literature evidence to natural products and export drug-aligned schema."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.adapters.natural_products.np_evidence import enrich_natural_products_evidence
from disease_pipeline.adapters.natural_products.np_export import export_natural_products_page, natural_product_from_row
from disease_pipeline.adapters.natural_products.score_np import apply_safety, deduplicate_nps, load_safety_map
from disease_pipeline.http_util import default_session
from disease_pipeline.models import Alteration, AlterationType, DiseaseIdentifiers, EvidenceTier, NaturalProduct
from disease_pipeline.options import PipelineOptions
from disease_pipeline.output.generate_html import write_page

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"

log = logging.getLogger(__name__)


async def enrich_one(path: Path, opts: PipelineOptions, *, write_html: bool) -> dict | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    slug = data.get("slug", path.stem)
    name = data["condition"]["name"]
    ids = data.get("identifiers", {})
    identifiers = DiseaseIdentifiers(
        name=name,
        mondo_id=ids.get("mondo_id"),
        efo_id=ids.get("efo_id"),
        omim_id=ids.get("omim_id"),
        orpha_id=ids.get("orpha_id"),
        mesh_id=ids.get("mesh_id"),
        umls_cui=ids.get("umls_cui"),
    )

    raw_rows = data.get("natural_products", [])
    if not raw_rows:
        log.info("'%s': no natural products — skip", name)
        return None

    nps = [natural_product_from_row(row) for row in raw_rows]
    nps = deduplicate_nps(nps)
    nps = apply_safety(nps, load_safety_map())

    gmi_articles = (data.get("summary") or {}).get("gmi_articles") or []
    gmi_by_name: dict[str, list[dict]] = {}
    if gmi_articles:
        gmi_by_name[name.lower()] = gmi_articles

    async with default_session() as session:
        evidence_map = await enrich_natural_products_evidence(
            nps,
            identifiers,
            session,
            opts,
            gmi_articles_by_name=gmi_by_name or None,
        )

    np_rows, ev_export = export_natural_products_page(
        slug, nps, evidence_map, gmi_articles=gmi_articles or None,
    )
    data["natural_products"] = np_rows
    data["natural_product_evidence"] = ev_export

    summary = data.setdefault("summary", {})
    summary["natural_product_count"] = len(np_rows)
    summary["np_evidence_count"] = len(ev_export)
    summary["pipeline_phase"] = max(summary.get("pipeline_phase", 6), 7)
    sources = summary.setdefault("sources_queried", [])
    for src in ("PubMed NP Literature", "ClinicalTrials.gov NP"):
        if src not in sources:
            sources.append(src)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if write_html:
        write_page(data, HTML_DIR)

    log.info("'%s': %d NPs, %d with evidence -> %s", name, len(np_rows), len(ev_export), path.name)
    return {"name": name, "slug": slug, "count": len(np_rows), "evidence": len(ev_export)}


async def run_batch(opts: PipelineOptions, *, write_html: bool, only_slug: str | None) -> list[dict]:
    paths = sorted(DATA_DIR.glob("*.json"))
    if only_slug:
        paths = [p for p in paths if p.stem == only_slug]
    if not paths:
        log.error("No matching disease JSON files")
        return []

    sem = asyncio.Semaphore(opts.batch_concurrency)

    async def bounded(p: Path) -> dict | None:
        async with sem:
            try:
                return await asyncio.wait_for(
                    enrich_one(p, opts, write_html=write_html),
                    timeout=opts.disease_timeout_sec,
                )
            except asyncio.TimeoutError:
                log.error("Timeout: %s", p.name)
            except Exception as e:
                log.error("Failed %s: %s", p.name, e)
            return None

    results = await asyncio.gather(*[bounded(p) for p in paths])
    return [r for r in results if r]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export natural products with drug-aligned schema and trial/literature evidence"
    )
    parser.add_argument("--slug", help="Run a single disease slug only")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--max-evidence", type=int, default=20)
    parser.add_argument("--html", action="store_true", help="Regenerate HTML pages")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    opts = PipelineOptions(
        phase=7,
        skip_np_evidence=False,
        max_np_evidence=args.max_evidence,
        disease_timeout_sec=args.timeout,
        batch_concurrency=args.concurrency,
        use_cache=True,
    )
    results = asyncio.run(run_batch(opts, write_html=args.html, only_slug=args.slug))
    ev_total = sum(r["evidence"] for r in results)
    log.info("Done: %d diseases, %d NPs with evidence attached", len(results), ev_total)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())