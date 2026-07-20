# Build spec: post-infectious syndrome (PAIS) cohort database

Instructions for a coding agent. Assumes a basic page already exists.

---

## 0. What this is, and what it is not

This catalogues **cohorts**, not patients. Each record is a study population that was followed for post-infectious outcomes. There is no personal health information anywhere in this system, no login, no patient-facing data entry.

If the intent is instead a patient registry, stop and flag it — that is a different build with IRB, consent, PHI handling, and hosting-jurisdiction requirements, and none of this spec applies.

**The problem it solves:** post-infectious syndrome research is scattered across cohorts that used different case definitions, instruments, timepoints, and control groups, which makes cross-syndrome comparison impossible and hides where the evidence gaps are. This database makes those differences machine-readable.

---

## 1. The single most important modelling decision

**The unit of record is the COHORT, not the publication.**

One cohort produces many papers. TELECHIK on Réunion produced at least two well-known analyses years apart. Q fever outbreak cohorts have been re-analysed repeatedly across decades. If you model papers as records, the database will overstate how much independent evidence exists — which is the exact error the field already makes.

So: `Cohort` 1—N `Publication`, and `Cohort` 1—N `Finding`. Findings attach to a publication AND to a cohort.

---

## 2. Data model

### 2.1 `Cohort`

**Identity**
- `id` — stable slug, never reused (e.g. `telechik-reunion`)
- `name`, `aliases[]`
- `outbreak_event` — nullable named event (e.g. `Bergen giardiasis 2004`, `Réunion chikungunya 2005-06`)

**Trigger**
- `pathogen_id` → `Pathogen` reference table
- `pathogen_class` — enum: `virus | bacterium | protozoan | vaccine | mixed | unknown`
- `exposure_ascertainment` — enum: `pcr | serology | culture | clinical_diagnosis | registry_code | self_report | mixed | not_reported`

**Design — this section is the point of the database**
- `design` — enum: `prospective_inception | prospective_non_inception | retrospective_cohort | cross_sectional | case_control | registry_linkage | self_controlled | survey`
- `denominator_defined` — enum: `yes | partial | no | unclear`
- `denominator_method` — free text, required when `denominator_defined != no`
- `recruitment_source` — enum: `community | population_registry | hospital | outpatient_clinic | occupational | household_contacts | self_referral | patient_organisation | mixed`
- `time_zero_definition` — free text
- `time_zero_precision` — enum: `exact_date | week | month | quarter | year | undefined`
- `control_group` — enum: `none | unexposed_matched | unexposed_unmatched | seronegative_contacts | household_contacts | other_disease | self_control | healthy_convenience`
- `control_matching_variables[]`

**Size and attrition**
- `n_source_population` (nullable)
- `n_enrolled`, `n_analysed`
- `followups[]` — array of `{ months: number, n_assessed: number, n_lost: number }`
- `max_followup_months`

**Measurement**
- `instruments[]` → `Instrument` reference table
- `case_definition` — enum: `fukuda_1994 | canadian_consensus | iom_nam_2015 | who_pcc_2021 | nice_ng188 | chalder_threshold | author_defined | none`
- `pem_assessed` — enum: `yes_validated_instrument | yes_single_item | no | unclear`
- `objective_measures[]` — enum multi: `cpet_single_day | cpet_two_day | tilt_table | nasa_lean | nirs | muscle_biopsy | other_biopsy | imaging | actigraphy | polysomnography | lab_panel | none`

**Biospecimens — the field that makes this useful rather than bibliographic**
- `specimens_collected` — boolean
- `specimen_types[]` — `serum | plasma | pbmc | whole_blood | stool | saliva | urine | csf | muscle_tissue | synovial | other`
- `acute_phase_specimens` — enum: `yes | no | unclear` (drawn during acute infection, before outcome known)
- `storage` — free text (e.g. `-80C`, `LN2 vapour`)
- `biobank_status` — enum: `active | archived | destroyed | unknown`
- `consent_future_use` — enum: `broad | disease_specific | none | unknown`
- `external_access` — enum: `open_application | collaboration_only | closed | unknown`
- `contact` — free text, public contact only, no personal emails unless already published

**Provenance and integrity**
- `registration_id` — NCT / ISRCTN / DRKS / other, nullable
- `funders[]`, `conflicts` — free text
- `data_availability` — free text
- `notes` — caveats, known criticisms, replication status

### 2.2 `Finding`

One extracted quantitative result. Many per cohort.

- `id`, `cohort_id`, `publication_id`
- `outcome` — controlled vocabulary: `chronic_fatigue | mecfs_criteria_met | pem | arthralgia | myalgia | joint_swelling | neurocognitive | sleep_disturbance | orthostatic_intolerance | ibs | depression | anxiety | ptsd | qol_impairment | unable_to_work | recovered | other`
- `outcome_verbatim` — exactly as the paper worded it
- `instrument_id` — nullable
- `timepoint_months`
- `n_with_outcome`, `n_assessed`, `percent`
- `ci_low`, `ci_high`, `ci_method` (nullable)
- `comparator_percent`, `comparator_n` (nullable)
- `effect_estimate`, `effect_type` — enum: `rr | or | hr | prevalence_ratio | risk_difference | none`
- `p_value` (nullable)
- `source_locator` — required. Where in the paper this came from: `Table 2`, `p. 634`, `Fig 3B`.

### 2.3 `Publication`

- `id`, `cohort_id`, `title`, `authors`, `year`, `journal`
- `doi` and/or `pmid` — **at least one required**
- `open_access` — boolean
- `is_primary_cohort_paper` — boolean

### 2.4 Reference tables

`Pathogen` (name, taxon, class, vector, endemic regions), `Instrument` (name, abbreviation, domain measured, validated_for).

---

## 3. Data hygiene rules — enforce these in schema, not in convention

1. **`null`, `not_reported`, and `not_applicable` are three different things.** Never collapse them. Use an explicit enum sentinel, not `null`, for "the paper does not say."
2. **Every `Finding` requires a `source_locator`.** A number without a table reference is not verifiable and should fail validation.
3. **Every `Publication` requires a DOI or PMID**, format-validated by regex.
4. **Controlled vocabularies are closed enums.** Free text only in fields explicitly designated free text. If a value doesn't fit, the enum gets extended by a schema change, not by an ad-hoc string.
5. **No computed composite "quality score."** Show the design fields and let users filter. A single score hides the tradeoffs and invites arguments about weighting.
6. **Percentages are stored as reported, not recalculated**, with `n_with_outcome` and `n_assessed` alongside so recalculation is possible and discrepancies visible.

---

## 4. Storage and contribution model

Recommended: **content as versioned flat files, not a database server.**

- One YAML or JSON file per cohort in `/data/cohorts/`, reference tables in `/data/ref/`
- JSON Schema (or Zod) validation in CI — a PR that breaks schema fails the build
- Build step compiles the flat files into a single static JSON index the frontend loads
- Contributions arrive as pull requests, which gives free provenance, diffs, review, and attribution

Rationale: this dataset is hundreds of records, not millions. A static build removes the backend, the hosting cost, the auth surface, and the backup problem, while making every change to every value permanently auditable. That auditability is a research requirement, not a nice-to-have.

Move to Postgres only if you later add per-user annotation or submissions from non-technical contributors via a form.

---

## 5. Views to build, in priority order

**1. Cohort table (default view).**
Sortable, filterable. Columns: name, pathogen, design, N, max follow-up, control group, denominator defined, specimens banked. Filters as faceted checkboxes on all enum fields.

**2. Cohort detail page.**
All fields grouped by the sections above. Findings table. Publications list. Prominent, honest display of design limitations rather than buried.

**3. Comparison view.**
Select 2–6 cohorts, render side-by-side on aligned rows. This is what makes the incomparability of the literature visible at a glance.

**4. Findings explorer.**
Filter by outcome and timepoint across all cohorts. Render as a forest-style plot: prevalence with CI, grouped by pathogen, ordered by timepoint. Do not pool. Display only — no meta-analysis, because the case definitions are not harmonised and pooling them would repeat the field's mistake.

**5. Gap matrix.**
Pathogen × design-quality grid. Cell contents = count of cohorts. Empty cells are the product: they show, visually, where no adequate study exists. Add a second matrix of pathogen × `acute_phase_specimens`.

**6. Specimen availability view.**
Filter to cohorts with banked specimens and non-closed external access. This is the view that turns the site from a bibliography into infrastructure.

---

## 6. Export and interoperability

- Per-cohort and bulk export: JSON, CSV, BibTeX for the publication set
- Stable permalink per cohort and per finding
- `schema.org/Dataset` JSON-LD on cohort pages
- Public, versioned schema document at a fixed URL
- CC BY 4.0 on the data, stated in the repo and in the footer

---

## 7. Explicitly out of scope for v1

- User accounts, comments, ratings
- Automated LLM extraction writing directly to records. Extraction assistance is fine; **every field must be human-verified against the source before merge**, and the PR must show the reviewer. An unverified auto-extracted research database is worse than no database.
- Meta-analysis or pooled estimates
- Patient-facing symptom checkers or anything resembling clinical advice

---

## 8. Seed data

Start with roughly 25–30 cohorts spanning the pathogen range, so the gap matrix is meaningful on day one. Prioritise cohorts that are strong on design, because they set the schema's ceiling: prospective inception cohorts with real control groups, and any cohort with banked acute-phase specimens.

Deliberately include weak cohorts too. A database that only contains good studies cannot demonstrate that most studies are weak, which is the argument the site exists to support.

---

## 9. Acceptance criteria

- [ ] Schema validation runs in CI and blocks merge on failure
- [ ] Every publication record has a DOI or PMID
- [ ] Every finding has a source locator
- [ ] `not_reported` is distinguishable from missing everywhere in the UI, not silently blank
- [ ] Gap matrix renders empty cells visibly rather than omitting rows
- [ ] Full dataset downloadable in one click as JSON and CSV
- [ ] Site functions with JavaScript disabled for at least the cohort table and detail pages
- [ ] No analytics that track individual users; no third-party fonts or scripts
