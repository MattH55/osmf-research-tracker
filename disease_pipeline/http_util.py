"""Shared async HTTP helpers with per-API semaphores and rate limiting."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from .config import HTTP_TIMEOUT, RATE_LIMITS, USER_AGENT, get_ncbi_api_key

log = logging.getLogger(__name__)

_last_request: dict[str, float] = {}
_rate_lock = asyncio.Lock()

SEMAPHORES: dict[str, asyncio.Semaphore] = {
    "open_targets": asyncio.Semaphore(10),
    "disgenet": asyncio.Semaphore(1),
    "hpo": asyncio.Semaphore(5),
    "orphanet": asyncio.Semaphore(5),
    "clinicaltrials": asyncio.Semaphore(1),
    "chembl": asyncio.Semaphore(10),
    "dgidb": asyncio.Semaphore(5),
    "pubmed": asyncio.Semaphore(10 if get_ncbi_api_key() else 3),
    "hmdb": asyncio.Semaphore(2),
    "pubchem": asyncio.Semaphore(5),
    "lotus": asyncio.Semaphore(5),
    "anthropic": asyncio.Semaphore(5),
    "default": asyncio.Semaphore(5),
}


def _host_key(url: str) -> str:
    if "opentargets" in url:
        return "open_targets"
    if "disgenet" in url:
        return "disgenet"
    if "hpo.jax" in url:
        return "hpo"
    if "orphadata" in url or "ols4" in url or "orphacode" in url:
        return "orphanet"
    if "clinicaltrials.gov" in url:
        return "clinicaltrials"
    if "chembl" in url:
        return "chembl"
    if "dgidb" in url:
        return "dgidb"
    if "ncbi.nlm.nih.gov" in url:
        return "pubmed"
    if "hmdb.ca" in url:
        return "hmdb"
    if "pubchem.ncbi.nlm.nih.gov" in url:
        return "pubchem"
    if "lotus.naturalproducts.net" in url:
        return "lotus"
    return "default"


async def _throttle(host: str) -> None:
    limit = RATE_LIMITS.get(host, RATE_LIMITS.get("default", 5))
    min_interval = 1.0 / max(limit, 0.1)
    async with _rate_lock:
        now = time.monotonic()
        last = _last_request.get(host, 0.0)
        wait = min_interval - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request[host] = time.monotonic()
    if host == "disgenet":
        await asyncio.sleep(1.0)


async def get_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Any:
    host = _host_key(url)
    sem = SEMAPHORES.get(host, SEMAPHORES["default"])
    async with sem:
        await _throttle(host)
        async with session.get(
            url,
            params=params,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout or HTTP_TIMEOUT),
        ) as resp:
            if resp.status == 404:
                return None
            resp.raise_for_status()
            return await resp.json(content_type=None)


async def post_json(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> Any:
    host = _host_key(url)
    sem = SEMAPHORES.get(host, SEMAPHORES["default"])
    async with sem:
        await _throttle(host)
        hdrs = {"Content-Type": "application/json"}
        if headers:
            hdrs.update(headers)
        async with session.post(
            url,
            json=payload,
            headers=hdrs,
            timeout=aiohttp.ClientTimeout(total=timeout or HTTP_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)


async def graphql(
    session: aiohttp.ClientSession,
    url: str,
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables
    data = await post_json(session, url, payload)
    if isinstance(data, dict) and data.get("errors"):
        log.warning("GraphQL errors from %s: %s", url, data["errors"][:2])
    return data or {}


def default_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession(headers={"User-Agent": USER_AGENT})