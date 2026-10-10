# Brief for procedure × jurisdiction batches (access-NN)

Base folder: `C:\Users\matth\OneDrive\Documents\OpenSourceMed\Opensource Medicine (1)\research-tracker\med-freedom-map\data\verification`

1. Read `PROTOCOL.md` in that folder. Use **Result schema B**.
2. Input: `batches\access-NN.jsonl` — 72 records = 2 procedures × 36 jurisdictions (US federal, 5 US states, and 30 countries/zones). Each record carries the stored values and narrative text to verify.
3. Output: `results\access-NN.jsonl`, one line per input `id`, appended and flushed every ~5 records.
4. Work yourself. Do NOT spawn sub-agents (the concurrency limit is reached). You have roughly 200 web searches: plan them.

## Method (efficient and rigorous)
- Group by procedure. For each procedure, first establish the *global* regulatory facts once (e.g. FDA/EMA approval status, scheduling, the main national regimes), then go jurisdiction by jurisdiction.
- For each jurisdiction find the one or two decisive facts: is the product/procedure authorised by that regulator (cite the regulator's database/decision/register entry), and which law permits/prohibits/limits it (cite the statute or official regulator page). Quote them.
- Then judge every narrative field against what you found. Keep text only if each factual statement is supported by your evidence; rewrite to remove unsupported specifics (numbers, clinic names, prices, timelines, residency rules) unless sourced; remove a field entirely if nothing in it is supportable.
- Costs: keep a range only with a source that gives prices for that jurisdiction (clinic price page, published survey, peer-reviewed costing, official fee schedule). Otherwise `cost.verdict = "remove"`.
- `oversight_quality` is an evaluative rating: confirm only if your evidence about the regime (licensing, product testing, inspection) clearly supports the stored level; otherwise `unsupported`.
- If a jurisdiction's status cannot be determined from any adequate source, mark the structured fields `unsupported` and remove the narrative fields. Never guess.
- Many records will share evidence (e.g. the same national law for both procedures, or the same FDA page for all US records). Reuse it, but each record needs its own evidence entries in its line.

## Finish
Check the output has exactly one valid JSON line per input id (no duplicates, valid enums). Report (max 200 words): counts of legal_status verdicts, how many text fields kept/rewritten/removed, costs kept/removed, and the most consequential corrections.

## Search budget (important — learned from batches 01–05)
WebSearch is capped at ~200 per round and the cap is SHARED by all agents running at the same time; earlier batches ran out and had to mark records unsupported. WebFetch is not capped. So:
- Use at most ~50 WebSearch calls. Prefer fetching known authoritative pages directly, e.g.:
  FDA (accessdata.fda.gov Drugs@FDA, fda.gov approval pages, DEA scheduling 21 CFR 1308), EMA (ema.europa.eu/en/medicines/human/EPAR/<product>), Health Canada (Drug Product Database, health-products.canada.ca), TGA (tga.gov.au, ARTG), MHRA (products.mhra.gov.uk), Swissmedic, PMDA (pmda.go.jp English), MFDS Korea, HSA Singapore, CDSCO India, ANVISA Brazil, COFEPRIS, national drug-control laws on official legislation sites (legislation.gov.uk, gesetze-im-internet.de, legifrance, BOE.es, wetten.overheid.nl, laws-lois.justice.gc.ca, legislation.gov.au), UNODC/INCB schedules, WHO; Wikipedia only as a lead to the primary source.
- If a regulator site times out, try the Internet Archive copy: https://web.archive.org/web/2026/<url>.
- Records left unsupported after a real attempt are fine; a guessed value is not.

## New legal_status value: NOT_AUTHORISED (added after batch 08)
Use `NOT_AUTHORISED` when your evidence shows the product/procedure has no marketing authorisation or legal basis in that jurisdiction but is not specifically criminalised or banned (e.g. absent from the national register while approved elsewhere). Use `PROHIBITED` only when a law or regulator affirmatively bans it (scheduling, criminal statute, explicit ban). `UNKNOWN` is only for `unsupported`.

## New access_pathway value: OVER_THE_COUNTER (added after batch 27)
Use `OVER_THE_COUNTER` when the product is lawfully sold without a prescription (dietary supplement, natural health product, listed/OTC medicine, food). Pair it with legal_status `UNREGULATED_PERMITTED` for unregulated supplements or `FULLY_APPROVED` for authorised OTC medicines.

## Country-grouped re-run batches (rerun-access-*)
These records were left `unsupported` in the first pass, usually because a national register or law could not be reached. Work country by country: for each country, first locate its medicines regulator register / approval database, its narcotics or controlled-substances schedule, and any relevant statute (official legislation site), using direct fetches and the Internet Archive for timeouts. Then resolve every record for that country. Each input line carries the original stored record plus `first_pass_notes` explaining what was tried. Output schema B, one line per input id, to `results\rerun-access-<x>.jsonl`. A record may legitimately stay `unsupported`.
