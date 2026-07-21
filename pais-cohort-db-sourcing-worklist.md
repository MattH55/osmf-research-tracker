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

## 2. What is already in the database (do not re-add)

Before hunting for new cohorts, know what is already covered. Re-adding a cohort under a
different name is the most common avoidable error. Check this list, and cross-reference any
candidate against the live `data/cohorts/` directory before authoring a file.

### Current inventory (27 cohorts, grouped by trigger)

| Trigger | Cohorts | Key features |
|---|---|---|
| **SARS-CoV-2** | `appelman-2024-lc-muscle`, `blomberg-2021-bergen-covid`, `davis-2021-longcovid`, `huang-2021-wuhan`, `phosp-covid`, `vitae-survey` | 6 cohorts; survey-heavy, one post-hospitalisation (PHOSP), one tissue (Appelman) |
| **SARS-CoV-1** | `lam-2009-sars-survivors`, `moldofsky-post-sars` | 2 cohorts; fatigue/sleep outcomes |
| **Dengue virus** | `colombo-dengue` | 1 cohort; single timepoint, no control |
| **Chikungunya virus** | `telechik-reunion`, `schilte-2013-chikungunya-reunion`, `marimoutou-2012-gendarmes` | 3 cohorts; same outbreak, different samples, linked via `related_cohorts` |
| **Ross River virus** | `mylonas-rrv-polyarthritis` | 1 cohort; joint outcomes |
| **West Nile virus** | `sejvar-wnv-neuroinvasive` | 1 cohort; neuroinvasive outcomes |
| **Zika virus** | `cao-lormeau-zika-gbs` | 1 cohort; GBS outcome |
| **Ebola virus** | `prevail-iii-ebola` | 1 cohort; large, controlled, multi-year follow-up |
| **Epstein-Barr virus** | `katz-2009-mononucleosis`, `white-1998-glandular-fever` | 2 cohorts; post-IM fatigue, some linked |
| **Coxiella burnetii** | `morroy-netherlands-qfever` | 1 cohort; large outbreak cohort |
| **Giardia duodenalis** | `bergen-giardiasis-2004` | 1 cohort; post-giardiasis IBS/fatigue |
| **Borrelia burgdorferi** | `aucott-slice-ptlds` | 1 cohort; post-treatment Lyme |
| **Campylobacter / E. coli** | `walkerton-health-study` | 1 cohort; post-enteric IBS, strong controlled design |
| **Pandemrix (H1N1 vaccine)** | `nohynek-2012-pandemrix-narcolepsy` | 1 cohort; registry-linked, age-stratified rate ratio |
| **COVID-19 vaccine** | `postvac-germany-survey`, `yale-listen-pvs` | 2 cohorts; survey/registry and biomarker deep-phenotyping |
| **Mixed (EBV/RRV/Coxiella)** | `dubbo-infection-outcomes` | 1 cohort; the classic post-infective fatigue comparison |
| **Unknown / idiopathic** | *(none — this is a major gap; see §4.A)* | No ME/CFS, fibromyalgia, or idiopathic chronic fatigue cohorts |

### Patterns visible in the gaps
- **0 ME/CFS or fibromyalgia cohorts** — the largest gap (see §4.A)
- **0 Gulf War Illness cohorts** — `environmental` trigger class now ready (see §3.2)
- **0 post-sepsis/post-ICU cohorts** — strong comparator class, completely absent
- **0 PANS/PANDAS cohorts** — entire IACC branch missing
- **0 post-polio, enterovirus, parvovirus B19 cohorts** — known PAIS literature, no coverage
- **0 post-malaria, post-hepatitis, post-influenza (non-pandemic) cohorts**
- **0 post-meningitis/encephalitis cohorts**
- **1 cohort each for dengue, Q-fever, Zika, WNV, Ross River** — need second cohorts for replication
- **Heavy survey bias in Long COVID** — need denominator-defined, controlled, and specimen-banking cohorts
- **No cohorts with banked acute-phase specimens outside of a few COVID studies** — a critical gap for biomarker work

---

## 3. Scope — and the modelling problem you must handle

The database is organised by **trigger** (`pathogen_id`). That is a clean fit for post-infection
syndromes but an awkward one for two important classes of IACC. Handle them explicitly:

### 3.1 Idiopathic / mixed-onset syndromes (ME/CFS, fibromyalgia)

The syndrome is the *outcome*, not the trigger. For a cohort with heterogeneous or unknown
onset, add a trigger entry to `data/ref/pathogens.json` such as `unknown-trigger` (class
`unknown`) or, where the cohort reports an onset breakdown, `mixed-infectious` (class `mixed`),
and record the reported infectious-onset fraction as an observation (`func:` or a new
`case-def:`). Note the tension in the cohort `notes`. Do **not** invent a pathogen.

For fibromyalgia specifically: many cohorts will have no reported infectious trigger. Add them
under `unknown-trigger` with a `notes` field that records the onset context (post-traumatic,
post-infectious, idiopathic, etc.) as reported by the study. Fibromyalgia cohorts are valuable
comparators for the fatigue-pain-spectrum IACCs.

### 3.2 Non-infectious exposure syndromes (Gulf War Illness)

The trigger is deployment/chemical exposure, not a pathogen. **DECIDED (approved by maintainer):
the trigger model is generalised to non-infectious exposures.** The `pathogen_class` enum now
includes `environmental`, the build label map renders it "Environmental / exposure", the
class-ordering places it after `vaccine`, and a trigger entry `gulf-war-exposures`
(class `environmental`) exists in `data/ref/pathogens.json`. You may author GWI (and other
exposure) cohorts directly against `pathogen_class: "environmental"` — no further schema change
or sign-off is required for this class. Record the specific exposures in the trigger's `vector`
and the cohort `notes`.

This same `environmental` class would also cover: World Trade Center first-responder cohorts
(toxic dust exposure → chronic respiratory/neurocognitive), Agent Orange exposure cohorts,
Camp Lejeune water contamination cohorts, and other environmental/toxic exposure syndromes that
produce multi-symptom chronic illnesses overlapping with the IACC spectrum.

### 3.3 What is in scope vs. out of scope

**In scope:** any followed study population (cohort, registry, biobank, comparative survey)
whose outcome is a chronic post-infection or infection-associated multi-symptom illness.
Includes:
- Prospective inception cohorts with unexposed controls
- Retrospective cohorts with a defined denominator
- Disease registries with longitudinal follow-up
- Biobanks with linked clinical outcomes
- Population-based administrative-health-data cohorts
- Patient-organisation surveys (flagged `patient_reported`, `self_selected`)
- Preprints and grey literature (flagged; see guide §5)

**Out of scope (unchanged):** patient-level/PHI data, pooled/meta-analytic estimates, composite
"burden/quality" scores, and harmonising-on-ingest. See guide §10.

---

## 4. The worklist — priority triggers and candidate cohorts

For each, the pattern is the same: identify the **cohort** (deduplicate the many papers onto one
cohort — see §5), verify design + N + follow-up + controls + headline numbers, author the file,
add measures/instruments as needed, flag honestly. Candidates below are **leads to verify**.

### A. ME/CFS — the anchor IACC, currently only present as post-infective sub-studies

**Priority: CRITICAL.** The database has `case-def:cfs` but zero dedicated ME/CFS cohorts. This
is the single largest gap and the highest-value expansion. ME/CFS is the reference syndrome for
the entire IACC spectrum, and without it the database cannot answer its central question: how
do post-infective fatigue syndromes compare to the idiopathic form?

#### A1. Large phenotyping cohorts / biobanks
- **CDC Multi-site Clinical Assessment of ME/CFS (MCAM)** — multi-clinic US cohort, deep
  phenotyping, ~400–500 participants. Papers: Unger et al. (multiple, 2017–). Key measures:
  DSQ, SF-36, medical-history standardised form, physical exam.
  - PMID to verify: 28682633 (Unger 2017, design paper)
- **UK ME/CFS Biobank (CureME, LSHTM)** — cases + healthy controls + MS disease controls,
  banked serum/PBMC/RNA/whole blood. ~600+ participants. Papers: Lacerda et al. (multiple).
  Key value: **banked specimens** with deep clinical phenotyping — fills the acute-phase
  specimen gap partially (pre-existing banked samples).
  - PMID to verify: 28373256 (Lacerda 2017)
- **NIH Intramural deep-phenotyping study (Walitt/Nath, 2024)** — small (~50–60), intensively
  measured with CPET, tilt-table, fMRI, metabolomics, proteomics, immunophenotyping. Despite
  small N, is the single most intensively measured ME/CFS cohort in existence. Good source for
  `mean_sd` / `physio:` / `paired_change` observations (2-day CPET workload drop, tilt-table
  haemodynamics).
  - PMID to verify: 38358935 (Walitt et al. 2024, Nature Communications)
- **DecodeME (UK)** — large genetic study of ME/CFS, ~17,000+ participants, GWAS + questionnaire
  data. Registy/biobank design. Key value: large N for symptom-prevalence observations.
  - PMID to verify: 36959927 (Devereux-Cooke et al. 2023, design paper)
- **You + ME Registry (Solve M.E.)** — patient registry, ~10,000+ enrolled, longitudinal
  patient-reported outcomes. Flag: `patient_reported`, `self_selected`.
  - URL: https://youandmeregistry.org/

#### A2. Community / epidemiological cohorts
- **DePaul University / Jason cohorts** — DSQ-based community samples, multiple papers
  spanning adult and paediatric populations. Some already partially linked via the Katz
  post-IM cohorts (see `katz-2009-mononucleosis.json`). Key value: DSQ instrument data with
  large community N. Multiple distinct cohorts — verify whether they are independent samples
  or overlapping.
  - Key concept: "DePaul Symptom Questionnaire" (DSQ) — must add as instrument in refs.
  - PMIDs to verify: 15282458 (Jason 2004, Fukuda-defined prevalence), 16476987 (Jason 2006,
    paediatric)
- **Georgia CFS surveillance study (Reeves et al.)** — population-based, CDC-led, Wichita +
  Georgia. Older but methodologically important. Flag: the empiric/Fukuda definition used has
  been heavily criticised.
  - PMID to verify: 15928179 (Reeves et al. 2005, Wichita)
- **Biopsychosocial model cohorts (UK PACE trial, etc.)** — the PACE trial (White et al. 2011,
  Lancet) is an RCT, not a cohort, but the PACE participants form a followed population with
  extensive outcome data at multiple timepoints. Out of scope as an RCT, but the baseline data
  and natural-history arms may be extractable as a cohort. **Tread carefully — this is a
  contested literature.** Flag heavily if added.

#### A3. Orthostatic intolerance / autonomic sub-studies (can attach to existing or be standalone)
- **Rowe (Johns Hopkins) orthostatic-intolerance cohorts** — tilt-table, autonomic testing in
  ME/CFS and POTS. Good `physio:tilt-table` / `physio:cpet-workload-drop` material. Multiple
  papers; verify whether one followed population or several distinct samples.
  - Likely measures: `physio:tilt-table-drop`, `physio:heart-rate-variability`,
    `physio:cerebral-blood-flow-velocity`
- **van Campen / Visser (Stichting CardioZorg, Netherlands)** — 2-day CPET studies in ME/CFS,
  demonstrating post-exertional reduction in workload at anaerobic threshold. Good `paired_change`
  material. Small N (~30–50) but highly specific to PEM physiology.
  - PMID to verify: 32672758 (van Campen et al. 2020, 2-day CPET)

#### A4. Likely new measures/instruments for ME/CFS expansion
DePaul Symptom Questionnaire (DSQ), DSQ-PEM subscale, Canadian Consensus Criteria (CCC 2003),
International Consensus Criteria (ICC 2011 / Carruthers), Institute of Medicine (IOM 2015 /
NAM) diagnostic criteria — these may already be enum values in `case_definition`. Bell
disability scale, 2-day CPET workload drop (`paired_change`), SF-36 physical function and
vitality subscales (instruments already exist but verify measure_ids), COMPASS-31 (autonomic
symptom score), orthostatic intolerance questionnaire (OIQ), PROMIS fatigue short form.

### B. Long COVID — add denominator-defined and controlled cohorts (we are survey-heavy)

**Priority: HIGH.** Current Long COVID cohorts are skewed toward surveys and convenience
samples. Add cohorts that have a defined denominator and an unexposed comparison group, plus
at least one specimen-banking cohort.

#### B1. Large controlled cohorts
- **NIH RECOVER-Adult** — very large US nationwide cohort, ~15,000+ enrolled across >200 sites,
  controlled (SARS-CoV-2 positive vs. negative), deep phenotyping with biospecimens. The
  flagship US Long COVID study. Multiple publications expected; start with the design paper
  and add observations as substudies publish.
  - PMID to verify: 36075778 (RECOVER design paper, Horwitz et al. 2023)
  - Key value: **banked acute and convalescent specimens**, standardised protocol across sites,
    enormous N. Will generate many observations over time — plan for iterative updates.
- **Zurich SARS-CoV-2 Cohort (Ballouz/Menges et al., BMJ 2023)** — population-based with
  unexposed comparison group. Previously flagged as un-added — resolve its numbers and add.
  - PMID to verify: 37277195 (Ballouz et al. 2023, BMJ)
- **German NAPKON-POP / COVIDOM** — population-based, multi-site, post-COVID follow-up with
  unexposed controls. Large N.
  - PMID to verify: 35653484 (NAPKON design paper, Schons et al. 2022)
- **CO-FLOW (Rotterdam)** — prospective cohort of hospitalised and non-hospitalised COVID-19
  patients with matched controls, Netherlands. Multiple timepoints, multi-system outcomes.
  - PMID to verify: 34876438 (CO-FLOW design, Wiertz et al. 2021)
- **PHOSP-COVID (UK)** — already in database (`phosp-covid.json`). **Do not re-add.** Attach
  additional PHOSP publications as publications/observations on the existing cohort.

#### B2. Administrative-health-data / rate cohorts
- **Ziyad Al-Aly VA cohorts** — enormous (~150,000+ COVID cases), US Veterans Health
  Administration data, controlled with contemporary and historical comparators, multi-system
  outcomes. Produce hazard ratios — use `value.type: effect_only` or `rate`. Multiple papers
  across organ systems; deduplicate carefully — most are analyses of the same VA population,
  not independent cohorts.
  - PMIDs to verify: 33826814 (Al-Aly et al. 2021, Nature — 6-month outcomes),
    35255492 (2-year outcomes, 2023, Nature Medicine)
- **Israeli / Maccabi Healthcare Services cohorts** — large HMO-based, controlled. Papers by
  Mizrahi et al. Use `effect_only` for HRs.
  - PMID to verify: 36355858 (Mizrahi et al. 2022, BMJ)
- **UK Biobank COVID-19 sub-studies** — brain imaging (Douaud et al. 2022, Nature), cardiac,
  multi-organ. Each is an analysis of the same UK Biobank population — coordinate to ensure
  one UK Biobank COVID cohort with substudies, not multiple cohorts.
  - PMID to verify: 35255459 (Douaud et al. 2022, Nature — brain imaging)

#### B3. Deep-phenotyping / immunophenotyping cohorts
- **Mount Sinai post-COVID cohort (Merad/Iwasaki)** — immunophenotyping, multi-omics, small
  N (~200–300) but deep molecular data. `lab:` / extension material.
  - PMID to verify: 34478646 (Su et al. 2022, Cell — multi-omics)
- **Yale LISTEN / Iwasaki lab** — `yale-listen-pvs.json` already exists in database but is
  under `covid-19-vaccine` trigger. If the same cohort tracks post-COVID outcomes separately,
  add those as observations on a separate `sars-cov-2` cohort linked via `related_cohorts`
  — verify whether LISTEN enrolled both post-COVID and post-vaccine participants as separate
  arms or as one cohort.

#### B4. Paediatric Long COVID (mostly absent)
- **NIH RECOVER-Paediatrics** — paediatric arm of RECOVER.
- **CLoCK study (UK)** — large paediatric post-COVID cohort with test-negative controls.
  - PMID to verify: 35728516 (Stephenson et al. 2022, Lancet Child & Adolescent Health)

### C. Post-treatment Lyme disease (PTLDS) / Borrelia — extend beyond Aucott (have)

**Priority: MEDIUM-HIGH.** One Lyme cohort (`aucott-slice-ptlds`) is in the database. The Lyme
post-treatment literature is large and contentious — add cohorts that represent the major camps
in the debate.

#### C1. Core Lyme cohorts
- **Klempner 2001 (NEJM) retreatment RCTs** — two RCTs (seropositive and seronegative) of
  extended antibiotic therapy for PTLDS. While RCTs, the enrolled populations form followed
  cohorts with extensive baseline and longitudinal functional/symptom data. Extractable as
  cohorts with the `notes` field recording that they are RCT arms. Add the control-arm data
  as comparator values.
  - PMID to verify: 11450676 (Klempner et al. 2001, NEJM)
- **Wormser (NY Medical College) prospective early-Lyme cohorts** — multiple papers tracking
  outcomes after early Lyme treatment. Good denominator-defined design.
  - PMIDs to verify: 12539066 (Wormser et al. 2003, Ann Intern Med — early Lyme outcomes),
    17029133 (Wormser et al. 2006, CID — long-term follow-up)
- **Marques (NIH) post-Lyme cohorts** — NIH intramural, deep phenotyping, controlled, banked
  specimens. Small N but high-quality data.
  - PMID to verify: 24918167 (Marques et al. 2014, PLoS ONE — xenodiagnosis study design)
- **Rebman/Aucott SLICE additional papers** — attach to existing `aucott-slice-ptlds` as
  publications, not a new cohort. The SLICE study has published multiple follow-up papers
  with additional outcomes. Search for "SLICE study Lyme" on PubMed.

#### C2. European Lyme cohorts
- **Ljostad (Norway) neuroborreliosis cohort** — prospective, controlled, long-term follow-up
  of treated neuroborreliosis.
  - PMID to verify: 19666975 (Ljostad et al. 2009, CID)
- **German neuroborreliosis cohorts** — multiple small German studies; verify if any have
  sufficient follow-up and control data.

### D. Gulf War Illness — trigger-class question resolved (§3.2)

**Priority: MEDIUM (unblocked).** The `environmental` pathogen_class and the
`gulf-war-exposures` trigger now exist, so GWI cohorts can be authored directly — no further
sign-off needed. GWI is the most
important non-infectious comparator for the IACC spectrum — its symptom overlap with ME/CFS
and fibromyalgia is well documented, and the deployment-exposure model is a clean test of
"multi-system insult → chronic illness" independent of microbial trigger.

#### D1. Core GWI cohorts
- **Steele (Kansas) cohort** — the foundational Kansas GWI case definition cohort. A
  population-based study of deployed vs. non-deployed Gulf War veterans with detailed
  symptom inventories.
  - PMID to verify: 10642574 (Steele et al. 2000, Am J Med — Kansas GWI definition)
- **CDC "Gulf War" / Fukuda 1998 cohorts** — the original CDC chronic multi-symptom illness
  definition for Gulf War veterans. Fukuda et al. 1998, JAMA.
  - PMID to verify: 9738602 (Fukuda et al. 1998, JAMA)
- **Millennium Cohort Study** — very large DoD longitudinal cohort (~200,000+), includes
  deployed and non-deployed service members, many substudies. Excellent denominator-defined
  design. Use `effect_only` for HRs from the many published analyses.
  - PMID to verify: 18381819 (Ryan et al. 2007, design paper)
- **Haley (UT Southwestern) syndrome-factor + brain-imaging cohorts** — smaller N but
  deep phenotyping with MRS brain imaging, autonomic testing, and factor-analytic syndrome
  definitions. Good `physio:` / imaging / `mean_sd` material.
  - PMID to verify: 9040528 (Haley et al. 1997, JAMA — syndrome factor analysis)
- **VA Gulf War registry** — grey-literature/registry, flag `grey_literature`,
  `patient_reported`, `self_selected`.

#### D2. Related military/occupational exposure cohorts (also need `environmental` class)
- **World Trade Center first-responder cohorts** — toxic dust exposure → chronic respiratory,
  GERD, sinonasal, and neurocognitive outcomes. Large N, controlled (exposed vs. unexposed
  responders), long follow-up. Multiple papers from the WTC Health Program.
  - PMID to verify: 17088555 (Herbert et al. 2006, Environ Health Perspect — WTC medical
    monitoring)
- **Agent Orange / Vietnam veterans cohorts** — dioxin exposure → multi-system chronic illness.
  Large administrative-health-data studies.
- **Camp Lejeune water contamination cohorts** — solvent-contaminated drinking water →
  multi-system outcomes.

### E. Post-Ebola — extend beyond PREVAIL III (have)

**Priority: LOW-MEDIUM.** One strong Ebola cohort (`prevail-iii-ebola`) already exists. Add
additional cohorts from other outbreak settings to demonstrate geographic and viral-strain
heterogeneity.

- **PostEboGui (Guinea)** — large survivor cohort, multi-system outcomes, controlled design
  (contacts). Ocular, neuro, and MSK sequelae.
  - PMID to verify: 28806567 (Etard et al. 2016/2017, Lancet Infect Dis — PostEboGui design)
- **Sierra Leone survivor cohorts (e.g., Tucker/PREVAIL-linked)** — ocular and neuro sequelae,
  some overlapping with PREVAIL III. Verify independence before adding as separate cohort.
  - PMID to verify: 31340949 (PREVAIL III ocular sub-study, Sneller et al. 2019)
- **Liberian survivor cohorts** — multiple small cohorts; verify if any have sufficient N and
  follow-up.
- Already have `extensions.ebola` schema — any new ebola cohort can use it.

### F. Other post-viral (broaden trigger coverage)

**Priority: MEDIUM-HIGH.** Many viruses with known post-infective sequelae have zero coverage.
This section fills the trigger diversity gap.

#### F1. Herpesvirus family
- **EBV → Multiple Sclerosis (Bjornevik 2022)** — a landmark infection→chronic-disease cohort
  using the Millennium/DoD serum repository. EBV seroconversion preceded MS onset in nearly
  every case. Model MS as the outcome (`event:`/`effect_only`, huge HR). This is a showcase
  for the infection→chronic-disease pipeline that the database is designed to document.
  - PMID to verify: 35025605 (Bjornevik et al. 2022, Science)
- **Post-mono beyond Katz/White** — additional infectious mononucleosis cohorts with fatigue
  outcomes beyond the two already in the database. Search for: IM + "prospective cohort" +
  fatigue. Candidate: Petersen et al. (Denmark, nationwide registry), Candy et al. (UK).
  - PMIDs to verify: 22805117 (Petersen et al. 2012, CID — post-IM fatigue, large N),
    16882470 (Candy et al. 2006, J Neurol Neurosurg Psychiatry)

#### F2. Enterovirus / Picornavirus
- **Enterovirus / Coxsackie B chronic sequelae** — known association with ME/CFS (enteroviral
  persistence hypothesis), myocarditis, and type 1 diabetes. Cohorts are likely small and
  scattered. Search: Coxsackie B + "prospective" + fatigue / myalgia / myocarditis.
- **Post-polio syndrome** — poliovirus. The classic post-viral fatigue syndrome. Large
  literature, well-characterised phenotype. New trigger: `poliovirus` (class `virus`).
  - Key features: new-onset fatigue + weakness + pain decades after acute paralytic polio,
    with a defined denominator (known polio survivors).
  - PMID to verify: 11455048 (Nollet et al. 2001, J Neurol Neurosurg Psychiatry — Dutch
    post-polio cohort)
- **Enterovirus D68 / AFM** — acute flaccid myelitis post-enterovirus D68. Small but growing
  literature. Paediatric.

#### F3. Parvovirus B19
- **Parvovirus B19 arthropathy / fatigue** — well-documented post-infectious arthritis and
  chronic fatigue. New trigger: `parvovirus-b19` (class `virus`).
  - Search: parvovirus B19 + "prospective cohort" + arthropathy / fatigue / chronic.
  - Candidate: Kerr et al. (UK), several Scandinavian outbreak studies.
  - PMID to verify: 11338670 (Kerr et al. 2001, J Infect — persistence hypothesis)

#### F4. Dengue, Zika, WNV, Ross River — second cohorts for replication
- **Dengue** — `colombo-dengue.json` exists. Add Seet 2007 Singapore as a second dengue cohort.
  - PMID to verify: 17883672 (Seet et al. 2007, J Clin Virol — post-dengue fatigue)
- **Zika** — `cao-lormeau-zika-gbs.json` exists. Add a Zika congenital syndrome (CZS) maternal
  cohort or a non-GBS adult Zika sequelae cohort.
- **West Nile** — `sejvar-wnv-neuroinvasive.json` exists. Add a non-neuroinvasive WNV
  fatigue cohort or a long-term WNV renal outcomes cohort.
  - PMID to verify: 18983443 (Sejvar et al. 2008 — WNV long-term follow-up, already
    attached as publication; verify if additional independent cohorts exist)
- **Ross River** — `mylonas-rrv-polyarthritis.json` exists. Additional RRV analyses from
  Australian outbreak cohorts; attach to existing where same population.
- **Chikungunya** — 3 cohorts already in database (TELECHIK / Schilte / Marimoutou). The
  chikungunya trigger is well-covered. Add additional publications as observations on the
  existing cohorts; no new cohorts needed unless a genuinely independent population from a
  different outbreak (e.g., Americas 2013–2015 CHIKV epidemic) is found.
  - Candidate: Colombian or Brazilian CHIKV cohorts (2014–2016 epidemic).

#### F5. Influenza (non-pandemic, non-H1N1-vaccine)
- **Post-influenza fatigue** — seasonal influenza as a trigger for post-viral fatigue.
  Under-studied relative to pandemic influenza. Search: influenza + "post-viral fatigue" +
  "cohort" / "prospective". Likely small, scattered literature.
- **Post-1918 influenza ("Spanish flu")** — historical cohorts, encephalitis lethargica
  (von Economo disease). Historical interest but unlikely to yield extractable numeric data
  by modern standards. Note for completeness; skip unless a meta-analysis or historical
  review provides extractable Ns.

#### F6. Hepatitis viruses
- **Post-hepatitis B / C fatigue** — chronic hepatitis outcomes include fatigue as a major
  symptom. Large treatment-trial populations with longitudinal fatigue data (PROMs, SF-36).
  New triggers: `hepatitis-b-virus`, `hepatitis-c-virus` (class `virus`).
  - These are a gray area: the fatigue is associated with chronic infection, not
    post-infective in the strict sense. Model as "infection-associated" with a `notes` caveat.
- **Post-hepatitis E** — emerging literature on chronic hepatitis E in immunocompromised,
  and post-HEV fatigue. Small literature.
- **Post-hepatitis A** — rare prolonged fatigue; small case series. Low priority.

#### F7. Other neurotropic / neuroinvasive viruses
- **HSV encephalitis survivors** — post-encephalitic cognitive/neuropsychiatric sequelae.
  Small cohorts. Herpes simplex virus → chronic neurocognitive outcomes.
- **Rabies survivors (rare)** — Milwaukee protocol survivors. Extremely small N, but the
  outcomes are dramatic and well-documented at the case level. Likely out of scope as
  case-report-level data.
- **Japanese encephalitis virus** — post-encephalitic sequelae. Large burden in Asia.
  - New trigger: `japanese-encephalitis-virus` (class `virus`).
- **Nipah virus survivors** — post-encephalitic and neuropsychiatric sequelae. Small
  outbreak cohorts from Malaysia, Bangladesh, India.
  - New trigger: `nipah-virus` (class `virus`).
  - PMID to verify: 16703543 (Sejvar et al. 2007, Clin Infect Dis — Nipah long-term outcomes)
- **Tick-borne encephalitis virus** — post-encephalitic fatigue and cognitive sequelae.
  European literature, modest N.
  - New trigger: `tick-borne-encephalitis-virus` (class `virus`).

### G. Post-enteric / bacterial IBS — extend beyond Walkerton (have)

**Priority: MEDIUM.** The Walkerton cohort (`walkerton-health-study.json`) is strong — a
large, controlled waterborne outbreak study with excellent post-infectious IBS data. Add
cohorts that replicate the post-infectious IBS phenotype with different pathogens,
geographies, and outbreak settings.

- **Spanish Salmonella / Campylobacter outbreak cohorts** — multiple published Spanish
  waterborne and foodborne outbreak cohorts with post-infectious IBS outcomes.
  - Search: Salmonella / Campylobacter + "post-infectious IBS" + Spain.
  - PMID to verify: 17805921 (Mearin et al. 2007, Gastroenterology — Spanish Salmonella
    outbreak PI-IBS), 20202266 (Thabane et al. 2010 — meta-analysis; use to find primary
    cohort papers)
- **Traveller's diarrhoea post-infectious IBS studies** — cohorts of travellers who
  developed acute diarrhoea and were followed for PI-IBS. Multiple pathogens. Good
  comparator: different exposure setting, same outcome.
  - PMID to verify: 17308215 (Stermer et al. 2006, Clin Infect Dis)
- **Shigella / ETEC outbreak cohorts** — additional enteric pathogens with known PI-IBS
  sequelae.
- **Norovirus outbreak cohorts** — post-viral-enteritis IBS. New trigger subtype for
  norovirus.
  - New trigger: `norovirus` (class `virus`).

### H. Streptococcal / immune-mediated neuropsychiatric — a distinct IACC branch

**Priority: MEDIUM.** Entirely absent from the database. PANS/PANDAS represents a
post-infectious neuropsychiatric phenotype that broadens the IACC spectrum beyond
fatigue-pain-cognitive domains.

#### H1. PANS / PANDAS
- **PANDAS cohorts (Swedo/NIMH)** — group A streptococcus → acute-onset OCD / tics in
  children. The index cohorts from NIMH. Small N, intensely phenotyped.
  - New trigger: `group-a-streptococcus` (class `bacterium`).
  - PMID to verify: 9734432 (Swedo et al. 1998, Am J Psychiatry — 50-case series / index
    description of PANDAS)
- **PANS consortium cohorts** — broader phenotype (not exclusively strep-triggered),
  multiple sites. Verify if there is a single followed cohort or several.
- **Cunningham Panel studies** — cohorts with anti-neuronal antibody measurements as
  biomarkers. `lab:` material.

#### H2. Sydenham chorea / acute rheumatic fever
- **Sydenham chorea longitudinal cohorts** — group A strep → chorea, carditis, arthritis.
  The classic post-streptococcal neuropsychiatric syndrome. Longitudinal follow-up gives
  valuable time-to-event / recurrence data.
  - PMID to verify: 10842295 (Cardoso et al. 2000/2002 — Sydenham chorea natural history)
- **RHD (rheumatic heart disease) registries** — large, long-term follow-up of acute
  rheumatic fever → chronic valvular disease. Mostly from LMICs (South Asia, sub-Saharan
  Africa, Pacific, Indigenous Australia/NZ). Registry design, large N.

### I. Post-sepsis / post-ICU (PICS) and post-pneumonia

**Priority: MEDIUM-HIGH.** Completely absent from the database. Post-intensive-care syndrome
(PICS) and post-sepsis syndrome are the most important non-infectious-trigger comparators
for the fatigue-cognitive-functional spectrum of IACCs. These are large, well-controlled,
methodologically rigorous cohorts that use validated instruments — exactly the strong-design
comparators that raise the database's ceiling.

#### I1. Post-sepsis cognitive/functional cohorts
- **Iwashyna (JAMA 2010)** — landmark study of cognitive and functional decline after severe
  sepsis in the US Health and Retirement Study. Large N, controlled (pre/post within-subject
  + population norms), validated cognitive instruments.
  - PMID to verify: 20949077 (Iwashyna et al. 2010, JAMA)
- **BRAIN-ICU / Vanderbilt post-ICU cohorts** — deep cognitive phenotyping, imaging
  biomarkers, long follow-up. Good `mean_sd` / `instr:` material.
  - PMID to verify: 24092943 (Pandharipande et al. 2013, NEJM — BRAIN-ICU)
- **UK post-ICU follow-up clinics** — multiple UK cohorts with functional, cognitive, and
  psychological outcomes at 6–12 months.
- **German SepNet cohorts** — post-sepsis quality-of-life and functional outcomes.

#### I2. ARDS / COVID-ARDS survivor cohorts
- **ARDSNet / NHLBI ARDS cohorts** — long-term follow-up of ARDS survivors with
  pulmonary function, functional status, and cognitive outcomes at 1–5 years.
  - PMID to verify: 12700356 (Herridge et al. 2003, NEJM — 1-year outcomes in ARDS
    survivors), 17720887 (Herridge et al. 2007, 5-year follow-up)
- **COVID-ARDS survivor cohorts** — overlap with Long COVID but with a distinct pulmonary
  and ICU-acquired-weakness phenotype. If these are subcohorts of existing Long COVID
  cohorts (PHOSP-COVID includes ICU survivors), attach to those.

#### I3. Post-pneumonia (community-acquired, non-ICU)
- **Community-acquired pneumonia (CAP) recovery cohorts** — post-pneumonia cardiovascular,
  cognitive, and functional outcomes at 1+ years. Large administrative-health-data studies
  with matched controls. Good `event:` / `effect_only` material.
  - PMID to verify: 25473557 (Corrales-Medina et al. 2015, JAMA — post-pneumonia CVD risk)

### J. Q-fever (second cohort), and additional PACVS/PVS biomarker cohorts

**Priority: LOW-MEDIUM.** One Q-fever cohort exists (`morroy-netherlands-qfever`).

- **Ayres 1998 (UK Q-fever fatigue)** — UK Q-fever outbreak cohort with detailed fatigue
  outcomes. Adds geographic/population diversity.
  - PMID to verify: 9615769 (Ayres et al. 1998, QJM)
- Additional Dutch Q-fever analyses — attach to `morroy-netherlands-qfever` if same
  outbreak population (verify — the Dutch outbreak was large and several research groups
  studied it; confirm whether distinct samples or overlapping).
- **PACVS/PVS biomarker cohorts beyond Marburg/LISTEN** — `marburg-pacvs.json` and
  `yale-listen-pvs.json` exist. Search for additional post-vaccination syndrome cohorts
  (Germany, Denmark, other European countries with large-scale COVID vaccination campaigns
  and subsequent PVS case series). Flag preprints/grey literature.
  - Candidate: Schieffer et al. (Marburg — already in database as `marburg-pacvs`), any
    independent replication cohorts.
- **Additional ME/CFS-PACVS overlap cohorts** — cohorts that enrolled both post-infectious
  and post-vaccination onset ME/CFS with a breakdown by trigger. Valuable for the
  infection-vs-vaccine comparison that the database framework can surface.

### K. Fibromyalgia — the pain-domain anchor

**Priority: MEDIUM.** Completely absent. Fibromyalgia is the reference syndrome for the
chronic widespread pain domain of the IACC spectrum, overlapping substantially with ME/CFS
and post-infectious syndromes. Add under `unknown-trigger` or `mixed-infectious` (see §3.1).

- **ACR criteria validation cohorts (Wolfe et al. 1990, 2010, 2016)** — the diagnostic
  criteria cohorts are large, multi-site, and include detailed symptom inventories.
  - PMIDs to verify: 2306288 (Wolfe et al. 1990, Arthritis Rheum — ACR 1990 criteria),
    20461783 (Wolfe et al. 2010, Arthritis Care Res — ACR 2010 criteria)
- **SWEF (Swedish Fibromyalgia) cohorts** — longitudinal, genetics, comorbidity.
- **Multinational fibromyalgia registries** — large N, patient-reported, flag `patient_reported`.
  - Example: National Data Bank for Rheumatic Diseases (US), German fibromyalgia registry.
- **Post-traumatic fibromyalgia cohorts** — distinct from post-infectious, but overlapping
  symptom profile. The trigger (physical trauma, MVAs, stress) is not infectious — model
  via `unknown-trigger` with `notes` recording the trauma context.

### L. Post-meningitis and post-encephalitis (bacterial, viral, TB)

**Priority: LOW-MEDIUM.** Entirely absent. Post-meningitic and post-encephalitic syndromes
include hearing loss, cognitive impairment, epilepsy, and fatigue — a distinct multi-system
outcome profile that broadens the database's coverage of neurological sequelae.

- **Bacterial meningitis survivor cohorts** — S. pneumoniae, N. meningitidis, H. influenzae
  → hearing loss, cognitive, seizure outcomes. New triggers: `streptococcus-pneumoniae`,
  `neisseria-meningitidis`, `haemophilus-influenzae` (class `bacterium`).
  - PMID to verify: 19148745 (Brouwer et al. 2010, Lancet Neurol — long-term sequelae of
    bacterial meningitis)
- **TB meningitis survivor cohorts** — Mycobacterium tuberculosis → high rates of
  neurological sequelae. LMIC literature.
  - New trigger: `mycobacterium-tuberculosis` (class `bacterium`).
- **Autoimmune encephalitis cohorts** — anti-NMDAR, anti-LGI1, etc. Not infection-triggered
  in the acute sense, but post-infectious triggers (HSV encephalitis → anti-NMDAR) are
  documented. Model under the relevant infectious trigger where causal linkage is established.

### M. Post-malaria chronic sequelae

**Priority: LOW.** Entirely absent. Cerebral malaria especially has well-documented chronic
neurological and cognitive sequelae. LMIC cohorts with long follow-up.

- New trigger: `plasmodium-falciparum` (class `protozoan`).
- **Cerebral malaria survivor cohorts** — African paediatric cohorts (Malawi, Uganda, Kenya)
  with cognitive, behavioural, and epilepsy outcomes at 1–5+ years.
  - PMID to verify: 15800015 (Boivin et al. 2005, Pediatrics — Ugandan cerebral malaria
    cognitive outcomes)
- **Post-malaria neurological syndrome (PMNS)** — rare, post-P. falciparum, autoimmune-
  mediated. Small case series; may not meet cohort N threshold.

### N. Other bacterial and parasitic triggers

**Priority: LOW.** Filling out the taxonomic coverage of the trigger registry.

#### N1. Mycoplasma
- **Mycoplasma pneumoniae** — post-Mycoplasma fatigue, neurological syndromes (ADEM,
  transverse myelitis, Guillain-Barré), and M. pneumoniae-induced rash and mucositis (MIRM).
  - New trigger: `mycoplasma-pneumoniae` (class `bacterium`).
  - Small cohorts; search: Mycoplasma pneumoniae + "post-infectious" + fatigue / neurological.

#### N2. Scrub typhus / leptospirosis / rickettsial diseases
- **Scrub typhus (Orientia tsutsugamushi)** — post-scrub-typhus fatigue, hearing loss,
  neuropsychiatric sequelae. Common in Asia-Pacific. New trigger: `orientia-tsutsugamushi`
  (class `bacterium`).
- **Leptospirosis** — post-leptospirosis fatigue, chronic kidney disease, uveitis.
  New trigger: `leptospira-interrogans` (class `bacterium`).
- **Murine typhus (Rickettsia typhi)** and **Rocky Mountain spotted fever (R. rickettsii)** —
  fatigue and neurological sequelae.

#### N3. Brucellosis
- **Post-brucellosis fatigue** — well-documented, large literature from endemic regions
  (Middle East, Mediterranean, Central Asia). New trigger: `brucella-melitensis` (class
  `bacterium`).
  - PMID: multiple Turkish and Iranian cohorts; search brucellosis + "post-treatment" +
    fatigue.

#### N4. Toxoplasmosis
- **Post-toxoplasmosis** and congenital toxoplasmosis → ocular/neurodevelopmental sequelae.
  New trigger: `toxoplasma-gondii` (class `protozoan`).

#### N5. Schistosomiasis
- **Chronic schistosomiasis** → hepatic fibrosis, portal hypertension, neuroschistosomiasis.
  New trigger: `schistosoma-mansoni` / `schistosoma-haematobium` (class `protozoan` /
  `helminth` — may need new pathogen_class `helminth` or use `protozoan` with a taxon note).
  This is chronic infection rather than post-infectious; model as infection-associated with
  appropriate caveats.

#### N6. Trypanosomiasis (Chagas, sleeping sickness)
- **Chagas disease** → chronic cardiomyopathy, megaoesophagus/megacolon. Large Latin
  American literature. New trigger: `trypanosoma-cruzi` (class `protozoan`).
  This is chronic infection, not post-infectious — caveat in `notes`.

### O. Post-surgical / post-traumatic syndromes (comparator controls)

**Priority: LOW.** Not infection-associated, but useful as "generic physiological insult"
comparators for the fatigue and functional-outcome domains. These are not the core mission
and should only be added after the main IACC gaps are filled.

- **Post-cardiac-surgery cognitive decline cohorts** — large literature, validated cognitive
  instruments at standard timepoints. Good comparator for post-sepsis cognitive decline and
  post-infectious brain fog.
- **Post-concussion syndrome / mild TBI cohorts** — symptom overlap with ME/CFS/fibromyalgia
  (headache, cognitive, fatigue, sleep). Sports-concussion and military-TBI registries with
  large N.
- **Post-chemotherapy fatigue ("chemo brain") cohorts** — large oncology-trial populations
  with fatigue and cognitive PROMs at standard timepoints. Valuable as a comparator for
  the physiology of post-insult fatigue: is post-infective fatigue distinguishable from
  post-chemotherapy fatigue by instrument profile?

### P. Chronic infection cohorts (HIV, chronic viral hepatitis, TB)

**Priority: LOW.** These are infection-associated (ongoing), not post-infectious. Include
sparingly as comparators for the infection→chronic-phenotype pipeline, with explicit
`notes` recording that the infection is chronic/active, not cleared.

- **HIV / ART-era chronic-inflammation cohorts** — large, well-characterised, long follow-up,
  controlled (HIV-negative comparators). The chronic inflammation model is mechanistically
  relevant to post-infectious fatigue. Use as comparator, not as core IACC.
  - Example: MACS/WIHS (now MACS-WIHS Combined Cohort Study), START trial, SMART trial.
- **Chronic hepatitis C (pre-DAA era)** — large treatment-trial populations with fatigue and
  SF-36 data. The interferon-treatment era generated extensive fatigue data.
- **Chronic tuberculosis** — post-treatment lung function and functional outcomes. Large
  LMIC literature.

---

## 5. Search strategy

### 5.1 Find the cohort, not the paper

Search PubMed/Europe PMC/Google Scholar for the syndrome + "prospective cohort" / "inception
cohort" / "longitudinal" / "registry" / "biobank" / "case-control" + the trigger. For each
hit, ask: *is this a new followed population, or another analysis of one already in the
database?* If the latter, add it as a `publication` on the existing cohort and its numbers as
`observations` — **never a duplicate cohort** (guide §1). Same-outbreak but different-sample
studies are separate cohorts linked via `related_cohorts`.

### 5.2 Deduplicate by population

Réunion chikungunya already shows the pattern (TELECHIK / Schilte / Marimoutou = three
cohorts; Duvignaud = another TELECHIK paper). Watch for cohort names, registration IDs
(NCT/ISRCTN), and identical N/site/recruitment dates. When in doubt, check the Methods
section for: "participants were drawn from the [named] cohort/study" → not a new cohort.

Common deduplication pitfalls:
- **RECOVER** has many papers from the same ~15,000-person cohort — all go on ONE cohort file
- **UK Biobank** COVID, brain, cardiac — all share the same denominator population
- **VA data** (Al-Aly et al.) — many organ-system papers, one VA COVID cohort (verify whether
  there are distinct VA cohorts or one large EHR-derived population used repeatedly)
- **Millennium Cohort Study** — >100 publications, one cohort
- **SLICE study** (Aucott/Rebman) — multiple papers, one cohort (already in database)

### 5.3 Prefer strong designs and specimen-banking cohorts

The gap matrices show where these are missing: prospective inception cohorts with unexposed
controls, and any cohort with banked **acute-phase** specimens. These are the highest-value
additions because they enable future biomarker work and strengthen causal inference.

Quality hierarchy for prioritisation (use, not a schema field — just guide your triage):
1. **Tier 1:** Prospective inception cohort, unexposed control group, banked acute-phase
   specimens, validated instruments, defined denominator, >80% follow-up
2. **Tier 2:** Prospective inception cohort, control group, validated instruments, defined
   denominator, no banked specimens or <80% follow-up
3. **Tier 3:** Retrospective cohort or registry, control group or population norms, validated
   instruments, denominator-defined
4. **Tier 4:** Convenience sample, self-selected survey, patient-organisation registry, no
   control group, no defined denominator

Flag Tier 3 and 4 cohorts with `self_selected`, `patient_reported`, `single_timepoint`,
`no_control` as appropriate. Add Tier 4 cohorts — the database needs them to show honest
evidentiary quality distributions — but do not let them outnumber Tier 1–2 cohorts for any
given trigger.

### 5.4 Grey literature and preprints are allowed but flagged

Preprints keep their DOI and get `type:preprint`; patient-org surveys/registries with no
DOI/PMID use a URL-only `type:grey_literature` publication and the `grey_literature` flag.
See guide §5.

### 5.5 Non-English literature

Cohorts published in languages other than English are in scope. Prioritise cohorts from
endemic regions where the trigger is common and the English-language literature is thin
(e.g., scrub typhus in Korean/Japanese literature, brucellosis in Turkish literature,
cerebral malaria in French-language African literature, Chagas in Portuguese/Spanish).
When adding a non-English cohort:
- Verify that you have adequate translation (human or reliable machine translation of the
  full text, not just the abstract)
- Record the original language in a `notes` field on the cohort or in `measure_verbatim`
- Flag `unverified_source` if you could not access/translate the full text and are working
  from an English abstract only — this is a genuine evidentiary caveat

### 5.6 Batch to be efficient

Collect and verify DOIs/PMIDs + headline numbers for ~5–10 candidates first, then author
the files in one pass, then one build + validate + commit. Resist the temptation to add
one cohort at a time — the build/validate/deploy loop has fixed overhead and batches
amortise it.

---

## 6. Registry / reference additions you will likely need

Add to `data/ref/` as required (guide §4; reuse before inventing, use HPO/LOINC/SNOMED/UCUM):

### 6.1 Pathogens/triggers (add to `data/ref/pathogens.json`)

Check existing entries (§2 table) before adding. New triggers likely needed:

| id | class | notes |
|---|---|---|
| `unknown-trigger` | `unknown` | For ME/CFS, fibromyalgia, and other idiopathic cohorts |
| `mixed-infectious` | `mixed` | For cohorts with heterogeneous/unknown infectious onsets |
| `gulf-war-exposures` | `environmental` | Added and ready (§3.2); reuse for other exposure syndromes (WTC dust, Agent Orange, Camp Lejeune) |
| `poliovirus` | `virus` | Post-polio syndrome |
| `parvovirus-b19` | `virus` | Parvovirus B19 arthropathy / fatigue |
| `enterovirus-coxsackie` | `virus` | Enterovirus / Coxsackie B chronic sequelae |
| `group-a-streptococcus` | `bacterium` | PANDAS, Sydenham chorea, ARF |
| `hepatitis-b-virus` | `virus` | Post-hepatitis B fatigue |
| `hepatitis-c-virus` | `virus` | Post-hepatitis C fatigue |
| `norovirus` | `virus` | Post-noroviral-enteritis IBS |
| `japanese-encephalitis-virus` | `virus` | Post-JE neurological sequelae |
| `nipah-virus` | `virus` | Post-Nipah neurological sequelae |
| `tick-borne-encephalitis-virus` | `virus` | Post-TBE fatigue/cognitive |
| `streptococcus-pneumoniae` | `bacterium` | Post-meningitis sequelae |
| `neisseria-meningitidis` | `bacterium` | Post-meningitis sequelae |
| `mycobacterium-tuberculosis` | `bacterium` | Post-TB lung disease, TB meningitis |
| `plasmodium-falciparum` | `protozoan` | Cerebral malaria sequelae |
| `mycoplasma-pneumoniae` | `bacterium` | Post-Mycoplasma fatigue, neurological |
| `orientia-tsutsugamushi` | `bacterium` | Scrub typhus sequelae |
| `leptospira-interrogans` | `bacterium` | Post-leptospirosis fatigue/CKD |
| `brucella-melitensis` | `bacterium` | Post-brucellosis fatigue |
| `toxoplasma-gondii` | `protozoan` | Post-toxoplasmosis / congenital |
| `trypanosoma-cruzi` | `protozoan` | Chagas chronic cardiomyopathy |

### 6.2 Case definitions (`case-def:` measures)

- `iom_nam_2015` (ME/CFS) — may already be in `case_definition` enum; add matching `case-def:` measure
- `canadian_consensus` (ME/CFS CCC 2003) — may already be in enum
- `international_consensus` (ME/CFS ICC 2011 / Carruthers) — may already be in enum
- `kansas_gwi` (Gulf War Illness, Steele 2000)
- `fukuda_gwi_1998` (CDC chronic multi-symptom illness for Gulf War, Fukuda 1998)
- `rome_iv_ibs` (Rome IV for PI-IBS — verify whether `sym:irritable-bowel-syndrome` already
  covers this or whether a separate case-def is needed)
- `pandas_swedo_1998` (PANDAS diagnostic criteria)
- `acr_fibromyalgia_1990`, `acr_fibromyalgia_2010`, `acr_fibromyalgia_2016` (Fibromyalgia
  ACR diagnostic criteria)

### 6.3 Instruments

- **DePaul Symptom Questionnaire (DSQ)** — core ME/CFS symptom inventory, also DSQ-PEM
  subscale for PEM
- **Bell disability scale** — ME/CFS functional impairment
- **PROMIS fatigue short form** — widely used across IACCs, standardised T-scores
- **COMPASS-31** — composite autonomic symptom score
- **Orthostatic Intolerance Questionnaire (OIQ)** — POTS/orthostatic intolerance
- **Nijmegen Clinical Screening Instrument (NCSI)** — Q-fever fatigue / multi-domain
  fatigue instrument
- **MASQ / PDQ** — cognitive symptom questionnaires
- **Rome IV diagnostic questionnaire** — for PI-IBS
- **YFAS / eating questionnaires** — if relevant for specific cohorts
- Verify whether SF-36 and Chalder Fatigue Scale already exist in `instruments.json`
  before adding.

### 6.4 Measures (add to `data/ref/measures.json`)

New measures beyond those implied by instruments above:
- `physio:tilt-table-drop` — haemodynamic response to tilt-table testing
- `physio:cpet-workload-drop` — 2-day CPET workload reduction at anaerobic threshold
  (`paired_change` value type)
- `physio:heart-rate-variability` — HRV parameters (mean_sd)
- `physio:cerebral-blood-flow-velocity` — Doppler CBFV during tilt (mean_sd)
- `event:multiple-sclerosis` — MS diagnosis as an outcome event
- `event:ocd-onset` — new-onset OCD for PANS/PANDAS
- `event:tic-onset` — new-onset tic disorder for PANS/PANDAS
- `event:sydenham-chorea` — chorea onset
- `event:seizure` — post-meningitis/encephalitis epilepsy
- `event:hearing-loss` — post-meningitis sensorineural hearing loss
- `func:return-to-work` — work/disability outcome (proportion or time_to_event)
- `func:activities-of-daily-living` — ADL dependency
- `lab:` analytes for immunophenotyping cohorts (cytokines, immune cell subsets,
  autoantibodies) — add as encountered, use LOINC where terms exist; add only when
  necessary, as these will proliferate rapidly
- Keep `sym:fatigue` and `sym:post-exertional-malaise` **always separate.**

---

## 7. Specimen banking inventory (cross-cutting search)

A cross-cutting to-do: find and add cohorts that have **banked acute-phase specimens**
(serum, PBMC, RNA, whole blood, CSF, tissue) regardless of trigger. These are the
highest-value cohorts for future biomarker work and are systematically absent from
the current database.

For each candidate in §4, note in your verification whether acute-phase specimens
were banked and whether they are available to external researchers. Add as an
Observation with `measure_id: lab:banked-specimens` and `value.type: presence` if the
schema supports this, or as a `qualitative` observation with `n_supporting` and a
`notes` field detailing specimen types, timepoints, and availability.

Known specimen-banking cohorts (verify and add):
- **UK ME/CFS Biobank** — serum, PBMC, RNA, whole blood (pre-existing, not acute-phase,
  but deeply characterised)
- **NIH RECOVER** — acute and convalescent COVID specimens
- **Yale LISTEN** — multi-omics, immune profiling (COVID and post-vaccine)
- **NIH intramural ME/CFS (Walitt/Nath)** — extensive multi-omics sampling
- **Millennium Cohort Study** — DoD serum repository (the Bjornevik EBV→MS paper used this)
- **NIH post-Lyme (Marques)** — banked specimens
- **UK Biobank COVID sub-study** — pre-pandemic baseline + post-COVID imaging and samples

---

## 8. Quality criteria for selecting among candidate cohorts

When you find multiple candidate cohorts for the same trigger, use these criteria to
prioritise. This is a judgement framework, not a rigid algorithm — two good criteria
can outweigh five weak ones.

### Primary criteria (weight these most heavily)
1. **Denominator is defined and reported.** A cohort with N=10,000 and a known
   denominator is strictly better than one with N=10,000 and an unknown response rate.
2. **Unexposed control group exists and is reported separately.** The comparator
   structure is the database's reason for existing.
3. **Acute-phase specimens were banked.** Binary: banked or not. If banked, are they
   available to external researchers? (This determines whether the cohort enables
   future discovery or only documents the past.)
4. **Follow-up ≥6 months with ≥2 timepoints.** Single-timepoint cohorts cannot
   distinguish trajectory from snapshot.
5. **A validated instrument was used at a standard timepoint.** Creates direct
   comparability across cohorts — the comparability signature machinery depends on this.

### Secondary criteria (tiebreakers)
6. **Diversity of the study population** (geographic, ethnic, socioeconomic, age range).
   A cohort from a LMIC setting where the trigger is endemic adds more value than a
   fifth cohort from a single high-income country.
7. **Sample size.** Larger N is better, but not at the expense of the primary criteria.
   A well-controlled N=100 is worth more than an uncontrolled survey N=10,000.
8. **Specificity of the trigger.** A cohort where the infecting pathogen was confirmed
   by PCR/serology is better than one where "flu-like illness" was the trigger.
9. **Availability of individual-level data** (open-access or by application). Not
   required for database entry, but worth noting for future harmonisation work.

### Exclusion criteria (do not add)
- **Meta-analyses, systematic reviews, pooled estimates.** Out of scope (guide §10).
- **Case reports or case series with N<10.** Too small to contribute meaningful
  aggregate observations.
- **No defined follow-up timepoint.** "At follow-up" with no specified interval is
  unextractable.
- **Trigger not identifiable.** "Post-infectious" with no pathogen class or named
  infection cannot be placed in the database framework.
- **Duplicate population** (already in database under a different name). §5.2.

---

## 9. Common extraction problems and how to handle them

### 9.1 The paper reports a percentage but no numerator/denominator
Use `value.type: proportion`, set `numerator` to `{"status":"measured_not_reported"}`,
`percent` to the reported value, and `precision` to `"approximate"`. Do not back-calculate
N unless the denominator is explicitly given — the risk of off-by-one errors from rounding
is real.

### 9.2 The paper reports only an effect size (OR/RR/HR) with no raw arm data
Use `value.type: effect_only`. Record the estimate, effect_type, CI, p_value, and
`adjusted_for[]` if available. Set `value` to `{"status":"not_applicable"}` (the raw
value is not reported) and `comparator.effect` to the effect estimate. This is common
in administrative-health-data studies (VA, Maccabi, Millennium Cohort).

### 9.3 The same outcome is reported at multiple timepoints
Create one Observation per timepoint. The `timepoint_band` field groups them for display;
the build does not collapse them. This is correct behaviour — a proportion at 3 months
and a proportion at 12 months are different facts.

### 9.4 The cohort reports both clinician-assessed and patient-reported outcomes for the same measure
Create separate Observations — the `method.ascertainment` field differs and they will
receive different comparability signatures. This is correct: clinician-ascertained fatigue
is not directly comparable to self-reported fatigue, and the signatures should reflect that.

### 9.5 The paper uses a composite outcome (e.g., "met ≥2 of fatigue, pain, cognitive")
Record the composite as an Observation with `measure_verbatim` quoting the exact composite
definition. If the components are also reported separately, record them as additional
Observations. Map the composite to the most specific existing measure, or create a new
composite measure with a `boundary_note` describing the components.

### 9.6 The control group is reported as a separate cohort in a different paper
Use `comparator.group: "external"` and cite the control-group publication in
`comparator.source`. This is common when a disease cohort is compared to published
population norms.

### 9.7 The cohort is an RCT arm
RCTs are out of scope as designs, but the participants form a followed population with
extractable baseline and outcome data. Add the cohort with the `notes` field recording
that participants were drawn from an RCT, and flag `single_timepoint` if only end-of-trial
data are available. The comparator is the other arm(s) of the same trial. This is most
relevant for the Klempner Lyme retreatment trials and for post-sepsis intervention trials
with longitudinal follow-up of both arms.

---

## 10. Targets and acceptance

- **Coverage goal:** at least one strong (Tier 1–2: prospective, controlled, or
  specimen-banking) cohort per trigger/disease in §4, plus flagged weak cohorts where
  that is all that exists.
- **ME/CFS minimum:** at least 3 ME/CFS cohorts (one large phenotyping, one community/
  epidemiological, one biobank) by the end of the first expansion batch.
- **Long COVID minimum:** at least one denominator-defined controlled cohort (RECOVER or
  Zurich) and one administrative-health-data rate cohort (VA or Maccabi).
- **Trigger diversity:** new pathogen entries for poliovirus, parvovirus B19,
  group A streptococcus, and at least 3 other pathogens from §6.1.
- **Every PR:** passes `python scripts/build_pais_cohorts.py --check`; every publication
  has a DOI/PMID or a flagged grey-literature URL; every observation has a
  `source_locator` and a real `measure_id`; missing numbers are typed sentinels;
  weak/preprint/grey cohorts carry `flags`; regenerated artifacts committed. (Full
  checklist: guide §9.)
- **Watch the gap matrices** on the live site after each batch — the
  newly-empty-then-filled cells are your scoreboard, and the "largest comparable set" per
  measure is the headline metric to grow (e.g., get several ME/CFS cohorts using the same
  instrument at the same timepoint into one comparability signature).

---

## 11. Order of work (suggested, revised)

This order maximises early impact on the gap matrices and defers work blocked on schema
decisions:

### Phase 1 — Foundation (ME/CFS, Long COVID controls, schema prerequisites)
1. **Schema prerequisites — DONE.** The `environmental` pathogen class and
   `gulf-war-exposures` trigger are already in place (§3.2); `unknown-trigger` and
   `mixed-infectious` exist for idiopathic/mixed onsets. No enum work remains.
2. **ME/CFS measure/instrument additions** — DSQ, IOM/CCC/ICC case definitions,
   Bell scale, CPET/tilt measures. Do these before authoring ME/CFS cohort files so
   records validate on first build.
3. **ME/CFS cohorts (§4.A)** — start with UK ME/CFS Biobank and NIH Walitt/Nath (the
   specimen-banking, deep-phenotyping anchors), then MCAM, then DePaul/Jason.
4. **Long COVID controlled cohorts (§4.B)** — RECOVER + Zurich + at least one
   administrative-health-data cohort (Al-Aly VA or Maccabi).

### Phase 2 — Comparator classes and Lyme
5. **Post-sepsis/PICS (§4.I)** — Iwashyna 2010 and BRAIN-ICU are the anchors.
6. **Lyme extensions (§4.C)** — Klempner, Wormser, and additional SLICE publications
   on the existing `aucott-slice-ptlds` cohort.
7. **Fibromyalgia (§4.K)** — ACR criteria cohorts, under `unknown-trigger`.

### Phase 3 — Trigger diversity and landmark studies
8. **EBV→MS (§4.F1, Bjornevik)** — a landmark that showcases `event:`/`effect_only`
   at scale.
9. **Gulf War Illness (§4.D)** — trigger class ready (`environmental`); start with
   Steele/Kansas and Millennium Cohort.
10. **PANS/PANDAS (§4.H)** — group A strep → OCD/tics; Swedo NIMH cohorts.
11. **Post-polio (§4.F2)** — classic post-viral fatigue, new trigger.
12. **Post-Ebola expansion (§4.E)** — PostEboGui (Guinea).

### Phase 4 — Breadth and LMIC representation
13. **Post-meningitis/encephalitis (§4.L)** — bacterial meningitis survivor cohorts.
14. **Post-malaria (§4.M)** — cerebral malaria cognitive outcomes.
15. **Post-hepatitis (§4.F6)** — B and C fatigue cohorts.
16. **Remaining post-viral (§4.F)** — parvovirus B19, enterovirus/Coxsackie, JE, Nipah.
17. **Post-enteric IBS expansion (§4.G)** — Spanish Salmonella/Campylobacter cohorts.
18. **Second cohorts for replication** — dengue, Q-fever, Zika, WNV, RRV (§4.F4, §4.J).

### Phase 5 — Niche triggers and comparators
19. **Post-surgical/post-traumatic comparators (§4.O)** — optional, low priority.
20. **Chronic infection comparators (§4.P)** — HIV, chronic HCV, chronic Chagas.
21. **Brucellosis, leptospirosis, scrub typhus, Mycoplasma (§4.N)** — fill out
    taxonomic coverage.

The environmental trigger class is already in place, so Gulf War cohorts are unblocked. Do
the ME/CFS measure/instrument additions **before** authoring ME/CFS cohorts, so the records
validate on first build.

---

## 12. Tracking your progress

Keep a running log of verification decisions in your PR description or a separate
`VERIFICATION_LOG.md` (not committed — it's your working notes):

```
Trigger: EBV → MS (Bjornevik 2022)
  Cohort identified: Millennium Cohort Study / DoD Serum Repository
  Dedup check: NOT in database; no overlapping cohort file
  Publication: Bjornevik et al. 2022, Science, PMID 35025605 — VERIFIED
  Design: nested case-control within longitudinal cohort, 10 million+ person-years
  Control: EBV-seronegative at baseline who remained seronegative (rare — 1 of 801 MS cases)
  Key numbers: HR ~32 for EBV+ vs EBV−; N=801 MS cases vs ~1,500 matched controls
  Value type: effect_only (HR)
  New measures needed: event:multiple-sclerosis
  Flags: none — strong design
  Decision: ADD
```

This makes your verification auditable and helps the maintainer review at speed.