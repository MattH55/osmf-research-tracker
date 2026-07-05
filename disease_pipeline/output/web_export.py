"""Transform pipeline output into web-ready DiseaseIntelligencePage JSON."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ..models import AgentClinicalEvidence, Alteration, DiseasePageData, Therapeutic

SCHEMA_VERSION = "1.1.0"
SITE_BASE = "https://research.opensourcemed.info"

TYPE_LABELS = {
    "A": "Molecular",
    "B": "Lab / Clinical",
    "C": "Scales & PROs",
    "D": "Pathology",
    "E": "Functional",
}

SUBTYPE_LABELS = {
    "gene": "Gene",
    "protein": "Protein",
    "metabolite": "Metabolite",
    "lab_value": "Lab value",
    "scale": "Clinical scale",
    "pathology": "Pathological finding",
    "functional_test": "Functional test",
    "imaging": "Imaging metric",
}

TIER_LABELS = {"A": "Strong", "B": "Moderate", "C": "Emerging"}

DIRECTION_LABELS = {
    "elevated": "Elevated",
    "reduced": "Reduced",
    "abnormal": "Abnormal",
}

DRUG_TYPE_LABELS = {
    "small_molecule": "Small molecule",
    "biologic": "Biologic",
    "cell_therapy": "Cell therapy",
    "gene_therapy": "Gene therapy",
    "device": "Device",
    "supplement": "Supplement",
    "herbal": "Herbal",
    "nutraceutical": "Nutraceutical",
    "lifestyle": "Lifestyle",
    "psychedelic": "Psychedelic",
}

PHASE_LABELS = {
    0: "Preclinical",
    1: "Phase I",
    2: "Phase II",
    3: "Phase III",
    4: "Approved",
}

DISCLAIMER = (
    "Alterations and therapeutics are aggregated from public databases "
    "(Open Targets, HPO, ChEMBL, DGIdb, and others). "
    "Natural agents are candidates from OSMF narrative reviews on "
    "opensourcemed.info/chronic-disease.html — not approved treatments. "
    "This page is for research orientation only — not medical advice."
)

DISPLAY_LIMITS = {
    "alterations": 80,
    "therapeutics_direct": 40,
    "therapeutics_via": 40,
    "therapeutics_merged": 50,
}


def web_slug(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"\s*\([^)]*\)", "", s)
    for suffix in (" mellitus", " (essential)"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s_]+", "-", s).strip("-")


def _short_name(full_name: str) -> str:
    s = full_name
    for cut in (" Mellitus", " (Crohn's/UC)", " and Other Dementias"):
        if cut in s:
            s = s.replace(cut, "")
    return s.strip() or full_name


def _item_id(slug: str, kind: str, key: str) -> str:
    safe = re.sub(r"[^\w.-]+", "-", key.lower()).strip("-")[:80]
    return f"{slug}:{kind}:{safe}"


def _alteration_links(alt: Alteration) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    ids = alt.source_ids or {}
    if ids.get("HPO"):
        links.append({"label": "HPO", "url": f"https://hpo.jax.org/app/browse/term/{ids['HPO']}"})
    if ids.get("UniProt"):
        links.append({"label": "UniProt", "url": f"https://www.uniprot.org/uniprotkb/{ids['UniProt']}"})
    if ids.get("Ensembl"):
        links.append({"label": "Ensembl", "url": f"https://ensembl.org/Homo_sapiens/Gene/Summary?g={ids['Ensembl']}"})
    if ids.get("LOINC"):
        links.append({"label": "LOINC", "url": f"https://loinc.org/{ids['LOINC']}"})
    if alt.subtype == "gene" and alt.name:
        links.append({"label": "Open Targets", "url": f"https://platform.opentargets.org/target/{ids.get('Ensembl', alt.name)}"})
    return links


def _therapeutic_links(drug: Therapeutic, *, natural_review: dict | None = None) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    if drug.chembl_id:
        links.append({"label": "ChEMBL", "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{drug.chembl_id}/"})
    if drug.chembl_id and drug.chembl_id.upper().startswith("CHEMBL"):
        links.append({"label": "Open Targets", "url": f"https://platform.opentargets.org/drug/{drug.chembl_id}"})
    if drug.source_type == "natural_agent":
        page_url = (natural_review or {}).get("source_page") or "https://opensourcemed.info/chronic-disease.html"
        links.append({"label": "OSMF Review", "url": page_url})
        review = (natural_review or {}).get("review") or {}
        if review.get("url"):
            links.append({"label": "Citation", "url": review["url"]})
    return links


def _export_alteration(slug: str, alt: Alteration) -> dict:
    t = alt.alteration_type.value if hasattr(alt.alteration_type, "value") else str(alt.alteration_type)
    return {
        "id": _item_id(slug, "alt", alt.canonical_id),
        "canonical_id": alt.canonical_id,
        "name": alt.name,
        "type": t,
        "type_label": TYPE_LABELS.get(t, t),
        "subtype": alt.subtype,
        "subtype_label": SUBTYPE_LABELS.get(alt.subtype, alt.subtype.replace("_", " ").title()),
        "direction": alt.direction,
        "direction_label": DIRECTION_LABELS.get(alt.direction or "", None),
        "frequency_label": alt.frequency_label,
        "frequency_pct": alt.frequency_pct,
        "sources": alt.sources,
        "source_ids": alt.source_ids,
        "evidence_tier": alt.evidence_tier.value,
        "evidence_tier_label": TIER_LABELS.get(alt.evidence_tier.value, alt.evidence_tier.value),
        "pubmed_count": alt.pubmed_count,
        "definition": alt.definition,
        "external_links": _alteration_links(alt),
    }


def _export_clinical_evidence(ev: AgentClinicalEvidence) -> dict:
    return {
        "drug_canonical_id": ev.drug_canonical_id,
        "drug_name": ev.drug_name,
        "clinical_trials": [t.model_dump() for t in ev.clinical_trials],
        "literature": [lit.model_dump() for lit in ev.literature],
        "counts": ev.counts,
        "search_links": ev.search_links,
    }


def _export_therapeutic(
    slug: str,
    drug: Therapeutic,
    *,
    evidence: AgentClinicalEvidence | None = None,
    natural_review: dict | None = None,
) -> dict:
    tier = drug.evidence_tier.value
    out = {
        "id": _item_id(slug, "drug", drug.chembl_id or drug.canonical_id),
        "canonical_id": drug.canonical_id,
        "name": drug.name,
        "drug_type": drug.drug_type,
        "drug_type_label": DRUG_TYPE_LABELS.get(drug.drug_type, drug.drug_type.replace("_", " ").title()),
        "mechanism": drug.mechanism,
        "max_phase": drug.max_phase,
        "phase_label": PHASE_LABELS.get(drug.max_phase, f"Phase {drug.max_phase}"),
        "approved_indications": drug.approved_indications,
        "source_type": drug.source_type,
        "via_alteration": drug.via_alteration,
        "sources": drug.sources,
        "evidence_tier": tier,
        "evidence_tier_label": TIER_LABELS.get(tier, tier),
        "repurposing_signal": drug.repurposing_signal,
        "pubmed_count": drug.pubmed_count,
        "score": drug.score,
        "chembl_id": drug.chembl_id,
        "external_links": _therapeutic_links(drug, natural_review=natural_review),
    }
    if evidence:
        out["clinical_evidence"] = _export_clinical_evidence(evidence)
    return out


def _tier_sort_key_alt(a: dict) -> tuple:
    return ({"A": 0, "B": 1, "C": 2}[a["evidence_tier"]], -len(a["sources"]), -a["pubmed_count"], a["name"])


def _tier_sort_key_drug(d: dict) -> tuple:
    return (-d["score"], -d["max_phase"], {"A": 0, "B": 1, "C": 2}[d["evidence_tier"]], d["name"])


def to_web_json(page: DiseasePageData, *, cap_display: bool = False) -> dict:
    slug = web_slug(page.identifiers.name)
    short = _short_name(page.identifiers.name)
    date_mod = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    meta = page.pipeline_meta

    ev_map = page.therapeutic_evidence or {}
    natural_review = meta.get("natural_review")
    all_alts = sorted((_export_alteration(slug, a) for a in page.alterations), key=_tier_sort_key_alt)

    def _exp_drug(d: Therapeutic) -> dict:
        return _export_therapeutic(
            slug,
            d,
            evidence=ev_map.get(d.canonical_id),
            natural_review=natural_review,
        )

    direct = sorted((_exp_drug(t) for t in page.therapeutics_direct), key=_tier_sort_key_drug)
    via = sorted((_exp_drug(t) for t in page.therapeutics_via_biomarker), key=_tier_sort_key_drug)
    natural = sorted((_exp_drug(t) for t in page.therapeutics_natural), key=_tier_sort_key_drug)
    merged = sorted((_exp_drug(t) for t in page.therapeutics_merged), key=_tier_sort_key_drug)

    if cap_display:
        alts_out = all_alts[: DISPLAY_LIMITS["alterations"]]
        direct_out = direct[: DISPLAY_LIMITS["therapeutics_direct"]]
        via_out = via[: DISPLAY_LIMITS["therapeutics_via"]]
        natural_out = natural
        merged_out = merged[: DISPLAY_LIMITS["therapeutics_merged"]]
    else:
        alts_out, direct_out, via_out, natural_out, merged_out = all_alts, direct, via, natural, merged

    alt_counts = meta.get("alteration_counts", {})
    tc = meta.get("therapeutic_counts", {})

    return {
        "schema_version": SCHEMA_VERSION,
        "slug": slug,
        "id": f"{slug}-intelligence",
        "condition": {
            "name": page.identifiers.name,
            "shortName": short,
            "alternateNames": [],
        },
        "identifiers": {
            k: v
            for k, v in page.identifiers.model_dump().items()
            if k != "name" and v is not None
        },
        "page": {
            "title": f"{short} — Disease Intelligence | OSMF",
            "breadcrumbName": f"{short} Intelligence",
            "description": (
                f"Structured alterations and therapeutics for {page.identifiers.name}: "
                f"molecular targets, clinical biomarkers, phenotypes, and ranked drugs "
                f"from Open Targets, HPO, ChEMBL, and DGIdb."
            ),
            "keywords": [
                f"{short} biomarkers",
                f"{short} therapeutics",
                "disease intelligence",
                "drug repurposing",
            ],
            "canonical": f"{SITE_BASE}/disease-intelligence/{slug}.html",
            "hero": (
                f"Disease intelligence for {page.identifiers.name}: "
                f"{len(page.alterations)} alterations and "
                f"{len(page.therapeutics_merged)} ranked therapeutics "
                f"from curated public databases."
            ),
            "dateModified": date_mod,
        },
        "summary": {
            "alteration_count": len(page.alterations),
            "therapeutic_counts": {
                "direct": tc.get("direct", len(page.therapeutics_direct)),
                "via_biomarker": tc.get("via_biomarker", len(page.therapeutics_via_biomarker)),
                "natural": tc.get("natural", len(page.therapeutics_natural)),
                "merged": tc.get("merged_total", len(page.therapeutics_merged)),
            },
            "alteration_counts_by_type": alt_counts,
            "sources_queried": meta.get("sources_queried", []),
            "pipeline_phase": meta.get("phase", 1),
            "build_time_seconds": meta.get("build_time_seconds", 0),
            "generated_at": meta.get("generated_at"),
            "display_limits": DISPLAY_LIMITS if cap_display else None,
            "displayed_alterations": len(alts_out),
            "displayed_therapeutics_merged": len(merged_out),
            "evidence_drugs": meta.get("evidence_drugs", len(ev_map)),
            "natural_product_count": len(page.natural_products),
        },
        "categories": TYPE_LABELS,
        "filters": ["A", "B", "C", "D", "E", "direct", "via_biomarker", "natural_agent", "repurposing"],
        "alterations": alts_out,
        "therapeutics": {
            "direct": direct_out,
            "via_biomarker": via_out,
            "natural": natural_out,
            "merged_ranked": merged_out,
        },
        "natural_review": natural_review,
        "clinical_evidence": {
            k: _export_clinical_evidence(v) for k, v in ev_map.items()
        },
        "natural_products": [
            np.model_dump(mode="json") for np in page.natural_products
        ],
        "disclaimer": DISCLAIMER,
    }


def from_spec_json(spec: dict, *, cap_display: bool = False) -> dict:
    """Convert pipeline spec JSON (from to_spec_json) to web schema."""
    from ..models import AgentClinicalEvidence, DiseaseIdentifiers

    disease = spec.get("disease", {})
    ids = disease.get("identifiers", {})
    meta = spec.get("pipeline_meta", {})
    ther = spec.get("therapeutics", {})

    page = DiseasePageData(
        identifiers=DiseaseIdentifiers(
            name=ids.get("name") or disease.get("name", ""),
            mondo_id=ids.get("mondo_id"),
            efo_id=ids.get("efo_id"),
            omim_id=ids.get("omim_id"),
            orpha_id=ids.get("orpha_id"),
            mesh_id=ids.get("mesh_id"),
            umls_cui=ids.get("umls_cui"),
        ),
        alterations=[Alteration(**a) for a in spec.get("alterations", [])],
        therapeutics_direct=[Therapeutic(**t) for t in ther.get("direct", [])],
        therapeutics_via_biomarker=[Therapeutic(**t) for t in ther.get("via_biomarker", [])],
        therapeutics_natural=[Therapeutic(**t) for t in ther.get("natural", [])],
        therapeutics_merged=[Therapeutic(**t) for t in ther.get("merged_ranked", [])],
        therapeutic_evidence={
            k: AgentClinicalEvidence(**v) for k, v in spec.get("therapeutic_evidence", {}).items()
        },
        pipeline_meta=meta,
    )
    return to_web_json(page, cap_display=cap_display)