"""GreenMedInfo disease page → substance lookup."""
from __future__ import annotations

import json
import logging
import re

import aiohttp

from ....config import PACKAGE_DIR
from ....models import DiseaseIdentifiers
from ...natural_products.gmi_disease_index import resolve_gmi_disease_slug
from ...natural_products.greenmedinfo_np import (
    GMI_BASE,
    _parse_articles,
    _parse_substances,
    gmi_search_fallback_url,
)
from ..browser import BrowserManager
from ..llm_parse import extract_gmi_disease

log = logging.getLogger(__name__)

_ACTION_MAP_PATH = PACKAGE_DIR / "seeds" / "gmi_action_genes.json"
_action_map: dict | None = None


def _load_action_map() -> dict:
    global _action_map
    if _action_map is None:
        if _ACTION_MAP_PATH.exists():
            _action_map = json.loads(_ACTION_MAP_PATH.read_text(encoding="utf-8"))
        else:
            _action_map = {}
    return _action_map


def actions_to_genes(actions: list[str]) -> list[str]:
    m = _load_action_map()
    genes: set[str] = set()
    for act in actions:
        for gene in m.get(act, []):
            genes.add(gene)
    return sorted(genes)


async def fetch_disease_substances(
    disease_slug: str,
    disease_name: str,
    bm: BrowserManager,
    session: aiohttp.ClientSession,
) -> tuple[list[dict], str, list[dict]]:
    gmi_slug = resolve_gmi_disease_slug(disease_slug, disease_name)
    if gmi_slug:
        url = f"{GMI_BASE}/disease/{gmi_slug}"
    else:
        url = gmi_search_fallback_url(disease_name)

    html = await bm.fetch_html(session, url, namespace="greenmedinfo", cache_key=url)
    if not html or "gmi-search" in url:
        return [], url, []

    records = _parse_substances(html)
    articles = _parse_articles(html)

    if not records:
        llm_rows = await extract_gmi_disease(html, disease_name)
        for row in llm_rows:
            records.append({
                "name": row.get("substance_name", ""),
                "slug": row.get("gmi_slug", ""),
                "url": f"{GMI_BASE}/substance/{row.get('gmi_slug', '')}",
                "source": "GreenMedInfo",
                "article_count": row.get("study_count", 0),
                "evidence_tier": row.get("evidence_tier"),
                "pharmacological_actions": row.get("pharmacological_actions", []),
            })

    out = []
    for rec in records:
        actions = rec.get("pharmacological_actions") or []
        tier = rec.get("evidence_tier")
        if not tier:
            count = rec.get("article_count", 0)
            tier = "GOLD" if count >= 10 else "SILVER" if count >= 3 else "BRONZE"
        out.append({
            "substance_name": rec["name"],
            "gmi_slug": rec.get("slug", ""),
            "study_count": rec.get("article_count", 0),
            "evidence_tier": tier,
            "pharmacological_actions": actions,
            "target_genes": actions_to_genes(actions),
            "url": rec.get("url"),
            "source": "GreenMedInfo",
        })

    log.info("[GMI] %d substances for '%s'", len(out), disease_name)
    return out, url, articles


async def fetch_for_identifiers(
    identifiers: DiseaseIdentifiers,
    disease_slug: str,
    bm: BrowserManager,
    session: aiohttp.ClientSession,
) -> tuple[list[dict], str, list[dict]]:
    return await fetch_disease_substances(disease_slug, identifiers.name, bm, session)