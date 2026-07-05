"""Module 8 — Assemble final disease page JSON record."""
from __future__ import annotations

from datetime import datetime, timezone

from ..adapters.normalize import seed_key
from ..models import AgentClinicalEvidence, Alteration, AlterationType, DiseaseIdentifiers, DiseasePageData, Therapeutic


def assemble_output(
    identifiers: DiseaseIdentifiers,
    alterations: list[Alteration],
    merged_direct: list[Therapeutic],
    merged_via: list[Therapeutic],
    merged_all: list[Therapeutic],
    *,
    merged_natural: list[Therapeutic] | None = None,
    natural_review: dict | None = None,
    therapeutic_evidence: dict[str, AgentClinicalEvidence] | None = None,
    sources_queried: list[str] | None = None,
    build_time_seconds: float = 0.0,
    phase: int = 1,
) -> DiseasePageData:
    alt_counts: dict[str, int] = {}
    for alt in alterations:
        key = alt.alteration_type.value if isinstance(alt.alteration_type, AlterationType) else str(alt.alteration_type)
        alt_counts[key] = alt_counts.get(key, 0) + 1

    meta = {
        "schema_version": "1.0",
        "phase": phase,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sources_queried": sources_queried or [],
        "alteration_counts": alt_counts,
        "therapeutic_counts": {
            "direct": len(merged_direct),
            "via_biomarker": len(merged_via),
            "natural": len(merged_natural or []),
            "merged_total": len(merged_all),
        },
        "build_time_seconds": build_time_seconds,
        "evidence_drugs": len(therapeutic_evidence or {}),
    }

    if natural_review:
        meta["natural_review"] = natural_review

    return DiseasePageData(
        identifiers=identifiers,
        alterations=alterations,
        therapeutics_direct=merged_direct,
        therapeutics_via_biomarker=merged_via,
        therapeutics_natural=merged_natural or [],
        therapeutics_merged=merged_all,
        therapeutic_evidence=therapeutic_evidence or {},
        pipeline_meta=meta,
    )


def to_web_export(page: DiseasePageData, *, cap_display: bool = False) -> dict:
    from .web_export import to_web_json
    return to_web_json(page, cap_display=cap_display)


def to_spec_json(page: DiseasePageData) -> dict:
    """Export JSON matching the spec output schema."""
    slug = seed_key(page.identifiers.name)
    return {
        "schema_version": page.pipeline_meta.get("schema_version", "1.0"),
        "generated_at": page.pipeline_meta.get("generated_at"),
        "disease": {
            "name": page.identifiers.name,
            "slug": slug,
            "identifiers": page.identifiers.model_dump(),
        },
        "alterations": [a.model_dump(mode="json") for a in page.alterations],
        "therapeutics": {
            "direct": [t.model_dump(mode="json") for t in page.therapeutics_direct],
            "via_biomarker": [t.model_dump(mode="json") for t in page.therapeutics_via_biomarker],
            "natural": [t.model_dump(mode="json") for t in page.therapeutics_natural],
            "merged_ranked": [t.model_dump(mode="json") for t in page.therapeutics_merged],
        },
        "therapeutic_evidence": {
            k: v.model_dump(mode="json") for k, v in page.therapeutic_evidence.items()
        },
        "pipeline_meta": page.pipeline_meta,
    }


# Back-compat alias
assemble_page = assemble_output