# Agent spec — Phase 6 module: incidence associations (genes, expression, exposures)

**Status:** spec module — appended to the agent spec after Phases 1–5. Nothing in this
module is implemented yet.
**Audience:** a coding agent with shell + git access, building on Phases 1–5.
**Reuses:** the Phase 1–5 QA framework — the numbered acceptance-check table (this module
continues it with checks 13–19), fixture-based unit tests, and one CI job.

---

## Why this module exists

The disease pages built in Phases 1–5 already carry an alterations table whose rows have
`direction` and `frequency` keys — `disease_pipeline/output/web_export.py` maps
`alt.direction` → `direction_label` and passes through `frequency_label` / `frequency_pct` —
but in the current data snapshot **0 of 11,288 alteration records across 107 pages carry a
value** for either key. The keys are present and `null`. A table of unlabelled rows is not
evidence.

Phase 6 exists so that **the sign of an association survives ingestion**: it is derived
once, centrally, from the effect estimate; it is required (rows without it are quarantined,
never rendered with "—"); and protective effects are never dropped, sign-flipped, or merged
into risk.

## Repo integration notes (this repository)

Phase 6 lands in **`disease_pipeline/`** — the generator behind `disease-intelligence/*.html`.

| Phase 6 deliverable | Concrete location in this repo |
|---|---|
| `incidence_associations` collection, per disease | New top-level array in `data/disease-intelligence/<slug>.json` |
| Schema migration + validation | `disease_intelligence.schema.json` — the top level today requires `schema_version, slug, id, condition, identifiers, page, summary, categories, filters, alterations, therapeutics`. Add the array to `properties` and `required`; bump `schema_version` (currently `1.1.0`) |
| Trait-map seed key | `identifiers.mondo_id` — present in 100 of the 107 built disease JSONs; the seven exceptions are listed under "Human pass required" below. Key the `MONDO → EFO → GWAS traits` table on `mondo_id` |
| Three rendered sections + new stat cards | `disease_pipeline/output/generate_html.py` — already emits `overview-card` / `stat-grid` / `stat-cell` stat cells and `<table class="data-table" id="alterations-table">` |
| Direction rendering (text-first, non-colour cue) | Reuse `DIRECTION_LABELS` / `direction_label` from `disease_pipeline/output/web_export.py` so sign wording matches the alterations table |
| CSV / JSON export | `disease_pipeline/output/web_export.py`, `disease_pipeline/export_web.py`; published by `disease_pipeline/publish_site.py` |
| Genetics / expression / MR connectors | Reuse the genetics explorer instead of re-implementing: `genetics_pipeline/adapters/gwas_catalog.py`, `ensembl.py`, `ols.py`, `europepmc.py`; flat-file conventions from `data/genetics/*.csv` |
| Treatment-leakage check (§6.5 #16) | Sources to keep *out* of the three new sections: `disease_pipeline/clinicaltrials_client.py`, `disease_pipeline/adapters/clinical.py`, `disease_pipeline/adapters/clinical_evidence.py` |
| CI job for checks 13–19 | `.github/workflows/` holds `validate-genetics.yml`, `validate-cohorts.yml` and three scheduled/deploy jobs — **no disease-intelligence validation job exists**. Follow `scripts/validate_genetics.py` → `genetics_pipeline/validate.py` (schema + referential integrity + a rejected malformed fixture), in a new workflow or by extending that one |

### Phase-numbering caveat (read before renumbering anything)

The DI pipeline already labels internal stages by phase:
`disease_pipeline/adapters/clinical_evidence.py` opens with
`"""Phase 6 — Clinical trial registry + published literature evidence per agent."""`,
`main.py` documents `--max-evidence-drugs` as "(phase 6)", and built JSONs carry
`summary.pipeline_phase` values of `6`, `7` and `8`. If this module's "Phase 6" shares that
numbering it must be renumbered to avoid ambiguity; otherwise keep the agent-spec phase
numbers separate, name everything after the `incidence_associations` key rather than the
phase number, and leave `summary.pipeline_phase` coherent.

## Prerequisite gaps to close before §6.4 can be satisfied

1. **Phase 3 table stack.** §6.4 gives every new table "the Phase 3 table stack
   (search/sort/export/sticky header)". The DI renderer today emits plain `.data-table`
   markup with category filter chips and the opt-in `hide-alterations-without-value`
   toggle; the only sticky element is the top nav. There is no per-table search, sort,
   export or sticky header. Land that stack (or confirm it is inherited) before wiring
   §6.4, and preserve the existing
   `#alterations.hide-alterations-without-value tbody tr.alt-no-value{display:none}`
   contract and the `display=''`-based filter chips when table markup changes.
2. **Test harness.** There is no pytest suite or CI job under `disease_pipeline/` today
   (`requirements-disease-pipeline.txt` carries no test dependency; validation is via
   `disease_pipeline/audit_*.py` and ad-hoc scripts). Checks 13–19 are fixture-based, so
   Phase 5's harness must be extended to this pipeline, or the checks must run inside the
   genetics validate job.
3. **`TODO(curator)` convention.** §6.6 defers the `MONDO → EFO` trait maps and the
   per-disease exposure umbrella-review seed files to a human pass, marked `TODO(curator)`
   rather than model-generated. That marker appears nowhere in this repo yet, so this module
   introduces it: keep the markers machine-greppable, and fail the build while any remain in
   a file the renderer reads.

---

## Phase 6 — Incidence associations: genes, expression, exposures

### Goal

Every disease page gains three evidence-typed sections linking entities to **disease incidence** (not progression, not treatment response), each row carrying an explicit **direction** (risk ↑ / protective ↓) and effect estimate. Negative associations are first-class citizens: they are never dropped, sign-flipped, or merged away.

### 6.1 Data model

One unified `incidence_associations` collection per disease; `entity_type` drives section rendering.

```json
{
  "entity_type": "gene | expression | exposure",
  "name": "STRING",
  "id": "ENSG… | RS… | CHEBI… | MESH…",
  "direction": "risk | protective",
  "effect": {
    "estimate": 1.18,
    "ci_low": 1.09,
    "ci_high": 1.28,
    "unit": "OR | beta | log2FC | HR | RR",
    "p_value": 4.2e-9
  },
  "evidence_type": "GWAS | fine_mapping | colocalization | mendelian_randomization | differential_expression | eQTL | observational | umbrella_review | curated_literature",
  "mapping_mechanism": "nearest_gene | eQTL | chromatin_interaction | coding_variant | direct_measurement",
  "population": "European | East Asian | … | multi",
  "tissue": "STRING | null",
  "source": "GWAS_Catalog | FinnGen | OpenTargets_Genetics | MR_EvE | GTEx | CTD | …",
  "source_ref": "URL or accession",
  "citation": "PMID or DOI"
}
```

Validation rules enforced at ingest:

- `direction` is **required and non-null**. If a source provides no sign, the row is quarantined to a review queue file (`_unsigned_associations.json`), never rendered with "—".
- Sign is derived once, centrally, from the estimate: `OR/RR/HR > 1` or `beta/log2FC > 0` → `risk`; below → `protective`. Never trust a text field from upstream.
- Confidence intervals crossing 1 (or 0 for beta) must render an explicit "CI includes null" badge and cannot be labeled risk or protective in derived copy — they stay in the table with a `not_significant` flag.

### 6.2 Source connectors

| Section | Source | What to pull | Direction available |
|---|---|---|---|
| Genes | Open Targets Genetics, GWAS Catalog | Lead SNPs per trait, mapped genes, beta/OR | Yes |
| Genes | FinnGen, Neale UK Biobank | Replication-grade associations | Yes |
| Genes | MR-EvE / TwoSampleMR results | Causal gene–disease estimates | Yes |
| Expression | GEO/sclabel-derived case-control datasets, PsychENCODE or tissue-appropriate consortia | log2FC cases vs controls, tissue label | Yes |
| Expression | GTEx / Human Protein Atlas | Baseline tissue expression (context only, not association) | n/a — render as context column |
| Exposures | MR-EvE exposure–outcome MR | Risk/protective exposures, bidirectional check | Yes |
| Exposures | CTD (Comparative Toxicogenomics Database) | Curated chemical/environment–disease links | Partial — infer from marker (increases/decreases); quarantine when absent |
| Exposures | Umbrella reviews / GBD risk factors (per-disease curated file) | Effect direction + citation | Yes |

Trait mapping: build a per-disease `MONDO → EFO → GWAS traits` alias table (manual seed file, `TODO(curator)` where ambiguous). A trait map mismatch must fail the build loudly, not silently skip.

Explicit exclusions:

- ClinicalTrials.gov interventions, arms, and outcome measures must **never** enter these sections (they are treatments/outcomes, not incidence exposures) — enforce with an integration test.
- Progression/severity/-survival endpoints are out of scope; filter to incidence/onset phenotypes at ingest.

### 6.3 Deduplication and evidence tiers

- Merge rows for the same gene across GWAS sources: keep per-source estimates in an expandable row detail, show strongest-source estimate on the main row, and display a "replicated in N sources" badge.
- Tiering (reuse existing badge system, now sign-aware):
  - **Strong**: GWAS-significant + MR or colocalization support
  - **Moderate**: GWAS-significant, single source
  - **Emerging**: candidate-gene / curated literature only
- For genes, always display the `mapping_mechanism` (nearest gene ≠ causal gene — this distinction is a credibility requirement, not decoration).

### 6.4 Rendering

Three new sections, each with the Phase 3 table stack (search/sort/export/sticky header):

1. **Genetic associations** — columns: Gene, Direction, Estimate (95% CI), Evidence tier, Mapping mechanism, Population, Sources, Links.
2. **Gene expression** — columns: Gene, Tissue, Direction (up/down in cases), log2FC, Evidence type, Dataset, Citation. Include one line stating whether expression evidence is causal (eQTL/coloc) or correlational.
3. **Exposures (risk & protective)** — columns: Exposure, Direction, Estimate, Evidence type (MR vs observational, visually distinguished), Population, Citation. Add a fixed disclaimer under the section header: "Associations, including MR results, are not clinical recommendations."

Direction rendering: text-first ("Risk ↑" / "Protective ↓"), with a non-color secondary cue per Phase 4 accessibility rules. Never color alone.

New stat cards in the overview: `Genetic associations (risk/protective counts)`, `Expression evidence`, `Exposures risk N · protective N`. If protective count is 0 after ingest, render "None identified" per rule 1.5 — never hide the category, since absence of evidence is itself informative.

### 6.5 QA / acceptance criteria (extend the CI table)

| # | Check | Pass condition |
|---|---|---|
| 13 | Direction coverage | 100% of rendered incidence rows have non-null direction or the `not_significant` flag |
| 14 | Sign sanity | Unit test: ingest fixtures with OR 1.2, 0.8, beta +0.3, −0.1, log2FC ±2 → directions render correctly |
| 15 | Protective survival | Count of protective rows in rendered HTML equals count in source data (nothing dropped/f sign-flipped in transform) |
| 16 | Treatment leakage | No ClinicalTrials.gov-sourced entity in the three new sections |
| 17 | Quarantine | `_unsigned_associations.json` exists and every entry has a source ref |
| 18 | Exposure tiering | MR-derived and observational exposures are distinguishable in rendered output |
| 19 | Context vs association | Baseline-expression (GTEx/HPA) data appears only as context, never as a directioned association row |

### 6.6 Deliverables

- Three ingest connectors (genetics, expression, exposures) + the `MONDO→EFO` trait-map seed files per disease.
- Schema migration: `incidence_associations` collection with validation.
- Rendered sections + updated stat cards + exported CSV/JSON endpoints.
- Fixture-based unit tests for checks 13–19, wired into the Phase 5 CI job.

One scope note: the agent can build all connectors, transforms, and rendering automatically, but the `MONDO → EFO` trait maps and the per-disease exposure umbrella-review seed files need a human pass — same pattern as before, `TODO(curator)` markers rather than model-generated facts.

---

## Human pass required (not model-generated)

Per §6.6, two artifacts are curator work and carry `TODO(curator)` markers:

1. **`MONDO → EFO → GWAS traits` trait maps.** Every seed file must key on
   `identifiers.mondo_id`, which is present in 100 of the 107 built disease JSONs in
   `data/disease-intelligence/`. These seven have no MONDO id today, so a trait map cannot
   key on one and the ingest must either fail loudly (§6.2) or quarantine the disease until
   the id is filled: `low-back-pain`, `mastocytosis-with-kit-d816v-mutation`, `obesity`,
   `psoriasis-vulgaris`, `sepsis`, `sjögrens-syndrome`, `tinnitus`.
2. **Per-disease exposure umbrella-review seed files** (effect direction + citation per
   exposure). GBD risk factors and umbrella reviews supply the direction; a model must not
   infer it.

## Open questions for the curator

- Trait-map granularity: one alias table per disease, or one global `MONDO → EFO` table plus
  a per-disease trait allow-list?
- Quarantine lifecycle: where does `_unsigned_associations.json` live relative to
  `data/disease-intelligence/` — committed (so the review diffs are auditable) or regenerated
  per build (gitignored)? And does check 17 pass when the quarantine file is legitimately
  empty?
- Wording: do "Risk ↑ / Protective ↓" replace the `DIRECTION_LABELS` strings already used by
  the alterations table, or sit alongside them? Two vocabularies for one concept will drift.
- `not_significant` rows: do they count toward the risk/protective counts on the new stat
  cards, or into a third "unresolved" count? §6.4 implies the former; check 13 allows either.
- Expression evidence floor: is any case-control dataset admissible, or is a minimum n /
  platform / tissue-match required before a `differential_expression` row may render?

