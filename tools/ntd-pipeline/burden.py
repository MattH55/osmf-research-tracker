"""
burden.py
---------
Death & disease-burden (DALYs) per NTD.

Burden is the ONE input that has no clean free API. The authoritative source is
IHME's Global Burden of Disease (GBD). This module is built so you swap in a real
GBD export the moment you have one, while still running out-of-the-box on a
clearly-labelled indicative seed.

PRECEDENCE:
  1. If a GBD export CSV is provided (--burden-csv), use it.  <- authoritative
  2. Else fall back to burden_seed.csv shipped here.          <- INDICATIVE ONLY

--- How to get the authoritative numbers (do this before publishing anything) ---
GBD Results Tool:  https://vizhub.healthdata.org/gbd-results/
  Measure  = Deaths, DALYs
  Cause    = the NTD causes under "Neglected tropical diseases and malaria"
  Location = Global (or your region), Year = latest (2021), Sex/Age = All
  Export CSV, then map its `cause_name` to our NTD keys via CAUSE_TO_KEY below.

WHO Global Health Observatory (free OData, no key) is an alternative for some
indicators: https://ghoapi.azureedge.net/api/  (indicator coverage is patchy for NTDs).
"""

from __future__ import annotations
import csv
import os
from typing import Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
_SEED = os.path.join(_HERE, "burden_seed.csv")

# Map GBD cause_name -> our NTD registry key (extend as needed for your export)
CAUSE_TO_KEY = {
    "Dengue": "dengue",
    "Rabies": "rabies",
    "Chagas disease": "chagas",
    "Visceral leishmaniasis": "leishmaniasis",
    "Cutaneous and mucocutaneous leishmaniasis": "leishmaniasis",
    "Schistosomiasis": "schistosomiasis",
    "Cysticercosis": "cysticercosis",
    "Lymphatic filariasis": "lymphatic_filariasis",
    "Onchocerciasis": "onchocerciasis",
    "African trypanosomiasis": "hat",
    "Ascariasis": "sth", "Hookworm disease": "sth", "Trichuriasis": "sth",
    "Cystic echinococcosis": "echinococcosis",
    "Food-borne trematodiases": "foodborne_trematodiases",
    "Leprosy": "leprosy",
    "Trachoma": "trachoma",
    "Scabies": "scabies",
    "Guinea worm disease": "dracunculiasis",
    "Yaws": "yaws",
    # snakebite lives under "Animal contact"/"Venomous animal contact" in GBD
    "Venomous animal contact": "snakebite",
}


def _load_csv(path: str) -> dict:
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = row["key"].strip()
            out[key] = {
                "deaths": _num(row.get("deaths")),
                "dalys": _num(row.get("dalys")),
                "source": row.get("source", ""),
                "confidence": row.get("confidence", ""),
            }
    return out


def _num(x) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load_burden(burden_csv: Optional[str] = None) -> dict:
    """Return {key: {deaths, dalys, source, confidence}}."""
    path = burden_csv if (burden_csv and os.path.exists(burden_csv)) else _SEED
    data = _load_csv(path)
    data["_meta"] = {"path": path, "is_seed": path == _SEED}
    return data


def get(burden: dict, key: str) -> dict:
    return burden.get(key, {"deaths": None, "dalys": None, "source": "", "confidence": ""})
