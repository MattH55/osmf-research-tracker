# BUILD SPEC — Right-to-Try Disease & Asset Database (RTT-DB)

**Owner:** Open Source Medicine Foundation
**Schema:** `therapeutic_adequacy.v0.2.0.schema.json`
**Reference implementation:** `build_tal.py`
**Audience:** coding agent + human curator

---

## 0. What this is, in one paragraph

A versioned, open, computable layer that answers two questions no existing database answers:

1. **For a given disease, is there actually adequate therapy?** Not "does an approved drug exist" — that is a trivial join and it is *wrong* in the cases that matter. Parkinson's has 20+ approved drugs and zero disease-modifying therapy. Hepatitis C was incurable in 2013 and routinely curable in 2015. No ontology encodes this.
2. **For a given disease, what investigational assets can lawfully be accessed outside a clinical trial** — under federal Right to Try, and under Montana SB 535, which are *different sets*.

The output is two linked JSONL artifacts: an **asset registry** (drug-level) and a **disease frame** (disease-level).

---

## 1. THE THREE TRAPS — read before writing any code

These are not edge cases. Each one, gotten wrong, produces a database that is confidently and dangerously incorrect. A previous version of this pipeline shipped with trap #1 baked in.

### Trap 1 — RTT eligibility is a property of the DRUG, not the drug-indication pair

21 U.S.C. § 360bbb-0a(a)(2):

> the term "eligible investigational drug" means an investigational drug — **(A) for which a Phase 1 clinical trial has been completed**;

Full stop. **No indication qualifier.** Montana SB 535 uses the same construction ("has successfully completed phase 1 of a clinical trial").

**Implication:** the eligible pool is every drug with *any* completed Phase 1, in *any* indication, that is not FDA-approved and is in active development. A physician may certify such a drug for a life-threatening condition it has never been studied in. This is thousands of assets, not dozens.

**Therefore:** compute eligibility ONCE, drug-level, into a global registry. Do **not** compute it per disease. The disease record stores only `indication_supported_asset_ids` — the strict subset with Phase ≥1 evidence in that disease, which is *legally unnecessary but practically decisive* (see Trap 4, below, which is not a data trap but a reality trap).

### Trap 2 — Ex-US approval does NOT disqualify

Prong (B) excludes drugs "approved or licensed for any use under **section 355 of this title or section 351 of the Public Health Service Act**." Those are US statutes. Montana keys off "not yet been approved for general use by the **United States** Food and Drug Administration."

**Rintatolimod (Ampligen) is approved in Argentina and is a fully eligible investigational drug under both.**

Open Targets / ChEMBL `isApproved` is a **global** flag. Using it as the disqualifier will silently and wrongly shrink the pool. Any drug flagged `isApproved` must be cross-checked against the **FDA Orange Book** (small molecules) and **Purple Book** (biologics) before being excluded. Emit a `_needs_us_approval_check` queue.

### Trap 3 — "Completed Phase 1" is a legal checkbox, not a safety statement

21 CFR 312.21(a)(1): Phase 1 studies "may be conducted in **patients or normal volunteer subjects**."

An oncology Phase 1 is a dose-escalation that *by construction* titrates upward until it finds unacceptable toxicity, in patients with terminal disease, with risk-benefit calibrated against imminent death. Its MTD is **not** a safety finding transferable to a severely disabled but non-dying ME/CFS patient. A healthy-volunteer SAD/MAD study transfers reasonably well. These two things carry the identical database flag `max_phase >= 1`.

**Therefore:** every asset record carries a `phase1` block (`population`, `design`, `dlt_observed`, `route`, `chronic_dosing_studied`) and a curated `safety_transferability` block including `population_risk_calibration_mismatch`. These are **not derivable from Open Targets**. They must be extracted from the ClinicalTrials.gov record of the earliest-phase trial. Default them to `unknown` — never to a permissive value.

**This block is the single most important contribution of the whole project.** It is what distinguishes a defensible access framework from a green light.

### Trap 4 (not a data trap, a reality trap) — the sponsor is the actual gate

The statute grants sponsors complete immunity for **refusing** access: "No liability shall lie against a sponsor... for its determination not to provide access." They bear all the downside of yes and none of the downside of no. A sponsor running Phase 2 in oncology has every incentive to refuse a cross-indication request, because an AE in an unstudied population lands in their safety database and can trigger a clinical hold on the program they actually care about.

**Therefore:** `sponsor_supply_posture` is a first-class field. A database of legally-eligible-but-unobtainable assets is a database of nothing. Note the double edge on `existing_expanded_access`: it proves willingness, but an open EAP can *defeat* the federal patient prong ("unable to participate in a clinical trial"). Montana has **no patient gate at all**, so it is pure upside there.

---

## 2. Data sources

| Source | Use | Access |
|---|---|---|
| **Open Targets Platform** (parquet bulk) | disease ontology, drug-indication-phase, molecule metadata | `s3://open-targets-data-releases/<REL>/output/` `--no-sign-request` |
| **ClinicalTrials.gov / AACT** | Phase 1 population & design (Trap 3); active-trial counts (federal patient prong); trial geography | free Postgres, `aact-db.ctti-clinicaltrials.org` |
| **FDA Orange Book / Purple Book** | US-specific approval (Trap 2) | FDA bulk downloads |
| **NLM MED-RT** | `may_treat` relations; independent cross-check on `has_approved_therapy` | NLM download |
| **Orphanet / Orphadata** | prevalence, rare-disease flag | free XML |
| **NCATS GARD** | rare disease backbone; source of the "~95% of rare diseases have no FDA-approved treatment" figure | API |
| **IHME GBD** | DALYs, for prioritising the curation queue | download |
| **MONDO** | canonical disease id; everything joins on this | OBO |

⚠️ Open Targets **renames dataset directories between releases** (`knownDrugsAggregated` → `known_drug`, `molecule` → `drug_molecule`). A wrong path yields an **empty frame, not an error**. Fail loudly on missing datasets. See `DATASET_ALIASES` in the reference implementation.

---

## 3. Pipeline

```
stage 0  ingest       sync OT parquet; pull AACT, Orange/Purple Book, MED-RT, Orphadata, GBD
stage 1  assets       drug-level registry -> assets.jsonl        [Traps 1, 2]
stage 2  us_approval  Orange/Purple Book join; resolve _needs_us_approval_check queue
stage 3  phase1       AACT join: extract Phase 1 population/design/DLT -> fills phase1 block  [Trap 3]
stage 4  diseases     disease-level frame -> diseases.jsonl; link indication_supported_asset_ids
stage 5  enrich       MED-RT cross-check, prevalence, DALYs, active-trial counts
stage 6  curate       LLM draft -> human verify; the fields no database contains
stage 7  validate     every record against the JSON Schema; CI-gated
stage 8  publish      versioned release, CC-BY-4.0, DOI via Zenodo
```

### Stage 1 — asset registry

Emit one record per drug with `max_phase >= 1` in any indication.

```
federal_rtt_eligible :=
      phase1_completed
  AND NOT approved_in_us                                  # Trap 2 — US only
  AND NOT withdrawn
  AND regulatory_status IN (nda_bla_filed, active_ind_pivotal_trial)
  AND NOT clinical_hold

montana_eligible :=
      phase1_completed
  AND NOT approved_in_us
  AND NOT withdrawn
  AND ( under_investigation_for_fda_approval
        OR demonstrated_safety_record )                   # <-- the disjunct that matters

montana_only := montana_eligible AND NOT federal_rtt_eligible
```

`demonstrated_safety_record` is **not computable**. Emit `null` and route to curation.

**`montana_only` is the highest-value output of this entire build.** It is the set of assets that cleared Phase 1, are not FDA-approved, have a safety record, and were **abandoned** — dead under federal RTT (which demands active development), alive under SB 535. Canonical example: **BC 007 / rovunaptabin** — Phase 2 missed its primary endpoint, the sponsor stated the data suggest the drug is safe and well tolerated, Berlin Cures GmbH went insolvent, IP moved to APTA Therapeutics. Efficacy failure and safety record are **orthogonal**; the schema must not conflate them.

Sort the curation queue by `montana_only DESC, cumulative_human_exposure DESC`.

### Stage 3 — Phase 1 characterisation (Trap 3)

For each asset, find the lowest-phase interventional trial in AACT and extract:

- `population` ← healthy volunteers vs patients (check `studies.healthy_volunteers`, eligibility criteria text, and whether the enrolled condition equals the target indication)
- `design` ← flag `mtd_dose_escalation` on any of: "maximum tolerated dose", "dose escalation", "3+3", "dose-limiting toxicity" in title/description/outcome measures
- `dlt_observed` ← from results section where posted; else `null`
- `route`, `chronic_dosing_studied` ← intervention description + duration

Then derive, per (asset, target_indication) pair:

```
population_risk_calibration_mismatch :=
      phase1.design == mtd_dose_escalation
  AND phase1.population == patients_other_indication
  AND target_disease.lethality NOT IN (rapidly_fatal, life_shortening)
```

**When this is TRUE, the record must not be presented as an access opportunity without a prominent warning.** This is the case where an oncology MTD is being extrapolated to a non-dying patient. Hard-code the guard; do not leave it to the consumer.

### Stage 4 — disease frame

Everything in MONDO. Key fields: `has_approved_therapy` (= `phase_4 > 0`), `indication_supported_asset_ids`, and:

```
rtt_practical_actionability :=
    indication_supported   if >=1 eligible asset studied in this disease
    global_only            if none studied here (legally reachable; sponsors will refuse)
    none                   if no eligible asset exists at all
```

`--untreated-only` filters to `has_approved_therapy == false` — that is the "diseases without a current drug" view.

### Stage 6 — curation

The fields no database on earth contains. LLM-drafts from label text, guidelines, and Cochrane reviews; **human verifies**; `curation_meta.method` records which.

- `curability` — curable_routinely / curable_in_subset / durable_remission_achievable / not_curable_modifiable / not_curable_unmodifiable
- `therapy_intent` — **the flagship field.** Ceiling of what best approved therapy achieves. Parkinson's = `symptomatic_only` despite 20+ phase-4 drugs.
- `lethality` — drives the federal patient gate (21 CFR 312.81). `non_fatal_severely_disabling` FAILS federal RTT, may satisfy the "severely debilitating" gate in Right-to-Try 2.0 statutes, and is **irrelevant in Montana**, which removed patient eligibility entirely in SB 422 (2023).
- `soc_staleness_years` — years since the SoC *meaningfully* changed. A me-too approval does not reset this clock.
- `demonstrated_safety_record` (asset), `safety_transferability` (asset × indication)

Prioritise the queue by `GBD DALYs × (NOT has_approved_therapy)`, then by whether any `montana_only` asset touches the disease.

---

## 4. Validation & acceptance criteria

CI must fail on any of the following:

- [ ] Any record fails the JSON Schema.
- [ ] `has_approved_therapy == true` but `n_drugs_by_phase.phase_4 == 0` (internal inconsistency).
- [ ] Any asset with `eligibility.approved_in_us == true` that has not passed the Orange/Purple Book check.
- [ ] Any asset with `federal_rtt_eligible == true` but `montana_eligible == false` (**impossible** — Montana is strictly broader; a violation means the logic is inverted somewhere).
- [ ] Any asset presented in an "access" view with `phase1.population == unknown`.
- [ ] Any (asset, disease) pair with `population_risk_calibration_mismatch == true` surfaced without the warning flag.
- [ ] Any `curated` field with `curation_meta.method == llm_draft_unverified` published in a release build.

**Regression fixtures** — these three must round-trip correctly, because each breaks a different naive assumption:

| Fixture | Breaks |
|---|---|
| **Parkinson's disease** | 20+ phase-4 drugs, `therapy_intent = symptomatic_only`. Breaks "approved drug ⇒ treated." |
| **Chronic hepatitis C** | `curability` moved to `curable_routinely` in ~2014. Breaks "curability is static" — hence versioning. |
| **Rintatolimod** | approved in Argentina, `approved_in_us = false`, `federal_rtt_eligible = true`. Breaks `isApproved` as a disqualifier. |
| **BC 007** | failed Phase 2, sponsor insolvent, `montana_only = true`. Breaks "efficacy failure ⇒ ineligible." |
| **PACVS** | `rtt_practical_actionability = none`. Breaks "there is always an asset." |

---

## 5. Known honest limitations — publish these

1. **Open Targets phase is not a completion flag.** `phase = 1` means a Phase 1 exists, not that it finished cleanly. Cross-check `status = Completed` in AACT.
2. **Devices are out of scope for federal RTT** (drugs and biologics only) but **in scope for Montana SB 535**, which covers "device or other treatment." Immunoadsorption columns and apheresis devices are a real, under-examined door. Open Targets does not cover devices at all — a separate GUDID/510(k)/CE-mark source is needed. **This is currently a gap.**
3. `demonstrated_safety_record` is a judgment call with no agreed standard. Ours is: published safety data from ≥1 completed trial, no program-halting toxicity, and cumulative exposure documented. Say so.
4. Montana SB 535 is **not an IND pathway.** Data generated under it is real-world evidence, not registrational. This database describes what is *lawful*, not what is *evidence-generating*. Do not let consumers confuse the two.
5. SB 535's adverse-event reporting standard was left to DPHHS rulemaking (draft rules April 2026). Until those land, there is no AE denominator for anything administered under it — which is precisely the gap an OSMF registry would fill.

---

## 6. Deliverables

```
out/
  assets.jsonl              drug-level RTT eligibility registry
  diseases.jsonl            disease-level therapeutic adequacy
  montana_only.jsonl        the abandoned-but-safe set — curate first
  untreated.jsonl           has_approved_therapy == false
  needs_us_approval_check.csv
  curation_queue.csv        DALY-weighted
  MANIFEST.json             source versions, row counts, generated_at
```

Release as CC-BY-4.0 with a Zenodo DOI. Version the *curated* layer independently of the *computed* layer: computed regenerates on every Open Targets release; curated is human capital and must not be silently overwritten.
