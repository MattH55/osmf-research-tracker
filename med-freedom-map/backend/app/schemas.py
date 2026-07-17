"""Pydantic schemas for API request/response validation."""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel


# ── Jurisdiction Schemas ─────────────────────────────────────────────────

class RegulationProfile(BaseModel):
    """Structured national/subnational regulation (jurisdiction_regulation.schema.json)."""
    drug_regulator: Optional[str] = None
    health_authority: Optional[str] = None
    controlled_substance_framework: Optional[str] = None
    un_conventions_party: Optional[bool] = None
    psychedelic_default: Optional[str] = None
    cannabis_default: Optional[str] = None
    assisted_dying_default: Optional[str] = None
    right_to_try_or_expanded_access: Optional[bool] = None
    compounding_environment: Optional[str] = None
    key_statutes: List[dict] = []
    pending_legislation: List[dict] = []
    last_reviewed: Optional[str] = None
    confidence: Optional[str] = None


class JurisdictionBase(BaseModel):
    name: str
    type: str
    country_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    general_notes: Optional[str] = None
    regulation: Optional[RegulationProfile] = None


class JurisdictionCreate(JurisdictionBase):
    id: Optional[str] = None
    parent_id: Optional[str] = None
    level: Optional[str] = None


class JurisdictionUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    general_notes: Optional[str] = None
    regulation: Optional[RegulationProfile] = None


class JurisdictionResponse(JurisdictionBase):
    id: str
    parent_id: Optional[str] = None
    level: Optional[str] = None
    last_updated: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Procedure / Therapy Schemas (therapy.schema.json) ─────────────────────

class PractitionerSetup(BaseModel):
    summary: Optional[str] = None
    difficulty: Optional[str] = None
    licenses: List[str] = []
    facility: List[str] = []
    training: List[str] = []
    staffing: List[str] = []
    product_source: List[str] = []
    regulatory_steps: List[str] = []
    capital_notes: Optional[str] = None
    ongoing_compliance: List[str] = []
    notes: Optional[str] = None


class ProcedureBase(BaseModel):
    name: str
    modality: str
    subcategory: Optional[str] = None
    therapeutic_areas: List[str] = []
    diseases: List[str] = []
    description: Optional[str] = None
    typical_us_cost_range: Optional[str] = None
    indications: Optional[str] = None
    sources: List[dict] = []
    regulatory_modality: Optional[str] = None
    restriction_driver: Optional[str] = None
    controlled_substance_class: Optional[str] = None
    default_global_posture: Optional[str] = None
    practitioner_setup: Optional[PractitionerSetup] = None


class ProcedureCreate(ProcedureBase):
    id: Optional[str] = None


class ProcedureUpdate(BaseModel):
    name: Optional[str] = None
    modality: Optional[str] = None
    subcategory: Optional[str] = None
    therapeutic_areas: Optional[List[str]] = None
    diseases: Optional[List[str]] = None
    description: Optional[str] = None
    typical_us_cost_range: Optional[str] = None
    indications: Optional[str] = None
    sources: Optional[List[dict]] = None
    regulatory_modality: Optional[str] = None
    restriction_driver: Optional[str] = None
    controlled_substance_class: Optional[str] = None
    default_global_posture: Optional[str] = None
    practitioner_setup: Optional[PractitionerSetup] = None


class ProcedureResponse(ProcedureBase):
    id: str

    model_config = {"from_attributes": True}


# ── Access Record Schemas ────────────────────────────────────────────────

class AccessRecordBase(BaseModel):
    procedure_id: str
    jurisdiction_id: str
    legal_status: str
    access_pathway_details: Optional[str] = None
    eligibility_requirements: Optional[str] = None
    provider_requirements: Optional[str] = None
    oversight_quality: Optional[str] = None
    oversight_notes: Optional[str] = None
    estimated_cost_range_usd: Optional[str] = None
    cost_notes: Optional[str] = None
    residency_travel_notes: Optional[str] = None
    risk_notes: Optional[str] = None
    arbitrage_summary: Optional[str] = None
    last_verified: Optional[str] = None
    sources: List[dict] = []
    status: str = "active"


class AccessRecordCreate(AccessRecordBase):
    id: Optional[str] = None


class AccessRecordUpdate(BaseModel):
    legal_status: Optional[str] = None
    access_pathway_details: Optional[str] = None
    eligibility_requirements: Optional[str] = None
    provider_requirements: Optional[str] = None
    oversight_quality: Optional[str] = None
    oversight_notes: Optional[str] = None
    estimated_cost_range_usd: Optional[str] = None
    cost_notes: Optional[str] = None
    residency_travel_notes: Optional[str] = None
    risk_notes: Optional[str] = None
    arbitrage_summary: Optional[str] = None
    last_verified: Optional[str] = None
    sources: Optional[List[dict]] = None
    status: Optional[str] = None


class AccessRecordResponse(AccessRecordBase):
    id: str
    procedure_name: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    modality: Optional[str] = None
    procedure_subcategory: Optional[str] = None
    jurisdiction_type: Optional[str] = None
    jurisdiction_country_code: Optional[str] = None
    jurisdiction_latitude: Optional[float] = None
    jurisdiction_longitude: Optional[float] = None

    model_config = {"from_attributes": True}


# ── Filter / Query Schemas ───────────────────────────────────────────────

class AccessRecordFilter(BaseModel):
    modality: Optional[List[str]] = None
    therapeutic_area: Optional[str] = None
    legal_status: Optional[List[str]] = None
    oversight_quality: Optional[List[str]] = None
    jurisdiction_id: Optional[str] = None
    procedure_id: Optional[str] = None
    search: Optional[str] = None
    status: str = "active"


# ── Import/Export ────────────────────────────────────────────────────────

class BulkImportRequest(BaseModel):
    jurisdictions: List[JurisdictionCreate] = []
    procedures: List[ProcedureCreate] = []
    access_records: List[AccessRecordCreate] = []


class ExportResponse(BaseModel):
    jurisdictions: List[dict] = []
    procedures: List[dict] = []
    access_records: List[dict] = []