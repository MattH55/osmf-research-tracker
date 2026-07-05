"""NP-2 — ClinicalTrials.gov dietary supplement interventions."""
from __future__ import annotations

import logging
import re
from collections import defaultdict

import aiohttp

from ...clinicaltrials_client import get_clinicaltrials
from ...models import DiseaseIdentifiers

log = logging.getLogger(__name__)

SUPPLEMENT_KEYWORDS = [
    "dietary supplement", "herbal", "botanical", "nutraceutical",
    "vitamin", "mineral", "probiotic", "prebiotic", "extract",
    "phytotherapy", "natural product", "traditional medicine",
    "omega-3", "fish oil", "curcumin", "berberine", "quercetin",
    "melatonin", "coenzyme q10", "coq10", "magnesium", "zinc",
    "resveratrol", "nac", "n-acetylcysteine", "ashwagandha",
    "ginseng", "echinacea", "elderberry", "cbd", "cannabidiol",
]

_PHARMA_PATTERNS = re.compile(
    r"\b(tablet|injection|infusion|chemotherapy|antibiotic|monoclonal|"
    r"placebo-controlled drug|pharmaceutical)\b",
    re.I,
)


def _is_supplement_intervention(name: str, intervention_type: str) -> bool:
    itype = (intervention_type or "").upper()
    if itype == "DRUG":
        return False
    if itype not in ("DIETARY_SUPPLEMENT", "OTHER", "BIOLOGICAL", ""):
        if itype not in ("DIETARY_SUPPLEMENT", "OTHER"):
            return False
    lower = name.lower()
    if _PHARMA_PATTERNS.search(lower):
        return False
    return any(kw in lower for kw in SUPPLEMENT_KEYWORDS) or itype == "DIETARY_SUPPLEMENT"


async def get_ct_supplement_interventions(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
) -> list[dict]:
    query_intr = " OR ".join(f'"{kw}"' for kw in SUPPLEMENT_KEYWORDS[:12])
    params = {
        "query.cond": identifiers.name,
        "query.intr": query_intr,
        "fields": "NCTId,InterventionName,InterventionType,Phase,OverallStatus,StartDate,PrimaryOutcomeMeasure",
        "format": "json",
        "pageSize": "200",
    }

    try:
        data = await get_clinicaltrials(session, params)
        if not data:
            return []
        studies = data.get("studies", [])
    except Exception as e:
        log.warning("[CT NP] search failed for '%s': %s", identifiers.name, e)
        return []

    agg: dict[str, dict] = defaultdict(lambda: {
        "trial_count": 0,
        "phases_seen": set(),
        "statuses": set(),
        "outcome_measures": set(),
    })

    for study in studies:
        proto = study.get("protocolSection", {})
        arms = proto.get("armsInterventionsModule", {})
        design = proto.get("designModule", {})
        status_mod = proto.get("statusModule", {})
        outcomes = proto.get("outcomesModule", {})

        phases = design.get("phases") or []
        status = status_mod.get("overallStatus", "")
        primary_outcomes = [
            o.get("measure", "") for o in (outcomes.get("primaryOutcomes") or [])
        ]

        for intervention in arms.get("interventions") or []:
            name = (intervention.get("name") or "").strip()
            itype = intervention.get("type", "")
            if not name or not _is_supplement_intervention(name, itype):
                continue
            key = name.lower()
            agg[key]["name"] = name
            agg[key]["trial_count"] += 1
            agg[key]["phases_seen"].update(phases)
            if status:
                agg[key]["statuses"].add(status)
            agg[key]["outcome_measures"].update(primary_outcomes[:3])

    results = []
    for entry in agg.values():
        results.append({
            "name": entry["name"],
            "trial_count": entry["trial_count"],
            "phases_seen": sorted(entry["phases_seen"]),
            "statuses": sorted(entry["statuses"]),
            "outcome_measures": sorted(entry["outcome_measures"])[:5],
        })

    results.sort(key=lambda x: x["trial_count"], reverse=True)
    results = results[:30]
    log.info("[CT NP] %d supplement interventions for '%s'", len(results), identifiers.name)
    return results