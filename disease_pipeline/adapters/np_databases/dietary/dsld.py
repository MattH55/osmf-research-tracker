"""DSLD — NIH Dietary Supplement Label Database (dosing enrichment)."""
from __future__ import annotations

import logging
import statistics

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT
from ....http_util import get_json

log = logging.getLogger(__name__)

DSLD_BASE = "https://api.ods.od.nih.gov/dsld/v8"


async def get_dosing_data(ingredient_name: str, session: aiohttp.ClientSession) -> dict | None:
    try:
        search = await get_json(
            session,
            f"{DSLD_BASE}/ingredient/search",
            params={"name": ingredient_name},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        if not search:
            return None
        items = search if isinstance(search, list) else search.get("results", [])
        if not items:
            return None
        dsld_id = items[0].get("dsld_id") or items[0].get("id")
        detail = await get_json(
            session,
            f"{DSLD_BASE}/ingredient/{dsld_id}",
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=HTTP_TIMEOUT,
        )
        doses = []
        forms: set[str] = set()
        combos: set[str] = set()
        for prod in (detail or {}).get("products", []):
            dose = prod.get("serve_size")
            if dose:
                try:
                    doses.append(float(dose))
                except (TypeError, ValueError):
                    pass
            if prod.get("form"):
                forms.add(prod["form"])
            for other in prod.get("other_ingredients", []):
                combos.add(other)
        return {
            "ingredient_name": ingredient_name,
            "typical_dose_mg": {
                "min": min(doses) if doses else None,
                "max": max(doses) if doses else None,
                "median": statistics.median(doses) if doses else None,
            },
            "common_forms": sorted(forms),
            "product_count": len((detail or {}).get("products", [])),
            "common_combinations": sorted(combos)[:20],
            "source": "DSLD",
        }
    except Exception as e:
        log.debug("[DSLD] %s: %s", ingredient_name, e)
        return None


async def get_top_supplement_dosing(
    disease_name: str,
    session: aiohttp.ClientSession,
) -> dict[str, dict]:
    """DSLD has no disease endpoint — returns empty; enrich per-NP later."""
    return {}