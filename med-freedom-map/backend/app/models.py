"""SQLAlchemy models for MedFreedom Arbitrage Map."""
import uuid
from datetime import date, datetime
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

class JurisdictionType(str, enum.Enum):
    COUNTRY = "Country"
    US_STATE = "US_State"
    ZEDE = "ZEDE"
    PROVINCE = "Province"
    TERRITORY = "Territory"
    FEDERAL = "Federal"


class Modality(str, enum.Enum):
    PSYCHEDELICS = "Psychedelics"
    GENE_THERAPY = "Gene_Therapy"
    STEM_CELL = "Stem_Cell"
    PEPTIDE = "Peptide"
    REPURPOSED = "Repurposed_Drug"
    REPRODUCTIVE = "Reproductive_Tech"
    ASSISTED_DYING = "Assisted_Dying"
    OTHER = "Other"


class LegalStatus(str, enum.Enum):
    FULLY_APPROVED = "Fully_Approved"
    REGULATED_THERAPY = "Regulated_Therapy_Program"
    DECRIMINALIZED = "Decriminalized_Possession"
    RIGHT_TO_TRY = "Right_To_Try"
    CLINICAL_TRIAL_ONLY = "Clinical_Trial_Only"
    PHYSICIAN_DISCRETION = "Physician_Discretion_Gray"
    PROHIBITED = "Prohibited"


class OversightQuality(str, enum.Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    VARIABLE = "Variable"


# ── Models ─────────────────────────────────────────────────────────────────

class Jurisdiction(Base):
    __tablename__ = "jurisdictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    type: Mapped[JurisdictionType] = mapped_column(SAEnum(JurisdictionType), nullable=False)
    country_code: Mapped[str] = mapped_column(String(3), nullable=False)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    general_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    access_records: Mapped[List["AccessRecord"]] = relationship(back_populates="jurisdiction", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value if isinstance(self.type, JurisdictionType) else self.type,
            "country_code": self.country_code,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "general_notes": self.general_notes,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    modality: Mapped[Modality] = mapped_column(SAEnum(Modality), nullable=False)
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
            "subcategory": self.subcategory,
            "therapeutic_areas": json.loads(self.therapeutic_areas) if self.therapeutic_areas else [],
            "description": self.description,
            "typical_us_cost_range": self.typical_us_cost_range,
            "indications": self.indications,
            "sources": json.loads(self.sources) if self.sources else [],
        }


class AccessRecord(Base):
    __tablename__ = "access_records"
    __table_args__ = (
        UniqueConstraint("procedure_id", "jurisdiction_id", name="uq_procedure_jurisdiction"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    procedure_id: Mapped[str] = mapped_column(String(36), ForeignKey("procedures.id", ondelete="CASCADE"), nullable=False)
    jurisdiction_id: Mapped[str] = mapped_column(String(36), ForeignKey("jurisdictions.id", ondelete="CASCADE"), nullable=False)
    legal_status: Mapped[LegalStatus] = mapped_column(SAEnum(LegalStatus), nullable=False)
    access_pathway_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eligibility_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    oversight_quality: Mapped[Optional[OversightQuality]] = mapped_column(SAEnum(OversightQuality), nullable=True)
    oversight_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_cost_range_usd: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cost_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    residency_travel_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    arbitrage_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_verified: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sources: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    status: Mapped[str] = mapped_column(String(20), default="active")

    procedure: Mapped["Procedure"] = relationship(back_populates="access_records")
    jurisdiction: Mapped["Jurisdiction"] = relationship(back_populates="access_records")

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "procedure_id": self.procedure_id,
            "jurisdiction_id": self.jurisdiction_id,
            "legal_status": self.legal_status.value if isinstance(self.legal_status, LegalStatus) else self.legal_status,
            "access_pathway_details": self.access_pathway_details,
            "eligibility_requirements": self.eligibility_requirements,
            "provider_requirements": self.provider_requirements,
            "oversight_quality": self.oversight_quality.value if isinstance(self.oversight_quality, OversightQuality) else self.oversight_quality if self.oversight_quality else None,
            "oversight_notes": self.oversight_notes,
            "estimated_cost_range_usd": self.estimated_cost_range_usd,
            "cost_notes": self.cost_notes,
            "residency_travel_notes": self.residency_travel_notes,
            "risk_notes": self.risk_notes,
            "arbitrage_summary": self.arbitrage_summary,
            "last_verified": self.last_verified.isoformat() if self.last_verified else None,
            "sources": json.loads(self.sources) if self.sources else [],
            "status": self.status,
        }