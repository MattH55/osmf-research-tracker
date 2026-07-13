# PeptideOS — An Evidence and Status Map

**Build brief.** A reference resource covering therapeutic peptides from approved drugs through gray-market research chemicals.

---

## 0. What this is, and what it refuses to be

Every peptide resource on the internet today is a storefront with a literature review bolted to the front of it. Search "retatrutide" and the top results are vendor blogs and affiliate wikis, written to capture people who have already decided to buy. The clinical information they contain is not *false*, exactly — it's selected. Nobody who makes money when you inject something is going to lead with "there is no human evidence that this works."

That is the gap. Not "information about peptides" — there's a glut of that. **Disinterested** information about peptides. There is almost none.

**This resource answers three questions per compound, and only these three:**

1. What is the actual evidence that it does anything in humans?
2. What is its legal and regulatory status, where you are?
3. If you obtained it on the gray market, what is actually in the vial?

**It does not answer — ever, on any page, in any format:**

- What dose to take
- How to reconstitute, inject, cycle, or stack it
- Where to buy it, or which vendors are trustworthy
- Whether *you* should take it

That last list is not squeamishness. A dosing table is the single line that converts an information resource into a usage guide, and a usage guide for unapproved drugs is facilitation. The line is bright, it is in the code as a lint rule (§6), and it does not move for traffic.

**The bet:** that a resource which refuses to help you buy the thing is the only one anyone will believe about whether the thing works.

---

## 1. Taxonomy — three classes, treated differently

Lumping semaglutide and BPC-157 under one banner is a category error that most sites make and that regulators will notice. Three separate classes, visually and structurally distinct on the site:

### Class A — Approved
Peptide drugs with marketing authorization in at least one major jurisdiction.
*e.g. semaglutide, tirzepatide, teriparatide, tesamorelin, bremelanotide, setmelanotide, octreotide, desmopressin, leuprolide, icatibant.*

Treatment: standard drug monograph. Label indications, approved doses (cite the label; do not compose your own), pivotal trials, safety profile, jurisdictional approval table. This class is uncontroversial and it anchors the site's credibility — it demonstrates you can write a competent monograph before you start telling people that their favorite research chemical has no human data.

### Class B — Investigational
In active clinical development with a real sponsor. Not approved anywhere.
*e.g. retatrutide, survodutide, mazdutide, cagrilintide, elamipretide.*

Treatment: **trial tracker.** Phase, sponsor, NCT numbers, readouts to date, expected filings. Retatrutide is the flagship here — three Phase 3 readouts in hand (TRIUMPH-4, TRANSCEND-T2D-1, TRIUMPH-1), NDA expected around Q4 2026, approval not before 2027.

**Class B carries a mandatory standing notice on every page:**

> This compound is an investigational drug. It is not approved in any jurisdiction. There is no lawful supply. Any material sold under this name is of unverified origin, and is neither manufactured nor tested to pharmaceutical standards.

Class B is where the real-world harm is concentrated right now — gray-market GLP-1/GIP agonists are being sold in unlabeled vials to people doing their own reconstitution arithmetic. Getting Class B right is the public-health justification for the whole project.

### Class C — Gray market
No approval anywhere, no active sponsor, sold as "research chemical, not for human consumption" — a labeling fiction that everyone involved understands.
*e.g. BPC-157, TB-500, ipamorelin, CJC-1295, epitalon, melanotan II, GHK-Cu, KPV, LL-37, semax, selank, AOD-9604, follistatin-344.*

Treatment: **evidence tier front and center, above the fold, before mechanism.** For most of Class C the honest answer is *no human RCT evidence exists*, and that sentence is the most useful thing the resource will ever tell anyone. It should be impossible to read a Class C page and not know it.

Note the traps: **PT-141 is bremelanotide** — approved as Vyleesi, so it is Class A when prescribed and Class C when bought as powder. **Sermorelin** was approved and withdrawn commercially. **Thymosin alpha-1** is approved in some countries and not others. Class assignment is per-jurisdiction, not global. Model it that way from the start (§3).

---

## 2. The evidence tier — the spine of the whole thing

One rubric, applied identically to every compound, displayed as a badge on every page. No compound gets to skip it. No compound gets a "promising!" exemption.

| Tier | Criterion |
|---|---|
| **E1** | Multiple adequately-powered, randomized, controlled human trials, consistent direction |
| **E2** | At least one adequately-powered RCT in the indication |
| **E3** | Small or underpowered human RCTs; conflicting results |
| **E4** | Human trials without randomization or control; open-label series |
| **E5** | Case reports and case series only |
| **E6** | Animal models only |
| **E7** | In vitro only |
| **E8** | **No published evidence of efficacy in any model.** Mechanistic speculation only. |

Two rules that make this honest rather than decorative:

- **Tier is per-indication, not per-compound.** BPC-157 may sit at E6 for tendon healing and E8 for everything else it is sold for. The badge is `E6 (tendon, rodent) / E8 (all other claimed uses)`. Compounds are marketed on their best claim; the resource must refuse that framing.
- **The denominator is stated.** "3 human RCTs" is meaningless without "out of 47 registered trials, of which 22 were terminated or never reported." Publication bias is the field's central pathology and the resource must surface it.

Add a separate, orthogonal **safety evidence** grade. A compound can be E8 for efficacy and still have a real safety signal — melanotan II has essentially no efficacy evidence and a genuine melanoma/priapism literature. Efficacy-unknown does not mean safety-unknown, and conflating the two is how people get hurt.

---

## 3. The compound record

`schema/compound.schema.json`

```jsonc
{
  "slug": "bpc-157",
  "names": { "inn": null, "common": ["BPC-157"], "codes": ["PL 14736"], "cas": "137525-51-0" },
  "sequence": "GEPPPGKPADDAGLV",
  "class": "A | B | C",                    // per jurisdiction, see below
  "structure": { "length_aa": 15, "modifications": [] },

  "evidence": [
    {
      "indication": "tendon healing",
      "tier": "E6",
      "human_rcts": 0,
      "human_trials_any": 0,
      "animal_studies": 21,
      "registered_trials_total": 3,
      "registered_trials_reported": 0,   // the publication-bias denominator
      "key_citations": ["doi:…"],
      "summary": "…",                     // ≤150 words, plain, no hedging upward
      "last_reviewed": "2026-07-13",
      "reviewer": "…"
    }
  ],

  "safety": {
    "grade": "S1..S5",
    "known_signals": [{ "signal": "…", "evidence": "…", "citation": "doi:…" }],
    "no_data_statement": true            // explicit when absence of signal ≠ evidence of safety
  },

  "regulatory": [                          // ALWAYS per-jurisdiction. Never a single global status.
    {
      "jurisdiction": "US",
      "status": "approved | investigational | unapproved | excluded_from_supplement_definition | 503a_category_2",
      "detail": "…",
      "source_url": "https://www.fda.gov/…",   // MANDATORY — see the verification rule below
      "source_retrieved": "2026-07-13",
      "source_quote_ref": "section/page"
    }
  ],

  "sport": { "wada_status": "prohibited | not_prohibited | monitored", "wada_class": "S2", "source_url": "…" },

  "market": {
    "sold_as": ["research chemical", "not for human consumption"],
    "typical_presentation": "lyophilized powder, 5mg vial",
    "purity_tests": ["<-- FK to the testing programme, §5 -->"]
  },

  "unknowns": [                            // MANDATORY, minimum 3 entries. The most valuable field on the page.
    "No human pharmacokinetic data by any route",
    "Oral bioavailability unestablished",
    "No long-term safety data at any dose"
  ]
}
```

### The verification rule — non-negotiable

**No regulatory status may be asserted from memory, from another website, or from a model's recollection.** Every `regulatory[]` entry requires a `source_url` pointing to the primary regulatory document — the FDA 503A bulk substances category lists, the Orange Book, the EMA register, the relevant guidance — retrieved and dated.

Regulatory status in this space is fast-moving, jurisdiction-specific, and constantly misreported. Half the errors on peptide sites are downstream of somebody confidently repeating a status that was true in 2023. The CI fails if any `regulatory[]` entry lacks a resolvable, dated `source_url`. Build that check in week one.

---

## 4. Page structure

Fixed order, every compound, no exceptions. The order is the argument.

1. **Evidence tier badge** — the first thing on the page, before the name is even fully explained
2. **What it is** — sequence, class, one paragraph
3. **Regulatory status, by jurisdiction** — a table
4. **What the human evidence shows** — and, prominently, where there is none
5. **Safety signals**
6. **What is unknown** — the `unknowns` array, rendered as a list
7. **Product quality** — purity testing results, if any (§5)
8. **Citations** — every claim, linked

Mechanism goes at the *bottom*, or is omitted entirely. Mechanism is the vendor's favorite section because a plausible mechanism reads like evidence to a non-specialist and costs nothing to assert. It is not evidence. Placing it above the human data is how every other site on the internet misleads without lying, and the fix is structural, not editorial.

---

## 5. The purity programme — the reason to build this at all

Everything above is aggregation, and aggregation can be copied. This cannot.

**People are already injecting this material.** For a Class C compound, "what does BPC-157 do in a rat" is an academic question. **"What is actually in the vial you bought"** is the live one, and no one is answering it.

**Design:**

- **Blinded procurement.** Purchase from vendors anonymously, through intermediaries, at retail. Vendors must not know product is destined for testing. Chain of custody documented from purchase to lab.
- **Assay panel:** identity (LC-MS/MS), purity (HPLC), quantity vs. label claim, endotoxin (LAL), sterility, and — for lyophilized product sold for injection — visible particulates and residual solvents.
- **Publication:** full methods, full results, vendor-named. Report the failures *and* the passes; a programme that only publishes failures is an attack, not a survey.
- **Cadence:** annual survey per compound class, with a public results table on every compound page.

**Why this is defensible:** it is harm reduction, not promotion. It tells people nothing about how to use these compounds and everything about how badly the supply chain fails. It is primary data, publishable in a real journal, uncopyable by affiliate sites (whose revenue depends on *not* doing it), and it is the same move as the hospital compliance scorecard — accountability applied to a market that has none.

**Get counsel first.** Purchasing unapproved drugs — even to analyze them — has its own legal wrinkles, and they differ by jurisdiction. Do not start procurement before a lawyer has read the protocol. This is exactly the mistake that was made last time, and it is cheap to avoid twice.

---

## 6. Editorial rules, enforced in CI

Not a style guide. Lint rules. The build fails.

- **No dosing.** No mg figures presented as a recommendation, no ranges, no "commonly used." Approved-drug label doses may be quoted *with the label cited*; nothing else.
- **No administration guidance.** No reconstitution, no injection technique, no cycling, no stacks, no "protocols."
- **No vendors.** No names, no links, no rankings, no "reputable sources." (Vendors appear in purity results, §5, as *subjects*, never as referrals.)
- **No affiliate links, ever.** No monetization hook in the codebase — not behind a flag, not in a config.
- **No purchase-intent SEO.** Prohibited from titles, meta, and keywords: "buy", "where to buy", "best", "source", "legit", "vendor", "for sale", "cheap". Grep the build output.
- **No second person imperative.** "You should," "you can take," "start with" — banned. The resource describes; it does not advise.
- **No unhedged mechanism-as-benefit.** "Promotes angiogenesis" is a finding in a model; "promotes healing" is a claim. The linter flags the second form.
- **No testimonials, anecdotes, or before/after content.** Ever.

Add a `/what-we-wont-tell-you` page, linked from every compound. State the policy plainly and say why. It will be the most-linked page on the site, and it is the entire brand in one document.

---

## 7. Governance and funding

- **Named editors.** Every compound record carries a reviewer and a review date. Anonymous authority is what the vendor sites use.
- **Standing COI disclosure on every page.** Maintainer's location, other ventures, funding sources, and an explicit statement that no vendor, manufacturer, or supplement company funds any part of this. If that ever changes, it is disclosed before it changes.
- **Correction log,** public and prominent, same discipline as the compliance work.
- **Funding:** grants, foundations, institutional licensing of the dataset. **Not** affiliate, not vendor sponsorship, not "educational grants" from anyone who sells peptides. The entire content ecosystem here is affiliate-funded, which is precisely *why* it is worthless — and why refusing that money is the only durable moat available.

---

## 8. Build order

| # | Deliverable | Acceptance test |
|---|---|---|
| 1 | Schema + CI lint rules (§6) + regulatory source-verification check | A page containing a dosing table **cannot** be merged |
| 2 | Evidence tier rubric, documented and published | Applied blind by two reviewers to the same compound → same tier |
| 3 | 10 Class A monographs | Establishes competence before controversy |
| 4 | Class B tracker (retatrutide first) | Standing investigational notice on every page |
| 5 | 20 Class C records | Most will be E8. Say so. |
| 6 | `/what-we-wont-tell-you` + COI + correction log | Live before the first Class C page |
| 7 | Purity programme protocol + legal review | Counsel signs off **before** procurement |
| 8 | First purity survey published | Methods complete enough to be replicated by a critic |

Milestones 3 → 5 in that order matters. If the site launches with BPC-157, it is a peptide site. If it launches with ten competent approved-drug monographs and *then* tells you that your favorite research chemical is E8, it is a reference work.

---

## 9. Sequencing — read this before you start

The trial programme comes first.

A peptide resource launched from Próspera, weeks after a supplement trial page was withdrawn, reads to a hostile observer as a pattern rather than a portfolio. Resolve the IND question, register the study, get the ethics review done — establish that the operation runs to a higher standard than the space it is in. **Then** publish this, as an evidence map from a group that runs registered trials.

Identical content. Entirely different reception. The wait is free; the misread is not.
