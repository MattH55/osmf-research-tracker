"""Module 2 — Molecular alterations (genes, proteins, metabolites)."""
from __future__ import annotations

import logging
import re

import aiohttp

from ..cache import cache_get, cache_set
from ..config import DISGENET_URL, OPEN_TARGETS_URL, UNIPROT_SEARCH, get_disgenet_api_key
from ..http_util import get_json, graphql
from ..models import Alteration, AlterationType, DiseaseIdentifiers, EvidenceTier
from ..options import PipelineOptions
from .ot_ids import ot_disease_id

log = logging.getLogger(__name__)

OT_TARGETS_QUERY = """
query DiseaseTargets($efoId: String!) {
  disease(efoId: $efoId) {
    associatedTargets(page: {index: 0, size: 100}) {
      rows {
        target {
          id
          approvedSymbol
          approvedName
          biotype
          proteinIds { id source }
        }
        score
        datatypeScores { id score }
      }
    }
  }
}
"""


OT_SCORES_QUERY = """
query DiseaseTargetScores($efoId: String!, $ids: [String!]) {
  disease(efoId: $efoId) {
    associatedTargets(Bs: $ids, page: {index: 0, size: 500}) {
      rows { target { id } score }
    }
  }
}
"""

OT_VERSION_QUERY = "query { meta { dataVersion { year month } } }"


def ot_score_label(score: float | None) -> str:
    """Evidence wording for an Open Targets gene row: the association score itself."""
    if score is None:
        return "Open Targets association (score n/a)"
    return f"OT score {score:.2f}"


async def ot_data_version(session: aiohttp.ClientSession) -> str | None:
    try:
        data = await graphql(session, OPEN_TARGETS_URL, OT_VERSION_QUERY, {})
        dv = ((data.get("data") or {}).get("meta") or {}).get("dataVersion") or {}
        return f"{dv.get('year')}.{dv.get('month')}" if dv.get("year") else None
    except Exception as e:  # pragma: no cover - network
        log.warning("[Open Targets] version lookup failed: %s", e)
        return None


async def ot_association_scores(
    ot_id: str, ensembl_ids: list[str], session: aiohttp.ClientSession
) -> dict[str, float]:
    """Current Open Targets overall association score for given targets of a disease."""
    scores: dict[str, float] = {}
    ids = [i for i in ensembl_ids if i]
    for start in range(0, len(ids), 200):
        chunk = ids[start : start + 200]
        data = await graphql(session, OPEN_TARGETS_URL, OT_SCORES_QUERY, {"efoId": ot_id, "ids": chunk})
        rows = (((data.get("data") or {}).get("disease") or {}).get("associatedTargets") or {}).get("rows") or []
        for row in rows:
            tid = (row.get("target") or {}).get("id")
            if tid:
                scores[tid] = float(row.get("score") or 0)
    return scores


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


def _ot_evidence_tier(score: float, datatypes: list[dict]) -> EvidenceTier:
    strong = [d for d in datatypes if d.get("score", 0) >= 0.3]
    if score >= 0.5 and len(strong) >= 2:
        return EvidenceTier.A
    if score >= 0.3 or len(strong) >= 1:
        return EvidenceTier.B
    return EvidenceTier.C


async def _open_targets_genes(
    identifiers: DiseaseIdentifiers, session: aiohttp.ClientSession
) -> list[Alteration]:
    ot_id = ot_disease_id(identifiers)
    if not ot_id:
        return []

    # v2: rows carry the OT association score (provenance fix 2026-10-15)
    ck = f"ot_targets:v2:{ot_id}"
    cached = cache_get("molecular", ck)
    if cached is not None:
        return [Alteration(**a) for a in cached]

    try:
        data = await graphql(session, OPEN_TARGETS_URL, OT_TARGETS_QUERY, {"efoId": ot_id})
        disease = (data.get("data") or {}).get("disease")
        if disease is None:
            # Not an Open Targets disease ID (e.g. MONDO terms OT does not index):
            # say so instead of silently returning nothing.
            log.warning("[Open Targets] %s is not an Open Targets disease ID", ot_id)
            return []
        rows = (disease.get("associatedTargets") or {}).get("rows", [])
    except Exception as e:
        log.warning("[Open Targets] gene fetch failed: %s", e)
        return []

    alterations: list[Alteration] = []
    for row in rows:
        target = row.get("target") or {}
        symbol = target.get("approvedSymbol") or ""
        if not symbol:
            continue
        ensembl_id = target.get("id", "")
        uniprot = ""
        for pid in target.get("proteinIds") or []:
            if pid.get("source") == "uniprot_swissprot" and pid.get("id"):
                uniprot = pid["id"]
                break
        canonical_id = uniprot or ensembl_id or _slug(symbol)
        score = float(row.get("score") or 0)
        datatypes = row.get("datatypeScores") or []
        alterations.append(
            Alteration(
                canonical_id=canonical_id,
                name=symbol,
                alteration_type=AlterationType.A,
                subtype="gene",
                sources=["Open Targets"],
                source_ids={"Ensembl": ensembl_id, **({"UniProt": uniprot} if uniprot else {})},
                # Gene-disease association, not a measured alteration: carry the
                # OT score itself instead of a derived tier.
                evidence_tier=EvidenceTier.N,
                evidence_label=ot_score_label(score),
                association_score=round(score, 4),
                definition=target.get("approvedName"),
            )
        )

    if alterations:
        cache_set("molecular", ck, [a.model_dump() for a in alterations])
    log.info("[Open Targets] %s → %d genes", identifiers.name, len(alterations))
    return alterations


async def get_disgenet_genes(umls_cui: str, session: aiohttp.ClientSession) -> list[dict]:
    api_key = get_disgenet_api_key()
    if not api_key or not umls_cui:
        return []

    ck = f"disgenet:{umls_cui}"
    cached = cache_get("molecular", ck)
    if cached is not None:
        return cached

    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"source": "ALL", "format": "json", "limit": 100, "min_score": 0.1}
    try:
        data = await get_json(session, f"{DISGENET_URL}/gda/disease/{umls_cui}", params=params, headers=headers)
        rows = data if isinstance(data, list) else data.get("data", data.get("results", []))
        if rows:
            cache_set("molecular", ck, rows)
        return rows or []
    except Exception as e:
        log.warning("[DisGeNET] failed for %s: %s", umls_cui, e)
        return []


async def _disgenet_alterations(
    identifiers: DiseaseIdentifiers, session: aiohttp.ClientSession
) -> list[Alteration]:
    rows = await get_disgenet_genes(identifiers.umls_cui or "", session)
    alterations: list[Alteration] = []
    for row in rows:
        symbol = row.get("gene_symbol") or row.get("geneSymbol") or ""
        if not symbol:
            continue
        score = float(row.get("score") or row.get("DSI") or 0)
        gene_id = str(row.get("geneid") or row.get("geneId") or "")
        alterations.append(
            Alteration(
                canonical_id=_slug(symbol),
                name=symbol,
                alteration_type=AlterationType.A,
                subtype="gene",
                sources=["DisGeNET"],
                source_ids={"NCBI Gene": gene_id} if gene_id else {},
                evidence_tier=EvidenceTier.B if score >= 0.3 else EvidenceTier.C,
            )
        )
    log.info("[DisGeNET] %s → %d genes", identifiers.name, len(alterations))
    return alterations


async def get_hmdb_metabolites(disease_name: str, session: aiohttp.ClientSession) -> list[Alteration]:
    """HMDB bulk cache not present — skip to avoid hanging on unavailable bulk download."""
    log.warning("[HMDB] bulk cache not available — skipping metabolites for '%s'", disease_name)
    return []


async def enrich_with_uniprot(
    alterations: list[Alteration],
    session: aiohttp.ClientSession,
    *,
    limit: int = 25,
) -> list[Alteration]:
    genes = [a for a in alterations if a.alteration_type == AlterationType.A and a.subtype == "gene"][:limit]
    if not genes:
        return alterations

    by_id = {a.canonical_id: a for a in alterations}
    for gene in genes:
        symbol = gene.name
        ck = f"uniprot_gene:{symbol}"
        cached = cache_get("molecular", ck)
        if cached:
            entry = cached
        else:
            try:
                data = await get_json(
                    session,
                    UNIPROT_SEARCH,
                    params={
                        "query": f"gene:{symbol} AND organism_id:9606",
                        "fields": "accession,gene_names,protein_name,go",
                        "format": "json",
                        "size": "1",
                    },
                )
                results = data.get("results", []) if data else []
                if not results:
                    continue
                entry = results[0]
                cache_set("molecular", ck, entry)
            except Exception as e:
                log.debug("[UniProt enrich] %s failed: %s", symbol, e)
                continue

        accession = entry.get("primaryAccession", "")
        pname = (entry.get("proteinDescription") or {}).get("recommendedName", {})
        full_name = (pname.get("fullName") or {}).get("value", symbol)
        go_terms = []
        for comment in entry.get("comments", []):
            if comment.get("commentType") == "FUNCTION":
                for text in comment.get("texts", []):
                    go_terms.append(text.get("value", ""))

        key = gene.canonical_id
        if key in by_id:
            source_ids = {**by_id[key].source_ids, "UniProt": accession}
            definition = by_id[key].definition or full_name
            if go_terms:
                definition = f"{definition}; GO: {go_terms[0][:120]}" if definition else go_terms[0][:120]
            by_id[key] = by_id[key].model_copy(
                update={"source_ids": source_ids, "definition": definition, "canonical_id": accession or key}
            )

    return list(by_id.values())


async def get_all(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    options: PipelineOptions,
) -> list[Alteration]:
    import asyncio

    tasks = [_open_targets_genes(identifiers, session)]
    if options.includes(4) and not options.skip_disgenet:
        tasks.append(_disgenet_alterations(identifiers, session))
    if options.includes(5) and not options.skip_hmdb:
        tasks.append(get_hmdb_metabolites(identifiers.name, session))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_alts: list[Alteration] = []
    for r in results:
        if isinstance(r, list):
            if r:
                options.note_source(r[0].sources[0])
            all_alts.extend(r)
        elif isinstance(r, Exception):
            log.warning("Molecular error: %s", r)

    if options.includes(5):
        all_alts = await enrich_with_uniprot(all_alts, session, limit=options.max_genes_for_drugs)

    return all_alts


fetch_molecular_alterations = get_all