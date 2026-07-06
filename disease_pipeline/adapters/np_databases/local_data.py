"""Local bulk data loaders — Dr. Duke's, IMPPAT, NPASS, FooDB, TCMSP."""
from __future__ import annotations

import csv
import json
import logging
import sqlite3
from collections import defaultdict
from pathlib import Path

from ...config import PACKAGE_DIR

log = logging.getLogger(__name__)

SEEDS = PACKAGE_DIR / "seeds"
DUKES_CSV = SEEDS / "dukes_bulk.csv"
IMPPAT_DB = SEEDS / "imppat.db"
NPASS_DB = SEEDS / "npass.db"
FOODB_DB = SEEDS / "foodb.db"
TCMSP_DIR = SEEDS / "tcmsp"
DUKE_MAP_PATH = SEEDS / "duke_activity_map.json"

_dukes_cache: dict | None = None
_duke_map_cache: dict | None = None


def load_duke_activity_map() -> dict[str, list[str]]:
    global _duke_map_cache
    if _duke_map_cache is not None:
        return _duke_map_cache
    if DUKE_MAP_PATH.exists():
        _duke_map_cache = json.loads(DUKE_MAP_PATH.read_text(encoding="utf-8"))
    else:
        _duke_map_cache = {}
    return _duke_map_cache


def load_dukes_data() -> dict[str, list[dict]]:
    """Activity → list of chemical records from Dr. Duke's CSV."""
    global _dukes_cache
    if _dukes_cache is not None:
        return _dukes_cache

    _dukes_cache = defaultdict(list)
    if not DUKES_CSV.exists():
        log.debug("[Dukes] seeds/dukes_bulk.csv not found — skipping")
        return _dukes_cache

    with DUKES_CSV.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            activity = (row.get("Activity") or row.get("activity") or "").strip()
            chemical = (row.get("Chemical") or row.get("chemical") or "").strip()
            plant = (row.get("Plant") or row.get("plant") or "").strip()
            if not activity or not chemical:
                continue
            key = activity.lower().replace(" ", "-")
            _dukes_cache[key].append({
                "chemical_name": chemical,
                "activity": activity,
                "source_plants": [plant] if plant else [],
                "low_dose_mg_kg": row.get("LowDoseMgKgBody") or row.get("LowDose"),
                "high_dose_mg_kg": row.get("HighDose") or row.get("HighDoseMgKgBody"),
            })
    return _dukes_cache


def open_sqlite(path: Path) -> sqlite3.Connection | None:
    if not path.exists():
        return None
    return sqlite3.connect(str(path))


def get_local_data() -> dict:
    """Bundle of local data handles for the pipeline."""
    return {
        "dukes": load_dukes_data(),
        "duke_activity_map": load_duke_activity_map(),
        "imppat_db": open_sqlite(IMPPAT_DB),
        "npass_db": open_sqlite(NPASS_DB),
        "foodb_db": open_sqlite(FOODB_DB),
        "tcmsp": _load_tcmsp_joined(),
    }


def _load_tcmsp_joined() -> dict:
    """Load pre-downloaded TCMSP CSV joins if present."""
    if not TCMSP_DIR.exists():
        return {}
    data: dict = {"herbs": {}, "by_target": defaultdict(list)}
    herb_path = TCMSP_DIR / "herb.csv"
    if herb_path.exists():
        with herb_path.open(encoding="utf-8", errors="replace", newline="") as f:
            for row in csv.DictReader(f):
                hid = row.get("herb_id") or row.get("Herb ID")
                if hid:
                    data["herbs"][hid] = row
    return data