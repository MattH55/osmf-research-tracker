"""Module 5 — Biomarker target → drug lookup (repurposing signals)."""
from __future__ import annotations

import logging
import re

import aiohttp

from ..cache import cache_get, cache_set
from ..config import CHEMBL_URL, DGIDB_URL
from ..http_util import graphql
from ..models import Alteration, AlterationType, DiseaseIdentifiers, EvidenceTier, Therapeutic
from ..options import PipelineOptions

log = logging.getLogger(__name__)

DGIDB_GENE_QUERY = """
query GeneInteractions($symbols: [String!]!) {
  genes(names: $symbols) {
    nodes {
      name
      interactions {
        drug { name conceptId approved }
        interactionTypes { type }
        interactionScore
      }
    }
  }
}
"""


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


async def get_dgidb_drugs_batch(
    gene_symbols: list[str], session: aiohttp.ClientSession
) -> dict[str, list[Therapeutic]]:
    result: dict[str, list[Therapeutic]] = {}
    batch_size = 20

    for i in range(0, len(gene_symbols), batch_size):
        batch = gene_symbols[i : i + batch_size]
        ck = f"dgidb_batch:{','.join(sorted(batch))}"
        cached = cache_get("drugs_via_target", ck)
        if cached is not None:
            for sym, drugs in cached.items():
                result.setdefault(sym, []).extend([Therapeutic(**t) for t in drugs])
            continue

        try:
            data = await graphql(session, DGIDB_URL, DGIDB_GENE_QUERY, {"symbols": batch})
            nodes = (data.get("data") or {}).get("genes", {}).get("nodes", [])
        except Exception as e:
            log.warning("[DGIdb batch] failed: %s", e)
            continue

        batch_cache: dict[str, list[dict]] = {}
        for node in nodes:
            symbol = node.get("name", "")
            drugs: list[Therapeutic] = []
            seen: set[str] = set()
            for ix in node.get("interactions", []):
                drug = ix.get("drug") or {}
                name = drug.get("name") or ""
                score = float(ix.get("interactionScore") or 0)
                approved = drug.get("approved", False)
                if not name or name.lower() in seen:
                    continue
                if score <= 3 and not approved:
                    continue
                seen.add(name.lower())
                concept = drug.get("conceptId", "")
                chembl_id = concept if concept.upper().startswith("CHEMBL") else None
                drugs.append(
                    Therapeutic(
                        canonical_id=chembl_id or _slug(name),
                        name=name,
                        drug_type="small_molecule",
                        mechanism="; ".join(t.get("type", "") for t in ix.get("interactionTypes", [])),
                        max_phase=4 if approved else 2,
                        source_type="via_biomarker",
                        via_alteration=symbol,
                        sources=["DGIdb"],
                        evidence_tier=EvidenceTier.A if approved else EvidenceTier.B,
                        chembl_id=chembl_id,
                        repurposing_signal=True,
                    )
                )
            batch_cache[symbol] = [d.model_dump() for d in drugs]
            result[symbol] = drugs

        if batch_cache:
            cache_set("drugs_via_target", ck, batch_cache)

    return result


async def get_drugs_for_target(
    uniprot_id: str | None,
    gene_symbol: str,
    session: aiohttp.ClientSession,
) -> list[Therapeutic]:
    ck = f"chembl_target:{gene_symbol}"
    cached = cache_get("drugs_via_target", ck)
    if cached is not None:
        return [Therapeutic(**t) for t in cached]

    from ..http_util import get_json

    try:
        target_data = await get_json(
            session,
            f"{CHEMBL_URL}/target.json",
            params={"target_synonym": gene_symbol, "organism": "Homo sapiens", "format": "json", "limit": 3},
            timeout=15,
        )
        targets = (target_data or {}).get("targets", [])
        if not targets:
            return []
        target_chembl_id = targets[0].get("target_chembl_id", "")
        drug_data = await get_json(
            session,
            f"{CHEMBL_URL}/molecule.json",
            params={
                "target_chembl_id": target_chembl_id,
                "max_phase__gte": 2,
                "format": "json",
                "limit": 50,
            },
            timeout=30,
        )
    except Exception as e:
        log.debug("[ChEMBL target] %s failed: %s", gene_symbol, e)
        return []

    therapeutics: list[Therapeutic] = []
    seen: set[str] = set()
    for mol in (drug_data or {}).get("molecules", []):
        chembl_id = mol.get("molecule_chembl_id", "")
        name = mol.get("pref_name") or chembl_id
        if not chembl_id or chembl_id in seen:
            continue
        seen.add(chembl_id)
        max_phase = int(float(mol.get("max_phase") or 0))
        therapeutics.append(
            Therapeutic(
                canonical_id=chembl_id,
                name=name,
                drug_type="small_molecule",
                max_phase=max_phase,
                source_type="via_biomarker",
                via_alteration=gene_symbol,
                sources=["ChEMBL"],
                evidence_tier=EvidenceTier.A if max_phase >= 4 else EvidenceTier.B,
                chembl_id=chembl_id,
                repurposing_signal=True,
            )
        )

    if therapeutics:
        cache_set("drugs_via_target", ck, [t.model_dump() for t in therapeutics])
    return therapeutics


async def get_all_for_targets(
    gene_symbols: list[str],
    alterations: list[Alteration],
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    options: PipelineOptions,
) -> list[Therapeutic]:
    import asyncio

    if options.skip_via_biomarker or not options.includes(3):
        return []

    symbols = gene_symbols[: options.max_genes_for_drugs]
    if not symbols:
        return []

    alt_by_name = {a.name: a for a in alterations if a.alteration_type == AlterationType.A}
    all_drugs: list[Therapeutic] = []

    dgidb_map = await get_dgidb_drugs_batch(symbols, session)
    for sym, drugs in dgidb_map.items():
        options.note_source("DGIdb")
        all_drugs.extend(drugs)

    chembl_tasks = []
    for sym in symbols[:10]:
        alt = alt_by_name.get(sym)
        uniprot = alt.source_ids.get("UniProt") if alt else None
        chembl_tasks.append(get_drugs_for_target(uniprot, sym, session))

    chembl_results = await asyncio.gather(*chembl_tasks, return_exceptions=True)
    for r in chembl_results:
        if isinstance(r, list) and r:
            options.note_source("ChEMBL")
            all_drugs.extend(r)
        elif isinstance(r, Exception):
            log.warning("ChEMBL via-target error: %s", r)

    log.info("[via-biomarker] %s → %d drugs from %d genes", identifiers.name, len(all_drugs), len(symbols))
    return all_drugs


fetch_via_biomarker_therapeutics = get_all_for_targets