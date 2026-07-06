"""Disease slug map — per-database URL slugs for RepurpOS conditions."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ...config import PACKAGE_DIR

log = logging.getLogger(__name__)

SLUG_MAP_PATH = PACKAGE_DIR / "seeds" / "disease_slugs.json"
GMI_OVERRIDES = PACKAGE_DIR / "seeds" / "gmi_disease_slugs.json"
EXAMINE_OVERRIDES = PACKAGE_DIR / "seeds" / "examine_condition_slugs.json"

_cache: dict | None = None


def _slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


def load_slug_map() -> dict[str, dict[str, str]]:
    global _cache
    if _cache is not None:
        return _cache

    if SLUG_MAP_PATH.exists():
        _cache = json.loads(SLUG_MAP_PATH.read_text(encoding="utf-8"))
        return _cache

    merged: dict[str, dict[str, str]] = {}
    if GMI_OVERRIDES.exists():
        for slug, gmi in json.loads(GMI_OVERRIDES.read_text(encoding="utf-8")).items():
            merged.setdefault(slug, {})["greenmedinfo"] = gmi
    if EXAMINE_OVERRIDES.exists():
        for slug, ex in json.loads(EXAMINE_OVERRIDES.read_text(encoding="utf-8")).items():
            merged.setdefault(slug, {})["examine"] = ex

    _cache = merged
    return _cache


def get_slug(
    disease_slug: str,
    disease_name: str,
    source: str,
    slug_map: dict | None = None,
) -> str | None:
    m = slug_map or load_slug_map()
    entry = m.get(disease_slug, {})
    if source in entry:
        return entry[source]
    if source == "greenmedinfo":
        return entry.get("greenmedinfo")
    if source == "examine":
        return entry.get("examine") or disease_slug or _slugify(disease_name)
    return disease_slug or _slugify(disease_name)