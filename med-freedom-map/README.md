# MedFreedom Arbitrage Map

**Medical Procedure Access by Jurisdiction - An Informed Arbitrage Tool**

Compare legal pathways, costs, oversight quality, and eligibility requirements for 20+ high-impact medical procedures across 16 jurisdictions worldwide.

> **⚠ DISCLAIMER:** For informational purposes only. Not medical, legal, or travel advice. Data may be inaccurate. Verify with official sources.

---

## Quick Start

### Backend (Python/FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On first run, the database auto-seeds with 16 jurisdictions, 21 procedures, and 27 access records. API docs at `http://localhost:8000/docs`.

### Frontend

Open `frontend/index.html` directly in a browser (it connects to `http://localhost:8000/api` by default), or serve with:

```bash
cd frontend
python -m http.server 3000
# Open http://localhost:3000
```

---

## Architecture

```
med-freedom-map/
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── models.py       # SQLAlchemy: Jurisdiction, Procedure, AccessRecord
│       ├── database.py     # SQLite engine & session
│       ├── schemas.py      # Pydantic request/response schemas
│       ├── seed.py         # Initial data (16 jdx, 21 procedures, 27 records)
│       └── main.py         # FastAPI: full CRUD, filters, search, export
├── frontend/
│   └── index.html          # SPA: public view + admin panel + Leaflet map
└── README.md
```

### Database (3 tables)

| Table | Key Fields |
|-------|-----------|
| **jurisdictions** | name, type (Country/US_State/ZEDE/etc), lat/lng |
| **procedures** | name, modality, therapeutic_areas, cost_range |
| **access_records** | procedure_id + jurisdiction_id, legal_status, oversight_quality, costs, eligibility, risk_notes, arbitrage_summary, sources |

### Enums

- **Legal Status:** Fully_Approved, Regulated_Therapy_Program, Decriminalized_Possession, Right_To_Try, Clinical_Trial_Only, Physician_Discretion_Gray, Prohibited
- **Oversight Quality:** High, Medium, Low, Variable
- **Modalities:** Psychedelics, Gene_Therapy, Stem_Cell, Peptide, Repurposed_Drug, Reproductive_Tech, Assisted_Dying

---

## Features

### Public View
- Search bar (procedures, conditions, treatments)
- 4 dropdown filters (modality, therapeutic area, legal status, oversight quality)
- Interactive Leaflet map with color-coded jurisdiction markers
- Sortable data table with clickable row detail modal
- CSV and JSON export
- Dark/light theme toggle
- Prominent disclaimer banner (dismissible)

### Admin Panel
- CRUD for procedures, jurisdictions, and access records
- Bulk JSON import
- Inline forms with all fields from the schema
- Cascade deletes (deleting a procedure/jurisdiction removes its access records)

### Detail Modal
- Full access record view: legal status badge, oversight, costs, eligibility, provider requirements, residency/travel notes, risk notes, arbitrage summary with source links

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET/POST | `/api/jurisdictions` | List/Create jurisdictions |
| GET/PUT/DELETE | `/api/jurisdictions/{id}` | Read/Update/Delete jurisdiction |
| GET/POST | `/api/procedures` | List/Create procedures |
| GET/PUT/DELETE | `/api/procedures/{id}` | Read/Update/Delete procedure |
| GET/POST | `/api/access-records` | List/Create access records |
| POST | `/api/access-records/query` | Flexible filtered query |
| GET/PUT/DELETE | `/api/access-records/{id}` | Read/Update/Delete access record |
| GET | `/api/filters/options` | Get all filter dropdown values |
| GET | `/api/search?q=...` | Unified search |
| GET | `/api/export/json` | Full JSON export |
| GET | `/api/export/csv` | CSV download |
| POST | `/api/bulk-import` | Bulk import jurisdictions + procedures + records |

---

## Seed Data (27 access records)

### Psychedelics
- Psilocybin for TRD → Oregon (Regulated), Colorado (Regulated), Australia (Fully Approved), Canada (Physician Discretion), Jamaica (Legal/Unregulated)
- Psilocybin for EOL Anxiety → Oregon (Regulated)
- MDMA for PTSD → Australia (Fully Approved)
- Ketamine for Depression → US Federal (Fully Approved), Oregon
- Ibogaine for Addiction → Mexico (Variable quality)
- DMT for Depression → Colorado (Decriminalized, Low oversight)
- LSD for Anxiety → Switzerland (Physician Discretion, High)

### Gene Therapy
- CRISPR Gene Therapy → Próspera ZEDE (Low oversight), US Federal (Right to Try)

### Stem Cell
- MSC Therapy → Mexico (Variable), Próspera ZEDE (Low)
- CAR-T → US Federal (Fully Approved, High)

### Assisted Dying
- MAID → Canada (Fully Approved, High), Switzerland (Fully Approved, High)

### Reproductive
- IVF + PGT → US Federal (High), Mexico (Variable)
- Surrogacy → Canada (Altruistic, High)

### Repurposed Drugs
- GLP-1 Agonists → US Federal (Fully Approved)
- Rapamycin (Longevity) → US Federal (Physician Discretion, Medium)

---

## Extending the Taxonomy

1. Add new modalities to the `Modality` enum in `models.py` and `MODALITIES` array in `index.html`
2. Add new therapeutic areas via the admin panel or seed data
3. New legal statuses: add to `LegalStatus` enum + frontend `LEGAL_STATUSES` array
4. Run `python -m app.seed` to re-seed after schema changes

---

## Tech Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy, SQLite (MVP)
- **Frontend:** Vanilla HTML/CSS/JS, Leaflet.js for maps
- **Future:** PostgreSQL + PostGIS, React/Next.js, Supabase Auth