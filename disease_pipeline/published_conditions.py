"""Rules for which RepurpOS conditions appear on the public index."""
from __future__ import annotations

import json
from pathlib import Path

_MANIFEST_PATH = Path(__file__).parent / "seeds" / "disease_db_100_manifest.json"

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


def db100_index_slugs() -> frozenset[str] | None:
    """Unique RepurpOS slugs covering disease_db_100.json, when manifest exists."""
    if not _MANIFEST_PATH.exists():
        return None
    rows = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    slugs = {row["slug"] for row in rows if row.get("slug")}
    return frozenset(slugs) if slugs else None


def on_db100_index(data: dict) -> bool:
    slugs = db100_index_slugs()
    if slugs is None:
        return True
    return data.get("slug", "") in slugs


def exclusion_reason(data: dict) -> str | None:
    slug = data.get("slug", "")
    if slug in EXCLUDED_SLUGS:
        keep = DUPLICATE_SLUGS[slug]
        return f"duplicate of {keep}"
    if biomarker_count(data) <= 0:
        return "no biomarkers"
    return None