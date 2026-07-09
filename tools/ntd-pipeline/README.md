# NTD Intelligence Pipeline

A coding workflow that, for the **21 WHO neglected tropical diseases**, assembles:

1. **Death & disease burden** — deaths/year and DALYs/year (ranking key)
2. **Top therapeutic hits** — approved/clinical drugs *and* top drug-targets
3. **Post-acute syndrome status** — whether each NTD has a distinct post-acute
   infection syndrome (the Long-COVID analog), chronic disease, or lasting sequela

Output is a ranked `.csv` (publication-friendly) and `.json` (full detail).

Built to slot into a RepurpOS-style disease-intelligence workflow. The design goal
was *no dead endpoints and no invented numbers*: ontology IDs resolve at runtime,
therapeutics come from live APIs, and burden is pluggable with a loudly-labelled
indicative fallback.

---

## Quick start

```bash
pip install -r requirements.txt

# runs with zero network - canned demo data, proves the wiring:
python pipeline.py --mock

# live run (needs internet), indicative burden:
python pipeline.py

# live run with authoritative burden from a GBD export:
python pipeline.py --burden-csv gbd_export.csv --top 21
```

Live mode reaches `api.platform.opentargets.org` and `clinicaltrials.gov`.

---

## The workflow (6 stages)

```
[1] SEED         ntd_registry.NTD_LIST         21 WHO NTD groups (noma added Dec-2023)
                                               dengue + chikungunya split into 2 rows
        |
[2] BURDEN       burden.load_burden()          GBD export  OR  indicative seed CSV
        |                                       -> deaths/yr, DALYs/yr  (ranking key)
        |
[3] RESOLVE      opentargets.resolve_disease()  disease name -> EFO/MONDO id
        |                                       (runtime lookup, never hardcoded)
        |
[4] THERAPEUTICS opentargets.known_drugs()      approved + clinical drugs (ChEMBL-sourced)
        |        opentargets.associated_targets() top drug-targets by association score
        |
[5] POST-ACUTE   ntd_registry.POST_ACUTE        curated table: has? / kind / syndrome / source
        |        clinicaltrials.post_acute_signal() live "is anyone studying the chronic phase?"
        |
[6] RANK/OUTPUT  pipeline.write_outputs()       sort by DALYs, then deaths -> CSV + JSON
```

---

## Data sources & endpoints

| Stage | Source | Endpoint / access | Notes |
|---|---|---|---|
| NTD list | WHO | curated in `ntd_registry.py` | 21 groups; list is dynamic, edit as WHO updates |
| Burden | **IHME GBD** | https://vizhub.healthdata.org/gbd-results/ | authoritative; export CSV, no free bulk API |
| Burden (alt) | WHO GHO | https://ghoapi.azureedge.net/api/ | free OData; patchy NTD coverage |
| Therapeutics | **Open Targets** | https://api.platform.opentargets.org/api/v4/graphql | GraphQL; `knownDrugs`, `associatedTargets` |
| Drug detail | ChEMBL | https://www.ebi.ac.uk/chembl/api/data/ | optional enrichment (via Open Targets drug ids) |
| Trials / signal | **ClinicalTrials.gov v2** | https://clinicaltrials.gov/api/v2/studies | v1 retired 2024; `countTotal=true` |
| Post-acute | literature | curated in `ntd_registry.POST_ACUTE` | knowledge question, maintained by hand |

---

## Post-acute classification

The `post_acute_kind` field is the analytically interesting column, and separates
three very different things people lump together:

- **`PAIS`** — a distinct *post-acute infection syndrome* emerging/persisting after
  the acute episode. The direct Long-COVID/PACVS analog.
  → Chagas (chronic cardiomyopathy), chikungunya (chronic arthritis),
    dengue (post-dengue fatigue), leishmaniasis (PKDL).
- **`chronic`** — the disease is chronic/progressive by nature after infection
  (schistosomiasis fibrosis, neurocysticercosis→epilepsy, LF lymphoedema…).
- **`sequela`** — lasting structural damage after cure (trachoma blindness,
  Buruli contractures, snakebite CKD/amputation, noma disfigurement).
- **`none`** — no meaningful post-acute phase (rabies, dracunculiasis).

The four **PAIS** entries are the ones most relevant to a post-viral / post-acute
research program — they are candidate comparators and mechanism analogs for PACVS.

---

## Output columns (CSV)

`rank, disease, pathogen, efo_id, deaths_per_year, dalys_per_year, burden_confidence,
has_post_acute, post_acute_kind, post_acute_syndrome, post_acute_onset,
post_acute_source, top_drugs, top_targets, ct_trials_total, ct_trials_post_acute`

The `.json` additionally carries `top_drug_detail` (phase, MoA, target, approval) and
`top_target_detail` (association score) per drug/target.

---

## Files

```
ntd_registry.py     21 NTDs + curated post-acute knowledge table
burden.py           burden loader + GBD refresh instructions + cause->key map
burden_seed.csv     INDICATIVE burden (replace with GBD export before publishing)
opentargets.py      GraphQL client: resolve_disease / known_drugs / associated_targets
clinicaltrials.py   CT.gov v2: trial counts + post-acute signal
pipeline.py         orchestrator + CLI + ranking + CSV/JSON writer + --mock
requirements.txt    requests
```

---

## Known limits / before you publish

- **Burden numbers in `burden_seed.csv` are indicative placeholders.** Replace them
  with a real GBD 2021 export (`--burden-csv`). DALY/death estimates for several NTDs
  (schistosomiasis, snakebite, scabies) are genuinely contested between sources —
  cite the exact GBD version and location you export.
- **Open Targets coverage is thin for some parasitic/venom NTDs.** `knownDrugs` reflects
  ChEMBL indications; standard-of-care drugs not in ChEMBL as an indication may be
  missed. The `--mock` benznidazole/miltefosine entries show the shape you want; for
  live gaps, cross-check WHO essential-medicines and DNDi pipelines.
- **`resolve_disease` picks the top search hit.** Spot-check the `efo_id` column for
  broad terms; override with `efo_hint` in the registry where the auto-pick is wrong.
- **Post-acute table is a curated starting point,** not a systematic review. Each row
  carries a source tag; deepen these before citing.

## Natural extension points

- Add a `naturalproducts.py` stage: for each disease EFO id, query Open Targets
  literature evidence + ChEMBL natural-product subsets → "top natural-product hits",
  mirroring the therapeutic-hit logic (fits the medicine-you-can-grow work).
- Swap the CT.gov signal for a PubMed/EuropePMC count to quantify post-acute research
  intensity per disease.
- Emit one disease-intelligence HTML page per NTD from the JSON (RepurpOS template).
```
