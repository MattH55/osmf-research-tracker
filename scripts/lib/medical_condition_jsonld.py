#!/usr/bin/env python3
"""
Ticket 4 helper — generate schema.org MedicalCondition JSON-LD blocks for disease pages.

Real field names confirmed from data/disease-intelligence/*.json.
Do NOT use the strategy doc's assumed names — use the field mapping below.

Exports:
  build_medical_condition_jsonld(disease_data, agent_slugs) -> dict
  to_jsonld_script(jsonld_dict) -> HTML <script> tag string
"""

import json
from typing import Optional, Dict, Any, List


def build_medical_condition_jsonld(
    data: Dict[str, Any],
    agent_slugs: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build a schema.org MedicalCondition JSON-LD dict from a disease-intelligence record.

    Args:
        data: Disease-intelligence JSON dict (from data/disease-intelligence/<slug>.json).
        agent_slugs: Optional lookup {agent_name: agent_slug} for resolving agent URLs.

    Returns a dict ready for json.dumps() into a <script type="application/ld+json"> block.
    Omits optional keys when data is missing rather than fabricating values.
    """
    slug = data.get("slug", "")
    condition = data.get("condition", {})
    page = data.get("page", {})
    identifiers = data.get("identifiers", {})
    therapies = data.get("therapeutics", {})

    canonical_label = condition.get("name") or page.get("title", "").split(" — ")[0] or slug.replace("-", " ").title()
    description = page.get("description", "")
    canonical_url = page.get("canonical", f"https://research.opensourcemed.info/disease-intelligence/{slug}.html")

    jsonld = {
        "@context": "https://schema.org",
        "@type": "MedicalCondition",
        "name": canonical_label,
        "url": canonical_url,
    }

    # ---- Alternate names ----
    aliases = condition.get("alternateNames", [])
    if aliases:
        jsonld["alternateName"] = aliases[:10]  # cap at 10

    # ---- Medical code (MONDO) ----
    mondo_id = identifiers.get("mondo_id")
    if mondo_id:
        jsonld["code"] = {
            "@type": "MedicalCode",
            "codeValue": mondo_id,
            "codingSystem": "MONDO",
        }

    # ---- Description ----
    if description:
        jsonld["description"] = description

    # ---- Possible treatments (from merged_ranked therapeutics) ----
    merged = therapies.get("merged_ranked", [])
    if merged:
        treatments = []
        seen = set()
        for agent in merged[:15]:  # cap at 15
            name = agent.get("name", "")
            if not name or name in seen:
                continue
            seen.add(name)
            treatment = {"@type": "Drug", "name": name}
            # Resolve agent URL if slugs lookup available
            if agent_slugs and name in agent_slugs:
                agent_slug = agent_slugs[name]
                treatment["url"] = f"https://research.opensourcemed.info/agents/{agent_slug}/"
            treatments.append(treatment)
        if treatments:
            jsonld["possibleTreatment"] = treatments

    # ---- Associated anatomy (from alteration targets, if available) ----
    # (Omitted — alterations are molecular/pathological targets, not anatomical sites)

    # ---- Source organization ----
    jsonld["sourceOrganization"] = {
        "@type": "Organization",
        "name": "Open Source Medicine Foundation",
        "url": "https://opensourcemed.info",
    }

    # ---- Last reviewed ----
    date_modified = page.get("dateModified")
    if date_modified:
        jsonld["lastReviewed"] = date_modified

    # ---- Keywords ----
    keywords = page.get("keywords", [])
    if keywords:
        jsonld["keywords"] = ", ".join(keywords[:8])

    return jsonld


def to_jsonld_script(jsonld_dict: Dict[str, Any]) -> str:
    """Render a JSON-LD dict as an HTML <script> tag."""
    json_str = json.dumps(jsonld_dict, ensure_ascii=False)
    return f'<script type="application/ld+json">\n{json_str}\n</script>'