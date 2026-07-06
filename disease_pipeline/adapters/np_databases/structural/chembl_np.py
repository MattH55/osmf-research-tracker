"""ChEMBL natural product bioactivity."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from ...natural_products.chembl_np import (
    get_chembl_np_batch,
    get_chembl_np_for_target,
    _resolve_chembl_target,
)
from ....models import Alteration

log = logging.getLogger(__name__)


async def resolve_gene_to_target_id(gene_symbol: str, session: aiohttp.ClientSession) -> str | None:
    return await _resolve_chembl_target(gene_symbol, session)


async def resolve_genes_to_targets(
    gene_symbols: list[str],
    session: aiohttp.ClientSession,
) -> dict[str, str]:
    pairs = await asyncio.gather(
        *[resolve_gene_to_target_id(g, session) for g in gene_symbols[:15]]
    )
    return {g: tid for g, tid in zip(gene_symbols[:15], pairs) if tid}


async def get_np_compounds_for_target(
    target_chembl_id: str,
    gene_symbol: str,
    session: aiohttp.ClientSession,
) -> list[dict]:
    rows = await get_chembl_np_for_target(target_chembl_id, gene_symbol, session)
    for r in rows:
        r["source"] = "ChEMBL-NP"
    return rows


async def get_np_compounds_for_targets(
    target_map: dict[str, str],
    session: aiohttp.ClientSession,
) -> list[dict]:
    tasks = [
        get_np_compounds_for_target(tid, gene, session)
        for gene, tid in target_map.items()
    ]
    results = await asyncio.gather(*tasks)
    out: list[dict] = []
    for batch in results:
        out.extend(batch)
    return out


async def get_np_for_alterations(
    alterations: list[Alteration],
    session: aiohttp.ClientSession,
    *,
    max_targets: int = 15,
) -> list[dict]:
    raw = await get_chembl_np_batch(alterations, session, max_targets=max_targets)
    for r in raw:
        r["source"] = "ChEMBL-NP"
    return raw