# PAIS Cohort Database — handoff / context for the next coding agent

You are taking over the **PAIS Cohort Database** inside the `research-tracker` repo. This file
is your entry point: read it, then the four docs it points to. It reflects the state at commit
`c82cbde` (main, in sync with origin).

---

## 0. Thirty-second summary

A catalogue of **cohorts** (followed study populations) for **infection- and exposure-associated
chronic conditions** — post-viral syndromes, ME/CFS, Long COVID, PACVS, post-treatment Lyme,
post-enteric IBS, Gulf War Illness, etc. It is a **static, flat-file, build-validated** dataset
rendered to plain HTML and served from GitHub Pages at
**https://research.opensourcemed.info/pais-cohorts.html**.

- **30 cohorts · 69 observations · 35 publications · 39 measures · 19 triggers** (as of `c82cbde`).
- One JSON file per cohort in `data/cohorts/`. A Python build validates them against a JSON
  Schema, compiles an index, and renders every page. CI blocks merges that break the schema or
  leave the built artifacts stale.
- Data model is **v2**: every reported result is one polymorphic `Observation` (discriminated-union
  `value`), keyed to a unified Measure registry, with typed missingness and comparability
  signatures. There is no `Finding`/`SymptomFinding` any more (those were v1/v1.1).

---

## 1. Read these first (in order)

| Doc | What it is | When you need it |
|---|---|---|
| `pais-cohort-db-HANDOFF.md` | **this file** — orientation, state, gotchas | now |
| `pais-cohort-db-expansion-guide.md` | **how to add** a cohort/observation: schema, value-type table, measures, flags, extensions, PR checklist | every time you author data |
| `pais-cohort-db-sourcing-worklist.md` | **what to add** — the prioritised backlog of diseases/cohorts (ME/CFS, Lyme, Gulf War, …) with candidate studies and the current-inventory table | to pick the next batch |
| `pais-cohort-db-v2-heterogeneous-schema.md` | the design spec for the v2 Observation model (rationale) | to understand *why* the schema is shaped this way |
| `pais-cohort-db-v1.1-symptoms-spec.md` | historical v1.1 spec (superseded by v2) | rarely; context only |

The two you will live in are the **expansion guide** (mechanics) and the **sourcing worklist**
(backlog). The worklist has a suggested phase order and a "what is already in the database"
inventory — check it before authoring so you don't add a duplicate cohort.

---

## 2. The files that matter

```
data/pais-cohort.schema.json      v2 JSON Schema — the structural source of truth
data/cohorts/<id>.json            one cohort per file (30 of them) ← you add/edit these
data/ref/pathogens.json           trigger registry (19; incl. unknown-trigger, mixed-infectious, gulf-war-exposures)
data/ref/measures.json            unified Measure registry (39; sym:/case-def:/func:/event:/lab:/physio:)
data/ref/instruments.json         measurement instruments (DSQ, Bell, COMPASS-31, SF-36, …)
data/ref/symptoms.json            LEGACY v1.1 table — superseded by measures.json; do not use for new work
schema/ext/<ns>.schema.json       Layer-3 extension schemas (ebola.schema.json exists)
scripts/build_pais_cohorts.py     validate + compile + render (this IS the CI gate)
scripts/migrate_v1_to_v2.py       one-off v1→v2 migration (reference only; do not re-run)
scripts/build_site_seo.py         site-wide SEO meta + sitemap (invoked at the tail of the build)
.github/workflows/validate-cohorts.yml   CI: schema + xref + rebuild-in-sync + v1 snapshot parse
data/v1/                          FROZEN v1.1 snapshot at stable URLs — never edit
```

**Generated (commit them, never hand-edit):** `data/pais-cohorts-index.json`,
`data/pais-cohorts.csv`, `data/pais-observations.csv`, `pais-cohorts.html`, `pais-cohorts/**`
(detail + `disease/` pages).

**Do NOT confuse** `data/cohorts/` (the PAIS database) with the many other `data/*.json` files
(`long-covid.json`, `me-cfs.json`, `gulf-war-illness.json`, `pacvs.json`, …). Those belong to a
*separate* disease-intelligence site in the same repo and are unrelated to this task.

---

## 3. The build/validate/deploy loop

```bash
python scripts/build_pais_cohorts.py --check   # validate only (schema + cross-refs + extensions). Fast. Use while iterating.
python scripts/build_pais_cohorts.py           # validate + regenerate ALL artifacts (also runs build_site_seo.py at the end)
```

- A non-zero exit = it will not merge. `--check` is exactly the first CI step.
- The **full build is deterministic**; the SEO step is **idempotent** (re-runs make no changes),
  so committed artifacts stay in sync. CI diffs `data/pais-cohorts-index.json`,
  both CSVs, `pais-cohorts.html`, and `pais-cohorts/**` and fails if they are stale — so always
  run the full build and commit the regenerated files with your data.
- **Deploy is automatic:** pushing to `main` triggers `.github/workflows/deploy-pages.yml`
  (GitHub Pages, `path: .`). No build step runs on Pages — it serves the committed files. So the
  committed HTML/JSON *is* the site. Pages usually goes live within ~10–30s of push.
- After pushing, verify live, e.g.:
  `curl -s https://research.opensourcemed.info/data/pais-cohorts-index.json | python -c "import json,sys;print(len(json.load(sys.stdin)['cohorts']))"`

---

## 4. The data model in one screen (details: expansion guide + v2 spec)

- **Cohort (Layer 1 Core):** identity, trigger (`pathogen_id`→registry, `pathogen_class` enum),
  design, denominator, control group, size/attrition, biospecimens, provenance, `flags[]`,
  `related_cohorts[]`, `publications[]`, `observations[]`. `schema_version:"2.0.0"`,
  `harmonisation_ruleset:"pais-harmony-v1"`.
- **Observation (Layer 2):** one reported result. `measure_id` (→ registry), `measure_verbatim`
  (never normalised), `population`/`timing`/`method` blocks, a discriminated-union **`value`**
  (proportion | count | rate | mean_sd | median_iqr | geometric_mean | categorical_distribution |
  time_to_event | effect_only | paired_change | presence | qualitative), a `comparator`, and
  per-observation `provenance`.
- **Typed missingness (never `null`, never a guess):** `{"status": "not_measured" |
  "measured_not_reported" | "reported_as_zero" | "not_applicable" | "unknown"}`. The
  `not_measured` vs `measured_not_reported` distinction is what makes the gap matrices honest.
- **Measures:** namespaced ids, HPO/LOINC/SNOMED/UCUM mapped. Reuse before inventing. Keep
  `sym:fatigue` and `sym:post-exertional-malaise` as separate concepts, always.
- **Comparability signature:** the build hashes `(measure_id, ascertainment, reference_period,
  denominator_basis, timepoint_band, value_type)`. Two observations are directly comparable iff
  signatures match. You write the six fields honestly; the build computes the rest and renders the
  "comparable sets" view. This is the site's headline idea.
- **Flags:** honest caveats rendered as badges (`preprint`, `grey_literature`, `patient_reported`,
  `self_selected`, `no_control`, `small_sample`, `author_conflict`, `unverified_source`, …).
  Flag weak/preprint/grey cohorts generously — they are welcome, but must be labelled.
- **Extensions (Layer 3):** namespaced objects for data nothing else reports; validated if
  `schema/ext/<ns>.schema.json` exists, else preserved and flagged unvalidated — never rejected.

---

## 5. The two hard rules (do not break these)

1. **Verify every field against the primary source before committing.** Confirm the DOI/PMID and
   every number from the actual paper/tables. The study names in the worklist are *leads to
   verify*, not citations to copy.
2. **Never fabricate** a number, denominator, or identifier. Unknown → a typed missingness
   sentinel. A grey-literature source with no DOI/PMID → a URL-only `type:grey_literature`
   publication plus the `grey_literature` flag (see expansion guide §5).

Publications need a `doi` or `pmid` (preprints keep their DOI + `type:preprint`); only
grey-literature/report/dataset types may be URL-only.

---

## 6. Where things stand / what's next

- **Done recently:** v1→v2 migration; comparable-set + gap-matrix + by-disease views; per-disease
  pages; flags + grey-literature/preprint publication types; SEO pass; first ME/CFS cohorts
  (UK ME/CFS Biobank, NIH Walitt/Nath) + NIH RECOVER; **`environmental` trigger class** generalised
  in (Gulf War and other exposure syndromes are now unblocked — `gulf-war-exposures` trigger
  exists).
- **Backlog = the sourcing worklist.** Follow its phase order. Immediate high-value targets:
  finish ME/CFS (MCAM, DePaul/Jason; add DSQ-based observations), Long COVID controls (Zurich,
  a VA/administrative cohort), post-sepsis/PICS (Iwashyna, BRAIN-ICU), Lyme extensions (attach
  Klempner/Wormser as needed), then Gulf War (Steele/Kansas, Millennium — trigger class is ready),
  EBV→MS (Bjornevik — showcases `event:`/`effect_only` at scale).
- **Add reference-table entries before the cohorts that need them** (measures/instruments/triggers),
  so records validate on first build. Several ME/CFS instruments already exist (DSQ, Bell,
  PROMIS-fatigue, COMPASS-31); add case-definition measures (IOM/CCC/ICC) as needed.
- Watch the gap matrices and the "largest comparable set" per measure after each batch — that is
  the scoreboard.

---

## 7. Environment gotchas (this repo, this machine)

- **Windows + Git Bash.** Prefix Python one-liners that print Unicode with `PYTHONIOENCODING=utf-8`
  or they crash on the cohort names. `LF will be replaced by CRLF` warnings on `git add` are
  benign.
- **Commit selectively — the working tree has unrelated pre-existing WIP** that must NOT be
  committed with cohort work: `hospital-ranking/**`, `disease_pipeline/output/generate_html.py`,
  `med-freedom-map/backend/*.db*`, and scratch scripts (`temp_add_pots.py`,
  `scripts/price_everything.py`, `scripts/enrich_prices_pots_mcas.py`). Stage explicit paths;
  after staging, sanity-check nothing unrelated slipped in
  (`git diff --cached --name-only | grep -iE 'hospital-ranking|disease_pipeline|\.db|temp_'`).
- **`gh` CLI is not authenticated** here. You can't list PRs or use GitHub API via `gh` without
  `gh auth login`. Deploy is push-to-main → Pages, so you rarely need `gh`.
- **Reading PDFs:** the Read tool's PDF renderer isn't installed; extract text with `pypdf`
  (`python -c "from pypdf import PdfReader; ..."`).
- **SEO/sitemap coupling:** `scripts/build_pais_cohorts.py` calls `scripts/build_site_seo.py` at
  the end, which rewrites site-wide SEO meta and `sitemap.xml`. The sitemap `<lastmod>` uses
  `date.today()` (nondeterministic) but is outside CI's sync-check paths, so it doesn't fail CI.
  If you build, this may show `sitemap.xml` and unrelated HTML as modified — commit only your
  PAIS files plus the PAIS artifacts unless you intend an SEO change.
- **CI (`validate-cohorts.yml`)** runs `--check`, confirms the frozen `data/v1/` snapshot still
  parses, and rebuilds to confirm artifacts are in sync. Match it locally before pushing.

---

## 8. Command cheat-sheet

```bash
# validate everything (CI's first step)
python scripts/build_pais_cohorts.py --check

# full rebuild (regenerates artifacts + SEO); run before committing data changes
python scripts/build_pais_cohorts.py

# count observations for a measure across cohorts (comparable-set intuition)
python -c "import json,glob,sys;sys.path.insert(0,'scripts');import build_pais_cohorts as b;\
c=[(p,json.load(open(p,encoding='utf-8'))) for p in glob.glob('data/cohorts/*.json')];\
print(sum(1 for d,o in b.all_observations(c) if o['measure_id']=='sym:fatigue'))"

# stage a data batch (example) then sanity-check and commit
git add data/cohorts/<new>.json data/ref/*.json data/pais-cohorts-index.json \
        data/pais-cohorts.csv data/pais-observations.csv pais-cohorts.html pais-cohorts/
git diff --cached --name-only | grep -iE 'hospital-ranking|disease_pipeline|\.db|temp_' || echo clean
git commit -m "..." && git push origin main

# verify live after deploy
curl -s "https://research.opensourcemed.info/data/pais-cohorts-index.json?cb=$(date +%s)" \
  | python -c "import json,sys;d=json.load(sys.stdin);print(len(d['cohorts']),'cohorts')"
```

---

## 9. Open decisions for the maintainer (surface these; don't decide unilaterally)

- **Scope framing:** the database now spans infection- *and* exposure-associated conditions
  (`environmental` class). If the maintainer wants the *headline* to stay strictly
  "infection-associated", add comparator framing to the page intro rather than removing the class.
- **Sitemap determinism:** `<lastmod>` uses today's date. Harmless, but if a fully reproducible
  sitemap is wanted, switch it to the git commit date or drop `lastmod`.
- **New `pathogen_class` values** (e.g. a future `physical`/`radiation` exposure) are enum changes
  that touch the schema, the build label map, and the class ordering in
  `cohorts_by_pathogen()` — make them deliberately, with sign-off, like `environmental` was.
