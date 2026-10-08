"""Module 6: grading + cross-phenotype matrix + evidence map (build spec
section 7). Pure logic over the loaded tables — no network calls.
"""
from __future__ import annotations

from .config import GENOME_WIDE_SIGNIFICANCE, SUGGESTIVE_UPPER
from .grading import grade_all
from .models import Association

CellState = str  # "significant" | "suggestive" | "tested_null" | "not_tested" | "conflicting"


def _released_phenotype_ids(tables: dict) -> list[str]:
    return [p.phenotype_id for p in tables["phenotypes"] if p.search_state != "not_searched"]


def _row_variant_ids(level: str, row_id: str, tables: dict) -> set[str]:
    if level == "locus":
        locus = next(l for l in tables["loci"] if l.locus_id == row_id)
        return {
            v.variant_id
            for v in tables["variants"]
            if v.chrom == locus.chrom and v.pos is not None and locus.start <= v.pos <= locus.end
        }
    if level == "gene":
        locus_ids = {lg.locus_id for lg in tables["locus_gene"] if lg.ensembl_gene_id == row_id}
        variant_ids: set[str] = set()
        for lid in locus_ids:
            variant_ids |= _row_variant_ids("locus", lid, tables)
        return variant_ids
    raise ValueError(level)


def _cell(associations: list[Association], phenotype_id: str) -> dict:
    hits = [a for a in associations if a.phenotype_id == phenotype_id]
    if not hits:
        return {"state": "not_tested", "grade": None}

    sig_directions = {a.effect_allele: (a.beta_or_or or 0) > 1 for a in hits if a.result == "significant" and a.beta_or_or}
    if len(set(sig_directions.values())) > 1:
        return {"state": "conflicting", "grade": None}

    significant = [a for a in hits if a.result == "significant"]
    if significant:
        best = min(significant, key=lambda a: a.p_value if a.p_value is not None else 1.0)
        return {"state": "significant", "grade": best.grade, "assoc_id": best.assoc_id}

    suggestive = [
        a for a in hits
        if a.result == "suggestive"
        or (a.p_value is not None and SUGGESTIVE_UPPER >= a.p_value >= GENOME_WIDE_SIGNIFICANCE)
    ]
    if suggestive:
        best = min(suggestive, key=lambda a: a.p_value if a.p_value is not None else 1.0)
        return {"state": "suggestive", "grade": best.grade, "assoc_id": best.assoc_id}

    if any(a.result == "tested_null" for a in hits):
        return {"state": "tested_null", "grade": None}

    return {"state": "not_tested", "grade": None}


def build_matrix(level: str, tables: dict) -> dict:
    grade_all(tables["associations"])
    phenotype_ids = _released_phenotype_ids(tables)

    if level == "locus":
        row_ids = [l.locus_id for l in tables["loci"]]
        row_label = lambda rid: rid  # noqa: E731
    elif level == "gene":
        row_ids = sorted({lg.ensembl_gene_id for lg in tables["locus_gene"]})
        symbol_by_id = {g.ensembl_gene_id: g.symbol for g in tables["genes"]}
        row_label = lambda rid: symbol_by_id.get(rid, rid)  # noqa: E731
    else:
        raise ValueError(level)

    rows = []
    for rid in row_ids:
        variant_ids = _row_variant_ids(level, rid, tables)
        row_assocs = [a for a in tables["associations"] if a.variant_id in variant_ids]
        cells = {pid: _cell(row_assocs, pid) for pid in phenotype_ids}
        rows.append({"row_id": rid, "label": row_label(rid), "cells": cells})

    return {"level": level, "columns": phenotype_ids, "rows": rows}


def build_evidence_map(target_id: str, tables: dict) -> dict:
    """PACVS evidence map: target -> related phenotypes (edge = relationship
    rationale) -> shared loci -> genes, with gap nodes where a related
    phenotype has no data.
    """
    grade_all(tables["associations"])
    relationships = [r for r in tables["phenotype_relationships"] if r.from_id == target_id]
    phenotype_by_id = {p.phenotype_id: p for p in tables["phenotypes"]}

    nodes = [{"id": target_id, "kind": "phenotype"}]
    edges = []
    for rel in relationships:
        related = phenotype_by_id.get(rel.to_id)
        is_gap = related is None or related.search_state in ("not_searched", "searched_none")
        nodes.append({"id": rel.to_id, "kind": "phenotype", "gap": is_gap})
        edges.append({
            "from": target_id,
            "to": rel.to_id,
            "kind": "relationship",
            "relationship_type": rel.relationship_type,
            "rationale": rel.rationale,
            "gap": is_gap,
        })

    # T2 associations surfaced on the target phenotype's page -> their loci/genes
    t2_on_target = [a for a in tables["associations"] if a.phenotype_id == target_id and a.tier == "T2"]
    variant_to_locus = {}
    for locus in tables["loci"]:
        for v in tables["variants"]:
            if v.chrom == locus.chrom and v.pos is not None and locus.start <= v.pos <= locus.end:
                variant_to_locus[v.variant_id] = locus.locus_id

    seen_loci = set()
    for a in t2_on_target:
        locus_id = variant_to_locus.get(a.variant_id)
        if not locus_id or locus_id in seen_loci:
            continue
        seen_loci.add(locus_id)
        nodes.append({"id": locus_id, "kind": "locus"})
        edges.append({"from": a.via_phenotype_id, "to": locus_id, "kind": "shared_locus"})
        for lg in tables["locus_gene"]:
            if lg.locus_id == locus_id:
                nodes.append({"id": lg.ensembl_gene_id, "kind": "gene"})
                edges.append({"from": locus_id, "to": lg.ensembl_gene_id, "kind": "locus_to_gene"})

    return {"target": target_id, "nodes": nodes, "edges": edges}
