# Non-drug evidence map, evidence-gap maps, supplement safety, condition briefs

Four public sections built from one classified dataset of ClinicalTrials.gov records.

| Section | URL | Generator |
|---|---|---|
| Non-drug evidence map (hub + one page per intervention class) | `/nondrug/` | `build_nondrug_pages.py` |
| Evidence-gap maps (one per condition) | `/evidence-gaps/` | `build_gap_maps.py` |
| Supplement safety (NIH text + FDA CAERS reports) | `/supplement-safety/` | `build_supplement_safety.py` |
| Printable one-page condition briefs | `/briefs/` | `build_briefs.py` |

## Data flow

1. `crawl_ctgov.py`: one ClinicalTrials.gov query per condition (`conditions.py`: every RepurpOS condition plus the post-viral set), non-drug intervention types only, 1,000 most recently updated trials per condition. Then `crawl_ctgov.py --supplements`: a second query per condition for named supplements that registries record as drugs. Raw responses are cached in `data/nondrug/cache/` (git-ignored, about 100 MB).
2. `build_dataset.py`: classifies every intervention (`taxonomy.py`), drops medicines, controls (placebo, sham, comparator, no-intervention arms), assessments and procedures, tags primary outcomes with domains (`outcomes.py`), and writes `data/nondrug/nondrug_trials.json` (committed).
3. `build_supplement_safety.py --fetch`: openFDA CAERS (suspect-only, counted here because openFDA's count endpoint cannot tie the suspect role to the matching product) and NIH ODS / NCCIH text, quoted verbatim. Writes `data/nondrug/supplement_safety.json` (committed).
4. The four page generators render from the committed JSON with no network. The daily workflow runs them, non-fatally, before `apply_osmf_ui.py`.

Run order after a crawl:

```
python scripts/nondrug/crawl_ctgov.py --refresh
python scripts/nondrug/crawl_ctgov.py --supplements --refresh
python scripts/nondrug/build_dataset.py
python scripts/nondrug/build_supplement_safety.py --fetch
python scripts/nondrug/build_nondrug_pages.py
python scripts/nondrug/build_gap_maps.py
python scripts/nondrug/build_briefs.py
python scripts/apply_osmf_ui.py
python scripts/build_site_seo.py
python scripts/nondrug/check_outcome_rules.py   # re-score the outcome rules
```

## Rules that matter

- **No efficacy grading.** Pages report trial status (registered, recruiting, completed, results posted). "Results posted" means the sponsor uploaded results, not that the intervention worked.
- **Registry type decides first.** DRUG/BIOLOGICAL are excluded, except clearly named supplements (`taxonomy.SUPPLEMENT_OVERRIDE`). BEHAVIORAL and DIETARY_SUPPLEMENT are included (unmatched names fall into "other" classes). DEVICE, OTHER and PROCEDURE are included only when the name matches a class, because unmatched devices are mostly surgical or hospital equipment.
- **Controls are excluded.** An intervention that appears only in placebo, sham, active-comparator or no-intervention arms is not counted (the pair quality gate).
- **Outcome rules are checked by hand.** `data/nondrug/outcome_rule_checks.json` holds three hand-labelled samples of 30 primary outcomes. The held-out sample agreed 20/30 before the rules were adjusted. Every outcome the rules labelled was labelled correctly; misses were left "unclassified" and are shown as such on every gap map. Add a fresh labelled sample before trusting a rule change.
- **Supplement safety.** NIH text is quoted verbatim; OSMF writes no interaction guidance of its own. The "Safety evidence from published studies" sections come from `data/nondrug/safety_library/`, a dated copy of the main site's verified library (opensourcemed.info `data/natural-products/safety/`, where every statement carries an abstract quote checked by `tools/verify_citations.py`); re-export it with `python tools/export_np_to_tracker.py` (run in the opensourcemed.info folder) after that library changes, and never edit the copy by hand. CAERS counts use brand-name matching, which is stated on each page. Reports are split by product name into single-ingredient and combination products (`is_combination`); reactions are shown for single-ingredient reports only, because calcium-with-vitamin-D tablets and multivitamins dominated some counts. Generic categories (probiotics, herbal products) get no count. Bare abbreviations are not used as search terms ("NAC" matched a company called NAC Marketing).
- **Gap statements.** A group's empty cells are reported only when it has at least `gaps.MIN_GROUP_TRIALS` (8) trials, ranked by how many trials of other approaches measured that outcome. The behavioural catch-all has its own group (`behavother`, `taxonomy.CATCHALL_GROUPS`) and is never the subject of a gap statement. Capped conditions get no "never measured" list.
- **Regex edits.** Write rules with `\b` only through a file or the editor: several patterns were once saved with a literal backspace character in place of `\b`, which silently disabled CPAP, ESWT, IV and MACE matching. Scan for control characters after any scripted edit.
- **Briefs** list medicines from the tracker condition page (registered trials in the condition), not RepurpOS's gene-target ranking, which is a mechanistic signal and would read as a recommendation on paper.

## Monthly crawl (to add by hand)

The crawl is deliberately not in the daily job. This workflow needs `contents: write` to commit the refreshed dataset; add it yourself at `.github/workflows/nondrug-monthly.yml`:

```yaml
name: Non-drug evidence map (monthly crawl)
on:
  schedule:
    - cron: '30 3 2 * *'   # 03:30 UTC on the 2nd of each month
  workflow_dispatch:
permissions:
  contents: write
jobs:
  crawl:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    steps:
      - uses: actions/checkout@v4.2.2
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - name: Crawl ClinicalTrials.gov and rebuild the dataset
        run: |
          python scripts/nondrug/crawl_ctgov.py --refresh
          python scripts/nondrug/crawl_ctgov.py --supplements --refresh
          python scripts/nondrug/build_dataset.py
          python scripts/nondrug/build_supplement_safety.py --fetch
        env:
          PYTHONIOENCODING: utf-8
      - name: Commit refreshed data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/nondrug/nondrug_trials.json data/nondrug/supplement_safety.json
          git diff --cached --quiet || git commit -m "chore: monthly non-drug evidence crawl"
          git pull --rebase origin main && git push
```

The next daily run regenerates the pages from the new data.

## Known limits

- Conditions whose search returns more than 1,000 trials are capped; every page names the cap and the registry total.
- Classes come from intervention names and can misfile an individual entry; the registry record is authoritative.
- Not built: device adverse events (FDA MAUDE), curated interaction databases (not openly licensed), and NPxP for chronic disease (NPxP lives at npxp.opensourcemed.info and covers cancer cell lines).
- Clinician review of the brief template and the supplement framing has not happened yet.

## Natural-products review on RepurpOS

`scripts/add_np_review_section.py` adds an evidence-graded natural-products review above the Natural Products table on the RepurpOS pages listed in `PAGE_FOR` in the script. Long COVID has no RepurpOS page, because its page is a redirect stub.

- **Data:** exported read-only from opensourcemed.info by `tools/export_np_to_tracker.py`. Authoring and citation checks stay there.
- **Drafts never enter the repository.** GitHub Pages serves every tracked file, raw data included. The export writes only *published* reviews to `data/natural-products-review/`. Drafts go to `_np_preview/data/`, which is gitignored. `--preview` (and `NP_PREVIEW=1` for the supplement-safety pages) renders drafts into `_np_preview/` for local checks.
- **By compound:** `data/natural-products-review/compounds/index.json` lists each ingredient's published review rows. The supplement-safety pages show them under "Evidence reviews by condition".
- **Separate grades:** the review grades (A–D, Negative, Insufficient) are a different scale from the pipeline's evidence tiers in the table. Each review card that matches a table row names that row and says so; combinations are not matched. The pipeline tiers are never changed.
- **Rerun after regenerating:** the block sits between `<!-- OSMF_NP_REVIEW_START -->` and `END` markers. `disease_pipeline/publish_site.py` regenerates pages without it, so rerun this script afterwards.
