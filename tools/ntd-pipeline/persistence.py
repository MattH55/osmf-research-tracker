"""
persistence.py
--------------
Literature percentages for persistent / post-infectious symptoms per NTD.

This is the substantive new data layer requested for the hosted section:
"does this NTD have a documented post-infectious syndrome, and what proportion
of patients have persistent symptoms?"

It EXTENDS ntd_registry.POST_ACUTE (which carries has/kind/syndrome/onset).
Here we add the quantified persistence figures, each with source tags and an
evidence-strength note. Where the literature does not support a single number,
`pct` is None and `detail` explains why (chronic-by-nature, structural sequela,
uniformly fatal, or not yet quantified).

All percentages below are drawn from peer-reviewed meta-analyses / cohort studies
(2003-2026). Verify against the cited source before altering. Numbers are the
proportion of the stated denominator population, NOT of all infected unless said.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Persistence:
    syndrome: str                 # name of the post-infectious syndrome
    pct: Optional[str]            # display string, e.g. "~40%" or "5-10% to 50-60%"
    denominator: str              # who the % is OF
    detail: str                   # one-line quantitative summary
    timeframe: str                # when it manifests / how long it persists
    strength: str                 # strong | moderate | limited
    sources: list = field(default_factory=list)


# key -> Persistence   (keys match ntd_registry.NTD.key)
PERSISTENCE = {
    "chikungunya": Persistence(
        syndrome="Chronic chikungunya arthritis / chronic inflammatory rheumatism",
        pct="~40%",
        denominator="symptomatic cases",
        detail="Persistent arthralgia >=3 months in a pooled ~40% (95% CI 31-49%); "
               "cohort range 7-79%; Americas meta-analyses up to 52%.",
        timeframe="months to years post-acute",
        strength="strong (multiple meta-analyses)",
        sources=["Rodriguez-Morales 2016 (pooled 40%)",
                 "Bonifay 2024 Lancet Infect Dis",
                 "Paixao 2018 (43% >3 mo)",
                 "Webb 2024 PLoS Negl Trop Dis (44% chronic)"]),

    "dengue": Persistence(
        syndrome="Post-dengue / post-infectious fatigue",
        pct="~20%",
        denominator="confirmed dengue patients",
        detail="Pooled post-infectious fatigue 20% (95% CI 10-36%); single cohorts "
               "25% (Seet 2007) and 32.3% at 2 months (Colombo 2021).",
        timeframe="weeks to months post-acute",
        strength="moderate-strong",
        sources=["eClinicalMedicine 2024 meta-analysis (PIF 20%)",
                 "Seet 2007 (25%)",
                 "Colombo Dengue Study 2021 (32.3%)"]),

    "chagas": Persistence(
        syndrome="Chronic Chagas cardiomyopathy + digestive megasyndromes",
        pct="~30% cardiac / ~10% digestive",
        denominator="chronically infected",
        detail="~30% develop chronic cardiomyopathy over 5-30 yr; ~10% develop "
               "digestive megasyndromes; ~60-70% stay in the indeterminate (silent) form.",
        timeframe="5-30 years after acute infection",
        strength="strong (consensus)",
        sources=["Nunes 2018 Circulation",
                 "WHO Chagas fact sheet",
                 "Rassi 2010 Lancet"]),

    "leishmaniasis": Persistence(
        syndrome="Post-kala-azar dermal leishmaniasis (PKDL)",
        pct="5-10% (ISC) -> 50-60% (E. Africa)",
        denominator="treated visceral leishmaniasis patients",
        detail="Dermal sequela after apparently cured VL: 5-10% (up to 20%) in the "
               "Indian subcontinent over 2-3 yr; 50-60% in Sudan/East Africa within 0-12 mo.",
        timeframe="months to years after VL cure",
        strength="strong",
        sources=["Zijlstra 2003 Lancet Infect Dis",
                 "Ganguly 2015",
                 "WHO leishmaniasis"]),

    "cysticercosis": Persistence(
        syndrome="Neurocysticercosis -> chronic epilepsy",
        pct="~30% of epilepsy",
        denominator="epilepsy cases in endemic areas",
        detail="Neurocysticercosis accounts for ~30% of epilepsy cases in endemic "
               "regions; a leading cause of acquired epilepsy worldwide.",
        timeframe="chronic (years)",
        strength="strong",
        sources=["Garcia 2020 NEJM", "WHO taeniasis/cysticercosis"]),

    "onchocerciasis": Persistence(
        syndrome="Onchocercal skin/eye disease; onchocerciasis-associated epilepsy",
        pct=None,
        denominator="infected in high-transmission foci",
        detail="Chronic dermatitis and vision loss are near-universal with heavy "
               "infection; epilepsy (incl. nodding syndrome) prevalence is elevated "
               "2-3x in highly endemic villages. Single pooled % not established.",
        timeframe="chronic",
        strength="moderate",
        sources=["Colebunders 2018", "WHO onchocerciasis"]),

    "lymphatic_filariasis": Persistence(
        syndrome="Chronic lymphoedema / hydrocele",
        pct=None,
        denominator="infected",
        detail="A substantial subset of infected progress to overt chronic disease "
               "(lymphoedema/elephantiasis, hydrocele); ~36 million with chronic "
               "manifestations globally. Proportion varies widely by setting.",
        timeframe="chronic morbidity",
        strength="moderate",
        sources=["WHO LF fact sheet"]),

    "snakebite": Persistence(
        syndrome="Chronic post-envenoming disability (CKD, amputation, chronic pain, PTSD)",
        pct=None,
        denominator="survivors of envenoming",
        detail="Long-term physical disability, chronic kidney disease, amputation and "
               "psychological sequelae in a meaningful minority of survivors; global "
               "estimate ~400,000 with permanent sequelae/yr. Single pooled % not established.",
        timeframe="chronic post-envenoming",
        strength="moderate",
        sources=["WHO snakebite strategy 2019", "Waiddyanatha 2022"]),

    "hat": Persistence(
        syndrome="Neuropsychiatric / sleep-cycle sequelae (CNS-stage)",
        pct=None,
        denominator="CNS-stage survivors",
        detail="Residual neuropsychiatric and sleep-architecture abnormalities after "
               "successful treatment of second-stage disease; not systematically quantified.",
        timeframe="post-treatment",
        strength="limited",
        sources=["WHO HAT technical reports"]),

    "leprosy": Persistence(
        syndrome="Chronic peripheral neuropathy / grade-2 disability",
        pct="~5-10% grade-2 disability",
        denominator="newly diagnosed",
        detail="Visible (grade-2) disability present in roughly 5-10% of new cases at "
               "diagnosis; chronic nerve damage and immune reactions persist after cure.",
        timeframe="at/after diagnosis",
        strength="moderate",
        sources=["WHO leprosy guidelines / weekly epidemiological record"]),
}


def get(key: str):
    """Return Persistence for a key, or None if not quantified/curated here."""
    return PERSISTENCE.get(key)
