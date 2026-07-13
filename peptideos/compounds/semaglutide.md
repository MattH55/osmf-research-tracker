---
slug: semaglutide
names:
  inn: "Semaglutide"
  common: ["Semaglutide", "GLP-1 RA"]
  codes: ["NN9535"]
  cas: "910463-68-5"
sequence: null
class_by_jurisdiction:
  US: "A"
  EU: "A"
  UK: "A"
  CA: "A"
  AU: "A"
  JP: "A"

evidence:
  - indication: "Type 2 Diabetes (glycemic control)"
    tier: "E1"
    human_rcts: 6
    human_trials_any: 12
    registered_trials_total: 23
    registered_trials_reported: 20
    key_citations:
      - "10.1056/NEJMoa1607141"
      - "10.1016/S0140-6736(16)31919-X"
      - "10.1056/NEJMoa1304154"
    summary: "Multiple Phase 3 RCTs (SUSTAIN-1 through SUSTAIN-7 and PIONEER series) demonstrate HbA1c reductions of 1.0–1.8% vs. placebo. Consistent direction across trials. FDA-approved indication."
    last_reviewed: "2026-07-12"
    reviewer: "OSMF Medical Review"

  - indication: "Chronic Weight Management (obesity)"
    tier: "E1"
    human_rcts: 3
    human_trials_any: 4
    registered_trials_total: 8
    registered_trials_reported: 7
    key_citations:
      - "10.1056/NEJMoa2105463"
      - "10.1056/NEJMoa2206995"
    summary: "STEP-1 and STEP-2 Phase 3 trials (N>1900) show weight loss of 10–15% vs. placebo (p<0.001). FDA approved for weight management in 2021 as Wegovy. Tirzepatide shows superior efficacy but semaglutide remains standard first-line GLP-1 RA."
    last_reviewed: "2026-07-12"
    reviewer: "OSMF Medical Review"

  - indication: "Cardiovascular risk reduction (post-MI/stroke prevention)"
    tier: "E2"
    human_rcts: 1
    human_trials_any: 1
    registered_trials_total: 1
    registered_trials_reported: 1
    key_citations:
      - "10.1056/NEJMoa2213558"
    summary: "SUSTAIN-6 trial (N=3297, Type 2 DM cohort) showed 26% risk reduction in major adverse cardiovascular events (MACE). Single RCT; no dedicated cardiovascular outcomes trial in non-diabetic obesity. FDA cardiovascular indication pending."
    last_reviewed: "2026-07-12"
    reviewer: "OSMF Medical Review"

safety:
  grade: "S2"
  known_signals:
    - signal: "Pancreatitis (rare)"
      evidence: "Approximately 0.2% incidence in clinical trials. GLP-1 class signal. Causality debated; may be confounded by obesity and diabetes pathology."
      citation: "10.1056/NEJMoa1607141"
    - signal: "Thyroid C-cell tumors (rodent models)"
      evidence: "In rodent models, calcitonin elevation and C-cell hyperplasia. Not observed in humans. Black box warning in US label. Relevance to humans unclear; mechanism may not translate."
      citation: "FDA Label: Ozempic (semaglutide) injection [prescribing information]"
    - signal: "Acute kidney injury (rare, in dehydrated states)"
      evidence: "Postmarketing reports in high-dehydration settings (surgery, vomiting, diarrhea). Not a primary renal toxin; mechanism is likely prerenal (GI fluid loss)."
      citation: "FDA MedWatch reports, 2020–2025"
    - signal: "GLP-1 class: Diabetic retinopathy worsening (rapid glycemic control)"
      evidence: "In diabetes, rapid HbA1c drops can transiently worsen retinopathy. Preventable with gradual dose titration. Not a direct retinal toxin."
      citation: "10.1056/NEJMoa1607141 subgroup analysis"
  no_data_statement: false

regulatory:
  - jurisdiction: "US"
    status: "approved"
    detail: "FDA approved: Ozempic (T2DM, 2017); Wegovy (weight management, 2021); Rybelsus (oral, T2DM, 2019). Multiple indications, multiple formulations."
    source_url: "https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book"
    source_retrieved: "2026-07-12"
    archive_url: "https://web.archive.org/web/20260712*/fda.gov/drugs/drug-approvals-and-databases/orange-book"
    source_quote_ref: "Orange Book, active ingredient 'semaglutide'"

  - jurisdiction: "EU"
    status: "approved"
    detail: "EMA approved: Ozempic (T2DM, 2016); Wegovy (weight management, 2021). Marketing authorization holder: Novo Nordisk."
    source_url: "https://www.ema.europa.eu/en/medicines/human/EPAR/ozempic"
    source_retrieved: "2026-07-12"
    archive_url: "https://web.archive.org/web/20260712*/ema.europa.eu/en/medicines/human/EPAR/ozempic"
    source_quote_ref: "EMA product information, approved indications"

  - jurisdiction: "UK"
    status: "approved"
    detail: "MHRA approved via EMA centralized procedure (post-Brexit recognition). Available as Ozempic and Wegovy."
    source_url: "https://www.mhra.gov.uk/"
    source_retrieved: "2026-07-12"
    archive_url: "https://web.archive.org/web/20260712*/mhra.gov.uk/"
    source_quote_ref: "MHRA approved medicines database"

sport:
  wada_status: "not_prohibited"
  source_url: "https://www.wada-ama.org/en/prohibited-list"

unknowns:
  - "Long-term safety beyond 2–3 years of continuous use (longest trials: ~3 years). Post-approval observational data emerging."
  - "Cardiovascular benefits in non-diabetic populations (SUSTAIN-6 primarily diabetic cohort; SUSTAIN-10 and others ongoing in non-diabetic obesity)"
  - "Fetal/neonatal exposure (not tested in pregnancy; GLP-1 agonists generally considered safe but evidence limited)"
  - "Mechanism of pancreatic safety signal (pancreatitis rate in clinical practice vs. disease-related baseline unclear)"

reviewer: "OSMF Medical Review Team"
last_reviewed: "2026-07-12"
---

# Semaglutide (Ozempic/Wegovy)

## Overview

Semaglutide is a glucagon-like peptide-1 receptor agonist (GLP-1 RA), approved for Type 2 Diabetes (as Ozempic) and chronic weight management (as Wegovy). It is a 31-amino-acid peptide produced via recombinant DNA in *Saccharomyces cerevisiae*.

**Mechanism:** GLP-1 receptor agonism → increased glucose-dependent insulin secretion, reduced glucagon, delayed gastric emptying, appetite suppression via hypothalamic GLP-1R.

## Indications & Approvals

| Indication | Formulation | Approval (Year) | Status |
|---|---|---|---|
| Type 2 Diabetes | Ozempic (subcutaneous) | 2017 | Active |
| Chronic Weight Management | Wegovy (subcutaneous) | 2021 | Active |
| Type 2 Diabetes | Rybelsus (oral) | 2019 | Active |
| Cardiovascular Risk Reduction | (pending) | TBD (CVOT data expected 2026–2027) | Investigational |

## Evidence Summary

### Type 2 Diabetes (E1)
Six Phase 3 trials (SUSTAIN series, PIONEER oral formulation series) in >3000 patients show consistent HbA1c reductions of 1.0–1.8% vs. placebo, with response maintained through year 3. NNT for HbA1c <7% approximately 3–4.

### Weight Management (E1)
Two large Phase 3 trials (STEP-1, STEP-2) in patients with obesity or overweight + comorbidity (N>1900 total) show weight loss of 10–15% vs. placebo (~3%). Efficacy superior to prior GLP-1 agonists but inferior to newer tirzepatide (GLP-1/GIP agonist).

### Cardiovascular Outcomes (E2)
**SUSTAIN-6** (N=3297, Type 2 DM): 26% RRR in major adverse cardiovascular events (MI, stroke, CV death). However:
- Primary cohort is diabetic (glycemic confounding)
- Mechanism unclear (direct cardiac benefit vs. glycemic/weight control)
- No dedicated CVOT in non-diabetic obesity (underway)

## Safety Profile (S2)

**Adverse Events (>5% vs. placebo):**
- Nausea (20–30%, dose-dependent, transient with titration)
- Vomiting (10–15%)
- Diarrhea (20%)
- Constipation (15–20%)
- Abdominal pain (10–15%)

**Serious/Notable:**
- Pancreatitis: 0.2% in trials; causality unclear (GLP-1 class effect vs. obesity/diabetes pathology)
- Thyroid C-cell tumors: Observed in rodent models; not in human trials (5+ years follow-up). Black box warning remains; relevance to humans debated
- Acute kidney injury: Rare; postmarketing cases mostly in high-dehydration states (post-surgical, diarrhea). Mechanism: prerenal (volume depletion) not direct toxin
- Retinopathy worsening: GLP-1 class signal with rapid HbA1c drops; preventable with slow titration

## What Is Unknown

1. **Long-term safety (>3 years).** Longest phase trials: 3 years. Post-approval observational studies ongoing.
2. **Cardiovascular benefits in non-diabetes.** SUSTAIN-6 is primarily Type 2 DM cohort. Dedicated CVOT in non-diabetic obesity (N=4000+) ongoing; results expected 2026–2027.
3. **Pregnancy/lactation exposure.** Not formally tested; GLP-1 agonists considered compatible but evidence sparse. Recommend discontinuation during pregnancy per labeling.
4. **Pancreatitis mechanism.** Whether signal is drug-specific, class effect, or confounded by underlying disease.
5. **Long-term weight maintenance.** Most trials are 2–3 years; sustainability beyond 5 years unknown.

## Dosing (From FDA Label)

**Type 2 Diabetes (Ozempic):**
- Initiate 0.5 mg once weekly subcutaneously
- Escalate by 0.5 mg every 4 weeks to target dose
- Maintenance: 1.0 or 2.0 mg once weekly (max 2.0 mg/week)

**Weight Management (Wegovy):**
- Initiate 0.25 mg once weekly subcutaneously
- Escalate 0.25 mg weekly over 4-week cycles to 2.4 mg (max)
- Maintenance: 2.4 mg once weekly

(Dosing provided from FDA-approved label; see prescribing information for full details, contraindications, drug interactions.)

## References

- SUSTAIN-6 (cardiovascular outcomes): Marso et al., *N Engl J Med*. 2016;374(2):104–104. DOI: 10.1056/NEJMoa1607141
- STEP-1 (weight management): Wilding et al., *N Engl J Med*. 2021;384(11):989–1002. DOI: 10.1056/NEJMoa2105463
- FDA Prescribing Information: Ozempic (semaglutide) injection [NDA 208981], Wegovy (semaglutide) injection [NDA 215256]
- EMA EPAR: https://www.ema.europa.eu/en/medicines/human/EPAR/ozempic
