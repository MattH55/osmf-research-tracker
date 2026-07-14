---
slug: teriparatide
names:
  inn: "Teriparatide"
  common: ["Teriparatide", "PTH (1-34)", "rhPTH(1-34)"]
  codes: ["LY333334"]
  cas: "103213-15-2"
sequence: null
class_by_jurisdiction:
  US: "A"
  EU: "A"
  UK: "A"
  CA: "A"
  AU: "A"

evidence:
  - indication: "Osteoporosis (postmenopausal women, men with low bone mass)"
    tier: "E1"
    human_rcts: 5
    human_trials_any: 8
    registered_trials_total: 12
    registered_trials_reported: 11
    key_citations:
      - "10.1056/NEJMoa003541"
      - "10.1056/NEJMoa021812"
    summary: "Multiple Phase 3 RCTs (N>1500 total) demonstrate 3–4% increase in bone mineral density at spine and hip vs. placebo, with 65% reduction in vertebral fractures (p<0.001) and 53% reduction in non-vertebral fractures. FDA approved 2002."
    last_reviewed: "2026-07-12"
    reviewer: "OSMF Medical Review"

safety:
  grade: "S2"
  known_signals:
    - signal: "Hypercalcemia (dose-dependent, transient)"
      evidence: "Mild hypercalcemia (10-11 mg/dL) in ~5% of patients within 4 hours of injection. Resolves by 24–48 hours. Increases urinary calcium."
      citation: "10.1056/NEJMoa003541"
    - signal: "Osteosarcoma (rodent models, black box warning)"
      evidence: "Dose-dependent osteosarcoma in rats (20–60 mg/kg); not in dogs or primates. Black box warning; mechanism unknown. No cases in human trials (max 2 years)."
      citation: "FDA Label: Forteo (teriparatide) injection [prescribing information]"
    - signal: "Gout / hyperuricemia (elevated uric acid)"
      evidence: "Uric acid elevation in ~3% of patients. Gout exacerbation reported but rare (<1%)."
      citation: "FDA MedWatch reports"
  no_data_statement: false

regulatory:
  - jurisdiction: "US"
    status: "approved"
    detail: "FDA approved: Forteo (osteoporosis, 2002). Maximum 2 years cumulative lifetime use (due to osteosarcoma black box warning in rodents)."
    source_url: "https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book"
    source_retrieved: "2026-07-12"
    archive_url: "https://web.archive.org/web/20260712*/fda.gov/drugs/drug-approvals-and-databases/orange-book"
    source_quote_ref: "Orange Book, active ingredient 'teriparatide'"

  - jurisdiction: "EU"
    status: "approved"
    detail: "EMA approved: Forsteo (osteoporosis, 2003). Same 2-year cumulative use restriction."
    source_url: "https://www.ema.europa.eu/en/medicines/human/EPAR/forsteo"
    source_retrieved: "2026-07-12"
    archive_url: "https://web.archive.org/web/20260712*/ema.europa.eu/en/medicines/human/EPAR/forsteo"
    source_quote_ref: "EMA product information"

sport:
  wada_status: "prohibited"
  wada_class: "S2"
  source_url: "https://www.wada-ama.org/en/prohibited-list"

unknowns:
  - "Long-term safety beyond 2 years cumulative use (clinical trials max 2 years; lifetime safety unknown)"
  - "Osteosarcoma risk in humans (only observed in rodents; mechanism in humans unknown; no cases in trials)"
  - "Optimal duration of therapy (current 2-year limit is regulatory/precaution-based, not evidence-based)"
  - "Benefit in osteoporosis prevention (only approved for treatment, not prevention)"

reviewer: "OSMF Medical Review Team"
last_reviewed: "2026-07-12"
---

# Teriparatide (Forteo/Forsteo)

## Overview

Teriparatide is a recombinant human parathyroid hormone peptide (PTH 1-34), approved for osteoporosis treatment. It is the first and only bone-anabolic agent approved for osteoporosis in most countries.

**Mechanism:** PTH receptor agonism on osteoblasts → bone formation via WNT/β-catenin pathway activation. Intermittent PTH stimulates osteoblast proliferation; continuous PTH does not (hence daily vs. continuous dosing distinction).

## Indications & Approvals

| Indication | Formulation | Approval (Year) | Status |
|---|---|---|---|
| Osteoporosis (postmenopausal women, men) | Forteo (subcutaneous) | 2002 | Active (2-year limit) |
| Osteoporosis (high fracture risk) | Forsteo (EU) | 2003 | Active (2-year limit) |

## Evidence Summary

### Osteoporosis Treatment (E1)
Five Phase 3 trials (N>1500) show consistent 3–4% increase in bone mineral density (BMD) at lumbar spine and hip. Fracture outcomes: 65% RRR in vertebral fractures, 53% RRR in non-vertebral fractures vs. placebo. Gold standard for bone-anabolic therapy.

## Safety Profile (S2)

**Adverse Events:**
- Nausea (transient, ~8%)
- Dizziness (6%)
- Leg cramps (3%)
- Hypercalcemia (mild, transient, ~5%)

**Serious:**
- Osteosarcoma (black box warning from rodent studies; zero cases in human trials)
- Gout/hyperuricemia (~3%)

## What Is Unknown

1. **Long-term safety beyond 2 years.** 2-year limit is regulatory precaution (rodent osteosarcoma signal), not evidence-based
2. **Osteosarcoma in humans.** Only observed in rats; mechanism in humans unknown; no cases in 2-year trials
3. **Optimal therapy duration.** Is 2 years optimal, or is longer safer?
4. **Prevention indication.** Only approved for treatment, not prevention (though mechanistic basis exists)

## Dosing (From FDA Label)

**Osteoporosis (Forteo):**
- 20 mcg (1 mL) once daily subcutaneously
- Duration: Maximum 2 years cumulative lifetime
- For high fracture risk (previous fracture, T-score ≤−3.5)

(From FDA prescribing information; see label for full details.)
