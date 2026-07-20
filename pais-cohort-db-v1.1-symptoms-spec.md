# PAIS Cohort Database — v1.1 spec addendum: symptom frequencies

Instructions for the coding agent. Extends the v1 spec. Assumes the current build (21 cohorts, `Finding` model, flat-file + CI validation) as the baseline.

---

## Why this is harder than it looks

Symptom frequency is the field's most-quoted and least-comparable number. Three cohorts reporting "fatigue: 40%" can mean three different things:

- fatigue on an open-ended "what symptoms do you have" question, vs a checklist item, vs a validated instrument above a threshold
- 40% of those enrolled, vs 40% of those still in follow-up at 12 months, vs 40% of those who were symptomatic at all
- fatigue "in the past week", vs "since infection", vs "right now"

If the database stores a symptom name and a percentage, it will produce confident cross-cohort comparisons that are wrong, and it will do so more persuasively than the literature does. The schema below exists to make each of those differences a required, visible field.

---

## 1. New entity: `SymptomFinding`

Split off from the general `Finding` record. `Finding` keeps non-symptom outcomes (QoL scores, work status, lab values, mortality). `SymptomFinding` handles symptom prevalence only.

```
SymptomFinding {
  id
  cohort_id
  publication_id

  // --- what was reported ---
  symptom_verbatim        string   REQUIRED  // exactly as printed in the paper
  symptom_id              string   REQUIRED  // mapped concept, → Symptom table
  mapping_confidence      enum     REQUIRED  // exact | close | broad | uncertain
  mapping_note            string   nullable  // required when confidence != exact

  // --- how it was measured ---
  ascertainment           enum     REQUIRED
    // validated_instrument_threshold | structured_checklist |
    // open_ended_report | clinician_assessed | medical_record_code |
    // physical_exam | unclear
  instrument_id           string   nullable  // → Instrument table
  severity_threshold      string   nullable  // e.g. "Chalder ≥4", "moderate or severe"
  reference_period        enum     REQUIRED
    // current | past_7d | past_30d | past_3mo | since_infection |
    // ever_since_onset | not_reported

  // --- the numbers ---
  timepoint_months        number   REQUIRED
  denominator_basis       enum     REQUIRED
    // enrolled | assessed_at_timepoint | symptomatic_subset |
    // responders | unclear
  n_with_symptom          number   nullable
  n_assessed              number   REQUIRED
  percent                 number   REQUIRED
  ci_low, ci_high         number   nullable
  value_precision         enum     REQUIRED
    // exact | approximate | derived | digitised_from_figure

  // --- the comparison, which is the whole point ---
  comparator_percent      number   nullable
  comparator_n            number   nullable
  comparator_group        enum     nullable   // mirrors cohort.control_group
  effect_estimate         number   nullable
  effect_type             enum     nullable   // rr | or | pr | rd | none
  p_value                 number   nullable

  source_locator          string   REQUIRED   // "Table 2", "Fig 3B", "p. 634"
  last_verified           date     REQUIRED
}
```

**Validation rules to enforce in CI:**

1. `mapping_note` required when `mapping_confidence != exact`
2. `comparator_percent` required when the parent cohort has `control_group != none` and the source reports one; if the source has controls but doesn't report this symptom in them, store the explicit sentinel `not_reported`, never blank
3. `n_with_symptom` and `n_assessed` must be consistent with `percent` to within rounding, or the record fails with a warning that must be explicitly acknowledged via `value_precision: approximate`
4. `instrument_id` required when `ascertainment = validated_instrument_threshold`

---

## 2. New reference table: `Symptom`

**Do not invent an ontology.** Map to the Human Phenotype Ontology — free, stable IDs, no licensing, and it covers nearly all of this. Add SNOMED CT codes as an optional second column for clinical interoperability.

```
Symptom {
  id                  // internal slug: "post-exertional-malaise"
  label               // display name
  hpo_id              // "HP:0012378" etc., nullable where no term exists
  snomed_id           // nullable
  domain              enum REQUIRED
  synonyms[]          // the verbatim strings seen in the literature
  definition_note     // how this database draws the boundary
}
```

`domain` enum — this is what the cross-pathogen views group on:

`fatigue_pem` · `neurocognitive` · `autonomic` · `musculoskeletal` · `sleep` · `sensory` · `gastrointestinal` · `respiratory` · `cardiovascular` · `dermatologic` · `neuropathic` · `psychiatric` · `reproductive` · `constitutional` · `other`

**Critical rule: `symptom_verbatim` is never overwritten or normalised.** The mapping is an additional layer, always reversible, always displayed alongside. A user must be able to see that "asthenia", "tiredness", "lassitude" and "fatigue" were four different words in four papers that this database chose to treat as one concept — and disagree with that choice.

Separate `fatigue` from `post_exertional_malaise` at the concept level and never merge them, even when a paper conflates them. Where a paper says only "fatigue", it maps to `fatigue` with `mapping_confidence: exact`, not to PEM.

---

## 3. New fields on `Cohort`

These prevent the single worst error this feature can produce.

```
symptom_inventory_scope   enum REQUIRED
  // comprehensive_inventory | targeted_panel | single_domain |
  // incidental | none
n_symptoms_queried        number nullable
symptom_instrument_note   string nullable
```

**Why this matters.** The Patient-Led Long COVID cohort surveyed on the order of two hundred symptoms. Dubbo asked about a handful. If the UI lets someone compare "number of symptoms reported" or "symptom breadth" across those two cohorts, it will report an artefact of questionnaire length as a finding about disease.

Any view that aggregates across cohorts must either filter on `symptom_inventory_scope` or display it per column. Enforce this in the component, not in a footnote.

---

## 4. Views to build

### 4.1 Symptom × cohort matrix (primary new view)
Rows = symptoms (grouped by domain, collapsible). Columns = cohorts. Cells = percent, shaded by magnitude.

- Distinguish **three** empty states visually and in the legend: *not measured in this cohort*, *measured and reported as absent/zero*, *measured but not reported*. These are different facts and the current `not_reported` discipline should extend here.
- Column headers show pathogen, timepoint, and `symptom_inventory_scope` badge.
- Default filter: single timepoint band, since mixing 6-month and 60-month estimates in one grid is meaningless.

### 4.2 Single-symptom cross-pathogen view (the argument view)
Pick one symptom. Render every cohort's estimate as a point with CI, grouped by pathogen, ordered by timepoint, with the control-group comparator shown as a second point on the same row.

This is the view that shows whether a symptom is a shared core feature or a pathogen-specific one — the empirical version of the tropism-versus-core question. Make it linkable and screenshot-friendly, because it's what people will cite.

Still no pooling. Display only.

### 4.3 Cohort symptom profile
On each cohort detail page: sorted horizontal bars of all symptoms reported, grouped by domain, with the comparator shown where it exists.

### 4.4 Gap matrix 3 — symptom domain × pathogen
Cell = number of cohorts that measured *anything* in that domain for that pathogen. This will be the most damning matrix on the site. Expect the autonomic and PEM rows to be nearly empty outside SARS-CoV-2.

### 4.5 Gap matrix 4 — PEM assessment × pathogen
`pem_assessed` is already in the schema and Dubbo is already recorded as `No`. Surface it as its own matrix. The fact that the field's landmark inception cohort never measured PEM is a finding, and right now it's buried on a detail page.

---

## 5. Comparability guardrail

Any view that places two or more cohorts side by side must run a comparability check and render an inline warning when the compared records differ on: `ascertainment`, `reference_period`, `denominator_basis`, or `symptom_inventory_scope`.

Wording should be specific, not generic — name the axis and the values. "These cohorts used different ascertainment: structured checklist vs open-ended report" is useful. "Interpret with caution" is not.

Do not disable the comparison. Show it, and show why it's shaky. The site's thesis is that this literature is incomparable; the tool should demonstrate that rather than pretend otherwise.

---

## 6. Seeding priorities

Add symptom findings to existing cohorts first, prioritising those with a control group — the comparator column is what makes this dataset unusual.

High-value additions, in order:

1. **Marimoutou 2012** (Réunion chikungunya, French military policemen, infected vs uninfected at 30 months). Occupationally matched with real unexposed controls and symptom-level data. Currently absent from the seed and it's arguably the best comparative symptom dataset in the whole PAIS literature.
2. **Duvignaud 2018** and **Gérardin 2011** — both TELECHIK. Attach as additional publications to the existing `telechik-reunion` cohort rather than as new cohorts. Good test of the one-cohort-many-papers model.
3. **Walkerton**, **Bergen giardiasis**, **Netherlands Q fever** — all have symptom-level data with comparison groups.
4. **Appelman 2024** (Amsterdam long COVID muscle biopsy) — small, but the only cohort with tissue-level objective measures; add as a new cohort.

---

## 7. Other improvements worth making at the same time

**Cohort relationships.** Add `related_cohorts[]` with `{ id, relation }` where relation ∈ `parent | child | overlapping_population | sibling_analysis`. TELECHIK sits inside a larger seroprevalence survey; several COVID cohorts overlap. Without this, someone summing Ns will double-count.

**Record verification metadata.** `last_verified` date and `verified_by` on each cohort, displayed. A research database with no staleness signal ages badly and invisibly.

**Missing-numerator display.** The Dubbo record currently shows `–/253` with 11%. Good that `value_precision` will now mark it, but render it as "11% (numerator not reported)" rather than an en-dash, which reads as a rendering bug.

**Attrition as a visible number.** `n_analysed / n_enrolled` as a percentage in the main table. Attrition silently reintroduces the selection bias the design fields are there to expose, and right now it's only visible if you open the record.

**Downloadable symptom matrix.** Long CSV — one row per `SymptomFinding` with all context columns denormalised — so people can do their own analysis without scraping. This is what will get the site cited.

---

## 8. Explicitly still out of scope

- Pooled prevalence estimates or meta-analysis of symptom frequencies
- Any composite "symptom burden score"
- Automated LLM mapping of `symptom_verbatim` → `symptom_id` merged without human review. Assisted mapping is fine; every mapping needs a human verifier recorded before merge, and `mapping_confidence` must be set by that human, not generated.
