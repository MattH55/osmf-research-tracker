"""NCCIH herb/supplement fact sheets."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT, PACKAGE_DIR
from ..llm_parse import extract_nccih_factsheet

log = logging.getLogger(__name__)

NCCIH_BASE = "https://www.nccih.nih.gov/health"
SLUGS_PATH = PACKAGE_DIR / "seeds" / "nccih_slugs.json"

_slugs: dict[str, str] | None = None


def _load_slugs() -> dict[str, str]:
    global _slugs
    if _slugs is None:
        _slugs = json.loads(SLUGS_PATH.read_text(encoding="utf-8")) if SLUGS_PATH.exists() else {}
    return _slugs


async def fetch_np_fact_sheet(np_name: str, session: aiohttp.ClientSession) -> dict | None:
    slug = _load_slugs().get(np_name.lower())
    if not slug:
        return None
    url = f"{NCCIH_BASE}/{slug}"
    try:
        async with session.get(
            url,
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                return None
            html = await resp.text(errors="replace")
    except Exception as e:
        log.debug("[NCCIH] fetch failed %s: %s", np_name, e)
        return None

    data = await extract_nccih_factsheet(html, np_name)
    if data:
        data["url"] = url
        data["source"] = "NCCIH"
        data["np_name"] = np_name
    return data


async def fetch_disease_nps(disease_name: str, session: aiohttp.ClientSession) -> list[dict]:
    """Return NCCIH fact sheets for common NPs (disease match via LLM when available)."""
    # NCCIH has no disease index — fetch a bounded set of high-value supplements only.
    priority = [
        "turmeric", "berberine", "magnesium", "vitamin d", "omega-3 fatty acids",
        "probiotics", "ashwagandha", "ginseng", "melatonin", "ginger",
    ]
    hits: list[dict] = []
    for np_name in priority:
        sheet = await fetch_np_fact_sheet(np_name, session)
        if sheet:
            hits.append(sheet)
    return hits