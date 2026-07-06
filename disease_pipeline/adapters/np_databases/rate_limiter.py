"""Per-domain rate limiters for NP database adapters."""
from __future__ import annotations

import asyncio
import time

from ...config import RATE_LIMITS

_LAST: dict[str, float] = {}
_LOCK = asyncio.Lock()
_SEMS: dict[str, asyncio.Semaphore] = {}


def semaphore_for(host: str, *, default: int = 2) -> asyncio.Semaphore:
    if host not in _SEMS:
        limit = int(RATE_LIMITS.get(host, RATE_LIMITS.get("default", default)))
        _SEMS[host] = asyncio.Semaphore(max(limit, 1))
    return _SEMS[host]


async def throttle(host: str) -> None:
    limit = RATE_LIMITS.get(host, RATE_LIMITS.get("default", 5))
    min_interval = 1.0 / max(float(limit), 0.1)
    async with _LOCK:
        now = time.monotonic()
        last = _LAST.get(host, 0.0)
        wait = min_interval - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _LAST[host] = time.monotonic()