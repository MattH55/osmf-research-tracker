"""Deduplicate and merge agent records across sources."""
from __future__ import annotations

import re

from .clinical_trials import search_trials_for_biomarker
from .models import AgentRecord, NormalizedBiomarker

RXNORM_CACHE: dict[str, str] = {}


def _norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _merge_key(rec: AgentRecord) -> str:
    if rec.agent_id.get("rxnorm"):
        return f"rxnorm:{rec.agent_id['rxnorm']}"
    if rec.agent_id.get("chembl_id"):
        return f"chembl:{rec.agent_id['chembl_id']}"
    return f"name:{_norm_name(rec.agent_name)}"


def _tier_rank(tier: str) -> int:
    return {"mechanistic": 3, "clinical": 2, "correlative": 1}.get(tier, 0)


def _pick_direction(a: str, b: str) -> str:
    if a == b:
        return a
    if a == "unclear":
        return b
    if b == "unclear":
        return a
    return a


def merge_agents(records: list[AgentRecord], norm: NormalizedBiomarker) -> list[AgentRecord]:
    merged: dict[str, AgentRecord] = {}
    for rec in records:
        key = _merge_key(rec)
        if key not in merged:
            merged[key] = rec
            continue
        prev = merged[key]
        # merge sources
        seen = {(s.database, s.pubmed_id, s.url) for s in prev.sources}
        for s in rec.sources:
            k = (s.database, s.pubmed_id, s.url)
            if k not in seen:
                prev.sources.append(s)
                seen.add(k)
        # upgrade tier
        if _tier_rank(rec.evidence_tier) > _tier_rank(prev.evidence_tier):
            prev.evidence_tier = rec.evidence_tier
        prev.direction_of_effect = _pick_direction(prev.direction_of_effect, rec.direction_of_effect)  # type: ignore
        # merge potency if missing
        if not prev.potency.get("value") and rec.potency.get("value"):
            prev.potency = rec.potency
        # merge ids
        prev.agent_id.update({k: v for k, v in rec.agent_id.items() if v})

    out = list(merged.values())

    # Clinical trial cross-reference — only for non-clinical tier, capped for latency
    candidates = [
        r for r in out
        if r.evidence_tier == "correlative" and not r.clinical_trial_refs
    ][:8]
    for rec in candidates:
        try:
            ncts = search_trials_for_biomarker(norm, rec.agent_name)
        except Exception:
            ncts = []
        if ncts:
            rec.clinical_trial_refs = list(dict.fromkeys(rec.clinical_trial_refs + ncts))
            rec.evidence_tier = "clinical"

    out.sort(
        key=lambda r: (
            _tier_rank(r.evidence_tier),
            -(r.potency.get("value") or 0) if isinstance(r.potency.get("value"), (int, float)) else 0,
            -len(r.sources),
            r.agent_name,
        ),
        reverse=True,
    )
    return out