"""GreenMedInfo disease slug index (from /greenmed/display/disease)."""
from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path

import aiohttp

from ...config import PACKAGE_DIR
from .web_fetch import fetch_html

log = logging.getLogger(__name__)

GMI_BASE = "https://greenmedinfo.com"
GMI_SITEMAP_URL = f"{GMI_BASE}/sitemap.xml"
GMI_DISEASE_INDEX_URL = f"{GMI_BASE}/greenmed/display/disease"
GMI_INDEX_PATH = PACKAGE_DIR / "seeds" / "gmi_disease_index.json"
GMI_OVERRIDES_PATH = PACKAGE_DIR / "seeds" / "gmi_disease_slugs.json"

_index_cache: set[str] | None = None
_overrides_cache: dict[str, str] | None = None


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


def _load_overrides() -> dict[str, str]:
    global _overrides_cache
    if _overrides_cache is not None:
        return _overrides_cache
    if GMI_OVERRIDES_PATH.exists():
        _overrides_cache = json.loads(GMI_OVERRIDES_PATH.read_text(encoding="utf-8"))
    else:
        _overrides_cache = {}
    return _overrides_cache


def load_gmi_disease_index() -> set[str]:
    global _index_cache
    if _index_cache is not None:
        return _index_cache
    if GMI_INDEX_PATH.exists():
        data = json.loads(GMI_INDEX_PATH.read_text(encoding="utf-8"))
        slugs = data.get("slugs") or data
        if isinstance(slugs, list):
            _index_cache = {s.removeprefix("/disease/").strip("/") for s in slugs}
            return _index_cache
    _index_cache = set()
    return _index_cache


async def refresh_gmi_disease_index(
    session: aiohttp.ClientSession,
    *,
    use_cache: bool = True,
) -> list[str]:
    """Fetch disease slugs from GMI disease directory (linked in sitemap)."""
    html = await fetch_html(
        session,
        GMI_DISEASE_INDEX_URL,
        namespace="greenmedinfo",
        cache_key="disease-index",
        use_cache=use_cache,
        ttl_days=30,
    )
    if not html:
        return sorted(load_gmi_disease_index())

    slugs = sorted({
        path.removeprefix("/disease/").strip("/")
        for path in re.findall(r'href="(/disease/[^"]+)"', html)
    })
    payload = {
        "source": GMI_DISEASE_INDEX_URL,
        "sitemap": GMI_SITEMAP_URL,
        "count": len(slugs),
        "slugs": slugs,
    }
    GMI_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    GMI_INDEX_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    global _index_cache
    _index_cache = set(slugs)
    log.info("[GMI] refreshed disease index: %d slugs", len(slugs))
    return slugs


def _token_score(a: str, b: str) -> float:
    ta = set(_slugify(a).split("-"))
    tb = set(b.split("-"))
    if not ta or not tb:
        return 0.0
    overlap = len(ta & tb) / max(len(ta), 1)
    ratio = SequenceMatcher(None, _slugify(a), b).ratio()
    return overlap * 0.7 + ratio * 0.3


def resolve_gmi_disease_slug(
    disease_slug: str,
    disease_name: str,
    *,
    index: set[str] | None = None,
) -> str | None:
    """Map RepurpOS slug/name to a GreenMedInfo /disease/{slug} page."""
    idx = index or load_gmi_disease_index()
    if not idx:
        return None

    overrides = _load_overrides()
    if disease_slug in overrides and overrides[disease_slug] in idx:
        return overrides[disease_slug]

    direct_candidates = [
        disease_slug,
        _slugify(disease_name),
        disease_slug.replace("-syndrome", ""),
        disease_slug.replace("-disorder", ""),
        disease_slug.replace("-disease", ""),
    ]
    for cand in direct_candidates:
        if cand and cand in idx:
            return cand

    # Prefer slugs that are exact token subsets (e.g. diabetes-mellitus-type-2)
    name_norm = _slugify(disease_name)
    best_slug: str | None = None
    best_score = 0.0
    for gmi_slug in idx:
        score = _token_score(name_norm, gmi_slug)
        if score > best_score:
            best_score = score
            best_slug = gmi_slug

    if best_slug and best_score >= 0.55:
        return best_slug
    return None


def gmi_disease_page_url(gmi_slug: str) -> str:
    return f"{GMI_BASE}/disease/{gmi_slug}"