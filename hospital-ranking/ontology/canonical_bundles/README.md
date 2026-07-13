# Canonical Bundles

Complete episode-of-care definitions for pilot procedures. Each bundle defines:

1. **Components** — Every cost element a patient pays for (itemized)
2. **Weights** — Proportion of total episode cost (must sum to 1.0)
3. **US codes** — CPT/DRG mappings
4. **Citations** — Sources for weights (published literature, surveys)

These bundles are the mechanism that enforces honest price comparisons: they force you to declare what is and isn't included before comparing a US price to an international price.

---

## Files

| File | Procedure | CPT/CDT | Status |
|------|-----------|---------|--------|
| `tka.yaml` | Total knee arthroplasty | CPT 27447 / DRG 469-470 | ✅ Complete |
| `tha.yaml` | Total hip arthroplasty | CPT 27130 / DRG 469-470 | ✅ Complete |
| `sleeve.yaml` | Laparoscopic sleeve gastrectomy | CPT 43775 / DRG 621-622 | ✅ Complete |
| `cataract.yaml` | Cataract extraction + IOL | CPT 66984 | ✅ Complete |
| `implant_single.yaml` | Single dental implant | CDT D6010/D6057/D6058 | ✅ Complete |

---

## How Bundles Drive Comparisons

### Example: US vs. Mexico for TKA

**US hospital MRF reports:** $18,000 (facility-only)  
**Completeness:** 45% (missing surgeon + anesthesia)

**Mexico facility quotes:** $12,000 (all-inclusive package)  
**Declared bundle:** facility + surgeon + anesthesia + implant + PT  
**Completeness:** 85%

**Comparison result:** `NOT_COMPARABLE`  
**Reason:** Completeness scores differ by >15% (45% vs 85%)  
**Savings claim:** BLOCKED

This is the feature. A lead-gen site divides $12,000 by $18,000, prints "33% savings," and gets sued. We report `NOT_COMPARABLE` and show WHY.

---

## Component Weights

Weights are **normalized to 1.0** per bundle. They represent the typical cost share of each component:

```
TKA:
  surgeon_fee:      0.20  (20% of total)
  facility_fee:     0.45  (45% of total)
  anesthesia:       0.08  (8% of total)
  implant:          0.15  (15% of total)
  pre_op_workup:    0.03  (3% of total)
  post_op_physio:   0.04  (4% of total)
  inpatient_nights: 0.05  (5% of total)
                    ----
                    1.00  ✓
```

### Completeness Score = Σ weight(c) for c in observed.bundle.includes

If a price observation includes ["facility_fee", "implant"] but NOT ["surgeon_fee", "anesthesia"]:

```
completeness = 0.45 + 0.15 = 0.60
```

The price observation carries this score; the comparison engine uses it to gate comparisons.

---

## Using Bundles in the Comparison Engine

1. **Load canonical bundle** for procedure (e.g., `tka.yaml`)
2. **Extract components** from US MRF price observation (e.g., only "facility_fee")
3. **Compute completeness_score** = sum of weights for included components
4. **Extract components** from international quote (e.g., all 7 components)
5. **Compute completeness_score** for international = 1.0
6. **Compare scores:**
   - If |US_score - INTL_score| > 0.15 → `NOT_COMPARABLE`, do not compute savings
   - Else → proceed to compute savings range (intl_low/intl_high vs us_low/us_high)

---

## Adding New Procedures

When expanding beyond the pilot 5:

1. Create `ontology/canonical_bundles/{slug}.yaml`
2. Define components with realistic weights (sourced from literature)
3. Cite all weights with academic/survey sources (not guesses)
4. Test with sample prices: does the completeness score block inappropriate comparisons?
5. Update `schema/procedure.schema.json` to add procedure if new
6. Commit with citation review

---

## Notes on Specific Procedures

### Dental Implants (`implant_single.yaml`)

This procedure is intentionally included to expose the limits of a CPT-centric system:

- Uses **CDT codes** (dental), not CPT
- Never appears in hospital MRFs
- Performed in private dental offices, not hospitals
- Insurance almost never covers (patient pays 100% out-of-pocket)

This is why medical tourism for dental is so price-sensitive: US patients pay full freight ($4,000–$6,000 per implant), while Mexico/Costa Rica packages are $1,500–$3,500. Direct international comparison is valid here because US patients actually DO pursue medical tourism for dental.

### Orthopedic Bundles (TKA, THA)

These are hospital inpatient DRG-bundled procedures in the US, which means:

- **Facility cost is bundled** with surgeon + anesthesia in the DRG rate
- Hospital MRFs report only the DRG bundled figure (no itemization)
- Surgeon's own fee schedule (if published) is separate
- International packages ALWAYS itemize all components

This asymmetry is the core reason most US vs. abroad comparisons are wrong.

### Bariatric (`sleeve.yaml`)

Sleeve gastrectomy is uniquely problematic internationally:

- High variance in what "included" means (vitamins? 1-year supply? For life?)
- Common complications (leak, stricture) with no standard pricing
- Weight loss "guarantee" clauses vary wildly
- International quotes are often aspirational ("typical $4,500") not contracted

The bundle makes this explicit: the international price you see is likely facility + surgeon + basic nutritional support for 3 months, but the completeness score flags that year-2+ vitamin cost and complication risk are not included.

### Cataract (`cataract.yaml`)

Cataract is the "cleanest" procedure for comparison:

- Outpatient (no bed cost)
- CPT code 66984 is unambiguous
- IOL type is explicitly variable (monofocal vs. premium)
- Comparisons must specify IOL type (comparing "basic" US to "premium" intl is misleading)

---

## Version Control & Updates

Bundles are committed to git. If literature changes weight guidance:

1. Update the YAML
2. Add a note in `notes` field explaining what changed
3. Commit with citation of new study
4. Re-run validator on all observations to see how completeness scores shift
5. Update methodology page to reflect new understanding

Bundles should be stable (not changing week-to-week) but defensible (backed by citable sources).

---

## Methodology Page Integration

The public methodology page (Milestone 9) will include:

1. Each bundle definition (component table + weights)
2. Citation for each weight
3. Worked example: US price with component breakdown → completeness score
4. Worked example: international price with component breakdown → completeness score
5. Comparison result: scores differ → NOT_COMPARABLE
6. Savings calculation (for cases that pass the completeness gate)

This is the artifact that allows a hostile reader to reproduce every number on the site.
