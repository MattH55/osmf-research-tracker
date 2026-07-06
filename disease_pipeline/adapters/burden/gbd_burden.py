"""IHME GBD USA burden — DALYs and deaths."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import aiohttp

from ...config import PACKAGE_DIR
from ...http_util import get_json
from ..remission.gbd import CAUSE_MAP_PATH, IHME_BASE, LOCATION_USA, AGE_ALL, SEX_BOTH, lookup_cause_id

log = logging.getLogger(__name__)

BURDEN_SEED_PATH = PACKAGE_DIR / "seeds" / "gbd_burden_usa.json"

MEASURE_DEATHS = 1
MEASURE_DALYS = 2
METRIC_NUMBER = 1
METRIC_RATE = 3


def _load_seed() -> dict[str, dict]:
    if not BURDEN_SEED_PATH.exists():
        return {}
    data = json.loads(BURDEN_SEED_PATH.read_text(encoding="utf-8"))
    return data.get("by_slug", data)


def _load_cause_map() -> dict[str, int]:
    if CAUSE_MAP_PATH.exists():
        data = json.loads(CAUSE_MAP_PATH.read_text(encoding="utf-8"))
        return {k: int(v) for k, v in data.get("by_slug", data).items()}
    return {}


async def _fetch_measure(
    session: aiohttp.ClientSession,
    *,
    cause_id: int,
    measure_id: int,
    metric_id: int,
    location_id: int,
    year: int,
) -> float | None:
    try:
        data = await get_json(
            session,
            f"{IHME_BASE}/result",
            params={
                "cause_id": cause_id,
                "measure_id": measure_id,
                "metric_id": metric_id,
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
        return float(row.get("val") or row.get("mean") or 0)
    except Exception as e:
        log.debug("[GBD burden] measure %s failed: %s", measure_id, e)
        return None


async def fetch_gbd_burden(
    disease_slug: str,
    disease_name: str,
    session: aiohttp.ClientSession,
    *,
    location_id: int = LOCATION_USA,
    year: int = 2021,
) -> dict | None:
    cause_map = _load_cause_map()
    cause_id = cause_map.get(disease_slug) or await lookup_cause_id(disease_name, session)
    if not cause_id:
        return None

    dalys = await _fetch_measure(
        session, cause_id=cause_id, measure_id=MEASURE_DALYS,
        metric_id=METRIC_NUMBER, location_id=location_id, year=year,
    )
    deaths = await _fetch_measure(
        session, cause_id=cause_id, measure_id=MEASURE_DEATHS,
        metric_id=METRIC_NUMBER, location_id=location_id, year=year,
    )
    daly_rate = await _fetch_measure(
        session, cause_id=cause_id, measure_id=MEASURE_DALYS,
        metric_id=METRIC_RATE, location_id=location_id, year=year,
    )
    death_rate = await _fetch_measure(
        session, cause_id=cause_id, measure_id=MEASURE_DEATHS,
        metric_id=METRIC_RATE, location_id=location_id, year=year,
    )

    if dalys is None and deaths is None:
        return None

    return {
        "gbd_cause_id": cause_id,
        "gbd_year": year,
        "gbd_location_id": location_id,
        "us_dalys": dalys,
        "us_deaths": deaths,
        "us_daly_rate_per_100k": daly_rate,
        "us_death_rate_per_100k": death_rate,
        "data_tier": "epidemiological",
        "source": "IHME GBD",
    }


def get_gbd_burden_from_seed(slug: str) -> dict | None:
    row = _load_seed().get(slug)
    return dict(row) if row else None