"""Phase 6 — Clinical trial registry + published literature evidence per agent."""
from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import quote_plus

import aiohttp

from ..cache import cache_get, cache_set
from ..clinicaltrials_client import get_clinicaltrials
from ..config import PUBMED_URL, get_ncbi_api_key
from ..http_util import get_json
from ..models import (
    AgentClinicalEvidence,
    ClinicalTrialRecord,
    DiseaseIdentifiers,
    DiseasePageData,
    LiteratureRecord,
    Therapeutic,
)
from ..options import PipelineOptions

log = logging.getLogger(__name__)

PUB_TYPE_LABELS = {
    "cochrane_review": "Cochrane review",
    "meta_analysis": "Meta-analysis",
    "systematic_review": "Systematic review",
    "clinical_trial": "Clinical trial publication",
    "rct": "Randomized controlled trial",
    "observational": "Observational study",
}

LITERATURE_QUERIES: list[tuple[str, str]] = [
    (
        "cochrane_review",
        "{drug} AND {condition} AND "
        "(Cochrane Database Syst Rev[Journal] OR cochrane[Title/Abstract])",
    ),
    (
        "meta_analysis",
        '{drug} AND {condition} AND "meta-analysis"[Publication Type]',
    ),
    (
        "systematic_review",
        '{drug} AND {condition} AND "systematic review"[Publication Type]',
    ),
    (
        "clinical_trial",
        '{drug} AND {condition} AND "clinical trial"[Publication Type]',
    ),
    (
        "rct",
        '{drug} AND {condition} AND "randomized controlled trial"[Publication Type]',
    ),
]


def _pubmed_params(term: str, retmax: int) -> dict[str, str]:
    params: dict[str, str] = {
        "db": "pubmed",
        "term": term,
        "retmode": "json",
        "retmax": str(retmax),
    }
    api_key = get_ncbi_api_key()
    if api_key:
        params["api_key"] = api_key
    return params


async def resolve_mesh_descriptor(mesh_id: str, session: aiohttp.ClientSession) -> str | None:
    if not mesh_id:
        return None
    ck = f"mesh_desc:{mesh_id}"
    cached = cache_get("evidence", ck)
    if cached is not None:
        return cached.get("term")

    try:
        es = await get_json(
            session,
            f"{PUBMED_URL}/esearch.fcgi",
            params={"db": "mesh", "term": mesh_id, "retmode": "json", "retmax": "1"},
        )
        uid = (es or {}).get("esearchresult", {}).get("idlist", [None])[0]
        if not uid:
            return None
        sm = await get_json(
            session,
            f"{PUBMED_URL}/esummary.fcgi",
            params={"db": "mesh", "id": uid, "retmode": "json"},
        )
        terms = (sm or {}).get("result", {}).get(uid, {}).get("ds_meshterms", [])
        term = terms[0] if terms else None
        if term:
            cache_set("evidence", ck, {"term": term})
        return term
    except Exception as e:
        log.debug("MeSH descriptor lookup failed for %s: %s", mesh_id, e)
        return None


def _condition_clause(mesh_term: str | None, identifiers: DiseaseIdentifiers) -> str:
    if mesh_term:
        return f'"{mesh_term}"[MeSH]'
    if identifiers.mesh_id:
        return f"{identifiers.mesh_id}[MeSH]"
    return f'"{identifiers.name}"[Title/Abstract]'


def _drug_clause(drug_name: str) -> str:
    clean = drug_name.replace('"', "").strip()
    return f'"{clean}"[Title/Abstract]'


async def _pubmed_count(session: aiohttp.ClientSession, term: str) -> int:
    try:
        data = await get_json(session, f"{PUBMED_URL}/esearch.fcgi", params=_pubmed_params(term, 0))
        if not data:
            return 0
        return int(data.get("esearchresult", {}).get("count", 0))
    except Exception:
        return 0


async def _pubmed_hits(
    session: aiohttp.ClientSession,
    term: str,
    *,
    limit: int,
) -> tuple[list[str], int]:
    try:
        data = await get_json(session, f"{PUBMED_URL}/esearch.fcgi", params=_pubmed_params(term, limit))
        if not data:
            return [], 0
        result = data.get("esearchresult", {})
        return result.get("idlist", []) or [], int(result.get("count", 0))
    except Exception as e:
        log.debug("PubMed search failed: %s", e)
        return [], 0


async def _pubmed_summaries(
    session: aiohttp.ClientSession,
    pmids: list[str],
) -> list[dict]:
    if not pmids:
        return []
    try:
        data = await get_json(
            session,
            f"{PUBMED_URL}/esummary.fcgi",
            params={
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
                **({"api_key": get_ncbi_api_key()} if get_ncbi_api_key() else {}),
            },
        )
        result = (data or {}).get("result", {})
        out: list[dict] = []
        for pmid in pmids:
            rec = result.get(pmid)
            if not rec or rec.get("error"):
                continue
            authors = rec.get("authors", [])
            author_str = ", ".join(a.get("name", "") for a in authors[:3])
            if len(authors) > 3:
                author_str += " et al."
            pubdate = rec.get("pubdate", "")
            year_match = re.search(r"(19|20)\d{2}", pubdate)
            out.append(
                {
                    "pmid": pmid,
                    "title": rec.get("title", "").rstrip("."),
                    "journal": rec.get("fulljournalname") or rec.get("source"),
                    "year": int(year_match.group()) if year_match else None,
                    "authors": author_str or None,
                }
            )
        return out
    except Exception as e:
        log.debug("PubMed summary failed: %s", e)
        return []


async def search_clinical_trials(
    identifiers: DiseaseIdentifiers,
    drug_name: str,
    session: aiohttp.ClientSession,
    *,
    limit: int = 8,
    use_cache: bool = True,
) -> tuple[list[ClinicalTrialRecord], int]:
    ck = f"ct:v2:{identifiers.name.lower()}:{drug_name.lower()}"
    if use_cache:
        cached = cache_get("evidence", ck)
    else:
        cached = None
    if cached is not None:
        trials = [ClinicalTrialRecord(**t) for t in cached.get("trials", [])]
        return trials, int(cached.get("total", len(trials)))

    params = {
        "query.cond": identifiers.name,
        "query.intr": drug_name,
        "pageSize": str(limit),
        "fields": "NCTId,BriefTitle,OverallStatus,Phase,EnrollmentCount,StartDate",
        "format": "json",
    }
    trials: list[ClinicalTrialRecord] = []
    total = 0
    try:
        data = await get_clinicaltrials(session, params)
        if not data:
            return [], 0
        studies = data.get("studies", [])
        total = int(data.get("totalCount", len(studies)) or len(studies))
        for study in studies:
            ps = study.get("protocolSection", {})
            ident = ps.get("identificationModule", {})
            status = ps.get("statusModule", {})
            design = ps.get("designModule", {})
            nct = ident.get("nctId", "")
            title = ident.get("briefTitle") or ident.get("officialTitle") or "Untitled study"
            phases = design.get("phases") or []
            phase = ", ".join(phases) if phases else None
            start = status.get("startDateStruct", {}) or {}
            year = None
            if start.get("date"):
                ym = re.search(r"(19|20)\d{2}", start["date"])
                year = int(ym.group()) if ym else None
            enrollment = design.get("enrollmentInfo", {}).get("count")
            trials.append(
                ClinicalTrialRecord(
                    nct_id=nct or None,
                    title=title,
                    status=status.get("overallStatus"),
                    phase=phase,
                    enrollment=int(enrollment) if enrollment else None,
                    source="ClinicalTrials.gov",
                    url=f"https://clinicaltrials.gov/study/{nct}" if nct else "",
                    year=year,
                )
            )
        if use_cache:
            cache_set("evidence", ck, {"trials": [t.model_dump() for t in trials], "total": total})
    except Exception as e:
        log.warning("[ClinicalTrials] drug evidence failed for %s + %s: %s", identifiers.name, drug_name, e)

    return trials, total


def _search_links(
    drug_name: str,
    identifiers: DiseaseIdentifiers,
    mesh_term: str | None,
) -> dict[str, str]:
    cond = mesh_term or identifiers.name
    drug_q = quote_plus(drug_name)
    cond_q = quote_plus(cond)
    return {
        "clinicaltrials_gov": (
            f"https://clinicaltrials.gov/search?cond={cond_q}&intr={drug_q}"
        ),
        "pubmed": (
            f"https://pubmed.ncbi.nlm.nih.gov/?term={quote_plus(drug_name)}+AND+"
            f"{quote_plus(f'{cond}[MeSH]' if mesh_term else identifiers.name)}"
        ),
        "cochrane": (
            f"https://www.cochranelibrary.com/search?p_p_id=scolarissearchresultsportlet_WAR"
            f"scolarissearchresults&query={drug_q}+{cond_q}"
        ),
    }


async def gather_drug_evidence(
    drug: Therapeutic,
    identifiers: DiseaseIdentifiers,
    mesh_term: str | None,
    session: aiohttp.ClientSession,
    options: PipelineOptions,
) -> AgentClinicalEvidence:
    ck = f"drug_ev:v2:{identifiers.name.lower()}:{drug.canonical_id}"
    if options.use_cache:
        cached = cache_get("evidence", ck)
        if cached is not None:
            return AgentClinicalEvidence(**cached)

    condition = _condition_clause(mesh_term, identifiers)
    drug_q = _drug_clause(drug.name)

    trials, trial_total = await search_clinical_trials(
        identifiers,
        drug.name,
        session,
        limit=options.max_trials_per_drug,
        use_cache=options.use_cache,
    )

    literature: list[LiteratureRecord] = []
    counts: dict[str, int] = {"trials_registry": trial_total, "total_publications": 0}

    seen_pmids: set[str] = set()
    for pub_type, template in LITERATURE_QUERIES:
        term = template.format(drug=drug_q, condition=condition)
        pmids, total = await _pubmed_hits(session, term, limit=options.max_literature_per_type)
        counts[pub_type] = total
        counts["total_publications"] = max(counts.get("total_publications", 0), total)
        new_pmids = [p for p in pmids if p not in seen_pmids]
        seen_pmids.update(new_pmids)
        for rec in await _pubmed_summaries(session, new_pmids):
            literature.append(
                LiteratureRecord(
                    pmid=rec["pmid"],
                    title=rec["title"],
                    journal=rec.get("journal"),
                    year=rec.get("year"),
                    publication_type=pub_type,
                    publication_type_label=PUB_TYPE_LABELS.get(pub_type, pub_type),
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{rec['pmid']}/",
                    authors=rec.get("authors"),
                )
            )
        await asyncio.sleep(0.12)

    assoc_term = f"{drug_q} AND {condition}"
    counts["association_total"] = await _pubmed_count(session, assoc_term)

    evidence = AgentClinicalEvidence(
        drug_canonical_id=drug.canonical_id,
        drug_name=drug.name,
        clinical_trials=trials,
        literature=literature,
        counts=counts,
        search_links=_search_links(drug.name, identifiers, mesh_term),
    )
    if options.use_cache:
        cache_set("evidence", ck, evidence.model_dump())
    return evidence


async def enrich_page(
    page: DiseasePageData,
    session: aiohttp.ClientSession,
    options: PipelineOptions,
) -> dict[str, AgentClinicalEvidence]:
    if options.skip_evidence or not options.includes(6):
        return {}

    mesh_term = await resolve_mesh_descriptor(page.identifiers.mesh_id or "", session)
    if mesh_term:
        options.note_source("PubMed MeSH")
    options.note_source("ClinicalTrials.gov")
    options.note_source("PubMed Literature")

    natural = [d for d in page.therapeutics_natural if d.source_type == "natural_agent"]
    pharma = [d for d in page.therapeutics_merged if d.source_type != "natural_agent"]
    natural_cap = min(len(natural), max(8, options.max_evidence_drugs // 3))
    pharma_cap = options.max_evidence_drugs - natural_cap
    candidates = natural[:natural_cap] + pharma[:pharma_cap]
    evidence_map: dict[str, AgentClinicalEvidence] = {}

    sem = asyncio.Semaphore(2)

    async def _one(drug: Therapeutic) -> None:
        async with sem:
            try:
                ev = await gather_drug_evidence(drug, page.identifiers, mesh_term, session, options)
                evidence_map[drug.canonical_id] = ev
                log.info(
                    "[Evidence] %s + %s → %d trials, %d literature hits",
                    page.identifiers.name,
                    drug.name,
                    len(ev.clinical_trials),
                    len(ev.literature),
                )
            except Exception as e:
                log.warning("[Evidence] failed for %s: %s", drug.name, e)

    await asyncio.gather(*[_one(d) for d in candidates])
    return evidence_map