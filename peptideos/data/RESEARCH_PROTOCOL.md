# PeptideOS compound research protocol (October 2026)

You are building **verified** compound records for PeptideOS, a disinterested evidence and regulatory map of therapeutic peptides. Read `../peptideos-build-brief.md` (editorial rules) first. The previous records were found to contain fabricated DOIs and trial numbers; nothing from `../compounds/*.md` may be reused unless you re-verify it yourself.

## Hard rules
1. **Every citation is real and checkable.** Give a DOI *and* the exact article title as printed by the publisher (or a PMID and its exact title). A script resolves each DOI via Crossref and compares titles; a mismatch fails the build. Do not cite from memory: open the record (doi.org, pubmed.ncbi.nlm.nih.gov, or api.crossref.org/works/<doi>) and copy the title.
2. **Every trial ID is real.** NCT IDs are checked against the ClinicalTrials.gov API with the registered brief title; give the title exactly as registered (api: `https://clinicaltrials.gov/api/v2/studies/<NCT>`).
3. **Every regulatory status has a primary source.** Regulator pages only (FDA Drugs@FDA / label / 503A bulks category lists / Federal Register; EMA EPAR or Union Register; MHRA; Health Canada DPD; TGA ARTG or Poisons Standard; PMDA; NMPA for China), plus a verbatim quote (≤40 words) that you read on that page, and the retrieval date. For "not approved" statuses, cite the regulator search/database page or an official list that shows absence, and say so in `detail`.
4. **No dosing, ever.** No amounts with units (mg, mcg, µg, IU, mL, units/kg) anywhere, not even label doses. No administration, reconstitution, cycling, stacking, or "protocol" language. No vendors, no prices, no purchase language. No second-person advice. No testimonials. No "promising"/"exciting".
5. **Evidence tier per indication** using the rubric: E1 multiple adequately powered RCTs consistent; E2 ≥1 adequately powered RCT; E3 small/underpowered or conflicting RCTs; E4 non-randomised/uncontrolled human trials; E5 case reports/series; E6 animal only; E7 in vitro only; E8 no published efficacy evidence in any model. Tier the indications the compound is **marketed or claimed** for, not just the approved one — for gray-market compounds that is the point.
6. **Safety grade:** S1 large long-term human exposure (post-marketing surveillance, >1 year, thousands exposed); S2 substantial controlled-trial safety data; S3 limited human safety data (small trials, <1 year); S4 minimal human exposure (case reports, tiny studies); S5 no human safety data. A documented harm goes in `known_signals` with a citation. Absence of data is stated, never implied as safety.
7. **Unknowns:** at least 3, specific (e.g. "No human pharmacokinetic data by any route"), never "more research needed".
8. **Mechanism:** one or two neutral sentences, rendered last on the page. Findings stay in their model ("increased X in rats"), never "promotes healing".
9. **Honesty over completeness.** If you cannot verify a field, leave it out or state the absence. A missing field is fine; a wrong one is not.

## Output: one YAML file per compound
Write `data/compounds/<slug>.yaml` (relative to `peptideos/`). Exact shape:

```yaml
slug: bpc-157
names:
  inn: null                       # INN if assigned
  common: ["BPC-157", "Body Protection Compound-157"]
  codes: ["PL 14736"]
  brands: []                      # approved brand names, if any
  cas: "137525-51-0"              # only if verified (cite in sources if unsure: leave null)
sequence: "GEPPPGKPADDAGLV"       # one-letter code; null if non-standard residues/lipidation
sequence_note: null               # e.g. "C-18 fatty diacid at Lys26; Aib at position 2"
class_by_jurisdiction: {US: C, EU: C, UK: C, CA: C, AU: C, JP: C, CN: C}   # A approved / B in active sponsored development / C neither
what_it_is: >-                    # ≤90 words, plain, no benefit claims
  A 15-amino-acid synthetic peptide fragment ...
evidence:
  - indication: "Tendon and ligament healing"
    tier: E6
    human_rcts: 0
    human_trials_any: 0
    summary: >-                   # ≤120 words; state the absence plainly
      ...
    citations:
      - doi: "10.xxxx/yyyy"
        title: "Exact title"
        year: 2019
        finding: "Increased tendon-to-bone healing in a rat model"   # neutral, model named
    trials_query: "BPC-157"      # ClinicalTrials.gov intervention search term for the denominator (build computes counts)
safety:
  grade: S5
  no_data_statement: true
  known_signals:
    - signal: "..."
      evidence: "..."
      citation: {doi: "...", title: "..."}
regulatory:
  - jurisdiction: US              # US EU UK CA AU JP CN
    status: unapproved            # approved | investigational | unapproved | 503a_category_1 | 503a_category_2 | withdrawn
    detail: "..."
    source_url: "https://www.fda.gov/..."
    source_title: "..."
    quote: "verbatim ≤40 words"
    retrieved: "2026-10-10"
sport:
  wada_status: prohibited         # prohibited | not_prohibited | monitored
  wada_class: "S0"                # e.g. S0, S2, S4.4
  source_url: "https://www.wada-ama.org/..."
  quote: "verbatim ≤40 words"
trials:                           # optional: key registered trials (Class A pivotal / Class B programme)
  - nct: "NCT0xxxxxxx"
    title: "Exact registered brief title"
    phase: "3"
    status: "Completed"           # as shown on ClinicalTrials.gov
unknowns:
  - "..."
mechanism: >-
  ...
reviewer: "OSMF research team (AI-assisted, source-verified)"
last_reviewed: "2026-10-10"
```

## Before you finish
Re-open each DOI's Crossref record and each NCT's API record and confirm the title you wrote matches. Confirm the YAML parses. Report per compound: class by jurisdiction, tiers, and anything you could not verify (max 250 words total).
