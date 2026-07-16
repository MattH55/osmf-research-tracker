"""SQLAlchemy models for MedFreedom Arbitrage Map (per medical-freedom-arbitrage-schema.md)."""
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Column, String, Text, Date, DateTime, Float, Enum as SAEnum,
    ForeignKey, UniqueConstraint, Index, JSON, create_engine, event
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    pass


# ── Enums ──────────────────────────────────────────────────────────────────

class JurisdictionLevel(str, enum.Enum):
    """Jurisdiction nesting hierarchy per schema §2."""
    SUPRANATIONAL = "Supranational"
    SOVEREIGN = "Sovereign"
    SUBNATIONAL = "Subnational"
    SPECIAL_ZONE = "Special_Zone"
    MUNICIPAL = "Municipal"


class JurisdictionType(str, enum.Enum):
    COUNTRY = "Country"
    US_STATE = "US_State"
    ZEDE = "ZEDE"
    PROVINCE = "Province"
    TERRITORY = "Territory"
    FEDERAL = "Federal"


class RegulatoryModality(str, enum.Enum):
    """Primary axis: what the procedure is legally per schema §1."""
    SMALL_MOLECULE_APPROVED = "Small_Molecule_Approved"
    SMALL_MOLECULE_OFFLABEL = "Small_Molecule_OffLabel"
    SMALL_MOLECULE_COMPOUNDED = "Small_Molecule_Compounded"
    SMALL_MOLECULE_UNAPPROVED = "Small_Molecule_Unapproved"
    CONTROLLED_SUBSTANCE = "Controlled_Substance"
    CELL_THERAPY_AUTOLOGOUS = "Cell_Therapy_Autologous"
    CELL_THERAPY_ALLOGENEIC = "Cell_Therapy_Allogeneic"
    GENE_THERAPY = "Gene_Therapy"
    PEPTIDE = "Peptide"
    BLOOD_PRODUCT_APHERESIS = "Blood_Product_Apheresis"
    DEVICE_PROCEDURE = "Device_Procedure"
    REPRODUCTIVE = "Reproductive"
    END_OF_LIFE = "End_of_Life"
    NUTRACEUTICAL_NATURAL = "Nutraceutical_Natural"


class RestrictionDriver(str, enum.Enum):
    """Secondary tag: why it's restricted per schema §1."""
    SAFETY_UNPROVEN = "Safety_Unproven"
    CONTROLLED_SUBSTANCE = "Controlled_Substance"
    ETHICS_CONTESTED = "Ethics_Contested"
    COST_OR_LICENSING = "Cost_or_Licensing"
    IMPORT_BARRIER = "Import_Barrier"
    NONE = "None"


class Modality(str, enum.Enum):
    """Legacy therapeutic category for backward compatibility."""
    PSYCHEDELICS = "Psychedelics"
    GENE_THERAPY = "Gene_Therapy"
    STEM_CELL = "Stem_Cell"
    PEPTIDE = "Peptide"
    REPURPOSED = "Repurposed_Drug"
    REPRODUCTIVE = "Reproductive_Tech"
    ASSISTED_DYING = "Assisted_Dying"
    CELLULAR = "Cellular"
    PHYTOCANNABINOID = "Phytocannabinoid"
    ONCOLOGY = "Oncology"
    OTHER = "Other"


class LegalStatus(str, enum.Enum):
    """Legal status per schema §4."""
    APPROVED_ON_LABEL = "Approved_On_Label"
    APPROVED_OFF_LABEL = "Approved_Off_Label"
    PERMITTED_EXPANDED_ACCESS = "Permitted_Expanded_Access"
    PERMITTED_RTT = "Permitted_RTT"
    CLINICAL_TRIAL_ONLY = "Clinical_Trial_Only"
    PHYSICIAN_DISCRETION_GRAY = "Physician_Discretion_Gray"
    UNREGULATED_PERMITTED = "Unregulated_Permitted"
    DECRIMINALIZED_NO_SUPPLY = "Decriminalized_No_Supply"
    PROHIBITED = "Prohibited"
    UNKNOWN = "Unknown"
    # Legacy values for backward compatibility
    FULLY_APPROVED = "Fully_Approved"
    REGULATED_THERAPY = "Regulated_Therapy_Program"
    DECRIMINALIZED = "Decriminalized_Possession"
    RIGHT_TO_TRY = "Right_To_Try"
    OFF_LABEL = "Off_Label"


class AccessPathway(str, enum.Enum):
    """How you actually get it per schema §4."""
    STANDARD_PRESCRIPTION = "Standard_Prescription"
    OFF_LABEL_PRESCRIPTION = "Off_Label_Prescription"
    COMPOUNDING = "Compounding"
    EXPANDED_ACCESS = "Expanded_Access"
    RIGHT_TO_TRY = "Right_To_Try"
    CLINICAL_TRIAL_ENROLLMENT = "Clinical_Trial_Enrollment"
    PERSONAL_IMPORT = "Personal_Import"
    LICENSED_PROVIDER_REGIME = "Licensed_Provider_Regime"
    MEDICAL_TOURISM_CASH = "Medical_Tourism_Cash"
    NONE = "None"


class OversightQuality(str, enum.Enum):
    """Regulatory oversight level per schema §3."""
    REGULATED_HIGH = "Regulated_High"
    REGULATED_MODERATE = "Regulated_Moderate"
    SELF_REGULATED = "Self_Regulated"
    MINIMAL = "Minimal"
    NONE = "None"
    # Legacy
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    VARIABLE = "Variable"


class PriceConfidence(str, enum.Enum):
    """Basis for price data per schema §3."""
    QUOTED = "Quoted"
    ESTIMATED = "Estimated"
    UNKNOWN = "Unknown"


class Confidence(str, enum.Enum):
    """Data confidence level per schema §3."""
    HIGH = "High"
    MODERATE = "Moderate"
    LOW = "Low"


class Volatility(str, enum.Enum):
    """Legal/regulatory volatility per schema §3."""
    STABLE = "Stable"
    PENDING_LEGISLATION = "Pending_Legislation"
    ACTIVE_FLUX = "Active_Flux"


# ── Models ─────────────────────────────────────────────────────────────────

class Jurisdiction(Base):
    """Jurisdiction model with nesting support per schema §2."""
    __tablename__ = "jurisdictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("jurisdictions.id"), nullable=True)
    level: Mapped[JurisdictionLevel] = mapped_column(SAEnum(JurisdictionLevel), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    type: Mapped[JurisdictionType] = mapped_column(SAEnum(JurisdictionType), nullable=False)
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    general_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    parent: Mapped[Optional["Jurisdiction"]] = relationship("Jurisdiction", remote_side=[id], foreign_keys=[parent_id])
    access_records: Mapped[List["AccessRecord"]] = relationship(back_populates="jurisdiction", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "parent_id": self.parent_id,
            "level": self.level.value if isinstance(self.level, JurisdictionLevel) else self.level,
            "name": self.name,
            "type": self.type.value if isinstance(self.type, JurisdictionType) else self.type,
            "country_code": self.country_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "general_notes": self.general_notes,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class Procedure(Base):
    """Procedure model with regulatory modality & restriction driver per schema §1."""
    __tablename__ = "procedures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    modality: Mapped[Modality] = mapped_column(SAEnum(Modality), nullable=False)
    regulatory_modality: Mapped[Optional[RegulatoryModality]] = mapped_column(SAEnum(RegulatoryModality), nullable=True)
    restriction_driver: Mapped[Optional[RestrictionDriver]] = mapped_column(SAEnum(RestrictionDriver), nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    therapeutic_areas: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array stored as text
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    typical_us_cost_range: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    indications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array stored as text

    access_records: Mapped[List["AccessRecord"]] = relationship(back_populates="procedure", cascade="all, delete-orphan")

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "name": self.name,
            "modality": self.modality.value if isinstance(self.modality, Modality) else self.modality,
            "regulatory_modality": self.regulatory_modality.value if isinstance(self.regulatory_modality, RegulatoryModality) else self.regulatory_modality,
            "restriction_driver": self.restriction_driver.value if isinstance(self.restriction_driver, RestrictionDriver) else self.restriction_driver,
            "subcategory": self.subcategory,
            "therapeutic_areas": json.loads(self.therapeutic_areas) if self.therapeutic_areas else [],
            "description": self.description,
            "typical_us_cost_range": self.typical_us_cost_range,
            "indications": self.indications,
            "sources": json.loads(self.sources) if self.sources else [],
        }


class AccessRecord(Base):
    """AccessCell per schema §3: procedure × jurisdiction join with legal, practical, and quality fields."""
    __tablename__ = "access_records"
    __table_args__ = (
        UniqueConstraint("procedure_id", "jurisdiction_id", name="uq_procedure_jurisdiction"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    procedure_id: Mapped[str] = mapped_column(String(36), ForeignKey("procedures.id", ondelete="CASCADE"), nullable=False)
    jurisdiction_id: Mapped[str] = mapped_column(String(36), ForeignKey("jurisdictions.id", ondelete="CASCADE"), nullable=False)

    # Legal / regulatory per schema §3
    legal_status: Mapped[LegalStatus] = mapped_column(SAEnum(LegalStatus), nullable=False)
    access_pathway: Mapped[Optional[AccessPathway]] = mapped_column(SAEnum(AccessPathway), nullable=True)
    regulatory_authority: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    legal_basis: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # statute/regulation citation

    # Eligibility (JSON) per schema §3
    eligibility_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # {residency_required, diagnosis_gate, age_min, prior_failure_required, referral_required}
    # Legacy text fields for backward compatibility
    eligibility_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Practical / arbitrage per schema §3
    price_local: Mapped[Optional[Float]] = mapped_column(Float, nullable=True)
    price_usd: Mapped[Optional[Float]] = mapped_column(Float, nullable=True)
    price_basis: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # cash_pay, insured, trial_free
    price_confidence: Mapped[Optional[PriceConfidence]] = mapped_column(SAEnum(PriceConfidence), nullable=True)
    estimated_cost_range_usd: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Travel friction (JSON) per schema §3
    travel_friction_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # {visa, min_stay_days, language}
    residency_travel_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Derived total per schema §3
    total_access_cost_usd: Mapped[Optional[Float]] = mapped_column(Float, nullable=True)

    # Quality / risk per schema §3
    oversight_quality: Mapped[Optional[OversightQuality]] = mapped_column(SAEnum(OversightQuality), nullable=True)
    oversight_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    known_risk_flags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    risk_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    arbitrage_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Provenance / freshness per schema §3
    last_verified: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    verified_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # source/agent
    sources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    confidence: Mapped[Optional[Confidence]] = mapped_column(SAEnum(Confidence), nullable=True)
    volatility: Mapped[Optional[Volatility]] = mapped_column(SAEnum(Volatility), nullable=True)

    # Legacy field
    status: Mapped[str] = mapped_column(String(20), default="active")

    # Backref details per schema §3
    access_pathway_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    procedure: Mapped["Procedure"] = relationship(back_populates="access_records")
    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="access_records")

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "procedure_id": self.procedure_id,
            "jurisdiction_id": self.jurisdiction_id,
            "legal_status": self.legal_status.value if isinstance(self.legal_status, LegalStatus) else self.legal_status,
            "access_pathway": self.access_pathway.value if isinstance(self.access_pathway, AccessPathway) else self.access_pathway,
            "regulatory_authority": self.regulatory_authority,
            "legal_basis": self.legal_basis,
            "eligibility_json": json.loads(self.eligibility_json) if self.eligibility_json else None,
            "eligibility_requirements": self.eligibility_requirements,
            "provider_requirements": self.provider_requirements,
            "price_local": self.price_local,
            "price_usd": self.price_usd,
            "price_basis": self.price_basis,
            "price_confidence": self.price_confidence.value if isinstance(self.price_confidence, PriceConfidence) else self.price_confidence,
            "estimated_cost_range_usd": self.estimated_cost_range_usd,
            "cost_notes": self.cost_notes,
            "travel_friction_json": json.loads(self.travel_friction_json) if self.travel_friction_json else None,
            "residency_travel_notes": self.residency_travel_notes,
            "total_access_cost_usd": self.total_access_cost_usd,
            "oversight_quality": self.oversight_quality.value if isinstance(self.oversight_quality, OversightQuality) else self.oversight_quality if self.oversight_quality else None,
            "oversight_notes": self.oversight_notes,
            "known_risk_flags": json.loads(self.known_risk_flags) if self.known_risk_flags else [],
            "risk_notes": self.risk_notes,
            "arbitrage_summary": self.arbitrage_summary,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "verified_by": self.verified_by,
            "sources": json.loads(self.sources) if self.sources else [],
            "confidence": self.confidence.value if isinstance(self.confidence, Confidence) else self.confidence,
            "volatility": self.volatility.value if isinstance(self.volatility, Volatility) else self.volatility,
            "status": self.status,
            "access_pathway_details": self.access_pathway_details,
        }


class EvidenceGrade(str, enum.Enum):
    """Evidence tier per RepurpOS / schema §5."""
    E1 = "E1"  # multiple RCTs consistent direction
    E2 = "E2"  # one RCT
    E3 = "E3"  # small/conflicting RCTs
    E4 = "E4"  # uncontrolled trials
    E5 = "E5"  # case series
    E6 = "E6"  # animal models
    E7 = "E7"  # in vitro
    E8 = "E8"  # no evidence


class Condition(Base):
    """Disease/condition model per schema §5."""
    __tablename__ = "conditions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    icd_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    procedure_indications: Mapped[List["ProcedureIndication"]] = relationship(back_populates="condition", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "icd_code": self.icd_code,
            "description": self.description,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class ProcedureIndication(Base):
    """Procedure–Condition join with evidence grade per schema §5."""
    __tablename__ = "procedure_indications"
    __table_args__ = (
        UniqueConstraint("procedure_id", "condition_id", name="uq_procedure_condition"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    procedure_id: Mapped[str] = mapped_column(String(36), ForeignKey("procedures.id", ondelete="CASCADE"), nullable=False)
    condition_id: Mapped[str] = mapped_column(String(36), ForeignKey("conditions.id", ondelete="CASCADE"), nullable=False)
    evidence_grade: Mapped[EvidenceGrade] = mapped_column(SAEnum(EvidenceGrade), nullable=False)
    evidence_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    procedure: Mapped["Procedure"] = relationship(foreign_keys=[procedure_id])
    condition: Mapped["Condition"] = relationship(back_populates="procedure_indications", foreign_keys=[condition_id])

    def to_dict(self):
        return {
            "id": self.id,
            "procedure_id": self.procedure_id,
            "condition_id": self.condition_id,
            "evidence_grade": self.evidence_grade.value if isinstance(self.evidence_grade, EvidenceGrade) else self.evidence_grade,
            "evidence_summary": self.evidence_summary,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }