"""Pydantic schemas for pipeline I/O."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


EntityType = Literal["gene", "protein", "metabolite", "unknown"]
EvidenceTier = Literal["mechanistic", "correlative", "clinical"]
Direction = Literal["increases", "decreases", "inhibits", "activates", "modulates", "unclear"]


class NormalizedBiomarker(BaseModel):
    input: str
    symbol: str | None = None
    uniprot_id: str | None = None
    ensembl_id: str | None = None
    chembl_target_id: str | None = None
    chebi_id: str | None = None
    pubchem_cid: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    entity_type: EntityType = "unknown"
    resolution_notes: list[str] = Field(default_factory=list)


class RawHit(BaseModel):
    agent: str
    agent_id: str | None = None
    interaction_type: str | None = None
    direction_hint: str | None = None
    source: str
    source_url: str
    potency: dict[str, Any] | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class SourceCitation(BaseModel):
    database: str | None = None
    url: str | None = None
    retrieved_at: str | None = None
    pubmed_id: str | None = None
    study_type: str | None = None
    species: str | None = None
    locator: str | None = None


class AgentRecord(BaseModel):
    agent_name: str
    agent_id: dict[str, str] = Field(default_factory=dict)
    direction_of_effect: Direction = "unclear"
    evidence_tier: EvidenceTier = "correlative"
    potency: dict[str, Any] = Field(default_factory=lambda: {"value": None, "unit": None, "measure": None})
    sources: list[SourceCitation] = Field(default_factory=list)
    clinical_trial_refs: list[str] = Field(default_factory=list)


class PipelineOutput(BaseModel):
    biomarker: NormalizedBiomarker
    agents: list[AgentRecord]
    coverage_notes: list[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())