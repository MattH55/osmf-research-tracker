# Coding-Agent Task Brief — Fill the MedFreedom data gaps

This brief is written for an autonomous coding agent working in this repo. It covers the
three known data gaps plus how to extend the new Gene Therapy Mapper. **Do not fabricate
clinical, legal, or pricing facts** — every value must be traceable to a cited public
source. When a fact cannot be sourced, leave the field null and record why.

## Repo orientation

- Backend app: `med-freedom-map/backend/app/`
- Models / schema: `app/models.py` (enums + `Jurisdiction`, `Procedure`, `AccessRecord`,
  `Condition`, `ProcedureIndication`)
- Seed data is split across modules, merged in `app/seed.py`:
  - `seed_enrichment.py` — base conditions, indications, disease maps, access enrichments
  - `seed_therapies_expansion.py` — extra procedures/conditions/indications
  - `seed_evidence_clinics.py` — evidence grades, indication fills, example clinics
  - `seed_practitioner_setup.py`, `seed_prohibitions.py`, `seed_regulation_links.py`,
    `seed_regulatory_inference.py` — setup, prohibitions, regulation links, inference
- Reference dataset (not DB): `app/gene_therapy_data.py`
- Read model of an access row is `AccessRecord.to_dict()`; API returns dicts.

### How to run / verify locally (Windows, Git Bash)
```bash
cd med-freedom-map/backend
python -m py_compile app/*.py                          # syntax
DATABASE_URL="sqlite:///./verify.db" PYTHONIOENCODING=utf-8 python -c "
import os; os.environ['DATABASE_URL']='sqlite:///./verify.db'
from app.seed import seed_database; print(seed_database())"
# then exercise endpoints with fastapi.testclient.TestClient(app)
rm -f verify.db verify.db-*
```
Deployed reseed (no shell on Render free tier): `POST /api/seed?reset=true`.

---

## GAP 1 — Evidence grades (schema §5)

**Field:** `ProcedureIndication.evidence_grade` (enum `EvidenceGrade` E1–E8) +
`evidence_summary` (text). Evidence lives on the **procedure×condition** pair, never on
the access record (same evidence applies in every market).

**Grade rubric (already in `models.py`):** E1 multi-RCT consistent · E2 one strong RCT ·
E3 small/conflicting RCTs · E4 uncontrolled trials · E5 case series · E6 animal · E7 in
vitro · E8 none.

**Task:**
1. Enumerate every `(procedure, condition)` pair that should exist. Source disease↔therapy
   links from `ALL_PROCEDURE_DISEASES` in `seed.py` and the `CONDITIONS*` lists.
2. Find pairs with **no** `ProcedureIndication` row, or a placeholder grade.
   ```python
   # count coverage
   from app.models import Procedure, ProcedureIndication
   # pairs missing = expected disease links minus existing indications
   ```
3. For each missing/weak pair, assign a grade + one-sentence `evidence_summary` **with a
   citation** (PubMed/DOI/registry). Add rows to `PROCEDURE_INDICATIONS_EXPANSION` in
   `seed_therapies_expansion.py` (or a new `seed_evidence_fill.py` merged in `seed.py`).
4. Prefer the most recent systematic review/meta-analysis for the grade call.

**Acceptance:** `/api/stats` `procedure_indications` ≥ number of documented disease links;
no procedure with diseases has zero graded indications; every new row has a non-empty
`evidence_summary` containing a source.

---

## GAP 2 — Pricing & confidence (schema §3)

**Fields on `AccessRecord`:** `price_usd` (float), `price_local`, `price_basis`
(`cash_pay|insured|trial_free`), `price_confidence` (`Quoted|Estimated|Unknown`),
`estimated_cost_range_usd` (text), `total_access_cost_usd` (float, **derived** =
procedure price + travel + accommodation), `confidence` (`High|Moderate|Low` — data
quality, not clinical), `volatility` (`Stable|Pending_Legislation|Active_Flux`).

**Current state:** only a minority of access rows have `price_usd`; most default to
`confidence=Low`, `volatility=Active_Flux`. See `/api/stats.access_records_with_price`.

**Task:**
1. For each active `AccessRecord`, source a real cash-pay price (clinic quotes, published
   tariffs, medical-tourism aggregators, peer-reviewed cost studies).
2. Set `price_usd` + `price_basis` + `price_confidence` (`Quoted` only with a real quote;
   else `Estimated`; else leave null + `Unknown`).
3. Compute `total_access_cost_usd` using the existing helpers in
   `populate_schema_fields.py` (`TRAVEL_COSTS`, `MIN_STAY_DAYS`, `parse_cost_range`,
   `build_schema_fields`) — reuse them; do not re-invent.
4. Set `confidence` from source quality and `volatility` from legal stability.
5. Put enrichments in `seed_enrichment.ACCESS_ENRICHMENTS` (applied via
   `apply_access_enrichment`) keyed by `(procedure_id, jurisdiction_id)`.

**Do not** invent prices. A missing price with `price_confidence=Unknown` is correct;
a fabricated number is a defect.

**Acceptance:** `access_records_with_price` rises materially; every priced row has a
`price_confidence` and at least one source in `sources`; `total_access_cost_usd` is
consistent with `price_usd` + travel for that jurisdiction.

---

## GAP 3 — Access pathway (schema §4, the "legal ≠ how you get it" axis)

**Field:** `AccessRecord.access_pathway` (enum `AccessPathway`:
`Standard_Prescription, Off_Label_Prescription, Compounding, Expanded_Access,
Right_To_Try, Clinical_Trial_Enrollment, Personal_Import, Licensed_Provider_Regime,
Medical_Tourism_Cash, None`). Distinct from `legal_status`.

**Task:**
1. For each active `AccessRecord`, set `access_pathway` to the *practical* route a patient
   actually uses in that jurisdiction (e.g. Oregon psilocybin = `Licensed_Provider_Regime`;
   US ketamine off-label = `Off_Label_Prescription`; Mexico stem cells =
   `Medical_Tourism_Cash`; unapproved-but-trial = `Clinical_Trial_Enrollment`).
2. Where the pathway can be inferred from `legal_status` + jurisdiction, encode the mapping
   in `seed_regulatory_inference.py`; encode genuine exceptions explicitly in
   `ACCESS_ENRICHMENTS`.

**Acceptance:** `/api/stats.access_records_with_pathway` ≈ total active access records;
spot-check 10 rows for a defensible legal_status↔access_pathway pairing.

---

## GAP 4 (optional) — Extend the Gene Therapy Mapper

Data module: `app/gene_therapy_data.py`; served at `/api/gene-therapies`. To add a disease,
append a dict to `GENE_THERAPIES` following the documented shape (disease, gene,
inheritance, omim, mechanism, biomarker, genetic_test, burden{incidence, us_patients,
global_patients, notes}, approved_therapies[], sources[]). `trials_url` auto-generates a
live ClinicalTrials.gov search — do not hand-copy NCT numbers. Burden = clearly-labeled
rough estimate. Good additions: Wiskott-Aldrich (WAS), X-linked SCID (IL2RG),
beta-thalassemia subtypes, Fanconi anemia, Pompe (GAA), MPS types (Hurler/Hunter),
Choroideremia (CHM), Retinitis pigmentosa (RPGR/PDE6), Danon (LAMP2), Friedreich ataxia
(FXN), Huntington (HTT — investigational ASO/AAV).

**Acceptance:** `/api/gene-therapies` count increases; each entry has ≥1 source; approved
entries have list price + first-approval year; investigational entries carry a
`pipeline_note`.

---

## Global rules
- Idempotent seeding: all data goes through the seed modules; never write one-off scripts
  that mutate prod directly. Re-running `seed_database()` must be safe.
- Every clinical/legal/price value carries a source. No source → null + note.
- After changes: `python -m py_compile app/*.py`, run the local seed, exercise endpoints
  with TestClient, then deploy and `POST /api/seed?reset=true`.
- Keep entries neutral and factual; this is informational data, not advice.
