"""NIH RCDC categorical spending — funding and CDC mortality."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ...config import PACKAGE_DIR

log = logging.getLogger(__name__)

RCDC_SEED_PATH = PACKAGE_DIR / "seeds" / "nih_rcdc_by_slug.json"
RCDC_MAP_PATH = PACKAGE_DIR / "seeds" / "rcdc_slug_map.json"

_cache: dict[str, dict] | None = None
_map_cache: dict[str, str] | None = None


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def load_rcdc_by_slug() -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache
    if not RCDC_SEED_PATH.exists():
        log.warning("nih_rcdc_by_slug.json not found — run build_rcdc_seed.py")
        _cache = {}
        return _cache
    payload = json.loads(RCDC_SEED_PATH.read_text(encoding="utf-8"))
    _cache = payload.get("by_slug", payload)
    return _cache


def load_slug_map() -> dict[str, str]:
    global _map_cache
    if _map_cache is not None:
        return _map_cache
    if RCDC_MAP_PATH.exists():
        _map_cache = json.loads(RCDC_MAP_PATH.read_text(encoding="utf-8"))
    else:
        _map_cache = {}
    return _map_cache


def get_rcdc_burden(slug: str, disease_name: str = "") -> dict | None:
    by_slug = load_rcdc_by_slug()
    if slug in by_slug:
        return dict(by_slug[slug])

    slug_map = load_slug_map()
    cat = slug_map.get(slug)
    if cat:
        for row in by_slug.values():
            if _norm(row.get("rcdc_category", "")) == _norm(cat):
                return dict(row)

    if disease_name:
        dn = _norm(disease_name)
        for row in by_slug.values():
            cat_n = _norm(row.get("rcdc_category", ""))
            if cat_n and (cat_n in dn or dn in cat_n):
                return dict(row)
    return None