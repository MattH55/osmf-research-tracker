#!/usr/bin/env python3
"""Run natural product discovery for all published disease-intelligence pages."""
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
from disease_pipeline.adapters.natural_products.np_export import export_natural_products_page
from disease_pipeline.adapters.natural_products.runner import build_natural_products
from disease_pipeline.http_util import default_session
from disease_pipeline.models import Alteration, AlterationType, DiseaseIdentifiers, EvidenceTier
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

    extra_meta: dict = {}
    slug = data.get("slug", path.stem)
    async with default_session() as session:
        nps = await build_natural_products(
            identifiers,
            alterations,
            session,
            opts,
            disease_slug=slug,
            extra_meta=extra_meta,
        )
        evidence_map = {}
        if not opts.skip_np_evidence:
            gmi_by_name = None
            if extra_meta.get("gmi_articles"):
                gmi_by_name = {name.lower(): extra_meta["gmi_articles"]}
            evidence_map = await enrich_natural_products_evidence(
                nps,
                identifiers,
                session,
                opts,
                gmi_articles_by_name=gmi_by_name,
            )

    np_rows, ev_export = export_natural_products_page(
        slug, nps, evidence_map, gmi_articles=extra_meta.get("gmi_articles"),
    )
    data["natural_products"] = np_rows
    data["natural_product_evidence"] = ev_export
    summary = data.setdefault("summary", {})
    summary["natural_product_count"] = len(nps)
    summary["np_evidence_count"] = len(ev_export)
    if extra_meta.get("gmi_articles"):
        summary["gmi_articles"] = extra_meta["gmi_articles"]
    summary["pipeline_phase"] = max(summary.get("pipeline_phase", 6), 7)
    if extra_meta.get("np_lookup_links"):
        summary["np_lookup_links"] = extra_meta["np_lookup_links"]
    sources = summary.setdefault("sources_queried", [])
    for src in ("PubMed NP", "ClinicalTrials.gov NP", "ChEMBL NP"):
        if src not in sources:
            sources.append(src)
    if not opts.skip_greenmedinfo and "GreenMedInfo" not in sources:
        sources.append("GreenMedInfo")
    if not opts.skip_examine and "Examine.com" not in sources:
        sources.append("Examine.com")

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if write_html:
        write_page(data, HTML_DIR)

    log.info("'%s': %d natural products -> %s", name, len(nps), path.name)
    return {"name": name, "slug": data["slug"], "count": len(nps)}


async def run_batch(opts: PipelineOptions, *, write_html: bool) -> list[dict]:
    paths = sorted(DATA_DIR.glob("*.json"))
    if not paths:
        log.error("No disease JSON files in %s", DATA_DIR)
        return []

    sem = asyncio.Semaphore(opts.batch_concurrency)

    async def bounded(p: Path) -> dict | None:
        async with sem:
            try:
                return await asyncio.wait_for(
                    enrich_one(p, opts, write_html=write_html), timeout=opts.disease_timeout_sec
                )
            except asyncio.TimeoutError:
                log.error("Timeout: %s", p.name)
            except Exception as e:
                log.error("Failed %s: %s", p.name, e)
            return None

    results = await asyncio.gather(*[bounded(p) for p in paths])
    return [r for r in results if r]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run NP discovery on all disease-intelligence JSON files")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--max-pubmed-np", type=int, default=50)
    parser.add_argument("--skip-llm", action="store_true", help="Skip Claude abstract extraction")
    parser.add_argument("--skip-pubchem-enrich", action="store_true", help="Skip PubChem bioassay enrichment")
    parser.add_argument("--skip-greenmedinfo", action="store_true", help="Skip GreenMedInfo substance lookup")
    parser.add_argument("--skip-examine", action="store_true", help="Skip Examine.com supplement lookup")
    parser.add_argument("--skip-np-evidence", action="store_true", help="Skip per-NP trial/literature evidence")
    parser.add_argument("--max-np-evidence", type=int, default=20)
    parser.add_argument("--html", action="store_true", help="Regenerate HTML pages")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    opts = PipelineOptions(
        phase=7,
        skip_llm_extract=args.skip_llm,
        skip_pubchem_enrich=args.skip_pubchem_enrich,
        skip_greenmedinfo=args.skip_greenmedinfo,
        skip_examine=args.skip_examine,
        skip_np_evidence=args.skip_np_evidence,
        max_np_evidence=args.max_np_evidence,
        max_pubmed_np_results=args.max_pubmed_np,
        disease_timeout_sec=args.timeout,
        batch_concurrency=args.concurrency,
        use_cache=True,
    )
    results = asyncio.run(run_batch(opts, write_html=args.html))
    total_np = sum(r["count"] for r in results)
    log.info("Done: %d/%d diseases, %d total NPs", len(results), len(list(DATA_DIR.glob('*.json'))), total_np)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())