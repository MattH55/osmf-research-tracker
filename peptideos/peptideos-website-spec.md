# PeptideOS — Website Implementation Spec

**For a coding agent.** Companion to the editorial brief (`peptideos-build-brief.md`), which is the source of truth for *what* the site says. This document is *how* it gets built.

Read the editorial brief first. The rules in it are not aspirations — most of them are implemented here as build-time failures.

---

## 1. Stack

| Concern | Choice | Why |
|---|---|---|
| Framework | **Astro** (static output) | Content collections + Zod schemas mean the data model is validated at build. Ships zero JS by default. |
| Content | **Markdown + YAML frontmatter**, in git | Human-diffable, PR-reviewable, forkable. The dataset must outlive the website. |
| Validation | **Zod**, via Astro content collections | A malformed compound record fails `astro build`. Not a warning. |
| Editorial lint | Custom Node script, run in CI **and** as a build integration | §4. This is the load-bearing part. |
| Search | **Pagefind** | Static, no server, no query logging. |
| Styling | Plain CSS with custom properties | No Tailwind. The token system (§5) is small and deliberate; a utility framework would dissolve it. |
| Hosting | **Cloudflare Pages** or Netlify, static | No server, no database, no user accounts, nothing to breach. |
| Analytics | None, or self-hosted aggregate-only | The site collects nothing. Say so on the privacy page and mean it. |

**No CMS. No database. No login. No forms.** The site has no way to collect a single byte from a visitor, and that is a feature to state publicly, not an omission to apologize for.

---

## 2. Repo layout

```
/
├── src/
│   ├── content/
│   │   ├── config.ts               # Zod schemas — the contract
│   │   ├── compounds/              # one .md per compound; YAML frontmatter = the record
│   │   │   ├── semaglutide.md
│   │   │   ├── retatrutide.md
│   │   │   └── bpc-157.md
│   │   └── pages/                  # policy pages (what-we-wont-tell-you, COI, corrections, methods)
│   ├── layouts/
│   ├── components/
│   │   ├── TierLadder.astro        # THE signature element — §5
│   │   ├── RegulatoryTable.astro
│   │   ├── EvidenceBlock.astro
│   │   ├── SafetySignals.astro
│   │   ├── UnknownsList.astro
│   │   └── PurityResults.astro
│   ├── pages/
│   │   ├── index.astro             # the tier grid — §6
│   │   ├── compounds/[slug].astro
│   │   ├── class/[a|b|c].astro
│   │   └── purity/
│   └── styles/tokens.css
├── scripts/
│   ├── lint-content.ts             # §4 — build fails on violation
│   ├── check-citations.ts          # DOI resolution
│   └── check-reg-sources.ts        # regulatory source URLs resolve + are archived
├── data/
│   └── purity/                     # assay results, CSV + JSON, one file per survey
└── .github/workflows/ci.yml
```

`data/` is the commons. It is published under CC-BY, it is complete without the website, and a fork of this repo with the site deleted should still be useful. Build for that.

---

## 3. The content contract

`src/content/config.ts` — Zod, enforced at build.

```ts
import { defineCollection, z } from 'astro:content';

const TIER = z.enum(['E1','E2','E3','E4','E5','E6','E7','E8']);
const SAFETY = z.enum(['S1','S2','S3','S4','S5']);

const evidence = z.object({
  indication: z.string(),
  tier: TIER,
  human_rcts: z.number().int().min(0),
  human_trials_any: z.number().int().min(0),
  registered_trials_total: z.number().int().min(0),
  registered_trials_reported: z.number().int().min(0),   // publication-bias denominator
  key_citations: z.array(z.string().regex(/^10\.\d{4,9}\//)).min(0),  // bare DOIs
  summary: z.string().max(900),
  last_reviewed: z.coerce.date(),
  reviewer: z.string(),
});

const regulatory = z.object({
  jurisdiction: z.enum(['US','EU','UK','CA','AU','JP','HN']),
  status: z.enum([
    'approved','investigational','unapproved',
    'excluded_from_supplement_definition','503a_category_2','503a_category_1',
  ]),
  detail: z.string(),
  source_url: z.string().url(),              // MANDATORY — primary regulator only
  source_retrieved: z.coerce.date(),
  archive_url: z.string().url(),             // MANDATORY — Wayback snapshot
});

export const collections = {
  compounds: defineCollection({
    type: 'content',
    schema: z.object({
      slug: z.string(),
      names: z.object({ inn: z.string().nullable(), common: z.array(z.string()), codes: z.array(z.string()), cas: z.string().nullable() }),
      sequence: z.string().regex(/^[ACDEFGHIKLMNPQRSTVWY-]*$/).nullable(),
      class_by_jurisdiction: z.record(z.enum(['A','B','C'])),   // NOT a single global class
      evidence: z.array(evidence).min(1),
      safety: z.object({
        grade: SAFETY,
        known_signals: z.array(z.object({ signal: z.string(), evidence: z.string(), citation: z.string() })),
        no_data_statement: z.boolean(),
      }),
      regulatory: z.array(regulatory).min(1),
      sport: z.object({ wada_status: z.enum(['prohibited','not_prohibited','monitored']), source_url: z.string().url() }),
      unknowns: z.array(z.string()).min(3),   // MANDATORY, min 3. The most valuable field on the page.
      reviewer: z.string(),
      last_reviewed: z.coerce.date(),
    }),
  }),
};
```

Three schema decisions carry real weight:

- **`class_by_jurisdiction` is a map, not a string.** PT-141 is bremelanotide (approved, Vyleesi) *and* a gray-market powder. Thymosin alpha-1 is approved in some countries, not others. A single global class field would force a lie on every page that has this problem, and several do.
- **`unknowns` has `.min(3)`.** You cannot ship a compound page without stating three things nobody knows about it. This is the single most differentiating field on the site and the schema makes it non-optional.
- **`registered_trials_total` vs `registered_trials_reported`.** Publication bias is the field's central pathology. Carrying both numbers makes it visible on every page without editorializing.

---

## 4. `lint-content.ts` — the rules that make this a reference work

Run in CI **and** as an Astro build integration. **Exit non-zero on any violation.** No warnings, no allowlist, no `// lint-disable`.

```ts
const RULES = [
  {
    id: 'no-dosing',
    // any mass/volume/frequency figure outside an approved-label quote block
    pattern: /\b\d+(\.\d+)?\s?(mg|mcg|µg|ug|g|iu|ml|cc)\b/gi,
    exempt: (ctx) => ctx.insideLabelQuote && ctx.hasLabelCitation,
    message: 'Dose figure outside a cited approved-label quote.',
  },
  {
    id: 'no-administration',
    pattern: /\b(reconstitut\w*|bacteriostatic|subcutaneous(ly)?|inject\w*|cycle|cycling|stack(ing|ed)?|titrat\w*|loading phase|protocol for)\b/gi,
    message: 'Administration guidance is prohibited.',
  },
  {
    id: 'no-purchase-intent',
    pattern: /\b(buy|purchase|where to (buy|get)|for sale|best (source|vendor)|legit|reputable (source|vendor)|coupon|discount code)\b/gi,
    scope: ['title','description','keywords','body','href'],
    message: 'Purchase-intent language or SEO.',
  },
  {
    id: 'no-vendors',
    // maintain an explicit denylist of known vendor domains; also flag ANY outbound
    // link not on the allowlist (pubmed, doi.org, fda.gov, ema.europa.eu, clinicaltrials.gov, wada, archive.org)
    check: (links) => links.filter(l => !ALLOWED_DOMAINS.includes(host(l))),
    message: 'Outbound link outside the primary-source allowlist.',
  },
  {
    id: 'no-second-person-advice',
    pattern: /\byou (should|can|could|may want to|might want to|will need to)\b/gi,
    message: 'The resource describes; it does not advise.',
  },
  {
    id: 'no-mechanism-as-benefit',
    pattern: /\b(promotes?|supports?|enhances?|boosts?|improves?|accelerates?|heals?|repairs?|restores?)\b/gi,
    exempt: (ctx) => ctx.insideCitedFinding,   // "X increased Y in [model] (ref)" is fine
    message: 'Benefit verb without a cited finding and a named model.',
  },
  {
    id: 'no-testimonials',
    pattern: /\b(before and after|my experience|users report|anecdotally|worked for me)\b/gi,
    message: 'Testimonial or anecdote.',
  },
  {
    id: 'no-affiliate',
    pattern: /(\?|&)(ref|aff|affiliate|utm_source=partner|tag)=/gi,
    message: 'Affiliate parameter.',
  },
];
```

Plus three structural checks:

- **`check-reg-sources.ts`** — every `regulatory[].source_url` must resolve (HTTP 200) **and** have a live `archive_url`. Regulatory status in this field is misreported constantly because people copy each other; the archive requirement means every claim on the site is pinned to a document you can produce.
- **`check-citations.ts`** — every DOI resolves. Fail on dead ones.
- **`check-staleness.ts`** — any compound whose `last_reviewed` is >12 months old renders a visible staleness banner. Not a silent decay.

**Also grep the built output**, not just the source. A dosing table that arrives via a component prop or an MDX import must fail too. Lint `dist/`, not `src/`.

---

## 5. Design system

**The subject's world is the certificate of analysis, not the medical blog.** Assay reports, chromatograms, vial labels, pharmacopoeial monographs. Cold, instrumental, measured. It should feel like a document produced by an instrument, not a page produced by a marketer — because that is precisely the distinction the whole project rests on.

Explicitly **not** the register of any competitor: no gradient hero, no stock photo of a vial in soft focus, no wellness-warm palette, no "unlock your potential" typography.

### Tokens (`src/styles/tokens.css`)

```css
:root {
  /* Surface — cool paper, not cream. This is a lab report, not a magazine. */
  --paper:      #F6F7F5;
  --paper-sunk: #ECEEEA;
  --ink:        #14161A;
  --ink-muted:  #5C6169;
  --rule:       #D5D8D2;

  /* Evidence tier ramp: KNOWLEDGE, not danger.
     Deliberately NOT red/green. E8 is "nobody knows", which is not "bad" —
     encoding it as red would be a lie the color scheme tells on every page. */
  --e1: #10504C;  --e2: #1B6B64;  --e3: #2F857B;
  --e4: #5D9C93;  --e5: #8AB2AB;  --e6: #A9BDB8;
  --e7: #BFC7C4;  --e8: #9AA0A6;   /* neutral grey — the null state */

  /* The ONLY warm/alert colour on the entire site. */
  --signal: #B4341F;   /* used exclusively for documented safety signals. Nothing else. */
}
```

**One colour, one meaning — enforce it.** `--signal` may appear only inside `SafetySignals.astro`. Add a CSS lint rule. The moment red is used for emphasis anywhere else, it stops meaning "there is a documented harm" and the site loses a channel it can't get back.

### Type

- **Display / headings: Archivo** — grotesque, institutional, documentary. Not editorial-warm.
- **Body: Source Serif 4** — technical long-form; designed to be read, not admired.
- **Data / utility: JetBrains Mono** — every number, tier code, CAS number, NCT ID, and amino acid sequence.

The **amino acid sequence is the site's typographic motif.** `GEPPPGKPADDAGLV` — set large, monospaced, letter-spaced, as the hero of every compound page. It's the compound's actual identity, it comes from the subject's own world, and it's the one thing on the page that no vendor blog thinks to lead with. Approved drugs get it. Gray-market chemicals get it. It's the great leveller: same treatment, same scrutiny, sequence first.

### Signature element — the Tier Ladder

`TierLadder.astro`. An eight-step instrument readout, E1 → E8, with the compound's position marked. Renders at the top of every compound page, above the name, and in miniature on every card in the index.

```
E1 ──── E2 ──── E3 ──── E4 ──── E5 ──── E6 ──── E7 ──── E8
                                         ▲
                              no human evidence
```

It is a **scale, not a badge**, because a badge invites the reader to see a rating and a scale forces them to see a position. It reads left-to-right from *established* to *unknown*, coloured on the teal→grey ramp. Per-indication, so a compound with three indications shows three ladders — which is itself the argument, because that's when the reader sees that the one indication it's marketed on is E6 and everything else is E8.

Accessibility: the ladder is never colour-alone. The tier code, the marker position, and a text label all carry the information. `prefers-reduced-motion` respected; no animation on the ladder at all.

---

## 6. The index page is the thesis

Do not build a search box and a list. Build **the grid**: every compound in the corpus, laid out as cards, **sorted by evidence tier**, with the tier ramp as the visual axis.

The honest headline of this entire resource — *most of these compounds have no human evidence* — should be visible in a single screen, without a word of argument, as a wall of grey E8 cards below a thin band of teal. Nobody has to be told. They can see it.

Filters: class (A/B/C), jurisdiction, tier, WADA status. No sort-by-popularity. No "trending." No "most searched." Those are engagement mechanics and they would quietly re-introduce the exact bias the site exists to remove.

---

## 7. Compound page — fixed order, no exceptions

The order **is** the argument. Hard-code it in the layout; don't let it be configurable.

1. Tier ladder(s)
2. Sequence (mono, large)
3. Names, CAS, class-by-jurisdiction
4. Regulatory table — with the mandatory standing notice for Class B/C
5. Human evidence — including, prominently, where there is none, and the registered-vs-reported trial denominator
6. Safety signals (the only place `--signal` red appears)
7. **What is unknown** — the `unknowns` list, rendered plainly and without hedging
8. Purity results, if any
9. Citations
10. Mechanism — **last, or omitted**

Mechanism goes at the bottom because a plausible mechanism reads like evidence to a non-specialist and costs nothing to assert. It is the vendor's favourite section for exactly that reason. Structural placement solves this permanently; editorial tone-policing does not.

---

## 8. Quality floor

- Static, no JS required for any content. Progressive enhancement only.
- Responsive to 360px. Keyboard focus visible. `prefers-reduced-motion` honoured.
- WCAG AA contrast — check the teal ramp's lighter steps (`--e6`, `--e7`) against `--paper`; darken them if they fail. The ramp serves accessibility, not the other way round.
- Print stylesheet. People will print monographs; let them.
- Every page has a `Last reviewed` date and a link to its source file on GitHub. Every page.
- COI disclosure and correction-log link in the global footer — not buried on an about page.

---

## 9. Build order

| # | Deliverable | Acceptance test |
|---|---|---|
| 1 | Zod schema + `lint-content.ts` + CI | A PR adding a dosing table to any compound **fails the build** |
| 2 | `check-reg-sources.ts` | A regulatory claim with no archived primary source fails |
| 3 | Tokens, type, `TierLadder.astro` | Ladder legible in greyscale and to a screen reader |
| 4 | Compound layout, fixed section order | Mechanism cannot be moved above evidence without editing the layout |
| 5 | 10 Class A monographs | Site launches as a reference work, not a peptide site |
| 6 | Index grid | The E8 wall is visible without scrolling |
| 7 | Class B tracker (retatrutide first) | Standing investigational notice renders on every Class B page |
| 8 | 20 Class C records | Most are E8. The grid shows it. |
| 9 | `/what-we-wont-tell-you`, COI, corrections, methods | Live **before** the first Class C page ships |
| 10 | Purity results template + `data/purity/` | Renders empty gracefully; ready for the first survey |

**Milestone 1 is the whole project.** If a PR containing a dosing table can be merged, every other guarantee on the site is a promise rather than a property, and promises erode under traffic pressure. Build the lint first, before a single page.
