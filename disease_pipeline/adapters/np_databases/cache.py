"""NP database cache — 30-day TTL for scraped pages, 7-day for APIs."""
from __future__ import annotations

from ...cache import cache_get as _get
from ...cache import cache_set as _set

SCRAPED_TTL_DAYS = 30
API_TTL_DAYS = 7


def cache_get(namespace: str, key: str, *, scraped: bool = False):
    ttl = SCRAPED_TTL_DAYS if scraped else API_TTL_DAYS
    return _get(namespace, key, ttl_days=ttl)


def cache_set(namespace: str, key: str, payload) -> None:
    _set(namespace, key, payload)