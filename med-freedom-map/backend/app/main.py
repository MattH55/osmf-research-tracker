"""FastAPI application for MedFreedom Arbitrage Map."""
import json
import csv
import io
from datetime import date, datetime
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .database import init_db, get_db, SessionLocal
from .models import Jurisdiction, Procedure, AccessRecord
from .schemas import (
    JurisdictionCreate, JurisdictionUpdate, JurisdictionResponse,
    ProcedureCreate, ProcedureUpdate, ProcedureResponse,
    AccessRecordCreate, AccessRecordUpdate, AccessRecordResponse,
    AccessRecordFilter, BulkImportRequest, ExportResponse,
)

app = FastAPI(
    title="MedFreedom Arbitrage Map API",
    description="Medical procedure access by jurisdiction for informed arbitrage decisions",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    # Initialize database schema (don't auto-seed due to field length constraints)
    # Run seeding manually via Shell: python -m app.seed


# ── Health Check ──────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/api/seed")
def seed_endpoint(db: Session = Depends(get_db)):
    """Manually trigger database seeding (only runs if tables are empty)."""
    try:
        jur_count = db.query(Jurisdiction).count()
        if jur_count > 0:
            return {"status": "already_seeded", "jurisdictions": jur_count}

        from .seed import seed_database
        seed_database()
        return {"status": "seeding_complete", "message": "Database seeded successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ══════════════════════════════════════════════════════════════════════════
# JURISDICTIONS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/jurisdictions", response_model=List[JurisdictionResponse])
def list_jurisdictions(db: Session = Depends(get_db)):
    return db.query(Jurisdiction).order_by(Jurisdiction.name).all()


@app.get("/api/jurisdictions/map-data")
def list_jurisdictions_map(db: Session = Depends(get_db)):
    """Return minimal jurisdiction data for map markers."""
    jurisdictions = db.query(Jurisdiction).all()
    return [
        {
            "id": j.id,
            "name": j.name,
            "type": j.type.value if hasattr(j.type, 'value') else j.type,
            "country_code": j.country_code,
            "latitude": j.latitude,
            "longitude": j.longitude,
            "general_notes": j.general_notes,
        }
        for j in jurisdictions
    ]


@app.get("/api/jurisdictions/{jurisdiction_id}", response_model=JurisdictionResponse)
def get_jurisdiction(jurisdiction_id: str, db: Session = Depends(get_db)):
    j = db.query(Jurisdiction).filter(Jurisdiction.id == jurisdiction_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")
    return j


@app.post("/api/jurisdictions", response_model=JurisdictionResponse)
def create_jurisdiction(data: JurisdictionCreate, db: Session = Depends(get_db)):
    j = Jurisdiction(**data.model_dump())
    db.add(j)
    db.commit()
    db.refresh(j)
    return j


@app.put("/api/jurisdictions/{jurisdiction_id}", response_model=JurisdictionResponse)
def update_jurisdiction(jurisdiction_id: str, data: JurisdictionUpdate, db: Session = Depends(get_db)):
    j = db.query(Jurisdiction).filter(Jurisdiction.id == jurisdiction_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(j, key, val)
    j.last_updated = datetime.utcnow()
    db.commit()
    db.refresh(j)
    return j


@app.delete("/api/jurisdictions/{jurisdiction_id}")
def delete_jurisdiction(jurisdiction_id: str, db: Session = Depends(get_db)):
    j = db.query(Jurisdiction).filter(Jurisdiction.id == jurisdiction_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")
    db.delete(j)
    db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# PROCEDURES
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/procedures", response_model=List[ProcedureResponse])
def list_procedures(
    modality: Optional[str] = None,
    therapeutic_area: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Procedure)
    if modality:
        q = q.filter(Procedure.modality == modality)
    if therapeutic_area:
        q = q.filter(Procedure.therapeutic_areas.contains(therapeutic_area))
    if search:
        q = q.filter(
            or_(
                Procedure.name.ilike(f"%{search}%"),
                Procedure.description.ilike(f"%{search}%"),
                Procedure.indications.ilike(f"%{search}%"),
                Procedure.therapeutic_areas.ilike(f"%{search}%"),
            )
        )
    return q.order_by(Procedure.name).all()


@app.get("/api/procedures/{procedure_id}", response_model=ProcedureResponse)
def get_procedure(procedure_id: str, db: Session = Depends(get_db)):
    p = db.query(Procedure).filter(Procedure.id == procedure_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return p


@app.post("/api/procedures", response_model=ProcedureResponse)
def create_procedure(data: ProcedureCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    d["therapeutic_areas"] = json.dumps(d["therapeutic_areas"])
    d["sources"] = json.dumps(d["sources"])
    p = Procedure(**d)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@app.put("/api/procedures/{procedure_id}", response_model=ProcedureResponse)
def update_procedure(procedure_id: str, data: ProcedureUpdate, db: Session = Depends(get_db)):
    p = db.query(Procedure).filter(Procedure.id == procedure_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procedure not found")
    d = data.model_dump(exclude_unset=True)
    if "therapeutic_areas" in d:
        d["therapeutic_areas"] = json.dumps(d["therapeutic_areas"])
    if "sources" in d:
        d["sources"] = json.dumps(d["sources"])
    for key, val in d.items():
        setattr(p, key, val)
    db.commit()
    db.refresh(p)
    return p


@app.delete("/api/procedures/{procedure_id}")
def delete_procedure(procedure_id: str, db: Session = Depends(get_db)):
    p = db.query(Procedure).filter(Procedure.id == procedure_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procedure not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# ACCESS RECORDS
# ══════════════════════════════════════════════════════════════════════════

@app.post("/api/access-records/query", response_model=List[AccessRecordResponse])
def query_access_records(filters: AccessRecordFilter, db: Session = Depends(get_db)):
    """Flexible query endpoint for access records with rich filtering."""
    q = db.query(
        AccessRecord,
        Procedure.name.label("procedure_name"),
        Procedure.modality.label("modality"),
        Procedure.subcategory.label("procedure_subcategory"),
        Jurisdiction.name.label("jurisdiction_name"),
        Jurisdiction.type.label("jurisdiction_type"),
        Jurisdiction.country_code.label("jurisdiction_country_code"),
        Jurisdiction.latitude.label("jurisdiction_latitude"),
        Jurisdiction.longitude.label("jurisdiction_longitude"),
    ).join(Procedure).join(Jurisdiction)

    q = q.filter(AccessRecord.status == filters.status)

    if filters.procedure_id:
        q = q.filter(AccessRecord.procedure_id == filters.procedure_id)
    if filters.jurisdiction_id:
        q = q.filter(AccessRecord.jurisdiction_id == filters.jurisdiction_id)
    if filters.modality:
        q = q.filter(Procedure.modality.in_(filters.modality))
    if filters.legal_status:
        q = q.filter(AccessRecord.legal_status.in_(filters.legal_status))
    if filters.oversight_quality:
        q = q.filter(AccessRecord.oversight_quality.in_(filters.oversight_quality))
    if filters.therapeutic_area:
        q = q.filter(Procedure.therapeutic_areas.contains(filters.therapeutic_area))
    if filters.search:
        search_term = f"%{filters.search}%"
        q = q.filter(
            or_(
                Procedure.name.ilike(search_term),
                Procedure.description.ilike(search_term),
                Procedure.indications.ilike(search_term),
                Procedure.therapeutic_areas.ilike(search_term),
                AccessRecord.access_pathway_details.ilike(search_term),
                AccessRecord.arbitrage_summary.ilike(search_term),
                Jurisdiction.name.ilike(search_term),
            )
        )

    results = q.order_by(Procedure.name, Jurisdiction.name).all()
    output = []
    for row in results:
        ar = row[0]
        d = ar.to_dict()
        d["procedure_name"] = row.procedure_name
        d["jurisdiction_name"] = row.jurisdiction_name
        d["modality"] = row.modality.value if hasattr(row.modality, 'value') else row.modality
        d["procedure_subcategory"] = row.procedure_subcategory
        d["jurisdiction_type"] = row.jurisdiction_type.value if hasattr(row.jurisdiction_type, 'value') else row.jurisdiction_type
        d["jurisdiction_country_code"] = row.jurisdiction_country_code
        d["jurisdiction_latitude"] = row.jurisdiction_latitude
        d["jurisdiction_longitude"] = row.jurisdiction_longitude
        output.append(d)
    return output


@app.get("/api/access-records", response_model=List[AccessRecordResponse])
def list_access_records(
    procedure_id: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(
        AccessRecord,
        Procedure.name.label("procedure_name"),
        Procedure.modality.label("modality"),
        Procedure.subcategory.label("procedure_subcategory"),
        Jurisdiction.name.label("jurisdiction_name"),
        Jurisdiction.type.label("jurisdiction_type"),
        Jurisdiction.country_code.label("jurisdiction_country_code"),
        Jurisdiction.latitude.label("jurisdiction_latitude"),
        Jurisdiction.longitude.label("jurisdiction_longitude"),
    ).join(Procedure).join(Jurisdiction)

    if procedure_id:
        q = q.filter(AccessRecord.procedure_id == procedure_id)
    if jurisdiction_id:
        q = q.filter(AccessRecord.jurisdiction_id == jurisdiction_id)

    results = q.order_by(Procedure.name, Jurisdiction.name).all()
    output = []
    for row in results:
        ar = row[0]
        d = ar.to_dict()
        d["procedure_name"] = row.procedure_name
        d["jurisdiction_name"] = row.jurisdiction_name
        d["modality"] = row.modality.value if hasattr(row.modality, 'value') else row.modality
        d["procedure_subcategory"] = row.procedure_subcategory
        d["jurisdiction_type"] = row.jurisdiction_type.value if hasattr(row.jurisdiction_type, 'value') else row.jurisdiction_type
        d["jurisdiction_country_code"] = row.jurisdiction_country_code
        d["jurisdiction_latitude"] = row.jurisdiction_latitude
        d["jurisdiction_longitude"] = row.jurisdiction_longitude
        output.append(d)
    return output


@app.get("/api/access-records/{record_id}", response_model=AccessRecordResponse)
def get_access_record(record_id: str, db: Session = Depends(get_db)):
    ar = db.query(AccessRecord).filter(AccessRecord.id == record_id).first()
    if not ar:
        raise HTTPException(status_code=404, detail="Access record not found")
    return ar


@app.post("/api/access-records", response_model=AccessRecordResponse)
def create_access_record(data: AccessRecordCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    if d.get("last_verified"):
        d["last_verified"] = date.fromisoformat(d["last_verified"])
    else:
        d.pop("last_verified", None)
    d["sources"] = json.dumps(d["sources"])
    ar = AccessRecord(**d)
    db.add(ar)
    db.commit()
    db.refresh(ar)
    return ar


@app.put("/api/access-records/{record_id}", response_model=AccessRecordResponse)
def update_access_record(record_id: str, data: AccessRecordUpdate, db: Session = Depends(get_db)):
    ar = db.query(AccessRecord).filter(AccessRecord.id == record_id).first()
    if not ar:
        raise HTTPException(status_code=404, detail="Access record not found")
    d = data.model_dump(exclude_unset=True)
    if d.get("last_verified"):
        d["last_verified"] = date.fromisoformat(d["last_verified"])
    if "sources" in d:
        d["sources"] = json.dumps(d["sources"])
    for key, val in d.items():
        setattr(ar, key, val)
    db.commit()
    db.refresh(ar)
    return ar


@app.delete("/api/access-records/{record_id}")
def delete_access_record(record_id: str, db: Session = Depends(get_db)):
    ar = db.query(AccessRecord).filter(AccessRecord.id == record_id).first()
    if not ar:
        raise HTTPException(status_code=404, detail="Access record not found")
    db.delete(ar)
    db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# SEARCH & DISCOVERY
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/search")
def search_all(q: str, db: Session = Depends(get_db)):
    """Unified search across procedures, jurisdictions, and access records."""
    search_term = f"%{q}%"

    procedures = db.query(Procedure).filter(
        or_(Procedure.name.ilike(search_term), Procedure.description.ilike(search_term))
    ).limit(10).all()

    jurisdictions = db.query(Jurisdiction).filter(
        Jurisdiction.name.ilike(search_term)
    ).limit(10).all()

    records = db.query(AccessRecord, Procedure.name, Jurisdiction.name)\
        .join(Procedure).join(Jurisdiction).filter(
            or_(
                AccessRecord.arbitrage_summary.ilike(search_term),
                AccessRecord.access_pathway_details.ilike(search_term),
            )
        ).limit(10).all()

    return {
        "procedures": [p.to_dict() for p in procedures],
        "jurisdictions": [j.to_dict() for j in jurisdictions],
        "access_records": [
            {**ar[0].to_dict(), "procedure_name": ar[1], "jurisdiction_name": ar[2]}
            for ar in records
        ],
    }


@app.get("/api/procedures/{procedure_id}/jurisdictions")
def get_procedure_jurisdictions(procedure_id: str, db: Session = Depends(get_db)):
    """Get all jurisdictions where a procedure is available, with access details."""
    rows = db.query(
        AccessRecord, Jurisdiction
    ).join(Jurisdiction).filter(
        AccessRecord.procedure_id == procedure_id,
        AccessRecord.status == "active",
    ).order_by(Jurisdiction.name).all()

    procedure = db.query(Procedure).filter(Procedure.id == procedure_id).first()
    if not procedure:
        raise HTTPException(status_code=404, detail="Procedure not found")

    return {
        "procedure": procedure.to_dict(),
        "jurisdictions": [
            {**ar.to_dict(), "jurisdiction": j.to_dict()}
            for ar, j in rows
        ],
    }


@app.get("/api/filters/options")
def get_filter_options(db: Session = Depends(get_db)):
    """Return all available filter values for the UI."""
    procedures = db.query(Procedure).all()
    jurisdictions = db.query(Jurisdiction).all()

    modalities = sorted(list(set(p.modality.value if hasattr(p.modality, 'value') else p.modality for p in procedures)))
    therapeutic_areas = set()
    for p in procedures:
        tas = json.loads(p.therapeutic_areas) if p.therapeutic_areas else []
        therapeutic_areas.update(tas)
    therapeutic_areas = sorted(list(therapeutic_areas))

    legal_statuses = [
        "Fully_Approved", "Regulated_Therapy_Program", "Decriminalized_Possession",
        "Right_To_Try", "Clinical_Trial_Only", "Physician_Discretion_Gray", "Prohibited"
    ]
    oversight_qualities = ["High", "Medium", "Low", "Variable"]

    return {
        "modalities": modalities,
        "therapeutic_areas": therapeutic_areas,
        "legal_statuses": legal_statuses,
        "oversight_qualities": oversight_qualities,
        "jurisdictions": [{"id": j.id, "name": j.name, "type": j.type.value if hasattr(j.type, 'value') else j.type} for j in jurisdictions],
    }


# ══════════════════════════════════════════════════════════════════════════
# EXPORT ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/export/json")
def export_json(db: Session = Depends(get_db)):
    """Export all data as JSON."""
    jurisdictions = db.query(Jurisdiction).all()
    procedures = db.query(Procedure).all()
    records = db.query(AccessRecord).all()

    return {
        "jurisdictions": [j.to_dict() for j in jurisdictions],
        "procedures": [p.to_dict() for p in procedures],
        "access_records": [r.to_dict() for r in records],
    }


@app.get("/api/export/csv")
def export_csv(db: Session = Depends(get_db)):
    """Export access records as CSV."""
    rows = db.query(
        AccessRecord, Procedure.name.label("pname"), Jurisdiction.name.label("jname")
    ).join(Procedure).join(Jurisdiction).order_by(Procedure.name, Jurisdiction.name).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Procedure", "Jurisdiction", "Legal Status", "Oversight Quality",
        "Cost Range (USD)", "Access Pathway", "Eligibility", "Provider Requirements",
        "Residency/Travel Notes", "Risk Notes", "Last Verified", "Arbitrage Summary"
    ])
    for ar, pname, jname in rows:
        writer.writerow([
            pname, jname,
            ar.legal_status.value if hasattr(ar.legal_status, 'value') else ar.legal_status,
            ar.oversight_quality.value if ar.oversight_quality and hasattr(ar.oversight_quality, 'value') else ar.oversight_quality,
            ar.estimated_cost_range_usd, ar.access_pathway_details, ar.eligibility_requirements,
            ar.provider_requirements, ar.residency_travel_notes, ar.risk_notes,
            ar.last_verified, ar.arbitrage_summary,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=medfreedom_export.csv"},
    )


# ══════════════════════════════════════════════════════════════════════════
# BULK IMPORT
# ══════════════════════════════════════════════════════════════════════════

@app.post("/api/bulk-import")
def bulk_import(data: BulkImportRequest, db: Session = Depends(get_db)):
    created = {"jurisdictions": 0, "procedures": 0, "access_records": 0}

    for jd in data.jurisdictions:
        existing = db.query(Jurisdiction).filter(Jurisdiction.id == jd.id).first() if jd.id else None
        if not existing:
            db.add(Jurisdiction(**jd.model_dump()))
            created["jurisdictions"] += 1

    for pd in data.procedures:
        existing = db.query(Procedure).filter(Procedure.id == pd.id).first() if pd.id else None
        if not existing:
            d = pd.model_dump()
            d["therapeutic_areas"] = json.dumps(d["therapeutic_areas"])
            d["sources"] = json.dumps(d["sources"])
            db.add(Procedure(**d))
            created["procedures"] += 1

    db.flush()

    for ad in data.access_records:
        existing = db.query(AccessRecord).filter(AccessRecord.id == ad.id).first() if ad.id else None
        if not existing:
            d = ad.model_dump()
            if d.get("last_verified"):
                d["last_verified"] = date.fromisoformat(d["last_verified"])
            else:
                d.pop("last_verified", None)
            d["sources"] = json.dumps(d["sources"])
            db.add(AccessRecord(**d))
            created["access_records"] += 1

    db.commit()
    return {"ok": True, "created": created}


# ── Run with: uvicorn app.main:app --reload ──────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)