"""Apply canonical professional disease display names to web JSON."""
from __future__ import annotations

from .adapters.remission.slug_map import display_names_for_slug


def apply_canonical_names(data: dict) -> dict:
    """Normalize condition + page metadata to manifest display names."""
    slug = data.get("slug", "")
    cond = data.setdefault("condition", {})
    short, full = display_names_for_slug(
        slug,
        fallback_short=cond.get("shortName"),
        fallback_full=cond.get("name"),
    )
    cond["shortName"] = short
    cond["name"] = full

    page = data.setdefault("page", {})
    page["title"] = f"{short} — RepurpOS | OpenSourceMedicine"
    page["breadcrumbName"] = f"{short} Intelligence"
    page["description"] = (
        f"Structured alterations and therapeutics for {full}: "
        f"molecular targets, clinical biomarkers, phenotypes, and ranked drugs "
        f"from Open Targets, HPO, ChEMBL, and DGIdb."
    )
    page["keywords"] = [
        f"{short} biomarkers",
        f"{short} therapeutics",
        "disease intelligence",
        "drug repurposing",
    ]
    if page.get("hero"):
        page["hero"] = (
            f"Disease intelligence for {full}: "
            f"{data.get('summary', {}).get('alteration_count', 0)} alterations and "
            f"{data.get('summary', {}).get('therapeutic_counts', {}).get('merged', 0)} "
            f"ranked therapeutics from curated public databases."
        )
    return data