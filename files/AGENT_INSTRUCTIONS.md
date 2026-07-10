# AGENT INSTRUCTIONS — Build & publish the NTD Intelligence section

**For:** a coding agent (e.g. Claude Code) with shell + git access.
**Goal:** generate a hosted "NTD Intelligence" section for
`research.opensourcemed.info`, matching the existing RepurpOS disease-page format,
where **every one of the 21 WHO NTDs** shows its burden, top therapeutic hits, and —
the point of this task — **whether a post-infectious syndrome is documented and the
literature percentage of patients with persistent symptoms**. Then commit and push to:

```
https://github.com/MattH55/osmf-research-tracker
```

You have been given this `ntd_pipeline/` bundle. Do the steps in order. Stop and
report if any acceptance check fails.

---

## 0. What's in the bundle

```
pipeline.py         orchestrator (burden + drugs/targets -> ntd_intelligence.json/.csv)
ntd_registry.py     21 WHO NTDs + curated post-acute classification
persistence.py      literature persistence % per post-infectious syndrome (+ citations)
render_html.py      generates ntd/index.html + ntd/<slug>.html in RepurpOS style
opentargets.py      Open Targets GraphQL client (drugs/targets)
clinicaltrials.py   ClinicalTrials.gov v2 client
burden.py           burden loader + GBD refresh instructions
burden_seed.csv     INDICATIVE burden (replace with a real GBD export)
requirements.txt    requests
build_and_publish.sh one-shot convenience script (see step 7)
```

The four NTDs with a genuine post-infectious infection syndrome (PAIS) and their
persistence figures are already curated in `persistence.py`:
Chagas (~30% cardiac/~10% digestive), chikungunya (~40% chronic arthralgia),
dengue (~20% post-infectious fatigue), leishmaniasis (PKDL 5–10% ISC → 50–60% E. Africa),
plus neurocysticercosis (~30% of endemic epilepsy). Each carries source tags.

---

## 1. Clone the target repo

```bash
git clone https://github.com/MattH55/osmf-research-tracker.git
cd osmf-research-tracker
```

Use whatever auth is already configured (an existing `gh auth login`, a cached
credential helper, or a `GITHUB_TOKEN`/PAT in the environment). **Do not hardcode
or print any token.** If cloning fails on auth, stop and report exactly what's needed.

## 2. Drop the pipeline in

```bash
mkdir -p tools/ntd-pipeline
cp -r /path/to/ntd_pipeline/* tools/ntd-pipeline/
python3 -m pip install -r tools/ntd-pipeline/requirements.txt
```

## 3. Inspect an existing disease page so the new pages match

Before rendering, look at how existing RepurpOS pages are structured **in this repo**
(or fetch one from the live site) and reconcile styling:

- If the repo already contains the disease-intelligence pages or a shared stylesheet
  (search: `find . -name '*.css'` and `ls disease-intelligence/ 2>/dev/null`), open one
  page, copy the `<head>` stylesheet `<link>` href, and set `SITE_CSS_HREF` at the top of
  `tools/ntd-pipeline/render_html.py` to that path. This makes the NTD pages inherit the
  exact site look. The embedded CSS in `render_html.py` is a close fallback if no shared
  sheet exists.
- Match the top-nav link list to the live site's nav if it differs from the `NAV` list in
  `render_html.py` (update in one place).
- Reference page for format: `disease-intelligence/myalgic-encephalomyelitis-chronic-fatigue-syndrome.html`
  (stat cards → overview → chronicity block → therapeutics). Our pages replace the
  "Remission & chronicity" block with a **"Post-infectious syndrome & persistent symptoms"** block.

## 4. (Recommended) Refresh the data live

The bundle renders out-of-the-box on mock/indicative data, but for a publishable page
refresh burden and therapeutics:

```bash
cd tools/ntd-pipeline
# Burden: export Global/latest Deaths + DALYs for the NTD causes from
#   https://vizhub.healthdata.org/gbd-results/  (see burden.py for exact filters),
#   save as gbd_export.csv, mapping cause_name via burden.CAUSE_TO_KEY.
python3 pipeline.py --burden-csv gbd_export.csv --drugs 8 --targets 8   # live Open Targets + CT.gov
```

Needs network to `api.platform.opentargets.org` and `clinicaltrials.gov`.
If no network/GBD export is available, run `python3 pipeline.py --mock --no-trials`
and leave a visible "indicative burden" note (the pages already print this caveat).

## 5. Render the section

```bash
cd tools/ntd-pipeline
python3 render_html.py          # writes ./ntd/index.html + ./ntd/<slug>.html (23 files)
```

Then place the output where the site serves it. Match the existing site's layout —
most likely a top-level `ntd/` directory that mirrors `disease-intelligence/`:

```bash
mkdir -p ../../ntd
cp -r ntd/* ../../ntd/
```

## 6. Wire it into site navigation

Add an "NTD Intelligence" entry to the site's main nav / index so the section is
reachable, pointing at `/ntd/index.html`. Mirror however `disease-intelligence` is
linked from `index.html`. Also add a link from the RepurpOS index page if appropriate.

## 7. One-shot alternative

`build_and_publish.sh` chains steps 4–5 and stages the output. Review before running:

```bash
cd tools/ntd-pipeline && ./build_and_publish.sh          # renders (mock unless GBD csv passed)
./build_and_publish.sh gbd_export.csv                    # live burden
```

## 8. Commit & push

```bash
cd osmf-research-tracker
git add ntd/ tools/ntd-pipeline/
git status                       # sanity-check the diff
git commit -m "Add NTD Intelligence section: burden, therapeutic hits, and post-infectious persistence for the 21 WHO NTDs"
git push origin HEAD
```

If the default branch is protected, push a branch and open a PR instead:

```bash
git checkout -b ntd-intelligence
git push -u origin ntd-intelligence
gh pr create --fill    # if gh is available
```

---

## Acceptance criteria (verify before reporting done)

1. `ntd/index.html` exists and lists **21 NTD groups** (22 rows — dengue & chikungunya
   are split; the page states this).
2. Each disease page has a **"Post-infectious syndrome & persistent symptoms"** section.
3. The four PAIS diseases show their persistence figure and citations:
   - chikungunya ~40%, dengue ~20%, chagas ~30% cardiac/~10% digestive,
     leishmaniasis 5–10%→50–60% (PKDL).
4. Pages visually match the RepurpOS style (shared CSS linked if the repo has one).
5. The section is reachable from site navigation.
6. Changes are pushed to `MattH55/osmf-research-tracker` (direct or via PR).

## Data provenance & caveats (keep these honest on the page)

- **Burden** = IHME GBD. The shipped `burden_seed.csv` is **indicative** — replace with a
  real GBD export before treating numbers as authoritative (snakebite/schistosomiasis/scabies
  estimates are contested between sources).
- **Therapeutics** = Open Targets `knownDrugs` (ChEMBL-indication-based); standard-of-care
  antiparasitics may be missing on live runs — cross-check WHO Essential Medicines & DNDi.
- **Persistence %** = curated from peer-reviewed meta-analyses/cohorts (cited per page).
  Percentages are of the stated denominator (e.g. "of symptomatic cases"), not of all infected.
  Diseases without a single defensible figure are marked "not quantified", not invented.
- Footer disclaimer on every page: associations, not a diagnostic test.

## Do NOT

- Do not invent persistence percentages for diseases where `persistence.py` leaves `pct=None`.
- Do not commit any GBD export that is license-restricted without checking terms.
- Do not print or commit auth tokens.
