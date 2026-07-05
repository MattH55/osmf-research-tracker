"""NP-4a — LOTUS compound lookup."""
from __future__ import annotations

import logging
from urllib.parse import quote

import aiohttp

from ...cache import cache_get, cache_set
from ...config import LOTUS_BASE
from ...http_util import get_json

log = logging.getLogger(__name__)


async def lotus_search_by_name(name: str, session: aiohttp.ClientSession) -> dict | None:
    ck = f"lotus:{name.lower()}"
    cached = cache_get("lotus", ck)
    if cached is not None:
        return cached if cached else None

    try:
        data = await get_json(
            session,
            f"{LOTUS_BASE}/search/simple",
            params={"query": name, "type": "wikidata_label", "limit": 3},
        )
        if not data:
            cache_set("lotus", ck, {})
            return None
        results = data if isinstance(data, list) else data.get("results", data.get("data", []))
        if not results:
            cache_set("lotus", ck, {})
            return None

        best = None
        for item in results:
            label = (item.get("label") or "").lower()
            if label == name.lower():
                best = item
                break
        best = best or results[0]
        out = {
            "wikidata_id": best.get("wikidata_id") or best.get("wd_id"),
            "label": best.get("label") or name,
            "structure": best.get("structure", {}),
            "organisms": best.get("organisms", []),
            "references_count": best.get("references_count", 0),
        }
        cache_set("lotus", ck, out)
        return out
    except Exception as e:
        log.debug("[LOTUS] search failed for '%s': %s", name[:40], e)
        cache_set("lotus", ck, {})
        return None


async def lotus_get_by_wikidata(wd_id: str, session: aiohttp.ClientSession) -> dict:
    ck = f"lotus_wd:{wd_id}"
    cached = cache_get("lotus", ck)
    if cached is not None:
        return cached

    try:
        data = await get_json(session, f"{LOTUS_BASE}/compound/{quote(wd_id, safe='')}")
        cache_set("lotus", ck, data or {})
        return data or {}
    except Exception as e:
        log.debug("[LOTUS] compound fetch failed for %s: %s", wd_id, e)
        return {}