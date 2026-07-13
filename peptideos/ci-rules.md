# PeptideOS CI Lint Rules

These rules are enforced by automated checks in the build pipeline. A violation **blocks merge**.

## Rule 1: No Dosing Information
**Check:** Grep all HTML content for dose-like patterns.

- ❌ BANNED: `mg/kg`, `mcg/day`, `200 mg`, `"commonly used dose"`, `"typical range"`
- ❌ BANNED: `"start with"`, `"initial dose"`, `"escalate to"`, `"maintenance"`
- ✅ ALLOWED: FDA-approved label doses quoted *with citation to the label*
  - Example: `"The labeled dose is 0.5–1.0 mg subcut weekly (per FDA label, revised 2024)"`
- ✅ ALLOWED: Clinical trial doses in trial summaries, *with trial citation*
  - Example: `"TRIUMPH-1 used 10 mg weekly; TRANSCEND-T2D used 12 mg weekly"`

**Enforcement:** All dosing patterns flagged in pre-commit check. CI fails if any are found outside of `<blockquote cite="[FDA-URL]">` or `<cite>NCT…</cite>` tags.

---

## Rule 2: No Administration Guidance
**Check:** Grep for reconstitution, injection, cycling, stacking keywords.

- ❌ BANNED: `"reconstitute with"`, `"dilute"`, `"draw up"`, `"inject subcutaneously"`
- ❌ BANNED: `"6-week cycle"`, `"stack with"`, `"protocol"`, `"on and off"`
- ✅ ALLOWED: Mechanism of action ("administered as a subcutaneous injection in clinical trials")
- ✅ ALLOWED: Route from approved label ("available as powder for injection")

---

## Rule 3: No Vendor Names or Links
**Check:** Forbidden vendor keywords.

- ❌ BANNED: Vendor names (even competitors)
- ❌ BANNED: Links to purchase sites
- ❌ BANNED: "Reputable source", "best vendor", "legit supplier"
- ✅ ALLOWED: Vendor names appear *only* in purity testing results (§5), labeled as subjects, never as recommendations

---

## Rule 4: No Affiliate Links
**Check:** Grep codebase for affiliate URL patterns.

- ❌ BANNED: `?ref=`, `?aff=`, `?partner=`, or any tracking parameter
- ❌ BANNED: Amazon Associates, eBay Partner Network, or shortener services
- ✅ ALLOWED: Direct links to primary sources (FDA, PubMed, ClinicalTrials.gov) with no tracking

Build fails if any affiliate pattern is detected. Period.

---

## Rule 5: No Purchase-Intent SEO
**Check:** Forbidden keywords in `<title>`, `<meta name="description">`, and `<meta name="keywords">`.

- ❌ BANNED: `"buy"`, `"where to buy"`, `"order"`, `"source"`, `"shop"`, `"cheap"`, `"best price"`
- ❌ BANNED: `"legit"`, `"legitimate"`, `"trustworthy"` (implies vendor judgment)
- ❌ BANNED: `"for sale"`, `"available"` (purchase-context words)
- ✅ ALLOWED: `"evidence"`, `"safety"`, `"regulatory status"`, `"clinical data"`

SEO checker runs on every page at build time. Titles with forbidden words are flagged.

---

## Rule 6: No Second-Person Imperative
**Check:** Regex for second-person construction.

- ❌ BANNED: `"you should take"`, `"you can use"`, `"start with"`, `"avoid if you"`
- ❌ BANNED: `"consider taking"`, `"might want to try"` (implies user choice)
- ✅ ALLOWED: `"BPC-157 is taken subcutaneously in research settings"`
- ✅ ALLOWED: `"Patients in trials received 0.5 mg weekly"`

The resource *describes* what happened in trials and what regulations say. It does not advise a reader.

---

## Rule 7: No Unhedged Mechanism-as-Benefit
**Check:** Grep for mechanism claims adjacent to benefit language.

- ❌ BANNED: `"activates PGC-1α [mechanism], promoting healing [benefit]"` (implies mechanism = benefit)
- ❌ BANNED: `"increases angiogenesis [in rats], improving blood flow [in humans]"` (species extrapolation)
- ✅ ALLOWED: `"increases angiogenesis in rodent models of tendon injury"` (stayed in animal model)
- ✅ ALLOWED: `"human trials have shown X in Y population (E2 evidence)"` (evidence tier explicit)

Linter flags sentences that state a mechanism and immediately claim a human benefit without evidence citation.

---

## Rule 8: No Testimonials, Anecdotes, or Before/After Content
**Check:** Grep for first-person singular, narrative voice, experience language.

- ❌ BANNED: `"I noticed"`, `"felt better"`, `"my experience"`, `"lost 10 pounds"`
- ❌ BANNED: Before/after photos, videos, or images
- ❌ BANNED: User reviews, Reddit quotes, blog anecdotes
- ✅ ALLOWED: `"In a randomized trial, patients reported [metric]"`

---

## Rule 9: Regulatory Source Verification (Critical)
**Check:** Automated validation of all `regulatory[]` entries.

For every regulatory entry:
1. `source_url` must be present
2. `source_url` must be resolvable (HTTP 200 response)
3. `source_url` must be a *primary* source (FDA, EMA, national health authority — not a secondary site)
4. `source_retrieved` must be within 6 months of build date (or CI warns for staleness)
5. `source_quote_ref` must be present (section, page, or date from document)

**Whitelist of primary sources:**
- `fda.gov` (Orange Book, 503A lists, FDA guidance)
- `ema.europa.eu` (EMA product registers)
- `clinicaltrials.gov` (trial registry)
- `regulations.gov` (Federal Register, FDA notices)
- National health authority equivalents (TGA, Health Canada, MHRA, PMDA)

**Blacklist (secondary sites, not allowed as regulatory proof):**
- Supplement company websites
- Wikipedia, generic medical wikis
- "Peptide education" blogs
- Affiliate sites of any kind
- Other peptide vendor sites

**CI fails if:** any `regulatory[]` entry lacks `source_url`, or if `source_url` is not primary.

---

## Rule 10: Evidence Tier Justification
**Check:** For E8 and E7 claims, require explicit justification.

- E8 entries must state: `"No published evidence of efficacy in any model. X species/mechanism tested; no human data."`
- E7 entries must state: `"In vitro only. No animal efficacy data."`

Do not allow vague language like `"limited evidence"` to stand for E8. Be specific about what the absence looks like.

---

## Rule 11: No "Promising" Without Quantification
**Check:** Grep for enthusiasm words without supporting data.

- ❌ BANNED: `"promising"`, `"exciting"`, `"shows potential"` without citation
- ✅ ALLOWED: `"promising in Phase 2 trials (N=47, p<0.05 for primary endpoint)"`

---

## Rule 12: Unknowns Array Mandatory, ≥3 Items
**Check:** Every compound record must have `unknowns` array with minimum 3 items.

- ❌ BANNED: Empty unknowns array
- ❌ BANNED: Generic placeholders like `"More research needed"`
- ✅ ALLOWED: Specific gaps:
  - `"No human pharmacokinetic data by any route"`
  - `"Oral bioavailability in humans not established"`
  - `"No long-term safety data (studies limited to 12 weeks)"`

Linter counts `unknowns` items. CI fails if count < 3.

---

## Enforcement Summary

| Check | Tool | Trigger |
|---|---|---|
| Rules 1–8 | `grep` + regex patterns | Pre-commit hook |
| Rule 9 (sources) | Custom CI script (test all URLs) | Build step, must pass before merge |
| Rule 10–12 | Schema validation + grep | Pre-commit hook |

**Build command:**
```bash
npm run validate-peptideos
```

This runs all checks and produces a report. Any failure blocks `git push`.

---

## Exceptions Policy

No exceptions. Not "for clarity," not "in this one case," not "because the audience will understand."

If you think a rule should change, file an issue, discuss it publicly, and update the rule for *everyone*. The rules are the product.

---

## What Happens When You Break a Rule

1. Pre-commit hook catches it → push rejected
2. Fix it locally → commit again
3. If you bypass the hook (`git commit --no-verify`), the CI catches it → PR fails
4. No merge until fixed

That's the design. The rules are not guidelines.
