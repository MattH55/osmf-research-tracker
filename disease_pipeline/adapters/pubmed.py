"""Module 7 — PubMed co-occurrence validation."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from ..cache import cache_get, cache_set
from ..config import PUBMED_URL, get_ncbi_api_key
from ..http_util import get_json
from ..models import Alteration, DiseaseIdentifiers, EvidenceTier, Therapeutic
from ..options import PipelineOptions

log = logging.getLogger(__name__)


async def get_pubmed_count(
    disease_mesh: str,
    term: str,
    session: aiohttp.ClientSession,
) -> int:
    if not disease_mesh or not term:
        return 0

    ck = f"{disease_mesh}:{term.lower()}"
    cached = cache_get("pubmed", ck)
    if cached is not None:
        return int(cached.get("count", 0))

    query = f'"{term}"[Title/Abstract] AND "{disease_mesh}"[MeSH Terms]'
    params: dict[str, str] = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": "0",
    }
    api_key = get_ncbi_api_key()
    if api_key:
        params["api_key"] = api_key

    try:
        data = await get_json(session, f"{PUBMED_URL}/esearch.fcgi", params=params)
        if not data:
            return 0
        count = int(data.get("esearchresult", {}).get("count", 0))
        if count > 0:
            cache_set("pubmed", ck, {"count": count})
        return count
    except Exception as e:
        log.warning("[PubMed] count failed for '%s': %s", term[:60], e)
        return 0


def _promote_tier(tier: EvidenceTier, count: int, source_count: int) -> EvidenceTier:
    if count >= 50 and source_count >= 2:
        return EvidenceTier.A
    if count >= 10:
        return EvidenceTier.B
    return tier


async def validate_batch(
    items: list[Alteration | Therapeutic],
    disease_identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    options: PipelineOptions | None = None,
) -> list[Alteration | Therapeutic]:
    opts = options or PipelineOptions()
    mesh = disease_identifiers.mesh_id or ""
    if not mesh or opts.skip_pubmed or not opts.includes(4):
        return items

    tier_c = [i for i in items if i.evidence_tier == EvidenceTier.C][: opts.max_pubmed_items]
    if not tier_c:
        return items

    async def _validate_one(item: Alteration | Therapeutic) -> Alteration | Therapeutic:
        term = item.name
        count = await get_pubmed_count(mesh, term, session)
        tier = _promote_tier(item.evidence_tier, count, len(item.sources))
        return item.model_copy(update={"pubmed_count": count, "evidence_tier": tier})

    results = await asyncio.gather(*[_validate_one(i) for i in tier_c], return_exceptions=True)
    updated_map = {id(items[i]): items[i] for i in range(len(items))}

    tier_c_ids = {id(i) for i in tier_c}
    for item, result in zip(tier_c, results):
        if isinstance(result, Exception):
            log.warning("[PubMed] validation error: %s", result)
            continue
        updated_map[id(item)] = result

    return [updated_map[id(i)] for i in items]


# Back-compat
validate_alterations = validate_batch
validate_therapeutics = validate_batch