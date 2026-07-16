# Medical freedom by jurisdiction — arbitrage map schema

A build-ready data model for a "pick a procedure → see where it's accessible, by what pathway, at what price, under what oversight" map. Written as a schema sketch, not final DDL — field names are indicative.

---

## 0. The one architectural decision

**This is not a separate system from the therapeutic-adequacy layer (TAL). It is a superset of it.**

The TAL answers: *for condition C, in jurisdiction J, is there an adequate approved option?* That is exactly the arbitrage map restricted to one jurisdiction and filtered to cells where the answer is "no." Formally, "diseases without treatment in J" is the projection:

```
TAL(J) = arbitrage_map WHERE jurisdiction = J AND best_accessible_option = none
```

So you don't build a parallel map. You **extend the TAL's condition/intervention tables to carry a `procedure × jurisdiction` join**, and the diseases-without-treatment view becomes one query against it. The arbitrage map is the general case; the TAL is the origin-jurisdiction, no-option slice. Everything below assumes you're growing the existing schema, not starting a new one.

---

## 1. Procedure taxonomy (the row axis)

The trap is treating "medical freedom" as one axis. No jurisdiction is uniformly free — Switzerland is open on assisted dying and ordinary on stem cells; Oregon is open on psilocybin and ordinary on biologics; Próspera is wide-open on gene therapy and peptides but tiny. A single "freedom score" per jurisdiction is noise.

The fix: organize procedures by **regulatory modality** — *what the thing is legally*, because that determines which regulatory regime applies and therefore where jurisdictions diverge. Then tag a secondary **restriction driver** — *why* it's restricted — which controls what a permissive jurisdiction actually has to change.

### Primary axis — `modality`

- `small_molecule_approved` — on-label approved drugs (arbitrage here is price/availability, not legality)
- `small_molecule_offlabel` — approved drug, unapproved indication (RepurpOS territory)
- `small_molecule_compounded` — compounded/pharmacy-prepared
- `small_molecule_unapproved` — not approved in this jurisdiction; access via import/RTT/trial
- `controlled_substance` — psychedelics, ibogaine, ketamine, cannabis, scheduled peptides
- `cell_therapy_autologous` — patient's own cells (legally distinct — often lighter regime)
- `cell_therapy_allogeneic` — donor cells (usually full biologic regime)
- `gene_therapy` — including enhancement/longevity constructs (the Próspera cases)
- `peptide` — regulatorily liminal; sits between drug, compounded, and supplement
- `blood_product_apheresis` — apheresis, exosomes, plasma-derived
- `device_procedure` — surgical/diagnostic/interventional
- `reproductive` — IVF, PGD, surrogacy, mitochondrial replacement (huge variance)
- `end_of_life` — assisted dying / euthanasia (huge variance)
- `nutraceutical_natural` — supplements, botanicals ("medicine you can grow")

### Secondary tag — `restriction_driver`

`safety_unproven` · `controlled_substance` · `ethics_contested` · `cost_or_licensing` · `import_barrier` · `none`

The driver tells you the *shape* of the arbitrage. A `safety_unproven` cell moves when a jurisdiction passes an RTT/medical-freedom law; a `controlled_substance` cell moves on scheduling; an `ethics_contested` cell (surrogacy, euthanasia) rarely moves and splits on values, not evidence.

---

## 2. Jurisdiction model (the column axis)

Jurisdictions **nest**, and this is not optional — US psychedelics are city-decriminalized under state-illegal under federal-illegal; Próspera is a ZEDE under Honduras. A flat country list gives wrong answers.

```
JURISDICTION
  id            uuid  PK
  parent_id     uuid  FK -> JURISDICTION   (null for sovereign)
  level         enum {supranational, sovereign, subnational, special_zone, municipal}
  name          string
  iso_region    string
```

`special_zone` covers ZEDEs (Próspera), charter cities, free zones (Dubai Healthcare City), and the like — the cells where the interesting arbitrage lives.

**Status resolution up the stack.** A cell's *effective* status is computed by walking `parent_id`. A procedure "legal" at municipal level but Schedule I federally is, in practice, `decriminalized_no_supply` — enforcement risk, no legal supply chain. Store the status at the level where it's set; resolve effective status at query time. Don't denormalize a single status onto the leaf — you'll get it wrong the first time a federal reschedule happens.

---

## 3. The AccessCell (the join — where the value is)

One row per `procedure × jurisdiction`. This is the heart; everything else is a lookup.

### Legal / regulatory
- `legal_status` — enum, see §4. The single most important field.
- `access_pathway` — enum, see §4. *How* you actually get it. A cell can be "not approved" yet fully accessible via RTT — legality alone is useless without pathway.
- `regulatory_authority` — governing body (FDA, EMA, COFEPRIS, Honduras/ZEDE authority…)
- `legal_basis` — statute/regulation/guidance citation → provenance, not prose
- `eligibility` — json: `{ residency_required, diagnosis_gate (any|chronic|terminal), age_min, prior_failure_required, referral_required }`. Eligibility is what kills most arbitrage — many pathways are gated to citizens or to terminal diagnoses.

### Practical (the arbitrage math)
- `price_local` + `price_usd` (normalized) + `price_basis` enum {cash_pay, insured, trial_free}
- `price_confidence` enum {quoted, estimated, unknown}
- `travel_friction` — json: `{ visa, min_stay_days, language }`
- `total_access_cost_usd` — derived: procedure + travel + stay

### Quality / risk (the anti-scam column)
- `oversight_quality` — enum {regulated_high, regulated_moderate, self_regulated, minimal, none}. Without this, an access map is just a directory of places to get exploited — which is precisely how the academic literature reads every existing medical-tourism resource.
- `known_risk_flags` — array
- (evidence lives on `PROC_INDICATION`, not here — see §5)

### Provenance / freshness (the thing that kills static maps)
- `last_verified` — date
- `verified_by` — source/agent
- `source_ids` — FK array -> SOURCE
- `confidence` — enum {high, moderate, low}
- `volatility` — enum {stable, pending_legislation, active_flux}. A static map is worse than nothing because people act on stale cells; `volatility` tells the UI which cells to re-check and which to caveat hard.

---

## 4. Controlled vocabularies

### `legal_status`
```
approved_on_label          approved for this indication here
approved_off_label         approved drug, this use is off-label
permitted_expanded_access  compassionate/named-patient/special access
permitted_rtt              accessible via right-to-try statute
clinical_trial_only        only inside an approved trial
physician_discretion_gray  practiced under discretion; unsettled
unregulated_permitted      legal and effectively unregulated
decriminalized_no_supply   penalties reduced; no legal supply chain
prohibited                 banned
unknown                    not yet researched
```

### `access_pathway`
```
standard_prescription · off_label_prescription · compounding · expanded_access
right_to_try · clinical_trial_enrollment · personal_import · licensed_provider_regime
medical_tourism_cash · none
```

`legal_status` and `access_pathway` are separate on purpose. "Not approved" + `right_to_try` is accessible; "approved" + `none` (supply gap) is not. The pair is the cell's real state.

---

## 5. Linking to demand (condition + evidence)

```
CONDITION            id, name, icd_code, tal_status_by_jurisdiction (view)
PROC_INDICATION      id, procedure_id FK, condition_id FK, evidence_grade
```

`evidence_grade` lives on the procedure–condition pair, **not** on the AccessCell — a stem-cell therapy has the same evidence base whether delivered in Tijuana or Tokyo; only its legal/price/oversight cell differs by place. This is where RepurpOS evidence plugs in.

An AccessCell becomes *arbitrage-interesting* when its procedure treats a condition that is therapeutically inadequate (per TAL) in some **other** jurisdiction whose residents can satisfy this cell's `eligibility`.

---

## 6. Arbitrage is a derived view, not a stored field

Don't store "arbitrage." Compute it. Given a patient's home jurisdiction `J_home` and condition `C`:

1. `procedures = PROC_INDICATION WHERE condition = C AND evidence_grade >= threshold`
2. `cells = ACCESS_CELL WHERE procedure IN procedures AND effective_status(cell) IN accessible_set AND eligibility_satisfiable_by(J_home resident)`
3. filter `cells WHERE oversight_quality >= min_quality`
4. rank by `total_access_cost_usd`
5. **arbitrage spread** = best accessible option elsewhere vs. the `J_home` option. When the home option is `none`, the spread is infinite — and that row *is* a TAL entry. Same query, different `J_home`.

The elegance: the diseases-without-treatment database falls out of this as the `J_home`, `best = none` special case. Build the general engine; the TAL is a saved filter on it.

---

## 7. Worked example

Procedure: **dental-pulp stem-cell "SGF" + apheresis** (the McCairn–Edogawa protocol), `modality = cell_therapy_autologous` (SGF) coupled with `blood_product_apheresis`, `restriction_driver = safety_unproven`. Treats a PACVS-type condition currently in the TAL as inadequately-treated in most jurisdictions.

| jurisdiction (level) | legal_status | access_pathway | eligibility | oversight_quality | volatility |
|---|---|---|---|---|---|
| Japan / Edogawa (sovereign) | `physician_discretion_gray` | `licensed_provider_regime` | referral, travel | regulated_moderate | stable |
| US federal | `clinical_trial_only` (SGF) | `clinical_trial_enrollment` | — | regulated_high | stable |
| Montana (subnational) | `permitted_rtt` (pending DCT) | `right_to_try` | chronic/terminal gate | regulated_moderate | pending_legislation |
| Próspera ZEDE (special_zone) | `unregulated_permitted` | `licensed_provider_regime` | contract-based | self_regulated | active_flux |

The apheresis component resolves separately — `approved_on_label` + `standard_prescription` in the US — which is exactly the kind of split the modality tagging is built to capture: half the protocol is freely accessible at home, only the SGF half needs an arbitrage jurisdiction. That decomposition is the actionable insight, and it only appears because procedures are typed by modality rather than lumped as one "treatment."

---

## 8. Build & maintenance notes

- **Maintenance is the real risk, not data acquisition.** The psychedelic trackers (Psychedelic Alpha, UC Berkeley BCSP) work because a law firm and an academic center feed them continuously. A static snapshot decays fastest exactly where it's most valuable — the `active_flux` cells. Budget for a verification loop keyed on `volatility` before you budget for coverage breadth.
- **Lead with `oversight_quality`, not coverage.** An OSMF-branded map will be read by the same community that treats "access map" as "scam directory." The oversight column being rigorous and prominent is what separates this from clinic lead-gen.
- **Seed narrow, prove the vertical.** One modality done well (peptides, or autologous cell therapy) beats fourteen done shallowly — same lesson the psychedelic verticals demonstrate.
- **Próspera is a primary source.** For the `special_zone` and gene-therapy/peptide cells, you have on-the-ground visibility the academic reviewers lack. That's a genuine data moat for those rows.
