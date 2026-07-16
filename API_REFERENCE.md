# MedFreedom Arbitrage Map - API Reference

**Base URL**: `https://medfreedom-api.onrender.com`  
**API Version**: 0.1.0  
**Environment**: Production on Render

---

## Quick Start

### Health Check (Verify API is Running)

```bash
curl https://medfreedom-api.onrender.com/api/health
```

**Response** (200 OK):
```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## Jurisdictions

### List All Jurisdictions

```bash
curl https://medfreedom-api.onrender.com/api/jurisdictions
```

**Response** (200 OK):
```json
[
  {
    "id": "us_federal",
    "name": "United States (Federal)",
    "type": "SOVEREIGN",
    "level": "SOVEREIGN",
    "parent_id": null,
    "country_code": "US",
    "latitude": 39.8283,
    "longitude": -98.5795,
    "general_notes": "Federal jurisdiction; state laws may vary",
    "last_updated": "2026-07-16"
  },
  ...
]
```

### Get Specific Jurisdiction

```bash
curl https://medfreedom-api.onrender.com/api/jurisdictions/oregon
```

**Response** (200 OK):
```json
{
  "id": "oregon",
  "name": "Oregon",
  "type": "SUBNATIONAL",
  "level": "SUBNATIONAL",
  "parent_id": "us_federal",
  "country_code": "US",
  "latitude": 43.8041,
  "longitude": -120.5542,
  "general_notes": "Psilocybin legal for TRD/EOL as of 2023",
  "last_updated": "2026-07-16"
}
```

### Create Jurisdiction

```bash
curl -X POST https://medfreedom-api.onrender.com/api/jurisdictions \
  -H "Content-Type: application/json" \
  -d '{
    "id": "new_jurisdiction",
    "name": "New Place",
    "type": "SUBNATIONAL",
    "level": "SUBNATIONAL",
    "parent_id": "us_federal",
    "country_code": "US",
    "latitude": 40.0,
    "longitude": -100.0,
    "general_notes": "New test jurisdiction"
  }'
```

---

## Procedures

### List All Procedures

```bash
curl https://medfreedom-api.onrender.com/api/procedures
```

**Response** (200 OK):
```json
[
  {
    "id": "psilocybin_trd",
    "name": "Psilocybin for Treatment-Resistant Depression",
    "modality": "PSYCHEDELIC_THERAPY",
    "regulatory_modality": "CONTROLLED_SUBSTANCE",
    "restriction_driver": "CONTROLLED_SUBSTANCE",
    "subcategory": "Psychedelic-Assisted Therapy",
    "therapeutic_areas": ["Mental Health", "Neurology"],
    "description": "FDA-approved breakthrough therapy for TRD",
    "typical_us_cost_range": "$2,000 - $3,000",
    "indications": ["Treatment-resistant depression", "Major depression"],
    "sources": ["FDA", "MAPS", "Clinical trials"]
  },
  ...
]
```

### Search Procedures

```bash
curl "https://medfreedom-api.onrender.com/api/procedures?search=psilocybin"
```

### Filter by Modality

```bash
curl "https://medfreedom-api.onrender.com/api/procedures?modality=CELL_THERAPY"
```

### Create Procedure

```bash
curl -X POST https://medfreedom-api.onrender.com/api/procedures \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New Therapy",
    "modality": "GENE_THERAPY",
    "regulatory_modality": "GENE_THERAPY",
    "restriction_driver": "NONE",
    "subcategory": "Advanced Gene Therapy",
    "therapeutic_areas": ["Oncology"],
    "description": "Description here",
    "typical_us_cost_range": "$50,000 - $100,000",
    "indications": ["Cancer", "Genetic disorder"],
    "sources": ["Clinical data"]
  }'
```

---

## Access Records

### List All Access Records

```bash
curl https://medfreedom-api.onrender.com/api/access-records
```

**Response** (200 OK):
```json
[
  {
    "id": "ar_001",
    "procedure_id": "psilocybin_trd",
    "jurisdiction_id": "oregon",
    "legal_status": "FULLY_APPROVED",
    "access_pathway": "LICENSED_PROVIDER_REGIME",
    "price_usd": 2500,
    "price_confidence": "HIGH",
    "total_access_cost_usd": 2650,
    "travel_friction_json": {"visa": "none", "min_stay_days": 1, "language": "English"},
    "oversight_quality": "REGULATED_HIGH",
    "confidence": "HIGH",
    "volatility": "STABLE",
    "verified_by": "MAPS",
    "last_verified": "2026-07-15",
    "arbitrage_summary": "Oregon psilocybin is the gold standard treatment",
    "known_risk_flags": [],
    "sources": ["MAPS"]
  },
  ...
]
```

### Filter Access Records by Procedure

```bash
curl "https://medfreedom-api.onrender.com/api/access-records?procedure_id=psilocybin_trd"
```

### Filter Access Records by Jurisdiction

```bash
curl "https://medfreedom-api.onrender.com/api/access-records?jurisdiction_id=oregon"
```

### Query with Advanced Filters

```bash
curl -X POST https://medfreedom-api.onrender.com/api/access-records/query \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active",
    "legal_status": ["FULLY_APPROVED", "RIGHT_TO_TRY"],
    "oversight_quality": ["REGULATED_HIGH", "REGULATED_MODERATE"],
    "search": "psilocybin"
  }'
```

### Create Access Record

```bash
curl -X POST https://medfreedom-api.onrender.com/api/access-records \
  -H "Content-Type: application/json" \
  -d '{
    "procedure_id": "psilocybin_trd",
    "jurisdiction_id": "oregon",
    "legal_status": "FULLY_APPROVED",
    "access_pathway": "LICENSED_PROVIDER_REGIME",
    "price_usd": 2500,
    "price_confidence": "HIGH",
    "total_access_cost_usd": 2650,
    "travel_friction_json": {"visa": "none", "min_stay_days": 1},
    "oversight_quality": "REGULATED_HIGH",
    "confidence": "HIGH",
    "volatility": "STABLE",
    "verified_by": "MAPS",
    "last_verified": "2026-07-16",
    "sources": ["MAPS", "Clinical data"]
  }'
```

---

## Search & Discovery

### Unified Search

```bash
curl "https://medfreedom-api.onrender.com/api/search?q=psilocybin"
```

**Response** (200 OK):
```json
{
  "procedures": [
    {
      "id": "psilocybin_trd",
      "name": "Psilocybin for Treatment-Resistant Depression",
      ...
    }
  ],
  "jurisdictions": [
    {
      "id": "oregon",
      "name": "Oregon",
      ...
    }
  ],
  "access_records": [
    {
      "id": "ar_001",
      "procedure_name": "Psilocybin for Treatment-Resistant Depression",
      "jurisdiction_name": "Oregon",
      ...
    }
  ]
}
```

### Get Procedure Availability by Jurisdiction

```bash
curl "https://medfreedom-api.onrender.com/api/procedures/{procedure_id}/jurisdictions"
```

**Example**:
```bash
curl "https://medfreedom-api.onrender.com/api/procedures/psilocybin_trd/jurisdictions"
```

---

## Export Data

### Export All Data as JSON

```bash
curl https://medfreedom-api.onrender.com/api/export/json > export.json
```

### Export Access Records as CSV

```bash
curl https://medfreedom-api.onrender.com/api/export/csv > export.csv
```

**CSV Columns**:
- Procedure
- Jurisdiction
- Legal Status
- Oversight Quality
- Cost Range (USD)
- Access Pathway
- Eligibility
- Provider Requirements
- Residency/Travel Notes
- Risk Notes
- Last Verified
- Arbitrage Summary

---

## Filter Options

Get all available filter values for UI construction:

```bash
curl https://medfreedom-api.onrender.com/api/filters/options
```

**Response**:
```json
{
  "modalities": ["CELL_THERAPY", "GENE_THERAPY", ...],
  "therapeutic_areas": ["Mental Health", "Oncology", ...],
  "legal_statuses": ["Fully_Approved", "Right_To_Try", "Prohibited", ...],
  "oversight_qualities": ["High", "Medium", "Low", "Variable"],
  "jurisdictions": [
    {"id": "us_federal", "name": "United States (Federal)", "type": "SOVEREIGN"},
    ...
  ]
}
```

---

## Data Types & Enums

### JurisdictionLevel

- `SUPRANATIONAL` - International/multinational
- `SOVEREIGN` - Country-level
- `SUBNATIONAL` - State/province level
- `SPECIAL_ZONE` - Special economic zones (e.g., Próspera)
- `MUNICIPAL` - City/local level

### RegulatoryModality (Procedure Type)

- `SMALL_MOLECULE_APPROVED` - FDA-approved drug
- `SMALL_MOLECULE_INVESTIGATIONAL` - Research stage
- `BIOLOGICAL_APPROVED` - Approved biotech therapy
- `CELL_THERAPY_AUTOLOGOUS` - Patient's own cells
- `CELL_THERAPY_ALLOGENEIC` - Donor cells
- `GENE_THERAPY` - Gene-level modification
- `PSYCHEDELIC_THERAPY` - Psilocybin, LSD, etc.
- `REPRODUCTIVE` - Surrogacy, IVF variants
- `END_OF_LIFE` - Assisted dying, euthanasia
- ... (14 total)

### RestrictionDriver (Why Restricted)

- `SAFETY_UNPROVEN` - Not enough safety data
- `CONTROLLED_SUBSTANCE` - DEA/similar scheduling
- `ETHICS_CONTESTED` - Ethical concerns (embryos, etc.)
- `COST_OR_LICENSING` - Economic barriers
- `IMPORT_BARRIER` - International trade/customs
- `NONE` - No restriction

### LegalStatus

- `APPROVED_ON_LABEL` - Approved for this indication
- `APPROVED_OFF_LABEL` - Approved for different use
- `CLINICAL_TRIAL_ONLY` - Available only in trials
- `RIGHT_TO_TRY` - RTT pathway available
- `DECRIMINALIZED` - Not legal but not prosecuted
- `PROHIBITED` - Illegal
- ... (10 total)

### AccessPathway

- `STANDARD_PRESCRIPTION` - Regular doctor prescription
- `OFF_LABEL_PRESCRIPTION` - Doctor can prescribe off-label
- `LICENSED_PROVIDER_REGIME` - Approved clinics/practitioners
- `RIGHT_TO_TRY` - Compassionate use pathway
- `CLINICAL_TRIAL` - Research study enrollment
- ... (10 total)

### Confidence (Data Quality)

- `HIGH` - Multiple verified sources, recent
- `MODERATE` - Some sources, reasonably current
- `LOW` - Single source or outdated info

### Volatility (Legal Stability)

- `STABLE` - Unlikely to change in next 12 months
- `PENDING_LEGISLATION` - New laws coming soon
- `ACTIVE_FLUX` - Rapidly changing legal landscape

### OversightQuality

- `REGULATED_HIGH` - Government oversight, strict standards
- `REGULATED_MODERATE` - Some government oversight
- `SELF_REGULATED` - Industry self-policing
- `MINIMAL` - Very limited oversight
- `NONE` - No regulatory oversight

---

## Bulk Import

```bash
curl -X POST https://medfreedom-api.onrender.com/api/bulk-import \
  -H "Content-Type: application/json" \
  -d '{
    "jurisdictions": [
      {"id": "j1", "name": "New Jurisdiction", "type": "SUBNATIONAL", ...}
    ],
    "procedures": [
      {"id": "p1", "name": "New Procedure", "modality": "CELL_THERAPY", ...}
    ],
    "access_records": [
      {"id": "ar1", "procedure_id": "p1", "jurisdiction_id": "j1", ...}
    ]
  }'
```

**Response**:
```json
{
  "ok": true,
  "created": {
    "jurisdictions": 1,
    "procedures": 1,
    "access_records": 1
  }
}
```

---

## Error Responses

### 404 Not Found

```json
{
  "detail": "Jurisdiction not found"
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 500 Server Error

Check Render logs for details. Common causes:
- Database connection lost
- Missing environment variables
- Service cold-start (wait 10 seconds and retry)

---

## Rate Limiting & Quotas

**Free Tier Limits** (Render):
- 512 MB RAM shared with database
- CPU: Shared single core
- No explicit rate limits, but:
  - Avoid >10 requests/second
  - Long queries may timeout
  - Service sleeps after 15 min inactivity (first request ~10s cold start)

---

## Example Workflows

### Find Treatment Options for a Condition

```bash
# 1. Search for procedures treating "depression"
curl "https://medfreedom-api.onrender.com/api/search?q=depression"

# 2. Get all jurisdictions where psilocybin is available
curl "https://medfreedom-api.onrender.com/api/procedures/psilocybin_trd/jurisdictions"

# 3. Filter by affordable options (<$5000)
# Parse response and filter by price_usd
```

### Compare Treatment Costs by Jurisdiction

```bash
curl -X POST https://medfreedom-api.onrender.com/api/access-records/query \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active",
    "procedure_id": "psilocybin_trd",
    "legal_status": ["FULLY_APPROVED", "RIGHT_TO_TRY"]
  }' | jq '.[] | {jurisdiction_name, price_usd, total_access_cost_usd}' | sort
```

### Export for Analysis

```bash
# Get JSON for programmatic analysis
curl https://medfreedom-api.onrender.com/api/export/json > data.json

# Get CSV for spreadsheet analysis
curl https://medfreedom-api.onrender.com/api/export/csv > data.csv
```

---

## Documentation Files

For more details, see:
- **SCHEMA_APPLICATION_SUMMARY.md** - Technical schema details
- **RENDER_DEPLOYMENT_GUIDE.md** - Deployment instructions
- **DEPLOYMENT_CHECKLIST.md** - Pre/post deployment steps
- **FINAL_SCHEMA_SUMMARY.txt** - Architecture overview

---

**API Status**: ✅ Live on Render  
**Last Updated**: 2026-07-16  
**Support**: Check Render dashboard logs for issues
