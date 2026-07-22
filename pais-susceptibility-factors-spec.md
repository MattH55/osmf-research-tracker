# PAIS Cohort Database — v2.1 spec: susceptibility and conversion predictors

Instructions for the coding agent. Extends the v2 heterogeneous-data schema. Target: for every syndrome in the database, capture what predicts who develops it — with emphasis on variables measured during the acute infection.

---

## 0. Scope discipline — read this before writing any schema

"Susceptibility factor" collapses four different causal questions. They are constantly conflated in this literature and must never be conflated in the data.

| Question | `question_type` | Example |
|---|---|---|
| Who gets infected? | `susceptibility_infection` | Occupational exposure to livestock in Q fever |
| Who gets severe acute disease? | `susceptibility_acute_severity` | Secondary heterotypic dengue infection |
| **Given infection, who develops the chronic syndrome?** | `conversion` | Acute illness severity in Dubbo |
| Among those who converted, who fails to recover? | `persistence` | Predictors of non-recovery at 4 years |

**`conversion` is the target of this build.** The others are recorded when a source reports them, but they are separate rows and must never be aggregated together. A factor can act in opposite directions on two of these.

---

## 1. The temporality rule

**A predictor measured after the outcome began is not a susceptibility factor.** It is a correlate of prevalent disease, and it is confounded by reverse causation.

Every predictor record carries:

```
measurement_window   enum REQUIRED
  // pre_infection | acute_phase | early_convalescent (≤3mo) |
  // post_outcome | genetic_fixed | unknown

temporality_valid    derived boolean
  // true only when measurement_window ∈
  // { pre_infection, acute_phase, genetic_fixed }
  // AND the cohort design is prospective_inception or registry_linkage
```

Default all views to `temporality_valid: true`. Make the invalid ones reachable but clearly labelled. This single field is what separates a susceptibility database from a pile of cross-sectional correlations, and it will exclude most of what the literature calls risk factors.

---

## 2. New entity: `Predictor`

One record per factor–outcome–cohort triple.

```jsonc
{
  "id": "dubbo-pred-0003",
  "cohort_id": "dubbo-infection-outcomes",
  "publication_id": "hickie-2006-bmj",
  "question_type": "conversion",

  // --- the factor ---
  "factor_id": "acute:illness-severity-composite",   // → Factor registry
  "factor_verbatim": "severity of the acute illness",
  "measurement_window": "acute_phase",
  "factor_value_type": "ordinal",        // binary | ordinal | continuous | categorical
  "contrast": "per 1 SD increase",       // REQUIRED — the comparison being made
  "reference_level": null,

  // --- the outcome it predicts ---
  "outcome_measure_id": "case-def:cfs-fukuda-1994",
  "outcome_timepoint_months": 6,

  // --- the estimate ---
  "estimate": {
    "type": "or",                        // or | rr | hr | beta | md | smd | none
    "value": null,
    "ci_low": null, "ci_high": null,
    "p_value": null,
    "direction": "increases_risk",       // increases_risk | decreases_risk |
                                          // null_result | not_reported
    "significant": true
  },

  // --- how the estimate was produced ---
  "model": {
    "type": "multivariable_logistic",    // univariable | multivariable_* |
                                          // survival | mixed_effects | none
    "adjusted_for": ["age", "sex"],
    "prespecified": "unclear",           // yes | no | unclear
    "n_predictors_tested": 12,
    "multiplicity_correction": "none"    // none | bonferroni | fdr | other | unclear
  },

  "n_analysed": 253,
  "provenance": { /* as v2: source_locator, extracted_by, verified_by, dates */ }
}
```

### 2.1 Non-negotiable fields, and why

- **`contrast`** — "female sex" means nothing without "versus male." "Viral load" means nothing without "per log10 copies/mL." Reject records without it.
- **`direction`** with an explicit `null_result` value — negative findings are the most valuable and least recorded content in this database. A factor tested in five cohorts and significant in one is a different fact from a factor tested once.
- **`n_predictors_tested`** and **`multiplicity_correction`** — a susceptibility database is a machine for aggregating false positives unless it records how many things were tested to find each one. Many of these papers test dozens of candidate predictors and report the survivors.
- **`adjusted_for`** — an unadjusted and an adjusted estimate for the same factor are two records, not one, and both should be stored where reported.

---

## 3. The `Factor` registry

Mirrors the v2 `Measure` registry pattern. Namespaced ids by domain.

```jsonc
{
  "id": "acute:illness-severity-composite",
  "domain": "acute_clinical",
  "label": "Acute illness severity (composite index)",
  "harmonised_construct": "acute_severity",   // ← the cross-pathogen key
  "native_scales": ["Dubbo somatic symptom severity score",
                    "WHO dengue severity grade",
                    "hospitalisation (binary)",
                    "WHO ordinal scale for COVID-19"],
  "ontology": { "snomed": null, "loinc": null },
  "unit": null, "unit_ucum": null
}
```

**Domains to seed:**

`host_demographic` · `host_genetic` · `host_prior_health` · `acute_clinical` · `acute_laboratory` · `acute_pathogen` · `acute_treatment` · `acute_immune` · `psychosocial` · `healthcare_access` · `environmental`

### 3.1 Acute-phase factors — the priority list

This is the heart of the build. Seed the registry with these, since they are what the request is actually about.

**`acute_clinical`**
hospitalisation · ICU admission · fever duration (days) · peak temperature · symptom count at presentation · composite severity score · presence of WHO warning signs · time from onset to presentation · rash · arthralgia at presentation · vomiting · bleeding manifestations · oxygen requirement · neurological involvement

**`acute_laboratory`**
platelet nadir · haematocrit peak / haemoconcentration · lymphocyte count · neutrophil-lymphocyte ratio · CRP · ferritin · LDH · ALT/AST · albumin · D-dimer · creatinine

**`acute_pathogen`**
viral load / Ct value · NS1 antigenaemia · serotype (dengue) · variant/strain · primary vs secondary infection (serostatus) · duration of viraemia/shedding · antigen persistence at convalescence

**`acute_treatment`**
corticosteroids · antivirals · antibiotics · NSAIDs · IV fluids volume · bed rest duration · antibody therapy

**`acute_immune`**
acute cytokine levels (IL-6, IL-1β, IFN-γ, TNF-α, IL-10) · autoantibody presence · lymphocyte subsets · complement activation

**`host_prior_health`**
pre-existing comorbidity count · prior ME/CFS or fibromyalgia · atopy/allergy · autoimmune disease · BMI · prior infection with same or related pathogen

**`host_genetic`**
HLA type · cytokine gene polymorphisms · P2X7 · specific GWAS loci (BTN2A2, OLFM4, RABGAP1L)

---

## 4. Cross-pathogen harmonisation — the hard part

The whole point is comparing "acute severity predicts conversion" across dengue, EBV, Ebola, Q fever and SARS-CoV-2. But acute severity is a WHO dengue grade in one cohort, ICU admission in another, and a self-report symptom score in Dubbo.

**Rule: never overwrite the native measure.** Add a harmonised layer, exactly as v2 does for symptoms.

```jsonc
"harmonised": {
  "ruleset": "pais-severity-harmony-v1",
  "construct": "acute_severity",
  "normalised_scale": "ordinal_0_4",
  "mapped_level": 3,
  "mapping_rationale": "hospitalised without ICU → level 3",
  "confidence": "close"
}
```

Define `ordinal_0_4` once, in a versioned document: 0 = asymptomatic, 1 = symptomatic ambulatory, 2 = ambulatory with functional limitation, 3 = hospitalised, 4 = ICU/organ support. Publish the mapping table alongside the data so anyone can reject it and remap from the native values.

Do the same for `viral_burden` and `inflammatory_burden`. Do **not** attempt it for anything else in v2.1 — three harmonised constructs done well beats eleven done badly.

---

## 5. Replication tracking — the payoff

Compute, don't store, per `(harmonised_construct or factor_id, outcome_construct, question_type)`:

```
n_cohorts_tested
n_pathogens_tested
n_significant
n_null
direction_concordance      // fraction agreeing on sign among significant results
temporality_valid_fraction
median_n_predictors_tested // multiplicity exposure of the supporting studies
```

Render as a **replication table** — the single most useful view in this feature. Expect two rows to stand out (acute severity, female sex) and a long tail of factors tested exactly once. That contrast *is* the finding, and no existing resource displays it.

**Do not compute a meta-analytic pooled effect.** Different contrasts, different adjustment sets, different outcome definitions. Display the estimates as a forest-style plot grouped by pathogen; leave pooling to whoever wants to defend it.

---

## 6. Views to build

1. **Factor × pathogen matrix.** Cell states, four-way: `never tested` · `tested, null` · `tested, significant` · `tested, conflicting`. Filter to `temporality_valid`. The `never tested` cells across the acute-laboratory domain will be the most damning output of this whole project.
2. **Per-syndrome susceptibility page.** One page per pathogen: everything tested, sorted by replication count then by evidence quality. Linked from each disease page.
3. **Replication table** (§5).
4. **Acute-phase coverage matrix.** Cohort × acute-variable-domain, showing which cohorts even *collected* acute clinical data. Many prospective-inception cohorts collected it and never published it against the chronic outcome — flag those separately as `collected_not_analysed`, because they are recoverable through collaboration rather than new enrolment.
5. **Single-factor detail page.** All estimates for one factor across all cohorts, with contrast, adjustment set, and multiplicity exposure shown per row.

---

## 7. Extraction workflow

1. Work cohort by cohort, in the order: prospective inception → registry linkage → everything else.
2. For each cohort, extract from the **cohort's full publication set**, not just the primary paper. Acute-phase clinical variables usually appear in an earlier acute-phase paper by the same group; the chronic outcome appears years later in a different journal. The v2 one-cohort-many-papers model is what makes this tractable — use it.
3. Extract the full multivariable model table where one exists, including non-significant rows. **Null results are required, not optional.**
4. Record `n_predictors_tested` from the paper's own methods or table length.
5. Where a cohort collected an acute variable but never analysed it against the chronic outcome, create the record with `estimate.direction: "not_reported"` and `analysis_status: "collected_not_analysed"`.
6. Human verification before merge, as v2. Assisted extraction is permitted; unverified merge is not.

---

## 8. What not to do

- **Don't pool across pathogens.** The comparison is the product; the pooled number would destroy it.
- **Don't rank factors by effect size.** Rank by replication and by temporality validity. Effect sizes here are not comparable across contrasts.
- **Don't import cross-sectional correlates of prevalent disease as susceptibility factors.** Store them with `measurement_window: post_outcome` and keep them out of default views.
- **Don't drop null results.** They are the reason to build this rather than read a review.
- **Don't let `harmonised_construct` become the primary key.** The native measure is the data; the harmonisation is an opinion, and opinions get versioned and can be rejected.

---

## 9. Acceptance criteria

- [ ] Every `Predictor` has `contrast`, `measurement_window`, and `direction` populated — schema-enforced
- [ ] `null_result` records exist and are ≥30% of the table (if they aren't, extraction is cherry-picking)
- [ ] `temporality_valid` is computed, not hand-entered
- [ ] Factor × pathogen matrix renders `never tested` distinctly from `tested, null`
- [ ] Replication table sorts by `n_cohorts_tested` and shows `n_null` alongside `n_significant`
- [ ] Harmonisation mapping table is published as a separate versioned file, and every harmonised record cites its ruleset version
- [ ] No pooled effect estimate appears anywhere in the UI or the export
