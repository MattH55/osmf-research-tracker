"""Module 6 — Merge, deduplicate, and score alterations and therapeutics."""
from __future__ import annotations

from ..models import Alteration, AlterationType, EvidenceTier, Therapeutic

_TIER_RANK = {EvidenceTier.A: 0, EvidenceTier.B: 1, EvidenceTier.C: 2}
_FREQ_RANK = {"obligate": 0, "very_frequent": 1, "frequent": 2, "occasional": 3}


def _best_tier(a: EvidenceTier, b: EvidenceTier) -> EvidenceTier:
    return a if _TIER_RANK[a] <= _TIER_RANK[b] else b


def _best_frequency(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    return a if _FREQ_RANK.get(a, 99) <= _FREQ_RANK.get(b, 99) else b


def _alteration_tier(sources: int, pubmed_count: int) -> EvidenceTier:
    if sources >= 3 or (sources >= 2 and pubmed_count > 50):
        return EvidenceTier.A
    if sources >= 2 or pubmed_count > 10:
        return EvidenceTier.B
    return EvidenceTier.C


def _therapeutic_tier(drug: Therapeutic) -> EvidenceTier:
    if drug.max_phase >= 4:
        return EvidenceTier.A
    if drug.max_phase >= 3 or (drug.max_phase >= 2 and len(drug.sources) >= 2):
        return EvidenceTier.B
    return EvidenceTier.C


def _therapeutic_score(drug: Therapeutic) -> int:
    if drug.source_type == "natural_agent":
        return drug.score or 30
    tier = drug.evidence_tier
    tier_bonus = {"A": 10, "B": 5, "C": 0}[tier.value]
    direct_bonus = 10 if drug.source_type == "direct" else 0
    source_bonus = min(len(drug.sources) * 5, 15)
    return drug.max_phase * 20 + source_bonus + direct_bonus + tier_bonus


def score_alterations(alterations: list[Alteration]) -> list[Alteration]:
    merged: dict[str, Alteration] = {}
    for alt in alterations:
        key = alt.canonical_id.lower()
        if key not in merged:
            merged[key] = alt
            continue
        existing = merged[key]
        sources = list(dict.fromkeys(existing.sources + alt.sources))
        source_ids = {**existing.source_ids, **alt.source_ids}
        pubmed = max(existing.pubmed_count, alt.pubmed_count)
        tier = _alteration_tier(len(sources), pubmed)
        merged[key] = existing.model_copy(
            update={
                "sources": sources,
                "source_ids": source_ids,
                "pubmed_count": pubmed,
                "evidence_tier": tier,
                "frequency_label": _best_frequency(existing.frequency_label, alt.frequency_label),
                "frequency_pct": existing.frequency_pct or alt.frequency_pct,
                "definition": existing.definition or alt.definition,
                "direction": existing.direction or alt.direction,
            }
        )

    scored = []
    for alt in merged.values():
        tier = _alteration_tier(len(alt.sources), alt.pubmed_count)
        scored.append(alt.model_copy(update={"evidence_tier": tier}))

    return sorted(
        scored,
        key=lambda a: (_TIER_RANK[a.evidence_tier], -len(a.sources), -a.pubmed_count, a.name),
    )


def _therapeutic_key(drug: Therapeutic) -> str:
    if drug.chembl_id:
        return drug.chembl_id.lower()
    return drug.name.lower().strip()


def _merge_drug(existing: Therapeutic, drug: Therapeutic) -> Therapeutic:
    sources = list(dict.fromkeys(existing.sources + drug.sources))
    approved = list(dict.fromkeys(existing.approved_indications + drug.approved_indications))
    in_direct = existing.source_type == "direct" or drug.source_type == "direct"
    merged = existing.model_copy(
        update={
            "sources": sources,
            "approved_indications": approved,
            "max_phase": max(existing.max_phase, drug.max_phase),
            "pubmed_count": max(existing.pubmed_count, drug.pubmed_count),
            "mechanism": existing.mechanism or drug.mechanism,
            "source_type": "direct" if in_direct else "via_biomarker",
            "via_alteration": existing.via_alteration or drug.via_alteration,
            "repurposing_signal": False if in_direct else True,
            "chembl_id": existing.chembl_id or drug.chembl_id,
            "rxnorm_id": existing.rxnorm_id or drug.rxnorm_id,
        }
    )
    tier = _therapeutic_tier(merged)
    return merged.model_copy(update={"evidence_tier": tier, "score": _therapeutic_score(merged)})


def _dedupe_list(drugs: list[Therapeutic]) -> list[Therapeutic]:
    seen: dict[str, Therapeutic] = {}
    for drug in drugs:
        key = _therapeutic_key(drug)
        if key not in seen:
            tier = _therapeutic_tier(drug)
            seen[key] = drug.model_copy(update={"evidence_tier": tier, "score": _therapeutic_score(drug)})
        else:
            seen[key] = _merge_drug(seen[key], drug)
    return list(seen.values())


def score_therapeutics(
    direct: list[Therapeutic],
    via_biomarker: list[Therapeutic],
    natural: list[Therapeutic] | None = None,
) -> tuple[list[Therapeutic], list[Therapeutic], list[Therapeutic], list[Therapeutic]]:
    merged_direct = _dedupe_list(direct)
    merged_via = _dedupe_list(via_biomarker)
    merged_natural = _dedupe_list(natural or [])

    all_merged: dict[str, Therapeutic] = {}
    for drug in merged_direct + merged_via + merged_natural:
        key = _therapeutic_key(drug)
        if key not in all_merged:
            all_merged[key] = drug
        else:
            all_merged[key] = _merge_drug(all_merged[key], drug)

    merged_all = sorted(all_merged.values(), key=lambda d: -d.score)
    return merged_direct, merged_via, merged_natural, merged_all


# Back-compat aliases
merge_alterations = score_alterations
merge_therapeutics = lambda d, v, n=None: score_therapeutics(d, v, n)[3]
dedupe_direct = _dedupe_list
dedupe_via_biomarker = _dedupe_list