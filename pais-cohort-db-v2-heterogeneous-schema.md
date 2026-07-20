# PAIS Cohort Database — schema for heterogeneous cohort data (v2)

Replaces the growing set of result entities (`Finding`, `SymptomFinding`, and whatever comes next) with one extensible model.

---

## The problem being solved

Cohorts in this database report structurally different things:

- Dubbo: proportion meeting a case definition at two timepoints
- Walkerton: risk ratios for post-infectious IBS with matched unexposed controls
- Moldofsky: mean sleep EEG parameters in 29 people versus controls
- PREVAIL III: incidence rates over five years with household-contact comparison
- Appelman: paired before/after tissue measurements in 25 people
- Davis: ~200 symptom prevalences from a self-selected survey
- Nohynek: registry-linked incidence with an age-stratified rate ratio

Adding a table per result shape produces an unmaintainable schema and views that need unions across six entities. Adding nullable columns to one table produces a hundred-column record that is 90% empty.

The solution is the one OMOP and FHIR both use: **a single observation record whose `value` is a discriminated union, keyed to a registry of measures.** Study-level aggregates rather than patient-level rows, so this is OMOP-inspired, not OMOP — the full CDM is the wrong tool for aggregate data.

---

## 1. Three-layer architecture

```
Layer 1  CORE        every cohort has these       strict, closed schema
Layer 2  OBSERVATION anything a cohort measured   one polymorphic record
Layer 3  EXTENSION   the genuinely idiosyncratic  namespaced, separately validated
```

Nothing moves between layers without a schema version bump.

---

## 2. Layer 1 — Core

Unchanged from v1: identity, trigger, design, size/attrition, biospecimens, provenance. These are the fields that exist for every cohort regardless of what it measured, and they stay a strict closed schema. Do not let observation-specific fields leak in here.

Add:

```
schema_version        string  REQUIRED   // "2.0.0"
harmonisation_ruleset string  REQUIRED   // "pais-harmony-v1"
related_cohorts[]     { id, relation }   // parent | child | overlapping_population | sibling_analysis
```

---

## 3. Layer 2 — the `Observation` record

One record per reported result, of any kind.

```jsonc
{
  "id": "dubbo-obs-0007",
  "cohort_id": "dubbo-infection-outcomes",
  "publication_id": "hickie-2006-bmj",
  "schema_version": "2.0.0",

  // WHAT was measured — always a registry reference
  "measure_id": "case-def:cfs-fukuda-1994",
  "measure_verbatim": "met diagnostic criteria for a chronic fatigue syndrome",

  // WHO it was measured in
  "population": {
    "scope": "whole_cohort",          // whole_cohort | subgroup | stratum
    "stratum": null,                   // { variable, level } when scope != whole_cohort
    "denominator_basis": "assessed_at_timepoint",
    "n_assessed": 253
  },

  // WHEN
  "timing": {
    "timepoint_months": 6,
    "timepoint_band": "3-6mo",         // derived, for grouping
    "reference_period": "current",
    "is_cumulative": false
  },

  // HOW
  "method": {
    "ascertainment": "structured_checklist",
    "instrument_id": null,
    "severity_threshold": null,
    "blinded_assessment": "not_reported"
  },

  // THE VALUE — discriminated union
  "value": {
    "type": "proportion",
    "numerator": { "status": "measured_not_reported" },
    "denominator": 253,
    "percent": 11.0,
    "ci": null,
    "precision": "approximate"
  },

  // THE COMPARISON
  "comparator": {
    "group": "none",
    "value": { "status": "not_applicable" },
    "effect": null
  },

  // PROVENANCE — per observation, not per cohort
  "provenance": {
    "source_locator": "Results, para 3",
    "extracted_by": "mh",
    "extracted_on": "2026-07-18",
    "verified_by": "mh",
    "verified_on": "2026-07-18",
    "extraction_method": "manual"      // manual | assisted_verified
  }
}
```

### 3.1 The `value` union — the load-bearing piece

Each variant is separately schema-validated on `type`.

| `type` | fields |
|---|---|
| `proportion` | numerator, denominator, percent, ci, precision |
| `count` | n, denominator?, precision |
| `rate` | events, person_time, person_time_unit, rate, ci |
| `mean_sd` | mean, sd, n, ci |
| `median_iqr` | median, q1, q3, n, range? |
| `geometric_mean` | gm, gsd, n |
| `categorical_distribution` | categories[] of { label, n, percent } |
| `time_to_event` | median_time, unit, n_events, n_at_risk, ci |
| `effect_only` | estimate, effect_type, ci, p_value, adjusted_for[] |
| `paired_change` | baseline, followup, delta, sd_delta, n_pairs, p_value |
| `presence` | boolean, basis |
| `qualitative` | text, n_supporting |

`paired_change` is what lets Appelman-style before/after exercise data sit in the same table as everything else. `rate` is what lets PREVAIL III's person-time data coexist with Dubbo's simple proportions without either being distorted.

### 3.2 Missingness is a typed value, never `null`

Any value slot accepts either a value or:

```jsonc
{ "status": "not_measured" }            // the study never assessed this
{ "status": "measured_not_reported" }   // assessed, number not published
{ "status": "reported_as_zero" }        // explicitly zero, not missing
{ "status": "not_applicable" }
{ "status": "unknown" }
```

These are five different facts and the UI must render them as five different things. `not_measured` versus `measured_not_reported` is the distinction that makes the gap matrices honest.

---

## 4. The `Measure` registry

One registry for everything measurable — symptoms, case definitions, instruments, lab analytes, physiologic tests, functional outcomes. Splitting these into separate tables forces a union in every cross-cutting query.

```jsonc
{
  "id": "sym:post-exertional-malaise",
  "kind": "symptom",              // symptom | case_definition | instrument_score
                                  // | lab | physiologic | functional | event
  "label": "Post-exertional malaise",
  "domain": "fatigue_pem",
  "ontology": {
    "hpo": null,
    "snomed": "76957007",
    "loinc": null
  },
  "default_value_type": "proportion",
  "synonyms": ["post-exertional symptom exacerbation", "PESE",
               "relapse after exertion"],
  "boundary_note": "Never merged with sym:fatigue, even where the source conflates them.",
  "unit": null,
  "unit_ucum": null
}
```

Namespaced ids (`sym:`, `lab:`, `instr:`, `physio:`, `event:`) keep the registry readable and make the kind obvious in any observation record.

Use HPO for symptoms, LOINC for labs, UCUM for units, SNOMED where the others have no term. Do not invent identifiers where a standard exists.

---

## 5. Layer 3 — namespaced extensions

The pressure valve. Some cohorts report things nothing else will ever report — chikungunya DAS28 joint counts, Ebola uveitis laterality, narcolepsy MSLT latencies.

```jsonc
"extensions": {
  "chikv": { "das28_esr_mean": 3.39, "das28_esr_sd": 0.87 },
  "ebola": { "uveitis_laterality": "bilateral", "n_eyes": 84 }
}
```

Rules:

1. Each namespace has its own JSON Schema at `/schema/ext/<ns>.schema.json`
2. CI validates a namespace **if a schema exists**; if none exists, the data is preserved and flagged `unvalidated`, never rejected
3. A namespace used by three or more cohorts is a candidate for promotion into a proper `Measure` and observations — review quarterly
4. Extensions never appear in cross-cohort comparison views, only on detail pages

This is what stops the core schema growing a field every time an unusual cohort is added.

---

## 6. Comparability signatures — the idea worth stealing

Rather than warning in the UI about incomparable comparisons, make comparability a property of the data.

Compute per observation:

```
comparability_signature = hash(
  measure_id,
  method.ascertainment,
  timing.reference_period,
  population.denominator_basis,
  timing.timepoint_band,
  value.type
)
```

Two observations sharing a signature are directly comparable. Differing signatures are not — and the diff of the component fields tells you exactly why, which is what the warning text should say.

Downstream this gives you: a "comparable set" filter on every view, an automatic explanation for every warning, and a queryable answer to "how many cohorts measured fatigue in a directly comparable way?" — which is currently unanswerable in this field and is a publishable finding on its own.

---

## 7. Harmonisation as an additive layer

Never mutate source values. Store both:

```jsonc
"as_reported": { ... },
"harmonised": {
  "ruleset": "pais-harmony-v1",
  "measure_id": "sym:fatigue",
  "value": { "type": "proportion", "percent": 40.2 },
  "transformations": ["mapped_verbatim:asthenia→fatigue",
                      "rebased_denominator:responders→assessed"],
  "confidence": "close"
}
```

Rulesets are versioned and named, so any derived figure can be reproduced and any harmonisation decision can be contested without re-extraction. When the ruleset changes, harmonised values are recomputed from source; source is never touched.

---

## 8. Migration path from v1

1. Freeze v1, tag the repo
2. Write `scripts/migrate_v1_to_v2.py`: existing `Finding` records → `Observation` with `value.type: proportion`, `measure_id` mapped to the new registry, `provenance.extraction_method: manual`
3. Backfill required v2 fields with explicit missingness sentinels, not guesses — `measured_not_reported` is the honest default for anything the v1 schema didn't capture
4. Run both schemas in CI for one release so a bad migration is visible
5. Keep `/data/v1/` published at stable URLs indefinitely; people will have cited it

---

## 9. What not to do

- **Don't use bare EAV.** Attribute-value pairs without a measure registry are unqueryable and drift immediately into synonym chaos.
- **Don't add nullable columns to a wide table.** That's the failure mode this design exists to avoid.
- **Don't let extensions become the default path.** If a third cohort needs the same extension, it belongs in the registry.
- **Don't harmonise on ingest.** Source values are the asset; harmonisation is an opinion and opinions get versioned.
- **Don't compute a comparability score.** The signature says comparable or not, and shows why. A score invites argument about weights instead of about evidence.
