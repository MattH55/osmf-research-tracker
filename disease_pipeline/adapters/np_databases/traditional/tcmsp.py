"""TCMSP — Traditional Chinese Medicine Systems Pharmacology."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT, PACKAGE_DIR
from ..local_data import TCMSP_DIR

log = logging.getLogger(__name__)

TCMSP_BASE = "https://tcmsp-e.com/tcmsp.php"
HERB_MAP_PATH = PACKAGE_DIR / "seeds" / "tcmsp_herb_map.json"


def _herb_map() -> dict:
    if HERB_MAP_PATH.exists():
        return json.loads(HERB_MAP_PATH.read_text(encoding="utf-8"))
    return {}


def map_herb_to_np_name(herb_name_en: str, synonym_index: dict) -> str:
    mapped = _herb_map().get(herb_name_en)
    if mapped:
        return mapped
    return synonym_index.get(herb_name_en.lower(), herb_name_en)


async def query_disease_herbs(
    disease_name: str,
    tcmsp_data: dict,
    session: aiohttp.ClientSession,
) -> list[dict]:
    if tcmsp_data.get("herbs"):
        return _query_from_bulk(disease_name, tcmsp_data)

    try:
        async with session.get(
            TCMSP_BASE,
            params={"qr": disease_name, "qsr": "Disease"},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                return []
            html = await resp.text(errors="replace")
    except Exception as e:
        log.debug("[TCMSP] query failed: %s", e)
        return []

    import re
    herbs = []
    for match in re.finditer(r'herb[_\s]*name[^>]*>([^<]+)<', html, re.I):
        herbs.append({
            "herb_name_en": match.group(1).strip(),
            "herb_name_cn": "",
            "tcmsp_herb_id": "",
            "active_compounds": [],
            "target_genes": [],
            "source": "TCMSP",
        })
    return herbs[:50]


def _query_from_bulk(disease_name: str, tcmsp_data: dict) -> list[dict]:
    return []