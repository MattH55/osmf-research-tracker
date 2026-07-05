"""Module 3 — Clinical / phenotypic alterations (HPO, Orphanet, trials, LOINC)."""
from __future__ import annotations

import logging
import re
from collections import Counter

import aiohttp

from ..cache import cache_get, cache_set
from ..clinicaltrials_client import paginate_clinicaltrials
from ..config import HPO_URL, MONARCH_API, ORPHADATA_PHENOTYPES
from ..http_util import get_json
from ..models import Alteration, AlterationType, DiseaseIdentifiers, EvidenceTier
from ..options import PipelineOptions

log = logging.getLogger(__name__)

HPO_TYPE_MAP: dict[str, tuple[str, str]] = {
    "HP:0003074": ("B", "lab_value"),
    "HP:0002149": ("B", "lab_value"),
    "HP:0003355": ("B", "lab_value"),
    "HP:0001948": ("B", "lab_value"),
    "HP:0004912": ("B", "lab_value"),
    "HP:0001410": ("D", "pathology"),
    "HP:0001395": ("D", "pathology"),
    "HP:0002621": ("D", "pathology"),
    "HP:0003011": ("E", "functional"),
    "HP:0001270": ("E", "functional"),
    "HP:0002167": ("E", "functional"),
}

COMMON_LOINC: dict[str, str] = {
    "hba1c": "4548-4",
    "fasting glucose": "1558-6",
    "egfr": "62238-1",
    "creatinine": "2160-0",
    "crp": "1988-5",
    "tsh": "3016-3",
    "ldl": "2089-1",
    "glucose": "2345-7",
    "insulin": "2484-4",
}

SCALE_ACRONYMS = (
    "das28", "haq", "sf-36", "eq-5d", "phq-9", "gad-7", "madrs", "panss",
    "mmse", "moca", "edss", "fvc", "fev1",
)

_FREQ_MAP = {
    "obligate": ("obligate", "99-80%"),
    "very frequent": ("very_frequent", "99-80%"),
    "very frequent (99-80%)": ("very_frequent", "99-80%"),
    "frequent": ("frequent", "79-30%"),
    "frequent (79-30%)": ("frequent", "79-30%"),
    "occasional": ("occasional", "29-5%"),
    "occasional (29-5%)": ("occasional", "29-5%"),
}


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


def classify_hpo_term(hpo_id: str, hpo_name: str) -> tuple[AlterationType, str]:
    if hpo_id in HPO_TYPE_MAP:
        t, s = HPO_TYPE_MAP[hpo_id]
        return AlterationType(t), s

    low = hpo_name.lower()
    if any(k in low for k in ("scale", "score", "index", "questionnaire", "prom")):
        if any(k in low for k in ("walk", "grip", "cognit", "strength", "spirometry")):
            return AlterationType.E, "functional_test"
        return AlterationType.C, "scale"
    if any(k in low for k in ("concentration", "level", "elevated", "reduced", "serum", "plasma", "urine", "glycemia")):
        direction = "elevated" if "hyper" in low or "elevated" in low or "increased" in low else (
            "reduced" if "hypo" in low or "reduced" in low or "decreased" in low else "abnormal"
        )
        return AlterationType.B, "lab_value"
    if any(k in low for k in ("fibrosis", "atrophy", "stenosis", "lesion", "mass", "tumor", "necrosis")):
        return AlterationType.D, "pathology"
    if any(k in low for k in ("impaired", "weakness", "disability", "fatigue", "limited", "reduced capacity")):
        return AlterationType.E, "functional_test"
    return AlterationType.D, "pathology"


def _parse_frequency(freq: dict | str | None) -> tuple[str | None, str | None]:
    if not freq:
        return None, None
    label = freq.get("label", freq) if isinstance(freq, dict) else str(freq)
    mapped = _FREQ_MAP.get(label.lower().strip())
    return mapped if mapped else (None, None)


async def get_hpo_phenotypes(
    omim_id: str | None,
    session: aiohttp.ClientSession,
    *,
    mondo_id: str | None = None,
) -> list[Alteration]:
    if not omim_id and not mondo_id:
        log.warning("HPO skipped: no OMIM or MONDO ID")
        return []

    ck = f"hpo_omim:{omim_id or mondo_id}"
    cached = cache_get("clinical", ck)
    if cached is not None:
        return [Alteration(**a) for a in cached]

    alterations: list[Alteration] = []
    try:
        data = None
        if omim_id:
            data = await get_json(session, f"{HPO_URL}/hpo/disease/OMIM:{omim_id}")
        if data:
            for assoc in data.get("associations", []):
                hp_id = assoc.get("hpo_id", "")
                hp_name = assoc.get("hpo_name", hp_id)
                if not hp_id:
                    continue
                alt_type, subtype = classify_hpo_term(hp_id, hp_name)
                freq_label, freq_pct = _parse_frequency(assoc.get("frequency"))
                direction = None
                if alt_type == AlterationType.B:
                    low = hp_name.lower()
                    if "hyper" in low or "elevated" in low:
                        direction = "elevated"
                    elif "hypo" in low or "reduced" in low:
                        direction = "reduced"
                alterations.append(
                    Alteration(
                        canonical_id=hp_id,
                        name=hp_name,
                        alteration_type=alt_type,
                        subtype=subtype,
                        direction=direction,
                        frequency_label=freq_label,
                        frequency_pct=freq_pct,
                        sources=["HPO"],
                        source_ids={"HPO": hp_id},
                        evidence_tier=EvidenceTier.B,
                    )
                )
            if alterations:
                cache_set("clinical", ck, [a.model_dump() for a in alterations])
                log.info("[HPO] OMIM:%s → %d phenotypes", omim_id, len(alterations))
                return alterations

        # Fallback: Monarch association API when HPO JAX endpoint unavailable
        subjects = []
        if mondo_id:
            subjects.append(mondo_id)
        if omim_id:
            subjects.append(f"OMIM:{omim_id}")
        monarch_items: list[dict] = []
        for subject in subjects:
            monarch = await get_json(
                session,
                f"{MONARCH_API}/association",
                params={"subject": subject, "predicate": "biolink:has_phenotype", "limit": 100},
            )
            monarch_items.extend((monarch or {}).get("items", []))
        seen_hp: set[str] = set()
        for item in monarch_items:
            obj = item.get("object", "")
            if not obj.startswith("HP:") or obj in seen_hp:
                continue
            seen_hp.add(obj)
            hp_name = item.get("object_label") or obj
            alt_type, subtype = classify_hpo_term(obj, hp_name)
            alterations.append(
                Alteration(
                    canonical_id=obj,
                    name=hp_name,
                    alteration_type=alt_type,
                    subtype=subtype,
                    sources=["HPO", "Monarch"],
                    source_ids={"HPO": obj},
                    evidence_tier=EvidenceTier.B,
                )
            )
        if alterations:
            cache_set("clinical", ck, [a.model_dump() for a in alterations])
    except Exception as e:
        log.error("HPO error for OMIM:%s: %s", omim_id, e)

    log.info("[HPO] OMIM:%s → %d phenotypes", omim_id, len(alterations))
    return alterations


async def get_orphanet_phenotypes(
    orpha_id: str | None, session: aiohttp.ClientSession
) -> list[Alteration]:
    if not orpha_id:
        return []

    orpha_num = orpha_id.replace("ORPHA:", "")
    ck = f"orphanet:{orpha_num}"
    cached = cache_get("clinical", ck)
    if cached is not None:
        return [Alteration(**a) for a in cached]

    alterations: list[Alteration] = []
    try:
        data = await get_json(session, f"{ORPHADATA_PHENOTYPES}/{orpha_num}")
        if not data:
            return []
        pheno_list = (
            data.get("results", {})
            .get("Phenotypes", {})
            .get("HPO phenotypes associated with the disease", [])
        )
        for pheno in pheno_list:
            hp_id = pheno.get("HPOId", "")
            if not hp_id:
                continue
            hp_name = pheno.get("HPOTerm", hp_id)
            alt_type, subtype = classify_hpo_term(hp_id, hp_name)
            freq_label, freq_pct = _parse_frequency(pheno.get("HPOFrequency"))
            alterations.append(
                Alteration(
                    canonical_id=hp_id,
                    name=hp_name,
                    alteration_type=alt_type,
                    subtype=subtype,
                    frequency_label=freq_label,
                    frequency_pct=freq_pct,
                    sources=["Orphanet"],
                    source_ids={"HPO": hp_id, "Orphanet": orpha_id},
                    evidence_tier=EvidenceTier.B,
                )
            )
        if alterations:
            cache_set("clinical", ck, [a.model_dump() for a in alterations])
    except Exception as e:
        log.warning("[Orphanet] failed for %s: %s", orpha_id, e)

    return alterations


def _normalize_measure(measure: str) -> str:
    low = re.sub(r"\s+", " ", measure.lower()).strip()
    low = re.sub(r"\([^)]*\)", "", low)
    low = re.sub(r"\s+", " ", low).strip(" -")
    for token in ("fev1", "pef", "fvc", "acr", "exacerbation", "hospitalization"):
        if token in low:
            return token
    return low


def _classify_endpoint(measure: str) -> tuple[AlterationType, str]:
    low = measure.lower()
    if any(acr in low for acr in SCALE_ACRONYMS):
        return AlterationType.C, "scale"
    if any(k in low for k in ("pain", "fatigue", "quality of life", "depression", "anxiety")):
        return AlterationType.C, "scale"
    if any(k in low for k in ("walk", "strength", "grip", "spirometry", "6mwt", "treadmill", "exercise")):
        return AlterationType.E, "functional_test"
    if any(k in low for k in ("scale", "score", "index", "questionnaire")):
        return AlterationType.C, "scale"
    return AlterationType.B, "lab_value"


async def get_ct_endpoints(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    *,
    page_size: int = 50,
    use_cache: bool = True,
) -> list[Alteration]:
    ck = f"ct_endpoints:v3:{identifiers.name.lower()}"
    if use_cache:
        cached = cache_get("clinical", ck)
        if cached is not None:
            return [Alteration(**a) for a in cached]

    per_page = 20
    max_pages = max(1, (page_size + per_page - 1) // per_page)
    params: dict[str, str] = {
        "query.cond": identifiers.name,
        "filter.overallStatus": "COMPLETED",
        "pageSize": str(per_page),
        "fields": "NCTId,BriefTitle,protocolSection.outcomesModule",
        "format": "json",
    }

    measure_counts: Counter[str] = Counter()
    measure_display: dict[str, str] = {}

    try:
        studies = await paginate_clinicaltrials(
            session,
            params,
            max_pages=max_pages,
        )
        if not studies:
            return []
        for study in studies[:page_size]:
            outcomes = (
                study.get("protocolSection", {})
                .get("outcomesModule", {})
            )
            for key in ("primaryOutcomes", "secondaryOutcomes"):
                for outcome in outcomes.get(key, []):
                    measure = (outcome.get("measure") or "").strip()
                    if len(measure) < 4:
                        continue
                    norm = _normalize_measure(measure)
                    measure_counts[norm] += 1
                    measure_display.setdefault(norm, measure)
    except Exception as e:
        log.warning("[ClinicalTrials] endpoints failed for %s: %s", identifiers.name, e)
        return []

    alterations: list[Alteration] = []
    for norm, count in measure_counts.most_common(30):
        if count < 2:
            continue
        display = measure_display[norm]
        alt_type, subtype = _classify_endpoint(display)
        alterations.append(
            Alteration(
                canonical_id=_slug(display),
                name=display,
                alteration_type=alt_type,
                subtype=subtype,
                sources=["ClinicalTrials.gov"],
                evidence_tier=EvidenceTier.B if count >= 5 else EvidenceTier.C,
            )
        )

    if alterations:
        cache_set("clinical", ck, [a.model_dump() for a in alterations])
    log.info("[ClinicalTrials] %s → %d endpoint alterations", identifiers.name, len(alterations))
    return alterations


def apply_loinc_lookup(alterations: list[Alteration]) -> list[Alteration]:
    updated: list[Alteration] = []
    for alt in alterations:
        low = alt.name.lower()
        for key, code in COMMON_LOINC.items():
            if key in low or low == key:
                source_ids = {**alt.source_ids, "LOINC": code}
                updated.append(alt.model_copy(update={"source_ids": source_ids}))
                break
        else:
            updated.append(alt)
    return updated


async def get_all(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    options: PipelineOptions,
) -> list[Alteration]:
    import asyncio

    if options.skip_clinical or not options.includes(2):
        return []

    results = await asyncio.gather(
        get_hpo_phenotypes(identifiers.omim_id, session, mondo_id=identifiers.mondo_id),
        get_orphanet_phenotypes(identifiers.orpha_id, session),
        get_ct_endpoints(
            identifiers,
            session,
            page_size=options.max_ct_studies,
            use_cache=options.use_cache,
        ),
        return_exceptions=True,
    )
    all_alts: list[Alteration] = []
    for r in results:
        if isinstance(r, list):
            all_alts.extend(r)
            if r:
                options.note_source(r[0].sources[0])
        elif isinstance(r, Exception):
            log.warning("Clinical adapter error: %s", r)

    return apply_loinc_lookup(all_alts)


# Back-compat alias
fetch_clinical_alterations = get_all