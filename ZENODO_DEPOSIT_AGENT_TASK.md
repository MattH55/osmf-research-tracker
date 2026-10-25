# Task: deposit OSMF datasets to Zenodo

**Audience:** a coding agent working in this repository (`research-tracker/`, GitHub `MattH55/osmf-research-tracker`).
**Owner:** Matthew Halma. Every step marked **GATE** needs the owner's explicit approval before you continue.
**Goal:** one citable Zenodo record (with a concept DOI) per OSMF dataset. Each record links back to its page on research.opensourcemed.info, and each page links to its DOI. The links and the DOIs are the point of the work. Do not compromise the data to get them.

---

## 0. Ground rules

1. **Publishing is permanent.** A published Zenodo record cannot be deleted by you, and its files cannot be replaced, only superseded by a new version. Do everything on the **sandbox** first. On production, create **drafts only**. The owner publishes, or gives you explicit per-record approval to call `publish`.
2. **Tokens:** read `ZENODO_SANDBOX_TOKEN` and `ZENODO_TOKEN` from the environment. Never print them, log them, write them to disk or commit them. Scopes needed: `deposit:write`, `deposit:actions`. If a token is missing, stop and ask.
3. **No pushing, no deploys.** Commit locally and report. The owner decides when to push. The main site (opensourcemed.info) is deployed by FTP, and you must not touch it. Hand back any main-site edits as a list.
4. **Never hand-edit generated directories** (`biomarkers/`, `pairs/`, `trials/`, `compare/`, `digest/`, `reports/`, `chronic-disease-interventions/`, …). Change the generator script, then regenerate.
5. **Do not enable the Zenodo GitHub integration** (release-triggered archiving), even though `.zenodo.json` exists. A GitHub release archive contains the whole repo, including `hospital-ranking/`. That folder holds Trilliant-derived price rows, and Trilliant's terms bar re-syndication. Section 7 covers what must happen before that integration is ever switched on.

---

## 1. The records

Build each record from an explicit allow-list of files, never from a whole directory. Paths are relative to `research-tracker/`.

| ID | Record title (draft) | Files | Landing page | Status |
|---|---|---|---|---|
| R1 | PAIS Cohort Database: post-acute infection syndrome cohorts, observations and estimates | `data/pais-*.csv`, `data/pais-*.json` (incl. `*.schema.json`), `data/cohorts/*.json` (zip), `data/ref/*.json`, current-schema spec docs (`pais-cohort-database-spec.md`, `pais-severity-harmony-v1.md`, `pais-susceptibility-factors-spec.md`; confirm which are current) | `/pais-cohorts.html` | **Ready** after the checks in §2 |
| R2 | OSMF Biomarker Atlases: biomarkers reported in patients vs. controls | `data/biomarkers/*.json`, `biomarkers.schema.json`, `data/genetics/*` | `/biomarker-atlas.html` | **Ready** after §2 |
| R3 | Post-viral illness literature index (Long COVID, PACVS, ME/CFS, Lyme, Gulf War Illness, MCAS, POTS) | `data/{long-covid,pacvs,me-cfs,lyme,gulf-war-illness,mcas,pots,other-post-viral,post-viral-illness}.json`, `post-viral-illness.schema.json`, **transformed** (see §2.3) | `/post-viral-illness.html` | **Needs transform** |
| R4 | Clinical trials snapshot and treatment ontology | `data/clinical_trials/clinical_trials_current.json`, `data/clinical_trials/treatment-ontology.json` (inspect `outcomes-cache.json`; include it only if it is derived data, not a raw API cache) | `/trials/index.html` | **Ready** after §2 |
| R5 | Therapeutic agents and drug-repurposing evidence | `data/therapeutic_agents.json`, `data/disease-agent-pairs.json`, `data/agent-literature/`, `data/agent-pipeline/` **excluding `cache/`**, `data/vocab/agent-slugs*.json`, `data/explorer-stats.json`, `data/explorer-validation.json` | `/tools/repurposing-explorer.html` | **Blocked**: licence decision (§2.2) and the pair quality gate (§2.4) |
| R6 | Chronic disease intelligence: druggable targets, candidate compounds and trials for 100+ conditions | `data/disease-intelligence/*.json` (zip; about 100 MB), `disease_intelligence.schema.json` | `/chronic-disease-interventions/index.html` | **Blocked**: licence decision (§2.2) |
| R7 | Medical Freedom Map: verified access data | `data/med-freedom/*.json` + `med-freedom-map/data/verification/` evidence | `/medical-freedom-map.html` | **Hold**: deposit only if the owner says so |

**Never deposit:**
- `hospital-ranking/` (third-party terms; the tool is offline)
- `peptideos/` (being rebuilt; earlier records were withdrawn)
- `data/commercial-tests/` and `data/consumable-products/` (commercial listings)
- any `cache/` directory
- `data/vocab/hpo/` (Human Phenotype Ontology files carry their own licence; cite HPO instead)
- `llm_*prompts*.json`
- `medfreedom.db`
- `_*.py`, `_*.txt`, logs, zips, screenshots

**GATE 1:** show the owner this table with the actual file counts and sizes you found, and get confirmation of the record list before building anything.

---

## 2. Pre-deposit checks (per record)

### 2.1 Content checks
- Every file is tracked in git (`git ls-files`). Record the commit SHA the bundle was built from.
- Validate each JSON file against its schema where one exists (`jsonschema`). Fix nothing silently: report failures.
- **No individual-level health data.** R1 should contain cohort-level aggregates from published studies only. Confirm this. If any row could identify a person, stop and report.
- Scan for secrets, emails and local paths (`C:\Users…`, tokens, API keys).

### 2.2 Licensing (report; the owner decides)
The repo LICENSE says OSMF-created data is CC BY 4.0, and third-party material stays under its original terms. For each record, list which fields are copied from third parties:
- **ChEMBL** (CC BY-SA 3.0). R5 and R6 carry ChEMBL identifiers and per-compound evidence (107 of 109 disease-intelligence files mention ChEMBL). Identifiers alone are facts, but copied ChEMBL attributes may force share-alike. Report which fields come from ChEMBL. The options are: (a) licence the record CC BY-SA 4.0, (b) strip the copied ChEMBL attributes and keep IDs, or (c) keep CC BY 4.0 with a per-field notice. **GATE 2:** the owner picks.
- **DGIdb** (aggregates sources with mixed terms), **Open Targets** (CC0), **ClinicalTrials.gov** (US government, attribution requested), **GWAS Catalog** (EMBL-EBI terms). List each in the record description with a link.
- **Short verbatim quotes** from papers (e.g. `measure_verbatim` in `pais-observations.csv`). Fine as quotation with citation. Report the longest one. If any exceeds roughly two sentences, flag it.

### 2.3 R3 transform: remove abstracts
The post-viral JSON files store PubMed abstracts. Abstracts are copyrighted by publishers and must not be redistributed. Build R3 from a copy with every `abstract` field removed. Keep PMID, DOI, title, journal, year and all OSMF-added classification fields. Do not modify the source files the site uses.

### 2.4 R5 quality gate
The pair data includes non-candidates, such as "Sodium Chloride for Hepatitis C", where saline is a trial diluent or placebo. Do not deposit R5 until the pair quality gate exists in the generator. A separate task covers it. Then deposit only gated pairs, or include a `passes_quality_gate` column. Ask the owner which.

### 2.5 Bundle layout
Build into `dist/zenodo/<record-id>/` and add `dist/` to `.gitignore`. Each bundle contains:
- the data files, with folders of more than about 20 files zipped (Zenodo allows at most 100 files per record)
- `README.md` covering: what it is, how it was generated (script names and commit SHA), schema, field-level provenance, licence notes, how to cite (with the reserved DOI, see §3), and "Research information, not medical advice"
- `CHECKSUMS.sha256`

---

## 3. Metadata

Write one file per record at `deposit/zenodo/<record-id>.metadata.json`, and commit these. Base the fields on `.zenodo.json`, with these corrections:

- `upload_type`: `"dataset"`
- `license`: use the Zenodo licence id (`"cc-by-4.0"`, lowercase). Verify the id against the API before use. `.zenodo.json` has `"CC-BY-4.0"`; fix it there too.
- `creators`: Halma (ORCID 0000-0003-2487-0636) and Tuszynski (ORCID 0000-0001-9976-0429), as in `.zenodo.json`. **GATE 3:** the owner confirms the creator list per record. Do not add anyone else unprompted.
- `contributors`: `{"name": "Open Source Medicine Foundation", "type": "HostingInstitution"}`
- `related_identifiers`:
  - landing page: `{"identifier": "https://research.opensourcemed.info/<page>", "relation": "isDocumentedBy", "resource_type": "other"}`
  - each upstream source: `"relation": "isDerivedFrom"` (ClinicalTrials.gov, ChEMBL, Open Targets, DGIdb, PubMed, GWAS Catalog as applicable)
  - OSMF papers that used the dataset: `"isSupplementTo"` with the paper DOI. **Only** with a DOI the owner supplies. Never infer one.
  - Remove `"isPublishedBy"` from `.zenodo.json`. It is not a valid DataCite relation.
- `version`: R1 uses semantic versions (git tag `pais-v1.1` exists, so `1.1`). Other records use date-based versions (`2026.10`).
- `keywords`: 5–10 per record, specific to it.
- `description`: HTML. Cover what the dataset is, coverage, provenance, the generation commit, a landing-page link and the not-medical-advice line.
- `prereserve_doi`: `true`. This lets you write the DOI into the bundle README before upload.
- `communities`: leave empty unless the owner creates an OSMF community and gives you its id.

---

## 4. Deposit procedure

Implement `scripts/zenodo/deposit.py` (Python 3.12 and `requests`) with `--sandbox`, `--record R1 …`, `--draft-only` (the default) and `--publish` (sandbox only, unless the owner approves). Write a run log to `deposit/zenodo/runs/<timestamp>.json` with no tokens in it.

API base: `https://sandbox.zenodo.org/api` or `https://zenodo.org/api`. Header: `Authorization: Bearer <token>`.

1. **Create:** `POST /deposit/depositions` with body `{"metadata": {...}}` including `prereserve_doi: true`. Keep `id`, `links.bucket` and `metadata.prereserve_doi.doi`.
2. **Stamp** the reserved DOI into the bundle `README.md` and regenerate `CHECKSUMS.sha256`.
3. **Upload** each file by streaming `PUT {links.bucket}/{filename}`. Use the bucket API, not the legacy `/files` endpoint, which has a 100 MB limit. Compare the returned checksum with your sha256 or md5.
4. **Set metadata:** `PUT /deposit/depositions/{id}` with `{"metadata": {...}}`. Fail loudly on any validation error.
5. **Publish** (sandbox, or production with approval): `POST /deposit/depositions/{id}/actions/publish`. Keep `doi` (the version DOI) and `conceptdoi`.
6. **Handle 429 and 5xx responses** with exponential backoff. Never retry a `publish` that may have succeeded: re-read the deposition first.

**Sandbox pass:** run all approved records on the sandbox, publish them there, then open each sandbox record and check the files, previews, licence, creators and links. Sandbox DOIs are not real DOIs. Never put them on the site.

**GATE 4:** send the owner a table of record, sandbox URL, file count, size, licence and creators, and wait for approval.

**Production:** run with `--draft-only`. Report each draft URL. **GATE 5:** the owner publishes each draft in the Zenodo web UI, or tells you per record to run `--publish`.

---

## 5. After publishing: link everything back

Do all of this through generators and scripts, then commit locally.

1. `data/zenodo-records.json`: a registry with `record_id`, `title`, `concept_doi`, `version_doi`, `version`, `zenodo_url` and `landing_page`. Generators read from it.
2. **Landing pages:** add a "Download and cite this dataset" block linking the **concept DOI** (always the latest version) to each landing page in §1. Add or extend `Dataset` JSON-LD with `identifier` (DOI URL), `sameAs`, `license`, `creator`, `isAccessibleForFree: true` and a `distribution` `DataDownload` pointing at the Zenodo record. Find the owning generator with `grep`. Never edit generated output.
3. `README.md`: replace the `zenodo.XXXXXXX` placeholder with a list of the record DOIs.
4. `CITATION.cff`: add an `identifiers:` entry for each concept DOI.
5. `llms.txt` (tracker): add a Datasets section with the DOIs.
6. **Main site (do not deploy):** list the edits for `opensourcemed.info/research-library.html` and `llms.txt` (a "Datasets" section with the DOIs) and hand them back.
7. Run the build and validation scripts the daily workflow runs. Report results.

**GATE 6:** report the commit(s) and wait. Do not push.

---

## 6. New versions (later)

- Snapshot when a schema changes or quarterly. **Never on the daily CI**, which would mint a version every day.
- `POST /deposit/depositions/{id}/actions/newversion`, then open `links.latest_draft`. Delete the inherited files (`DELETE /deposit/depositions/{draft_id}/files/{file_id}`), upload the new bundle, bump `version` and `publication_date`, and follow the same gates.
- The site keeps linking the concept DOI, so it never needs changing.

---

## 7. Preconditions for ever enabling the GitHub integration

The GitHub integration would only archive code, and only after all of these hold:
- A `.gitattributes` file marks as `export-ignore` at least `hospital-ranking/`, `peptideos/`, `data/`, `medfreedom.db`, `**/cache/`, and all scratch, log, zip and screenshot files. Verify with `git archive HEAD | tar -t`.
- `.zenodo.json` describes a **software** record (`upload_type: software`, licence `mit`), not the datasets.
- The owner approves it. This is out of scope for this task.

---

## 8. Final report to the owner

- the records deposited, with concept DOI, version DOI, licence and size
- records held or blocked, with the reason
- every licensing decision made and who made it
- the files changed and the commits, unpushed
- main-site edits to apply
- anything you were unsure about
