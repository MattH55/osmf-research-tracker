#!/usr/bin/env python3
"""Run full 20-database NP repurposing pipeline across disease-intelligence pages."""
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

from disease_pipeline.adapters.np_databases.browser import BrowserManager
from disease_pipeline.adapters.np_databases.local_data import get_local_data
from disease_pipeline.adapters.np_databases.runner import build_np_repurposing_leads
from disease_pipeline.adapters.natural_products.np_evidence import enrich_natural_products_evidence
from disease_pipeline.adapters.natural_products.np_export import export_natural_products_page, natural_product_from_row
from disease_pipeline.adapters.natural_products.score_np import apply_safety, deduplicate_nps, load_safety_map
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


async def enrich_one(path: Path, opts: PipelineOptions, local_data: dict, *, write_html: bool) -> dict | None:
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
    type_a = [a for a in alterations if a.alteration_type == AlterationType.A]
    existing = [natural_product_from_row(row) for row in data.get("natural_products", [])]
    extra_meta: dict = {}
    slug = data.get("slug", path.stem)

    async with default_session() as session:
        async with BrowserManager(use_playwright=opts.use_playwright, use_cache=opts.use_cache) as bm:
            ref_nps = await build_np_repurposing_leads(
                identifiers,
                type_a,
                session,
                bm,
                local_data,
                disease_slug=slug,
                options=opts,
                extra_meta=extra_meta,
            )
        nps = deduplicate_nps(existing + ref_nps)
        nps = apply_safety(nps, load_safety_map())

        gmi_by_name = None
        if extra_meta.get("gmi_articles"):
            gmi_by_name = {name.lower(): extra_meta["gmi_articles"]}
        evidence_map = {}
        if not opts.skip_np_evidence:
            evidence_map = await enrich_natural_products_evidence(
                nps, identifiers, session, opts, gmi_articles_by_name=gmi_by_name,
            )

    np_rows, ev_export = export_natural_products_page(slug, nps, evidence_map)
    data["natural_products"] = np_rows
    data["natural_product_evidence"] = ev_export
    summary = data.setdefault("summary", {})
    summary["natural_product_count"] = len(nps)
    summary["np_evidence_count"] = len(ev_export)
    summary["pipeline_phase"] = max(summary.get("pipeline_phase", 7), 8)
    if extra_meta.get("np_lookup_links"):
        summary["np_lookup_links"] = extra_meta["np_lookup_links"]
    if extra_meta.get("gmi_articles"):
        summary["gmi_articles"] = extra_meta["gmi_articles"]
    if extra_meta.get("np_source_counts"):
        summary["np_source_counts"] = extra_meta["np_source_counts"]
    sources = summary.setdefault("sources_queried", [])
    for src in (
        "GreenMedInfo", "Examine.com", "NCCIH", "ClinicalTrials.gov", "PubMed",
        "TCMSP", "BATMAN-TCM", "IMPPAT", "ETCM", "SymMap",
        "LOTUS", "COCONUT", "NPASS", "ChEMBL-NP", "PubChem BioAssay",
        "Dr. Duke's", "KNApSAcK", "DSLD", "Phenol-Explorer", "FooDB",
    ):
        if src not in sources:
            sources.append(src)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if write_html:
        write_page(data, HTML_DIR)

    log.info("'%s': %d NPs (20-DB pipeline) -> %s", name, len(nps), path.name)
    return {"name": name, "slug": slug, "count": len(nps)}


async def run_batch(opts: PipelineOptions, *, write_html: bool, only_slug: str | None) -> list[dict]:
    paths = sorted(DATA_DIR.glob("*.json"))
    if only_slug:
        paths = [p for p in paths if p.stem == only_slug]
    if not paths:
        log.error("No matching disease JSON files")
        return []

    local_data = get_local_data()
    sem = asyncio.Semaphore(opts.batch_concurrency)

    async def bounded(p: Path) -> dict | None:
        async with sem:
            try:
                return await asyncio.wait_for(
                    enrich_one(p, opts, local_data, write_html=write_html),
                    timeout=opts.disease_timeout_sec,
                )
            except asyncio.TimeoutError:
                log.error("Timeout: %s", p.name)
            except Exception as e:
                log.error("Failed %s: %s", p.name, e, exc_info=True)
            return None

    results = await asyncio.gather(*[bounded(p) for p in paths])
    return [r for r in results if r]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Full 20-database NP repurposing pipeline")
    parser.add_argument("--slug", help="Run a single disease slug only")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--playwright", action="store_true", help="Use Playwright for GMI/Examine")
    parser.add_argument("--skip-evidence", action="store_true")
    parser.add_argument("--skip-synthesis", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    opts = PipelineOptions(
        phase=8,
        skip_llm_extract=True,
        skip_pubchem_enrich=True,
        skip_np_evidence=args.skip_evidence,
        skip_np_synthesis=args.skip_synthesis,
        use_playwright=args.playwright,
        max_np_evidence=15,
        disease_timeout_sec=args.timeout,
        batch_concurrency=args.concurrency,
        use_cache=True,
    )
    results = asyncio.run(run_batch(opts, write_html=args.html, only_slug=args.slug))
    total = sum(r["count"] for r in results)
    log.info("Done: %d diseases, %d total NPs", len(results), total)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())