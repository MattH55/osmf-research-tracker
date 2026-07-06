"""Examine.com condition → supplement lookup."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import quote_plus

import aiohttp

from ...config import PACKAGE_DIR
from ...models import DiseaseIdentifiers
from ...options import PipelineOptions
from .web_fetch import fetch_html

log = logging.getLogger(__name__)

EXAMINE_BASE = "https://examine.com"
_SLUG_OVERRIDES_PATH = PACKAGE_DIR / "seeds" / "examine_condition_slugs.json"

_SUPPLEMENT_RE = re.compile(
    r'/supplements/([a-z0-9-]+)/"><span[^>]*>([^<]+)</span></a>',
    re.I,
)
_SLUG_ONLY_RE = re.compile(r"/supplements/([a-z0-9-]+)/", re.I)

_slug_overrides: dict[str, str] | None = None


def _load_slug_overrides() -> dict[str, str]:
    global _slug_overrides
    if _slug_overrides is not None:
        return _slug_overrides
    if _SLUG_OVERRIDES_PATH.exists():
        _slug_overrides = json.loads(_SLUG_OVERRIDES_PATH.read_text(encoding="utf-8"))
    else:
        _slug_overrides = {}
    return _slug_overrides


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[-\s]+", "-", text).strip("-")


def condition_slug_candidates(disease_slug: str, disease_name: str) -> list[str]:
    overrides = _load_slug_overrides()
    if disease_slug in overrides:
        return [overrides[disease_slug]]
    name_slug = _slugify(disease_name)
    candidates = []
    for slug in (disease_slug, name_slug):
        if slug and slug not in candidates:
            candidates.append(slug)
    return candidates


def examine_condition_url(slug: str) -> str:
    return f"{EXAMINE_BASE}/conditions/{slug}/"


def examine_search_url(disease_name: str) -> str:
    return f"{EXAMINE_BASE}/search/?q={quote_plus(disease_name)}"


def _parse_supplements(html: str) -> list[dict]:
    seen: set[str] = set()
    records: list[dict] = []

    for slug, raw_name in _SUPPLEMENT_RE.findall(html):
        name = re.sub(r"\s+", " ", raw_name).strip()
        if not name or slug in seen:
            continue
        seen.add(slug)
        records.append({
            "name": name,
            "slug": slug,
            "url": f"{EXAMINE_BASE}/supplements/{slug}/",
            "source": "Examine.com",
        })

    if records:
        return records

    for slug in _SLUG_ONLY_RE.findall(html):
        if slug in seen:
            continue
        seen.add(slug)
        records.append({
            "name": slug.replace("-", " ").title(),
            "slug": slug,
            "url": f"{EXAMINE_BASE}/supplements/{slug}/",
            "source": "Examine.com",
        })
    return records


async def search_examine_supplements(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    *,
    disease_slug: str = "",
    options: PipelineOptions | None = None,
) -> tuple[list[dict], str | None]:
    """Return supplement records and the Examine condition URL when found."""
    opts = options or PipelineOptions()
    slug = disease_slug or _slugify(identifiers.name)

    for candidate in condition_slug_candidates(slug, identifiers.name):
        url = examine_condition_url(candidate)
        html = await fetch_html(
            session,
            url,
            namespace="examine",
            cache_key=url,
            use_cache=opts.use_cache,
        )
        if not html:
            continue
        records = _parse_supplements(html)[:60]
        if records:
            log.info("[Examine] %d supplements for '%s' (%s)", len(records), identifiers.name, candidate)
            return records, url

    log.info("[Examine] no condition page for '%s'", identifiers.name)
    return [], None