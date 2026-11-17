"""Condition list for the non-drug evidence map: every RepurpOS condition plus the post-viral set."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Post-viral conditions the tracker follows that are not RepurpOS conditions (or need a better query).
POST_VIRAL = [
    {"slug": "long-covid", "name": "Long COVID", "query": "Long COVID", "page": "/long-covid.html"},
    {"slug": "pots", "name": "Postural orthostatic tachycardia syndrome (POTS)", "query": "Postural Orthostatic Tachycardia Syndrome", "page": "/pots.html"},
    {"slug": "mcas", "name": "Mast cell activation syndrome (MCAS)", "query": "Mast Cell Activation Syndrome", "page": "/mcas.html"},
    {"slug": "gulf-war-illness", "name": "Gulf War Illness", "query": "Gulf War Illness", "page": "/gulf-war-illness.html"},
    {"slug": "lyme-ptlds", "name": "Lyme disease and post-treatment Lyme disease syndrome", "query": "Lyme Disease", "page": "/lyme.html"},
]


# Combined condition names search badly as one phrase; query each part.
QUERY_OVERRIDES = {
    "myalgic-encephalomyelitis-chronic-fatigue-syndrome": "Myalgic Encephalomyelitis OR Chronic Fatigue Syndrome",
    "hivaids": "HIV OR AIDS",
    "post-acute-covidvaccination-syndrome": "Post-Acute COVID-19 Vaccination Syndrome OR post-vaccination syndrome OR post-COVID-19 vaccine",
}


def load_conditions() -> list[dict]:
    """Return [{slug, name, query, page, repurpos}] sorted by name. RepurpOS conditions query by their name."""
    out: dict[str, dict] = {}
    for f in sorted((ROOT / "data" / "disease-intelligence").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        cond = d.get("condition") or {}
        name = cond.get("name") or d["slug"].replace("-", " ").title()
        out[d["slug"]] = {
            "slug": d["slug"], "name": name,
            "query": QUERY_OVERRIDES.get(d["slug"]) or " OR ".join(p.strip() for p in name.split("/")),
            "page": f"/chronic-disease-interventions/{d['slug']}.html"
            if (ROOT / "chronic-disease-interventions" / f"{d['slug']}.html").exists() else None,
            "repurpos": f"/disease-intelligence/{d['slug']}.html"
            if (ROOT / "disease-intelligence" / f"{d['slug']}.html").exists() else None,
        }
    for c in POST_VIRAL:
        out.setdefault(c["slug"], {**c, "repurpos": None})
    return sorted(out.values(), key=lambda c: c["name"].lower())
