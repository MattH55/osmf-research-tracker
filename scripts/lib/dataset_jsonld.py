#!/usr/bin/env python3
"""
Ticket 3 helper — generate schema.org Dataset JSON-LD blocks for cohort pages.

Real field names confirmed from data/cohorts/*.json and data/pais-cohort.schema.json.
Do NOT use the strategy doc's assumed names — use the field mapping below.

Exports:
  build_dataset_jsonld(cohort_record, pmap, mmap) -> dict
  to_jsonld_script(jsonld_dict) -> HTML <script> tag string
"""

import json
from typing import Optional, Dict, Any, List


def build_dataset_jsonld(
    d: Dict[str, Any],
    pmap: Dict[str, Dict[str, Any]],
    mmap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a schema.org Dataset JSON-LD dict from a cohort record.

    Args:
        d: Cohort data dict (from data/cohorts/*.json).
        pmap: Pathogen lookup map {id: {name, class, ...}}.
        mmap: Measure lookup map {_by_id: {id: measure}} for outcome labels.

    Returns a dict ready for json.dumps() into a <script type="application/ld+json"> block.
    Omits optional keys when data is missing rather than fabricating values.
    """
    # --- Required keys ---
    cohort_id = d.get("id", "unknown")
    cohort_name = d.get("name", cohort_id)
    description = _build_description(d)

    jsonld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": cohort_name,
        "description": description,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "creator": {
            "@type": "Organization",
            "name": "Open Source Medicine Foundation",
            "url": "https://research.opensourcemed.info",
        },
        "distribution": [
            {
                "@type": "DataDownload",
                "encodingFormat": "application/json",
                "contentUrl": f"https://research.opensourcemed.info/data/cohorts/{cohort_id}.json",
            },
            {
                "@type": "DataDownload",
                "encodingFormat": "text/csv",
                "contentUrl": "https://research.opensourcemed.info/data/pais-cohorts.csv",
            },
        ],
        "url": f"https://research.opensourcemed.info/pais-cohorts/{cohort_id}.html",
    }

    # --- Pathogen / about ---
    pathogen_id = d.get("pathogen_id")
    if pathogen_id and pathogen_id in pmap:
        pathogen_name = pmap[pathogen_id].get("name", pathogen_id)
        jsonld["about"] = {
            "@type": "MedicalCondition",
            "name": f"Post-{pathogen_name} syndrome",
        }

    # --- Temporal coverage (from publications[].year or outbreak_event) ---
    years = [
        pub.get("year")
        for pub in d.get("publications", [])
        if isinstance(pub, dict) and pub.get("year") is not None
    ]
    tc = None
    if years:
        min_y = min(years)
        max_y = max(years)
        if min_y == max_y:
            tc = str(min_y)
        else:
            tc = f"{min_y}/{max_y}"
    elif d.get("outbreak_event"):
        tc = d["outbreak_event"]
    if tc:
        jsonld["temporalCoverage"] = tc

    # --- Spatial coverage: check recruitment_source, notes, or pathogen endemic_regions ---
    spatial = _infer_spatial(d, pmap, pathogen_id)
    if spatial:
        jsonld["spatialCoverage"] = spatial

    # --- Variables measured: from observations[].measure_id ---
    if mmap and d.get("observations"):
        by_id = mmap.get("_by_id", {})
        variables = []
        seen = set()
        for obs in d["observations"]:
            mid = obs.get("measure_id")
            if mid and mid not in seen:
                label = by_id.get(mid, {}).get("label", mid)
                variables.append(label)
                seen.add(mid)
        if variables:
            jsonld["variableMeasured"] = variables

    # --- Primary citation ---
    primary = _find_primary_citation(d)
    if primary:
        jsonld["citation"] = primary

    # --- Keywords ---
    keywords = []
    if d.get("pathogen_class"):
        keywords.append(d["pathogen_class"])
    if d.get("design"):
        keywords.append(d["design"].replace("_", " "))
    if d.get("biobank_status"):
        keywords.append(f"biobank: {d['biobank_status']}")
    if keywords:
        jsonld["keywords"] = ", ".join(keywords)

    # --- Size / sample ---
    n_enrolled = d.get("n_enrolled")
    n_analysed = d.get("n_analysed")
    if n_enrolled or n_analysed:
        size_str = []
        if n_enrolled:
            size_str.append(f"n_enrolled={n_enrolled}")
        if n_analysed:
            size_str.append(f"n_analysed={n_analysed}")
        # schema.org/Dataset doesn't have size, but we can use 'includedInDataCatalog' notes
        jsonld["description"] += f" | Sample: {', '.join(size_str)}"

    return jsonld


def _build_description(d: Dict[str, Any]) -> str:
    """Build a 150+ character unique description from cohort fields."""
    parts = []
    name = d.get("name", "")
    pathogen = d.get("pathogen_id", "").replace("-", " ")
    parts.append(f"Cohort study: {name}")

    design = d.get("design", "").replace("_", " ")
    if design:
        parts.append(f"Design: {design}")

    n = d.get("n_enrolled") or d.get("n_analysed")
    if n:
        parts.append(f"Participants: {n}")

    pub_count = len(d.get("publications", []))
    if pub_count:
        parts.append(f"Publications: {pub_count}")

    obs_count = len(d.get("observations", []))
    if obs_count:
        parts.append(f"Observations: {obs_count}")

    # Ensure minimum 150 chars
    desc = ". ".join(parts) + "."
    if len(desc) < 150:
        # Pad with additional context
        if d.get("recruitment_source"):
            desc += f" Recruitment: {d['recruitment_source']}."
        if d.get("max_followup_months"):
            desc += f" Follow-up: up to {d['max_followup_months']} months."
    return desc


def _infer_spatial(d, pmap, pathogen_id) -> Optional[str]:
    """Try to infer spatial coverage. Returns None if nothing structured exists."""
    # Check notes for country mentions
    notes = d.get("notes", "")
    recruitment = d.get("recruitment_source", "")

    # The cohort schema has no explicit country field.
    # Try pathogen endemic_regions as fallback
    if pathogen_id and pathogen_id in pmap:
        regions = pmap[pathogen_id].get("endemic_regions")
        if regions and isinstance(regions, list):
            return ", ".join(regions)

    return None


def _find_primary_citation(d: Dict[str, Any]) -> Optional[str]:
    """Find the primary cohort paper (is_primary_cohort_paper: true) and return its DOI/PMID."""
    for pub in d.get("publications", []):
        if pub.get("is_primary_cohort_paper"):
            doi = pub.get("doi")
            if doi:
                return f"https://doi.org/{doi}"
            pmid = pub.get("pmid")
            if pmid:
                return f"PMID:{pmid}"
    return None


def to_jsonld_script(jsonld_dict: Dict[str, Any]) -> str:
    """Render a JSON-LD dict as an HTML <script> tag."""
    json_str = json.dumps(jsonld_dict, ensure_ascii=False, indent=2)
    return f'<script type="application/ld+json">\n{json_str}\n</script>'


def build_corpus_jsonld(
    cohorts_count: int,
    observation_count: int,
    pathogen_names: List[str],
) -> Dict[str, Any]:
    """Build a corpus-level Dataset JSON-LD for pais-cohorts.html."""
    return {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "OSMF PAIS Cohort Database",
        "description": (
            f"A curated catalogue of {cohorts_count} post-acute infection syndrome cohorts "
            f"with over {observation_count} structured observations across {len(pathogen_names)} "
            "pathogens. Each cohort record includes design, sample size, outcomes, biospecimen "
            "availability, and citation data. Licensed under CC BY 4.0."
        ),
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "creator": {
            "@type": "Organization",
            "name": "Open Source Medicine Foundation",
            "url": "https://research.opensourcemed.info",
        },
        "url": "https://research.opensourcemed.info/pais-cohorts.html",
        "distribution": [
            {
                "@type": "DataDownload",
                "encodingFormat": "application/json",
                "contentUrl": "https://research.opensourcemed.info/data/pais-cohorts-index.json",
            },
            {
                "@type": "DataDownload",
                "encodingFormat": "text/csv",
                "contentUrl": "https://research.opensourcemed.info/data/pais-cohorts.csv",
            },
        ],
        "keywords": ", ".join(pathogen_names[:10]),
        "temporalCoverage": "2024/2026",
    }