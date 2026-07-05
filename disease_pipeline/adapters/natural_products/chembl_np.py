"""NP-3 — ChEMBL natural product bioactivity against Type A targets."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

import aiohttp

from ...cache import cache_get, cache_set
from ...config import CHEMBL_URL
from ...http_util import get_json
from ...models import Alteration, AlterationType

log = logging.getLogger(__name__)


async def _resolve_chembl_target(
    gene_symbol: str, session: aiohttp.ClientSession
) -> str | None:
    ck = f"target:{gene_symbol}"
    cached = cache_get("chembl_np", ck)
    if cached is not None:
        return cached.get("target_chembl_id")

    try:
        data = await get_json(
            session,
            f"{CHEMBL_URL}/target.json",
            params={
                "target_synonym": gene_symbol,
                "organism": "Homo sapiens",
                "limit": 5,
            },
        )
        targets = (data or {}).get("targets", [])
        target_id = targets[0].get("target_chembl_id") if targets else None
        cache_set("chembl_np", ck, {"target_chembl_id": target_id})
        return target_id
    except Exception as e:
        log.debug("[ChEMBL NP] target resolve failed for %s: %s", gene_symbol, e)
        return None


async def get_chembl_np_for_target(
    target_chembl_id: str,
    gene_symbol: str,
    session: aiohttp.ClientSession,
) -> list[dict]:
    ck = f"np_act:{target_chembl_id}"
    cached = cache_get("chembl_np", ck)
    if cached is not None:
        return cached.get("activities", [])

    try:
        data = await get_json(
            session,
            f"{CHEMBL_URL}/activity.json",
            params={
                "target_chembl_id": target_chembl_id,
                "molecule__natural_product": "1",
                "standard_type__in": "IC50,Ki,Kd,EC50,Potency,Inhibition",
                "standard_relation__in": "=,<",
                "standard_value__lte": "10000",
                "assay_type": "B",
                "limit": 100,
            },
        )
        activities = (data or {}).get("activities", [])
        results: list[dict] = []
        seen_mols: set[str] = set()

        for act in activities:
            mol_id = act.get("molecule_chembl_id", "")
            if not mol_id or mol_id in seen_mols:
                continue
            seen_mols.add(mol_id)

            mol_data = await get_json(session, f"{CHEMBL_URL}/molecule/{mol_id}.json")
            mol = (mol_data or {}).get("molecule", mol_data) or {}
            if mol.get("natural_product") != 1:
                continue

            results.append({
                "molecule_chembl_id": mol_id,
                "molecule_pref_name": mol.get("pref_name") or act.get("molecule_pref_name", ""),
                "standard_value": act.get("standard_value"),
                "standard_units": act.get("standard_units"),
                "standard_type": act.get("standard_type"),
                "assay_description": act.get("assay_description", ""),
                "target_gene": gene_symbol,
                "max_phase": mol.get("max_phase", 0),
            })

        cache_set("chembl_np", ck, {"activities": results})
        return results
    except Exception as e:
        log.warning("[ChEMBL NP] activity fetch failed for %s: %s", target_chembl_id, e)
        return []


async def get_chembl_np_batch(
    type_a_alterations: list[Alteration],
    session: aiohttp.ClientSession,
    *,
    max_targets: int = 10,
) -> list[dict]:
    genes = [
        a.name for a in type_a_alterations
        if a.alteration_type == AlterationType.A and a.subtype in ("gene", "protein")
    ][:max_targets]

    if not genes:
        return []

    sem = asyncio.Semaphore(5)

    async def _for_gene(gene: str) -> list[dict]:
        async with sem:
            target_id = await _resolve_chembl_target(gene, session)
            if not target_id:
                return []
            return await get_chembl_np_for_target(target_id, gene, session)

    all_acts = await asyncio.gather(*[_for_gene(g) for g in genes])

    grouped: dict[str, dict] = {}
    for acts in all_acts:
        for act in acts:
            cid = act["molecule_chembl_id"]
            if cid not in grouped:
                grouped[cid] = {
                    "chembl_id": cid,
                    "name": act["molecule_pref_name"],
                    "targets_hit": [],
                    "activities": [],
                    "max_phase": act.get("max_phase", 0),
                }
            grouped[cid]["targets_hit"].append(act["target_gene"])
            grouped[cid]["activities"].append(act)
            grouped[cid]["targets_hit"] = sorted(set(grouped[cid]["targets_hit"]))

    return list(grouped.values())