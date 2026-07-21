# PAIS Cohort Database — expansion guide for a coding agent

How to add cohorts and observations to the PAIS cohort database (v2, Observation model) without
breaking it. Assumes the current build: 27 cohorts, one JSON file per cohort under
`data/cohorts/`, a unified Measure registry, comparability signatures, CI validation, and a
static build served from GitHub Pages at research.opensourcemed.info.

Read this before touching the data. The two hard rules:

1. **Every field is human-verified against the primary source before merge.** Assisted
   extraction is fine; unverified auto-extraction is not. An unverified research database is
   worse than none.
2. **Never fabricate a number, a DOI, or a denominator.** If the source does not report
   something, say so with a typed missingness sentinel, never a guess and never `null`.

---

## 0. Orientation — the files you will touch

```
data/pais-cohort.schema.json     the v2 JSON Schema (source of truth for structure)
data/cohorts/<id>.json           one cohort per file  ← you mostly add/edit these
data/ref/pathogens.json          disease/trigger registry
data/ref/measures.json           unified Measure registry (what was measured)
data/ref/instruments.json        measurement instruments (how)
schema/ext/<ns>.schema.json      optional Layer-3 extension schemas
scripts/build_pais_cohorts.py    validate + compile + render (run this; it is the CI gate)
scripts/migrate_v1_to_v2.py      one-off v1→v2 migration (reference only)
data/v1/                         frozen v1.1 snapshot — do not edit
```

Build + validate locally (this is exactly what CI runs):

```bash
python scripts/build_pais_cohorts.py --check   # validate only (fast; use while iterating)
python scripts/build_pais_cohorts.py           # validate + rebuild all artifacts
```

A non-zero exit means it will not merge. Commit the regenerated artifacts
(`data/pais-cohorts-index.json`, both CSVs, `pais-cohorts.html`, `pais-cohorts/**`) alongside
the data — CI diffs them and fails if they are stale.

---

## 1. The mental model

- The unit of record is the **cohort** (a followed study population), never the publication.
  One cohort → many publications (`publications[]`) and many **observations**
  (`observations[]`). If a new paper reports on an existing cohort, add it as a publication and
  its numbers as observations on that cohort — do **not** create a second cohort. Sibling
  studies of the same outbreak (e.g. TELECHIK / Schilte / Marimoutou on Réunion) are separate
  cohorts linked via `related_cohorts`.
- Every reported result is one **Observation** whose `value` is a discriminated union. Pick the
  `value.type` that matches how the source reported it — do not coerce a rate into a proportion.
- Comparability is computed, not asserted: the build hashes
  `(measure_id, ascertainment, reference_period, denominator_basis, timepoint_band, value_type)`
  into a signature. Two observations are directly comparable iff their signatures match. You do
  not write the signature; you write the six fields honestly and the build does the rest.

---

## 2. To add a NEW cohort

1. **Verify the source.** Get the primary paper. Confirm design, N enrolled/analysed, follow-up,
   control group, and each number you intend to record, from the actual text/tables.
2. **Ensure the trigger exists** in `data/ref/pathogens.json`. If not, add it (stable
   `id`, `name`, `class` ∈ virus|bacterium|protozoan|vaccine|mixed|unknown, `vector`,
   `endemic_regions`).
3. **Create `data/cohorts/<slug>.json`.** Copy an existing cohort of a similar shape as a
   template (e.g. `katz-2009-mononucleosis.json` for a clean prospective cohort;
   `marburg-pacvs.json` for a biomarker/lab cohort; `vitae-survey.json` for a flagged survey).
   Fill the Core fields exactly per the schema enums. Required core:
   `schema_version:"2.0.0"`, `harmonisation_ruleset:"pais-harmony-v1"`, identity, trigger,
   design, `control_group`, `symptom_inventory_scope`, `last_verified` (YYYY-MM-DD),
   `verified_by`, `publications` (≥1), `observations`.
4. **Add each finding as an Observation** (see §3).
5. **Flag honestly** (see §5) if the cohort is a preprint, grey literature, patient-reported,
   uncontrolled, self-selected, or has an author conflict.
6. Run `--check`, fix errors, then the full build, then commit data + artifacts.

Slugs are permanent and never reused. Prefer `firstauthor-year-topic` or `place-trigger-year`.

---

## 3. To add an Observation

An observation records ONE result. Skeleton (see any cohort file for full examples):

```jsonc
{
  "id": "cohortslug-measure-timepoint",     // unique within the cohort, [a-z0-9-]
  "cohort_id": "<this cohort id>",
  "publication_id": "<one of this cohort's publications>",
  "schema_version": "2.0.0",
  "measure_id": "sym:fatigue",              // MUST exist in measures.json (§4)
  "measure_verbatim": "…exact wording from the paper…",
  "population": { "scope": "whole_cohort",  // whole_cohort | subgroup | stratum
                  "stratum": null,          // {variable,level} when not whole_cohort
                  "denominator_basis": "assessed_at_timepoint",
                  "n_assessed": 253 },       // integer OR a missingness sentinel
  "timing": { "timepoint_months": 6, "timepoint_band": "3-6mo",
              "reference_period": "current", "is_cumulative": false },
  "method": { "ascertainment": "structured_checklist", "instrument_id": null,
              "severity_threshold": null, "blinded_assessment": "not_reported" },
  "value": { "type": "proportion", "numerator": 39, "denominator": 253,
             "percent": 13, "ci": null, "precision": "exact" },
  "comparator": { "group": "none", "value": {"status":"not_applicable"}, "effect": null },
  "harmonised": null,
  "provenance": { "source_locator": "Table 2", "extracted_by": "you",
                  "extracted_on": "2026-07-20", "verified_by": "you",
                  "verified_on": "2026-07-20", "extraction_method": "manual" }
}
```

**Pick the right `value.type`** (each is validated separately on `type`):

| Source reports… | use `type` | key fields |
|---|---|---|
| “X% (n/N)” | `proportion` | numerator, denominator, percent, ci, precision |
| a raw count | `count` | n, denominator?, precision |
| events per person-time / incidence | `rate` | events, person_time, person_time_unit, rate, ci |
| mean ± SD of a measurement | `mean_sd` | mean, sd, n, ci, unit |
| median (IQR) | `median_iqr` | median, q1, q3, n |
| an adjusted effect with no raw arm data | `effect_only` | estimate, effect_type, ci, p_value, adjusted_for |
| before/after paired measurement | `paired_change` | baseline, followup, delta, sd_delta, n_pairs |
| present/absent | `presence` | boolean, basis |
| a narrative/mechanistic finding with no number | `qualitative` | text, n_supporting |
| a distribution over categories | `categorical_distribution` | categories[] |
| time-to-event / survival | `time_to_event` | median_time, unit, n_events, n_at_risk |

**`timepoint_band`** ∈ acute | 0-3mo | 3-6mo | 6-12mo | 12-24mo | 24mo+ | unspecified — derive it
from `timepoint_months` (the build in `migrate_v1_to_v2.py:band()` shows the exact cutoffs).

**The comparator is the point of the database.** If the cohort has a control group, record it:
`comparator.group` (mirror `control_group`), `comparator.value` (a value of the same type, or a
missingness sentinel), and `comparator.effect` (rr/or/hr/pr/rd/smd/beta + ci + p).

---

## 4. Measures — reuse before you invent

`measure_id` must already exist in `data/ref/measures.json`. Search it first. Only add a new
Measure when nothing fits, and follow the rules:

- Namespaced id: `sym:` symptom, `case-def:` case definition, `func:` functional outcome,
  `event:` discrete event, `lab:` analyte, `physio:` physiologic/tissue, `instr:` instrument
  score. Kebab-case after the colon.
- Map to a standard ontology: **HPO** for symptoms, **LOINC** for labs, **UCUM** for units,
  **SNOMED** where the others have no term. Do not invent identifiers where a standard exists.
- Keep `sym:fatigue` and `sym:post-exertional-malaise` as **separate concepts and never merge
  them**, even where a paper conflates them (`measure_verbatim` preserves the source wording).
- Put verbatim source phrasings into `synonyms[]`; add a `boundary_note` describing where this
  concept ends and the next begins.

---

## 5. Missingness and flags — the honesty machinery

**Typed missingness.** Any value slot takes a value or one sentinel object — never `null`:

```
{"status":"not_measured"}          the study never assessed this
{"status":"measured_not_reported"} assessed, number not published
{"status":"reported_as_zero"}      explicitly zero, not missing
{"status":"not_applicable"}
{"status":"unknown"}
```

`not_measured` vs `measured_not_reported` is the distinction that makes the gap matrices honest.
When a v2 field has no counterpart in the source, `measured_not_reported` is the correct default,
not a guess.

**Flags** (`flags[]` on the cohort) surface evidentiary caveats as badges everywhere the cohort
appears: `preprint`, `grey_literature`, `patient_reported`, `not_peer_reviewed`, `self_selected`,
`small_sample`, `author_conflict`, `unverified_source`, `single_timepoint`, `no_control`. Flag
generously — a flagged weak cohort is welcome (the database needs weak cohorts to show most
studies are weak); an unflagged one is a hazard.

**Publication types.** Peer-reviewed papers need a `doi` or `pmid`. A preprint usually has a DOI
(use it) plus `"type":"preprint"`. Grey literature (patient-org survey, report) with no DOI/PMID
is admitted only as `"type":"grey_literature"` (or `report`/`dataset`) with a `url`, and the
cohort must carry the `grey_literature` flag.

---

## 6. Layer-3 extensions — the pressure valve

For data nothing else reports (e.g. Ebola uveitis laterality, chikungunya DAS28 joint counts),
add a namespaced object under `extensions` (on the cohort or an observation):

```jsonc
"extensions": { "ebola": { "baseline_ocular_exam_n": 789, "uveitis_laterality": "bilateral" } }
```

- If `schema/ext/<ns>.schema.json` exists, CI validates the payload against it.
- If it does not, the data is preserved and flagged `unvalidated` — never rejected.
- A namespace used by **3+ cohorts** is a candidate for promotion into a proper Measure +
  observations. Do not let extensions become the default path for ordinary results.

---

## 7. Grouping by disease

Cohorts are grouped by trigger automatically: the build reads `pathogen_id`, renders a
"Cohorts by disease" section on the main page, and generates one page per disease at
`pais-cohorts/disease/<pathogen_id>.html`. You do not hand-maintain these — just set
`pathogen_id` correctly and add the pathogen to `pathogens.json`. Ordering is by pathogen class
(virus → bacterium → protozoan → vaccine → mixed) then name.

---

## 8. Expansion priorities (where the gaps are)

Consult the gap matrices on the live site; empty cells are the to-do list. As of this writing:

- **Autonomic and PEM measurement outside SARS-CoV-2** is almost absent — prioritise cohorts
  with tilt-table / NASA lean / validated PEM instruments for non-COVID triggers.
- **Acute-phase specimens** are missing for most triggers — cohorts that banked serum/PBMC
  during acute infection are the highest-value additions.
- **Directly-comparable fatigue estimates**: fatigue is measured by many cohorts but across
  ~12 different comparability signatures. Cohorts using a shared, validated instrument at a
  standard timepoint would create a comparable set worth reporting.
- **Under-represented triggers** with known PAIS literature: parvovirus B19, enterovirus/
  Coxsackie, Campylobacter/Salmonella enteric fever, post-polio, Q-fever (second cohort),
  dengue (second cohort), and additional PACVS biomarker cohorts.
- **Value-type coverage**: `mean_sd` (e.g. Moldofsky sleep-EEG parameters) and `paired_change`
  (exercise pre/post) are under-used — extracting those turns qualitative cards into data.

Batch verification is efficient: confirm each candidate's DOI/PMID and headline numbers first,
then author the files.

---

## 9. Checklist before you open a PR

- [ ] `python scripts/build_pais_cohorts.py --check` passes (0 errors).
- [ ] Every publication has a DOI or PMID, or is a flagged grey-literature URL source.
- [ ] Every observation has a `source_locator` and a real `measure_id`.
- [ ] Missing numbers are typed sentinels, not `null` and not guesses.
- [ ] Weak/preprint/grey/uncontrolled cohorts carry the appropriate `flags`.
- [ ] New measures use namespaced ids with HPO/LOINC/SNOMED/UCUM where a term exists.
- [ ] Regenerated artifacts committed (index JSON, both CSVs, `pais-cohorts.html`,
      `pais-cohorts/**`) — CI diffs them.
- [ ] `last_verified` / `verified_by` set on the cohort and provenance on each observation.

---

## 10. Explicitly out of scope

- Pooled prevalence estimates, meta-analysis, or any composite "quality"/"burden" score. The
  comparability signature says comparable or not, and shows why; a score invites argument about
  weights instead of about evidence.
- Patient-level rows or any PHI. This is a catalogue of study-level aggregates.
- Harmonising on ingest. Source values are the asset; harmonisation is a versioned, additive
  opinion (`harmonised` block, ruleset `pais-harmony-v1`) computed from source, never a mutation
  of it.
- Editing `data/v1/**` (frozen) or rewriting history of published cohort slugs/URLs.
