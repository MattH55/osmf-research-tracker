"""COCONUT — Collection of Open Natural Products."""
from __future__ import annotations

import logging
from urllib.parse import quote

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT
from ....http_util import get_json
from ..cache import cache_get, cache_set

log = logging.getLogger(__name__)

COCONUT_BASE = "https://coconut.naturalproducts.net/api"


async def search_by_name(name: str, session: aiohttp.ClientSession) -> dict | None:
    ck = f"coconut:{name.lower()}"
    cached = cache_get("coconut", ck)
    if cached is not None:
        return cached or None
    try:
        data = await get_json(
            session,
            f"{COCONUT_BASE}/search",
            params={"query": name, "type": "name"},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if not data:
            cache_set("coconut", ck, {})
            return None
        results = data if isinstance(data, list) else data.get("results", [])
        best = results[0] if results else None
        cache_set("coconut", ck, best or {})
        return best
    except Exception as e:
        log.debug("[COCONUT] search failed: %s", e)
        cache_set("coconut", ck, {})
        return None


async def search_nps_for_targets(
    gene_symbols: list[str],
    session: aiohttp.ClientSession,
) -> list[dict]:
    out: list[dict] = []
    for gene in gene_symbols[:8]:
        try:
            data = await get_json(
                session,
                f"{COCONUT_BASE}/search",
                params={"query": gene, "type": "target"},
                headers={"User-Agent": BROWSER_USER_AGENT},
                timeout=HTTP_TIMEOUT,
            )
            rows = data if isinstance(data, list) else (data or {}).get("results", [])
            for row in rows[:15]:
                out.append({
                    "name": row.get("name") or row.get("pref_name", ""),
                    "coconut_id": row.get("id", ""),
                    "target_gene": gene,
                    "source": "COCONUT",
                })
        except Exception:
            continue
    return out