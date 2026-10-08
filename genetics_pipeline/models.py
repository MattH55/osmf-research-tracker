"""Pydantic models mirroring data/genetics/genetic-correlate.schema.json.

One model per $defs entry in the schema; field names match CSV headers so
csv.DictReader rows can be validated with Model(**row) after light type
coercion (see io_tables.py).
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel


class Phenotype(BaseModel):
    phenotype_id: str
    label: str
    efo_id: Optional[str] = None
    mondo_id: Optional[str] = None
    hpo_ids: str = ""
    role: Literal["target", "source", "reference"]
    search_state: Literal["searched_none", "searched_underpowered", "has_evidence", "not_searched"]
    last_searched: Optional[str] = None
    search_queries: str = ""
    search_sources: str = ""


class PhenotypeRelationship(BaseModel):
    from_id: str
    to_id: str
    relationship_type: Literal["clinical_overlap", "shared_exposure", "symptom_overlap", "mechanistic_hypothesis"]
    rationale: str
    citation_id: Optional[str] = None


class Study(BaseModel):
    study_id: str
    phenotype_id: str
    case_definition: str = ""
    case_n: int
    control_n: int
    ancestry: str
    platform: str = ""
    significance_threshold: float
    publication_id: str = ""
    summary_stats_url: Optional[str] = None
    licence: str


class Variant(BaseModel):
    variant_id: str
    rsid: Optional[str] = None
    chrom: str
    pos: Optional[int] = None
    ref: Optional[str] = None
    alt: Optional[str] = None
    variant_kind: Literal["snv", "indel", "hla_allele"] = "snv"
    maf_ancestry: str = ""


class Association(BaseModel):
    assoc_id: str
    study_id: str
    variant_id: str
    phenotype_id: str
    effect_allele: Optional[str] = None
    beta_or_or: Optional[float] = None
    effect_measure: Optional[Literal["beta", "or"]] = None
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    p_value: Optional[float] = None
    tier: Literal["T1", "T2", "T3"]
    result: Literal["significant", "suggestive", "tested_null"]
    replicated: bool = False
    fine_mapped: bool = False
    source_id: str
    via_phenotype_id: Optional[str] = None

    # computed by grading.py, not read from CSV
    grade: Optional[Literal["A", "B", "C", "D"]] = None


class Gene(BaseModel):
    ensembl_gene_id: str
    symbol: str
    biotype: str
    chrom: str = ""
    start: Optional[int] = None
    end: Optional[int] = None
    assembly: str = "GRCh38"


class Locus(BaseModel):
    locus_id: str
    chrom: str
    start: int
    end: int
    lead_variant: str
    definition_method: Literal["open_targets_credible_set", "distance_window_50kb"]


class LocusGene(BaseModel):
    locus_id: str
    ensembl_gene_id: str
    l2g_score: Optional[float] = None
    nearest_gene: bool = False
    assignment_method: Literal["open_targets_l2g", "distance_window", "coloc"]


class Source(BaseModel):
    source_id: str
    name: str
    release: Optional[str] = None
    url: Optional[str] = None
    licence: str
    retrieved_at: str


class Publication(BaseModel):
    publication_id: str
    title: str
    year: int
    journal: Optional[str] = None
    preprint: bool = False
