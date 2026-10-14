# PeptideOS rebuild: handoff (2026-10-10)

## State in one paragraph
PeptideOS has been rebuilt from scratch: 37 compound records, each researched under `data/RESEARCH_PROTOCOL.md` and machine-checked, are rendered into a static site with an index, a methods page, a purity page, an open-data page, and governance pages. The previous content was withdrawn: its citations were fabricated (of 26 DOIs, 18 didn't resolve and 7 of the 8 that did pointed to unrelated papers; all 5 NCTs were wrong), and its COI page listed grants that couldn't be substantiated. The corrections log says so. **Published 2026-10-14** at https://research.opensourcemed.info/peptideos/ (GitHub Pages).

## Pipeline
| Step | Command (from `research-tracker/`, with `PYTHONIOENCODING=utf-8`) | What it does |
|---|---|---|
| Validate + lint | `python scripts/build_peptideos.py --check` | Schema, tier/count consistency, no doses/administration/vendors/advice/testimonials/hype, primary-source domains, outbound-link allowlist. Any violation exits 1. |
| Source check | `python scripts/verify_peptideos_sources.py [slug ...]` | DOI→Crossref and PMID→PubMed title match; NCT→ClinicalTrials.gov title match; regulator/WADA quotes found on page (static, then browser UA, Internet Archive, then headless Chrome across all frames; reads PDF and xlsx). Writes `data/source-check.json`. Hard failures block the build. |
| Build | `python scripts/build_peptideos.py [--refresh-trials]` | Renders `index.html`, `compounds/<slug>.html`, `methods`, `what-we-wont-tell-you`, `purity`, `coi-disclosure`, `corrections`, `data` pages; exports `data/peptideos.json` and `.csv` (CC BY); `--refresh-trials` updates ClinicalTrials.gov registered/with-results counts in `data/trials/`. |

- **Code:** `scripts/peptideos_lib.py` holds the rules: tiers, safety grades, lint regexes, allowlists. Styling is `assets/peptideos.css` (spec tokens; `--signal` red is lint-restricted to `.signal` rules).
- **Daily CI:** `.github/workflows/daily-research-update.yml` runs `build_peptideos.py --refresh-trials` before `apply_osmf_chrome.py`.
- **Sitemap:** `peptideos` is in `build_site_seo.py` PUBLIC_DIRS. It is *not* in `apply_osmf_ui.py`, deliberately: PeptideOS keeps its own lab-report chrome.
- **Dependency:** PyYAML was added to `requirements.txt`.

## Records (37)
| Group | Records |
|---|---|
| Approved monographs | Semaglutide, tirzepatide, teriparatide, tesamorelin, setmelanotide, bremelanotide, afamelanotide, octreotide, desmopressin, leuprolide, icatibant, elamipretide |
| Investigational | Retatrutide, survodutide, cagrilintide. Mazdutide is B everywhere except CN A (see below). |
| Gray market | BPC-157, TB-500, KPV, GHK-Cu, AOD-9604, follistatin-344, MOTS-c, LL-37, thymosin-α1, epitalon, semax, selank, dihexa, PE-22-28, GHRP-6, hexarelin, CJC-1295, ipamorelin, sermorelin (US withdrawn), kisspeptin-10, melanotan II |

Source check (2026-10-10): **0 hard failures across all 37.** Three regulator quotes are unconfirmed by the script and need a human look: **mazdutide, retatrutide, survodutide** (see `quote_unconfirmed` in `data/source-check.json`). Fix them by quoting text that is on the page, or by adding the URL to `manual_quote_confirmations` after checking it by eye.

## Known gaps (honest, not errors)
- **Class by jurisdiction:** UK, AU, JP and CN are mostly `null` ("not verified" on the page). Regulator sites blocked or timed out (TGA, NMPA HTTP 412, PMDA partly). This is the biggest content gap: a second research pass on UK MHRA products, the TGA ARTG and PMDA would lift most pages.
- **Mazdutide CN = A** rests on a peer-reviewed secondary source ("Mazdutide: First Approval", Drugs 2025), not an NMPA page. Verify by hand or set it to null.
- **Thymosin α1:** its approvals in China and Italy are unverified, so its "not prohibited" WADA status is inferred.
- **Semax and selank:** Russian approval is unverified (the register is script-rendered), so neither record has a WADA field.
- **BPC-157:** press reports a July 2026 FDA advisory committee vote, but the FDA page found has no vote record, so it isn't stated.
- **Trial counts:** many `human_rcts` values are `null` and render as "n/c" (not counted). Counting them would strengthen the index headline, which only counts explicit zeros.
- **Unchecked data:** PE-22-28's sequence was derived, not read from a source. Some CAS numbers come from PubChem synonyms.
- **No human second review yet:** records name "OSMF research team (AI-assisted, source-verified)". The brief (§8.2) asks for blind double-tiering by two reviewers.

## Decisions for the maintainer
1. **Pushing.** Use `git push https://github.com/MattH55/osmf-research-tracker.git main` (explicit URL because `.git/config` is a broken OneDrive placeholder; restore it with remote `origin` = that URL and branch `main` tracking `origin/main`).
2. **COI funding text.** `coi-disclosure.html` now says "no dedicated external funding". Correct this in `coi_page()` in `scripts/build_peptideos.py` if it's wrong. Named editors: add a human reviewer name to records once one exists.
3. **Purity programme:** the page says "not started; counsel reviews first". Update it only after legal sign-off.

## Next steps, in order
1. Resolve the three unconfirmed quotes and the mazdutide CN source.
2. Run a research pass for UK, AU, JP and CN regulatory entries (same protocol; agents can self-check with the two commands above).
3. Run a human blind re-tier of a sample (say 10 records) and log any changes in `CORRECTIONS` in `build_peptideos.py`.
4. Full desktop QA. Desktop screenshots were checked only for 4 compound pages, the index and methods. Mobile (390px) passed for the index, methods and 6 compound pages.
5. Add research.opensourcemed.info to Search Console.
