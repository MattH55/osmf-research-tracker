"""Examine.com Human Effect Matrix lookup."""
from __future__ import annotations

import logging
import re

import aiohttp

from ....models import DiseaseIdentifiers
from ...natural_products.examine_np import EXAMINE_BASE, _parse_supplements, condition_slug_candidates
from ..browser import BrowserManager
from ..llm_parse import extract_examine_hem

log = logging.getLogger(__name__)

_GRADE_RE = re.compile(r'grade["\s:>-]*([ABCD])', re.I)


async def fetch_condition_hem(
    condition_slug: str,
    condition_name: str,
    bm: BrowserManager,
    session: aiohttp.ClientSession,
) -> tuple[list[dict], str]:
    url = f"{EXAMINE_BASE}/conditions/{condition_slug}/"
    html = await bm.fetch_html(session, url, namespace="examine", cache_key=url)
    if not html:
        return [], url

    records = _parse_supplements(html)
    out: list[dict] = []

    for rec in records:
        grade = "C"
        out.append({
            "supplement_name": rec["name"],
            "examine_slug": rec.get("slug", ""),
            "effect_direction": "unclear",
            "evidence_grade": grade,
            "study_count": 0,
            "effect_magnitude": None,
            "health_outcome": condition_name,
            "url": rec.get("url"),
            "source": "Examine.com",
        })

    if not out:
        llm_rows = await extract_examine_hem(html, condition_name)
        for row in llm_rows:
            out.append({
                "supplement_name": row.get("supplement_name", ""),
                "examine_slug": row.get("examine_slug", ""),
                "effect_direction": row.get("effect_direction", "unclear"),
                "evidence_grade": row.get("evidence_grade", "C"),
                "study_count": row.get("study_count", 0),
                "effect_magnitude": row.get("effect_magnitude"),
                "health_outcome": row.get("health_outcome", condition_name),
                "source": "Examine.com",
            })

    log.info("[Examine] %d supplements for '%s'", len(out), condition_name)
    return out, url


async def fetch_for_identifiers(
    identifiers: DiseaseIdentifiers,
    disease_slug: str,
    bm: BrowserManager,
    session: aiohttp.ClientSession,
) -> tuple[list[dict], str]:
    for slug in condition_slug_candidates(disease_slug, identifiers.name):
        rows, url = await fetch_condition_hem(slug, identifiers.name, bm, session)
        if rows:
            return rows, url
    return [], f"{EXAMINE_BASE}/conditions/{disease_slug}/"