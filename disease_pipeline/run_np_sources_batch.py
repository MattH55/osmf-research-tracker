#!/usr/bin/env python3
"""Run GreenMedInfo + Examine.com lookups across all disease-intelligence pages."""
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

from disease_pipeline.adapters.natural_products.runner import build_natural_products
from disease_pipeline.adapters.natural_products.score_np import apply_safety, deduplicate_nps, load_safety_map
from disease_pipeline.http_util import default_session
from disease_pipeline.models import Alteration, AlterationType, DiseaseIdentifiers, EvidenceTier, NaturalProduct
from disease_pipeline.options import PipelineOptions
from disease_pipeline.output.generate_html import write_page

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"

log = logging.getLogger(__name__)


def _alteration_from_web(row: dict) -> Alteration:
    t = row.get("type", "C")
    return Alteration(
        canonical_id=row.get("canonical_id", row.get("id", "")),
        name=row["name"],
        alteration_type=AlterationType(t),
        subtype=row.get("subtype", "gene" if t == "A" else "pathology"),
        direction=row.get("direction"),
        frequency_label=row.get("frequency_label"),
        frequency_pct=row.get("frequency_pct"),
        sources=row.get("sources", []),
        source_ids=row.get("source_ids", {}),
        evidence_tier=EvidenceTier(row.get("evidence_tier", "C")),
        pubmed_count=row.get("pubmed_count", 0),
        definition=row.get("definition"),
    )


async def enrich_one(path: Path, opts: PipelineOptions, *, write_html: bool) -> dict | None:
    data = json.loads(path.read_text(encoding="utf-8"))
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
    alterations = [_alteration_from_web(a) for a in data.get("alterations", [])]
    existing = [NaturalProduct.model_validate(row) for row in data.get("natural_products", [])]
    extra_meta: dict = {}

    async with default_session() as session:
        ref_nps = await build_natural_products(
            identifiers,
            alterations,
            session,
            opts,
            disease_slug=data.get("slug", ""),
            extra_meta=extra_meta,
        )

    nps = deduplicate_nps(existing + ref_nps)
    nps = apply_safety(nps, load_safety_map())
    data["natural_products"] = [np.model_dump(mode="json") for np in nps]
    summary = data.setdefault("summary", {})
    summary["natural_product_count"] = len(nps)
    summary["pipeline_phase"] = max(summary.get("pipeline_phase", 6), 7)
    if extra_meta.get("np_lookup_links"):
        summary["np_lookup_links"] = extra_meta["np_lookup_links"]
    sources = summary.setdefault("sources_queried", [])
    for src in ("GreenMedInfo", "Examine.com"):
        if src not in sources:
            sources.append(src)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if write_html:
        write_page(data, HTML_DIR)

    log.info("'%s': %d natural products (GMI/Examine) -> %s", name, len(nps), path.name)
    return {"name": name, "slug": data["slug"], "count": len(nps)}


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
        description="Enrich disease pages with GreenMedInfo and Examine.com natural product lookups"
    )
    parser.add_argument("--slug", help="Run a single disease slug only")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--html", action="store_true", help="Regenerate HTML pages")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    opts = PipelineOptions(
        phase=7,
        skip_llm_extract=True,
        skip_pubchem_enrich=True,
        skip_clinical_np=True,
        skip_mechanistic_np=True,
        skip_greenmedinfo=False,
        skip_examine=False,
        disease_timeout_sec=args.timeout,
        batch_concurrency=args.concurrency,
        use_cache=True,
    )
    results = asyncio.run(run_batch(opts, write_html=args.html, only_slug=args.slug))
    total_np = sum(r["count"] for r in results)
    log.info("Done: %d diseases, %d total NPs", len(results), total_np)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())