"""FastAPI application for MedFreedom Arbitrage Map."""
import json
import csv
import io
import os
from datetime import date, datetime
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from .database import init_db, reset_db, get_db, SessionLocal
from .models import Jurisdiction, Procedure, AccessRecord, Condition, ProcedureIndication, WatchSubscription
from .access_flags import enrich_access_dict
from .email_digest import (
    valid_email,
    email_configured,
    resolve_watch_items,
    build_digest_text,
    build_digest_html,
    send_email,
    upsert_subscription,
    snapshot_from_resolved,
    apply_snapshot_to_items,
)
from .schemas import (
    JurisdictionCreate, JurisdictionUpdate,
    ProcedureCreate, ProcedureUpdate,
    AccessRecordCreate, AccessRecordUpdate,
    AccessRecordFilter, BulkImportRequest,
)

app = FastAPI(
    title="MedFreedom Provider Map API",
    description="Cross-jurisdiction market entry data for providers: legal status, regulation links, setup requirements, and evidence grades",
    version="0.3.0",
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
    # Non-destructive: create tables if missing, never drop existing data.
    init_db()


# ── Meta / health / admin ───────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve the dashboard UI."""
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path, media_type="text/html")
    return {"message": "MedFreedom Arbitrage Map API", "version": "0.2.0"}


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.3.0", "audience": "providers"}


@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    """Row counts for the dashboard — one cheap round-trip."""
    priced = (
        db.query(func.count(AccessRecord.id))
        .filter(AccessRecord.price_usd.isnot(None))
        .scalar()
        or 0
    )
    with_pathway = (
        db.query(func.count(AccessRecord.id))
        .filter(AccessRecord.access_pathway.isnot(None))
        .scalar()
        or 0
    )
    disease_names = set()
    for p in db.query(Procedure).all():
        if p.diseases:
            try:
                disease_names.update(json.loads(p.diseases))
            except Exception:
                pass
    return {
        "jurisdictions": db.query(func.count(Jurisdiction.id)).scalar() or 0,
        "procedures": db.query(func.count(Procedure.id)).scalar() or 0,
        "access_records": db.query(func.count(AccessRecord.id)).scalar() or 0,
        "conditions": db.query(func.count(Condition.id)).scalar() or 0,
        "procedure_indications": db.query(func.count(ProcedureIndication.id)).scalar() or 0,
        "diseases": len(disease_names),
        "access_records_with_price": priced,
        "access_records_with_pathway": with_pathway,
    }


@app.post("/api/seed")
def seed_endpoint(reset: bool = False, db: Session = Depends(get_db)):
    """Seed the database. Pass ?reset=true to drop and rebuild the schema first.

    Idempotent: without reset it only fills what is empty, so it is safe to call
    repeatedly (e.g. after the free-tier instance restarts).
    """
    try:
        if reset:
            db.close()
            reset_db()
        from .seed import seed_database
        result = seed_database()
        return {"status": "ok", **result}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ══════════════════════════════════════════════════════════════════════════
# JURISDICTIONS
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/jurisdictions")
def list_jurisdictions(db: Session = Depends(get_db)):
    return [j.to_dict() for j in db.query(Jurisdiction).order_by(Jurisdiction.name).all()]


@app.get("/api/jurisdictions/map-data")
def list_jurisdictions_map(db: Session = Depends(get_db)):
    """Minimal jurisdiction data for map markers."""
    return [
        {
            "id": j.id,
            "name": j.name,
            "type": j.type.value if hasattr(j.type, "value") else j.type,
            "country_code": j.country_code,
            "latitude": j.latitude,
            "longitude": j.longitude,
            "general_notes": j.general_notes,
        }
        for j in db.query(Jurisdiction).all()
    ]


@app.get("/api/jurisdictions/{jurisdiction_id}")
def get_jurisdiction(jurisdiction_id: str, db: Session = Depends(get_db)):
    """Full jurisdiction profile for the user-facing explorer (notes + treatments available there)."""
    j = db.query(Jurisdiction).filter(Jurisdiction.id == jurisdiction_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")

    parent = None
    if j.parent_id:
        p = db.query(Jurisdiction).filter(Jurisdiction.id == j.parent_id).first()
        if p:
            parent = {"id": p.id, "name": p.name, "level": p.level.value if hasattr(p.level, "value") else p.level}

    children = [
        {
            "id": c.id,
            "name": c.name,
            "level": c.level.value if hasattr(c.level, "value") else c.level,
            "type": c.type.value if hasattr(c.type, "value") else c.type,
        }
        for c in db.query(Jurisdiction).filter(Jurisdiction.parent_id == jurisdiction_id).order_by(Jurisdiction.name).all()
    ]

    rows = (
        db.query(AccessRecord, Procedure)
        .join(Procedure, AccessRecord.procedure_id == Procedure.id)
        .filter(AccessRecord.jurisdiction_id == jurisdiction_id, AccessRecord.status == "active")
        .order_by(Procedure.name)
        .all()
    )

    return {
        **j.to_dict(),
        "parent": parent,
        "children": children,
        "treatments": [
            enrich_access_dict({
                **ar.to_dict(),
                "procedure_name": proc.name,
                "modality": proc.modality.value if hasattr(proc.modality, "value") else proc.modality,
                "regulatory_modality": (
                    proc.regulatory_modality.value
                    if proc.regulatory_modality and hasattr(proc.regulatory_modality, "value")
                    else proc.regulatory_modality
                ),
                "typical_us_cost_range": proc.typical_us_cost_range,
            })
            for ar, proc in rows
        ],
    }


@app.post("/api/jurisdictions")
def create_jurisdiction(data: JurisdictionCreate, db: Session = Depends(get_db)):
    j = Jurisdiction(**data.model_dump())
    db.add(j)
    db.commit()
    db.refresh(j)
    return j.to_dict()


@app.put("/api/jurisdictions/{jurisdiction_id}")
def update_jurisdiction(jurisdiction_id: str, data: JurisdictionUpdate, db: Session = Depends(get_db)):
    j = db.query(Jurisdiction).filter(Jurisdiction.id == jurisdiction_id).first()
    if not j:
        raise HTTPException(status_code=404, detail="Jurisdiction not found")
    for key, val in data.model_dump(exclude_unset=True).items():
        setattr(j, key, val)
    db.commit()
    db.refresh(j)
    return j.to_dict()


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

@app.get("/api/procedures")
def list_procedures(
    modality: Optional[str] = None,
    therapeutic_area: Optional[str] = None,
    disease: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Procedure)
    if modality:
        q = q.filter(Procedure.modality == modality)
    if therapeutic_area:
        q = q.filter(Procedure.therapeutic_areas.contains(therapeutic_area))
    if disease:
        # diseases stored as JSON text array — substring match is enough for seed data
        q = q.filter(Procedure.diseases.ilike(f"%{disease}%"))
    if search:
        q = q.filter(
            or_(
                Procedure.name.ilike(f"%{search}%"),
                Procedure.description.ilike(f"%{search}%"),
                Procedure.indications.ilike(f"%{search}%"),
                Procedure.therapeutic_areas.ilike(f"%{search}%"),
                Procedure.diseases.ilike(f"%{search}%"),
            )
        )
    return [p.to_dict() for p in q.order_by(Procedure.name).all()]


@app.get("/api/procedures/{procedure_id}")
def get_procedure(procedure_id: str, db: Session = Depends(get_db)):
    p = db.query(Procedure).filter(Procedure.id == procedure_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return p.to_dict()


@app.post("/api/procedures")
def create_procedure(data: ProcedureCreate, db: Session = Depends(get_db)):
    d = data.model_dump()
    d["therapeutic_areas"] = json.dumps(d.get("therapeutic_areas") or [])
    d["diseases"] = json.dumps(d.get("diseases") or [])
    d["sources"] = json.dumps(d.get("sources") or [])
    p = Procedure(**d)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p.to_dict()


@app.put("/api/procedures/{procedure_id}")
def update_procedure(procedure_id: str, data: ProcedureUpdate, db: Session = Depends(get_db)):
    p = db.query(Procedure).filter(Procedure.id == procedure_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Procedure not found")
    d = data.model_dump(exclude_unset=True)
    if "therapeutic_areas" in d:
        d["therapeutic_areas"] = json.dumps(d["therapeutic_areas"])
    if "diseases" in d:
        d["diseases"] = json.dumps(d["diseases"])
    if "sources" in d:
        d["sources"] = json.dumps(d["sources"])
    for key, val in d.items():
        setattr(p, key, val)
    db.commit()
    db.refresh(p)
    return p.to_dict()


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

def _access_row_to_dict(row) -> dict:
    """Merge an AccessRecord ORM row with the joined procedure/jurisdiction labels."""
    ar = row[0]
    d = ar.to_dict()
    d["procedure_name"] = row.procedure_name
    d["jurisdiction_name"] = row.jurisdiction_name
    d["modality"] = row.modality.value if hasattr(row.modality, "value") else row.modality
    d["procedure_subcategory"] = row.procedure_subcategory
    d["jurisdiction_type"] = row.jurisdiction_type.value if hasattr(row.jurisdiction_type, "value") else row.jurisdiction_type
    d["jurisdiction_country_code"] = row.jurisdiction_country_code
    d["jurisdiction_latitude"] = row.jurisdiction_latitude
    d["jurisdiction_longitude"] = row.jurisdiction_longitude
    return enrich_access_dict(d)


def _access_query(db: Session):
    return db.query(
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


@app.post("/api/access-records/query")
def query_access_records(filters: AccessRecordFilter, db: Session = Depends(get_db)):
    """Flexible query endpoint for access records with rich filtering."""
    q = _access_query(db).filter(AccessRecord.status == filters.status)

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
        term = f"%{filters.search}%"
        q = q.filter(
            or_(
                Procedure.name.ilike(term),
                Procedure.description.ilike(term),
                Procedure.indications.ilike(term),
                Procedure.therapeutic_areas.ilike(term),
                AccessRecord.access_pathway_details.ilike(term),
                AccessRecord.arbitrage_summary.ilike(term),
                Jurisdiction.name.ilike(term),
            )
        )

    return [_access_row_to_dict(r) for r in q.order_by(Procedure.name, Jurisdiction.name).all()]


@app.get("/api/access-records")
def list_access_records(
    procedure_id: Optional[str] = None,
    jurisdiction_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = _access_query(db)
    if procedure_id:
        q = q.filter(AccessRecord.procedure_id == procedure_id)
    if jurisdiction_id:
        q = q.filter(AccessRecord.jurisdiction_id == jurisdiction_id)
    return [_access_row_to_dict(r) for r in q.order_by(Procedure.name, Jurisdiction.name).all()]


@app.get("/api/access-records/{record_id}")
def get_access_record(record_id: str, db: Session = Depends(get_db)):
    ar = db.query(AccessRecord).filter(AccessRecord.id == record_id).first()
    if not ar:
        raise HTTPException(status_code=404, detail="Access record not found")
    return enrich_access_dict(ar.to_dict())


@app.post("/api/access-records")
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
    return ar.to_dict()


@app.put("/api/access-records/{record_id}")
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
    return ar.to_dict()


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
    term = f"%{q}%"

    procedures = db.query(Procedure).filter(
        or_(Procedure.name.ilike(term), Procedure.description.ilike(term),
            Procedure.indications.ilike(term), Procedure.therapeutic_areas.ilike(term))
    ).limit(20).all()

    jurisdictions = db.query(Jurisdiction).filter(
        or_(Jurisdiction.name.ilike(term), Jurisdiction.general_notes.ilike(term))
    ).limit(20).all()

    records = db.query(AccessRecord, Procedure.name, Jurisdiction.name)\
        .join(Procedure).join(Jurisdiction).filter(
            or_(
                AccessRecord.arbitrage_summary.ilike(term),
                AccessRecord.access_pathway_details.ilike(term),
            )
        ).limit(20).all()

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
    """All jurisdictions where a procedure is available, with access details."""
    procedure = db.query(Procedure).filter(Procedure.id == procedure_id).first()
    if not procedure:
        raise HTTPException(status_code=404, detail="Procedure not found")

    rows = db.query(AccessRecord, Jurisdiction).join(Jurisdiction).filter(
        AccessRecord.procedure_id == procedure_id,
        AccessRecord.status == "active",
    ).order_by(Jurisdiction.name).all()

    indications = (
        db.query(ProcedureIndication, Condition)
        .join(Condition, ProcedureIndication.condition_id == Condition.id)
        .filter(ProcedureIndication.procedure_id == procedure_id)
        .order_by(ProcedureIndication.evidence_grade)
        .all()
    )

    juris = [
        enrich_access_dict({**ar.to_dict(), "jurisdiction": j.to_dict()})
        for ar, j in rows
    ]
    summary = {
        "total": len(juris),
        "allowed": sum(1 for x in juris if x.get("access_flags", {}).get("allowed")),
        "offered": sum(1 for x in juris if x.get("access_flags", {}).get("offered")),
        "allowed_not_offered": sum(
            1 for x in juris
            if x.get("access_flags", {}).get("allowed") and not x.get("access_flags", {}).get("offered")
        ),
        "trial_only": sum(1 for x in juris if x.get("access_flags", {}).get("trial_only")),
        "prohibited": sum(1 for x in juris if x.get("access_flags", {}).get("prohibited")),
        "pending_legislation": sum(1 for x in juris if x.get("access_flags", {}).get("pending_legislation")),
        "legislation_watch": sum(1 for x in juris if x.get("access_flags", {}).get("legislation_watch")),
    }
    return {
        "procedure": procedure.to_dict(),
        "jurisdictions": juris,
        "summary": summary,
        "indications": [
            {**pi.to_dict(), "condition": c.to_dict()}
            for pi, c in indications
        ],
    }


# ══════════════════════════════════════════════════════════════════════════
# CONDITIONS & EVIDENCE (§5)
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/conditions")
def list_conditions(db: Session = Depends(get_db)):
    return [c.to_dict() for c in db.query(Condition).order_by(Condition.name).all()]


@app.get("/api/conditions/{condition_id}")
def get_condition(condition_id: str, db: Session = Depends(get_db)):
    c = db.query(Condition).filter(Condition.id == condition_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Condition not found")
    indications = (
        db.query(ProcedureIndication, Procedure)
        .join(Procedure, ProcedureIndication.procedure_id == Procedure.id)
        .filter(ProcedureIndication.condition_id == condition_id)
        .order_by(ProcedureIndication.evidence_grade)
        .all()
    )
    return {
        **c.to_dict(),
        "indications": [
            {**pi.to_dict(), "procedure": p.to_dict()}
            for pi, p in indications
        ],
    }


@app.get("/api/procedure-indications")
def list_procedure_indications(
    procedure_id: Optional[str] = None,
    condition_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = (
        db.query(ProcedureIndication, Procedure, Condition)
        .join(Procedure, ProcedureIndication.procedure_id == Procedure.id)
        .join(Condition, ProcedureIndication.condition_id == Condition.id)
    )
    if procedure_id:
        q = q.filter(ProcedureIndication.procedure_id == procedure_id)
    if condition_id:
        q = q.filter(ProcedureIndication.condition_id == condition_id)
    rows = q.order_by(Condition.name, Procedure.name).all()
    return [
        {
            **pi.to_dict(),
            "procedure_name": p.name,
            "condition_name": c.name,
            "condition_icd": c.icd_code,
        }
        for pi, p, c in rows
    ]


@app.get("/api/diseases")
def list_diseases(db: Session = Depends(get_db)):
    """Unique disease names across treatments, with how many treatments target each."""
    counts = {}
    for p in db.query(Procedure).all():
        for d in (json.loads(p.diseases) if p.diseases else []):
            counts[d] = counts.get(d, 0) + 1
    return [
        {"name": name, "treatment_count": counts[name]}
        for name in sorted(counts.keys(), key=str.lower)
    ]


@app.get("/api/filters/options")
def get_filter_options(db: Session = Depends(get_db)):
    """All available filter values for the UI."""
    procedures = db.query(Procedure).all()
    jurisdictions = db.query(Jurisdiction).all()

    modalities = sorted({p.modality.value if hasattr(p.modality, "value") else p.modality for p in procedures})
    therapeutic_areas = set()
    diseases = set()
    for p in procedures:
        therapeutic_areas.update(json.loads(p.therapeutic_areas) if p.therapeutic_areas else [])
        diseases.update(json.loads(p.diseases) if p.diseases else [])

    return {
        "modalities": modalities,
        "therapeutic_areas": sorted(therapeutic_areas),
        "diseases": sorted(diseases, key=str.lower),
        "legal_statuses": [
            "Fully_Approved", "Regulated_Therapy_Program", "Decriminalized_Possession",
            "Right_To_Try", "Clinical_Trial_Only", "Physician_Discretion_Gray", "Prohibited",
        ],
        "oversight_qualities": ["High", "Medium", "Low", "Variable"],
        "jurisdictions": [
            {"id": j.id, "name": j.name, "type": j.type.value if hasattr(j.type, "value") else j.type}
            for j in jurisdictions
        ],
    }


# ══════════════════════════════════════════════════════════════════════════
# EXPORT
# ══════════════════════════════════════════════════════════════════════════

@app.get("/api/export/json")
def export_json(db: Session = Depends(get_db)):
    """Export all data as JSON."""
    return {
        "jurisdictions": [j.to_dict() for j in db.query(Jurisdiction).all()],
        "procedures": [p.to_dict() for p in db.query(Procedure).all()],
        "access_records": [r.to_dict() for r in db.query(AccessRecord).all()],
        "conditions": [c.to_dict() for c in db.query(Condition).all()],
        "procedure_indications": [pi.to_dict() for pi in db.query(ProcedureIndication).all()],
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
        "Procedure", "Jurisdiction", "Legal Status", "Access Pathway", "Oversight Quality",
        "Price USD", "Price Confidence", "Cost Range (USD)", "Access Pathway Details",
        "Eligibility", "Provider Requirements",
        "Residency/Travel Notes", "Risk Notes", "Last Verified", "Arbitrage Summary",
    ])
    for ar, pname, jname in rows:
        writer.writerow([
            pname, jname,
            ar.legal_status.value if hasattr(ar.legal_status, "value") else ar.legal_status,
            ar.access_pathway.value if ar.access_pathway and hasattr(ar.access_pathway, "value") else ar.access_pathway,
            ar.oversight_quality.value if ar.oversight_quality and hasattr(ar.oversight_quality, "value") else ar.oversight_quality,
            ar.price_usd,
            ar.price_confidence.value if ar.price_confidence and hasattr(ar.price_confidence, "value") else ar.price_confidence,
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


# ══════════════════════════════════════════════════════════════════════════
# WATCHLIST EMAIL DIGESTS
# ══════════════════════════════════════════════════════════════════════════

def _request_base_url() -> str:
    return (os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")


@app.get("/api/watch/status")
def watch_email_status():
    """Whether outbound email is configured (Resend or SMTP)."""
    cfg = email_configured()
    return {
        "email": cfg,
        "digest_secret_set": bool(os.getenv("DIGEST_SECRET")),
        "note": "Without RESEND_API_KEY or SMTP_*, digests can still be previewed and copied; send will be log-only / fail soft.",
    }


@app.post("/api/watch/subscribe")
def watch_subscribe(payload: dict, db: Session = Depends(get_db)):
    """Upsert email + watch items for weekly/daily digests.

    Body: { email, items: [{procedure_id|therapyId, jurisdiction_id|jurId, ...}], frequency?: weekly|daily }
    """
    email = (payload or {}).get("email") or ""
    if not valid_email(email):
        raise HTTPException(400, "Valid email required")
    items = (payload or {}).get("items") or []
    if not isinstance(items, list) or not items:
        raise HTTPException(400, "items array required (at least one therapy×market)")
    freq = (payload or {}).get("frequency") or "weekly"
    sub = upsert_subscription(db, email, items, freq)
    # Build live preview for confirmation email optional
    resolved = resolve_watch_items(db, json.loads(sub.items_json))
    return {
        "status": "ok",
        "subscription": {
            "email": sub.email,
            "item_count": len(resolved),
            "frequency": sub.frequency,
            "id": sub.id,
        },
        "email_provider": email_configured(),
        "preview_changed": sum(1 for r in resolved if r.get("changed")),
    }


@app.post("/api/watch/digest/preview")
def watch_digest_preview(payload: dict, db: Session = Depends(get_db)):
    """Build a digest from items (no send). Body: { email?, items }."""
    email = ((payload or {}).get("email") or "you@example.com").strip()
    items = (payload or {}).get("items") or []
    resolved = resolve_watch_items(db, items)
    base = _request_base_url()
    text = build_digest_text(email, resolved, base_url=base)
    html = build_digest_html(email, resolved, base_url=base)
    return {
        "status": "ok",
        "text": text,
        "html": html,
        "resolved": resolved,
        "changed_count": sum(1 for r in resolved if r.get("changed")),
        "email_provider": email_configured(),
    }


@app.post("/api/watch/digest/send")
def watch_digest_send(payload: dict, db: Session = Depends(get_db)):
    """Send digest for one email subscription, or all if admin secret provided.

    Body options:
      { email } — send to that subscriber
      { all: true, secret } — send all active (secret must match DIGEST_SECRET)
      { email, items, force: true } — one-off send without requiring subscription
    """
    payload = payload or {}
    base = _request_base_url()
    secret = os.getenv("DIGEST_SECRET") or ""

    if payload.get("all"):
        if not secret or payload.get("secret") != secret:
            raise HTTPException(403, "Invalid or missing DIGEST_SECRET")
        subs = db.query(WatchSubscription).filter(WatchSubscription.active.is_(True)).all()
        results = []
        for sub in subs:
            results.append(_send_one_sub(db, sub, base))
        return {"status": "ok", "sent": results}

    email = (payload.get("email") or "").strip().lower()
    if not valid_email(email):
        raise HTTPException(400, "Valid email required")

    # One-off with explicit items
    if payload.get("items") and payload.get("force"):
        items = payload["items"]
        resolved = resolve_watch_items(db, items)
        text = build_digest_text(email, resolved, base_url=base)
        html = build_digest_html(email, resolved, base_url=base)
        subject = "MedFreedom watchlist digest"
        if any(r.get("changed") for r in resolved):
            subject = f"MedFreedom: {sum(1 for r in resolved if r.get('changed'))} market status change(s)"
        send_result = send_email(email, subject, text, html)
        return {
            "status": "ok" if send_result.get("ok") else "send_failed",
            "send": send_result,
            "text": text if not send_result.get("ok") else None,
            "changed_count": sum(1 for r in resolved if r.get("changed")),
        }

    sub = (
        db.query(WatchSubscription)
        .filter(WatchSubscription.email == email, WatchSubscription.active.is_(True))
        .first()
    )
    if not sub:
        raise HTTPException(404, "No active subscription for this email — call /api/watch/subscribe first")
    result = _send_one_sub(db, sub, base)
    return {"status": "ok" if result.get("send", {}).get("ok") else "send_failed", **result}


def _send_one_sub(db: Session, sub: WatchSubscription, base: str) -> dict:
    items = json.loads(sub.items_json) if sub.items_json else []
    snap = json.loads(sub.last_snapshot_json) if sub.last_snapshot_json else {}
    items_with_prev = apply_snapshot_to_items(items, snap)
    resolved = resolve_watch_items(db, items_with_prev)
    text = build_digest_text(sub.email, resolved, base_url=base, unsub_token=sub.unsubscribe_token)
    html = build_digest_html(sub.email, resolved, base_url=base, unsub_token=sub.unsubscribe_token)
    changed_n = sum(1 for r in resolved if r.get("changed"))
    subject = "MedFreedom watchlist digest"
    if changed_n:
        subject = f"MedFreedom: {changed_n} market status change(s)"
    send_result = send_email(sub.email, subject, text, html)
    # Always update snapshot after an attempted send so change detection advances
    if send_result.get("ok") or os.getenv("DIGEST_UPDATE_ON_FAIL") == "1":
        sub.last_snapshot_json = json.dumps(snapshot_from_resolved(resolved))
        sub.last_sent_at = datetime.now()
        # Keep last_verdict on items for client sync
        by_key = {
            f"{r['procedure_id']}::{r['jurisdiction_id']}": r.get("verdict")
            for r in resolved
        }
        new_items = []
        for it in items:
            pid = it.get("procedure_id") or it.get("therapyId")
            jid = it.get("jurisdiction_id") or it.get("jurId")
            d = dict(it)
            if pid and jid and by_key.get(f"{pid}::{jid}"):
                d["last_verdict"] = by_key[f"{pid}::{jid}"]
            new_items.append(d)
        sub.items_json = json.dumps(new_items)
        db.commit()
    return {
        "email": sub.email,
        "changed_count": changed_n,
        "item_count": len(resolved),
        "send": send_result,
        "text": None if send_result.get("ok") else text,
    }


@app.get("/api/watch/unsubscribe")
def watch_unsubscribe(token: str = Query(...), db: Session = Depends(get_db)):
    sub = db.query(WatchSubscription).filter(WatchSubscription.unsubscribe_token == token).first()
    if not sub:
        raise HTTPException(404, "Invalid token")
    sub.active = False
    db.commit()
    return {"status": "ok", "message": f"Unsubscribed {sub.email}"}


# ── Run with: uvicorn app.main:app --reload ──────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
