"""Cached HTML fetch for natural-product reference sites."""
from __future__ import annotations

import asyncio
import logging
import time

import aiohttp

from ...cache import cache_get, cache_set
from ...config import BROWSER_USER_AGENT, HTTP_TIMEOUT, RATE_LIMITS

log = logging.getLogger(__name__)

_HOST_SEMS: dict[str, asyncio.Semaphore] = {
    "greenmedinfo": asyncio.Semaphore(1),
    "examine": asyncio.Semaphore(1),
}
_LAST_FETCH: dict[str, float] = {}
_FETCH_LOCK = asyncio.Lock()


def _host_from_url(url: str) -> str:
    if "greenmedinfo" in url:
        return "greenmedinfo"
    if "examine.com" in url:
        return "examine"
    return "default"


async def _throttle(host: str) -> None:
    limit = RATE_LIMITS.get(host, RATE_LIMITS.get("default", 5))
    min_interval = 1.0 / max(limit, 0.1)
    async with _FETCH_LOCK:
        now = time.monotonic()
        last = _LAST_FETCH.get(host, 0.0)
        wait = min_interval - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _LAST_FETCH[host] = time.monotonic()


async def fetch_html(
    session: aiohttp.ClientSession,
    url: str,
    *,
    namespace: str,
    cache_key: str,
    use_cache: bool = True,
    ttl_days: int = 14,
) -> str | None:
    if use_cache:
        cached = cache_get(namespace, cache_key, ttl_days=ttl_days)
        if isinstance(cached, str) and cached:
            return cached

    host = _host_from_url(url)
    sem = _HOST_SEMS.get(host, asyncio.Semaphore(2))
    headers = {
        "User-Agent": BROWSER_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        async with sem:
            await _throttle(host)
            async with session.get(
                url,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
                allow_redirects=True,
            ) as resp:
                if resp.status == 404:
                    return None
                if resp.status == 429:
                    log.warning("[NP web] rate limited: %s", url)
                    return None
                resp.raise_for_status()
                html = await resp.text(errors="replace")
    except Exception as e:
        log.warning("[NP web] fetch failed %s: %s", url, e)
        return None

    if use_cache and html:
        cache_set(namespace, cache_key, html)
    return html