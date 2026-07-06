"""Export natural products using the same web schema as repurposed drugs."""
from __future__ import annotations

from ...display_np_names import resolve_np_display_name
from ...np_publications import resolve_np_publications
from ...models import AgentClinicalEvidence, NaturalProduct, NPEvidenceTier, NPType, SafetyTier
from ...output.web_export import (
    DRUG_TYPE_LABELS,
    PHASE_LABELS,
    TIER_LABELS,
    _export_clinical_evidence,
    _item_id,
)

NP_TIER_TO_EVIDENCE = {
    NPEvidenceTier.A: "A",
    NPEvidenceTier.B: "B",
    NPEvidenceTier.C: "C",
    NPEvidenceTier.D: "C",
}


def _np_external_links(np: NaturalProduct) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    if np.pubchem_cid:
        links.append({
            "label": "PubChem",
            "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{np.pubchem_cid}",
        })
    for cid in np.chembl_ids[:1]:
        links.append({
            "label": "ChEMBL",
            "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{cid}/",
        })
    for src, url in np.source_links.items():
        if url:
            links.append({"label": src, "url": url})
    return links


def _phase_from_np(np: NaturalProduct, evidence: AgentClinicalEvidence | None) -> int:
    from .np_evidence import _max_phase_from_evidence

    phase = _max_phase_from_evidence(evidence)
    if phase:
        return phase
    if np.ct_trial_count >= 3:
        return 2
    if np.ct_trial_count >= 1:
        return 1
    return 0


def natural_product_from_row(row: dict) -> NaturalProduct:
    if row.get("source_type") == "natural_product":
        np_type = row.get("drug_type", "nutraceutical")
        try:
            np_type_enum = NPType(np_type)
        except ValueError:
            np_type_enum = NPType.nutraceutical
        tier_raw = row.get("evidence_tier", "D")
        try:
            tier_enum = NPEvidenceTier(tier_raw)
        except ValueError:
            tier_enum = NPEvidenceTier.D
        try:
            safety = SafetyTier(row.get("safety_tier", "unknown"))
        except ValueError:
            safety = SafetyTier.unknown
        return NaturalProduct(
            canonical_id=row["canonical_id"],
            name=row["name"],
            common_names=row.get("common_names", [row["name"]]),
            np_type=np_type_enum,
            mechanism=row.get("mechanism"),
            target_names=[t.strip() for t in (row.get("via_alteration") or "").split(",") if t.strip()],
            chembl_ids=[row["chembl_id"]] if row.get("chembl_id") else [],
            sources=row.get("sources", []),
            source_links={
                link["label"]: link["url"]
                for link in row.get("external_links", [])
                if link.get("label") and link.get("url")
            },
            safety_tier=safety,
            np_evidence_tier=tier_enum,
            key_findings=row.get("key_findings"),
            score=float(row.get("score", 0)),
            ct_trial_count=int(
                (row.get("clinical_evidence") or {}).get("counts", {}).get("trials_registry", 0)
            ),
        )
    return NaturalProduct.model_validate(row)


def export_natural_product(
    slug: str,
    np: NaturalProduct,
    *,
    evidence: AgentClinicalEvidence | None = None,
) -> dict:
    tier = NP_TIER_TO_EVIDENCE.get(np.np_evidence_tier, "C")
    if isinstance(tier, NPEvidenceTier):
        tier = NP_TIER_TO_EVIDENCE.get(tier, "C")
    tier_str = tier.value if hasattr(tier, "value") else str(tier)
    np_type = np.np_type.value if hasattr(np.np_type, "value") else str(np.np_type)
    max_phase = _phase_from_np(np, evidence)
    pubmed_n = 0
    if evidence:
        pubmed_n = int(evidence.counts.get("association_total") or evidence.counts.get("total_publications") or 0)

    display_name = resolve_np_display_name(
        np.name,
        common_names=np.common_names,
        canonical_id=np.canonical_id,
    )
    common_names = list(np.common_names or [])
    if display_name and display_name.lower() not in {c.lower() for c in common_names}:
        common_names.insert(0, display_name)

    out: dict = {
        "id": _item_id(slug, "np", np.canonical_id),
        "canonical_id": np.canonical_id,
        "name": display_name,
        "drug_type": np_type,
        "drug_type_label": DRUG_TYPE_LABELS.get(np_type, np_type.replace("_", " ").title()),
        "mechanism": np.mechanism,
        "max_phase": max_phase,
        "phase_label": PHASE_LABELS.get(max_phase, "Preclinical" if max_phase == 0 else f"Phase {max_phase}"),
        "approved_indications": [],
        "source_type": "natural_product",
        "via_alteration": ", ".join(np.target_names[:2]) or None,
        "sources": np.sources,
        "evidence_tier": tier_str,
        "evidence_tier_label": TIER_LABELS.get(tier_str, tier_str),
        "repurposing_signal": False,
        "pubmed_count": pubmed_n,
        "score": int(round(np.score)),
        "chembl_id": np.chembl_ids[0] if np.chembl_ids else None,
        "external_links": _np_external_links(np),
        "safety_tier": np.safety_tier.value if hasattr(np.safety_tier, "value") else str(np.safety_tier),
        "common_names": common_names[:6],
        "key_findings": np.key_findings,
    }
    if evidence:
        out["clinical_evidence"] = _export_clinical_evidence(evidence)
    return out


def _attach_publications(
    row: dict,
    *,
    gmi_articles: list[dict] | None = None,
    disease_name: str | None = None,
) -> dict:
    pubs = resolve_np_publications(
        row,
        gmi_articles=gmi_articles,
        disease_name=disease_name,
        limit=3,
    )
    if pubs:
        row["supporting_publications"] = pubs
    return row


def export_natural_products_page(
    slug: str,
    nps: list[NaturalProduct],
    evidence_map: dict[str, AgentClinicalEvidence],
    *,
    gmi_articles: list[dict] | None = None,
    disease_name: str | None = None,
) -> tuple[list[dict], dict[str, dict]]:
    rows = [
        _attach_publications(
            export_natural_product(slug, np, evidence=evidence_map.get(np.canonical_id)),
            gmi_articles=gmi_articles,
            disease_name=disease_name,
        )
        for np in nps
    ]
    ev_export = {
        k: _export_clinical_evidence(v) for k, v in evidence_map.items()
    }
    return rows, ev_export