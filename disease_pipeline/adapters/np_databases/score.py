"""Evidence-weighted repurposing score across 20 NP databases."""
from __future__ import annotations

from ...models import NPEvidenceTier, NaturalProduct, SafetyTier

SOURCE_WEIGHTS: dict[str, float] = {
    "Examine.com (A)": 10,
    "GreenMedInfo (GOLD)": 9,
    "PubMed (meta-analysis)": 9,
    "Examine.com (B)": 7,
    "GreenMedInfo (SILVER)": 6,
    "ClinicalTrials.gov (Phase 3)": 7,
    "NPASS": 5,
    "ChEMBL-NP": 5,
    "TCMSP": 4,
    "BATMAN-TCM": 4,
    "IMPPAT": 4,
    "ETCM": 4,
    "SymMap": 4,
    "ClinicalTrials.gov (Phase 2)": 4,
    "Examine.com (C)": 3,
    "GreenMedInfo (BRONZE)": 3,
    "PubMed (RCT)": 3,
    "Dr. Duke's": 2,
    "KNApSAcK": 2,
    "Phenol-Explorer": 2,
    "FooDB": 2,
    "PubChem BioAssay": 1,
    "COCONUT": 1,
    "LOTUS": 1,
    "NCCIH": 1,
}


def _tier_from_sources(np: NaturalProduct) -> NPEvidenceTier:
    if np.meta_analysis_count >= 1:
        return NPEvidenceTier.A
    if np.rct_count >= 2 or np.systematic_review_count >= 1:
        return NPEvidenceTier.B
    if np.ct_trial_count >= 1 or np.linked_alteration_ids:
        return NPEvidenceTier.C
    return np.np_evidence_tier


def compute_repurposing_score(
    np: NaturalProduct,
    disease_name: str,
    *,
    source_hits: dict[str, int] | None = None,
    type_a_genes: set[str] | None = None,
    nccih_mentions_condition: bool = False,
) -> float:
    score = 0.0
    hits = source_hits or {}

    for label, count in hits.items():
        weight = SOURCE_WEIGHTS.get(label, 1)
        score += weight * count

    if np.rct_count >= 1:
        score += 5
    if hits.get("TCMSP", 0) and hits.get("IMPPAT", 0):
        score += 3
    if type_a_genes and np.target_names:
        overlap = type_a_genes & set(np.target_names)
        if overlap:
            score += 3
    if nccih_mentions_condition:
        score += 2

    if np.safety_tier == SafetyTier.caution:
        score -= 5
    elif np.safety_tier == SafetyTier.avoid:
        score -= 15

    return min(max(score, 0.0), 100.0)