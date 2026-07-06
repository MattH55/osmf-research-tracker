"""Merge 20 database outputs into NaturalProduct objects."""
from __future__ import annotations

import logging
import re

import aiohttp

from ...models import NPEvidenceTier, NaturalProduct, NPType, SafetyTier
from ..natural_products.score_np import deduplicate_nps
from .normalize import canonical_key, load_np_synonyms, normalize_name

log = logging.getLogger(__name__)


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


def _np_type(value: str | None) -> NPType:
    if not value:
        return NPType.nutraceutical
    try:
        return NPType(value)
    except ValueError:
        return NPType.nutraceutical


def _gmi_tier(tier: str | None) -> NPEvidenceTier:
    return {
        "GOLD": NPEvidenceTier.A,
        "SILVER": NPEvidenceTier.B,
        "BRONZE": NPEvidenceTier.C,
    }.get((tier or "").upper(), NPEvidenceTier.C)


def _examine_tier(grade: str | None) -> NPEvidenceTier:
    try:
        return NPEvidenceTier((grade or "D").upper())
    except ValueError:
        return NPEvidenceTier.D


async def _upsert(
    merged: dict[str, NaturalProduct],
    source_hits: dict[str, dict[str, int]],
    raw_name: str,
    source: str,
    synonym_index: dict,
    session: aiohttp.ClientSession,
    *,
    source_label: str | None = None,
    url: str | None = None,
    tier: NPEvidenceTier | None = None,
    targets: list[str] | None = None,
    findings: str | None = None,
) -> None:
    if not raw_name or len(raw_name) < 2:
        return
    norm = await normalize_name(raw_name, synonym_index, session, resolve_external=False)
    key = canonical_key(norm, raw_name)
    name = norm.get("canonical_name") or raw_name
    cid = norm.get("pubchem_cid")
    canonical_id = str(cid or _slug(name))

    links = {source: url} if url else {}
    hit_label = source_label or source

    if key not in merged:
        merged[key] = NaturalProduct(
            canonical_id=canonical_id,
            name=name,
            common_names=[raw_name] if raw_name != name else [],
            np_type=_np_type(norm.get("np_type")),
            pubchem_cid=cid,
            lotus_wikidata_id=norm.get("lotus_wikidata_id"),
            sources=[source],
            source_links=links,
            target_names=targets or [],
            linked_alteration_ids=targets or [],
            key_findings=findings,
            np_evidence_tier=tier or NPEvidenceTier.D,
        )
    else:
        existing = merged[key]
        merged_links = dict(existing.source_links)
        merged_links.update(links)
        merged[key] = existing.model_copy(update={
            "sources": sorted(set(existing.sources + [source])),
            "source_links": merged_links,
            "common_names": sorted(set(existing.common_names + [raw_name])),
            "target_names": sorted(set(existing.target_names + (targets or []))),
            "linked_alteration_ids": sorted(set(existing.linked_alteration_ids + (targets or []))),
            "key_findings": findings or existing.key_findings,
            "np_evidence_tier": _best_tier(existing.np_evidence_tier, tier or existing.np_evidence_tier),
        })

    hits = source_hits.setdefault(canonical_id, {})
    hits[hit_label] = hits.get(hit_label, 0) + 1


def _best_tier(a: NPEvidenceTier, b: NPEvidenceTier) -> NPEvidenceTier:
    order = {NPEvidenceTier.A: 0, NPEvidenceTier.B: 1, NPEvidenceTier.C: 2, NPEvidenceTier.D: 3}
    return a if order[a] <= order[b] else b


async def build_np_records(
    all_raw: dict,
    identifiers,
    synonym_index: dict,
    session: aiohttp.ClientSession,
) -> tuple[list[NaturalProduct], dict[str, dict[str, int]]]:
    merged: dict[str, NaturalProduct] = {}
    source_hits: dict[str, dict[str, int]] = {}

    for row in all_raw.get("gmi", []):
        await _upsert(
            merged, source_hits, row.get("substance_name", ""), "GreenMedInfo", synonym_index, session,
            source_label=f"GreenMedInfo ({row.get('evidence_tier', 'BRONZE')})",
            url=row.get("url"), tier=_gmi_tier(row.get("evidence_tier")),
            targets=row.get("target_genes"), findings=f"{row.get('study_count', 0)} GMI studies",
        )

    for row in all_raw.get("examine", []):
        await _upsert(
            merged, source_hits, row.get("supplement_name", ""), "Examine.com", synonym_index, session,
            source_label=f"Examine.com ({row.get('evidence_grade', 'C')})",
            url=row.get("url"), tier=_examine_tier(row.get("evidence_grade")),
            findings=row.get("health_outcome"),
        )

    for row in all_raw.get("nccih", []):
        await _upsert(
            merged, source_hits, row.get("np_name", ""), "NCCIH", synonym_index, session,
            source_label="NCCIH", url=row.get("url"), findings=row.get("bottom_line"),
        )

    for row in all_raw.get("ct", []):
        phases = row.get("phases_seen") or []
        label = "ClinicalTrials.gov (Phase 3)" if any("3" in p for p in phases) else "ClinicalTrials.gov (Phase 2)"
        await _upsert(
            merged, source_hits, row.get("np_name", ""), "ClinicalTrials.gov", synonym_index, session,
            source_label=label,
            tier=NPEvidenceTier.B if "Phase 3" in label else NPEvidenceTier.C,
            findings=f"{row.get('trial_count', 0)} trials",
        )

    for row in all_raw.get("pubmed", []):
        st = row.get("study_type", "other")
        label = "PubMed (meta-analysis)" if st == "meta_analysis" else "PubMed (RCT)" if st == "rct" else "PubMed"
        tier = NPEvidenceTier.A if st == "meta_analysis" else NPEvidenceTier.B if st == "rct" else NPEvidenceTier.C
        await _upsert(
            merged, source_hits, row.get("np_name", ""), "PubMed", synonym_index, session,
            source_label=label, tier=tier, findings=row.get("outcome_note") or row.get("key_finding"),
        )

    for source_key, name_field, src_label in (
        ("tcmsp", "herb_name_en", "TCMSP"),
        ("batman", "ingredient_name", "BATMAN-TCM"),
        ("imppat", "chemical_name", "IMPPAT"),
        ("etcm", "herb_name", "ETCM"),
        ("symmap", "herb_name_en", "SymMap"),
    ):
        for row in all_raw.get(source_key, []):
            await _upsert(
                merged, source_hits, row.get(name_field, ""), src_label, synonym_index, session,
                source_label=src_label, targets=row.get("target_genes"),
                tier=NPEvidenceTier.C,
            )

    for row in all_raw.get("lotus", []):
        await _upsert(merged, source_hits, row.get("name", ""), "LOTUS", synonym_index, session, source_label="LOTUS", tier=NPEvidenceTier.D)

    for row in all_raw.get("coconut", []):
        await _upsert(merged, source_hits, row.get("name", ""), "COCONUT", synonym_index, session, source_label="COCONUT", tier=NPEvidenceTier.D)

    for row in all_raw.get("npass", []):
        await _upsert(
            merged, source_hits, row.get("compound_name", ""), "NPASS", synonym_index, session,
            source_label="NPASS", targets=[row.get("target_gene", "")], tier=NPEvidenceTier.C,
        )

    for row in all_raw.get("chembl_np", []):
        await _upsert(
            merged, source_hits, row.get("name", ""), "ChEMBL-NP", synonym_index, session,
            source_label="ChEMBL-NP", targets=row.get("targets_hit", []), tier=NPEvidenceTier.C,
        )

    for row in all_raw.get("pubchem", []):
        name = row.get("name") or f"CID-{row.get('cid', '')}"
        await _upsert(merged, source_hits, name, "PubChem BioAssay", synonym_index, session, source_label="PubChem BioAssay", tier=NPEvidenceTier.D)

    for row in all_raw.get("dukes", []):
        await _upsert(merged, source_hits, row.get("chemical_name", ""), "Dr. Duke's", synonym_index, session, source_label="Dr. Duke's", tier=NPEvidenceTier.D)

    for row in all_raw.get("knapsack", []):
        await _upsert(merged, source_hits, row.get("metabolite_name", ""), "KNApSAcK", synonym_index, session, source_label="KNApSAcK", tier=NPEvidenceTier.D)

    for row in all_raw.get("phenol", []):
        await _upsert(merged, source_hits, row.get("compound_name", ""), "Phenol-Explorer", synonym_index, session, source_label="Phenol-Explorer", tier=NPEvidenceTier.D)

    for row in all_raw.get("foodb", []):
        await _upsert(merged, source_hits, row.get("compound_name", ""), "FooDB", synonym_index, session, source_label="FooDB", tier=NPEvidenceTier.D)

    nps = deduplicate_nps(list(merged.values()))
    return nps, source_hits