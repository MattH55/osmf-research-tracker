"""WHO GHE 2021 burden — US and global DALYs and deaths."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ...config import PACKAGE_DIR

log = logging.getLogger(__name__)

BURDEN_SEED_PATH = PACKAGE_DIR / "seeds" / "ghe_burden_by_slug.json"

_cache: dict[str, dict] | None = None


def _load_seed() -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache
    if not BURDEN_SEED_PATH.exists():
        log.debug("ghe_burden_by_slug.json not found — run build_ghe_burden.py")
        _cache = {}
        return _cache
    payload = json.loads(BURDEN_SEED_PATH.read_text(encoding="utf-8"))
    _cache = payload.get("by_slug", payload)
    return _cache


def get_ghe_burden_from_seed(slug: str) -> dict | None:
    row = _load_seed().get(slug)
    return dict(row) if row else None