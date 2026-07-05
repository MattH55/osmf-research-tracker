"""ClinicalTrials.gov v2 API client with compliant headers and rate limiting."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import aiohttp

from .config import CLINICALTRIALS_TIMEOUT, CLINICALTRIALS_URL, clinicaltrials_headers

log = logging.getLogger(__name__)

# ClinicalTrials.gov: max 1 request per second
clinicaltrials_sem = asyncio.Semaphore(1)
_last_ct_request = 0.0
_ct_lock = asyncio.Lock()
def _urllib_preferred() -> bool:
    env = os.getenv("CLINICALTRIALS_USE_URLLIB", "1").lower()
    return env not in ("0", "false", "no")


_use_urllib_fallback: bool | None = True if _urllib_preferred() else None


async def _throttle_ct() -> None:
    global _last_ct_request
    async with _ct_lock:
        now = time.monotonic()
        wait = 1.05 - (now - _last_ct_request)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_ct_request = time.monotonic()


def _fetch_ct_sync(
    url: str,
    params: dict[str, Any],
    headers: dict[str, str],
) -> tuple[int, dict[str, Any] | None, str]:
    """urllib transport — used when aiohttp is TLS-fingerprint blocked."""
    query = urlencode(params)
    full_url = f"{url}?{query}" if query else url
    req = Request(full_url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=CLINICALTRIALS_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body), ""
    except HTTPError as e:
        retry_after = e.headers.get("Retry-After", "") if e.headers else ""
        try:
            body = e.read().decode("utf-8", errors="replace")
            payload = json.loads(body) if body else None
        except Exception:
            payload = None
        return e.code, payload, retry_after
    except URLError as e:
        if isinstance(e.reason, TimeoutError | socket.timeout):
            raise TimeoutError(str(e)) from e
        raise RuntimeError(str(e)) from e


def _handle_urllib_response(
    status: int,
    data: dict[str, Any] | None,
    attempt: int,
    *,
    retry_after: str = "",
) -> dict[str, Any] | None | str:
    """Return parsed JSON, None (terminal), or 'retry'."""
    if status == 200 and data is not None:
        return data
    if status == 404:
        return None
    if status == 403:
        log.warning("[ClinicalTrials] 403 Forbidden. Check User-Agent and rate limits.")
        return "retry"
    if status == 429:
        log.warning("[ClinicalTrials] Rate limited. Waiting...")
        return "retry"
    log.warning("[ClinicalTrials] Status %s", status)
    return None


def _retry_wait(status: int, attempt: int, retry_after: str = "") -> float:
    if status == 429 and retry_after.isdigit():
        return float(retry_after)
    if status == 429:
        return 10.0
    return 5.0 * (attempt + 1)


async def get_clinicaltrials(
    session: aiohttp.ClientSession,
    params: dict[str, Any],
    *,
    max_retries: int = 3,
) -> dict[str, Any] | None:
    """
    Safe async query to ClinicalTrials.gov v2 /studies endpoint.

    Example::

        params = {
            "query.cond": "type 2 diabetes",
            "filter.overallStatus": "COMPLETED",
            "fields": "NCTId,BriefTitle,PrimaryOutcome,SecondaryOutcome",
            "pageSize": "100",
            "format": "json",
        }
        data = await get_clinicaltrials(session, params)
    """
    global _use_urllib_fallback
    url = f"{CLINICALTRIALS_URL}/studies"
    headers = clinicaltrials_headers()
    query = {**params, "format": params.get("format", "json")}

    for attempt in range(max_retries):
        async with clinicaltrials_sem:
            await _throttle_ct()

            try:
                if _use_urllib_fallback:
                    status, data, retry_after = await asyncio.to_thread(
                        _fetch_ct_sync, url, query, headers
                    )
                    result = _handle_urllib_response(
                        status, data, attempt, retry_after=retry_after
                    )
                    if result == "retry":
                        await asyncio.sleep(_retry_wait(status, attempt, retry_after))
                        continue
                    return result

                async with session.get(
                    url,
                    params=query,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=CLINICALTRIALS_TIMEOUT),
                ) as response:
                    if response.status == 200:
                        return await response.json(content_type=None)

                    elif response.status == 403:
                        log.warning(
                            "[ClinicalTrials] 403 Forbidden. Check User-Agent and rate limits."
                        )
                        if not _use_urllib_fallback:
                            _use_urllib_fallback = True
                            status, data, _ = await asyncio.to_thread(
                                _fetch_ct_sync, url, query, headers
                            )
                            if status == 200 and data is not None:
                                return data
                        await asyncio.sleep(5 * (attempt + 1))
                        continue

                    elif response.status == 429:
                        log.warning("[ClinicalTrials] Rate limited. Waiting...")
                        await asyncio.sleep(10)
                        continue

                    elif response.status == 404:
                        return None

                    else:
                        log.warning("[ClinicalTrials] Status %s", response.status)
                        return None

            except asyncio.TimeoutError:
                log.warning("[ClinicalTrials] Timeout")
                await asyncio.sleep(3)
            except Exception as e:
                log.warning("[ClinicalTrials] Error: %s", e)
                await asyncio.sleep(3)

    log.warning("ClinicalTrials.gov gave up after %d retries", max_retries)
    return None


async def paginate_clinicaltrials(
    session: aiohttp.ClientSession,
    params: dict[str, Any],
    *,
    max_pages: int = 5,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """Fetch multiple pages using pageToken (preferred over huge pageSize)."""
    studies: list[dict[str, Any]] = []
    page_token: str | None = None

    for _ in range(max_pages):
        page_params = dict(params)
        if page_token:
            page_params["pageToken"] = page_token
        data = await get_clinicaltrials(session, page_params, max_retries=max_retries)
        if not data:
            break
        studies.extend(data.get("studies", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return studies