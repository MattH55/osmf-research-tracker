"""Clinical trial and literature evidence for natural products (same shape as drug evidence)."""
from __future__ import annotations

import asyncio
import logging
import re

import aiohttp

from ...adapters.clinical_evidence import gather_drug_evidence, resolve_mesh_descriptor
from ...models import AgentClinicalEvidence, DiseaseIdentifiers, LiteratureRecord, NaturalProduct, Therapeutic
from ...options import PipelineOptions

log = logging.getLogger(__name__)

_PHASE_RANK = {
    "PHASE4": 4,
    "PHASE 4": 4,
    "PHASE3": 3,
    "PHASE 3": 3,
    "PHASE2": 2,
    "PHASE 2": 2,
    "PHASE1": 1,
    "PHASE 1": 1,
}


def _max_phase_from_evidence(evidence: AgentClinicalEvidence | None) -> int:
    if not evidence:
        return 0
    best = 0
    for trial in evidence.clinical_trials:
        phase = (trial.phase or "").upper()
        for key, rank in _PHASE_RANK.items():
            if key in phase:
                best = max(best, rank)
    return best


def _therapeutic_shim(np: NaturalProduct) -> Therapeutic:
    return Therapeutic(
        canonical_id=np.canonical_id,
        name=np.name,
        drug_type=np.np_type.value if hasattr(np.np_type, "value") else str(np.np_type),
        mechanism=np.mechanism,
        source_type="natural_agent",
        sources=np.sources,
        chembl_id=np.chembl_ids[0] if np.chembl_ids else None,
    )


def _merge_reference_literature(
    evidence: AgentClinicalEvidence,
    np: NaturalProduct,
    *,
    gmi_articles: list[dict] | None = None,
) -> AgentClinicalEvidence:
    literature = list(evidence.literature)
    seen_titles = {lit.title.lower() for lit in literature}

    for article in gmi_articles or []:
        title = (article.get("title") or "").strip()
        url = article.get("url") or ""
        if not title or title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())
        literature.append(
            LiteratureRecord(
                title=title,
                publication_type="reference",
                publication_type_label="GreenMedInfo article",
                url=url or "https://www.greenmedinfo.com",
            )
        )

    search_links = dict(evidence.search_links)
    for src, url in np.source_links.items():
        key = re.sub(r"[^a-z0-9]+", "_", src.lower()).strip("_")
        if key and url:
            search_links[key] = url

    return evidence.model_copy(update={
        "literature": literature[:30],
        "search_links": search_links,
    })


async def gather_np_evidence(
    np: NaturalProduct,
    identifiers: DiseaseIdentifiers,
    mesh_term: str | None,
    session: aiohttp.ClientSession,
    options: PipelineOptions,
    *,
    gmi_articles: list[dict] | None = None,
) -> AgentClinicalEvidence:
    drug = _therapeutic_shim(np)
    evidence = await gather_drug_evidence(drug, identifiers, mesh_term, session, options)
    return _merge_reference_literature(evidence, np, gmi_articles=gmi_articles)


async def enrich_natural_products_evidence(
    nps: list[NaturalProduct],
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    options: PipelineOptions,
    *,
    gmi_articles_by_name: dict[str, list[dict]] | None = None,
) -> dict[str, AgentClinicalEvidence]:
    if options.skip_np_evidence or not nps:
        return {}

    mesh_term = await resolve_mesh_descriptor(identifiers.mesh_id or "", session)
    cap = min(len(nps), options.max_np_evidence)
    candidates = nps[:cap]
    evidence_map: dict[str, AgentClinicalEvidence] = {}
    sem = asyncio.Semaphore(2)

    async def _one(np: NaturalProduct) -> None:
        articles = None
        if gmi_articles_by_name:
            for key in (np.name.lower(), *(c.lower() for c in np.common_names)):
                if key in gmi_articles_by_name:
                    articles = gmi_articles_by_name[key]
                    break
        async with sem:
            try:
                ev = await gather_np_evidence(
                    np, identifiers, mesh_term, session, options, gmi_articles=articles
                )
                evidence_map[np.canonical_id] = ev
                log.info(
                    "[NP Evidence] %s + %s → %d trials, %d literature",
                    identifiers.name,
                    np.name,
                    len(ev.clinical_trials),
                    len(ev.literature),
                )
            except Exception as e:
                log.warning("[NP Evidence] failed for %s: %s", np.name, e)

    await asyncio.gather(*[_one(np) for np in candidates])
    return evidence_map