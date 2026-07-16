"""Pydantic schemas for API request/response validation."""
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel


# ── Jurisdiction Schemas ─────────────────────────────────────────────────

class JurisdictionBase(BaseModel):
    name: str
    type: str
    country_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    general_notes: Optional[str] = None


class JurisdictionCreate(JurisdictionBase):
    id: Optional[str] = None


class JurisdictionUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    general_notes: Optional[str] = None


class JurisdictionResponse(JurisdictionBase):
    id: str
    last_updated: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Procedure Schemas ────────────────────────────────────────────────────

class ProcedureBase(BaseModel):
    name: str
    modality: str
    subcategory: Optional[str] = None
    therapeutic_areas: List[str] = []
    description: Optional[str] = None
    typical_us_cost_range: Optional[str] = None
    indications: Optional[str] = None
    sources: List[dict] = []


class ProcedureCreate(ProcedureBase):
    id: Optional[str] = None


class ProcedureUpdate(BaseModel):
    name: Optional[str] = None
    modality: Optional[str] = None
    subcategory: Optional[str] = None
    therapeutic_areas: Optional[List[str]] = None
    description: Optional[str] = None
    typical_us_cost_range: Optional[str] = None
    indications: Optional[str] = None
    sources: Optional[List[dict]] = None


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