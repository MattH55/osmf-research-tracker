"""Stage 2 — Structured database queries (async, parallel).

Adapters: DGIdb · Open Targets · ChEMBL · CTD
DrugBank is excluded (commercial licence required; noted in coverage_notes).

Each adapter returns list[RawHit]. Failures are isolated — one failed adapter
does not abort the others. Results are cached per-source per-biomarker for
DEFAULT_TTL_DAYS days.
"""
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .cache import cache_get, cache_set
from .models import NormalizedBiomarker, PotencyData, RawHit

log = logging.getLogger(__name__)

DGIDB_URL      = "https://dgidb.org/api/graphql"
OPENTARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"
CHEMBL_BASE    = "https://www.ebi.ac.uk/chembl/api/data"
CTD_URL        = "https://ctdbase.org/tools/batchQuery.go"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _map_direction(interaction_type: str) -> str:
    t = (interaction_type or "").lower()
    if any(k in t for k in ("inhibitor", "blocker", "antagonist", "suppressor", "inverse agonist")):
        return "inhibits"
    if any(k in t for k in ("activator", "agonist", "stimulator", "inducer", "potentiator")):
        return "activates"
    if "decrease" in t:
        return "decreases"
    if "increase" in t:
        return "increases"
    if any(k in t for k in ("modulator", "binder", "substrate", "ligand", "cofactor")):
        return "modulates"
    return "unclear"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=12),
    retry=retry_if_exception_type(httpx.HTTPStatusError),
)
async def _graphql(
    client: httpx.AsyncClient, url: str, query: str, variables: dict | None = None
) -> dict:
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    r = await client.post(url, json=payload, timeout=20)
    if r.status_code == 429:
        raise httpx.HTTPStatusError("429 Too Many Requests", request=r.request, response=r)
    r.raise_for_status()
    return r.json()


# ─── DGIdb ───────────────────────────────────────────────────────────────────

async def _dgidb(norm: NormalizedBiomarker, client: httpx.AsyncClient) -> list[RawHit]:
    symbol = norm.symbol or norm.input_name
    ck = f"dgidb:{symbol}"
    cached = cache_get("stage2_dgidb", ck)
    if cached is not None:
        return [RawHit(**h) for h in cached]

    query = """
    query($genes: [String!]!) {
      genes(names: $genes) {
        nodes {
          name
          interactions {
            drug { name conceptId }
            interactionTypes { type directionality }
            interactionScore
            publications { pmid }
            sources { fullName sourceDbName }
          }
        }
      }
    }
    """
    try:
        data = await _graphql(client, DGIDB_URL, query, {"genes": [symbol]})
        nodes = data.get("data", {}).get("genes", {}).get("nodes", [])
        hits: list[RawHit] = []
        for node in nodes:
            for ix in node.get("interactions", []):
                drug = ix.get("drug") or {}
                if not drug.get("name"):
                    continue
                itype = " ".join(t.get("type", "") for t in ix.get("interactionTypes", [])) or "unknown"
                pmids = [str(p["pmid"]) for p in ix.get("publications", []) if p.get("pmid")]
                hits.append(RawHit(
                    agent=drug["name"],
                    agent_id=drug.get("conceptId", ""),
                    interaction_type=itype,
                    direction=_map_direction(itype),
                    source="DGIdb",
                    source_url=f"https://dgidb.org/genes/{symbol}",
                    evidence_tier="mechanistic",
                    pubmed_ids=pmids,
                    raw={"score": ix.get("interactionScore")},
                ))
        cache_set("stage2_dgidb", ck, [h.model_dump() for h in hits])
        log.info("[DGIdb] %s → %d hits", symbol, len(hits))
        return hits
    except Exception as e:
        log.warning("[DGIdb] failed for %s: %s", symbol, e)
        return []


# ─── Open Targets ─────────────────────────────────────────────────────────────

async def _opentargets(norm: NormalizedBiomarker, client: httpx.AsyncClient) -> list[RawHit]:
    ensembl_id = norm.ensembl_id
    if not ensembl_id:
        log.debug("[OpenTargets] skipped — no Ensembl ID for %s", norm.input_name)
        return []

    ck = f"ot:{ensembl_id}"
    cached = cache_get("stage2_ot", ck)
    if cached is not None:
        return [RawHit(**h) for h in cached]

    # Platform v24+ renamed knownDrugs → drugAndClinicalCandidates.
    # Row type: ClinicalTargetFromTarget {id, maxClinicalStage: String, drug: Drug}
    # Drug.drugType is a plain String; maxClinicalStage is "PHASE_3" / "PHASE_4" etc.
    query = """
    query($ensemblId: String!) {
      target(ensemblId: $ensemblId) {
        drugAndClinicalCandidates {
          count
          rows {
            id
            maxClinicalStage
            drug { id name drugType }
          }
        }
      }
    }
    """
    try:
        data = await _graphql(client, OPENTARGETS_URL, query, {"ensemblId": ensembl_id})
        target = (data.get("data") or {}).get("target") or {}
        rows = (target.get("drugAndClinicalCandidates") or {}).get("rows") or []
        hits: list[RawHit] = []
        for row in rows:
            drug = row.get("drug") or {}
            if not drug.get("name"):
                continue
            stage = (row.get("maxClinicalStage") or "").upper()
            # "PHASE_3", "PHASE_4", "APPROVED" → clinical; lower → mechanistic
            tier = "clinical" if any(k in stage for k in ("PHASE_3", "PHASE_4", "APPROVED")) else "mechanistic"
            drug_type = drug.get("drugType") or ""
            hits.append(RawHit(
                agent=drug["name"],
                agent_id=drug.get("id", ""),
                interaction_type=drug_type,
                direction=_map_direction(drug_type),
                source="Open Targets",
                source_url=f"https://platform.opentargets.org/target/{ensembl_id}",
                evidence_tier=tier,
                raw={"maxClinicalStage": stage},
            ))
        cache_set("stage2_ot", ck, [h.model_dump() for h in hits])
        log.info("[OpenTargets] %s → %d hits", ensembl_id, len(hits))
        return hits
    except Exception as e:
        log.warning("[OpenTargets] failed for %s: %s", ensembl_id, e)
        return []


# ─── ChEMBL ───────────────────────────────────────────────────────────────────

async def _chembl(norm: NormalizedBiomarker, client: httpx.AsyncClient) -> list[RawHit]:
    uniprot_id = norm.uniprot_id
    if not uniprot_id:
        log.debug("[ChEMBL] skipped — no UniProt ID for %s", norm.input_name)
        return []

    ck = f"chembl:{uniprot_id}"
    cached = cache_get("stage2_chembl", ck)
    if cached is not None:
        return [RawHit(**h) for h in cached]

    try:
        # Resolve UniProt → ChEMBL target via component accession (more reliable than /search)
        r = await client.get(
            f"{CHEMBL_BASE}/target.json",
            params={
                "target_components__accession": uniprot_id,
                "format": "json",
                "limit": "5",
            },
            timeout=15,
        )
        r.raise_for_status()
        chembl_target_id: str | None = None
        for t in r.json().get("targets", []):
            chembl_target_id = t.get("target_chembl_id")
            if chembl_target_id:
                break

        if not chembl_target_id:
            log.debug("[ChEMBL] no target for UniProt %s", uniprot_id)
            return []

        # Fetch bioactivity records (only those with a pChEMBL value)
        r2 = await client.get(
            f"{CHEMBL_BASE}/activity.json",
            params={
                "target_chembl_id": chembl_target_id,
                "format": "json",
                "limit": "200",
                "pchembl_value__isnull": "false",
            },
            timeout=20,
        )
        r2.raise_for_status()
        activities = r2.json().get("activities", [])

        hits: list[RawHit] = []
        seen: set[str] = set()
        for act in activities:
            mol_name = act.get("molecule_pref_name") or act.get("molecule_chembl_id", "")
            if not mol_name or mol_name in seen:
                continue
            seen.add(mol_name)
            atype = act.get("standard_type", "") or ""
            try:
                val = float(act.get("standard_value") or 0)
            except (TypeError, ValueError):
                val = None
            potency = PotencyData(
                value=val,
                unit=act.get("standard_units"),
                measure=atype if atype in ("IC50", "Ki", "EC50", "Kd") else None,
            )
            direction = "inhibits" if atype in ("IC50", "Ki", "Kd") else (
                "activates" if atype == "EC50" else "modulates"
            )
            hits.append(RawHit(
                agent=mol_name,
                agent_id=act.get("molecule_chembl_id", ""),
                interaction_type=atype,
                direction=direction,
                source="ChEMBL",
                source_url=f"https://www.ebi.ac.uk/chembl/target_report_card/{chembl_target_id}/",
                evidence_tier="mechanistic",
                potency=potency,
                raw={"assay_type": act.get("assay_type"), "chembl_target": chembl_target_id},
            ))

        cache_set("stage2_chembl", ck, [h.model_dump() for h in hits])
        log.info("[ChEMBL] %s → %d hits", uniprot_id, len(hits))
        return hits
    except Exception as e:
        log.warning("[ChEMBL] failed for %s: %s", uniprot_id, e)
        return []


# ─── CTD ──────────────────────────────────────────────────────────────────────

async def _ctd(norm: NormalizedBiomarker, client: httpx.AsyncClient) -> list[RawHit]:
    symbol = norm.symbol or norm.input_name
    ck = f"ctd:{symbol}"
    cached = cache_get("stage2_ctd", ck)
    if cached is not None:
        return [RawHit(**h) for h in cached]

    try:
        r = await client.get(
            CTD_URL,
            params={
                "inputType": "gene",
                "inputTerms": symbol,
                "report": "genes_curated_chemical_gene_interactions",
                "format": "json",
            },
            timeout=25,
            follow_redirects=True,
        )
        r.raise_for_status()
        raw = r.json()
        records: list[dict] = raw if isinstance(raw, list) else []

        hits: list[RawHit] = []
        for rec in records[:200]:
            chemical = rec.get("ChemicalName") or rec.get("chemicalname", "")
            if not chemical:
                continue
            ix_action = rec.get("Interaction") or rec.get("interaction") or ""
            pmids_raw = rec.get("PubMedIds") or rec.get("pubmedids") or ""
            pmids = [p.strip() for p in str(pmids_raw).split("|") if p.strip()] if pmids_raw else []
            hits.append(RawHit(
                agent=chemical,
                agent_id=rec.get("CasRN", ""),
                interaction_type=ix_action,
                direction=_map_direction(ix_action),
                source="CTD",
                source_url=f"https://ctdbase.org/detail.go?type=gene&acc={symbol}",
                evidence_tier="correlative",
                pubmed_ids=pmids,
            ))

        cache_set("stage2_ctd", ck, [h.model_dump() for h in hits])
        log.info("[CTD] %s → %d hits", symbol, len(hits))
        return hits
    except Exception as e:
        log.warning("[CTD] failed for %s: %s", symbol, e)
        return []


# ─── Orchestrator ─────────────────────────────────────────────────────────────

async def run_database_queries(
    norm: NormalizedBiomarker,
    client: httpx.AsyncClient,
) -> tuple[list[RawHit], list[str]]:
    coverage_notes = ["DrugBank not queried — commercial licence required."]

    results = await asyncio.gather(
        _dgidb(norm, client),
        _opentargets(norm, client),
        _chembl(norm, client),
        _ctd(norm, client),
        return_exceptions=True,
    )

    hits: list[RawHit] = []
    for name, result in zip(["DGIdb", "Open Targets", "ChEMBL", "CTD"], results):
        if isinstance(result, Exception):
            coverage_notes.append(f"{name} query raised an exception: {result}")
        else:
            hits.extend(result)

    return hits, coverage_notes
