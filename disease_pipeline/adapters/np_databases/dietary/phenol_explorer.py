"""Phenol-Explorer — food phenolic compounds."""
from __future__ import annotations

import logging

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT
from ....http_util import get_json
from ....models import DiseaseIdentifiers

log = logging.getLogger(__name__)

PHENOL_BASE = "https://phenol-explorer.eu/api"


async def get_compounds_for_disease(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    activity_terms: list[str] | None = None,
) -> list[dict]:
    try:
        data = await get_json(
            session,
            f"{PHENOL_BASE}/compounds.xml",
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if not data:
            return []
    except Exception as e:
        log.debug("[Phenol-Explorer] unavailable: %s", e)
        return []

    terms = {t.lower() for t in (activity_terms or [])}
    out: list[dict] = []
    compounds = data if isinstance(data, list) else data.get("compounds", [])
    for c in compounds[:200]:
        activities = [a.lower() for a in c.get("biological_activities", [])]
        if terms and not (terms & set(activities)):
            continue
        out.append({
            "compound_name": c.get("name", ""),
            "phenol_explorer_id": c.get("id", ""),
            "compound_class": c.get("class", ""),
            "biological_activities": c.get("biological_activities", []),
            "food_sources": c.get("food_sources", []),
            "source": "Phenol-Explorer",
        })
    return out[:50]