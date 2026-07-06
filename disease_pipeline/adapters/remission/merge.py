"""Merge remission layers — DB100 ground truth wins on locked fields."""
from __future__ import annotations

from datetime import datetime, timezone

LOCKED_FIELDS = frozenset({
    "spontaneous_remission_rate",
    "best_intervention_remission_rate",
    "drug_free_remission_rate",
    "chronicity_rate",
    "relapse_rate_after_remission",
    "remission_definition",
    "gap_size",
    "barrier_type",
    "barrier_detail",
    "last_soc_change",
    "outdated_treatments",
    "adjunctive_emerging",
    "frontier_signal",
    "follow_up_reference",
})


def _pick_best_pubmed(pubmed_rows: list[dict]) -> dict:
    """Choose highest-confidence PubMed extraction for supplemental fields."""
    best: dict = {}
    best_conf = -1
    conf_rank = {"high": 3, "medium": 2, "low": 1}
    for row in pubmed_rows:
        ext = row.get("extracted") or {}
        rank = conf_rank.get((ext.get("confidence") or "").lower(), 0)
        if rank >= best_conf:
            best_conf = rank
            best = ext
    return best


def merge_remission_layers(
    *,
    db100: dict | None,
    gbd: dict | None,
    pubmed_rows: list[dict],
) -> dict:
    merged: dict = {
        "layers": [],
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }

    if db100:
        merged.update({k: v for k, v in db100.items() if k not in ("layers",)})
        merged["layers"].append("disease_db_100")
        merged["source_locked"] = True
        merged["confidence"] = db100.get("confidence", "high")

    if gbd:
        for k, v in gbd.items():
            if k not in merged or merged.get(k) is None:
                merged[k] = v
        merged["layers"].append("gbd_epidemiological")

    if pubmed_rows:
        merged["pubmed_extractions"] = pubmed_rows
        merged["layers"].append("pubmed_systematic_reviews")
        best = _pick_best_pubmed(pubmed_rows)
        if best and not merged.get("source_locked"):
            field_map = {
                "spontaneous_remission_rate": "spontaneous_remission_rate",
                "treatment_remission_rate": "best_intervention_remission_rate",
                "drug_free_remission_rate": "drug_free_remission_rate",
                "chronicity_rate": "chronicity_rate",
                "relapse_rate_after_remission": "relapse_rate_after_remission",
                "remission_definition_used": "remission_definition",
            }
            for src, dst in field_map.items():
                if best.get(src) and not merged.get(dst):
                    merged[dst] = best[src]
            if not merged.get("confidence"):
                merged["confidence"] = best.get("confidence", "medium")
        elif best:
            # Only fill gaps not covered by locked manual data
            if not merged.get("relapse_rate_after_remission") and best.get("relapse_rate_after_remission"):
                merged["relapse_rate_after_remission"] = best["relapse_rate_after_remission"]
            if not merged.get("remission_definition") and best.get("remission_definition_used"):
                merged["remission_definition"] = best["remission_definition_used"]

    if not merged.get("confidence"):
        merged["confidence"] = "low" if gbd else "unknown"

    return merged