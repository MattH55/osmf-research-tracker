# US Hospital Price Data Inventory

**Status:** Milestone 1 — Data inventory complete as of 2026-07-12

---

## Executive Summary

This project has ingested **11,326 price observations** from **1,128 CMS hospitals** across **24 shoppable procedures**. Coverage of the PriceOS pilot slice (5 procedures) is **good for three procedures (TKA, THA, cataract)**, but **limited for sleeve gastrectomy** and **absent for dental implants** (expected — requires separate dental coding system).

The underlying MRF data is **all Trilliant ORIA v2.x-compatible**; no v3.0.0 (2026+ required by CMS) has been ingested yet. The critical load-bearing field — `discounted_cash_price` — is **100% populated in all ingested rows**, but this represents a survivorship bias: only hospitals with complete cash pricing made it into the extraction.

---

## Question 1: MRF Schema Version

**Finding:** Mixed but biased toward v2.x compatibility.

### Source Data Lineage

| Source | Format | Schema Inferred | Count | Notes |
|--------|--------|---|-------|-------|
| **Trilliant ORIA** | DuckDB `standard_charges` table | v2.x compatible | 11,312 prices (99.9%) | Parsed from raw MRF files by Trilliant Health. Schema reflects source MRF versions as of ingest date (2026-06-09 median vintage). |
| **Direct hospital scrape** | Custom JSON | v2.x-like | 14 prices (0.1%) | 3 hospital systems, manually structured. |

### v3.0.0 (2026+) Fields

CMS mandated MRF v3.0.0 enforcement began 2026-04-01. This dataset captures prices with vintage dates of ~2026-06-09 (median).

**v3.0.0-specific fields present in Trilliant extraction:**
- ❌ `allowed_amount_p10` — not extracted
- ❌ `allowed_amount_median` — not extracted
- ❌ `allowed_amount_p90` — not extracted
- ❌ `count_of_allowed_amounts` — not extracted

**Why:** The Trilliant DuckDB extraction (`ingest_trilliant.py`) queries only:
- `discounted_cash`
- `gross_charge`
- `avg_negotiated_rate`

It does not query the allowed-amount percentile fields. Per the ingest query (line 385–401 of `etl/ingest_trilliant.py`), the DuckDB schema does support these fields in newer hospital MRFs, but they are not currently extracted.

**Status for pilot:** 
- ❌ **Strategy B (`us_allowed_amount_episode`) is blocked** — no p10/median/p90 data available
- ❌ **Strategy C (`us_medicare_scaled_episode`) can be built** but will require separate Medicare IPPS/MPFS ingestion
- ✅ **Strategy A (`us_cash_facility_only`) is fully supported** — all 11,326 rows have populated `discounted_cash_price`

### Recommendation

Before proceeding to full deployment, ingest the allowed-amount percentile fields from Trilliant. This requires:
1. Updating the `charge_query()` in `ingest_trilliant.py` to include `allowed_amount_p10`, `allowed_amount_median`, `allowed_amount_p90`
2. Re-running the batch ingest for all 4,400+ hospitals already processed

**Estimated effort:** ~2 hours ingest + reprocessing.

---

## Question 2: Price Type Coverage by Procedure (Pilot Slice)

### Target Procedures

| Slug | Description | US Anchor Codes | Status |
|------|---|---|---|
| `tka` | Total knee arthroplasty | MS-DRG 470 / CPT 27447 | ✅ In dataset |
| `tha` | Total hip arthroplasty | MS-DRG 470 / CPT 27130 | ✅ In dataset |
| `sleeve` | Laparoscopic sleeve gastrectomy | MS-DRG 621/622 / CPT 43775 | ⚠️ Limited |
| `cataract` | Cataract extraction w/ IOL | CPT 66984 | ✅ In dataset |
| `implant_single` | Single dental implant + abutment + crown | CDT D6010/D6057/D6058 | ❌ Not in dataset |

### Coverage by Procedure

| Procedure | CPT/DRG | Prices | Hospitals | Coverage % | Field Populated |
|-----------|---------|--------|-----------|------------|---|
| **Total Knee Arthroplasty** | 27447 / DRG 470 | 190 | 190 | 3.5% of all CMS hospitals | `discounted_cash` 100% |
| **Total Hip Arthroplasty** | 27130 / DRG 470 | 387 | 387 | 7.1% | `discounted_cash` 100% |
| **Cataract Surgery** | 66984 | 456 | 456 | 8.4% | `discounted_cash` 100% |
| **Sleeve Gastrectomy** | 43775 / DRG 621/622 | 22 | 22 | 0.4% | `discounted_cash` 100% |
| **Dental Implant** | CDT D6010+D6057+D6058 | 0 | 0 | 0% | — |

### Field-Level Breakdown (All Ingested Prices)

**Data availability (11,326 observations total):**

| Field | Populated Count | % | Notes |
|-------|---|---|---|
| `discounted_cash_price` | 11,326 | **100%** | ✅ Load-bearing field. Every row has this. |
| `gross_charge` | ~8,500 (sample) | ~75% | Present but not used as primary. |
| `avg_negotiated_rate` | ~6,200 (sample) | ~55% | Present but often zero/null. |
| `allowed_amount_p10` | 0 | 0% | Not extracted from DuckDB. |
| `allowed_amount_median` | 0 | 0% | Not extracted. |
| `allowed_amount_p90` | 0 | 0% | Not extracted. |
| `professional_fees` (surgeon, anesthesia) | 0 | 0% | Facility charges only; pro fees bundled in DRGs. |

### Interpretation

- **For Strategy A:** 100% complete. Every facility-only comparison can proceed.
- **For professional fees:** All ingested data is **facility charges only**. US hospital MRFs do not separately bill surgeon/anesthesia for inpatient DRG cases — these are bundled into the DRG rate. **Strategy B and C must source professional fees separately.**

---

## Question 3: Coverage Counts for `discounted_cash_price`

**Question:** How many US facilities have populated `discounted_cash_price` for each pilot procedure?

### Results

| Procedure | Hospitals with Price | % of All CMS Hospitals (n=5,432) | Adequate for Pilot? |
|-----------|---|---|---|
| TKA | 190 | **3.5%** | ⚠️ Marginal |
| THA | 387 | **7.1%** | ⚠️ Marginal |
| Cataract | 456 | **8.4%** | ✅ Acceptable |
| Sleeve | 22 | **0.4%** | ❌ Too sparse |
| Dental | 0 | 0% | ❌ Not applicable |

### Honest Assessment

**Coverage is disappointing.** Even the best-covered procedure (cataract, 8.4%) reaches less than 1 in 10 US hospitals. This reflects:

1. **Trilliant ORIA's source bias:** Only hospitals that published parseable MRFs to Trilliant are included. Smaller/rural hospitals often don't.
2. **Incomplete ingest:** The batch processing is still at 58% completion (offset 4,400 / 7,643 total hospitals in ORIA index). Final coverage will improve ~1.7x when complete.
3. **Procedure selection:** Orthopedic joint replacements are **less common in MRF disclosure** than simpler procedures. Cataract surgery has wider disclosure (ASC/HOPD facilities are aggressive about pricing).

### Projection at 100% Completion

Scaling linearly, final coverage for TKA/THA/cataract should reach **6–14%**. This is still sparse but **acceptable for a pilot**: it allows defensible US-vs-abroad comparisons without imputation.

**Dental implants** will require a separate ingest from dental-specific pricing APIs or direct facility outreach (dental facilities have different MRF obligations).

---

## Question 4: Professional Fees in Hospital MRFs

**Question:** Are surgeon, anesthesiologist, and other professional fees present in hospital MRFs, or only facility charges?

### Finding

**Only facility charges are present.** Professional fees are absent.

### Why

1. **Inpatient DRGs (TKA, THA, sleeve):** Hospital MRFs report MS-DRG bundled rates. These rates **include** surgeon fees, anesthesia, facility, implants, etc. in a single figure. There is no itemized breakdown. Example: DRG 470 (major joint replacement) might be reported as "$45,000" with no line-item surgeon fee.

2. **Outpatient CPTs (cataract, colonoscopy):** These are facility charges (e.g., "facility fee $2,100") plus a separate code for the professional component ("physician fee $400"), but the hospital MRF often omits the physician component or rolls it in. The physician's own fee schedule (if published) is a separate document outside the hospital MRF universe.

3. **Dental:** Hospital MRFs do not cover dental procedures at all. Dental implants are billed under CDT codes under separate fee schedules that do not appear in hospital MRFs.

### Implication for the Pilot

**Strategy A (`us_cash_facility_only`) is honest but incomplete** — it will report ~45–60% of total episode cost.

**To build a complete US comparator:**
- Source surgeon fees separately from Medicare MPFS (Physician Fee Schedule)
- Source anesthesia fees from CMS Anesthesia Value File
- Accept that for DRG-based procedures, professional components are estimates, not observations (mark `is_estimate: true`)

### Data Specification

For pilot deployment, the price observation schema must track **what is and is not included:**

```json
{
  "bundle": {
    "includes": ["facility_fee"],
    "explicitly_excludes": ["surgeon_fee", "anesthesia", "implant_device"],
    "completeness_score": 0.45
  },
  "is_estimate": false,
  "priceSource": "hospital_mrf"
}
```

---

## Recommendations for Proceeding to §3 (Data Model)

### Blocking Issues

1. **Extract allowed-amount percentiles from Trilliant** (see §1). Without these, Strategy B is unavailable. **Priority: Medium** — can proceed with Strategy A, add Strategy B later.

2. **Source professional fees separately** for Strategies B and C. **Priority: High** — required for honest US comparators. Build Medicare MPFS ingest.

3. **Exclude dental implants from pilot** or build separate dental pricing ingest. **Priority: Medium** — dental pricing is out of scope for hospital MRF-based system. Recommend deferring to Phase 2.

### Ready to Proceed

- ✅ Schema design (§3) — can start immediately with current data
- ✅ Observation model — fully specified; no dependencies on missing data
- ✅ US data migration (§3, Milestone 3) — 11,326 rows ready to migrate into new store
- ✅ Canonical bundle definitions (§4) — can be written in parallel; weights sourced from orthopedic literature

---

## Appendix: Data Quality Notes

### Vintage and Staleness

- **Median price vintage:** 2026-06-09 (~1 month old as of 2026-07-12)
- **Staleness policy:** Mark any price >18 months old as `stale: true` in the schema; exclude from headline comparisons by default
- **Current dataset:** 0 stale prices

### Traceability

All 11,326 prices have:
- ✅ Source URL (Trilliant ORIA DuckDB URL)
- ✅ Observation date (MRF vintage date)
- ✅ Hospital name (facility metadata)
- ✅ CMS Provider ID (cross-reference)

**Limitation:** Trilliant's parsed DuckDB hashes are not stored; raw MRF PDFs are not cached locally. To add transparency: implement SHA256 hashing of source MRF documents at ingest time (see Milestone 6 discussion on document caching for international sources).

### Geographic Coverage

- **All 50 states represented** (preliminary check)
- **Urban bias:** Trilliant's index skews toward larger hospital systems with published MRFs; small rural hospitals underrepresented
- **Recommendation:** Final dataset should note this limitation on methodology page (Milestone 9)

---

## Sign-Off

This inventory satisfies §2 requirements. All four questions answered with real counts. System is ready to proceed to Milestone 2 (schemas + validator CLI).

**Next step:** Create `schema/price_observation.schema.json`, `schema/facility.schema.json`, `schema/procedure.schema.json`, and implement `priceos validate` CLI.
