"""NP-7 — NP-specific scoring, deduplication, and safety application."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ...config import NP_SAFETY_PATH
from ...models import NPEvidenceTier, NaturalProduct, NPType, SafetyTier

log = logging.getLogger(__name__)

_SAFETY_ORDER = {
    SafetyTier.avoid: 0,
    SafetyTier.caution: 1,
    SafetyTier.unknown: 2,
    SafetyTier.generally_safe: 3,
    SafetyTier.GRAS: 4,
}

_TIER_ORDER = {NPEvidenceTier.A: 0, NPEvidenceTier.B: 1, NPEvidenceTier.C: 2, NPEvidenceTier.D: 3}


def load_safety_map() -> dict:
    path = Path(NP_SAFETY_PATH)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safety_tier_from_str(value: str | None) -> SafetyTier:
    if not value:
        return SafetyTier.unknown
    try:
        return SafetyTier(value)
    except ValueError:
        return SafetyTier.unknown


def _np_type_from_str(value: str | None) -> NPType:
    if not value:
        return NPType.nutraceutical
    mapping = {
        "vitamin": NPType.nutraceutical,
        "mineral": NPType.nutraceutical,
        "other": NPType.nutraceutical,
    }
    if value in mapping:
        return mapping[value]
    try:
        return NPType(value)
    except ValueError:
        return NPType.nutraceutical


def assign_np_evidence_tier(np: NaturalProduct) -> NPEvidenceTier:
    if np.meta_analysis_count >= 1 or np.rct_count >= 3:
        return NPEvidenceTier.A
    if 1 <= np.rct_count <= 2 or np.systematic_review_count >= 1:
        return NPEvidenceTier.B
    if np.ct_trial_count >= 2 or (np.linked_alteration_ids and np.pubchem_bioassay_count > 5):
        return NPEvidenceTier.C
    return NPEvidenceTier.D


def score_np(np: NaturalProduct) -> float:
    score = 0.0

    score += min(np.meta_analysis_count * 20, 40)
    score += min(np.rct_count * 8, 32)
    score += min(np.systematic_review_count * 10, 20)
    score += min(np.ct_trial_count * 3, 9)

    score += min(len(np.linked_alteration_ids) * 10, 30)

    safety_pts = {
        SafetyTier.GRAS: 10,
        SafetyTier.generally_safe: 7,
        SafetyTier.caution: 2,
        SafetyTier.unknown: 0,
        SafetyTier.avoid: -20,
    }
    score += safety_pts.get(np.safety_tier, 0)

    if np.traditional_systems:
        score += 5
    if np.traditional_indication:
        score += 5

    return min(max(score, 0.0), 100.0)


def apply_safety(nps: list[NaturalProduct], safety_map: dict) -> list[NaturalProduct]:
    out: list[NaturalProduct] = []
    for np in nps:
        keys = [np.name.lower(), *(c.lower() for c in np.common_names)]
        entry = None
        for k in keys:
            if k in safety_map:
                entry = safety_map[k]
                break
        if not entry:
            out.append(np)
            continue
        tier = _safety_tier_from_str(entry.get("safety_tier"))
        interactions = entry.get("interactions") or entry.get("known_interactions") or []
        contraindications = entry.get("contraindications", [])
        out.append(np.model_copy(update={
            "safety_tier": tier,
            "herb_drug_interactions": sorted(set(np.herb_drug_interactions + interactions)),
            "contraindications": sorted(set(np.contraindications + contraindications)),
        }))
    return out


def _dedup_key(np: NaturalProduct) -> str:
    if np.pubchem_cid:
        return f"cid:{np.pubchem_cid}"
    return f"name:{np.name.lower()}"


def _best_tier(a: NPEvidenceTier, b: NPEvidenceTier) -> NPEvidenceTier:
    return a if _TIER_ORDER[a] <= _TIER_ORDER[b] else b


def _worst_safety(a: SafetyTier, b: SafetyTier) -> SafetyTier:
    return a if _SAFETY_ORDER[a] <= _SAFETY_ORDER[b] else b


def deduplicate_nps(nps: list[NaturalProduct]) -> list[NaturalProduct]:
    merged: dict[str, NaturalProduct] = {}

    for np in nps:
        key = _dedup_key(np)
        if key not in merged:
            merged[key] = np
            continue
        existing = merged[key]
        merged[key] = existing.model_copy(update={
            "sources": sorted(set(existing.sources + np.sources)),
            "common_names": sorted(set(existing.common_names + np.common_names + [np.name])),
            "meta_analysis_count": max(existing.meta_analysis_count, np.meta_analysis_count),
            "rct_count": max(existing.rct_count, np.rct_count),
            "systematic_review_count": max(existing.systematic_review_count, np.systematic_review_count),
            "ct_trial_count": max(existing.ct_trial_count, np.ct_trial_count),
            "linked_alteration_ids": sorted(set(existing.linked_alteration_ids + np.linked_alteration_ids)),
            "target_names": sorted(set(existing.target_names + np.target_names)),
            "chembl_ids": sorted(set(existing.chembl_ids + np.chembl_ids)),
            "active_constituents": sorted(set(existing.active_constituents + np.active_constituents)),
            "herb_drug_interactions": sorted(set(existing.herb_drug_interactions + np.herb_drug_interactions)),
            "contraindications": sorted(set(existing.contraindications + np.contraindications)),
            "traditional_systems": sorted(set(existing.traditional_systems + np.traditional_systems)),
            "key_findings": (
                np.key_findings
                if np.key_findings and (not existing.key_findings or len(np.key_findings) > len(existing.key_findings))
                else existing.key_findings
            ),
            "mechanism": np.mechanism or existing.mechanism,
            "scientific_name": np.scientific_name or existing.scientific_name,
            "pubchem_cid": np.pubchem_cid or existing.pubchem_cid,
            "lotus_wikidata_id": np.lotus_wikidata_id or existing.lotus_wikidata_id,
            "pubchem_bioassay_count": max(existing.pubchem_bioassay_count, np.pubchem_bioassay_count),
            "np_evidence_tier": _best_tier(existing.np_evidence_tier, np.np_evidence_tier),
            "safety_tier": _worst_safety(existing.safety_tier, np.safety_tier),
        })

    result = list(merged.values())
    for np in result:
        np.np_evidence_tier = assign_np_evidence_tier(np)
        np.score = score_np(np)
    result.sort(key=lambda x: x.score, reverse=True)
    return result