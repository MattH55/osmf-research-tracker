"""HTTP helpers: caching, retries, structured logging."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import CACHE_DIR, CACHE_TTL_DAYS, LOG_DIR, SOURCE_MAX_RETRIES, SOURCE_TIMEOUT_S

LOG_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("biomarker_agent_pipeline")
if not logger.handlers:
    fh = logging.FileHandler(LOG_DIR / "api_calls.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)


def _cache_path(source: str, key: str) -> Path:
    safe = hashlib.sha256(key.encode()).hexdigest()[:24]
    d = CACHE_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{safe}.json"


def read_cache(source: str, key: str) -> Any | None:
    path = _cache_path(source, key)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    age_days = (time.time() - payload.get("_cached_at", 0)) / 86400
    if age_days > CACHE_TTL_DAYS:
        return None
    return payload.get("data")


def write_cache(source: str, key: str, data: Any) -> None:
    path = _cache_path(source, key)
    path.write_text(
        json.dumps({"_cached_at": time.time(), "data": data}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def log_call(source: str, query: str, status: int, latency_ms: float, note: str = "") -> None:
    logger.info(
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "source": source,
                "query": query[:500],
                "status": status,
                "latency_ms": round(latency_ms, 1),
                "note": note,
            }
        )
    )


def request_json(
    source: str,
    cache_key: str,
    method: str,
    url: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    headers: dict | None = None,
    use_cache: bool = True,
) -> Any:
    if use_cache:
        cached = read_cache(source, cache_key)
        if cached is not None:
            log_call(source, cache_key, 200, 0, "cache_hit")
            return cached

    last_err = None
    for attempt in range(SOURCE_MAX_RETRIES + 1):
        t0 = time.time()
        try:
            with httpx.Client(timeout=SOURCE_TIMEOUT_S) as client:
                if method.upper() == "POST":
                    resp = client.post(url, json=json_body, headers=headers)
                else:
                    resp = client.get(url, params=params, headers=headers)
            latency = (time.time() - t0) * 1000
            log_call(source, cache_key, resp.status_code, latency)
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(min(2 ** attempt, 8))
                continue
            resp.raise_for_status()
            data = resp.json()
            if use_cache:
                write_cache(source, cache_key, data)
            return data
        except Exception as err:
            last_err = err
            time.sleep(min(2 ** attempt, 8))
    raise RuntimeError(f"{source} request failed for {cache_key}: {last_err}")