"""Dr. Duke's Phytochemical Database."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def _match_disease_key(disease_name: str, activity_map: dict) -> list[str]:
    lower = disease_name.lower()
    for key, terms in activity_map.items():
        if key in lower or lower in key:
            return terms
    for key, terms in activity_map.items():
        if any(tok in lower for tok in key.split()):
            return terms
    return activity_map.get(lower.replace(" ", "-"), [])


async def query_disease(disease_name: str, dukes_data: dict, activity_map: dict) -> list[dict]:
    terms = _match_disease_key(disease_name, activity_map)
    if not terms:
        return []

    seen: set[str] = set()
    out: list[dict] = []
    for term in terms:
        key = term.lower().replace(" ", "-")
        for rec in dukes_data.get(key, []):
            chem = rec.get("chemical_name", "")
            if not chem or chem in seen:
                continue
            seen.add(chem)
            out.append({
                "chemical_name": chem,
                "activity": rec.get("activity", term),
                "source_plants": rec.get("source_plants", []),
                "low_dose_mg_kg": rec.get("low_dose_mg_kg"),
                "high_dose_mg_kg": rec.get("high_dose_mg_kg"),
                "source": "Dr. Duke's",
            })
    return out