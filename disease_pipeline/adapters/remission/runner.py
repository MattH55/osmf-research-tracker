"""Orchestrate three-layer remission enrichment."""
from __future__ import annotations

import logging

import aiohttp

from ...models import DiseaseIdentifiers
from ...options import PipelineOptions
from .db100 import get_db100_remission
from .gbd import get_gbd_remission_rate
from .merge import merge_remission_layers
from .pubmed import search_and_extract

log = logging.getLogger(__name__)


async def enrich_remission(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    *,
    disease_slug: str = "",
    options: PipelineOptions | None = None,
) -> dict:
    opts = options or PipelineOptions()
    slug = disease_slug or identifiers.name

    db100 = get_db100_remission(slug, identifiers.name)

    gbd = None
    if not opts.skip_gbd_remission:
        gbd = await get_gbd_remission_rate(slug, identifiers.name, session)

    pubmed_rows: list[dict] = []
    if not opts.skip_pubmed_remission:
        pubmed_rows = await search_and_extract(
            identifiers.name,
            identifiers.mesh_id,
            session,
            use_llm=not opts.skip_llm_extract,
        )

    remission = merge_remission_layers(db100=db100, gbd=gbd, pubmed_rows=pubmed_rows)
    log.info(
        "[Remission] '%s' layers=%s locked=%s",
        identifiers.name,
        remission.get("layers"),
        remission.get("source_locked", False),
    )
    return remission