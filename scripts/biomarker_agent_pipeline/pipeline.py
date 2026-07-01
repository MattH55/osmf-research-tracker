"""Main pipeline entry: find_agents_for_biomarker."""
from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone

from .adapters import query_chembl, query_ctd, query_dgidb, query_opentargets
from .config import EXCLUDED_SOURCES
from .extract import extract_from_database_hits, extract_from_literature
from .literature import mine_literature
from .merge import merge_agents
from .models import PipelineOutput, RawHit
from .config import openai_api_key
from .normalize import normalize_biomarker


def _query_structured_sources(norm):
    adapters = [
        ("DGIdb", query_dgidb),
        ("OpenTargets", query_opentargets),
        ("ChEMBL", query_chembl),
        ("CTD", query_ctd),
    ]
    hits: list[RawHit] = []
    errors: list[str] = []

    def run_one(item):
        name, fn = item
        try:
            return fn(norm), None
        except Exception as err:
            return [], f"{name} query failed: {err}"

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result, err in pool.map(run_one, adapters):
            hits.extend(result)
            if err:
                errors.append(err)
    return hits, errors


def find_agents_for_biomarker(biomarker: str, *, skip_literature: bool = False) -> dict:
    coverage: list[str] = []
    if "drugbank" in EXCLUDED_SOURCES:
        coverage.append("DrugBank excluded (paid license) — not queried.")

    norm = normalize_biomarker(biomarker)
    coverage.extend(norm.resolution_notes)

    db_hits, db_errors = _query_structured_sources(norm)
    coverage.extend(db_errors)

    articles: list = []
    if skip_literature:
        coverage.append("Literature mining skipped (--skip-literature).")
    else:
        articles, lit_notes = mine_literature(norm)
        coverage.extend(lit_notes)

    db_records = extract_from_database_hits(db_hits)
    lit_records = extract_from_literature(articles, norm) if articles else []

    if not lit_records and articles:
        coverage.append("Literature present but no grounded agent claims extracted (rule/LLM).")
    if not openai_api_key():
        coverage.append("OPENAI_API_KEY not set — literature extraction uses rule-based parser only.")

    merged = merge_agents(db_records + lit_records, norm)

    output = PipelineOutput(
        biomarker=norm,
        agents=merged,
        coverage_notes=coverage,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
    return output.model_dump()