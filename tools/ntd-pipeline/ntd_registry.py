"""
ntd_registry.py
---------------
Canonical seed data for the NTD intelligence pipeline.

Two things live here, because neither can be pulled cleanly from an API:

1) NTD_LIST  - the 21 disease groups on the WHO NTD list (noma added Dec 2023).
               Ontology IDs are RESOLVED AT RUNTIME (opentargets.resolve_disease)
               rather than hardcoded, so we never ship a stale/wrong EFO/MONDO id.
               A few high-confidence ids are pre-filled as hints.

2) POST_ACUTE - a curated knowledge table answering "does this NTD have a
                post-acute / chronic-sequela syndrome?".  This is a literature
                question, not an API field, so it is maintained by hand with
                short source tags.  `kind` distinguishes a genuine post-acute
                infection syndrome (PAIS - the Long-COVID analog) from chronic
                progressive disease or downstream sequelae.

Everything here is meant to be edited. Treat it as data, not code.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NTD:
    key: str                      # stable slug
    name: str                     # WHO display name
    pathogen: str                 # bacteria | virus | protozoa | helminth | fungus | mite | venom | polymicrobial
    search_terms: list            # names to resolve against Open Targets / used for CT.gov cond=
    efo_hint: Optional[str] = None  # optional pre-known EFO/MONDO id (verified at runtime anyway)
    note: str = ""


# --- The official WHO 21 (some groups split for burden/therapeutic granularity) ---
# WHO groups "dengue and chikungunya" as ONE entry; we split them internally because
# their burden, drugs, and post-acute syndromes differ. `note` records the grouping.
NTD_LIST = [
    NTD("buruli_ulcer", "Buruli ulcer", "bacteria",
        ["Buruli ulcer", "Mycobacterium ulcerans infection"], efo_hint="EFO_0007124"),
    NTD("chagas", "Chagas disease", "protozoa",
        ["Chagas disease", "American trypanosomiasis"], efo_hint="EFO_0004264"),
    NTD("dengue", "Dengue", "virus",
        ["dengue", "dengue fever", "severe dengue"], efo_hint="EFO_0001056",
        note="WHO groups dengue+chikungunya as one NTD entry; split here."),
    NTD("chikungunya", "Chikungunya", "virus",
        ["chikungunya", "chikungunya fever"], efo_hint="EFO_0007200",
        note="WHO groups dengue+chikungunya as one NTD entry; split here."),
    NTD("dracunculiasis", "Dracunculiasis (Guinea-worm disease)", "helminth",
        ["dracunculiasis", "Guinea worm disease"]),
    NTD("echinococcosis", "Echinococcosis", "helminth",
        ["echinococcosis", "hydatid disease"], efo_hint="EFO_0007309"),
    NTD("foodborne_trematodiases", "Foodborne trematodiases", "helminth",
        ["opisthorchiasis", "clonorchiasis", "fascioliasis", "paragonimiasis"]),
    NTD("hat", "Human African trypanosomiasis (sleeping sickness)", "protozoa",
        ["human African trypanosomiasis", "sleeping sickness"], efo_hint="EFO_0007360"),
    NTD("leishmaniasis", "Leishmaniasis", "protozoa",
        ["leishmaniasis", "visceral leishmaniasis", "kala-azar"], efo_hint="EFO_0004257"),
    NTD("leprosy", "Leprosy (Hansen's disease)", "bacteria",
        ["leprosy", "Hansen disease"], efo_hint="EFO_0005066"),
    NTD("lymphatic_filariasis", "Lymphatic filariasis", "helminth",
        ["lymphatic filariasis", "elephantiasis"], efo_hint="EFO_0007370"),
    NTD("mycetoma", "Mycetoma, chromoblastomycosis and other deep mycoses", "fungus",
        ["mycetoma", "chromoblastomycosis", "eumycetoma"]),
    NTD("noma", "Noma (cancrum oris)", "polymicrobial",
        ["noma", "cancrum oris", "necrotizing ulcerative stomatitis"],
        note="Added to WHO NTD list December 2023 (21st NTD)."),
    NTD("onchocerciasis", "Onchocerciasis (river blindness)", "helminth",
        ["onchocerciasis", "river blindness"], efo_hint="EFO_0007438"),
    NTD("rabies", "Rabies", "virus",
        ["rabies"], efo_hint="EFO_0001064"),
    NTD("scabies", "Scabies and other ectoparasitoses", "mite",
        ["scabies"], efo_hint="EFO_0007469"),
    NTD("schistosomiasis", "Schistosomiasis", "helminth",
        ["schistosomiasis", "bilharzia"], efo_hint="EFO_0007488"),
    NTD("sth", "Soil-transmitted helminthiases", "helminth",
        ["ascariasis", "trichuriasis", "hookworm infection", "soil-transmitted helminthiasis"]),
    NTD("snakebite", "Snakebite envenoming", "venom",
        ["snakebite envenoming", "snake envenomation"]),
    NTD("cysticercosis", "Taeniasis / cysticercosis", "helminth",
        ["cysticercosis", "neurocysticercosis", "taeniasis"], efo_hint="EFO_0007511"),
    NTD("trachoma", "Trachoma", "bacteria",
        ["trachoma"], efo_hint="EFO_0007520"),
    NTD("yaws", "Yaws (endemic treponematoses)", "bacteria",
        ["yaws", "endemic treponematosis"]),
]

# Supplemental viral diseases — high global burden, same page template as NTDs
# but not on the official WHO NTD list (shown in a separate index section).
SUPPLEMENTAL_VIRAL = [
    NTD("measles", "Measles", "virus",
        ["measles", "rubeola"], efo_hint="EFO_0007184",
        note="Supplemental viral disease — not on WHO NTD list; included for post-viral research parity."),
    NTD("yellow_fever", "Yellow fever", "virus",
        ["yellow fever"], efo_hint="EFO_0007187",
        note="Supplemental viral disease — not on WHO NTD list."),
    NTD("zika", "Zika virus disease", "virus",
        ["zika", "zika virus infection", "zika fever"], efo_hint="EFO_0007690",
        note="Supplemental viral disease — not on WHO NTD list."),
]

SUPPLEMENTAL_KEYS = {n.key for n in SUPPLEMENTAL_VIRAL}


def all_diseases() -> list:
    """WHO NTD rows plus supplemental viral diseases for rendering."""
    return NTD_LIST + SUPPLEMENTAL_VIRAL


def is_supplemental(key: str) -> bool:
    return key in SUPPLEMENTAL_KEYS


# --- Post-acute / chronic-sequela knowledge table -----------------------------
# kind:
#   "PAIS"     -> distinct post-acute INFECTION syndrome emerging/persisting after
#                 the acute episode (the Long-COVID analog) - highest relevance to
#                 post-viral / post-acute research programs.
#   "chronic"  -> disease is chronic/progressive by nature after infection.
#   "sequela"  -> lasting damage/disability after cure (structural, not a syndrome).
#   "none"     -> no meaningful post-acute phase.
@dataclass
class PostAcute:
    has: bool
    kind: str            # PAIS | chronic | sequela | none
    syndrome: str        # name of the syndrome / sequela
    onset: str           # typical timing
    source: str          # short citation tag(s)


POST_ACUTE = {
    "chagas": PostAcute(True, "PAIS",
        "Chronic Chagas cardiomyopathy + digestive megasyndromes (megaesophagus/megacolon)",
        "years-to-decades after acute infection",
        "WHO Chagas fact sheet; Nunes 2018 Circulation"),
    "chikungunya": PostAcute(True, "PAIS",
        "Post-chikungunya chronic inflammatory rheumatism / chronic arthralgia",
        "weeks-to-years post-acute",
        "Zaid 2021 Lancet ID; WHO"),
    "dengue": PostAcute(True, "PAIS",
        "Post-dengue fatigue syndrome / prolonged post-viral fatigue",
        "weeks-to-months post-acute",
        "Seet 2007; Garcia 2011"),
    "leishmaniasis": PostAcute(True, "PAIS",
        "Post-kala-azar dermal leishmaniasis (PKDL) after visceral leishmaniasis",
        "months-to-years after VL treatment",
        "Zijlstra 2003 Lancet ID; WHO"),
    "hat": PostAcute(True, "sequela",
        "Neuropsychiatric / sleep-cycle sequelae after CNS-stage disease",
        "post-treatment",
        "WHO HAT technical reports"),
    "snakebite": PostAcute(True, "sequela",
        "Chronic disability: amputation, chronic kidney disease, chronic pain, PTSD",
        "post-envenoming",
        "WHO snakebite strategy 2019; Waiddyanatha 2022"),
    "onchocerciasis": PostAcute(True, "chronic",
        "Chronic dermatitis, vision loss/blindness, onchocerciasis-associated epilepsy / nodding syndrome",
        "chronic",
        "Colebunders 2018 (nodding syndrome); WHO"),
    "lymphatic_filariasis": PostAcute(True, "chronic",
        "Chronic lymphoedema / elephantiasis, hydrocele",
        "chronic morbidity",
        "WHO LF fact sheet"),
    "leprosy": PostAcute(True, "sequela",
        "Chronic peripheral neuropathy, disability, immune-mediated reactions (ENL/type-1)",
        "during/after treatment",
        "WHO leprosy guidelines"),
    "schistosomiasis": PostAcute(True, "chronic",
        "Chronic hepatic/urogenital fibrosis; bladder cancer risk; female genital schistosomiasis",
        "chronic",
        "Colley 2014 Lancet"),
    "cysticercosis": PostAcute(True, "chronic",
        "Neurocysticercosis -> chronic epilepsy (leading cause of acquired epilepsy in endemic areas)",
        "chronic",
        "Garcia 2020 NEJM"),
    "trachoma": PostAcute(True, "sequela",
        "Conjunctival scarring -> trichiasis -> irreversible blindness",
        "chronic/late",
        "WHO trachoma (SAFE)"),
    "buruli_ulcer": PostAcute(True, "sequela",
        "Contractures, deformity, functional limitation after healing",
        "post-treatment",
        "WHO Buruli ulcer"),
    "noma": PostAcute(True, "sequela",
        "Severe facial disfigurement, trismus, functional (eating/speech) impairment in survivors",
        "post-acute (survivors)",
        "Srour 2015; WHO"),
    "echinococcosis": PostAcute(True, "chronic",
        "Chronic cystic/alveolar organ disease; recurrence after surgery",
        "chronic",
        "WHO echinococcosis"),
    "foodborne_trematodiases": PostAcute(True, "chronic",
        "Chronic biliary disease; cholangiocarcinoma (Opisthorchis/Clonorchis)",
        "chronic/late",
        "IARC group-1 carcinogen; WHO"),
    "sth": PostAcute(True, "chronic",
        "Chronic anaemia, malnutrition, growth & cognitive impairment (children)",
        "chronic morbidity",
        "WHO STH fact sheet"),
    "mycetoma": PostAcute(True, "chronic",
        "Chronic progressive subcutaneous destruction, disability, amputation",
        "chronic by nature",
        "WHO mycetoma"),
    "yaws": PostAcute(True, "chronic",
        "Chronic destructive skin/bone/cartilage lesions if untreated",
        "chronic/late",
        "WHO yaws eradication"),
    "scabies": PostAcute(True, "sequela",
        "Secondary bacterial infection -> post-streptococcal (acute rheumatic fever, glomerulonephritis)",
        "downstream",
        "Romani 2015 Lancet ID"),
    "dracunculiasis": PostAcute(False, "none",
        "Transient joint involvement; no defined post-acute syndrome (near eradication)",
        "-",
        "WHO GWEP"),
    "rabies": PostAcute(False, "none",
        "Essentially uniformly fatal once symptomatic - no post-acute phase",
        "-",
        "WHO rabies"),
    "measles": PostAcute(True, "sequela",
        "Subacute sclerosing panencephalitis (SSPE); post-measles immune amnesia; bronchiectasis",
        "months-to-years post-infection",
        "WHO measles; Laksono 2020 Science; Campbell 2019"),
    "yellow_fever": PostAcute(True, "sequela",
        "Post-vaccine neurological events (YEL-AND); chronic fatigue in survivors (rare)",
        "days-to-weeks post-vaccine or post-infection",
        "WHO yellow fever; Lindsey 2016"),
    "zika": PostAcute(True, "PAIS",
        "Guillain-Barré syndrome; congenital Zika syndrome (vertical transmission)",
        "days-to-months post-acute",
        "Cao-Lormeau 2016 NEJM; WHO Zika"),
}


def get_post_acute(key: str) -> PostAcute:
    return POST_ACUTE.get(key, PostAcute(False, "none", "unknown", "-", "not curated"))
