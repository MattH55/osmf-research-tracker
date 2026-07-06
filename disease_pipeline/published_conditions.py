"""Rules for which RepurpOS conditions appear on the public index."""
from __future__ import annotations

# Canonical slug -> duplicate slug(s) merged or superseded.
DUPLICATE_SLUGS: dict[str, str] = {
    "ankylosing-spondylitis-axial-spondyloarthropathy": "ankylosing-spondylitis",
    "dementia-and-cognitive-aging": "alzheimers-disease-and-other-dementias",
    "insomnia-sleep-disorders": "insomnia",
    "stroke": "ischemic-stroke",
    "mecfs": "myalgic-encephalomyelitis-chronic-fatigue-syndrome",
    "nafld-mash": "metabolic-dysfunction-associated-steatohepatitis",
}

EXCLUDED_SLUGS: frozenset[str] = frozenset(DUPLICATE_SLUGS.keys())


def biomarker_count(data: dict) -> int:
    """Alterations are the biomarker inventory for RepurpOS."""
    summary = data.get("summary", {})
    return int(summary.get("alteration_count", len(data.get("alterations", []))))


def clinical_biomarker_count(data: dict) -> int:
    summary = data.get("summary", {})
    by_type = summary.get("alteration_counts_by_type", {})
    if by_type:
        return int(by_type.get("B", 0))
    return sum(1 for alt in data.get("alterations", []) if alt.get("type") == "B")


def is_publishable(data: dict) -> bool:
    slug = data.get("slug", "")
    if slug in EXCLUDED_SLUGS:
        return False
    return biomarker_count(data) > 0


def exclusion_reason(data: dict) -> str | None:
    slug = data.get("slug", "")
    if slug in EXCLUDED_SLUGS:
        keep = DUPLICATE_SLUGS[slug]
        return f"duplicate of {keep}"
    if biomarker_count(data) <= 0:
        return "no biomarkers"
    return None