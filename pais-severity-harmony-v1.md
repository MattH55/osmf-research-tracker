# pais-severity-harmony-v1 — severity/burden harmonisation rulesets

Versioned mapping tables that let acute-phase factors be compared across pathogens **without
overwriting the native measure**. Every harmonised `Predictor` record cites `"ruleset":
"pais-severity-harmony-v1"` and carries its own `mapped_level` + `mapping_rationale` +
`confidence`, so any consumer can reject this mapping and remap from the native values.

Only **three** constructs are harmonised in v2.1. Everything else stays native-only.

---

## 1. `acute_severity` → `ordinal_0_4`

A single ordinal scale for "how sick were they in the acute phase", onto which each cohort's
native severity measure is mapped.

| Level | Definition | Typical native mappings |
|---|---|---|
| **0** | Asymptomatic / subclinical | seropositive, no acute illness |
| **1** | Symptomatic, ambulatory, no functional limitation | mild self-limited illness; low symptom-count |
| **2** | Ambulatory with functional limitation | bed rest / off work but not hospitalised; high acute symptom burden; WHO dengue "warning signs" without hospitalisation |
| **3** | Hospitalised (ward) | hospital admission without ICU; WHO ordinal 4–5 for COVID-19; severe dengue admitted to ward |
| **4** | ICU / organ support | ICU admission, mechanical ventilation, vasopressors, WHO ordinal 6–9 |

Notes:
- A **continuous or composite native score** (e.g. the Dubbo somatic symptom severity score) maps
  to a level by where the study's own cut-points place the subject; when only "per 1 SD" contrasts
  are reported, record the native contrast and set `mapped_level: null` with
  `confidence: "uncertain"`.
- Binary "hospitalised (yes/no)" maps yes→3, no→(1 or 2 per the study's ambulatory description).
- Do not infer a level the source does not support; use `confidence` honestly
  (`exact | close | broad | uncertain`).

## 2. `viral_burden` → `ordinal_0_3`

| Level | Definition |
|---|---|
| **0** | Below detection / cleared |
| **1** | Low (high Ct, low copy number, brief viraemia) |
| **2** | Moderate |
| **3** | High (low Ct, high copy number, prolonged viraemia/shedding, high NS1 antigenaemia) |

Native measures: RT-PCR Ct value (inverse), copies/mL, NS1 antigen level, days of detectable
virus. Ct and copy-number map in opposite directions — record the native `contrast` explicitly.

## 3. `inflammatory_burden` → `ordinal_0_3`

| Level | Definition |
|---|---|
| **0** | Within reference range |
| **1** | Mildly elevated |
| **2** | Moderately elevated |
| **3** | Markedly elevated / cytokine-storm range |

Native measures: CRP, ferritin, neutrophil-lymphocyte ratio, acute cytokine panel (IL-6, IL-1β,
IFN-γ, TNF-α, IL-10). Map by the study's own reference cut-points; where only a per-unit contrast
is reported, keep it native and set `mapped_level: null`.

---

## Change control

- This file is the authority for `ruleset: "pais-severity-harmony-v1"`. Changing any mapping
  requires a new ruleset id (`-v2`) — never edit v1 in place, because harmonised values already
  cite it.
- Harmonisation is **additive and rejectable**: the native `factor_verbatim` and native value are
  always stored on the Predictor; `harmonised` is an opinion layered on top.
- No pooled/meta-analytic estimate is derived from harmonised levels. They exist to align
  rows in the factor × pathogen and replication views, not to average across contrasts.
