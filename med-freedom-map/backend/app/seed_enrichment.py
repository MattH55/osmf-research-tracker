"""Enrichment data for access pathways (§4), pricing, and evidence grades (§5).

Values are derived from the already-researched narrative fields in seed.ACCESS_RECORDS
(cost ranges, pathway prose, published trial status) — not fabricated clinical claims.
Price midpoints are ESTIMATED unless the source text was a hard quote.
"""
from datetime import date

from .models import (
    AccessPathway,
    PriceConfidence,
    Confidence,
    Volatility,
    EvidenceGrade,
)


# ── §4 Access pathway + pricing patches ─────────────────────────────────────
# Key: (procedure_id, jurisdiction_id)
# Applied on every seed run so free-tier restarts pick up enrichment without reset.

ACCESS_ENRICHMENTS = {
    # Oregon regulated psilocybin
    ("proc-psilocybin-trd", "jur-us-or"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 2500.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 2800.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.ACTIVE_FLUX,
        "cost_notes_append": "Midpoint of $1,500–3,500 per session (OPS centers, cash-pay).",
    },
    ("proc-psilocybin-eol", "jur-us-or"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 2500.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 2800.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.ACTIVE_FLUX,
    },
    # Colorado dual model
    ("proc-psilocybin-trd", "jur-us-co"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 2000.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 2300.0,
        "confidence": Confidence.LOW,
        "volatility": Volatility.PENDING_LEGISLATION,
        "cost_notes_append": "Healing-center list prices not fully public; estimate from interim underground/early-center ranges $1,000–3,000. Personal cultivation is near-zero cash cost but not a licensed pathway.",
    },
    ("proc-dmt-depression", "jur-us-co"): {
        "access_pathway": AccessPathway.NONE,
        "price_usd": None,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.UNKNOWN,
        "total_access_cost_usd": None,
        "confidence": Confidence.LOW,
        "volatility": Volatility.ACTIVE_FLUX,
        "cost_notes_append": "Decriminalized personal use only — no licensed commercial/therapeutic supply; no reliable market price.",
    },
    # Australia TGA authorized prescriber
    ("proc-psilocybin-trd", "jur-au"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 9750.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 10500.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Midpoint of USD $6,500–13,000 per course (AU$10–20k); limited Medicare rebate.",
    },
    ("proc-mdma-ptsd", "jur-au"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 13250.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 15000.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Midpoint of USD $10,000–16,500 per multi-session course.",
    },
    # Próspera ZEDE
    ("proc-gene-crispr", "jur-hn-prospera"): {
        "access_pathway": AccessPathway.MEDICAL_TOURISM_CASH,
        "price_usd": 37500.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 40000.0,
        "confidence": Confidence.LOW,
        "volatility": Volatility.ACTIVE_FLUX,
        "cost_notes_append": "Public experimental quotes ~$25k–50k (e.g. plasmid/gene programs); not FDA-equivalent pricing.",
    },
    ("proc-stem-msc", "jur-hn-prospera"): {
        "access_pathway": AccessPathway.MEDICAL_TOURISM_CASH,
        "price_usd": 17500.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 19000.0,
        "confidence": Confidence.LOW,
        "volatility": Volatility.ACTIVE_FLUX,
        "cost_notes_append": "Midpoint of $5,000–30,000 clinic packages.",
    },
    # Canada / Switzerland MAID
    ("proc-maid", "jur-ca"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 0.0,
        "price_basis": "insured",
        "price_confidence": PriceConfidence.QUOTED,
        "total_access_cost_usd": 0.0,
        "confidence": Confidence.HIGH,
        "volatility": Volatility.PENDING_LEGISLATION,
        "cost_notes_append": "Publicly funded under provincial plans for eligible residents; $0 procedure cost. Travel/residency establishment costs are separate.",
    },
    ("proc-maid", "jur-ch"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 10500.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 12500.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Dignitas ~CHF 7.5–10.5k; Pegasos ~CHF 10–12k. Midpoint ~USD $10,500 org fees; travel/housing extra.",
    },
    # Switzerland / Canada psychedelics
    ("proc-lsd-anxiety", "jur-ch"): {
        "access_pathway": AccessPathway.EXPANDED_ACCESS,
        "price_usd": 11300.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 12000.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "BAG exceptional authorization; CHF 5–15k course midpoint ~USD $11,300. Some cantonal insurance partial cover.",
    },
    ("proc-psilocybin-trd", "jur-ca"): {
        "access_pathway": AccessPathway.EXPANDED_ACCESS,
        "price_usd": 6250.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 7000.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.ACTIVE_FLUX,
        "cost_notes_append": "SAP/Section 56 pathway; CAD $5–12k midpoint ~USD $6,250. Physician visits may be provincial-covered.",
    },
    # Mexico medical tourism
    ("proc-stem-msc", "jur-mx"): {
        "access_pathway": AccessPathway.MEDICAL_TOURISM_CASH,
        "price_usd": 14000.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 15500.0,
        "confidence": Confidence.LOW,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Wide clinic range $3,000–25,000+; midpoint for due-diligence comparison only.",
    },
    ("proc-ibogaine-addiction", "jur-mx"): {
        "access_pathway": AccessPathway.MEDICAL_TOURISM_CASH,
        "price_usd": 7500.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 8500.0,
        "confidence": Confidence.LOW,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Medical-supervised clinics typically $6–12k; broader market $3–8k. Cardiac-capable clinics cost more.",
    },
    # US ketamine
    ("proc-ketamine-depression", "jur-us-federal"): {
        "access_pathway": AccessPathway.OFF_LABEL_PRESCRIPTION,
        "price_usd": 600.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 4200.0,
        "confidence": Confidence.HIGH,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "IV cash-pay ~$400–800/infusion (mid $600); induction series ~6 sessions. Spravato often insured (~$590–885 drug + admin).",
    },
    ("proc-ketamine-depression", "jur-us-or"): {
        "access_pathway": AccessPathway.OFF_LABEL_PRESCRIPTION,
        "price_usd": 500.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.QUOTED,
        "total_access_cost_usd": 3500.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Portland competitive IV range $350–650; using mid $500. Spravato insurance pathway same as federal.",
    },
    # US small molecules
    ("proc-repurposed-semaglutide", "jur-us-federal"): {
        "access_pathway": AccessPathway.STANDARD_PRESCRIPTION,
        "price_usd": 1150.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 1150.0,
        "confidence": Confidence.HIGH,
        "volatility": Volatility.ACTIVE_FLUX,
        "cost_notes_append": "Brand list ~$900–1,400/mo (mid $1,150). Compounded often $200–500/mo when allowed. Insured copays far lower with PA.",
    },
    ("proc-repurposed-rapamycin", "jur-us-federal"): {
        "access_pathway": AccessPathway.OFF_LABEL_PRESCRIPTION,
        "price_usd": 100.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 250.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Generic sirolimus ~$50–150/mo drug; telemed membership + labs extra (~$100–400).",
    },
    # Surrogacy Canada
    ("proc-repro-surrogacy", "jur-ca"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 59000.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 65000.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Total journey mid of CAD $60–100k (~USD $44–74k) including IVF, expenses, legal, agency.",
    },
    # Jamaica retreats
    ("proc-psilocybin-trd", "jur-jm"): {
        "access_pathway": AccessPathway.MEDICAL_TOURISM_CASH,
        "price_usd": 5000.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 6500.0,
        "confidence": Confidence.LOW,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "5–7 day retreat mid of $2,000–8,000; airfare typically $500–1,500 additional.",
    },
    # US gene / cell
    ("proc-gene-crispr", "jur-us-federal"): {
        "access_pathway": AccessPathway.RIGHT_TO_TRY,
        "price_usd": 2200000.0,
        "price_basis": "insured",
        "price_confidence": PriceConfidence.QUOTED,
        "total_access_cost_usd": 2500000.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Casgevy list ~$2.2M when on-label. RTT/Expanded Access: drug often free but hospitalization $100k–500k+. Dual pathway.",
    },
    ("proc-stem-car-t", "jur-us-federal"): {
        "access_pathway": AccessPathway.STANDARD_PRESCRIPTION,
        "price_usd": 424000.0,
        "price_basis": "insured",
        "price_confidence": PriceConfidence.QUOTED,
        "total_access_cost_usd": 750000.0,
        "confidence": Confidence.HIGH,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Drug list $373–475k (mid $424k); total episode often $500k–1M+. Medicare/commercial typically cover labeled indications.",
    },
    # IVF
    ("proc-repro-ivf", "jur-us-federal"): {
        "access_pathway": AccessPathway.LICENSED_PROVIDER_REGIME,
        "price_usd": 18500.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 25000.0,
        "confidence": Confidence.HIGH,
        "volatility": Volatility.PENDING_LEGISLATION,
        "cost_notes_append": "Cycle mid $12–25k; PGT + meds often push total ~$20–30k cash-pay. Mandate-state insurance reduces OOP.",
    },
    ("proc-repro-ivf", "jur-mx"): {
        "access_pathway": AccessPathway.MEDICAL_TOURISM_CASH,
        "price_usd": 6000.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 8000.0,
        "confidence": Confidence.MODERATE,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "IVF cycle mid $4–8k; PGT extra $1.5–3k. ~50–70% below US cash-pay.",
    },
    # US adjunct procedures
    ("proc-nad-iv", "jur-us-federal"): {
        "access_pathway": AccessPathway.OFF_LABEL_PRESCRIPTION,
        "price_usd": 450.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 3600.0,
        "confidence": Confidence.LOW,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Per-infusion mid $300–600 ($450); multi-session packages $3–8k common.",
    },
    ("proc-hbot", "jur-us-federal"): {
        "access_pathway": AccessPathway.STANDARD_PRESCRIPTION,
        "price_usd": 250.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 7500.0,
        "confidence": Confidence.HIGH,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "$150–350/session mid $250; 20–40 session courses $3–14k. FDA indications often insured.",
    },
    ("proc-fmt", "jur-us-federal"): {
        "access_pathway": AccessPathway.STANDARD_PRESCRIPTION,
        "price_usd": 1750.0,
        "price_basis": "insured",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 1750.0,
        "confidence": Confidence.HIGH,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "rCDI mid $500–3,000, usually insured. Off-label IBD/IBS cash-pay often $2–5k+.",
    },
    # Mescaline retreats (seeded under MX id; pathway is tourism cash)
    ("proc-mescaline-therapy", "jur-mx"): {
        "access_pathway": AccessPathway.MEDICAL_TOURISM_CASH,
        "price_usd": 2000.0,
        "price_basis": "cash_pay",
        "price_confidence": PriceConfidence.ESTIMATED,
        "total_access_cost_usd": 3500.0,
        "confidence": Confidence.LOW,
        "volatility": Volatility.STABLE,
        "cost_notes_append": "Retreat mid $1–3k (Andean/Amazon programs also common); travel $1–2k. Minimal medical oversight.",
    },
}


# ── Procedure → diseases (primary clinical targets for UI filter/display) ────
# Human-readable disease names shown on treatments and used for filtering.

PROCEDURE_DISEASES = {
    "proc-psilocybin-trd": ["Treatment-Resistant Depression", "Major Depressive Disorder"],
    "proc-psilocybin-eol": ["Cancer-Related Anxiety", "End-of-Life Existential Distress", "Adjustment Disorder"],
    "proc-mdma-ptsd": ["Post-Traumatic Stress Disorder (PTSD)"],
    "proc-ketamine-depression": ["Treatment-Resistant Depression", "Major Depressive Disorder", "Suicidal Ideation"],
    "proc-ibogaine-addiction": ["Opioid Use Disorder", "Substance Use Disorder"],
    "proc-gene-crispr": ["Sickle Cell Disease", "Beta-Thalassemia", "Genetic Blood Disorders"],
    "proc-gene-aa9": ["Spinal Muscular Atrophy (SMA)", "Inherited Retinal Dystrophy", "Hemophilia B", "Duchenne Muscular Dystrophy"],
    "proc-stem-msc": ["Osteoarthritis", "Autoimmune Disease", "Inflammatory Conditions", "Crohn's Disease"],
    "proc-stem-car-t": ["Relapsed/Refractory B-cell ALL", "Diffuse Large B-cell Lymphoma", "Multiple Myeloma"],
    "proc-maid": ["Terminal Illness", "Grievous Irremediable Medical Condition", "Intolerable Suffering"],
    "proc-peptide-bpc": ["Tendon/Ligament Injury", "Inflammatory Bowel Disease", "Gastric Ulcer", "Wound Healing Impairment"],
    "proc-peptide-thymosin": ["Chronic Hepatitis B", "Chronic Hepatitis C", "Immune Deficiency", "Chronic Viral Infection"],
    "proc-repro-ivf": ["Infertility", "Recurrent Pregnancy Loss", "Genetic Carrier Status"],
    "proc-repro-surrogacy": ["Uterine Factor Infertility", "Medical Contraindication to Pregnancy", "Recurrent IVF Failure"],
    "proc-repurposed-ldn": ["Fibromyalgia", "Crohn's Disease", "Multiple Sclerosis", "ME/CFS", "Long COVID", "Chronic Pain"],
    "proc-repurposed-methylene": ["Mild Cognitive Impairment", "Bipolar Depression", "Mitochondrial Dysfunction", "Methemoglobinemia"],
    "proc-repurposed-semaglutide": ["Obesity", "Type 2 Diabetes", "Cardiovascular Disease Risk", "NAFLD/NASH"],
    "proc-repurposed-rapamycin": ["Age-Related Functional Decline", "Lymphangioleiomyomatosis (LAM)", "Transplant Rejection (labeled)"],
    "proc-stem-exosome": ["Osteoarthritis", "Androgenetic Alopecia", "Skin Aging", "Soft Tissue Injury"],
    "proc-dmt-depression": ["Major Depressive Disorder", "Treatment-Resistant Depression"],
    "proc-lsd-anxiety": ["Generalized Anxiety Disorder", "Illness-Related Anxiety"],
    "proc-mescaline-therapy": ["Depression", "Substance Use Disorder", "Existential Distress"],
    "proc-nad-iv": ["Chronic Fatigue", "Long COVID", "Mitochondrial Dysfunction", "Age-Related Decline"],
    "proc-hbot": ["Diabetic Foot Ulcer", "Chronic Osteomyelitis", "Traumatic Brain Injury (off-label)", "Chronic Lyme (off-label)"],
    "proc-fmt": ["Recurrent C. difficile Infection", "Ulcerative Colitis (off-label)", "Crohn's Disease (off-label)"],
    "proc-pt-141": ["Hypoactive Sexual Desire Disorder (HSDD)", "Erectile Dysfunction (off-label)"],
    "proc-cryotherapy": ["Muscle Recovery", "Chronic Inflammation", "Sports Injury Recovery"],
    "proc-prp-therapy": ["Knee Osteoarthritis", "Tendinopathy", "Rotator Cuff Injury", "Androgenetic Alopecia"],
    "proc-nmn-nmad": ["Age-Related Functional Decline", "Metabolic Syndrome"],
    "proc-ayahuasca": ["Depression", "Substance Use Disorder", "PTSD", "Existential Distress"],
    "proc-medical-cannabis": ["Chronic Pain", "Epilepsy", "PTSD", "Chemotherapy-Induced Nausea", "Anxiety"],
    "proc-ozone-therapy": ["Chronic Wound", "Chronic Infection", "Osteoarthritis (off-label)"],
    "proc-stem-nsc": ["Parkinson's Disease", "ALS", "Spinal Cord Injury", "Alzheimer's Disease"],
    "proc-proton-therapy": ["Pediatric Cancer", "CNS Tumors", "Prostate Cancer", "Base-of-Skull Tumors"],
    "proc-senolytics": ["Frailty", "Age-Related Functional Decline", "Cellular Senescence"],
    "proc-chelation": ["Lead Poisoning", "Heavy Metal Toxicity", "Iron Overload"],
    "proc-metformin-longevity": ["Type 2 Diabetes (labeled)", "Age-Related Functional Decline", "Prediabetes"],
}


# ── §5 Conditions (focused seed set) ─────────────────────────────────────────

CONDITIONS = [
    {
        "id": "cond-trd",
        "name": "Treatment-Resistant Depression",
        "icd_code": "F33.2",
        "description": "Major depressive disorder that has not responded to at least two adequate antidepressant trials. Primary indication for several psychedelic and ketamine pathways in this map.",
    },
    {
        "id": "cond-ptsd",
        "name": "Post-Traumatic Stress Disorder",
        "icd_code": "F43.1",
        "description": "PTSD meeting clinical diagnostic criteria (e.g. CAPS-5). Core indication for MDMA-assisted psychotherapy programs.",
    },
    {
        "id": "cond-oud",
        "name": "Opioid Use Disorder",
        "icd_code": "F11.2",
        "description": "Opioid dependence/use disorder; primary use-case for medically supervised ibogaine detoxification clinics.",
    },
    {
        "id": "cond-scd",
        "name": "Sickle Cell Disease",
        "icd_code": "D57",
        "description": "Sickle cell disease with recurrent vaso-occlusive crises; labeled indication for exa-cel/Casgevy and related gene therapies.",
    },
    {
        "id": "cond-rr-heme",
        "name": "Relapsed/Refractory Hematologic Malignancy",
        "icd_code": "C85.9",
        "description": "Relapsed or refractory B-cell ALL, DLBCL, multiple myeloma, and related labeled CAR-T indications.",
    },
    {
        "id": "cond-obesity",
        "name": "Obesity / Overweight with Comorbidity",
        "icd_code": "E66",
        "description": "BMI ≥30, or ≥27 with weight-related comorbidity — labeled population for Wegovy/Zepbound and related GLP-1 agonists.",
    },
    {
        "id": "cond-t2d",
        "name": "Type 2 Diabetes Mellitus",
        "icd_code": "E11",
        "description": "Type 2 diabetes; original labeled indication for Ozempic/Mounjaro and related GLP-1/GIP agents.",
    },
    {
        "id": "cond-infertility",
        "name": "Infertility",
        "icd_code": "N97",
        "description": "Inability to achieve pregnancy after 12 months of unprotected intercourse (or earlier with known pathology). Primary demand driver for IVF/PGT.",
    },
    {
        "id": "cond-rcdi",
        "name": "Recurrent Clostridioides difficile Infection",
        "icd_code": "A04.72",
        "description": "Recurrent CDI after antibiotic failure; FDA-cleared indication for fecal microbiota products/FMT.",
    },
    {
        "id": "cond-eol-anxiety",
        "name": "Cancer-Related End-of-Life Anxiety / Existential Distress",
        "icd_code": "F43.8",
        "description": "Anxiety, depression, or existential distress associated with life-threatening cancer or terminal illness.",
    },
    {
        "id": "cond-diabetic-wound",
        "name": "Diabetic Foot Ulcer / Chronic Wound",
        "icd_code": "E11.621",
        "description": "Non-healing diabetic wounds; classic FDA-covered hyperbaric oxygen therapy indication.",
    },
    {
        "id": "cond-aging",
        "name": "Age-Related Functional Decline / Longevity Interest",
        "icd_code": "R54",
        "description": "Not a formal disease entity; captures off-label longevity use of mTOR inhibitors, NAD+ precursors, and related interventions.",
    },
    {
        "id": "cond-gad",
        "name": "Generalized Anxiety Disorder",
        "icd_code": "F41.1",
        "description": "GAD; primary clinical development indication for LSD-assisted therapy (e.g. MM-120).",
    },
    {
        "id": "cond-oa",
        "name": "Osteoarthritis",
        "icd_code": "M19",
        "description": "Degenerative joint disease; common marketed use for MSC and regenerative tourism clinics (evidence variable).",
    },
]


# ── §5 Procedure–condition evidence grades ───────────────────────────────────
# Grades follow schema: E1 multi-RCT consistent · E2 one RCT · E3 small/conflicting
# · E4 uncontrolled · E5 case series · E6 animal · E7 in vitro · E8 none.
# Summaries cite well-known landmark literature already referenced in procedure sources.

PROCEDURE_INDICATIONS = [
    {
        "id": "pi-psilo-trd",
        "procedure_id": "proc-psilocybin-trd",
        "condition_id": "cond-trd",
        "evidence_grade": EvidenceGrade.E2,
        "evidence_summary": "Phase 2b COMPASS/Goodwin et al. (NEJM 2022) and earlier academic RCTs (Carhart-Harris, Davis) show large effect sizes in TRD; confirmatory phase 3 still maturing. Grade E2 (strong single-class RCTs, not yet multi-pivotal approval package).",
    },
    {
        "id": "pi-psilo-eol",
        "procedure_id": "proc-psilocybin-eol",
        "condition_id": "cond-eol-anxiety",
        "evidence_grade": EvidenceGrade.E2,
        "evidence_summary": "Landmark RCTs at Johns Hopkins, NYU, and UCLA (Griffiths 2016, Ross 2016) for cancer-related anxiety/depression; consistent direction with durable effects in small-moderate samples. E2.",
    },
    {
        "id": "pi-mdma-ptsd",
        "procedure_id": "proc-mdma-ptsd",
        "condition_id": "cond-ptsd",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "Two MAPS/Lykos phase 3 RCTs (Mitchell et al. Nature Medicine 2021 and follow-on) showed substantial CAPS-5 reductions; ~67% no longer met PTSD criteria in pivotal report. Multi-RCT consistent → E1. FDA CRL 2024 did not erase the trial data; regulatory status remains separate from evidence grade.",
    },
    {
        "id": "pi-ket-trd",
        "procedure_id": "proc-ketamine-depression",
        "condition_id": "cond-trd",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "Multiple RCTs for IV ketamine and pivotal trials for esketamine (Spravato) support rapid antidepressant effect in TRD/suicidality. On-label approval for esketamine. E1.",
    },
    {
        "id": "pi-ibo-oud",
        "procedure_id": "proc-ibogaine-addiction",
        "condition_id": "cond-oud",
        "evidence_grade": EvidenceGrade.E4,
        "evidence_summary": "Observational cohorts and open-label series report interruption of opioid withdrawal; no large definitive RCTs. Documented cardiac mortality risk. E4 (uncontrolled clinical evidence).",
    },
    {
        "id": "pi-crispr-scd",
        "procedure_id": "proc-gene-crispr",
        "condition_id": "cond-scd",
        "evidence_grade": EvidenceGrade.E2,
        "evidence_summary": "Casgevy (exa-cel) approved on basis of pivotal clinical trial data showing elimination of severe VOCs in majority of treated SCD patients. Single pivotal program class → E2 (regulatory-grade, not multi-independent confirmatory packages).",
    },
    {
        "id": "pi-cart-heme",
        "procedure_id": "proc-stem-car-t",
        "condition_id": "cond-rr-heme",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "Multiple pivotal trials across Kymriah, Yescarta, Breyanzi, Carvykti, Abecma, etc., with durable remissions in R/R B-cell and myeloma populations. E1.",
    },
    {
        "id": "pi-glp1-obesity",
        "procedure_id": "proc-repurposed-semaglutide",
        "condition_id": "cond-obesity",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "STEP (semaglutide) and SURMOUNT (tirzepatide) multi-RCT programs show large, consistent weight loss. E1.",
    },
    {
        "id": "pi-glp1-t2d",
        "procedure_id": "proc-repurposed-semaglutide",
        "condition_id": "cond-t2d",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "Extensive phase 3 programs (SUSTAIN, SURPASS, etc.) plus cardiovascular outcome trials (e.g. SELECT for semaglutide in overweight/obese with CV disease). E1.",
    },
    {
        "id": "pi-rapa-aging",
        "procedure_id": "proc-repurposed-rapamycin",
        "condition_id": "cond-aging",
        "evidence_grade": EvidenceGrade.E4,
        "evidence_summary": "Robust lifespan extension in model organisms; human evidence for healthspan is early (open-label, participant-led PEARL, small trials). Not disease-modifying RCTs for aging per se. E4.",
    },
    {
        "id": "pi-ivf-infert",
        "procedure_id": "proc-repro-ivf",
        "condition_id": "cond-infertility",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "Decades of RCTs and registry data establish IVF (with/without PGT in selected cases) as standard fertility treatment with quantified live-birth rates. E1.",
    },
    {
        "id": "pi-fmt-rcdi",
        "procedure_id": "proc-fmt",
        "condition_id": "cond-rcdi",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "Multiple RCTs and meta-analyses show >80–90% cure for recurrent CDI vs antibiotics; FDA-cleared microbiota products. E1.",
    },
    {
        "id": "pi-hbot-wound",
        "procedure_id": "proc-hbot",
        "condition_id": "cond-diabetic-wound",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "RCTs and UHMS-supported evidence base for selected chronic wound indications; longstanding FDA-cleared use. E1 for labeled wound indications (not for off-label Lyme/TBI claims).",
    },
    {
        "id": "pi-lsd-gad",
        "procedure_id": "proc-lsd-anxiety",
        "condition_id": "cond-gad",
        "evidence_grade": EvidenceGrade.E2,
        "evidence_summary": "Modern MindMed MM-120 phase 2b for GAD reported clinically meaningful reductions; historical LSD psychotherapy literature is older and less controlled. Contemporary grade E2.",
    },
    {
        "id": "pi-msc-oa",
        "procedure_id": "proc-stem-msc",
        "condition_id": "cond-oa",
        "evidence_grade": EvidenceGrade.E3,
        "evidence_summary": "Heterogeneous small RCTs and uncontrolled series for OA; effect sizes and product characterization vary widely. Conflicting/insufficient standardization → E3.",
    },
    {
        "id": "pi-nad-aging",
        "procedure_id": "proc-nad-iv",
        "condition_id": "cond-aging",
        "evidence_grade": EvidenceGrade.E5,
        "evidence_summary": "Popular longevity clinic use; human evidence for IV NAD+ on hard clinical endpoints is sparse (case series, small open-label). E5.",
    },
    {
        "id": "pi-mesc-trd",
        "procedure_id": "proc-mescaline-therapy",
        "condition_id": "cond-trd",
        "evidence_grade": EvidenceGrade.E5,
        "evidence_summary": "Traditional/ceremonial use and emerging interest; modern controlled clinical evidence for mescaline in depression remains limited (case series / early research). E5.",
    },
    {
        "id": "pi-surrogacy-infert",
        "procedure_id": "proc-repro-surrogacy",
        "condition_id": "cond-infertility",
        "evidence_grade": EvidenceGrade.E1,
        "evidence_summary": "Gestational surrogacy is established reproductive practice with large outcome registries; evidence grade reflects clinical standard for indicated populations (uterine factor, recurrent failure, same-sex male couples), not a drug RCT package.",
    },
]


def apply_access_enrichment(ar_orm, enrichment: dict, today=None) -> bool:
    """Apply enrichment dict onto an AccessRecord ORM instance. Returns True if changed."""
    changed = False
    for key in (
        "access_pathway",
        "price_usd",
        "price_basis",
        "price_confidence",
        "total_access_cost_usd",
        "confidence",
        "volatility",
    ):
        if key not in enrichment:
            continue
        new_val = enrichment[key]
        old_val = getattr(ar_orm, key, None)
        # Normalize enum compare
        old_cmp = old_val.value if hasattr(old_val, "value") else old_val
        new_cmp = new_val.value if hasattr(new_val, "value") else new_val
        if old_cmp != new_cmp:
            setattr(ar_orm, key, new_val)
            changed = True

    append = enrichment.get("cost_notes_append")
    if append:
        existing = ar_orm.cost_notes or ""
        if append not in existing:
            ar_orm.cost_notes = (existing + " " + append).strip() if existing else append
            changed = True

    if changed:
        ar_orm.last_verified = today or date.today()
        ar_orm.verified_by = "seed_enrichment_v1"
    return changed
