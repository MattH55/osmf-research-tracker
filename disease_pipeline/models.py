from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AlterationType(str, Enum):
    A = "A"  # molecular: gene / protein / metabolite
    B = "B"  # clinical measurement: lab value, vital, imaging metric
    C = "C"  # validated disease scale or PRO instrument
    D = "D"  # pathological / structural finding
    E = "E"  # functional impairment


class EvidenceTier(str, Enum):
    A = "A"  # multiple independent databases + literature (>50 papers)
    B = "B"  # single database + literature (>10 papers)
    C = "C"  # single source or literature only (<10 papers)


class DiseaseIdentifiers(BaseModel):
    name: str
    mondo_id: Optional[str] = None
    efo_id: Optional[str] = None
    omim_id: Optional[str] = None
    orpha_id: Optional[str] = None
    mesh_id: Optional[str] = None
    umls_cui: Optional[str] = None


class Alteration(BaseModel):
    canonical_id: str
    name: str
    alteration_type: AlterationType
    subtype: str
    direction: Optional[str] = None
    frequency_label: Optional[str] = None
    frequency_pct: Optional[str] = None
    sources: list[str] = Field(default_factory=list)
    source_ids: dict[str, str] = Field(default_factory=dict)
    evidence_tier: EvidenceTier = EvidenceTier.C
    pubmed_count: int = 0
    definition: Optional[str] = None


class Therapeutic(BaseModel):
    canonical_id: str
    name: str
    drug_type: str
    mechanism: Optional[str] = None
    max_phase: int = 0
    approved_indications: list[str] = Field(default_factory=list)
    source_type: Literal["direct", "via_biomarker", "natural_agent"]
    via_alteration: Optional[str] = None
    sources: list[str] = Field(default_factory=list)
    evidence_tier: EvidenceTier = EvidenceTier.C
    chembl_id: Optional[str] = None
    rxnorm_id: Optional[str] = None
    repurposing_signal: bool = False
    pubmed_count: int = 0
    score: int = 0


class ClinicalTrialRecord(BaseModel):
    nct_id: Optional[str] = None
    title: str
    status: Optional[str] = None
    phase: Optional[str] = None
    enrollment: Optional[int] = None
    source: str = "ClinicalTrials.gov"
    url: str
    year: Optional[int] = None


class LiteratureRecord(BaseModel):
    pmid: Optional[str] = None
    title: str
    journal: Optional[str] = None
    year: Optional[int] = None
    publication_type: str
    publication_type_label: str
    url: str
    authors: Optional[str] = None


class AgentClinicalEvidence(BaseModel):
    drug_canonical_id: str
    drug_name: str
    clinical_trials: list[ClinicalTrialRecord] = Field(default_factory=list)
    literature: list[LiteratureRecord] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    search_links: dict[str, str] = Field(default_factory=dict)


class NPType(str, Enum):
    botanical = "botanical"
    nutraceutical = "nutraceutical"
    probiotic = "probiotic"
    amino_acid = "amino_acid"
    food_compound = "food_compound"
    tcm_herb = "tcm_herb"
    ayurvedic = "ayurvedic"
    mushroom = "mushroom"


class NPEvidenceTier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class SafetyTier(str, Enum):
    GRAS = "GRAS"
    generally_safe = "generally_safe"
    caution = "caution"
    avoid = "avoid"
    unknown = "unknown"


class NaturalProduct(BaseModel):
    canonical_id: str
    name: str
    common_names: list[str] = Field(default_factory=list)
    scientific_name: Optional[str] = None
    np_type: NPType = NPType.nutraceutical

    meta_analysis_count: int = 0
    rct_count: int = 0
    systematic_review_count: int = 0
    ct_trial_count: int = 0
    np_evidence_tier: NPEvidenceTier = NPEvidenceTier.D
    key_findings: Optional[str] = None

    linked_alteration_ids: list[str] = Field(default_factory=list)
    target_names: list[str] = Field(default_factory=list)
    mechanism: Optional[str] = None
    chembl_ids: list[str] = Field(default_factory=list)

    active_constituents: list[str] = Field(default_factory=list)

    safety_tier: SafetyTier = SafetyTier.unknown
    herb_drug_interactions: list[str] = Field(default_factory=list)
    contraindications: list[str] = Field(default_factory=list)

    traditional_systems: list[str] = Field(default_factory=list)
    traditional_indication: Optional[str] = None

    pubchem_cid: Optional[str] = None
    lotus_wikidata_id: Optional[str] = None
    hmdb_id: Optional[str] = None
    coconut_id: Optional[str] = None
    pubchem_bioassay_count: int = 0

    sources: list[str] = Field(default_factory=list)
    score: float = 0.0


class DiseasePageData(BaseModel):
    identifiers: DiseaseIdentifiers
    alterations: list[Alteration] = Field(default_factory=list)
    therapeutics_direct: list[Therapeutic] = Field(default_factory=list)
    therapeutics_via_biomarker: list[Therapeutic] = Field(default_factory=list)
    therapeutics_natural: list[Therapeutic] = Field(default_factory=list)
    therapeutics_merged: list[Therapeutic] = Field(default_factory=list)
    therapeutic_evidence: dict[str, AgentClinicalEvidence] = Field(default_factory=dict)
    natural_products: list[NaturalProduct] = Field(default_factory=list)
    pipeline_meta: dict = Field(default_factory=dict)