"""File-based JSON cache keyed by namespace + logical key."""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import CACHE_DIR, CACHE_TTL_DAYS

log = logging.getLogger(__name__)


def _cache_path(namespace: str, key: str) -> Path:
    safe = hashlib.md5(key.encode()).hexdigest()
    p = CACHE_DIR / namespace
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{safe}.json"


def cache_get(namespace: str, key: str, ttl_days: int = CACHE_TTL_DAYS) -> dict | list | None:
    path = _cache_path(namespace, key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
        if datetime.now(timezone.utc) - cached_at.replace(tzinfo=timezone.utc) > timedelta(days=ttl_days):
            return None
        return data.get("payload")
    except Exception as e:
        log.debug("Cache read error (%s): %s", namespace, e)
        return None


def cache_set(namespace: str, key: str, payload: dict | list) -> None:
    path = _cache_path(namespace, key)
    try:
        path.write_text(
            json.dumps(
                {"_cached_at": datetime.now(timezone.utc).isoformat(), "payload": payload},
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        log.warning("Cache write failed (%s): %s", namespace, e)