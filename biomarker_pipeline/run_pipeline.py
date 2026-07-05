#!/usr/bin/env python3
"""
Biomarker → Therapeutic Agent Discovery Pipeline
=================================================
Usage (standalone):
    python -m biomarker_pipeline.run_pipeline --biomarker PPARG
    python -m biomarker_pipeline.run_pipeline --biomarker PPARG --output results/PPARG.json
    python -m biomarker_pipeline.run_pipeline --biomarker PPARG --skip-llm

Environment variables:
    NCBI_API_KEY        — NCBI E-utilities key (optional but recommended)
    ANTHROPIC_API_KEY   — Required for Stage 4 LLM extraction

Outputs a PipelineOutput JSON with agents ranked by evidence tier.
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .models import Agent, AgentId, BiomarkerInfo, PipelineOutput, RawHit, SourceRef
from .stage1_normalize import normalize_biomarker
from .stage2_databases import run_database_queries
from .stage3_literature import mine_literature
from .stage4_llm import extract_agents_from_literature

log = logging.getLogger(__name__)

# Evidence tier sort order (lower = higher priority)
_TIER_ORDER = {"mechanistic": 0, "clinical": 1, "correlative": 2}


def _configure_logging(level: int = logging.INFO) -> None:
    handlers = [logging.StreamHandler()]
    log_file = Path(__file__).parent / "pipeline.log"
    try:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    except OSError:
        pass
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


def _raw_hits_to_agents(hits: list[RawHit]) -> list[Agent]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    merged: dict[str, Agent] = {}
    for hit in hits:
        key = hit.agent.strip().lower()
        if not key:
            continue
        source = SourceRef(
            database=hit.source,
            url=hit.source_url or None,
            retrieved_at=now,
        )
        chembl_id = hit.agent_id if hit.agent_id.upper().startswith("CHEMBL") else None
        agent_id  = AgentId(chembl_id=chembl_id)

        if key in merged:
            existing = merged[key]
            existing.sources.append(source)
            # Upgrade tier if new source is stronger
            if hit.evidence_tier == "mechanistic":
                existing.evidence_tier = "mechanistic"
            elif hit.evidence_tier == "clinical" and existing.evidence_tier == "correlative":
                existing.evidence_tier = "clinical"
            # Prefer first non-null potency
            if hit.potency.value is not None and existing.potency.value is None:
                existing.potency = hit.potency
        else:
            merged[key] = Agent(
                agent_name=hit.agent,
                agent_id=agent_id,
                direction_of_effect=hit.direction,
                evidence_tier=hit.evidence_tier,
                potency=hit.potency,
                sources=[source],
            )
    return list(merged.values())


def _merge_agents(db_agents: list[Agent], lit_agents: list[Agent]) -> list[Agent]:
    merged: dict[str, Agent] = {a.agent_name.strip().lower(): a for a in db_agents}
    for agent in lit_agents:
        key = agent.agent_name.strip().lower()
        if key in merged:
            existing = merged[key]
            existing.sources.extend(agent.sources)
            if agent.evidence_tier == "mechanistic":
                existing.evidence_tier = "mechanistic"
            elif agent.evidence_tier == "clinical" and existing.evidence_tier == "correlative":
                existing.evidence_tier = "clinical"
        else:
            merged[key] = agent
    return sorted(merged.values(), key=lambda a: _TIER_ORDER.get(a.evidence_tier, 3))


async def find_agents_for_biomarker(
    biomarker: str,
    ncbi_api_key: str = "",
    anthropic_api_key: str = "",
    max_literature: int = 50,
    skip_llm: bool = False,
) -> PipelineOutput:
    log.info("=" * 64)
    log.info("Pipeline start: %s", biomarker)
    coverage_notes: list[str] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "OSMF-BiomarkerPipeline/0.1 (research@opensourcemed.info)"},
        follow_redirects=True,
        timeout=30,
    ) as client:
        # Stage 1 — identifier normalisation
        log.info("[Stage 1] Normalising '%s'", biomarker)
        norm = await normalize_biomarker(biomarker, client)
        log.info(
            "[Stage 1] symbol=%s  uniprot=%s  ensembl=%s  entity=%s",
            norm.symbol, norm.uniprot_id, norm.ensembl_id, norm.entity_type,
        )

        # Stages 2 + 3 — parallel DB queries and literature mining
        log.info("[Stage 2+3] DB queries + literature mining")
        (raw_hits, db_notes), (abstracts, lit_notes) = await asyncio.gather(
            run_database_queries(norm, client),
            mine_literature(norm, client, ncbi_api_key, max_literature),
        )
        coverage_notes.extend(db_notes)
        coverage_notes.extend(lit_notes)
        log.info("[Stage 2] %d raw DB hits", len(raw_hits))
        log.info("[Stage 3] %d abstracts", len(abstracts))

        # Stage 4 — LLM extraction
        if skip_llm:
            lit_agents: list[Agent] = []
            coverage_notes.append("Stage 4 LLM extraction skipped (--skip-llm).")
        else:
            log.info("[Stage 4] LLM extraction from %d abstracts", len(abstracts))
            lit_agents, llm_notes = await extract_agents_from_literature(
                norm, abstracts, anthropic_api_key
            )
            coverage_notes.extend(llm_notes)
            log.info("[Stage 4] %d literature agents", len(lit_agents))

    # Stage 5 — assemble and rank output
    db_agents = _raw_hits_to_agents(raw_hits)
    agents    = _merge_agents(db_agents, lit_agents)

    biomarker_info = BiomarkerInfo(
        input=biomarker,
        normalized_symbol=norm.symbol,
        uniprot_id=norm.uniprot_id,
        ensembl_id=norm.ensembl_id,
        synonyms=norm.synonyms,
        entity_type=norm.entity_type,
    )
    output = PipelineOutput(
        biomarker=biomarker_info,
        agents=agents,
        coverage_notes=coverage_notes,
    )
    log.info("[Stage 5] Done — %d agents for %s", len(agents), biomarker)
    return output


def main() -> None:
    _configure_logging()

    parser = argparse.ArgumentParser(
        description="Biomarker → Therapeutic Agent Discovery Pipeline"
    )
    parser.add_argument("--biomarker", required=True, help="Gene symbol / protein / metabolite name")
    parser.add_argument("--output", default=None, help="Output JSON file (default: stdout)")
    parser.add_argument("--max-literature", type=int, default=50, help="Max abstracts to mine")
    parser.add_argument("--skip-llm", action="store_true", help="Skip Stage 4 LLM extraction")
    parser.add_argument("--verbose", action="store_true", help="DEBUG logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    result = asyncio.run(find_agents_for_biomarker(
        biomarker=args.biomarker,
        ncbi_api_key=os.environ.get("NCBI_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        max_literature=args.max_literature,
        skip_llm=args.skip_llm,
    ))

    out_json = result.model_dump_json(indent=2)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_json, encoding="utf-8")
        print(f"Results written to {out_path}")
    else:
        print(out_json)


if __name__ == "__main__":
    main()
