"""Layer 3 ground truth — disease_db_100.json manual remission entries."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ...config import PACKAGE_DIR
from .slug_map import slug_for_label

log = logging.getLogger(__name__)

DB100_PATH = PACKAGE_DIR / "seeds" / "disease_db_100.json"

_cache_by_slug: dict[str, dict] | None = None
_cache_by_label: dict[str, dict] | None = None


def _row_to_remission(row: dict) -> dict:
    sources = {}
    if row.get("sources"):
        sources["manual"] = row["sources"]
    return {
        "disease": row.get("disease", ""),
        "spontaneous_remission_rate": row.get("spontaneous_remission_rate"),
        "best_intervention_remission_rate": row.get("best_intervention_remission_rate"),
        "drug_free_remission_rate": row.get("drug_free_remission_rate"),
        "chronicity_rate": row.get("chronicity_rate"),
        "relapse_rate_after_remission": row.get("relapse_rate_after_remission"),
        "remission_definition": row.get("remission_definition"),
        "gap_size": row.get("gap_size"),
        "barrier_type": row.get("barrier_type"),
        "barrier_detail": row.get("barrier_detail"),
        "last_soc_change": row.get("last_soc_change"),
        "outdated_treatments": row.get("outdated_treatments"),
        "adjunctive_emerging": row.get("adjunctive_emerging"),
        "frontier_signal": row.get("frontier_signal"),
        "follow_up_reference": row.get("follow_up_reference"),
        "sources": sources,
        "confidence": "high",
        "source_locked": True,
        "data_tier": "clinical_manual",
        "last_updated": "2026-06-30",
        "notes": (
            "Manually curated from landmark trials, registries, and guidelines "
            "(disease_db_100.json). Protected from automated overwrite."
        ),
    }


def load_db100_by_slug() -> dict[str, dict]:
    global _cache_by_slug, _cache_by_label
    if _cache_by_slug is not None:
        return _cache_by_slug

    if not DB100_PATH.exists():
        log.warning("disease_db_100.json not found at %s", DB100_PATH)
        _cache_by_slug = {}
        _cache_by_label = {}
        return _cache_by_slug

    payload = json.loads(DB100_PATH.read_text(encoding="utf-8"))
    by_slug: dict[str, dict] = {}
    by_label: dict[str, dict] = {}

    for row in payload.get("diseases", []):
        label = row.get("disease", "")
        if not label:
            continue
        rem = _row_to_remission(row)
        by_label[label] = rem
        slug = slug_for_label(label)
        # Prefer first entry per slug; duplicates keep richer manual data
        if slug not in by_slug:
            by_slug[slug] = rem

    _cache_by_slug = by_slug
    _cache_by_label = by_label
    log.info("[DB100] loaded remission data for %d slugs", len(by_slug))
    return by_slug


def get_db100_remission(slug: str, disease_name: str = "") -> dict | None:
    by_slug = load_db100_by_slug()
    if slug in by_slug:
        return dict(by_slug[slug])
    # Fuzzy: match disease name to label keys
    if disease_name:
        dn = disease_name.lower()
        for label, rem in (_cache_by_label or {}).items():
            if label.lower() in dn or dn in label.lower():
                return dict(rem)
    return None


def db100_row_for_page(slug: str) -> dict:
    """Flat dict for chronic-disease-interventions HTML generator."""
    rem = get_db100_remission(slug)
    if not rem:
        return {}
    return {
        "disease": rem.get("disease", ""),
        "spontaneous_remission_rate": rem.get("spontaneous_remission_rate", ""),
        "best_intervention_remission_rate": rem.get("best_intervention_remission_rate", ""),
        "gap_size": rem.get("gap_size", ""),
        "primary_barrier": rem.get("barrier_type", ""),
        "barrier_detail": rem.get("barrier_detail", ""),
        "notes": rem.get("barrier_detail") or rem.get("notes", ""),
        "last_soc_change": rem.get("last_soc_change", ""),
        "outdated_treatments": rem.get("outdated_treatments", ""),
        "adjunctive_emerging": rem.get("adjunctive_emerging", ""),
        "frontier_signal": rem.get("frontier_signal", ""),
    }