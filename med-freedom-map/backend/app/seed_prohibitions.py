"""National-law defaults: explicit Prohibited access cells + jurisdiction regulation profiles.

Empty map cells mean unresearched — NOT prohibited. This module fills classical
psychedelics / cannabis / MAID defaults from UN-convention and national scheduling
patterns, with known exceptions left to existing seed rows (never overwritten).
"""
from datetime import date

from .models import (
    LegalStatus as LS,
    OversightQuality as OQ,
    AccessPathway as AP,
    PriceConfidence as PC,
    Confidence as CF,
    Volatility as VL,
)

LV = date(2026, 7, 1)

# Classical / atypical psychedelics: typically Schedule I / Class A / BtMG non-verkehrsfähig
# unless a specific AccessCell already exists (Oregon, AU TGA, CH BAG, etc.).
CONTROLLED_PSYCHEDELICS = [
    "proc-psilocybin-trd",
    "proc-psilocybin-eol",
    "proc-psilocybin-microdose",
    "proc-mdma-ptsd",
    "proc-dmt-depression",
    "proc-lsd-anxiety",
    "proc-mescaline-therapy",
    "proc-ayahuasca",
    "proc-5meo-dmt",
    "proc-ibogaine-addiction",
]

# Ketamine is scheduled but medical use is widespread — do NOT blanket-prohibit.
# Medical cannabis / MAID handled separately.


def _prohibited(
    proc_id,
    jur_id,
    *,
    authority,
    legal_basis,
    details,
    confidence=CF.MODERATE,
    volatility=VL.STABLE,
    sources=None,
):
    return {
        "procedure_id": proc_id,
        "jurisdiction_id": jur_id,
        "legal_status": LS.PROHIBITED,
        "access_pathway": AP.NONE,
        "oversight_quality": OQ.HIGH,
        "regulatory_authority": authority,
        "legal_basis": legal_basis,
        "access_pathway_details": details,
        "eligibility_requirements": "No lawful therapeutic access pathway for the general public under current national rules (trials or narrow exemptions may exist separately).",
        "provider_requirements": "Cannot lawfully market or operate a commercial therapy program without a specific statutory/regulatory exception.",
        "oversight_notes": "Prohibition is the default under national controlled-substance law; presence of underground activity does not create a legal pathway.",
        "estimated_cost_range_usd": "N/A — no legal market",
        "cost_notes": "No lawful price discovery.",
        "residency_travel_notes": "Travel for this therapy typically means going to a jurisdiction with an explicit exception — check destination law carefully.",
        "risk_notes": "Criminal liability for possession, supply, or practice; product quality risks if sourced illicitly.",
        "arbitrage_summary": "Prohibited under national law. Seek only jurisdictions with explicit regulated, expanded-access, or decrim pathways — not this cell.",
        "price_usd": None,
        "price_basis": "cash_pay",
        "price_confidence": PC.UNKNOWN,
        "total_access_cost_usd": None,
        "confidence": confidence,
        "volatility": volatility,
        "verified_by": "seed_prohibitions_v1",
        "last_verified": LV,
        "sources": sources or [],
        "setup_requirements": None,  # filled later if needed
    }


# Per-jurisdiction national law notes for classical psychedelics (sovereign + federal).
# Subnational US states inherit federal Schedule I unless an existing seed row already maps them.
JUR_PSYCHEDELIC_LAW = {
    "jur-us-federal": {
        "authority": "DEA / FDA (Controlled Substances Act)",
        "basis": "21 U.S.C. § 812 — Schedule I for LSD, psilocybin, MDMA, DMT, mescaline, etc.; no accepted medical use federally (except approved products like esketamine for ketamine class).",
        "details": "Federal Schedule I prohibits manufacture, distribution, and possession outside DEA-registered research. State programs (OR/CO) create subnational tension but do not repeal federal law.",
        "sources": [{"title": "DEA Controlled Substance Schedules", "url": "https://www.dea.gov/drug-information/drug-scheduling"}],
    },
    "jur-uk": {
        "authority": "Home Office / MHRA (Misuse of Drugs Act 1971)",
        "basis": "Class A: LSD, psilocybin/psilocin, DMT, MDMA; no routine medical prescribing pathway.",
        "details": "Clinical trials possible under licence; no Oregon-style service centres. Medical cannabis is a separate Class B / specialty pathway.",
        "sources": [{"title": "UK Misuse of Drugs Act", "url": "https://www.gov.uk/government/publications/controlled-drugs-list--2"}],
    },
    "jur-de": {
        "authority": "BfArM / BtMG",
        "basis": "Betäubungsmittelgesetz — classical psychedelics largely non-marketable narcotics; medical exceptions narrow.",
        "details": "Research possible under narcotics permits; no general therapeutic programme for psilocybin/MDMA/LSD as of review date.",
        "sources": [{"title": "BfArM narcotics", "url": "https://www.bfarm.de"}],
    },
    "jur-fr": {
        "authority": "ANSM / Code de la santé publique",
        "basis": "Stupefiants scheduling for classical psychedelics; no general medical access programme.",
        "details": "Research/ATU-class pathways are exceptional; commercial psychedelic therapy not authorised.",
        "sources": [{"title": "ANSM", "url": "https://ansm.sante.fr"}],
    },
    "jur-es": {
        "authority": "AEMPS",
        "basis": "Spanish narcotics control aligned with UN conventions — classical psychedelics prohibited outside research.",
        "details": "Private consumption nuances do not create a regulated therapy supply.",
        "sources": [{"title": "AEMPS", "url": "https://www.aemps.gob.es"}],
    },
    "jur-nl": {
        "authority": "IGJ / Opiumwet",
        "basis": "Hard drugs list includes psilocybin mushrooms, LSD, MDMA, DMT; sclerotia (truffles) are a famous exception for psilocin-containing material.",
        "details": "Do not conflate legal truffle retail with lawful MDMA/LSD/mushroom therapy clinics. MDMA/LSD remain prohibited outside research.",
        "sources": [{"title": "Dutch Opium Act overview", "url": "https://www.government.nl"}],
        # For NL we still prohibit MDMA/LSD/etc. but may skip some psilocybin rows if seed has truffle access
    },
    "jur-be": {
        "authority": "FAMHP",
        "basis": "Narcotics law — classical psychedelics prohibited outside authorised research.",
        "details": "No general psychedelic therapy licensing.",
        "sources": [],
    },
    "jur-se": {
        "authority": "Läkemedelsverket / police narcotics control",
        "basis": "Narcotic drugs classification — classical psychedelics illegal.",
        "details": "Research possible under permit; no public therapy programme.",
        "sources": [],
    },
    "jur-po": {  # Poland
        "authority": "URPL / Polish Act on Counteracting Drug Addiction",
        "basis": "Group I-P controlled substances include LSD, psilocybin, MDMA, DMT, etc.",
        "details": "No regulated psychedelic therapy pathway.",
        "sources": [],
    },
    "jur-pt": {
        "authority": "INFARMED / decrim law (2001)",
        "basis": "Personal use decriminalised administratively; production/trafficking remain criminal. No licensed therapy supply for classical psychedelics.",
        "details": "Decrim ≠ legal commercial therapy. Pathway remains None for medical programmes.",
        "sources": [{"title": "SICAD Portugal", "url": "https://www.sicad.pt"}],
        "status_override": LS.DECRIMINALIZED,  # personal possession posture — still no supply
        "pathway": AP.NONE,
        "vol": VL.STABLE,
    },
    "jur-ch": {
        "authority": "Swissmedic / BAG",
        "basis": "Narcotics Act — substances controlled; BAG exceptional authorisations exist case-by-case for some psychedelics.",
        "details": "Default remains prohibited for open practice; exceptional permits are separate AccessCells where seeded.",
        "sources": [{"title": "Swiss BAG", "url": "https://www.bag.admin.ch"}],
    },
    "jur-au": {
        "authority": "TGA",
        "basis": "Poisons Standard — psilocybin/MDMA rescheduled for authorised psychiatrist use (2023) for specific indications; other psychedelics remain tightly controlled.",
        "details": "Do not treat all psychedelics as available — only seeded TGA pathways apply. Others stay prohibited.",
        "sources": [{"title": "TGA psilocybin/MDMA", "url": "https://www.tga.gov.au"}],
    },
    "jur-jp": {
        "authority": "MHLW",
        "basis": "Stimulants Control Act / Narcotics and Psychotropics Control Act — extremely strict; classical psychedelics prohibited.",
        "details": "No recreational or wellness pathway; research tightly controlled.",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-kr": {
        "authority": "MFDS",
        "basis": "Narcotics Control Act — classical psychedelics prohibited.",
        "details": "Strict enforcement culture; no therapy tourism pathway.",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-sg": {
        "authority": "HSA / Misuse of Drugs Act",
        "basis": "Class A controlled drugs with severe trafficking penalties — classical psychedelics and cannabis prohibited.",
        "details": "Among the strictest regimes globally; no medical cannabis or psychedelic therapy programme.",
        "sources": [{"title": "Singapore CNB", "url": "https://www.cnb.gov.sg"}],
        "confidence": CF.HIGH,
    },
    "jur-in": {
        "authority": "Narcotic Drugs and Psychotropic Substances Act, 1985",
        "basis": "NDPS schedules cover major psychedelics; no national therapy programme.",
        "details": "Research possible with permits; commercial therapy not authorised.",
        "sources": [],
    },
    "jur-il": {
        "authority": "Ministry of Health",
        "basis": "Dangerous Drugs Ordinance — classical psychedelics controlled; medical cannabis is separate licensed system.",
        "details": "Psychedelic therapy not generally authorised outside research.",
        "sources": [],
    },
    "jur-uae": {
        "authority": "UAE Ministry of Health / narcotics law",
        "basis": "Zero-tolerance narcotics enforcement — classical psychedelics prohibited.",
        "details": "Severe criminal penalties; no therapy pathway.",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-tu": {
        "authority": "TİTCK / Turkish narcotics law",
        "basis": "Controlled narcotics — classical psychedelics prohibited outside research.",
        "details": "No regulated therapy programme.",
        "sources": [],
    },
    "jur-th": {
        "authority": "Thai FDA / Narcotics Act (reforms ongoing)",
        "basis": "Most classical psychedelics remain controlled; cannabis policy has been in flux separately.",
        "details": "Do not assume wellness tourism covers MDMA/psilocybin mushrooms legally.",
        "sources": [],
        "vol": VL.ACTIVE_FLUX,
    },
    "jur-ph": {
        "authority": "FDA Philippines / Dangerous Drugs Act",
        "basis": "Dangerous drugs schedules — classical psychedelics prohibited.",
        "details": "Strict penalties; no therapy programme.",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-mx": {
        "authority": "COFEPRIS / Ley General de Salud",
        "basis": "Psychotropics schedules — classical psychedelics generally prohibited; enforcement and gray tourism vary by substance/region.",
        "details": "Ibogaine/retreat markets operate in gray zones but do not equal national authorisation for all psychedelics.",
        "sources": [],
        "vol": VL.ACTIVE_FLUX,
        "confidence": CF.LOW,
    },
    "jur-br": {
        "authority": "ANVISA",
        "basis": "Controlled substances list — many psychedelics prohibited; ayahuasca religious use is a specific constitutional/religious exception.",
        "details": "Religious ayahuasca ≠ general psilocybin/MDMA therapy legalisation.",
        "sources": [],
    },
    "jur-ar": {
        "authority": "ANMAT / narcotics law",
        "basis": "Controlled psychotropics — classical psychedelics prohibited outside research.",
        "details": "No national therapy programme.",
        "sources": [],
    },
    "jur-cl": {
        "authority": "ISP / Chilean narcotics framework",
        "basis": "Controlled substances — classical psychedelics generally prohibited.",
        "details": "Limited reform debates; default remains prohibition for therapy businesses.",
        "sources": [],
        "vol": VL.ACTIVE_FLUX,
    },
    "jur-cr": {
        "authority": "Ministry of Health Costa Rica",
        "basis": "Controlled narcotics — classical psychedelics not authorised as medicines.",
        "details": "Retreat tourism may occur in gray zones without creating a regulated medical pathway.",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-za": {
        "authority": "SAHPRA",
        "basis": "Medicines and controlled substances frameworks — classical psychedelics not authorised for general therapy.",
        "details": "Research possible; no national service-centre model.",
        "sources": [],
    },
    "jur-ca": {
        "authority": "Health Canada / CDSA",
        "basis": "Controlled Drugs and Substances Act schedules classical psychedelics; SAP/Section 56 are exceptional pathways.",
        "details": "Default is prohibited for open practice; seeded SAP/Section 56 cells are exceptions.",
        "sources": [{"title": "CDSA", "url": "https://laws-lois.justice.gc.ca/eng/acts/c-38.8/"}],
    },
    "jur-hn-prospera": {
        "authority": "Próspera ZEDE / contested Honduran framework",
        "basis": "Special zone rules may diverge; national Honduran narcotics law still relevant outside ZEDE perimeter.",
        "details": "Do not assume all psychedelics are free — only explicitly structured programmes apply. Legal uncertainty high.",
        "sources": [],
        "vol": VL.ACTIVE_FLUX,
        "confidence": CF.LOW,
    },
    # US states without specific seed rows inherit federal prohibition language
    "jur-us-ca": {
        "authority": "DEA Schedule I (federal) + CA state law",
        "basis": "Federal Schedule I; CA has not enacted Oregon-style regulated psilocybin therapy statewide.",
        "details": "City decrim ordinances may reduce local enforcement priority but do not create licensed therapy supply.",
        "sources": [],
        "vol": VL.ACTIVE_FLUX,
        "confidence": CF.MODERATE,
    },
    "jur-us-tx": {
        "authority": "DEA Schedule I + Texas controlled substances law",
        "basis": "Federal and state prohibition for classical psychedelics.",
        "details": "No regulated therapy programme; Right to Try does not open Schedule I retail therapy.",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-fl": {
        "authority": "DEA Schedule I + Florida law",
        "basis": "Classical psychedelics prohibited.",
        "details": "No statewide regulated psilocybin/MDMA therapy programme.",
        "sources": [],
        "confidence": CF.HIGH,
    },
}

# Therapies that should NOT get blanket prohibition from this matrix
SKIP_PROCS_FOR_JUR = {
    # Australia: psilo TRD + MDMA PTSD already have TGA pathways
    ("proc-psilocybin-trd", "jur-au"),
    ("proc-psilocybin-eol", "jur-au"),
    ("proc-mdma-ptsd", "jur-au"),
    # Oregon / Colorado special
    ("proc-psilocybin-trd", "jur-us-or"),
    ("proc-psilocybin-eol", "jur-us-or"),
    ("proc-psilocybin-microdose", "jur-us-or"),
    ("proc-psilocybin-trd", "jur-us-co"),
    ("proc-dmt-depression", "jur-us-co"),
    ("proc-psilocybin-microdose", "jur-us-co"),
    # Jamaica mushrooms
    ("proc-psilocybin-trd", "jur-jm"),
    ("proc-psilocybin-eol", "jur-jm"),
    ("proc-psilocybin-microdose", "jur-jm"),
    # NL truffles microdose / possible
    ("proc-psilocybin-microdose", "jur-nl"),
    # CH BAG LSD
    ("proc-lsd-anxiety", "jur-ch"),
    # CA SAP
    ("proc-psilocybin-trd", "jur-ca"),
    # MX ibogaine gray already seeded
    ("proc-ibogaine-addiction", "jur-mx"),
    # BR ayahuasca religious already seeded
    ("proc-ayahuasca", "jur-br"),
    # MX mescaline/ayahuasca gray already
    ("proc-mescaline-therapy", "jur-mx"),
    ("proc-ayahuasca", "jur-mx"),
    ("proc-ayahuasca", "jur-cr"),
    ("proc-ayahuasca", "jur-cl"),
    # CO 5meo decrim cell may exist
    ("proc-5meo-dmt", "jur-us-co"),
    ("proc-5meo-dmt", "jur-mx"),
}


# Medical cannabis: only fill where clearly prohibited and no access row
CANNABIS_PROHIBITED_JURS = {
    "jur-sg": "Misuse of Drugs Act — cannabis strictly prohibited; severe penalties.",
    "jur-jp": "Cannabis Control Act — possession/use criminalised; medical pathway extremely limited/absent for flower.",
    "jur-kr": "Narcotics Control Act — cannabis prohibited outside narrow research.",
    "jur-uae": "Zero-tolerance narcotics law — cannabis prohibited.",
    "jur-ph": "Dangerous Drugs Act — cannabis prohibited (enforcement historically severe).",
    "jur-in": "NDPS Act — cannabis resin/ganja controlled; no national medical flower programme comparable to CA/DE.",
}

# MAID: prohibited where no national framework (explicit)
MAID_PROHIBITED_JURS = {
    "jur-us-federal": "No federal MAID statute; federal controlled substances / assisted suicide constraints. State Death with Dignity laws are subnational exceptions not seeded for every state.",
    "jur-uk": "Assisted dying not generally lawful in England/Wales (ongoing legislative debate — volatility high).",
    "jur-au": "Federal complexity; voluntary assisted dying is state/territory-based — not a single national open pathway for non-residents.",
    "jur-de": "Assisted suicide legal nuances post-BVerfG but organised MAID clinic model differs from NL/BE; no Dutch-style euthanasia statute — treat open commercial MAID as unavailable.",
    "jur-fr": "No full MAID legalisation as of review (debates ongoing).",
    "jur-po": "Prohibited.",
    "jur-se": "No MAID legalisation.",
    "jur-jp": "Prohibited.",
    "jur-kr": "Prohibited.",
    "jur-sg": "Prohibited.",
    "jur-il": "No general MAID framework.",
    "jur-mx": "No national MAID framework.",
    "jur-br": "Prohibited nationally.",
    "jur-in": "Passive withdrawal frameworks differ; active MAID not generally lawful.",
    "jur-th": "Prohibited.",
    "jur-uae": "Prohibited.",
    "jur-tu": "Prohibited.",
    "jur-ph": "Prohibited.",
    "jur-za": "No national MAID statute (constitutional litigation history — still not open access).",
    "jur-ar": "No national MAID framework.",
    "jur-cl": "No national MAID framework.",
    "jur-cr": "Prohibited.",
    "jur-jm": "Prohibited.",
}


# ── Jurisdiction regulation profiles (structured) ───────────────────────────

JURISDICTION_REGULATION = {
    "jur-us-federal": {
        "drug_regulator": "FDA",
        "health_authority": "HHS / DEA (controlled substances)",
        "controlled_substance_framework": "Controlled Substances Act Schedule I–V",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Prohibited",
        "assisted_dying_default": "Limited_Subnational",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Controlled Substances Act", "citation": "21 U.S.C. § 801 et seq.", "url": "https://www.dea.gov/drug-information/csa"},
            {"name": "Federal Right to Try Act", "citation": "21 U.S.C. § 360bbb-0a"},
            {"name": "FD&C Act", "citation": "21 U.S.C. § 301 et seq."},
        ],
        "pending_legislation": [
            {"title": "State psychedelic programmes (OR/CO model diffusion)", "status": "Active_state_level", "affects": ["Psychedelics"], "notes": "Federal Schedule I unchanged."},
        ],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-us-or": {
        "drug_regulator": "FDA (federal) + OHA Psilocybin Services",
        "health_authority": "Oregon Health Authority",
        "controlled_substance_framework": "Federal CSA + state Measure 109 programme",
        "un_conventions_party": True,
        "psychedelic_default": "Regulated_Therapy_Program",
        "cannabis_default": "Medical_And_Adult_Use",
        "assisted_dying_default": "Assisted_Suicide_Only",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Oregon Psilocybin Services Act (Measure 109)", "citation": "ORS 475A"},
            {"name": "Oregon Death with Dignity Act", "citation": "ORS 127.800"},
        ],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-us-co": {
        "drug_regulator": "FDA + DORA Natural Medicine Division",
        "health_authority": "Colorado Department of Regulatory Agencies",
        "controlled_substance_framework": "Federal CSA + Prop 122 Natural Medicine Health Act",
        "un_conventions_party": True,
        "psychedelic_default": "Decriminalized_No_Supply",
        "cannabis_default": "Medical_And_Adult_Use",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Natural Medicine Health Act (Prop 122)", "citation": "Colorado Constitution / statute"},
        ],
        "pending_legislation": [
            {"title": "Healing center rulemaking / rollout", "status": "Ongoing", "affects": ["proc-psilocybin-trd"], "notes": "Regulated centers phased; personal use decrim already active."},
        ],
        "last_reviewed": "2026-07-01",
        "confidence": "Moderate",
    },
    "jur-uk": {
        "drug_regulator": "MHRA",
        "health_authority": "Home Office (Misuse of Drugs) + DHSC / NICE",
        "controlled_substance_framework": "Misuse of Drugs Act 1971 Class A/B/C",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Pending_Legislation",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Restrictive",
        "key_statutes": [
            {"name": "Misuse of Drugs Act 1971", "url": "https://www.legislation.gov.uk/ukpga/1971/38"},
            {"name": "Human Medicines Regulations", "citation": "2012"},
        ],
        "pending_legislation": [
            {"title": "Assisted dying bills (Westminster / Scotland tracks)", "status": "Parliamentary", "affects": ["proc-maid"]},
        ],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-de": {
        "drug_regulator": "BfArM",
        "health_authority": "BMG",
        "controlled_substance_framework": "BtMG (Narcotics Act)",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_And_Adult_Use",
        "assisted_dying_default": "Assisted_Suicide_Only",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Betäubungsmittelgesetz (BtMG)"},
            {"name": "Cannabis Act (CanG) 2024 reforms", "notes": "Adult-use limited + medical prescribing changes"},
        ],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-au": {
        "drug_regulator": "TGA",
        "health_authority": "Department of Health and Aged Care",
        "controlled_substance_framework": "Poisons Standard (SUSMP) scheduling",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Limited_Subnational",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Therapeutic Goods Act 1989"},
            {"name": "TGA psilocybin/MDMA rescheduling 2023", "notes": "Authorised psychiatrist pathway for TRD/PTSD"},
        ],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-ca": {
        "drug_regulator": "Health Canada",
        "health_authority": "Health Canada + provinces",
        "controlled_substance_framework": "CDSA schedules",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_And_Adult_Use",
        "assisted_dying_default": "Euthanasia_And_Assisted_Suicide",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Controlled Drugs and Substances Act"},
            {"name": "Cannabis Act 2018"},
            {"name": "Criminal Code MAID provisions (Bill C-14 / C-7)"},
        ],
        "pending_legislation": [
            {"title": "MAID mental illness sole condition track", "status": "Delayed/tracked to later year", "affects": ["proc-maid"]},
        ],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-ch": {
        "drug_regulator": "Swissmedic",
        "health_authority": "BAG (FOPH)",
        "controlled_substance_framework": "Narcotics Act (BetmG)",
        "un_conventions_party": True,
        "psychedelic_default": "Expanded_Access",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Assisted_Suicide_Only",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Swiss Criminal Code Art. 115 (assisted suicide)"},
            {"name": "Narcotics Act — exceptional authorisations via BAG"},
        ],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-nl": {
        "drug_regulator": "MEB / IGJ",
        "health_authority": "VWS",
        "controlled_substance_framework": "Opium Act (List I/II) — truffle exception for sclerotia",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Decriminalized",
        "assisted_dying_default": "Euthanasia_And_Assisted_Suicide",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Dutch Termination of Life on Request and Assisted Suicide Act"},
            {"name": "Opium Act — smart shop sclerotia policy"},
        ],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-be": {
        "drug_regulator": "FAMHP",
        "health_authority": "FPS Health",
        "controlled_substance_framework": "Narcotics legislation",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Euthanasia_And_Assisted_Suicide",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [{"name": "Belgian Euthanasia Act 2002"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-es": {
        "drug_regulator": "AEMPS",
        "health_authority": "Ministry of Health",
        "controlled_substance_framework": "Spanish narcotics schedules",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Euthanasia_And_Assisted_Suicide",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [{"name": "Organic Law 3/2021 (euthanasia)"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-jp": {
        "drug_regulator": "PMDA / MHLW",
        "health_authority": "MHLW",
        "controlled_substance_framework": "Narcotics & Stimulants Control Acts — very strict",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Prohibited",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Restrictive",
        "key_statutes": [{"name": "Narcotics and Psychotropics Control Act"}, {"name": "Cannabis Control Act"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-sg": {
        "drug_regulator": "HSA",
        "health_authority": "MOH / CNB",
        "controlled_substance_framework": "Misuse of Drugs Act — severe penalties",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Prohibited",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": False,
        "compounding_environment": "Restrictive",
        "key_statutes": [{"name": "Misuse of Drugs Act"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-mx": {
        "drug_regulator": "COFEPRIS",
        "health_authority": "Secretaría de Salud",
        "controlled_substance_framework": "Ley General de Salud psychotropics schedules",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Highly_Variable",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": False,
        "compounding_environment": "Permissive",
        "key_statutes": [{"name": "Ley General de Salud"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "Moderate",
    },
    "jur-br": {
        "drug_regulator": "ANVISA",
        "health_authority": "Ministry of Health",
        "controlled_substance_framework": "Portaria SVS/MS controlled lists",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [
            {"name": "Religious ayahuasca recognition (STF / CONAD framework)", "notes": "Exception for sacramental use"},
        ],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "Moderate",
    },
    "jur-jm": {
        "drug_regulator": "Ministry of Health",
        "health_authority": "Ministry of Health",
        "controlled_substance_framework": "Dangerous Drugs Act — psilocybin mushrooms historically unscheduled",
        "un_conventions_party": True,
        "psychedelic_default": "Unregulated_Permitted",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": False,
        "compounding_environment": "Unknown",
        "key_statutes": [{"name": "Dangerous Drugs Act (psilocybin omission)"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "Moderate",
    },
    "jur-pt": {
        "drug_regulator": "INFARMED",
        "health_authority": "SICAD / Ministry of Health",
        "controlled_substance_framework": "Decriminalisation 2001 + trafficking still criminal",
        "un_conventions_party": True,
        "psychedelic_default": "Decriminalized_No_Supply",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Pending_Legislation",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [{"name": "Law 30/2000 (decriminalisation)"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-il": {
        "drug_regulator": "Ministry of Health",
        "health_authority": "MOH",
        "controlled_substance_framework": "Dangerous Drugs Ordinance",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Moderate",
        "key_statutes": [{"name": "Medical cannabis programme regulations"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-fr": {
        "drug_regulator": "ANSM",
        "health_authority": "Ministry of Health",
        "controlled_substance_framework": "Stupéfiants schedules",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Medical_Only",
        "assisted_dying_default": "Pending_Legislation",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Restrictive",
        "key_statutes": [{"name": "Code de la santé publique — stupéfiants"}],
        "pending_legislation": [
            {"title": "End-of-life / aide à mourir legislative debates", "status": "Active", "affects": ["proc-maid"]},
        ],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-kr": {
        "drug_regulator": "MFDS",
        "health_authority": "MOHW",
        "controlled_substance_framework": "Narcotics Control Act",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Prohibited",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Restrictive",
        "key_statutes": [{"name": "Narcotics Control Act"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "High",
    },
    "jur-th": {
        "drug_regulator": "Thai FDA",
        "health_authority": "MOPH",
        "controlled_substance_framework": "Narcotics Act (cannabis reforms in flux)",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Highly_Variable",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": False,
        "compounding_environment": "Permissive",
        "key_statutes": [{"name": "Narcotics Act", "notes": "Cannabis policy oscillated 2022–2026"}],
        "pending_legislation": [
            {"title": "Cannabis re-regulation proposals", "status": "Flux", "affects": ["proc-medical-cannabis"]},
        ],
        "last_reviewed": "2026-07-01",
        "confidence": "Moderate",
    },
    "jur-in": {
        "drug_regulator": "CDSCO",
        "health_authority": "Ministry of Health and Family Welfare",
        "controlled_substance_framework": "NDPS Act 1985",
        "un_conventions_party": True,
        "psychedelic_default": "Prohibited",
        "cannabis_default": "Prohibited",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Permissive",
        "key_statutes": [{"name": "Narcotic Drugs and Psychotropic Substances Act, 1985"}],
        "pending_legislation": [],
        "last_reviewed": "2026-07-01",
        "confidence": "Moderate",
    },
    "jur-hn-prospera": {
        "drug_regulator": "Próspera ZEDE health rules (contested)",
        "health_authority": "ZEDE administration / Honduran interface",
        "controlled_substance_framework": "Special zone + national law tension",
        "un_conventions_party": True,
        "psychedelic_default": "Highly_Variable",
        "cannabis_default": "Highly_Variable",
        "assisted_dying_default": "Prohibited",
        "right_to_try_or_expanded_access": True,
        "compounding_environment": "Permissive",
        "key_statutes": [{"name": "ZEDE organic law / reforms", "notes": "Constitutional challenges — active flux"}],
        "pending_legislation": [
            {"title": "ZEDE legal status disputes", "status": "Contested", "affects": ["Gene_Therapy", "Peptide", "Stem_Cell"]},
        ],
        "last_reviewed": "2026-07-01",
        "confidence": "Low",
    },
}


# Therapy-level controlled substance class / global posture
THERAPY_CONTROL_META = {
    "proc-psilocybin-trd": ("Schedule_I", "Widely_Prohibited"),
    "proc-psilocybin-eol": ("Schedule_I", "Widely_Prohibited"),
    "proc-psilocybin-microdose": ("Schedule_I", "Widely_Prohibited"),
    "proc-mdma-ptsd": ("Schedule_I", "Widely_Prohibited"),
    "proc-dmt-depression": ("Schedule_I", "Widely_Prohibited"),
    "proc-lsd-anxiety": ("Schedule_I", "Widely_Prohibited"),
    "proc-mescaline-therapy": ("Schedule_I", "Widely_Prohibited"),
    "proc-ayahuasca": ("Schedule_I", "Widely_Prohibited"),
    "proc-5meo-dmt": ("Schedule_I", "Widely_Prohibited"),
    "proc-ibogaine-addiction": ("Schedule_I", "Widely_Prohibited"),
    "proc-ketamine-depression": ("Schedule_III", "Widely_OffLabel"),
    "proc-ketamine-assisted-psychotherapy": ("Schedule_III", "Widely_OffLabel"),
    "proc-medical-cannabis": ("Varies", "Highly_Variable"),
    "proc-maid": ("Unscheduled", "Highly_Variable"),
    "proc-repro-surrogacy": ("Unscheduled", "Highly_Variable"),
    "proc-mito-replacement": ("Unscheduled", "Widely_Prohibited"),
    "proc-ozone-therapy": ("Unscheduled", "Highly_Variable"),
    "proc-peptide-bpc": ("Unscheduled", "Widely_Prohibited"),
    "proc-peptide-cjc-ipa": ("Unscheduled", "Widely_Prohibited"),
}


# ── Additional therapies often banned (not only classical psychedelics) ─────

# All forms of surrogacy banned (commercial + altruistic)
SURROGACY_ALL_BANNED = {
    "jur-fr": {
        "basis": "French Civil Code Art. 16-7 — any surrogacy agreement is void; arrangement is unlawful.",
        "details": "Both commercial and altruistic surrogacy prohibited. Contracts unenforceable; criminal exposure for intermediaries.",
        "authority": "French Civil Code / bioethics framework",
        "sources": [{"title": "Surrogacy laws by country (overview)", "url": "https://en.wikipedia.org/wiki/Surrogacy_laws_by_country"}],
    },
    "jur-de": {
        "basis": "Embryo Protection Act (Embryonenschutzgesetz) §1 — surrogacy arrangements banned for medical professionals; birth mother is legal mother.",
        "details": "All surrogacy (commercial and altruistic) illegal to arrange/perform in Germany.",
        "authority": "ESchG / German family law",
        "sources": [{"title": "EPRS Surrogacy in the EU", "url": "https://www.europarl.europa.eu/RegData/etudes/BRIE/2025/769508/EPRS_BRI(2025)769508_EN.pdf"}],
    },
    "jur-es": {
        "basis": "Law 14/2006 (and prior Law 35/1988 Art. 10) — surrogacy contracts void; birth mother is mother.",
        "details": "All surrogacy prohibited domestically; cross-border arrangements create parentage recognition issues.",
        "authority": "Spanish ART law",
        "sources": [{"title": "EPRS Surrogacy in the EU", "url": "https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2025)769508"}],
    },
    "jur-se": {
        "basis": "Surrogacy not permitted within Swedish healthcare; arrangements not legally facilitated.",
        "details": "Healthcare system may not provide surrogacy; legal parentage frameworks do not support domestic surrogacy programmes.",
        "authority": "Swedish healthcare / family law practice",
        "sources": [{"title": "Surrogacy laws by country", "url": "https://en.wikipedia.org/wiki/Surrogacy_laws_by_country"}],
    },
    "jur-ch": {
        "basis": "Swiss reproductive medicine law — surrogacy prohibited.",
        "details": "All surrogacy banned; Swiss residents sometimes pursue arrangements abroad with legal complexity.",
        "authority": "Swiss Reproductive Medicine Act",
        "sources": [{"title": "Surrogacy laws by country", "url": "https://en.wikipedia.org/wiki/Surrogacy_laws_by_country"}],
    },
    "jur-po": {
        "basis": "Polish law does not permit surrogacy arrangements; contracts treated as void.",
        "details": "No lawful domestic surrogacy pathway.",
        "authority": "Polish family / medical law",
        "sources": [{"title": "Surrogacy laws by country", "url": "https://en.wikipedia.org/wiki/Surrogacy_laws_by_country"}],
    },
    "jur-pt": {
        "basis": "Portuguese law has restricted/banned surrogacy pathways (reforms historically unstable).",
        "details": "Treat domestic surrogacy programmes as unavailable/prohibited pending clear statutory programme.",
        "authority": "Portuguese ART law",
        "sources": [{"title": "Reuters surrogacy legality overview", "url": "https://www.reuters.com/world/which-countries-allow-commercial-surrogacy-2023-04-05/"}],
        "vol": VL.ACTIVE_FLUX,
        "confidence": CF.MODERATE,
    },
    "jur-jp": {
        "basis": "Japanese professional guidelines and legal practice effectively bar surrogacy arrangements.",
        "details": "No recognised domestic surrogacy programme; parentage and medical ethics barriers.",
        "authority": "Japan Society of Obstetrics and Gynecology / family law practice",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-sg": {
        "basis": "Singapore prohibits surrogacy arrangements.",
        "details": "No lawful surrogacy pathway for commissioning parents domestically.",
        "authority": "Singapore MOH / family law",
        "sources": [],
        "confidence": CF.HIGH,
    },
}

# Mitochondrial replacement / three-person IVF — banned or not authorised outside UK-class programmes
MRT_PROHIBITED = {
    "jur-us-federal": {
        "basis": "US appropriations riders bar FDA from accepting applications involving heritable genetic modification of embryos — MRT effectively prohibited clinically.",
        "details": "No FDA pathway for clinical MRT; UK is the primary regulated destination.",
        "authority": "FDA / Congressional appropriations language",
        "sources": [{"title": "MRT US ban discussion", "url": "https://www.scientificamerican.com/article/congress-revives-ban-on-altering-the-dna-of-human-embryos-used-for-pregnancies/"}],
        "confidence": CF.HIGH,
    },
    "jur-de": {
        "basis": "Embryo Protection Act restricts embryo manipulation incompatible with MRT clinical practice.",
        "details": "MRT not an available clinical service.",
        "authority": "ESchG",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-fr": {
        "basis": "French bioethics law — germline/heritable embryo modification pathways not authorised for MRT clinical use.",
        "details": "No clinical MRT programme.",
        "authority": "Bioethics statutes / ANSM",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-ca": {
        "basis": "Assisted Human Reproduction Act prohibits altering the genome of a cell of a human being or in vitro embryo such that the alteration is capable of being transmitted to descendants — interpreted to block MRT clinical use.",
        "details": "MRT not available as clinical care in Canada.",
        "authority": "AHRA",
        "sources": [{"title": "Assisted Human Reproduction Act", "url": "https://laws-lois.justice.gc.ca/eng/acts/a-13.4/"}],
        "confidence": CF.HIGH,
    },
    "jur-jp": {
        "basis": "Japanese guidelines/law restrict heritable genome interventions; MRT not authorised as standard care.",
        "details": "No open clinical MRT pathway.",
        "authority": "MHLW / professional guidelines",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-sg": {
        "basis": "Strict reproductive genetics rules — MRT not authorised.",
        "details": "No clinical MRT programme.",
        "authority": "MOH Singapore",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-kr": {
        "basis": "Bioethics and Safety Act framework restricts heritable genetic modification of embryos.",
        "details": "MRT not available clinically.",
        "authority": "MFDS / bioethics law",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-es": {
        "basis": "Spanish ART law does not authorise mitochondrial donation programmes comparable to UK HFEA.",
        "details": "No regulated MRT clinical service.",
        "authority": "Spanish ART law / AEMPS",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-nl": {
        "basis": "Dutch embryo legislation does not provide a UK-style licensed MRT clinical pathway for patients.",
        "details": "Research ≠ clinical service for patients seeking MRT.",
        "authority": "Embryo Act / IGJ",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-be": {
        "basis": "Belgian embryo research rules; no routine MRT clinical authorisation for reproduction.",
        "details": "No patient MRT service pathway seeded as available.",
        "authority": "Belgian embryo law",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-se": {
        "basis": "Swedish genetic integrity / embryo rules — MRT not offered as care.",
        "details": "No clinical MRT programme.",
        "authority": "Swedish National Council on Medical Ethics framework",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-ch": {
        "basis": "Swiss reproductive medicine law — restrictive on embryo manipulation for heritable change.",
        "details": "MRT not a lawful clinical offering.",
        "authority": "Swiss Reproductive Medicine Act",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-mx": {
        "basis": "No national regulated MRT pathway; practice would fall outside authorised ART standards.",
        "details": "Not a recognised regulated service — treat as unavailable/prohibited for patient planning.",
        "authority": "COFEPRIS / ART practice",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-br": {
        "basis": "ANVISA/CFM frameworks do not authorise MRT as standard ART.",
        "details": "No regulated MRT programme.",
        "authority": "ANVISA / CFM",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-in": {
        "basis": "ART/surrogacy regulation environment does not establish licensed MRT services.",
        "details": "No recognised national MRT clinical pathway.",
        "authority": "ART regulatory framework",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-il": {
        "basis": "Israeli ART regulation — MRT not an established licensed service.",
        "details": "No routine MRT programme.",
        "authority": "Ministry of Health",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-uae": {
        "basis": "UAE reproductive medicine rules — MRT not authorised.",
        "details": "No clinical MRT pathway.",
        "authority": "MOHAP / DHA frameworks",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-tu": {
        "basis": "Turkish ART regulation — MRT not authorised clinical service.",
        "details": "No MRT programme.",
        "authority": "TİTCK / MOH",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-po": {
        "basis": "Polish embryo protection culture/law — MRT not available.",
        "details": "No clinical MRT pathway.",
        "authority": "Polish medical law",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-pt": {
        "basis": "Portuguese ART law — no licensed MRT service.",
        "details": "No clinical MRT pathway.",
        "authority": "Portuguese ART regulation",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-za": {
        "basis": "No licensed MRT clinical pathway under SAHPRA/ART practice.",
        "details": "Unavailable as regulated care.",
        "authority": "SAHPRA",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-th": {
        "basis": "Thai ART regulation does not establish MRT clinical service.",
        "details": "Unavailable as regulated care.",
        "authority": "Thai FDA / MOPH",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-ph": {
        "basis": "No MRT clinical authorisation.",
        "details": "Unavailable.",
        "authority": "FDA Philippines",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-ar": {
        "basis": "No national MRT programme.",
        "details": "Unavailable as regulated care.",
        "authority": "ANMAT",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-cl": {
        "basis": "No national MRT programme.",
        "details": "Unavailable as regulated care.",
        "authority": "ISP Chile",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-cr": {
        "basis": "No MRT programme.",
        "details": "Unavailable.",
        "authority": "Ministry of Health",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-jm": {
        "basis": "No MRT programme.",
        "details": "Unavailable.",
        "authority": "Ministry of Health",
        "sources": [],
        "confidence": CF.LOW,
    },
    "jur-us-or": {
        "basis": "Federal appropriations bar controls US clinical MRT regardless of state.",
        "details": "State cannot authorise clinical MRT while federal rider blocks FDA.",
        "authority": "FDA / federal law",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-co": {
        "basis": "Federal appropriations bar controls US clinical MRT regardless of state.",
        "details": "No state pathway around federal ban.",
        "authority": "FDA / federal law",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-ca": {
        "basis": "Federal appropriations bar controls US clinical MRT.",
        "details": "No California clinical MRT pathway.",
        "authority": "FDA / federal law",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-tx": {
        "basis": "Federal appropriations bar controls US clinical MRT.",
        "details": "No Texas clinical MRT pathway.",
        "authority": "FDA / federal law",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-fl": {
        "basis": "Federal appropriations bar controls US clinical MRT.",
        "details": "No Florida clinical MRT pathway.",
        "authority": "FDA / federal law",
        "sources": [],
        "confidence": CF.HIGH,
    },
}

# Medical ozone — FDA explicitly hostile; several systems do not authorise as medicine
OZONE_PROHIBITED = {
    "jur-us-federal": {
        "basis": "FDA position: ozone is a toxic gas with no known useful medical application in specific therapeutic claims historically enforced; medical ozone generators marketed for disease treatment face enforcement.",
        "details": "Not a lawful FDA-approved medical therapy business for disease treatment claims.",
        "authority": "FDA",
        "sources": [{"title": "FDA ozone generators consumer update", "url": "https://www.fda.gov/consumers/consumer-updates"}],
        "confidence": CF.HIGH,
    },
    "jur-us-or": {
        "basis": "Federal FDA posture applies; Oregon does not create a lawful medical ozone disease-treatment pathway.",
        "details": "Same federal constraints.",
        "authority": "FDA",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-co": {
        "basis": "Federal FDA posture applies.",
        "details": "No state medical ozone authorisation for disease claims.",
        "authority": "FDA",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-ca": {
        "basis": "Federal FDA posture applies.",
        "details": "No lawful disease-treatment ozone pathway.",
        "authority": "FDA",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-tx": {
        "basis": "Federal FDA posture applies.",
        "details": "No lawful disease-treatment ozone pathway.",
        "authority": "FDA",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-us-fl": {
        "basis": "Federal FDA posture applies.",
        "details": "No lawful disease-treatment ozone pathway.",
        "authority": "FDA",
        "sources": [],
        "confidence": CF.HIGH,
    },
    "jur-uk": {
        "basis": "Ozone not an MHRA-authorised medicine for general therapeutic marketing; disease claims require authorisation.",
        "details": "Cannot lawfully market as an approved medical treatment without authorisation.",
        "authority": "MHRA",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-sg": {
        "basis": "HSA does not authorise ozone therapy as standard medicine; disease claims restricted.",
        "details": "Not a lawful approved therapy programme.",
        "authority": "HSA",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-jp": {
        "basis": "Not an authorised standard medical therapy under PMDA for broad indications.",
        "details": "No general medical ozone therapy pathway.",
        "authority": "PMDA/MHLW",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-au": {
        "basis": "Not TGA-approved as a registered medicine for general ozone therapy claims.",
        "details": "Marketing as approved treatment without registration is unlawful.",
        "authority": "TGA",
        "sources": [],
        "confidence": CF.MODERATE,
    },
    "jur-ca": {
        "basis": "Not authorised as a general Health Canada approved therapy for broad disease claims.",
        "details": "Unapproved therapeutic marketing restricted.",
        "authority": "Health Canada",
        "sources": [],
        "confidence": CF.MODERATE,
    },
}

# Unapproved peptide injectables — jurisdictions with clear "do not compound / not authorised medicine"
PEPTIDE_PROHIBITED = {
    "proc-peptide-bpc": {
        "jur-de": {
            "basis": "Not an authorised medicinal product; compounding/import for human therapeutic use not a standard lawful pathway.",
            "details": "BPC-157 is not an approved German medicine; cannot be marketed as such.",
            "authority": "BfArM / AMG",
            "confidence": CF.MODERATE,
        },
        "jur-fr": {
            "basis": "Not ANSM-authorised medicinal product for general therapeutic use.",
            "details": "No lawful approved BPC-157 medicine pathway.",
            "authority": "ANSM",
            "confidence": CF.MODERATE,
        },
        "jur-jp": {
            "basis": "Not PMDA-approved medicine; research chemical injection not lawful medical practice.",
            "details": "No approved BPC-157 product.",
            "authority": "PMDA",
            "confidence": CF.HIGH,
        },
        "jur-sg": {
            "basis": "Not HSA-approved therapeutic product.",
            "details": "Cannot lawfully market as medicine.",
            "authority": "HSA",
            "confidence": CF.HIGH,
        },
        "jur-ca": {
            "basis": "Not a Health Canada approved drug; compounding/import constraints apply.",
            "details": "No approved BPC-157 DIN product pathway for routine care.",
            "authority": "Health Canada",
            "confidence": CF.MODERATE,
        },
        "jur-ch": {
            "basis": "Not Swissmedic-authorised medicine for general use.",
            "details": "No standard authorised product.",
            "authority": "Swissmedic",
            "confidence": CF.MODERATE,
        },
        "jur-nl": {
            "basis": "Not an authorised medicinal product for routine prescribing.",
            "details": "No standard BPC-157 medicine authorisation.",
            "authority": "MEB/IGJ",
            "confidence": CF.MODERATE,
        },
        "jur-se": {
            "basis": "Not an authorised medicine.",
            "details": "No approved product pathway.",
            "authority": "Läkemedelsverket",
            "confidence": CF.MODERATE,
        },
        "jur-be": {
            "basis": "Not an authorised medicine.",
            "details": "No approved product pathway.",
            "authority": "FAMHP",
            "confidence": CF.MODERATE,
        },
        "jur-es": {
            "basis": "Not AEMPS-authorised medicine.",
            "details": "No approved product pathway.",
            "authority": "AEMPS",
            "confidence": CF.MODERATE,
        },
        "jur-il": {
            "basis": "Not an authorised Israeli medicine for routine use.",
            "details": "No approved product pathway.",
            "authority": "Ministry of Health",
            "confidence": CF.LOW,
        },
        "jur-kr": {
            "basis": "Not MFDS-approved medicine.",
            "details": "No approved product pathway.",
            "authority": "MFDS",
            "confidence": CF.MODERATE,
        },
        "jur-uae": {
            "basis": "Not authorised therapeutic product for marketing.",
            "details": "No approved pathway.",
            "authority": "MOHAP",
            "confidence": CF.MODERATE,
        },
    },
    "proc-peptide-cjc-ipa": {
        "jur-us-federal": {
            "basis": "Not FDA-approved; many GH secretagogue peptides face compounding restrictions / enforcement risk for human therapeutic marketing.",
            "details": "Cannot lawfully market as FDA-approved therapy; research-chemical injection model is not compliant medical practice.",
            "authority": "FDA",
            "confidence": CF.HIGH,
            "vol": VL.ACTIVE_FLUX,
        },
        "jur-uk": {
            "basis": "Not MHRA-authorised medicines for anti-aging use.",
            "details": "No lawful approved product pathway for wellness secretagogue clinics.",
            "authority": "MHRA",
            "confidence": CF.HIGH,
        },
        "jur-au": {
            "basis": "Not TGA-registered medicines for this use; compounding/import constraints.",
            "details": "No standard approved pathway.",
            "authority": "TGA",
            "confidence": CF.HIGH,
        },
        "jur-de": {
            "basis": "Not authorised medicinal products for anti-aging marketing.",
            "details": "No approved pathway.",
            "authority": "BfArM",
            "confidence": CF.MODERATE,
        },
        "jur-ca": {
            "basis": "Not Health Canada approved drugs for this indication.",
            "details": "No approved pathway for routine care.",
            "authority": "Health Canada",
            "confidence": CF.MODERATE,
        },
        "jur-jp": {
            "basis": "Not PMDA-approved for wellness use.",
            "details": "No approved pathway.",
            "authority": "PMDA",
            "confidence": CF.HIGH,
        },
        "jur-sg": {
            "basis": "Not HSA-approved therapeutic products.",
            "details": "No approved pathway.",
            "authority": "HSA",
            "confidence": CF.HIGH,
        },
        "jur-fr": {
            "basis": "Not ANSM-authorised medicines for this use.",
            "details": "No approved pathway.",
            "authority": "ANSM",
            "confidence": CF.MODERATE,
        },
    },
}


def build_prohibited_access_records(existing_pairs: set):
    """Return list of access record dicts for pairs not already present."""
    out = []

    def add(rec):
        key = (rec["procedure_id"], rec["jurisdiction_id"])
        if key in existing_pairs:
            return
        if key in SKIP_PROCS_FOR_JUR:
            return
        existing_pairs.add(key)
        out.append(rec)

    # Classical psychedelics × jurisdictions with law notes
    for jur_id, law in JUR_PSYCHEDELIC_LAW.items():
        for proc_id in CONTROLLED_PSYCHEDELICS:
            if (proc_id, jur_id) in SKIP_PROCS_FOR_JUR:
                continue
            if law.get("status_override") == LS.DECRIMINALIZED:
                rec = _prohibited(
                    proc_id, jur_id,
                    authority=law["authority"],
                    legal_basis=law["basis"],
                    details=law["details"] + " Personal use may be administrative offence only; supply remains illegal.",
                    confidence=law.get("confidence", CF.MODERATE),
                    volatility=law.get("vol", VL.STABLE),
                    sources=law.get("sources"),
                )
                rec["legal_status"] = LS.DECRIMINALIZED
                rec["access_pathway"] = AP.NONE
                rec["arbitrage_summary"] = "Decriminalised personal use context but no legal therapy supply. Not a destination for regulated care."
                add(rec)
                continue
            details = law["details"]
            if jur_id == "jur-nl" and proc_id.startswith("proc-psilocybin"):
                details += " Soft exception: psilocybin sclerotia (truffles) sold in smart shops are legal retail — not the same as licensed therapy or mushroom fruiting bodies."
            add(_prohibited(
                proc_id, jur_id,
                authority=law["authority"],
                legal_basis=law["basis"],
                details=details,
                confidence=law.get("confidence", CF.MODERATE),
                volatility=law.get("vol", VL.STABLE),
                sources=law.get("sources"),
            ))

    # Cannabis prohibitions
    for jur_id, basis in CANNABIS_PROHIBITED_JURS.items():
        add(_prohibited(
            "proc-medical-cannabis", jur_id,
            authority="National narcotics authority",
            legal_basis=basis,
            details="No lawful medical cannabis programme for general patients under current national rules.",
            confidence=CF.HIGH,
            sources=[],
        ))

    # MAID prohibitions
    for jur_id, basis in MAID_PROHIBITED_JURS.items():
        if jur_id in ("jur-ca", "jur-ch", "jur-nl", "jur-be", "jur-es"):
            continue
        vol = VL.PENDING_LEGISLATION if jur_id in ("jur-uk", "jur-fr", "jur-de", "jur-au") else VL.STABLE
        add(_prohibited(
            "proc-maid", jur_id,
            authority="National criminal / health law",
            legal_basis=basis,
            details="No open national MAID access pathway for patients under this jurisdiction id. Subnational exceptions may exist elsewhere (e.g. some US states, Australian states).",
            confidence=CF.MODERATE,
            volatility=vol,
            sources=[],
        ))

    # Surrogacy total bans
    for jur_id, law in SURROGACY_ALL_BANNED.items():
        if not law:
            continue
        add(_prohibited(
            "proc-repro-surrogacy", jur_id,
            authority=law.get("authority", "National family / ART law"),
            legal_basis=law["basis"],
            details=law.get("details", law["basis"]),
            confidence=law.get("confidence", CF.HIGH),
            volatility=law.get("vol", VL.STABLE),
            sources=law.get("sources"),
        ))

    # MRT bans
    for jur_id, law in MRT_PROHIBITED.items():
        add(_prohibited(
            "proc-mito-replacement", jur_id,
            authority=law.get("authority", "National ART / bioethics law"),
            legal_basis=law["basis"],
            details=law.get("details", law["basis"]),
            confidence=law.get("confidence", CF.MODERATE),
            volatility=law.get("vol", VL.STABLE),
            sources=law.get("sources"),
        ))

    # Ozone
    for jur_id, law in OZONE_PROHIBITED.items():
        add(_prohibited(
            "proc-ozone-therapy", jur_id,
            authority=law.get("authority", "Medicines regulator"),
            legal_basis=law["basis"],
            details=law.get("details", law["basis"]),
            confidence=law.get("confidence", CF.MODERATE),
            volatility=law.get("vol", VL.STABLE),
            sources=law.get("sources"),
        ))

    # Peptides (BPC, CJC/ipa)
    for proc_id, jur_map in PEPTIDE_PROHIBITED.items():
        for jur_id, law in jur_map.items():
            add(_prohibited(
                proc_id, jur_id,
                authority=law.get("authority", "Medicines regulator"),
                legal_basis=law["basis"],
                details=law.get("details", law["basis"]),
                confidence=law.get("confidence", CF.MODERATE),
                volatility=law.get("vol", VL.STABLE),
                sources=law.get("sources"),
            ))

    return out


def all_jurisdiction_regulation():
    return dict(JURISDICTION_REGULATION)


def all_therapy_control_meta():
    return dict(THERAPY_CONTROL_META)
