"""BATMAN-TCM — network pharmacology REST API."""
from __future__ import annotations

import logging

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT
from ....http_util import post_json

log = logging.getLogger(__name__)

BATMAN_BASE = "http://batman.cbi.pku.edu.cn/batman_tcm"


async def query_disease_ingredients(
    disease_name: str,
    session: aiohttp.ClientSession,
) -> list[dict]:
    try:
        data = await post_json(
            session,
            f"{BATMAN_BASE}/search_by_disease",
            {"disease": disease_name, "format": "json"},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if not data:
            return []
        rows = data if isinstance(data, list) else data.get("results", data.get("data", []))
        out = []
        for row in rows:
            out.append({
                "ingredient_name": row.get("ingredient_name") or row.get("name", ""),
                "ingredient_id": row.get("ingredient_id", ""),
                "herb_sources": row.get("herb_sources", []),
                "target_genes": row.get("target_genes", []),
                "disease_score": row.get("disease_score", 0.0),
                "source": "BATMAN-TCM",
            })
        return out
    except Exception as e:
        log.debug("[BATMAN-TCM] unavailable: %s", e)
        return []