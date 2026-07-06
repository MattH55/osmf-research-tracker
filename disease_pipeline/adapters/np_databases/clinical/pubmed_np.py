"""PubMed + LLM natural product extraction."""
from __future__ import annotations

import logging

import aiohttp

from ....models import DiseaseIdentifiers
from ....options import PipelineOptions
from ...natural_products import llm_extract, pubmed_np as pubmed_mod

log = logging.getLogger(__name__)


async def search_and_extract(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    options: PipelineOptions | None = None,
) -> list[dict]:
    opts = options or PipelineOptions()
    records = await pubmed_mod.search_pubmed_np(
        identifiers, session, max_results=opts.max_pubmed_np_results, options=opts
    )
    if opts.skip_llm_extract:
        return [
            {
                "np_name": r.get("title", "")[:80],
                "study_type": r.get("study_type", "other"),
                "outcome": "unclear",
                "source_pmid": r.get("pmid"),
                "year": r.get("year"),
                "source": "PubMed",
            }
            for r in records
        ]

    extracted = await llm_extract.extract_np_from_abstracts(records, identifiers.name, opts)
    for row in extracted:
        row["source"] = "PubMed"
    return extracted