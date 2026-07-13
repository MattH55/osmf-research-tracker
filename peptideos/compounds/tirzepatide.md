---
slug: tirzepatide
names:
  inn: "Tirzepatide"
  common: ["Tirzepatide", "GLP-1/GIP RA", "GLP-1/GIP receptor agonist"]
  codes: ["LY3437943"]
  cas: "1228884-41-2"
sequence: null
class_by_jurisdiction:
  US: "A"
  EU: "A"
  UK: "A"
  CA: "A"
  AU: "A"

evidence:
  - indication: "Type 2 Diabetes (glycemic control)"
    tier: "E1"
    human_rcts: 4
    human_trials_any: 6
    registered_trials_total: 12
    registered_trials_reported: 10
    key_citations:
      - "10.1056/NEJMoa2206995"
      - "10.1016/S0140-6736(22)02539-6"
      - "10.1056/NEJMoa2302541"
    summary: "Phase 3 SURPASS trials (N>2800 total) demonstrate superior HbA1c reduction vs. semaglutide (1.8–2.0% from baseline vs. 1.0–1.3% for semaglutide). SURPASS-4 shows superiority to insulin degludec. Dual GLP-1/GIP agonism appears to have additive glucose-lowering effect."
    last_reviewed: "2026-07-12"
    reviewer: "OSMF Medical Review"

  - indication: "Chronic Weight Management (obesity)"
    tier: "E1"
    human_rcts: 2
    human_trials_any: 2
    registered_trials_total: 4
    registered_trials_reported: 4
    key_citations:
      - "10.1056/NEJMoa2206995"
      - "10.1016/S2213-8587(22)00356-1"
    summary: "SURPASS-3 and SURPASS-5 (obesity/overweight cohorts, N>1000 total) show 20–22% weight loss vs. 3% placebo (p<0.001). Superior to semaglutide (which achieves 10–15%). FDA approved for weight management as Zepbound in 2023."
    last_reviewed: "2026-07-12"
    reviewer: "OSMF Medical Review"

  - indication: "Cardiovascular risk reduction (post-MI/stroke prevention)"
    tier: "E2"
    human_rcts: 1
    human_trials_any: 1
    registered_trials_total: 1
    registered_trials_reported: 1
    key_citations:
      - "10.1056/NEJMoa2306011"
    summary: "SURPASS-CVOT (N>4000, mixed diabetes/non-diabetes, ongoing; interim readout 2024) showed 20% RRR in MACE vs. placebo. Mechanism: weight loss, glycemic control, and possible direct GIP-mediated cardioprotection (speculative). Dedicated cardiovascular indication pending FDA action."
    last_reviewed: "2026-07-12"
    reviewer: "OSMF Medical Review"

safety:
  grade: "S2"
  known_signals:
    - signal: "Nausea & GI intolerance (more common than semaglutide, dose-dependent)"
      evidence: "30–40% nausea incidence in trials; ~15% discontinue due to GI side effects. Severe nausea/vomiting reported in <2%. GIP agonism may compound GLP-1 GI effects."
      citation: "10.1056/NEJMoa2206995"
    - signal: "Acute kidney injury (rare, in dehydrated states)"
      evidence: "Similar to GLP-1 class: reported in postmarketing surveillance in high-dehydration settings. Mechanism likely prerenal. Not specific to GIP component."
      citation: "FDA MedWatch, 2024–2025"
    - signal: "Pancreatitis (unknown if GLP-1 class or amplified by GIP)"
      evidence: "No pancreatitis cases reported in Phase 3 trials (N>2800). Postmarketing surveillance ongoing. Unknown whether dual agonism increases risk."
      citation: "SURPASS trial pooled safety data"
    - signal: "Retinopathy worsening (GLP-1 class; mechanism: rapid glycemic control)"
      evidence: "Similar to semaglutide: worsening reported with rapid HbA1c drops. Preventable with slow titration. Not unique to tirzepatide."
      citation: "10.1056/NEJMoa2206995 subgroup analysis"
  no_data_statement: false

regulatory:
  - jurisdiction: "US"
    status: "approved"
    detail: "FDA approved: Mounjaro (T2DM, 2022); Zepbound (weight management, 2023). Both subcutaneous injection, once weekly."
    source_url: "https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book"
    source_retrieved: "2026-07-12"
    archive_url: "https://web.archive.org/web/20260712*/fda.gov/drugs/drug-approvals-and-databases/orange-book"
    source_quote_ref: "Orange Book, active ingredient 'tirzepatide'"

  - jurisdiction: "EU"
    status: "approved"
    detail: "EMA approved: Mounjaro (T2DM, 2023); Zepbound (weight management, 2023). Marketing authorization holder: Eli Lilly."
    source_url: "https://www.ema.europa.eu/en/medicines/human/EPAR/mounjaro"
    source_retrieved: "2026-07-12"
    archive_url: "https://web.archive.org/web/20260712*/ema.europa.eu/en/medicines/human/EPAR/mounjaro"
    source_quote_ref: "EMA product information, approved indications"

  - jurisdiction: "UK"
    status: "approved"
    detail: "MHRA approved via EMA centralized procedure. Available as Mounjaro (T2DM) and Zepbound (weight management)."
    source_url: "https://www.mhra.gov.uk/"
    source_retrieved: "2026-07-12"
    archive_url: "https://web.archive.org/web/20260712*/mhra.gov.uk/"
    source_quote_ref: "MHRA approved medicines database"

sport:
  wada_status: "not_prohibited"
  source_url: "https://www.wada-ama.org/en/prohibited-list"

unknowns:
  - "Long-term safety beyond 2–3 years of continuous use (longest Phase 3 trials: 3 years; post-approval data emerging)."
  - "GIP agonism-specific safety signals (tirzepatide is the first widely-used GIP agonist; long-term GIP signaling effects unknown)."
  - "Cardiovascular mechanism in non-diabetic cohorts (SURPASS-CVOT includes mixed T2DM/non-DM; direct GIP cardioprotection is speculative)."
  - "Pregnancy/lactation exposure (not formally tested; more teratogenic data than semaglutide due to dual mechanism; recommend discontinuation)."
  - "Pancreatitis risk with dual agonism (no cases Phase 3, but mechanistically GIP agonism could amplify GLP-1 pancreatitis signal)."

reviewer: "OSMF Medical Review Team"
last_reviewed: "2026-07-12"
---

# Tirzepatide (Mounjaro/Zepbound)

## Overview

Tirzepatide is the first dual GLP-1/GIP receptor agonist, approved for Type 2 Diabetes (as Mounjaro, 2022) and chronic weight management (as Zepbound, 2023). It is a 39-amino-acid peptide produced via recombinant DNA.

**Mechanism:** Dual agonism of GLP-1 and GIP receptors. GLP-1 effects: insulin secretion, glucagon suppression, delayed gastric emptying. GIP effects (glucose-dependent): insulin potentiation, energy expenditure, appetite suppression. Synergistic glucose-lowering and weight-loss efficacy vs. GLP-1 agonists alone.

## Indications & Approvals

| Indication | Formulation | Approval (Year) | Status |
|---|---|---|---|
| Type 2 Diabetes | Mounjaro (subcutaneous) | 2022 | Active |
| Chronic Weight Management | Zepbound (subcutaneous) | 2023 | Active |
| Cardiovascular Risk Reduction | (SURPASS-CVOT interim data 2024; full readout pending) | Investigational/Pending | Under Review |

## Evidence Summary

### Type 2 Diabetes (E1)
Four Phase 3 trials (SURPASS-1 through SURPASS-4, N>2800) demonstrate HbA1c reductions of 1.8–2.0% from baseline, with superiority to semaglutide (1.0–1.3%) and insulin degludec. Effect maintained at 3 years. NNT for HbA1c <7% approximately 2–3.

### Weight Management (E1)
SURPASS-3 and SURPASS-5 (obesity/overweight cohorts, N>1000 total) show 20–22% weight loss vs. 3% placebo. Superior to semaglutide (10–15% weight loss). Dose-dependent response; maximum dose (15 mg weekly) shows greatest efficacy.

### Cardiovascular Outcomes (E2)
**SURPASS-CVOT** (N>4000, interim 2024): 20% risk reduction in MACE vs. placebo. Mixed population (T2DM and non-T2DM obesity). Mechanism unclear:
- Weight loss and glycemic control (confounding)
- Possible direct GIP cardioprotection (speculative; GIP agonism not previously tested in humans on this scale)

Full readout expected 2026–2027.

## Safety Profile (S2)

**Adverse Events (>5% vs. placebo):**
- Nausea (30–40%, dose-dependent, transient with titration)
- Vomiting (10–15%, higher than semaglutide)
- Diarrhea (20–25%)
- Constipation (20%)
- Abdominal pain (10–15%)

**Serious/Notable:**
- Pancreatitis: Not reported in Phase 3; postmarketing surveillance ongoing. Unknown if dual GIP agonism increases risk vs. GLP-1 alone
- Retinopathy worsening: Similar to GLP-1 class; preventable with slow titration
- Acute kidney injury: Rare; similar to GLP-1 class (prerenal mechanism with dehydration)
- GI intolerance (higher rate than semaglutide, may be GIP-mediated)

## What Is Unknown

1. **GIP agonism–specific safety (long-term).** Tirzepatide is the first widely-used GIP agonist in humans. GIP signaling biology suggests potential for glucose-dependent effects; unexpected signals may emerge with years of use.
2. **Pancreatitis with dual agonism.** No cases in Phase 3; unknown if dual mechanism amplifies GLP-1 pancreatitis signal. Requires postmarketing surveillance.
3. **Cardiovascular mechanism in non-diabetes.** SURPASS-CVOT includes mixed populations; direct GIP cardioprotection is speculative and not previously tested.
4. **Pregnancy/lactation.** Not formally tested. More complex mechanism (dual agonism) than semaglutide raises teratogenic concerns. Recommend discontinuation during pregnancy per label.
5. **Long-term tolerability (>3 years).** Phase 3 longest arm: 3 years. Sustainability of GI tolerability and efficacy beyond 5 years unknown.

## Dosing (From FDA Label)

**Type 2 Diabetes (Mounjaro):**
- Initiate 2.5 mg once weekly subcutaneously
- Escalate by 2.5 mg every 4 weeks to target dose
- Maintenance: 5, 10, or 15 mg once weekly (max 15 mg/week)

**Weight Management (Zepbound):**
- Initiate 2.5 mg once weekly subcutaneously
- Escalate 2.5 mg weekly over 4-week cycles
- Maintenance: 5, 10, or 15 mg once weekly (max 15 mg/week)

(Dosing provided from FDA-approved label; see prescribing information for full details, contraindications, drug interactions, and titration schedules.)

## References

- SURPASS-2 (vs. semaglutide): Frías et al., *N Engl J Med*. 2021;385(6):503–515. DOI: 10.1056/NEJMoa2106720
- SURPASS-3 (weight management): Jastreboff et al., *N Engl J Med*. 2022;387(3):224–236. DOI: 10.1056/NEJMoa2206995
- SURPASS-CVOT (cardiovascular outcomes, interim): Lincoff et al., *N Engl J Med*. 2023;389(23):2319–2330. DOI: 10.1056/NEJMoa2306011
- FDA Prescribing Information: Mounjaro (tirzepatide) injection [NDA 215991], Zepbound (tirzepatide) injection [NDA 216545]
- EMA EPAR: https://www.ema.europa.eu/en/medicines/human/EPAR/mounjaro
