from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class AgentId(BaseModel):
    rxnorm: Optional[str] = None
    chembl_id: Optional[str] = None


class PotencyData(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    measure: Optional[str] = None  # IC50, Ki, EC50, Kd


class SourceRef(BaseModel):
    database: Optional[str] = None
    url: Optional[str] = None
    retrieved_at: Optional[str] = None
    pubmed_id: Optional[str] = None
    study_type: Optional[str] = None
    species: Optional[str] = None


class Agent(BaseModel):
    agent_name: str
    agent_id: AgentId = Field(default_factory=AgentId)
    direction_of_effect: str = "unclear"   # increases|decreases|inhibits|activates|modulates|unclear
    evidence_tier: str = "correlative"      # mechanistic|correlative|clinical
    potency: PotencyData = Field(default_factory=PotencyData)
    sources: list[SourceRef] = Field(default_factory=list)
    clinical_trial_refs: list[str] = Field(default_factory=list)


class NormalizedBiomarker(BaseModel):
    input_name: str
    symbol: Optional[str] = None
    uniprot_id: Optional[str] = None
    ensembl_id: Optional[str] = None
    synonyms: list[str] = Field(default_factory=list)
    entity_type: str = "gene"   # gene|protein|metabolite


class BiomarkerInfo(BaseModel):
    input: str
    normalized_symbol: Optional[str] = None
    uniprot_id: Optional[str] = None
    ensembl_id: Optional[str] = None
    synonyms: list[str] = Field(default_factory=list)
    entity_type: str = "gene"


class RawHit(BaseModel):
    agent: str
    agent_id: str = ""
    interaction_type: str = "unknown"
    direction: str = "unclear"
    source: str
    source_url: str = ""
    evidence_tier: str = "correlative"
    potency: PotencyData = Field(default_factory=PotencyData)
    pubmed_ids: list[str] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class PipelineOutput(BaseModel):
    biomarker: BiomarkerInfo
    agents: list[Agent] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


# ─── Atlas (disease-vs-control marker direction) models ──────────────────────
# Distinct from Agent.direction_of_effect above, which describes what a drug
# does to a gene. These describe whether the marker itself is elevated or
# reduced in the disease state relative to healthy controls — the question
# the biomarkers.schema.json atlas format actually requires.

class MarkerLiteratureRef(BaseModel):
    pmid: str
    title: str = ""
    abstract: str = ""
    source: str = "PubMed"
    first_author: Optional[str] = None
    pub_year: Optional[str] = None
    journal: Optional[str] = None
    doi: Optional[str] = None


class MarkerDirectionClaim(BaseModel):
    direction: str = "unclear"          # up|down|mixed|unclear (vs. healthy controls)
    comparison_population: str = ""     # e.g. "healthy controls", "disease-matched"
    symptoms: str = ""
    supporting_quote: str = ""
    pmid: str = ""
    citation: str = ""                  # "Author et al. YEAR"
    doi: str = ""


class DiseaseAgentTrialEvidence(BaseModel):
    nct_id: str
    title: str = ""
    status: str = ""
    phase: str = ""
    intervention_type: str = ""  # DRUG, BIOLOGICAL, DEVICE, BEHAVIORAL, DIETARY_SUPPLEMENT, PROCEDURE, OTHER


class DiseaseAgentCandidate(BaseModel):
    """A therapeutic agent found by searching FROM the disease directly
    (ClinicalTrials.gov interventions + Open Targets disease->knownDrugs),
    as opposed to Agent in models.py, which is found by searching from one
    of a disease's pre-selected gene targets. This surfaces agents whose
    mechanism doesn't route through the curated gene panel at all (combination
    therapies, non-pharmacological interventions, drugs hitting targets we
    didn't think to curate)."""
    agent_name: str
    target_genes: list[str] = Field(default_factory=list)  # from Open Targets, if resolved
    max_phase: Optional[str] = None
    approval_status: Optional[str] = None
    trial_evidence: list[DiseaseAgentTrialEvidence] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)  # "ClinicalTrials.gov" | "Open Targets"


class DiseaseAgentDiscoveryOutput(BaseModel):
    disease: str
    candidates: list[DiseaseAgentCandidate] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


class MarkerAtlasCandidate(BaseModel):
    """One gene/marker's aggregated disease-vs-control evidence for a single
    disease, ready to be reduced into a biomarkers.schema.json marker entry."""
    symbol: str
    synonyms: list[str] = Field(default_factory=list)
    entity_type: str = "gene"
    claims: list[MarkerDirectionClaim] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
