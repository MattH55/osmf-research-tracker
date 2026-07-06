"""Orchestrate Path A (clinical) + Path B (mechanistic) natural product discovery."""
from __future__ import annotations

import asyncio
import logging
import re

import aiohttp

from ...models import Alteration, DiseaseIdentifiers, NaturalProduct, NPType, SafetyTier
from ...options import PipelineOptions
from . import (
    chembl_np,
    clinicaltrials_np,
    examine_np,
    greenmedinfo_np,
    llm_extract,
    normalize_np,
    pubchem_np,
    pubmed_np,
    score_np,
)

log = logging.getLogger(__name__)


async def _empty_np_list() -> list[NaturalProduct]:
    return []


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


def _np_type(value: str | None) -> NPType:
    if not value:
        return NPType.nutraceutical
    try:
        return NPType(value)
    except ValueError:
        return NPType.nutraceutical


def _safety_tier(value: str | None) -> SafetyTier:
    if not value:
        return SafetyTier.unknown
    try:
        return SafetyTier(value)
    except ValueError:
        return SafetyTier.unknown


def _build_np_from_clinical(norm: dict, record: dict) -> NaturalProduct:
    study_type = record.get("study_type", "other")
    outcome = record.get("outcome", "unclear")
    positive = outcome == "positive"

    meta_count = rct_count = sr_count = 0
    if study_type == "meta_analysis" and positive:
        meta_count = 1
    elif study_type == "rct" and positive:
        rct_count = 1
    elif study_type == "systematic_review":
        sr_count = 1
    elif study_type == "clinical_trial" and positive:
        rct_count = 1

    ct_count = record.get("trial_count", 0)
    sources = ["PubMed"] if record.get("pmid") or record.get("outcome_note") else []
    if ct_count:
        sources.append("ClinicalTrials.gov")

    canonical_id = norm.get("pubchem_cid") or _slug(norm["canonical_name"])
    return NaturalProduct(
        canonical_id=str(canonical_id),
        name=norm["canonical_name"],
        common_names=[record.get("np_name", norm["canonical_name"])],
        scientific_name=record.get("np_scientific") or norm.get("source_plant"),
        np_type=_np_type(norm.get("np_type") or record.get("np_type")),
        meta_analysis_count=meta_count,
        rct_count=rct_count,
        systematic_review_count=sr_count,
        ct_trial_count=ct_count,
        key_findings=record.get("outcome_note") or record.get("key_findings"),
        mechanism=record.get("mechanism"),
        safety_tier=_safety_tier(norm.get("safety_tier")),
        herb_drug_interactions=list(norm.get("known_interactions") or []),
        pubchem_cid=norm.get("pubchem_cid"),
        lotus_wikidata_id=norm.get("lotus_wikidata_id"),
        sources=sources,
    )


def _build_np_from_reference(norm: dict, record: dict) -> NaturalProduct:
    source = record.get("source", "")
    sources = [source] if source else []
    link = record.get("url")
    source_links = {source: link} if source and link else {}
    sr_count = 1 if source == "Examine.com" else 0

    canonical_id = norm.get("pubchem_cid") or _slug(norm["canonical_name"])
    return NaturalProduct(
        canonical_id=str(canonical_id),
        name=norm["canonical_name"],
        common_names=[record.get("name", norm["canonical_name"])],
        np_type=_np_type(norm.get("np_type")),
        systematic_review_count=sr_count,
        key_findings=record.get("key_findings"),
        safety_tier=_safety_tier(norm.get("safety_tier")),
        herb_drug_interactions=list(norm.get("known_interactions") or []),
        pubchem_cid=norm.get("pubchem_cid"),
        lotus_wikidata_id=norm.get("lotus_wikidata_id"),
        sources=sources,
        source_links=source_links,
    )


def _build_np_from_chembl(norm: dict, record: dict) -> NaturalProduct:
    targets = record.get("targets_hit", [])
    activities = record.get("activities", [])
    mechanism = None
    if activities:
        best = min(
            (a for a in activities if a.get("standard_value")),
            key=lambda a: float(a.get("standard_value") or 99999),
            default=None,
        )
        if best:
            mechanism = f"{best.get('standard_type', 'Activity')} {best.get('standard_value')} {best.get('standard_units', '')}".strip()

    canonical_id = norm.get("pubchem_cid") or record.get("chembl_id") or _slug(norm["canonical_name"])
    return NaturalProduct(
        canonical_id=str(canonical_id),
        name=norm["canonical_name"],
        common_names=[record.get("name", "")],
        np_type=_np_type(norm.get("np_type")),
        scientific_name=norm.get("source_plant"),
        linked_alteration_ids=targets,
        target_names=targets,
        mechanism=mechanism,
        chembl_ids=[record.get("chembl_id", "")],
        safety_tier=_safety_tier(norm.get("safety_tier")),
        herb_drug_interactions=list(norm.get("known_interactions") or []),
        pubchem_cid=norm.get("pubchem_cid"),
        lotus_wikidata_id=norm.get("lotus_wikidata_id"),
        sources=["ChEMBL"],
    )


async def _enrich_pubchem(nps: list[NaturalProduct], session: aiohttp.ClientSession) -> list[NaturalProduct]:
    out: list[NaturalProduct] = []
    for np in nps:
        if not np.pubchem_cid:
            out.append(np)
            continue
        count = await pubchem_np.pubchem_get_bioassay_count(np.pubchem_cid, session)
        out.append(np.model_copy(update={"pubchem_bioassay_count": count}))
    return out


async def _get_clinical_nps(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    synonym_index: dict,
    options: PipelineOptions,
) -> list[NaturalProduct]:
    pubmed_records, ct_records = await asyncio.gather(
        pubmed_np.search_pubmed_np(
            identifiers, session, max_results=options.max_pubmed_np_results, options=options
        ),
        clinicaltrials_np.get_ct_supplement_interventions(identifiers, session),
    )

    extracted = await llm_extract.extract_np_from_abstracts(
        pubmed_records, identifiers.name, options
    )

    all_np_names: list[tuple[str, dict]] = [
        (r["np_name"], r) for r in extracted if r.get("np_name")
    ]
    all_np_names.extend((r["name"], r) for r in ct_records if r.get("name"))

    nps: list[NaturalProduct] = []
    for raw_name, record in all_np_names:
        norm = await normalize_np.normalize_np_name(raw_name, synonym_index, session)
        if not norm.get("resolved"):
            log.debug("[NP] unresolved name: %s", raw_name)
            continue
        nps.append(_build_np_from_clinical(norm, record))
    return nps


async def _get_reference_nps(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    synonym_index: dict,
    options: PipelineOptions,
    *,
    disease_slug: str = "",
) -> tuple[list[NaturalProduct], dict[str, str]]:
    lookup_links: dict[str, str] = {}
    tasks = []
    labels: list[str] = []

    if not options.skip_greenmedinfo:
        tasks.append(greenmedinfo_np.search_greenmedinfo_substances(identifiers, session, options=options))
        labels.append("gmi")
    if not options.skip_examine:
        tasks.append(
            examine_np.search_examine_supplements(
                identifiers, session, disease_slug=disease_slug, options=options
            )
        )
        labels.append("examine")

    if not tasks:
        return [], lookup_links

    results = await asyncio.gather(*tasks)
    raw_records: list[dict] = []

    for label, result in zip(labels, results):
        if label == "gmi":
            records, gmi_url = result
            lookup_links["GreenMedInfo"] = gmi_url
            raw_records.extend(records)
        else:
            records, examine_url = result
            if examine_url:
                lookup_links["Examine.com"] = examine_url
            elif not options.skip_examine:
                lookup_links["Examine.com"] = examine_np.examine_search_url(identifiers.name)
            raw_records.extend(records)

    nps: list[NaturalProduct] = []
    for record in raw_records:
        raw_name = record.get("name", "")
        if not raw_name:
            continue
        norm = await normalize_np.normalize_np_name(
            raw_name, synonym_index, session, resolve_external=False
        )
        nps.append(_build_np_from_reference(norm, record))
    return nps, lookup_links


async def _get_mechanistic_nps(
    alterations: list[Alteration],
    session: aiohttp.ClientSession,
    synonym_index: dict,
    options: PipelineOptions,
) -> list[NaturalProduct]:
    raw = await chembl_np.get_chembl_np_batch(
        alterations, session, max_targets=options.max_genes_for_drugs
    )
    nps: list[NaturalProduct] = []
    for record in raw:
        name = record.get("name", "")
        if not name:
            continue
        norm = await normalize_np.normalize_np_name(name, synonym_index, session)
        if not norm.get("resolved"):
            norm = {
                "canonical_name": name,
                "canonical_key": _slug(name),
                "pubchem_cid": None,
                "np_type": "food_compound",
                "resolved": True,
            }
        nps.append(_build_np_from_chembl(norm, record))
    return nps


async def build_natural_products(
    identifiers: DiseaseIdentifiers,
    alterations: list[Alteration],
    session: aiohttp.ClientSession,
    options: PipelineOptions,
    *,
    disease_slug: str = "",
    extra_meta: dict | None = None,
) -> list[NaturalProduct]:
    if options.skip_natural_products or not options.includes(7):
        return []

    synonym_index = normalize_np.load_np_synonyms()
    safety_map = score_np.load_safety_map()

    clinical_coro = (
        _get_clinical_nps(identifiers, session, synonym_index, options)
        if not options.skip_clinical_np
        else _empty_np_list()
    )
    mechanistic_coro = (
        _get_mechanistic_nps(alterations, session, synonym_index, options)
        if not options.skip_mechanistic_np
        else _empty_np_list()
    )
    reference_coro = _get_reference_nps(
        identifiers, session, synonym_index, options, disease_slug=disease_slug
    )

    np_clinical, np_mechanistic, ref_result = await asyncio.gather(
        clinical_coro,
        mechanistic_coro,
        reference_coro,
    )
    np_reference, lookup_links = ref_result
    if extra_meta is not None and lookup_links:
        extra_meta["np_lookup_links"] = lookup_links

    raw_nps = np_clinical + np_mechanistic + np_reference
    if not raw_nps:
        log.info("[NP] No natural products found for '%s'", identifiers.name)
        return []

    nps = score_np.deduplicate_nps(raw_nps)
    nps = score_np.apply_safety(nps, safety_map)
    if not options.skip_pubchem_enrich:
        nps = await _enrich_pubchem(nps, session)

    for i, np in enumerate(nps):
        tier = score_np.assign_np_evidence_tier(np)
        nps[i] = np.model_copy(update={
            "np_evidence_tier": tier,
            "score": score_np.score_np(np.model_copy(update={"np_evidence_tier": tier})),
        })
    nps.sort(key=lambda x: x.score, reverse=True)

    log.info("[NP] %d natural products for '%s'", len(nps), identifiers.name)
    return nps