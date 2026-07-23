# Programmatic SEO Build Spec — OSMF Disease & Cohort Pages

**Target properties:** research.opensourcemed.info (RepurpOS, PAIS cohorts, NTD pipeline)
**Owner:** OSMF
**Status:** build spec for coding agent

---

## 0. Objective and the failure mode to avoid

Generate a few hundred to a few thousand indexable pages from existing structured data (100 diseases, 21 WHO NTDs, 21 PAIS cohorts, natural-products and repurposing tracks), each capable of ranking for a specific long-tail query.

The failure mode for programmatic SEO is **mass thin pages**. Google's site-quality systems evaluate the domain in aggregate; 400 templated stubs will suppress the 40 good pages. Every rule in §4 exists to prevent this. If a rule in §4 conflicts with shipping volume, the rule wins.

**Non-goal:** ranking for head terms ("long covid treatment"). Not winnable. The entire play is intent-specific long tail where the structured data *is* the answer.

---

## 1. Query intent map

Build the page inventory from queries, not from the database schema. Each template below must correspond to a query pattern a real person types.

| Template | Query pattern | Example |
|---|---|---|
| A. Disease hub | `<disease> treatment evidence`, `<disease> repurposed drugs`, `is there a treatment for <disease>` | "myalgic encephalomyelitis repurposed drugs" |
| B. Disease × agent | `<agent> for <disease>`, `does <agent> help <disease>`, `<agent> <disease> evidence` | "low dose naltrexone for ME/CFS evidence" |
| C. Agent hub | `<agent> mechanism`, `<agent> clinical trials`, `<agent> dosing evidence` | "nattokinase clinical evidence" |
| D. Cohort record | `<pathogen> post-infectious cohort study`, `<cohort name>` | "Q fever fatigue syndrome cohort" |
| E. Pathogen hub | `does <pathogen> cause chronic illness`, `long <pathogen>` | "long dengue chronic symptoms" |
| F. Gap matrix / dataset | `post-infectious syndrome dataset`, `<pathogen> cohort data` | "post-viral cohort dataset download" |
| G. Standard-of-care staleness | `when was <disease> guideline last updated`, `<disease> no approved treatment` | "conditions with no FDA approved treatment" |

Before generating any template at scale, pull volume + competition for 20 sampled instances of its pattern. **Templates where the median sampled query has zero volume do not get built.** Document the sample in `/seo/intent-validation.json`.

---

## 2. URL architecture

Decide once; migrations are expensive.

```
https://research.opensourcemed.info/
  /diseases/                                  # index
  /diseases/<disease-slug>/                   # Template A
  /diseases/<disease-slug>/<agent-slug>/      # Template B
  /agents/                                    # index
  /agents/<agent-slug>/                       # Template C
  /cohorts/                                   # index (replaces pais-cohorts.html)
  /cohorts/<cohort-id>-<short-slug>/          # Template D
  /pathogens/<pathogen-slug>/                 # Template E
  /data/<dataset-slug>/                       # Template F
```

Rules:
- Trailing slash, lowercase, hyphens. Enforce in build; fail CI on violation.
- Slugs from a **pinned controlled vocabulary** (MONDO for disease, ChEBI/RxNorm for agents, NCBITaxon for pathogens), with a human-readable override map at `/data/slug-overrides.yaml`. Never slug from a free-text label that can change.
- `/pais-cohorts.html` → 301 to `/cohorts/`. Preserve any existing inbound links.
- Disease aliases (ME/CFS vs myalgic encephalomyelitis vs chronic fatigue syndrome) get **one canonical URL** plus alias pages that 301, never `rel=canonical` duplicates. Alias list lives in the vocabulary file.

---

## 3. Data model → template binding

Each template is a pure function of a record plus its joins. Define the contract explicitly so the generator fails loudly on missing fields rather than emitting a blank section.

```yaml
# /schemas/page-contract.yaml
template_A_disease:
  required:
    - mondo_id
    - canonical_label
    - aliases[]
    - prevalence_estimate {value, unit, source_pmid}
    - approved_treatments[] {agent, indication, approval_year, agency}
    - guideline_last_updated {year, body, url}   # staleness signal
    - candidate_agents[] >= 3 {agent_slug, evidence_grade, n_studies}
  optional:
    - biomarkers[]
    - mechanism_summary
    - related_cohorts[]  # join to Template D
  unique_prose_min_words: 250

template_B_disease_agent:
  required:
    - disease_slug, agent_slug
    - evidence_grade                            # your existing graded scale
    - studies[] >= 1 {pmid, design, n, effect_direction, outcome_measure}
    - mechanism_rationale
    - safety_notes
  unique_prose_min_words: 200

template_D_cohort:
  required:
    - cohort_id, pathogen, country, year_range
    - design, denominator, n_enrolled, n_followed
    - followup_duration
    - outcomes_measured[]
    - biospecimen_availability
    - primary_citation {pmid|doi}
  optional:
    - symptom_frequencies[]                     # per your roadmap
    - acute_phase_specimens
  unique_prose_min_words: 150
```

---

## 4. Thin-content gating (non-negotiable)

A generated page is emitted with `index,follow` **only if all** of:

1. It meets `unique_prose_min_words` for its template — where "unique" means text not appearing verbatim on any other page in the corpus. Compute with shingled MinHash across the corpus at build time; fail any page with >70% 5-gram overlap against another page.
2. It has at least the minimum required rows (≥3 candidate agents for A, ≥1 study for B, complete required block for D).
3. It has ≥3 outbound internal links and ≥3 inbound internal links (see §7).
4. It carries at least one primary source citation with a resolvable PMID/DOI.

Pages failing any check are emitted with `<meta name="robots" content="noindex,follow">` and **excluded from the sitemap**, but remain crawlable and linked. Track the noindex count in build output; it's your content-debt backlog.

**Generate the prose, don't template it.** Templated sentences with variable substitution ("Evidence for {agent} in {disease} is {grade}") are exactly what gets classified as scaled content abuse. Use an LLM pass over the structured record to write genuinely distinct summary prose, then:
- store the generated prose in the repo as reviewable content, not at render time;
- require human review before an A-template page flips to `index` (B/D can go on spot-check);
- log the generating model + date in front matter for auditability.

---

## 5. Title / meta / heading formulas

Keep titles under 60 chars where possible; write descriptions for click-through, not keyword density.

```
Template A
  <title>{canonical_label}: Repurposed Drug Evidence | OSMF</title>
  <h1>{canonical_label} — treatment evidence</h1>
  <meta description>{n_agents} candidate agents reviewed against {n_studies}
    studies. Approved treatments, evidence grades, and open data from the
    Open Source Medicine Foundation.</meta>

Template B
  <title>{agent_label} for {disease_short}: Evidence Review | OSMF</title>
  <h1>Does {agent_label} help {disease_short}?</h1>

Template C
  <title>{agent_label}: Mechanism, Trials & Evidence Grade | OSMF</title>

Template D
  <title>{pathogen} post-infectious cohort — {country} {year_range} | OSMF</title>
  <h1>{cohort_label}</h1>

Template E
  <title>Chronic illness after {pathogen}: cohorts & evidence | OSMF</title>
```

Uniqueness check in CI: no two emitted pages may share a title or a meta description.

---

## 6. Structured data (JSON-LD)

One `<script type="application/ld+json">` per page, validated against schema.org in CI.

**Template A** — `MedicalCondition` + `BreadcrumbList` + optional `FAQPage`:

```json
{
  "@context": "https://schema.org",
  "@type": "MedicalCondition",
  "name": "{canonical_label}",
  "alternateName": ["{alias1}", "{alias2}"],
  "code": {"@type": "MedicalCode", "codeValue": "{mondo_id}", "codingSystem": "MONDO"},
  "possibleTreatment": [
    {"@type": "Drug", "name": "{agent_label}", "url": "{agent_url}"}
  ],
  "citation": [{"@type": "ScholarlyArticle", "identifier": "PMID:{pmid}"}],
  "sourceOrganization": {"@type": "Organization", "name": "Open Source Medicine Foundation"},
  "lastReviewed": "{iso_date}"
}
```

**Template D** — `Dataset` (this is the one that gets you into Google Dataset Search, which is a real, low-competition traffic source for cohort records):

```json
{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "name": "{cohort_label}",
  "description": "{150+ char unique description}",
  "license": "https://creativecommons.org/licenses/by/4.0/",
  "creator": {"@type": "Organization", "name": "Open Source Medicine Foundation"},
  "distribution": [{
    "@type": "DataDownload",
    "encodingFormat": "text/csv",
    "contentUrl": "{raw_file_url}"
  }],
  "variableMeasured": ["{outcome1}", "{outcome2}"],
  "temporalCoverage": "{year_range}",
  "spatialCoverage": "{country}",
  "citation": "{doi}"
}
```

Also emit a `Dataset` node for the corpus as a whole at `/data/pais-cohorts/`, and register it with Google Dataset Search + re3data + DataCite (mint a DOI via Zenodo per release — this gives you citable versions *and* an authoritative inbound link).

---

## 7. Internal linking

Orphan pages don't rank. Enforce link topology in the generator, don't hand-curate.

- **Hub → spoke:** every A page links to all its B children, all related D cohorts, and its E pathogen hub.
- **Spoke → hub:** every B page links up to its A and C parents, plus 3–5 sibling B pages selected by evidence-grade adjacency (not random, not alphabetical).
- **Lateral:** every D cohort links to 3 D cohorts sharing pathogen or design, and to its E hub.
- **Anchor text:** use the target page's `<h1>` noun phrase, varied across instances. Never "click here", never the bare URL.
- CI check: every emitted page has inbound links from ≥3 distinct pages. Fail the build on orphans.
- Cross-property: each A page for a post-viral condition links to the relevant spikeprotein.site / VitalScan page, and vice versa. This is how the six domains start compounding instead of competing.

---

## 8. Rendering, crawl, and indexing

- **Static generation only.** Full HTML content in the initial response. No content that appears only after client-side fetch — the current flat-file + JS pattern will not reliably index.
- Sitemap **index** at `/sitemap.xml` pointing to per-template sitemaps (`sitemap-diseases.xml`, `sitemap-cohorts.xml`, …), max 10k URLs each. `lastmod` derived from the content hash of the underlying record, not the build timestamp — false lastmod churn degrades crawl trust.
- Only `index`-eligible pages (§4) appear in sitemaps.
- `robots.txt` allows all; explicitly `Disallow:` any faceted/filter URL patterns.
- Ping IndexNow (Bing/Yandex) on every deploy with the changed-URL list. Submit sitemaps in Google Search Console.
- Set up GSC **and** Bing Webmaster Tools for every subdomain and every OSMF domain, today, regardless of the rest of this spec.
- Per-page `<link rel="canonical">` self-referencing, absolute URL.

---

## 9. E-E-A-T layer

Health content ("your money or your life") is held to a higher quality bar. These are not optional decorations.

On every A/B/C page, above the fold or in a persistent sidebar:
- **Reviewed by:** Matthew Halma, PhD Candidate — with link to `/about/editorial/` and ORCID `0000-0003-2487-0636`.
- **Last reviewed:** ISO date, updated when the underlying record changes.
- **Evidence grade legend** linking to a written methodology page at `/methods/evidence-grading/`.
- A visible **"Not medical advice"** line — short, one sentence, not a wall.
- Full citation list with resolvable DOI/PMID links, rendered as visible HTML.

Build `/methods/` as a real section: grading rubric, inclusion criteria, data provenance, update cadence, conflict-of-interest statement, funding disclosure. This page will get few visitors and is load-bearing for every other page's credibility.

---

## 10. Conversion layer

Traffic without a capture mechanism is wasted. Per template:

- **End of every A/D page:** one-line "This resource is free and donor-funded" + donate button (not PayPal-only — see separate funnel work).
- **Every D cohort page and the /data/ index:** email-gated CSV/JSON export of the full dataset. This is the highest-intent list you can build — researchers and clinicians, not casual traffic.
- **A pages for conditions with no approved treatment:** contextual link to the relevant VitalScan4PACVS or trial-participation content.
- Instrument with a single analytics property across all six domains; tag outbound cross-property links.

**Track per-template:** impressions, clicks, position (from GSC API), and downstream email signups / donations. Store weekly snapshots in `/seo/metrics/`.

---

## 11. Build order

| Phase | Scope | Gate to proceed |
|---|---|---|
| 0 | GSC/Bing setup, crawl audit, confirm current indexing status | Baseline documented |
| 1 | URL architecture, vocabulary pinning, redirects, static rendering | Existing pages indexed |
| 2 | Template D (cohorts, 21 pages) + Dataset schema + Zenodo DOI | Dataset Search inclusion confirmed |
| 3 | Template A (diseases) — ship **20 pages only**, fully reviewed | ≥8 of 20 ranked top-50 for a target query at 8 weeks |
| 4 | Template A remainder + Template E | Phase 3 gate passed |
| 5 | Template B at scale (the volume play) | Phase 4 stable, no manual-action / quality drop |
| 6 | Template C, F, G | — |

**Do not skip the Phase 3 gate.** Twenty pages tells you whether the template can rank before you generate a thousand of them. If the gate fails, the problem is the template or the domain, and scaling multiplies the failure.

---

## 12. Kill criteria

Stop and diagnose if any of these fire:
- Indexed-page count grows but total clicks are flat over 8 weeks → thin content; noindex the bottom tranche.
- Average position for previously-ranking pages degrades after a scaled release → site-wide quality signal hit; roll back to the last reviewed tranche.
- GSC "Crawled – currently not indexed" exceeds 30% of submitted URLs → §4 gating is too loose.
- Manual action in GSC → immediate full rollback of generated content, then remediate.
