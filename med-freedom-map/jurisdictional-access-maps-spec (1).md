# Build Spec — Jurisdictional Medical Access Maps

**Working name:** medical freedom maps
**Sits with:** Right to Try resource, hospital price tracker
**Property:** new sub-brand front door; shared infrastructure with opensourcemed.info
**Status:** build spec for coding agent

---

## 0. Editorial posture (read first — everything else follows from this)

This resource **aggregates and joins existing tracked sources. It does not perform primary legal research and does not state what the law is.**

Consequences, all binding:

- Every displayed value carries a citation, a source, and a verification date. A value without provenance is a build error, not a warning.
- Where a secondary tracker (NCSL, CCHP, FSMB) is the source, cite the tracker — not the underlying statute — unless a statute has been read directly and logged as `source_type: primary_statute`.
- Never mirror a third-party dataset. Store the derived value plus a link. Several sources below prohibit redistribution; check each one's terms before ingest and record the outcome in the source registry.
- Stale is displayed as stale. A greyed cell reading "last verified 2025-03" is correct behaviour; a confident green checkmark on unverified data is the failure this whole spec exists to prevent.
- Site-wide notice: informational aggregation, not legal or medical advice, verify with counsel before acting.

**The unique value is the join across layers**, not any single layer. Nobody else places telehealth licensure beside compounding rules beside scope of practice beside price. Compete there.

---

## 1. Data model

One record per `(jurisdiction, layer, dimension)`. Flat files, PR-based contribution, CI-validated — same pattern as the PAIS cohort database.

```yaml
# /data/cells/US-MT/right_to_try.yaml
jurisdiction: US-MT              # ISO 3166-2, or ISO 3166-1 for national tier
layer: right_to_try
dimensions:
  - id: rtt_enacted
    value: true
    citation: "Mont. Code Ann. § 50-XX-XXX"
    source_id: goldwater_rtt
    source_url: https://...
    source_type: primary_statute      # primary_statute | secondary_tracker | agency_guidance
    verified_on: 2026-07-15
    verified_by: mhalma
    confidence: high                  # high | medium | derived
    note: "SB 535 (2023) expands beyond baseline RTT."
```

```yaml
# /schemas/layer-registry.yaml — the controlled vocabulary
layers:
  - id: scope_of_practice
    label: "Scope of practice"
    review_cadence_days: 365
    dimensions:
      - {id: np_practice_authority, type: enum, values: [full, reduced, restricted]}
      - {id: pa_collaboration_required, type: bool}
      - {id: naturopath_licensed, type: bool}
      - {id: naturopath_prescriptive_authority, type: enum, values: [none, limited, full]}
      - {id: cpm_midwife_licensed, type: bool}
      - {id: pharmacist_prescribing, type: enum, values: [none, protocol, independent]}

  - id: licensure_compacts
    review_cadence_days: 180
    dimensions:
      - {id: imlc_status, type: enum, values: [participating, enacted_not_implemented, pending, none]}
      - {id: nlc_status, type: enum, values: [participating, pending, none]}
      - {id: psypact_status, type: enum, values: [participating, pending, none]}
      - {id: compact_effective_date, type: date}

  - id: certificate_of_need
    review_cadence_days: 365
    dimensions:
      - {id: con_program_exists, type: bool}
      - {id: services_regulated_count, type: int}
      - {id: hospital_beds_regulated, type: bool}
      - {id: imaging_regulated, type: bool}
      - {id: asc_regulated, type: bool}

  - id: right_to_try
    review_cadence_days: 365
    dimensions:
      - {id: rtt_enacted, type: bool}
      - {id: rtt_year, type: int}
      - {id: individualized_rtt, type: bool}
      - {id: manufacturer_liability_shield, type: bool}
      - {id: insurer_coverage_required, type: bool}

  - id: regenerative_medicine
    review_cadence_days: 365
    dimensions:
      - {id: unapproved_cell_therapy_permitted, type: bool}
      - {id: disclosure_requirement, type: bool}
      - {id: practitioner_scope_limit, type: text}
      - {id: statute_ref, type: text}

  - id: off_label_prescribing
    review_cadence_days: 270
    dimensions:
      - {id: board_discipline_protection, type: bool}
      - {id: pharmacist_refusal_to_fill_protection, type: bool}
      - {id: pharmacist_refusal_prohibited, type: bool}
      - {id: statute_era, type: enum, values: [pre_2020, 2020_2023, post_2023, none]}

  - id: direct_primary_care
    review_cadence_days: 365
    dimensions:
      - {id: dpc_statute_exists, type: bool}
      - {id: declared_not_insurance, type: bool}

  - id: vaccine_exemption
    review_cadence_days: 270
    dimensions:
      - {id: medical_exemption, type: bool}
      - {id: religious_exemption, type: bool}
      - {id: philosophical_exemption, type: bool}
      - {id: exemption_process, type: enum, values: [form, notarized, provider_signature, education_module, none]}

  - id: telehealth
    review_cadence_days: 120          # highest volatility — see §3
    dimensions:
      - {id: modality_neutral, type: bool}
      - {id: audio_only_permitted, type: bool}
      - {id: relationship_established_via_telehealth, type: bool}
      - {id: out_of_state_registration_pathway, type: bool}
      - {id: controlled_substance_posture, type: enum, values: [federal_baseline, stricter]}

  - id: compounding
    review_cadence_days: 180
    dimensions:
      - {id: office_use_permitted, type: bool}
      - {id: out_of_state_pharmacy_license_required, type: bool}
      - {id: state_503b_registration_required, type: bool}
      - {id: anticipatory_compounding_limit, type: text}

  - id: price_transparency
    review_cadence_days: 180
    dimensions:
      - {id: state_law_beyond_federal, type: bool}
      - {id: enforcement_mechanism, type: text}
    joins: hospital_price_tracker     # see §6
```

---

## 2. Source registry

`/data/sources.yaml`. Nothing gets ingested without an entry here.

```yaml
- id: ncsl
  name: National Conference of State Legislatures
  covers: [vaccine_exemption, certificate_of_need, right_to_try]
  format: html
  ingest: manual
  terms_reviewed: PENDING
  redistribution_permitted: PENDING

- id: cchp
  name: Center for Connected Health Policy — State Telehealth Laws
  covers: [telehealth]
  format: pdf_biannual
  ingest: manual
  cadence: biannual
  note: "Authoritative but goes stale between editions. Do not treat edition date as verification date."

- id: fsmb
  covers: [telehealth, off_label_prescribing]
- id: aanp_state_practice
  covers: [scope_of_practice]
- id: aapa_state_law
  covers: [scope_of_practice]
- id: dpc_frontier
  covers: [direct_primary_care]
- id: mercatus_con
  covers: [certificate_of_need]
  format: csv
- id: alliance_pharmacy_compounding
  covers: [compounding]
- id: nabp_state_boards
  covers: [compounding, scope_of_practice]
- id: imlc_official / nlc_ncsbn / psypact_official
  covers: [licensure_compacts]
  note: "Official compact member lists are primary. Prefer over aggregators."
- id: immunize_org
  covers: [vaccine_exemption]
- id: goldwater_rtt
  covers: [right_to_try]
- id: legiscan
  covers: [ALL]
  format: api
  role: change_detection_only          # never a value source
- id: cms_hospital_transparency
  covers: [price_transparency]
  role: joins to hospital price tracker
```

Every entry needs `terms_reviewed` resolved to a date and `redistribution_permitted` to true/false before that source can be used in a build. CI fails on `PENDING`.

---

## 3. Refresh and verification pipeline

**Change detection (automated, nightly).**
LegiScan (or Open States) API watcher, one keyword set per layer per state. Any matching bill introduced, amended, or enacted opens a GitHub issue tagged `layer:<id>` `state:<code>` with the bill text link. This never writes a value — it only queues human review.

**Source-edition watcher (automated, weekly).**
HTTP HEAD/content-hash check on each source registry URL. Change in hash → issue tagged `source-updated`.

**Verification sweep (manual, per-layer cadence).**
Each layer's `review_cadence_days` drives a scheduled job that lists cells past due. Reviewer updates `verified_on` even when the value is unchanged — re-verification is the product.

**Confidence rendering:**

| Age vs cadence | State | Display |
|---|---|---|
| < 100% | `current` | Normal |
| 100–150% | `aging` | Normal + "last verified {date}" |
| > 150% | `stale` | Greyed, value hidden behind a click, banner |
| No citation | `invalid` | Never rendered; build error |

**Corrections.** Public "suggest a correction" on every cell, opening a pre-filled GitHub issue requiring a citation URL. Same PR workflow as the cohort database. Publish a `/corrections/` log — visible correction history is a credibility asset, not an embarrassment.

---

## 4. Page templates

```
/maps/                                        # index, all layers
/maps/<layer-slug>/                           # T1: layer hub, national map
/maps/<layer-slug>/where-<dimension-slug>/    # T2: list page  ← highest SEO value
/maps/<layer-slug>/<state-slug>/              # T3: leaf
/states/<state-slug>/                         # T4: state hub, all layers
/compare/                                     # noindex, tool only
```

**T2 is the priority build.** These match how people search, there are ~30 of them rather than 550, and they're the pages that get cited and linked.

```
T1  <title>{Layer} by State — 2026 Map | {Brand}</title>
    <h1>{Layer}: state-by-state</h1>

T2  <title>Which States {Dimension Phrase}? (Updated {Month Year})</title>
    <h1>States where {dimension phrase}</h1>
    Body: count + interactive map + sortable table + methodology + per-state links

T3  <title>{Layer} in {State} — Requirements & Citations | {Brand}</title>
    <h1>{Layer} in {State}</h1>
    Body: value table w/ citations, verification dates, neighbouring-state
          comparison, links to other layers for this state

T4  <title>Healthcare Access Laws in {State}: Full Profile | {Brand}</title>
```

Every T3/T4 page cross-links to the same state in the hospital price tracker and, where relevant, the RTT resource. That join is the whole product thesis — make it structural, not incidental.

**Thin-content gate.** T3 pages emit `noindex,follow` unless the state has ≥60% of that layer's dimensions populated and current, plus ≥150 words of non-templated prose. T4 requires ≥4 populated layers.

**JSON-LD.** `BreadcrumbList` everywhere. `Dataset` on T1 and T2 (with `spatialCoverage`, `temporalCoverage`, `license: CC BY 4.0`, `DataDownload` to the CSV export). `FAQPage` on T3 for the two or three questions the state's cells actually answer. Validate in CI.

---

## 5. Embed component (the backlink engine)

The highest-leverage distribution asset in this build. Treat it as a first-class product.

- `<script src="https://{brand}/embed.js" data-layer="..." data-dimension="...">` rendering an interactive choropleth in a shadow DOM.
- **Attribution link is non-removable** and is a real `<a href>` with descriptive anchor text — this is what makes embeds worth building.
- Embeds pull live data, so anyone who embeds it stays current and you stay in front of their audience.
- One-click "Embed this map" on every T1 and T2 page, with a copy-paste snippet and a preview.
- Log embed referrers to `/analytics/embeds` — this is your outreach list.
- Ship a static PNG/SVG fallback for newsletters and print.

Outreach targets once live: state-level advocacy orgs, medical tourism operators, DPC practice directories, patient groups, and state-policy journalists ahead of legislative sessions.

---

## 6. Cross-property joins

- **Hospital price tracker:** `price_transparency` layer links each state's legal posture to actual observed price data. "This state requires X; here's what hospitals actually charge" is a story no one else can tell.
- **Right to Try resource:** `right_to_try` and `regenerative_medicine` layers are the RTT resource's map view. Same data, two front doors.
- **International tier (Phase 4):** national-level records for Honduras/Próspera, Mexico, Costa Rica, Japan, Bahamas, El Salvador, Switzerland, UAE — joined to medical tourism pricing. Smaller dimension set (treatment availability, practitioner licensure recognition, import rules, malpractice regime). This is where the resource stops being a US policy map and becomes a decision tool.

---

## 7. Build order

| Phase | Scope | Gate |
|---|---|---|
| 0 | Schema, source registry with terms resolved, CI validation, correction workflow | No `PENDING` sources |
| 1 | Three low-volatility layers: `scope_of_practice`, `licensure_compacts`, `certificate_of_need` | 50 states populated, ≥90% current |
| 2 | T2 list pages + embed component for Phase 1 layers | ≥5 external embeds live |
| 3 | `right_to_try` + `regenerative_medicine` + `direct_primary_care` | Verification sweep completed once on schedule |
| 4 | `off_label_prescribing`, `vaccine_exemption`, `price_transparency` | — |
| 5 | `telehealth`, `compounding` — highest maintenance, ship last | Sweep cadence demonstrably held for 2 cycles |
| 6 | International tier + medical tourism join | — |
| 7 | Annual composite index + ranked report | — |

Phase 1 is deliberately the politically neutral, well-sourced, high-volume material. It proves the pipeline and earns domain trust before anything contested ships.

**Do not start Phase 5 until the verification sweep has run on schedule twice.** Telehealth and compounding will make you look wrong faster than any other layer.

---

## 8. CI gates

- Every dimension value has `citation`, `source_id`, `source_url`, `verified_on`, `source_type`. Missing → build fails.
- `source_id` resolves to a registry entry with `terms_reviewed` set. Unresolved → build fails.
- No layer ships with >20% `stale` cells.
- No orphan pages; every T3 has ≥3 inbound internal links.
- No duplicate `<title>` or meta description across the corpus.
- JSON-LD validates.
- Slug and jurisdiction codes conform to the pinned vocabulary.

---

## 9. Measurement

Weekly snapshots to `/metrics/`:
- GSC impressions/clicks/position, segmented by template (T1–T4).
- Embed count and referring domains — the primary KPI for Phase 2.
- Correction submissions received and resolution time.
- Percentage of cells `current` per layer — the health metric that governs whether to add layers or maintain existing ones.

**Stop-adding-layers rule:** if any shipped layer drops below 80% `current`, no new layer ships until it recovers. Breadth without maintenance is the failure mode for this entire category of resource.
