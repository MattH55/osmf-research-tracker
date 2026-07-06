"""PubChem BioAssay — active compounds for disease targets."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from ....config import PUBCHEM_BASE
from ....http_util import get_json
from ...natural_products.pubchem_np import pubchem_search_by_name

log = logging.getLogger(__name__)


async def _gene_aids(gene_symbol: str, session: aiohttp.ClientSession) -> list[str]:
    try:
        data = await get_json(session, f"{PUBCHEM_BASE}/assay/target/genesym/{gene_symbol}/aids/JSON")
        aids = (data or {}).get("IdentifierList", {}).get("AID", [])
        return [str(a) for a in aids[:5]]
    except Exception:
        return []


async def get_active_nps_for_genes(
    gene_symbols: list[str],
    session: aiohttp.ClientSession,
) -> list[dict]:
    out: list[dict] = []
    for gene in gene_symbols[:8]:
        aids = await _gene_aids(gene, session)
        for aid in aids:
            try:
                data = await get_json(
                    session,
                    f"{PUBCHEM_BASE}/assay/aid/{aid}/cids/JSON",
                    params={"cids_type": "active"},
                )
                cids = (data or {}).get("IdentifierList", {}).get("CID", [])[:20]
                for cid in cids:
                    out.append({
                        "cid": str(cid),
                        "gene_target": gene,
                        "assay_id": aid,
                        "source": "PubChem BioAssay",
                    })
            except Exception:
                continue
    return out


async def enrich_compound_names(records: list[dict], session: aiohttp.ClientSession) -> list[dict]:
    enriched = []
    for rec in records[:30]:
        name = rec.get("name", "")
        if not name and rec.get("cid"):
            info = await pubchem_search_by_name(f"CID{rec['cid']}", session)
            if info:
                rec["name"] = info.get("iupac_name", rec["cid"])
        enriched.append(rec)
    return enriched