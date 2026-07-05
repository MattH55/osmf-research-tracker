"""Disease Intelligence Pipeline orchestrator."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from .adapters import clinical, clinical_evidence, drugs_direct, drugs_via_target, molecular, natural_agents, normalize, pubmed, score
from .adapters.normalize import seed_key
from .cache import cache_get, cache_set
from .http_util import default_session
from .models import AlterationType, DiseasePageData
from .options import PipelineOptions, options_for_phase
from .output.assembler import assemble_output

log = logging.getLogger(__name__)


async def build_disease_page(
    disease_name: str,
    options: PipelineOptions | None = None,
) -> DiseasePageData:
    opts = options or PipelineOptions(phase=1)
    cache_key = f"{seed_key(disease_name)}:p{opts.phase}"

    if opts.use_cache:
        cached = cache_get("pipeline", cache_key)
        if cached is not None:
            log.info("Cache hit for '%s'", disease_name)
            return DiseasePageData(**cached)

    t0 = time.monotonic()

    async def _run() -> DiseasePageData:
        async with default_session() as session:
            identifiers = await normalize.normalize_disease(disease_name, session)
            opts.note_source("Seeds" if identifiers.efo_id else "Open Targets")

            async def _empty() -> list:
                return []

            mol_task = molecular.get_all(identifiers, session, opts)
            clin_task = clinical.get_all(identifiers, session, opts) if opts.includes(2) else _empty()
            mol_alts, clin_alts = await asyncio.gather(mol_task, clin_task)
            alterations = score.score_alterations(mol_alts + clin_alts)

            type_a = [a for a in alterations if a.alteration_type == AlterationType.A]
            gene_symbols = [a.name for a in type_a]

            direct_task = drugs_direct.get_all(identifiers, session, opts)
            via_task = (
                drugs_via_target.get_all_for_targets(gene_symbols, alterations, identifiers, session, opts)
                if opts.includes(3)
                else _empty()
            )
            direct_drugs, via_drugs = await asyncio.gather(direct_task, via_task)

            natural_drugs, natural_meta = natural_agents.get_for_disease(disease_name)
            if natural_drugs:
                opts.note_source("OSMF Chronic Disease Review")

            merged_direct, merged_via, merged_natural, merged_all = score.score_therapeutics(
                direct_drugs, via_drugs, natural_drugs
            )

            if opts.includes(4) and not opts.skip_pubmed:
                alterations = await pubmed.validate_batch(alterations, identifiers, session, opts)
                merged_all = await pubmed.validate_batch(merged_all, identifiers, session, opts)

            evidence_map: dict = {}
            if opts.includes(6) and not opts.skip_evidence:
                page_stub = assemble_output(
                    identifiers,
                    alterations,
                    merged_direct,
                    merged_via,
                    merged_all,
                    merged_natural=merged_natural,
                    natural_review=natural_meta,
                    sources_queried=list(opts.sources_queried),
                    build_time_seconds=0,
                    phase=opts.phase,
                )
                evidence_map = await clinical_evidence.enrich_page(page_stub, session, opts)

            elapsed = round(time.monotonic() - t0, 2)
            return assemble_output(
                identifiers,
                alterations,
                merged_direct,
                merged_via,
                merged_all,
                merged_natural=merged_natural,
                natural_review=natural_meta,
                therapeutic_evidence=evidence_map,
                sources_queried=opts.sources_queried,
                build_time_seconds=elapsed,
                phase=opts.phase,
            )

    try:
        page = await asyncio.wait_for(_run(), timeout=opts.disease_timeout_sec)
    except asyncio.TimeoutError:
        log.error("Pipeline timed out after %.0fs for '%s'", opts.disease_timeout_sec, disease_name)
        raise

    if opts.use_cache:
        cache_set("pipeline", cache_key, page.model_dump())

    log.info(
        "Done '%s' phase=%d: %d alterations, %d therapeutics (%.1fs)",
        page.identifiers.name,
        opts.phase,
        len(page.alterations),
        len(page.therapeutics_merged),
        page.pipeline_meta.get("build_time_seconds", 0),
    )
    return page


async def build_batch(
    disease_names: list[str],
    options: PipelineOptions | None = None,
) -> list[DiseasePageData]:
    opts = options or PipelineOptions()
    sem = asyncio.Semaphore(opts.batch_concurrency)
    output_dir = Path(__file__).parent / "cache" / "pages"
    output_dir.mkdir(parents=True, exist_ok=True)

    async def bounded(name: str) -> DiseasePageData | None:
        async with sem:
            try:
                page = await build_disease_page(name, opts)
                slug = seed_key(name)
                out_path = output_dir / f"{slug}.json"
                import json
                from .output.assembler import to_spec_json
                out_path.write_text(json.dumps(to_spec_json(page), indent=2), encoding="utf-8")
                log.info("Wrote %s", out_path)
                return page
            except Exception as e:
                log.error("Failed '%s': %s", name, e)
                return None

    results = await asyncio.gather(*[bounded(n) for n in disease_names])
    return [r for r in results if r is not None]


# Back-compat
run_pipeline = build_disease_page