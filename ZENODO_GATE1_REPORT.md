# Zenodo deposit: Gate 1 report (2026-10-25)

Companion to `ZENODO_DEPOSIT_AGENT_TASK.md`. Produced from the local checkout at commit `9ea175bda`, read-only. Nothing was built or deposited.

## Per-record inventory

| ID | Files | Size | Not in git | Uncommitted local changes | Schema check | Verdict |
|---|---|---|---|---|---|---|
| R1 PAIS cohorts | 53 | 0.8 MB | 0 | 0 | 32/32 cohort files pass | **Ready** |
| R2 Biomarker atlases | 45 (38 after exclusions) | 2.7 MB | 0 | 4 | 25 pass; 7 fail because they are not atlas files | **Ready after narrowing the allow-list** |
| R3 Post-viral literature | 10 | 1.1 MB | 0 | 0 | 8/8 fail (`schema_version` missing) | **Needs transform and a schema fix** |
| R4 Trials + ontology | 3 | 9.0 MB | 0 | 0 | no schema | **Ready** |
| R5 Repurposing evidence | 10 | 2.1 MB | 4 | 2 | no schema | **Blocked** (licence, quality gate, junk files) |
| R6 Disease intelligence | 108 | 103.1 MB | 1 | 95 | 0/107 pass (version 1.1.0 data vs 1.0.0 schema) | **Blocked** (licence, schema, uncommitted data) |
| R7 Medical Freedom Map | 173 | 25.8 MB | 0 | 0 | no schema | **Hold** (owner decision) |

## Findings

**R1:** No identifying data found. Rows are cohort-level aggregates from published studies (enrolled and analysed counts, design, follow-up). The longest verbatim quote is 153 characters, a single sentence (`pais-observations.csv`, `measure_verbatim`). No secrets or local paths.

**R2:** `data/biomarkers/` contains 7 files that are not atlases. Exclude them: `agent-discovery.json`, `commercial-links.json`, `consumable-links.json`, `intervention-links.json`, `outcome-ontology.json`, `search-index.json`, `trial-links.json`. Two of them are commercial listings, which are on the never-deposit list. Four atlas files have uncommitted local changes, so commit them before building the bundle.

**R3:** All 537 studies carry a stored PubMed abstract. The transform in §2.3 of the task file is required. The schema file `post-viral-illness.schema.json` does not describe these per-condition files (it requires `schema_version`, which they lack). Either write a schema for the deposited (abstract-free) shape or ship without one and document the fields in the README.

**R4:** `outcomes-cache.json` holds registry outcome measures for 635 trials, copied from ClinicalTrials.gov. It is registry content, not an opaque API dump, so it is fine to include. Rename it in the bundle (e.g. `trial-outcomes.json`).

**R5:**
- Untracked junk is caught by the allow-list: `data/agent-pipeline/logs/api_calls.log` and `data/agent-pipeline/results/il6-test.json` (a test run; its only "API_KEY" hit is a log message saying a key was not set, not a secret). Exclude `logs/` and `results/` as well as `cache/`.
- `explorer-stats.json` and `explorer-validation.json` are not in git. Commit them or drop them.
- ChEMBL-derived fields: `chembl_id`, `mechanisms`, `Proposed Mechanism`, `chembl_approved` counts, `merged_with_chembl_id`.
- Still blocked on the pair quality gate (§2.4).

**R6:**
- **ChEMBL content is substantial, not just identifiers:** 56,700 `max_phase` values and 8,861 `mechanism` values copied from ChEMBL, plus 39,036 ChEMBL IDs. Stripping them (licence option b) would remove the clinical-phase data the site depends on. ChEMBL's CC BY-SA 3.0 allows adaptations under later versions with the same elements, so **CC BY-SA 4.0 for R5 and R6 is the straightforward option** (option a).
- All 107 files declare `schema_version` 1.1.0 while `disease_intelligence.schema.json` pins 1.0.0. Update the schema to 1.1.0 and re-validate before deposit.
- 95 of 108 files have uncommitted local changes (about 121k insertions and 164k deletions across the data folders). The GitHub copy is older than the local one. Commit first so the bundle's commit SHA is meaningful.
- An untracked file has a non-ASCII name: `sjögrens-syndrome.json`. Rename it to ASCII or exclude it.

**R7 (if the owner approves it later):** exclude `med-freedom-map/data/verification/.page-cache/` (2,228 cached copies of third-party web pages; copyright) and scrub the local Windows path in `ACCESS_BRIEF.md`.

## Decisions needed from the owner

1. **Confirm the record list.** Recommended first batch: R1, R2, R4, then R3 once transformed.
2. **Licence for R5 and R6** (GATE 2). Recommendation: CC BY-SA 4.0.
3. **Commit the local data changes** (R2, R5, R6) so bundles can cite a commit.
4. **Creators per record** (GATE 3).
5. **Zenodo tokens** (sandbox and production) in the environment of whichever session continues.

## Tooling note

`jsonschema` is not installed in the system Python. Validation above used a scratch install. Add it to `requirements.txt` or install it before rerunning.
