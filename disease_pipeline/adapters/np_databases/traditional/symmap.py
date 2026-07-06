"""SymMap — TCM symptom → disease → herb links."""
from __future__ import annotations

import logging

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT
from ....http_util import get_json

log = logging.getLogger(__name__)

SYMMAP_BASE = "https://www.symmap.org"


async def query_disease_herbs(
    disease_name: str,
    session: aiohttp.ClientSession,
) -> list[dict]:
    try:
        data = await get_json(
            session,
            f"{SYMMAP_BASE}/api/diseases",
            params={"name": disease_name, "format": "json"},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if not data:
            return []
        rows = data if isinstance(data, list) else data.get("data", data.get("herbs", []))
        return [
            {
                "herb_name_en": r.get("herb_name_en") or r.get("name", ""),
                "herb_name_cn": r.get("herb_name_cn", ""),
                "symmap_herb_id": r.get("herb_id", ""),
                "associated_symptoms": r.get("symptoms", []),
                "target_genes": r.get("target_genes", []),
                "disease_score": r.get("score", 0.0),
                "source": "SymMap",
            }
            for r in rows
        ]
    except Exception as e:
        log.debug("[SymMap] unavailable: %s", e)
        return []