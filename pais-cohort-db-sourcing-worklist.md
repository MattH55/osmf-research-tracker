# PAIS Cohort Database — sourcing worklist for a coding agent

A research-sourcing brief for an agent tasked with **growing** the cohort database toward full
coverage of infection-associated (and closely-related) chronic conditions. This is the *what to
find* companion to `pais-cohort-db-expansion-guide.md` (the *how to add a record* manual). Read
that guide first — it defines the schema, the Observation model, typed missingness, flags,
measures, and the build/validate/deploy loop. This document does not repeat it.

Working directory: `research-tracker` (the repo you are in). Data lives in `data/cohorts/`,
build with `python scripts/build_pais_cohorts.py`.

---

## 1. Mission

The database currently holds ~27 cohorts, heavily weighted toward acute-outbreak arboviruses,
COVID, and a handful of classic post-infective-fatigue studies. The literature it is meant to
map is far larger. Your job is to **find, verify, and add the missing cohorts** across the full
span of **infection-associated chronic conditions (IACCs / IACIs)** and the multi-symptom
"contested" illnesses that belong in the same comparison — ME/CFS, post-treatment Lyme, Gulf War
Illness, fibromyalgia, post-sepsis/post-ICU, PANS/PANDAS, and every post-acute infection
syndrome with a followed study population.

The value of each addition is not the disease name — it is the **design**: a denominator, a
control group, banked acute-phase specimens, a validated instrument at a defined timepoint. Add
strong cohorts because they raise the ceiling, and weak ones (flagged) because the database
exists to show that most of this literature is weak.

### The two non-negotiable rules (from the guide, restated)
1. **Every field is human/agent-verified against the primary source before merge.** Confirm the
   DOI/PMID and every number from the actual paper. The study names and identifiers in this
   worklist are **leads to verify, not facts to copy** — treat them as a starting search, not a
   citation.
2. **Never fabricate a number, denominator, or identifier.** Unknown → a typed missingness
   sentinel, never a guess.

---

## 2. Scope — and the modelling problem you must handle

The database is organised by **trigger** (`pathogen_id`). That is a clean fit for post-infection
syndromes but an awkward one for two important classes of IACC. Handle them explicitly:

- **Idiopathic / mixed-onset syndromes (ME/CFS, fibromyalgia).** The syndrome is the *outcome*,
  not the trigger. For a cohort with heterogeneous or unknown onset, add a trigger entry to
  `data/ref/pathogens.json` such as `unknown-trigger` (class `unknown`) or, where the cohort
  reports an onset breakdown, `mixed-infectious` (class `mixed`), and record the reported
  infectious-onset fraction as an observation (`func:` or a new `case-def:`). Note the tension in
  the cohort `notes`. Do **not** invent a pathogen.
- **Non-infectious exposure syndromes (Gulf War Illness).** The trigger is deployment/chemical
  exposure, not a pathogen. The current `pathogen_class` enum has no "environmental/toxic" value.
  **This is a schema decision for the maintainer — do not silently bend the enum.** Options to
  propose in your PR: (a) add `environmental` to the `pathogen_class` enum and to the build's
  label map, with a pathogen entry like `gulf-war-exposures`; or (b) use class `mixed`/`unknown`
  with an explanatory `notes` and an `unverified_source`/`no_control`-style flag. Recommend (a);
  implement only after the maintainer agrees, because it is an enum change that touches the
  schema, the build labels, and the gap matrices.

**In scope:** any followed study population (cohort, registry, biobank, comparative survey) whose
outcome is a chronic post-infection or infection-associated multi-symptom illness.
**Out of scope (unchanged):** patient-level/PHI data, pooled/meta-analytic estimates, composite
"burden/quality" scores, and harmonising-on-ingest. See guide §10.

---

## 3. The worklist — priority triggers and candidate cohorts

For each, the pattern is the same: identify the **cohort** (deduplicate the many papers onto one
cohort — see §4), verify design + N + follow-up + controls + headline numbers, author the file,
add measures/instruments as needed, flag honestly. Candidates below are **leads to verify**.

### A. ME/CFS — the anchor IACC, currently only present as post-infective sub-studies
Highest priority; the database has `case-def:cfs` but almost no dedicated ME/CFS cohort.
- **CDC Multi-site Clinical Assessment of ME/CFS (MCAM)** — multi-clinic US cohort, deep phenotyping.
- **UK ME/CFS Biobank (CureME, LSHTM)** — cases + healthy + MS controls, banked specimens.
- **DePaul University / Jason cohorts** — DSQ-based, community and post-IM (some already linked via Katz).
- **You + ME Registry (Solve M.E.)** and **DecodeME** (UK genetic study, large N) — registries/biobanks.
- **Stanford / Montoya, Nath NIH intramural deep-phenotyping study (2024, Walitt et al.)** — small, intensively measured; good `mean_sd` / `physio:` / `paired_change` material (CPET, tilt).
- **Rowe (Johns Hopkins) orthostatic-intolerance cohorts** — `physio:tilt-table`, autonomic.
Likely new measures/instruments: DePaul Symptom Questionnaire (DSQ), Canadian Consensus /
Institute of Medicine (IOM 2015) / International Consensus Criteria case definitions (some already
in `case_definition` enum), Bell disability scale, 2-day CPET workload drop (`paired_change`).

### B. Long COVID — add denominator-defined and controlled cohorts (we are survey-heavy)
- **NIH RECOVER-Adult** (very large, US, controlled) — the flagship; extract by symptom/timepoint.
- **Zurich SARS-CoV-2 Cohort (Ballouz/Menges, BMJ 2023)** — population-based, unexposed comparison (flagged as un-added earlier — resolve its numbers and add).
- **German NAPKON-POP / COVIDOM** — population-based.
- **CO-FLOW (Rotterdam)**, **Israeli/Maccabi**, **Ziyad Al-Aly VA cohorts** (rates, HRs → `rate`/`effect_only`).
- **Mount Sinai / Yale (Iwasaki) immunophenotyping cohorts** — `lab:`/extension material.

### C. Post-treatment Lyme disease (PTLDS) / Borrelia — extend beyond Aucott (have)
- **Klempner 2001 (NEJM) retreatment RCTs** — controlled, functional outcomes.
- **Wormser (NY Medical College) prospective early-Lyme cohorts**.
- **Rebman/Aucott SLICE additional papers** (attach to existing `aucott-slice-ptlds` as publications, not a new cohort).
- **Marques (NIH) post-Lyme cohorts**.

### D. Gulf War Illness — resolve the trigger-class question (§2) first
- **Steele (Kansas) cohort and Kansas GWI case definition**.
- **CDC "Gulf War" case definition (Fukuda 1998)** cohorts.
- **Millennium Cohort Study** (very large DoD longitudinal) — rates/HRs.
- **Haley (UT Southwestern) syndrome-factor + brain-imaging cohorts** — `physio:`/imaging.
- **VA Gulf War registry** — grey-literature/registry, flag accordingly.

### E. Post-Ebola — extend beyond PREVAIL III (have)
- **PostEboGui (Guinea)**, **Sierra Leone survivor cohorts (e.g., Tucker/PREVAIL-linked)** — ocular, neuro, MSK sequelae (`extensions.ebola` already has a schema).

### F. Other post-viral (broaden trigger coverage)
- **Post-polio syndrome** cohorts (poliovirus — new trigger).
- **Enterovirus / Coxsackie B** chronic sequelae; **parvovirus B19** arthropathy/fatigue.
- **EBV → multiple sclerosis** (Bjornevik 2022, Science, Millennium/DoD serum cohort) — a landmark infection→chronic-disease cohort; model MS as the outcome (`event:`/`effect_only`, huge HR).
- **Post-mono** beyond Katz/White (have): additional IM cohorts.
- **Dengue** (add Seet 2007 Singapore as a second dengue cohort), **Zika** beyond Cao-Lormeau (have), **West Nile** beyond Sejvar (have), **Ross River/chikungunya** additional analyses (attach to existing cohorts where same population).

### G. Post-enteric / bacterial IBS — extend beyond Walkerton (have)
- **Spanish Salmonella/Campylobacter outbreak cohorts**, **traveller's-diarrhoea post-infectious IBS** studies, other waterborne-outbreak cohorts. Non-fatigue outcomes broaden the measure coverage.

### H. Streptococcal / immune-mediated neuropsychiatric — a distinct IACC branch
- **PANS / PANDAS** cohorts (group A strep → OCD/tics; Swedo/NIMH).
- **Acute rheumatic fever / Sydenham chorea** longitudinal cohorts (strep → cardiac/neuro).

### I. Post-sepsis / post-ICU (PICS) and post-pneumonia
- **Post-sepsis cognitive/functional cohorts (e.g., Iwashyna, JAMA 2010)**, **ARDS/ICU survivor cohorts** — large, controlled, functional and cognitive outcomes; a well-designed comparator class for the fatigue-spectrum syndromes.

### J. Q-fever (second cohort), and additional PACVS biomarker cohorts
- **Ayres 1998 (UK Q-fever fatigue)**; additional Dutch Q-fever analyses (attach to `morroy-netherlands-qfever` if same population).
- Additional **PACVS/PVS** biomarker cohorts beyond Marburg/LISTEN (flag preprints/grey lit).

---

## 4. Search strategy

- **Find the cohort, not the paper.** Search PubMed/Europe PMC/Google Scholar for the syndrome +
  "prospective cohort" / "inception cohort" / "longitudinal" / "registry" / "biobank" /
  "case-control" + the trigger. For each hit, ask: *is this a new followed population, or another
  analysis of one already in the database?* If the latter, add it as a `publication` on the
  existing cohort and its numbers as `observations` — **never a duplicate cohort** (guide §1).
  Same-outbreak but different-sample studies are separate cohorts linked via `related_cohorts`.
- **Deduplicate by population.** Réunion chikungunya already shows the pattern (TELECHIK /
  Schilte / Marimoutou = three cohorts; Duvignaud = another TELECHIK paper). Watch for cohort
  names, registration IDs (NCT/ISRCTN), and identical N/site.
- **Prefer strong designs and specimen-banking cohorts** (the gap matrices show where these are
  missing): prospective inception cohorts with unexposed controls, and any cohort with banked
  **acute-phase** specimens.
- **Grey literature and preprints are allowed but flagged** (guide §5): preprints keep their DOI
  and get `type:preprint`; patient-org surveys/registries with no DOI/PMID use a URL-only
  `type:grey_literature` publication and the `grey_literature` flag.
- **Batch to be efficient:** collect and verify DOIs/PMIDs + headline numbers for ~5–10
  candidates first, then author the files in one pass, then one build + validate + commit.

---

## 5. Registry / reference additions you will likely need

Add to `data/ref/` as required (guide §4; reuse before inventing, use HPO/LOINC/SNOMED/UCUM):
- **Pathogens/triggers:** poliovirus, parvovirus-b19, enterovirus-coxsackie, group-a-streptococcus,
  unknown-trigger, mixed-infectious, and (pending maintainer sign-off) an `environmental` class
  with `gulf-war-exposures`.
- **Case definitions (`case-def:`):** iom_nam_2015 / canadian_consensus / international_consensus
  ME/CFS (already enum values in `case_definition`; add matching `case-def:` measures for
  observations), Kansas GWI, CDC/Fukuda GWI, Rome IV for PI-IBS (have `sym:irritable-bowel-syndrome`).
- **Instruments:** DSQ, Bell scale, PEM-specific instruments (DSQ-PEM), PROMIS fatigue, SF-36
  (have), Chalder (have), Nijmegen/NCSI (Q-fever), MASQ/PDQ cognitive.
- **Measures:** `physio:tilt-table-drop`, `physio:cpet-workload-drop` (`paired_change`),
  `event:multiple-sclerosis`, `func:` outcomes for work/disability as needed, more `lab:` analytes
  for immunophenotyping cohorts. Keep `sym:fatigue` and `sym:post-exertional-malaise` separate.

---

## 6. Targets and acceptance

- **Coverage goal:** at least one strong (prospective, controlled, or specimen-banking) cohort per
  trigger/disease in §3, plus flagged weak cohorts where that is all that exists.
- **Every PR:** passes `python scripts/build_pais_cohorts.py --check`; every publication has a
  DOI/PMID or a flagged grey-literature URL; every observation has a `source_locator` and a real
  `measure_id`; missing numbers are typed sentinels; weak/preprint/grey cohorts carry `flags`;
  regenerated artifacts committed. (Full checklist: guide §9.)
- **Watch the gap matrices** on the live site after each batch — the newly-empty-then-filled cells
  are your scoreboard, and the "largest comparable set" per measure is the headline metric to grow
  (e.g., get several ME/CFS cohorts using the same instrument at the same timepoint into one
  comparability signature).

---

## 7. Order of work (suggested)

1. **ME/CFS (§A)** — biggest gap, anchors the whole IACC framing; resolve DSQ/IOM measures.
2. **Long COVID controlled/denominator-defined (§B)** — RECOVER + Zurich + a VA rate cohort.
3. **Lyme extensions (§C)** and **post-sepsis/PICS (§I)** — strong comparator designs.
4. **Gulf War (§D)** — but open the schema-enum decision with the maintainer first.
5. **EBV→MS (§F, Bjornevik)** — a landmark that showcases `event:`/`effect_only` at scale.
6. Everything else in §3 as candidates verify out.

Do the schema-enum conversation (environmental trigger class) **before** authoring Gulf War
cohorts, and the ME/CFS measure/instrument additions **before** authoring ME/CFS cohorts, so the
records validate on first build.
