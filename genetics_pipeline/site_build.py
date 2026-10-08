"""Module 7: site build. Renders the static /genetics/ site (HTML + JSON)
from the loaded, graded tables. Jinja templates; the client-side search index
is a plain array baked into index.html (small dataset, no server needed).
"""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import DATA_DIR, MANIFEST_PATH, ROOT, SITE_DIR
from .grading import grade_all
from .io_tables import load_all, write_json
from .matrix import build_evidence_map, build_matrix

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html.j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _enrich_associations(tables: dict) -> list[dict]:
    phenotype_label = {p.phenotype_id: p.label for p in tables["phenotypes"]}
    variant_by_id = {v.variant_id: v for v in tables["variants"]}
    gene_by_id = {g.ensembl_gene_id: g for g in tables["genes"]}
    genes_by_locus: dict[str, list] = {}
    for lg in tables["locus_gene"]:
        genes_by_locus.setdefault(lg.locus_id, []).append(lg)
    variant_to_locus = {}
    for locus in tables["loci"]:
        for v in tables["variants"]:
            if v.chrom == locus.chrom and v.pos is not None and locus.start <= v.pos <= locus.end:
                variant_to_locus[v.variant_id] = locus.locus_id

    enriched = []
    for a in tables["associations"]:
        v = variant_by_id.get(a.variant_id)
        locus_id = variant_to_locus.get(a.variant_id)
        genes = []
        if locus_id:
            for lg in genes_by_locus.get(locus_id, []):
                g = gene_by_id.get(lg.ensembl_gene_id)
                if g:
                    genes.append(g)
        row = a.model_dump()
        row["rsid"] = v.rsid if v else None
        row["phenotype_label"] = phenotype_label.get(a.phenotype_id, a.phenotype_id)
        row["trait_label"] = phenotype_label.get(a.phenotype_id, a.phenotype_id)
        row["genes"] = [g.model_dump() for g in genes]
        enriched.append(row)
    return enriched


def build(check: bool = False) -> None:
    tables = load_all()
    grade_all(tables["associations"])
    assoc = _enrich_associations(tables)
    env = _env()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def render(template_name: str, out_path: Path, **ctx) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        html = env.get_template(template_name).render(**ctx)
        out_path.write_text(html + "\n", encoding="utf-8")

    base_ctx = dict(build_id=manifest["build_id"])

    # ---- index ----
    released = [p for p in tables["phenotypes"] if p.search_state != "not_searched"]
    pending = [p for p in tables["phenotypes"] if p.search_state == "not_searched"]
    render(
        "index.html.j2",
        SITE_DIR / "index.html",
        title="Genetic Correlates Explorer",
        description="What genetic evidence exists for PACVS and adjacent post-acute phenotypes, how strong it is, and where it is missing.",
        canonical_url="https://research.opensourcemed.info/genetics/",
        root_prefix="../",
        genetics_prefix="",
        phenotypes=[p.model_dump() for p in released],
        pending_count=len(pending),
        **base_ctx,
    )

    # ---- phenotype pages ----
    phenotype_relationships = tables["phenotype_relationships"]
    phenotype_by_id = {p.phenotype_id: p for p in tables["phenotypes"]}
    for p in released:
        p_assoc = [a for a in assoc if a["phenotype_id"] == p.phenotype_id]
        p_studies = [s for s in tables["studies"] if s.study_id in {a["study_id"] for a in p_assoc}]
        rels = []
        for r in phenotype_relationships:
            if r.from_id != p.phenotype_id:
                continue
            related = phenotype_by_id.get(r.to_id)
            rels.append({
                "to_label": related.label if related else r.to_id,
                "to_state": related.search_state if related else "not_searched",
                "relationship_type": r.relationship_type,
                "rationale": r.rationale,
                "citation_id": r.citation_id,
            })

        is_pacvs = p.phenotype_id == "pacvs"
        evidence_map_json = json.dumps(build_evidence_map(p.phenotype_id, tables)) if is_pacvs else "null"

        render(
            "phenotype.html.j2",
            SITE_DIR / "phenotype" / f"{p.phenotype_id}.html",
            title=p.label,
            description=f"Genetic evidence for {p.label}: tiered associations, studies and search state.",
            canonical_url=f"https://research.opensourcemed.info/genetics/phenotype/{p.phenotype_id}.html",
            root_prefix="../../",
            genetics_prefix="../",
            phenotype=p.model_dump(),
            associations=p_assoc,
            studies=[s.model_dump() for s in p_studies],
            relationships=rels,
            is_pacvs=is_pacvs,
            evidence_map_json=evidence_map_json,
            **base_ctx,
        )

    # ---- variant pages ----
    for v in tables["variants"]:
        v_assoc = [a for a in assoc if a["variant_id"] == v.variant_id]
        locus_genes = []
        for a in v_assoc:
            for g in a["genes"]:
                locus_genes.append({"ensembl_gene_id": g["ensembl_gene_id"], "symbol": g["symbol"], "assignment_method": "distance_window", "nearest_gene": False})
        seen = set()
        genes_dedup = []
        for lg in locus_genes:
            if lg["ensembl_gene_id"] in seen:
                continue
            seen.add(lg["ensembl_gene_id"])
            genes_dedup.append(lg)
        render(
            "variant.html.j2",
            SITE_DIR / "variant" / f"{v.variant_id}.html",
            title=v.rsid or v.variant_id,
            description=f"Cross-phenotype associations for {v.rsid or v.variant_id}.",
            canonical_url=f"https://research.opensourcemed.info/genetics/variant/{v.variant_id}.html",
            root_prefix="../../",
            genetics_prefix="../",
            variant=v.model_dump(),
            associations=v_assoc,
            genes=genes_dedup,
            **base_ctx,
        )

    # ---- gene pages ----
    for g in tables["genes"]:
        lgs = [lg for lg in tables["locus_gene"] if lg.ensembl_gene_id == g.ensembl_gene_id]
        locus_ids = {lg.locus_id for lg in lgs}
        variant_ids = set()
        for locus in tables["loci"]:
            if locus.locus_id in locus_ids:
                for v in tables["variants"]:
                    if v.chrom == locus.chrom and v.pos is not None and locus.start <= v.pos <= locus.end:
                        variant_ids.add(v.variant_id)
        g_assoc = [a for a in assoc if a["variant_id"] in variant_ids]
        render(
            "gene.html.j2",
            SITE_DIR / "gene" / f"{g.ensembl_gene_id}.html",
            title=g.symbol,
            description=f"Loci, associations and RepurpOS links for {g.symbol}.",
            canonical_url=f"https://research.opensourcemed.info/genetics/gene/{g.ensembl_gene_id}.html",
            root_prefix="../../",
            genetics_prefix="../",
            gene=g.model_dump(),
            locus_genes=[lg.model_dump() for lg in lgs],
            associations=g_assoc,
            **base_ctx,
        )

    # ---- matrix pages + JSON ----
    column_labels = {p.phenotype_id: p.label for p in tables["phenotypes"]}
    for level, filename in (("locus", "matrix.html"), ("gene", "matrix-gene.html")):
        m = build_matrix(level, tables)
        write_json(m, SITE_DIR / "data" / f"matrix-{level}.json")
        render(
            "matrix.html.j2",
            SITE_DIR / filename,
            title="Cross-Phenotype Matrix",
            description="Locus/gene-level cross-phenotype genetic evidence matrix.",
            canonical_url=f"https://research.opensourcemed.info/genetics/{filename}",
            root_prefix="../",
            genetics_prefix="",
            level=level,
            matrix=m,
            column_labels=column_labels,
            **base_ctx,
        )

    # ---- methods ----
    render(
        "methods.html.j2",
        SITE_DIR / "methods.html",
        title="Methods",
        description="Grading rules, overlap thresholds and search queries for the Genetic Correlates Explorer.",
        canonical_url="https://research.opensourcemed.info/genetics/methods.html",
        root_prefix="../",
        genetics_prefix="",
        phenotypes=[p.model_dump() for p in tables["phenotypes"]],
        not_yet_implemented=manifest.get("not_yet_implemented", []),
        **base_ctx,
    )

    # ---- bulk JSON + CSV downloads ----
    write_json([p.model_dump() for p in tables["phenotypes"]], SITE_DIR / "data" / "phenotypes.json")
    write_json(assoc, SITE_DIR / "data" / "associations.json")
    write_json(
        {"target": "pacvs", **build_evidence_map("pacvs", tables)},
        SITE_DIR / "data" / "evidence-map-pacvs.json",
    )

    print(f"Built {len(released)} phenotype pages, {len(tables['variants'])} variant pages, "
          f"{len(tables['genes'])} gene pages, matrix (locus+gene), methods page.")


if __name__ == "__main__":
    import sys

    build(check="--check" in sys.argv)
