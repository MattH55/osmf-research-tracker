"""Layer 1 — IHME GBD epidemiological remission transition rates."""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import aiohttp

from ...config import PACKAGE_DIR
from ...http_util import get_json

log = logging.getLogger(__name__)

IHME_BASE = "https://api.healthdata.org/gbd-api/v1"
CAUSE_MAP_PATH = PACKAGE_DIR / "seeds" / "gbd_cause_map.json"

MEASURE_REMISSION = 9
METRIC_RATE = 3
LOCATION_USA = 102
AGE_ALL = 22
SEX_BOTH = 3


def _load_cause_map() -> dict[str, int]:
    if CAUSE_MAP_PATH.exists():
        data = json.loads(CAUSE_MAP_PATH.read_text(encoding="utf-8"))
        return {k: int(v) for k, v in data.get("by_slug", data).items()}
    return {}


async def lookup_cause_id(disease_name: str, session: aiohttp.ClientSession) -> int | None:
    try:
        data = await get_json(
            session,
            f"{IHME_BASE}/cause",
            params={"q": disease_name, "format": "json"},
        )
        if not data:
            return None
        rows = data if isinstance(data, list) else data.get("data", data.get("results", []))
        if rows:
            return int(rows[0].get("cause_id") or rows[0].get("id"))
    except Exception as e:
        log.debug("[GBD] cause lookup failed for '%s': %s", disease_name, e)
    return None


def rate_to_annual_probability(rate_per_100k: float) -> float:
    """Convert GBD rate (per 100,000 person-years) to approximate annual P(remission)."""
    if rate_per_100k <= 0:
        return 0.0
    return 1.0 - math.exp(-rate_per_100k / 100_000.0)


async def get_gbd_remission_rate(
    disease_slug: str,
    disease_name: str,
    session: aiohttp.ClientSession,
    *,
    location_id: int = LOCATION_USA,
    year: int = 2021,
) -> dict | None:
    cause_map = _load_cause_map()
    cause_id = cause_map.get(disease_slug)
    if not cause_id:
        cause_id = await lookup_cause_id(disease_name, session)
    if not cause_id:
        return None

    try:
        data = await get_json(
            session,
            f"{IHME_BASE}/result",
            params={
                "cause_id": cause_id,
                "measure_id": MEASURE_REMISSION,
                "metric_id": METRIC_RATE,
                "age_id": AGE_ALL,
                "sex_id": SEX_BOTH,
                "location_id": location_id,
                "year_id": year,
                "format": "json",
            },
        )
        if not data:
            return None
        rows = data if isinstance(data, list) else data.get("data", [])
        if not rows:
            return None
        row = rows[0]
        mean = float(row.get("val") or row.get("mean") or 0)
        lower = float(row.get("lower") or row.get("lower_bound") or mean)
        upper = float(row.get("upper") or row.get("upper_bound") or mean)
        return {
            "gbd_epi_remission_rate_per_100k": mean,
            "gbd_epi_lower": lower,
            "gbd_epi_upper": upper,
            "gbd_epi_annual_probability": round(rate_to_annual_probability(mean), 6),
            "gbd_cause_id": cause_id,
            "gbd_location_id": location_id,
            "gbd_year": year,
            "data_tier": "epidemiological",
            "note": "EPIDEMIOLOGICAL transition rate (DisMod), not clinical remission criteria",
            "confidence": "low",
        }
    except Exception as e:
        log.debug("[GBD] remission fetch failed for %s: %s", disease_slug, e)
        return None