"""ClinicalTrials.gov dietary supplement interventions."""
from __future__ import annotations

import logging

import aiohttp

from ....models import DiseaseIdentifiers
from ...natural_products.clinicaltrials_np import get_ct_supplement_interventions

log = logging.getLogger(__name__)


async def fetch_supplement_trials(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
) -> list[dict]:
    raw = await get_ct_supplement_interventions(identifiers, session)
    out: list[dict] = []
    for rec in raw:
        phases = list(rec.get("phases_seen") or [])
        statuses = rec.get("statuses") or {}
        trial_count = rec.get("trial_count", 0)
        tier = "C"
        if trial_count >= 5 and any("3" in p for p in phases):
            tier = "A"
        elif trial_count >= 2 and any("2" in p for p in phases):
            tier = "B"
        out.append({
            "np_name": rec.get("name", ""),
            "trial_count": trial_count,
            "phases_seen": phases,
            "statuses": statuses,
            "outcome_measures": list(rec.get("outcome_measures") or []),
            "signal_tier": tier,
            "source": "ClinicalTrials.gov",
        })
    return out