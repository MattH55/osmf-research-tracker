"""LOTUS — natural product occurrences + Wikidata."""
from __future__ import annotations

import logging

import aiohttp

from ....models import Alteration, AlterationType
from ...natural_products.lotus import lotus_search_by_name

log = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"


async def search_by_name(name: str, session: aiohttp.ClientSession) -> dict | None:
    return await lotus_search_by_name(name, session)


async def search_nps_for_targets(
    alterations: list[Alteration],
    session: aiohttp.ClientSession,
) -> list[dict]:
    genes = [a.name for a in alterations if a.alteration_type == AlterationType.A]
    out: list[dict] = []
    for gene in genes[:10]:
        rows = await _sparql_target(gene, session)
        out.extend(rows)
    return out


async def _sparql_target(gene_symbol: str, session: aiohttp.ClientSession) -> list[dict]:
    query = f"""
    SELECT ?np ?npLabel WHERE {{
      ?np wdt:P31 wd:Q11173 .
      ?np rdfs:label ?npLabel .
      FILTER(CONTAINS(LCASE(?npLabel), "{gene_symbol.lower()}"))
    }} LIMIT 10
    """
    try:
        async with session.get(
            WIKIDATA_SPARQL,
            params={"query": query, "format": "json"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()
    except Exception as e:
        log.debug("[LOTUS/WD] SPARQL failed for %s: %s", gene_symbol, e)
        return []

    results = []
    for binding in data.get("results", {}).get("bindings", []):
        results.append({
            "name": binding.get("npLabel", {}).get("value", ""),
            "wikidata_id": binding.get("np", {}).get("value", "").rsplit("/", 1)[-1],
            "target_gene": gene_symbol,
            "source": "LOTUS",
        })
    return results