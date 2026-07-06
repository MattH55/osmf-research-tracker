"""ETCM — Evidence-Based Traditional Chinese Medicine."""
from __future__ import annotations

import logging
import re

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT
from ....http_util import get_json

log = logging.getLogger(__name__)

ETCM_BASE = "http://www.tcmip.cn/ETCM"


async def query_disease(disease_name: str, session: aiohttp.ClientSession) -> list[dict]:
    try:
        data = await get_json(
            session,
            f"{ETCM_BASE}/index.php/Front/Disease/getDisease",
            params={"name": disease_name},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if data and isinstance(data, dict):
            herbs = data.get("herbs") or data.get("data", [])
            return [
                {
                    "herb_name": h.get("herb_name") or h.get("name", ""),
                    "compounds": h.get("compounds", []),
                    "targets": h.get("targets", []),
                    "evidence_grade": h.get("evidence_grade", "C"),
                    "source": "ETCM",
                }
                for h in herbs
            ]
    except Exception:
        pass

    try:
        async with session.get(
            f"{ETCM_BASE}/index.php/Front/Disease/index.html",
            params={"name": disease_name},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                return []
            html = await resp.text(errors="replace")
    except Exception as e:
        log.debug("[ETCM] fetch failed: %s", e)
        return []

    herbs = []
    for m in re.finditer(r'herb[^>]*>([^<]{2,60})<', html, re.I):
        herbs.append({
            "herb_name": m.group(1).strip(),
            "compounds": [],
            "targets": [],
            "evidence_grade": "C",
            "source": "ETCM",
        })
    return herbs[:30]