# Medical Freedom Map — claim verification protocol (October 2026)

Every public claim on the Medical Freedom Map and the state law maps must be
supported by a specific, retrievable source, or it is corrected or removed.
This file is the instruction set for each verification batch. Results are
applied by `scripts/apply_verification.py` (state-law cells) and
`scripts/apply_access_verification.py` (procedure × jurisdiction records).

## What counts as support
1. **Specific source**: a deep URL to the page that states the fact: the
   statute section, regulator page, official member list, or a named tracker
   page for that exact topic. A site homepage (e.g. `https://www.mercatus.org/`)
   is **never** support.
2. **Retrievable now**: fetch the page during this pass. If it will not load,
   find another source; do not cite what you could not read.
3. **Quoted**: record a short verbatim quote (max ~40 words) from the page that
   states the fact. Paraphrase is not evidence.
4. **Source hierarchy**: primary law or regulator > official compact/agency
   list > reputable tracker (NCSL, KFF, Mercatus page for that state, AANP map,
   CCHP state page, peer-reviewed review) > reputable news. Prefer the highest
   available. Wikipedia and vendor/clinic marketing pages are leads only, never
   final evidence (exception: a clinic's own price page may support a price).
5. **Currency**: the fact must hold as of today (October 2026). If a law
   changed, record the current value and the effective date.

## Verdicts (one per claim)
- `confirmed` — the stored value is right and you have evidence.
- `corrected` — the stored value is wrong; give the right value plus evidence.
- `unsupported` — after a genuine search (at least two queries and the obvious
  primary source), no adequate source states it either way. It will be removed
  from display or marked "not verified". Do NOT guess to avoid this verdict.
- `ambiguous` — sources conflict or the category does not fit the law; explain
  in `notes` and give the best-supported value with evidence.

## Free-text fields (procedure records)
Each narrative field is a set of claims. Return, per field, either `keep`
(every factual statement is supported by your evidence), `rewrite` (supply new
text that contains only supported statements, same style, no new unsupported
facts), or `remove` (nothing in it can be supported). Costs: keep only if a
source (price page, published survey, peer-reviewed costing, regulator fee
schedule) supports the range; otherwise `remove`.

## Output
Write JSON Lines to the results path given in your batch instructions, one
object per claim/record, exactly in the schema given there. Flush results to
disk every ~10 items (append), so progress survives interruption. Never edit
the source data files directly. Report at the end: counts per verdict, the most
consequential corrections, and anything you could not resolve.

## Honesty rules
- Do not invent statute numbers, URLs, quotes or dates. A wrong citation is
  worse than `unsupported`.
- If you are unsure whether a quote supports the value, it does not.
- Record what you actually read; the coordinator spot-checks quotes against
  the live pages.

## Result schema A — state-law cells (batches `state-*.jsonl`)
Input lines carry `key`, `jurisdiction`, `layer`, `dimension`, `type`, `allowed_values`, `stored_value`, `stored_citation`, `stored_source_url`, `stored_note`.
Write one line per input key to `results/<batch>.jsonl`:
```json
{"key":"US-CA|certificate_of_need|con_program_exists","verdict":"confirmed|corrected|unsupported|ambiguous",
 "value":false,                       // correct value, same type as `type` (bool/int/enum from allowed_values/date YYYY-MM-DD/text)
 "evidence_url":"https://...deep page...","evidence_title":"...","evidence_quote":"verbatim ≤40 words",
 "source_type":"primary_statute|official_list|regulator|secondary_tracker|peer_reviewed|news",
 "as_of":"2026-10-09","citation":"human-readable citation, e.g. 'Cal. Health & Safety Code § …' or 'IMLCC participating states list'",
 "notes":"optional: change history, caveats"}
```
Efficiency: most layers have one authoritative list covering all states (e.g. IMLCC/NLC/PSYPACT official maps, AANP practice environment map, NCSL tables, Right to Try statute lists). Fetch it once and reuse it for all states, still giving the deep URL and the state-specific quote or table row. When a list is the evidence, quote the state's entry.

## Result schema B — procedure × jurisdiction records (batches `access-*.jsonl`)
Write one line per input `id` to `results/<batch>.jsonl`:
```json
{"id":"<record id>",
 "legal_status":{"verdict":"confirmed|corrected|unsupported|ambiguous","value":"<one of the legal_status enum>"},
 "access_pathway":{"verdict":"…","value":"<access_pathway enum>"},
 "regulatory_authority":{"verdict":"…","value":"text"},
 "legal_basis":{"verdict":"…","value":"specific statute/regulation/decision, or null"},
 "oversight_quality":{"verdict":"…","value":"<oversight enum>"},
 "cost":{"verdict":"confirmed|corrected|remove","estimated_cost_range_usd":"text or null","price_usd":number_or_null},
 "text":{"access_pathway_details":{"action":"keep|rewrite|remove","text":"only when rewrite"},
         "eligibility_requirements":{…},"provider_requirements":{…},"residency_travel_notes":{…},
         "risk_notes":{…},"oversight_notes":{…},"cost_notes":{…},"arbitrage_summary":{…}},
 "evidence":[{"url":"deep url","title":"…","quote":"verbatim ≤40 words","supports":["legal_status","access_pathway",…]}],
 "notes":"optional"}
```
Allowed legal_status: FULLY_APPROVED, APPROVED_ON_LABEL, APPROVED_OFF_LABEL, PERMITTED_EXPANDED_ACCESS, RIGHT_TO_TRY, CLINICAL_TRIAL_ONLY, PHYSICIAN_DISCRETION_GRAY, REGULATED_THERAPY, UNREGULATED_PERMITTED, DECRIMINALIZED, DECRIMINALIZED_NO_SUPPLY, PROHIBITED, UNKNOWN.
Allowed access_pathway: STANDARD_PRESCRIPTION, OFF_LABEL_PRESCRIPTION, COMPOUNDING, EXPANDED_ACCESS, RIGHT_TO_TRY, CLINICAL_TRIAL_ENROLLMENT, LICENSED_PROVIDER_REGIME, PERSONAL_IMPORT, MEDICAL_TOURISM_CASH, NONE.
Allowed oversight_quality: REGULATED_HIGH, REGULATED_MODERATE, HIGH, MEDIUM, LOW, MINIMAL, VARIABLE (oversight is a judgment: keep it only if the evidence about the regulatory regime supports it; otherwise verdict `unsupported`).
Efficiency: a procedure's status in a jurisdiction usually rests on one or two facts (is the product/procedure approved by that regulator? is there a statute permitting/prohibiting it?). Look those up from the regulator's database or law first, then judge the text fields against what you found. Generic approved drugs (repurposed modality): confirm the drug is authorised in that country (national register / regulator database / SmPC listing), and that off-label prescribing is lawful there; cite both.

## Result schema C — procedure and jurisdiction descriptions (batch `access-meta.jsonl`)
One line per input `id`:
```json
{"id":"…","kind":"procedure|jurisdiction",
 "description":{"action":"keep|rewrite|remove","text":"only when rewrite"},       // procedures
 "typical_us_cost_range":{"action":"keep|rewrite|remove","text":"…"},              // procedures
 "general_notes":{"action":"keep|rewrite|remove","text":"…"},                      // jurisdictions
 "evidence":[{"url":"…","title":"…","quote":"…","supports":["description",…]}],"notes":"…"}
```
