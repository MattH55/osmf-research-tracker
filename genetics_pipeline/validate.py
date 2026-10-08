"""Schema + referential-integrity validation for data/genetics/*.csv.

Two layers, matching the PAIS cohort database's validate.py pattern:
  1. Each row validates against its $defs entry in genetic-correlate.schema.json
     (pydantic already enforces this on load — see io_tables.py — so this
     module focuses on layer 2)
  2. Cross-references between tables resolve (study_id, variant_id,
     phenotype_id, gene_id, locus_id, source_id, publication_id)
"""
from __future__ import annotations

from .io_tables import load_all


class ValidationError(RuntimeError):
    pass


def validate_cross_references(tables: dict) -> list[str]:
    errors: list[str] = []

    phenotype_ids = {p.phenotype_id for p in tables["phenotypes"]}
    study_ids = {s.study_id for s in tables["studies"]}
    variant_ids = {v.variant_id for v in tables["variants"]}
    gene_ids = {g.ensembl_gene_id for g in tables["genes"]}
    locus_ids = {l.locus_id for l in tables["loci"]}
    source_ids = {s.source_id for s in tables["sources"]}
    publication_ids = {p.publication_id for p in tables["publications"]}

    for r in tables["phenotype_relationships"]:
        if r.from_id not in phenotype_ids:
            errors.append(f"phenotype_relationships: from_id {r.from_id!r} not in phenotypes")
        if r.to_id not in phenotype_ids:
            errors.append(f"phenotype_relationships: to_id {r.to_id!r} not in phenotypes")

    for s in tables["studies"]:
        if s.phenotype_id not in phenotype_ids:
            errors.append(f"studies: {s.study_id} references unknown phenotype_id {s.phenotype_id!r}")
        if s.publication_id and s.publication_id not in publication_ids:
            errors.append(f"studies: {s.study_id} references unknown publication_id {s.publication_id!r}")

    for a in tables["associations"]:
        if a.study_id not in study_ids:
            errors.append(f"associations: {a.assoc_id} references unknown study_id {a.study_id!r}")
        if a.variant_id not in variant_ids:
            errors.append(f"associations: {a.assoc_id} references unknown variant_id {a.variant_id!r}")
        if a.phenotype_id not in phenotype_ids:
            errors.append(f"associations: {a.assoc_id} references unknown phenotype_id {a.phenotype_id!r}")
        if a.source_id not in source_ids:
            errors.append(f"associations: {a.assoc_id} references unknown source_id {a.source_id!r}")
        if a.via_phenotype_id and a.via_phenotype_id not in phenotype_ids:
            errors.append(f"associations: {a.assoc_id} references unknown via_phenotype_id {a.via_phenotype_id!r}")
        if a.tier == "T2" and not a.via_phenotype_id:
            errors.append(f"associations: {a.assoc_id} is tier T2 but has no via_phenotype_id (UI rule: T2 rows must name the source phenotype)")
        if a.tier != "T2" and a.via_phenotype_id:
            errors.append(f"associations: {a.assoc_id} has via_phenotype_id set but tier is {a.tier}, not T2")

    for lg in tables["locus_gene"]:
        if lg.locus_id not in locus_ids:
            errors.append(f"locus_gene: references unknown locus_id {lg.locus_id!r}")
        if lg.ensembl_gene_id not in gene_ids:
            errors.append(f"locus_gene: references unknown ensembl_gene_id {lg.ensembl_gene_id!r}")

    return errors


def validate_framing(tables: dict) -> list[str]:
    """Build spec section 9 framing requirements that are mechanically checkable."""
    errors: list[str] = []
    banned = ("cause", "causes", "causal", "risk gene")
    for p in tables["phenotypes"]:
        label_lower = p.label.lower()
        for word in banned:
            if word in label_lower:
                errors.append(f"phenotypes: {p.phenotype_id} label contains banned framing word {word!r}")
    return errors


def run() -> None:
    tables = load_all()
    errors = validate_cross_references(tables) + validate_framing(tables)
    if errors:
        raise ValidationError("\n".join(errors))
    print(f"OK: {sum(len(v) for v in tables.values())} rows across {len(tables)} tables, no cross-reference or framing errors")


if __name__ == "__main__":
    run()
