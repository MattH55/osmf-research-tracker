"""Disease-level agent discovery — search FROM the disease, not from a
pre-selected gene panel.

The existing pipeline (run_pipeline.py / run_for_diseases.py) only finds
agents that interact with one of a disease's ~10-15 curated genes
(disease_biomarkers.py). That misses:
  - agents whose mechanism doesn't route through any curated gene at all
    (combination therapies, lifestyle/procedural interventions, drugs
    hitting a target we didn't think to curate)
  - the ground-truth set of what's actually been trialled for the disease,
    independent of any target hypothesis

Two sources, both disease-name-first:
  - ClinicalTrials.gov API v2: search by condition, extract every
    intervention (drug/biological/device/etc.) across all matching trials.
  - Open Targets: resolve disease name -> EFO ID via their search endpoint,
    then query disease-level knownDrugs (drug + target gene + max phase),
    which can surface target genes outside the curated panel too.

Results are aggregated per unique agent name across both sources so a page
can show "found via N clinical trials, targets GENE per Open Targets" in
one place.
"""
import asyncio
import json
import logging
import re
import urllib.parse
import urllib.request
from collections import defaultdict

import httpx

from .cache import cache_get, cache_set
from .models import DiseaseAgentCandidate, DiseaseAgentDiscoveryOutput, DiseaseAgentTrialEvidence

log = logging.getLogger(__name__)

CT_API = "https://clinicaltrials.gov/api/v2/studies"
OPENTARGETS_URL = "https://api.platform.opentargets.org/api/v4/graphql"

# Filtered out of ClinicalTrials.gov intervention names — not therapeutic
# agents, just trial-arm bookkeeping labels.
_GENERIC_ARM_NAMES = {
    "placebo", "standard of care", "usual care", "no intervention",
    "control", "sham", "sham procedure", "observation",
}


def _norm_agent_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


async def _graphql(client: httpx.AsyncClient, url: str, query: str, variables: dict) -> dict:
    r = await client.post(url, json={"query": query, "variables": variables}, timeout=20)
    r.raise_for_status()
    return r.json()


# ─── ClinicalTrials.gov: disease -> interventions ─────────────────────────────

async def _fetch_trial_interventions(
    disease_name: str,
    client: httpx.AsyncClient,
    max_results: int = 100,
) -> tuple[dict[str, list[DiseaseAgentTrialEvidence]], list[str]]:
    """Returns {agent_name: [trial evidence, ...]}."""
    cache_key = f"ctgov_interventions:{disease_name}:{max_results}"
    cached = cache_get("disease_agents_ctgov", cache_key, ttl_days=14)
    if cached is not None:
        return (
            {k: [DiseaseAgentTrialEvidence(**e) for e in v] for k, v in cached["agents"].items()},
            cached["notes"],
        )

    # Uses urllib, not the shared httpx client: CT.gov's bot-detection returns
    # a bare 403 to httpx's default TLS/HTTP2 fingerprint (verified live —
    # identical headers succeed under urllib and curl, fail under httpx),
    # matching why generate_disease_pages.py's working _fetch_trials also
    # uses urllib. No `fields` projection param either; fetch full studies
    # and parse the nested modules ourselves.
    params = {
        "query.cond": disease_name,
        "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING,COMPLETED",
        "pageSize": str(min(max_results, 200)),
        "format": "json",
    }
    notes: list[str] = []
    agents: dict[str, list[DiseaseAgentTrialEvidence]] = defaultdict(list)
    try:
        url = CT_API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(
            url, headers={"User-Agent": "OSMF-BiomarkerAtlasPipeline/0.1 (research@opensourcemed.info)"}
        )
        body = await asyncio.to_thread(lambda: urllib.request.urlopen(req, timeout=25).read())
        studies = json.loads(body).get("studies", [])
        for s in studies:
            proto = s.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            arms = proto.get("armsInterventionsModule", {})
            nct_id = ident.get("nctId", "")
            title = ident.get("briefTitle", "")
            status = status_mod.get("overallStatus", "")
            phase = ", ".join(design.get("phases", [])) or "N/A"
            for iv in arms.get("interventions", []):
                name = (iv.get("name") or "").strip()
                itype = iv.get("type", "")
                # CT.gov's "OTHER" type is a catch-all that, in practice, is
                # where non-agent cohort/observational labels collect (e.g.
                # "Comorbidity Burden", "Diabetes Status" from poorly
                # structured observational trials) rather than real agents —
                # verified against live data during the asthma/T2D pilot.
                if not name or name.lower() in _GENERIC_ARM_NAMES or itype == "OTHER":
                    continue
                agents[name].append(DiseaseAgentTrialEvidence(
                    nct_id=nct_id, title=title, status=status, phase=phase,
                    intervention_type=iv.get("type", ""),
                ))
        notes.append(f"ClinicalTrials.gov: {len(studies)} trials scanned, {len(agents)} distinct interventions.")
    except Exception as e:
        notes.append(f"ClinicalTrials.gov intervention fetch failed: {e}")
        log.warning("[DiseaseAgents/CTGov] failed for %s: %s", disease_name, e)

    cache_set("disease_agents_ctgov", cache_key, {
        "agents": {k: [e.model_dump() for e in v] for k, v in agents.items()},
        "notes": notes,
    })
    return agents, notes


# ─── Open Targets: disease -> known drugs ─────────────────────────────────────

async def _resolve_disease_efo(disease_name: str, client: httpx.AsyncClient) -> str | None:
    cache_key = f"efo:{disease_name}"
    cached = cache_get("disease_agents_ot_search", cache_key, ttl_days=30)
    if cached is not None:
        return cached.get("efo_id")

    query = """
    query($q: String!) {
      search(queryString: $q, entityNames: ["disease"], page: {index: 0, size: 3}) {
        hits { id name entity }
      }
    }
    """
    efo_id = None
    try:
        data = await _graphql(client, OPENTARGETS_URL, query, {"q": disease_name})
        hits = ((data.get("data") or {}).get("search") or {}).get("hits") or []
        if hits:
            efo_id = hits[0].get("id")
    except Exception as e:
        log.warning("[DiseaseAgents/OT search] failed for %s: %s", disease_name, e)

    cache_set("disease_agents_ot_search", cache_key, {"efo_id": efo_id})
    return efo_id


async def _fetch_opentargets_disease_drugs(
    disease_name: str,
    client: httpx.AsyncClient,
) -> tuple[dict[str, dict], list[str]]:
    """Returns {agent_name: {"target_genes": [...], "max_phase": str, "approval_status": str}}."""
    notes: list[str] = []
    efo_id = await _resolve_disease_efo(disease_name, client)
    if not efo_id:
        notes.append(f"Open Targets: no disease match found for '{disease_name}'.")
        return {}, notes

    cache_key = f"ot_known_drugs:{efo_id}"
    cached = cache_get("disease_agents_ot_drugs", cache_key, ttl_days=14)
    if cached is not None:
        return cached["agents"], cached["notes"]

    # Platform v24+ renamed disease.knownDrugs -> disease.drugAndClinicalCandidates
    # (mirrors the same rename on Target, see stage2_databases.py). Row type
    # ClinicalIndicationFromDisease has no `target` field, so target genes
    # aren't resolvable at the disease level without a second per-drug
    # mechanismsOfAction query — left empty here rather than adding that cost;
    # target attribution still comes from the gene-first pipeline.
    query = """
    query($efoId: String!) {
      disease(efoId: $efoId) {
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
    agents: dict[str, dict] = {}
    try:
        data = await _graphql(client, OPENTARGETS_URL, query, {"efoId": efo_id})
        disease = (data.get("data") or {}).get("disease") or {}
        rows = (disease.get("drugAndClinicalCandidates") or {}).get("rows") or []
        for row in rows:
            drug = row.get("drug") or {}
            name = (drug.get("name") or "").strip()
            if not name:
                continue
            entry = agents.setdefault(name, {"target_genes": [], "max_phase": None, "approval_status": None})
            stage = (row.get("maxClinicalStage") or "").upper()
            if entry["max_phase"] is None:
                entry["max_phase"] = stage or None
            if "APPROVAL" in stage and "PRE" not in stage:
                entry["approval_status"] = "Approved"
        notes.append(f"Open Targets: {len(rows)} known-drug rows -> {len(agents)} distinct agents for EFO {efo_id}.")
    except Exception as e:
        notes.append(f"Open Targets known-drugs fetch failed: {e}")
        log.warning("[DiseaseAgents/OT drugs] failed for %s (%s): %s", disease_name, efo_id, e)

    cache_set("disease_agents_ot_drugs", cache_key, {"agents": agents, "notes": notes})
    return agents, notes


# ─── Orchestrator ──────────────────────────────────────────────────────────────

async def find_agents_for_disease(
    disease_name: str,
    client: httpx.AsyncClient,
    max_trials: int = 100,
) -> DiseaseAgentDiscoveryOutput:
    log.info("[DiseaseAgents] %s", disease_name)
    trial_agents, ct_notes = await _fetch_trial_interventions(disease_name, client, max_trials)
    ot_agents, ot_notes = await _fetch_opentargets_disease_drugs(disease_name, client)

    merged: dict[str, DiseaseAgentCandidate] = {}
    for name, evidence in trial_agents.items():
        key = _norm_agent_key(name)
        if not key:
            continue
        c = merged.setdefault(key, DiseaseAgentCandidate(agent_name=name))
        c.trial_evidence.extend(evidence)
        if "ClinicalTrials.gov" not in c.sources:
            c.sources.append("ClinicalTrials.gov")

    for name, info in ot_agents.items():
        key = _norm_agent_key(name)
        if not key:
            continue
        c = merged.setdefault(key, DiseaseAgentCandidate(agent_name=name))
        for gene in info["target_genes"]:
            if gene not in c.target_genes:
                c.target_genes.append(gene)
        if info["max_phase"] and not c.max_phase:
            c.max_phase = info["max_phase"]
        if info["approval_status"]:
            c.approval_status = info["approval_status"]
        if "Open Targets" not in c.sources:
            c.sources.append("Open Targets")

    candidates = sorted(
        merged.values(),
        key=lambda c: (len(c.trial_evidence) + len(c.target_genes)),
        reverse=True,
    )

    return DiseaseAgentDiscoveryOutput(
        disease=disease_name,
        candidates=candidates,
        coverage_notes=ct_notes + ot_notes,
    )
