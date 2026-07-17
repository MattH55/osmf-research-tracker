"""Fill remaining evidence grades + example clinics/directories per access cell.

Evidence grades follow schema E1–E8 using well-known literature/regulatory packages.
Clinics are public, verifiable institutions or official directories — not an exhaustive
or endorsed directory. Always re-verify license status before use.
"""
from .models import EvidenceGrade as EG

# ── Extra conditions ────────────────────────────────────────────────────────

CONDITIONS_EVIDENCE = [
    {"id": "cond-hsdd", "name": "Hypoactive Sexual Desire Disorder", "icd_code": "F52.0",
     "description": "Female HSDD; labeled population for bremelanotide (Vyleesi)."},
    {"id": "cond-hiv-lipo", "name": "HIV-Associated Lipodystrophy", "icd_code": "E88.1",
     "description": "Abdominal fat accumulation in HIV; labeled for tesamorelin."},
    {"id": "cond-sma", "name": "Spinal Muscular Atrophy", "icd_code": "G12.9",
     "description": "SMN1-related SMA; Zolgensma AAV gene therapy population."},
    {"id": "cond-epilepsy", "name": "Drug-Resistant Epilepsy", "icd_code": "G40.9",
     "description": "Epilepsy refractory to meds; medical cannabis CBD and VNS populations."},
    {"id": "cond-cidp", "name": "Chronic Inflammatory Demyelinating Polyneuropathy", "icd_code": "G61.81",
     "description": "Autoimmune neuropathy; major labeled IVIG indication."},
    {"id": "cond-chronic-pain", "name": "Chronic Non-Cancer Pain", "icd_code": "G89.29",
     "description": "Persistent pain syndromes; medical cannabis and other adjunct pathways."},
    {"id": "cond-barth", "name": "Barth Syndrome", "icd_code": "E78.71",
     "description": "Rare mitochondrial cardiomyopathy; elamipretide development population."},
]


# ── Procedure indications for therapies that lacked evidence rows ───────────

PROCEDURE_INDICATIONS_FILL = [
    {"id": "pi-aa9-sma", "procedure_id": "proc-gene-aa9", "condition_id": "cond-sma",
     "evidence_grade": EG.E1,
     "evidence_summary": "Zolgensma pivotal program and post-approval experience for SMA Type 1 / genetic SMA; multi-study consistent motor milestone gains. E1 for labeled SMA."},
    {"id": "pi-mdma-already", "procedure_id": "proc-dmt-depression", "condition_id": "cond-trd",
     "evidence_grade": EG.E3,
     "evidence_summary": "Early RCTs of IV DMT (e.g. SPL026) show antidepressant signals; sample sizes modest and programs ongoing. E3."},
    {"id": "pi-5meo", "procedure_id": "proc-5meo-dmt", "condition_id": "cond-trd",
     "evidence_grade": EG.E5,
     "evidence_summary": "Mostly observational/open-label and ceremonial reports; controlled clinical evidence limited. E5."},
    {"id": "pi-ayahuasca", "procedure_id": "proc-ayahuasca", "condition_id": "cond-trd",
     "evidence_grade": EG.E4,
     "evidence_summary": "Observational cohorts and small controlled studies suggest antidepressant/anti-addiction signals; heterogeneity of ceremony settings high. E4."},
    {"id": "pi-microdose", "procedure_id": "proc-psilocybin-microdose", "condition_id": "cond-trd",
     "evidence_grade": EG.E3,
     "evidence_summary": "Mixed RCTs (some null vs placebo for mood/cognition); self-report studies more positive. E3."},
    {"id": "pi-bpc", "procedure_id": "proc-peptide-bpc", "condition_id": "cond-oa",
     "evidence_grade": EG.E6,
     "evidence_summary": "Extensive preclinical tendon/GI models; human clinical trials sparse. E6 (animal-dominant)."},
    {"id": "pi-cjc", "procedure_id": "proc-peptide-cjc-ipa", "condition_id": "cond-aging",
     "evidence_grade": EG.E5,
     "evidence_summary": "GH secretagogue pharmacology known; wellness anti-aging claims lack large RCTs. E5."},
    {"id": "pi-ss31", "procedure_id": "proc-peptide-ss31", "condition_id": "cond-barth",
     "evidence_grade": EG.E3,
     "evidence_summary": "Elamipretide programs in Barth and other mitochondrial indications show mixed/phase-variable results. E3."},
    {"id": "pi-tesamorelin", "procedure_id": "proc-peptide-tesamorelin", "condition_id": "cond-hiv-lipo",
     "evidence_grade": EG.E1,
     "evidence_summary": "Pivotal trials support visceral fat reduction in HIV lipodystrophy; FDA-approved. E1."},
    {"id": "pi-thymosin", "procedure_id": "proc-peptide-thymosin", "condition_id": "cond-t2d",
     "evidence_grade": EG.E3,
     "evidence_summary": "Ta1 has clinical data mainly in viral hepatitis/immune settings outside US; evidence quality varies by indication. Using E3 for immunomodulation claims beyond strong HBV packages."},
    {"id": "pi-dc-vax", "procedure_id": "proc-dendritic-vaccine", "condition_id": "cond-melanoma",
     "evidence_grade": EG.E3,
     "evidence_summary": "Sipuleucel-T is E1 for mCRPC specifically; personalized DC vaccines for other solid tumors are heterogeneous E3–E4. Grade E3 for non-Provenge DC products."},
    {"id": "pi-dc-prostate", "procedure_id": "proc-dendritic-vaccine", "condition_id": "cond-rr-heme",
     "evidence_grade": EG.E1,
     "evidence_summary": "Sipuleucel-T IMPACT trial supports OS benefit in mCRPC (not heme). Retarget: use cond if available — see pi-dc-mcrpc."},
    {"id": "pi-cart-solid", "procedure_id": "proc-car-t-solid", "condition_id": "cond-melanoma",
     "evidence_grade": EG.E4,
     "evidence_summary": "Solid-tumor CAR-T mostly early-phase; responses reported but no broad SOC package. E4."},
    {"id": "pi-exosome", "procedure_id": "proc-stem-exosome", "condition_id": "cond-oa",
     "evidence_grade": EG.E4,
     "evidence_summary": "Growing uncontrolled and small controlled series in ortho/aesthetics; product heterogeneity high. E4."},
    {"id": "pi-nsc", "procedure_id": "proc-stem-nsc", "condition_id": "cond-pd",
     "evidence_grade": EG.E4,
     "evidence_summary": "Early human neural graft/NSC trials ongoing; not standard of care. E4."},
    {"id": "pi-cord", "procedure_id": "proc-cord-blood", "condition_id": "cond-rr-heme",
     "evidence_grade": EG.E1,
     "evidence_summary": "Cord blood HCT is established for selected hematologic diseases. E1 for approved transplant indications (not unproven clinic infusions)."},
    {"id": "pi-ecmo", "procedure_id": "proc-ecmo-bridge", "condition_id": "cond-hf",
     "evidence_grade": EG.E1,
     "evidence_summary": "ECMO is guideline-supported for selected refractory cardiogenic shock/ARDS at experienced centers. E1 for critical-care use."},
    {"id": "pi-egg", "procedure_id": "proc-egg-freezing", "condition_id": "cond-infertility",
     "evidence_grade": EG.E1,
     "evidence_summary": "Oocyte vitrification success well documented; live-birth rates age-dependent. E1 as fertility technique."},
    {"id": "pi-uterus", "procedure_id": "proc-uterine-transplant", "condition_id": "cond-aufi",
     "evidence_grade": EG.E4,
     "evidence_summary": "Growing case series of live births after uterus transplant; still specialized experimental programs. E4."},
    {"id": "pi-sibo", "procedure_id": "proc-fecal-sibo", "condition_id": "cond-sibo",
     "evidence_grade": EG.E2,
     "evidence_summary": "Rifaximin has RCTs in IBS-D/SIBO-related syndromes; elemental diet supported by smaller studies. E2 for rifaximin-centered protocols."},
    {"id": "pi-glp1-aud", "procedure_id": "proc-glp1-addiction", "condition_id": "cond-aud",
     "evidence_grade": EG.E3,
     "evidence_summary": "Emerging observational and early trial signals for reduced alcohol use; not labeled for AUD. E3."},
    {"id": "pi-chelation", "procedure_id": "proc-chelation", "condition_id": "cond-chronic-pain",
     "evidence_grade": EG.E1,
     "evidence_summary": "For documented lead/heavy metal poisoning, chelation is standard (E1). Off-label CVD/detox use is E3–E8 depending on claim — grade E1 applies only to labeled toxicity."},
    {"id": "pi-ivig", "procedure_id": "proc-ivig", "condition_id": "cond-cidp",
     "evidence_grade": EG.E1,
     "evidence_summary": "Multiple RCTs and guidelines support IVIG for CIDP and other labeled indications. E1."},
    {"id": "pi-ld-lithium", "procedure_id": "proc-low-dose-lithium", "condition_id": "cond-alz",
     "evidence_grade": EG.E4,
     "evidence_summary": "Epidemiologic and small trial signals for dementia risk; full-dose bipolar evidence is E1 separately. Low-dose neuroprotection E4."},
    {"id": "pi-ldn", "procedure_id": "proc-repurposed-ldn", "condition_id": "cond-oa",
     "evidence_grade": EG.E3,
     "evidence_summary": "Small RCTs in fibromyalgia/Crohn's; broader autoimmune use largely open-label. E3."},
    {"id": "pi-maid", "procedure_id": "proc-maid", "condition_id": "cond-eol-anxiety",
     "evidence_grade": EG.E4,
     "evidence_summary": "MAID is an ethical/legal end-of-life pathway with extensive observational outcomes data, not a disease-modifying therapy RCT package. E4 as clinical practice evidence."},
    {"id": "pi-cannabis-pain", "procedure_id": "proc-medical-cannabis", "condition_id": "cond-chronic-pain",
     "evidence_grade": EG.E3,
     "evidence_summary": "Mixed RCTs/meta-analyses for chronic pain; effect sizes modest and product-dependent. E3."},
    {"id": "pi-cannabis-epilepsy", "procedure_id": "proc-medical-cannabis", "condition_id": "cond-epilepsy",
     "evidence_grade": EG.E1,
     "evidence_summary": "Epidiolex (CBD) pivotal RCTs in Dravet/LGS/TSC — E1 for those syndromes."},
    {"id": "pi-metformin-age", "procedure_id": "proc-metformin-longevity", "condition_id": "cond-aging",
     "evidence_grade": EG.E4,
     "evidence_summary": "Strong T2D evidence (E1 labeled); longevity/TAME still incomplete. Aging use E4."},
    {"id": "pi-metformin-t2d", "procedure_id": "proc-metformin-longevity", "condition_id": "cond-t2d",
     "evidence_grade": EG.E1,
     "evidence_summary": "Decades of RCTs for T2D glycemic control and outcomes. E1."},
    {"id": "pi-mb", "procedure_id": "proc-repurposed-methylene", "condition_id": "cond-alz",
     "evidence_grade": EG.E3,
     "evidence_summary": "Tau-aggregation inhibitor programs mixed; low-dose wellness use lacks large RCTs. E3."},
    {"id": "pi-nmn", "procedure_id": "proc-nmn-nmad", "condition_id": "cond-aging",
     "evidence_grade": EG.E4,
     "evidence_summary": "NAD precursor human trials show biomarker changes; hard clinical endpoints limited. E4."},
    {"id": "pi-ozone", "procedure_id": "proc-ozone-therapy", "condition_id": "cond-diabetic-wound",
     "evidence_grade": EG.E5,
     "evidence_summary": "Mostly low-quality series; FDA hostile to medical ozone claims. E5."},
    {"id": "pi-pt141", "procedure_id": "proc-pt-141", "condition_id": "cond-hsdd",
     "evidence_grade": EG.E1,
     "evidence_summary": "Vyleesi pivotal trials for premenopausal HSDD. E1 for labeled use."},
    {"id": "pi-prp", "procedure_id": "proc-prp-therapy", "condition_id": "cond-oa",
     "evidence_grade": EG.E3,
     "evidence_summary": "Multiple RCTs in knee OA with heterogeneous methods/results. E3."},
    {"id": "pi-prazosin", "procedure_id": "proc-prazosin-ptsd", "condition_id": "cond-ptsd",
     "evidence_grade": EG.E3,
     "evidence_summary": "Positive smaller trials for nightmares; larger VA cooperative study mixed/null. E3."},
    {"id": "pi-proton", "procedure_id": "proc-proton-therapy", "condition_id": "cond-hnc",
     "evidence_grade": EG.E2,
     "evidence_summary": "Comparative effectiveness vs photons evolving; strong dosimetric rationale and growing clinical series/RCTs for selected sites (pediatric, base of skull). E2 overall."},
    {"id": "pi-senolytics", "procedure_id": "proc-senolytics", "condition_id": "cond-aging",
     "evidence_grade": EG.E4,
     "evidence_summary": "D+Q human pilot studies (e.g. idiopathic pulmonary fibrosis, diabetic kidney) small; aging indication experimental. E4."},
    {"id": "pi-trt", "procedure_id": "proc-trt", "condition_id": "cond-hypogonadism",
     "evidence_grade": EG.E1,
     "evidence_summary": "RCTs and guidelines support TRT for confirmed hypogonadism with monitoring. E1."},
    {"id": "pi-apheresis-lc", "procedure_id": "proc-apheresis-longcovid", "condition_id": "cond-long-covid",
     "evidence_grade": EG.E5,
     "evidence_summary": "Mostly uncontrolled clinic series for PASC; RCTs limited. E5."},
    {"id": "pi-vns-dep", "procedure_id": "proc-vns-depression", "condition_id": "cond-trd",
     "evidence_grade": EG.E2,
     "evidence_summary": "FDA approval for chronic TRD based on long-term data; sham-controlled acute data debated. E2."},
    {"id": "pi-cryo", "procedure_id": "proc-cryotherapy", "condition_id": "cond-oa",
     "evidence_grade": EG.E4,
     "evidence_summary": "Sports recovery literature mixed; limited disease-modifying RCTs. E4."},
    # Fix dendritic: remove bad pi-dc-prostate targeting wrong condition — use a proper one
]

# Replace the mistaken PI with a clean prostate-oriented note using obesity? Better add cond-mcrpc
CONDITIONS_EVIDENCE.append(
    {"id": "cond-mcrpc", "name": "Metastatic Castration-Resistant Prostate Cancer", "icd_code": "C61",
     "description": "mCRPC; sipuleucel-T (Provenge) labeled population."}
)

PROCEDURE_INDICATIONS_FILL = [p for p in PROCEDURE_INDICATIONS_FILL if p["id"] != "pi-dc-prostate"]
PROCEDURE_INDICATIONS_FILL.append(
    {"id": "pi-dc-mcrpc", "procedure_id": "proc-dendritic-vaccine", "condition_id": "cond-mcrpc",
     "evidence_grade": EG.E1,
     "evidence_summary": "Sipuleucel-T IMPACT RCT showed overall survival benefit in mCRPC. E1 for this product/indication."}
)
# Fix thymosin to use a better condition - chronic infection not t2d
PROCEDURE_INDICATIONS_FILL = [p for p in PROCEDURE_INDICATIONS_FILL if p["id"] != "pi-thymosin"]
PROCEDURE_INDICATIONS_FILL.append(
    {"id": "pi-thymosin-hbv", "procedure_id": "proc-peptide-thymosin", "condition_id": "cond-cidp",
     "evidence_grade": EG.E3,
     "evidence_summary": "Ta1 clinical literature strongest historically in chronic viral hepatitis (international approvals); US evidence package limited. E3 for immune-adjuvant uses."}
)
# Actually cidp is wrong for thymosin - keep as general E3 on long-covid or create cond-hbv
CONDITIONS_EVIDENCE.append(
    {"id": "cond-hbv", "name": "Chronic Hepatitis B", "icd_code": "B18.1",
     "description": "Chronic HBV; historical Zadaxin/thymalfasin indication in many countries."}
)
PROCEDURE_INDICATIONS_FILL = [p for p in PROCEDURE_INDICATIONS_FILL if p["id"] != "pi-thymosin-hbv"]
PROCEDURE_INDICATIONS_FILL.append(
    {"id": "pi-thymosin-hbv", "procedure_id": "proc-peptide-thymosin", "condition_id": "cond-hbv",
     "evidence_grade": EG.E3,
     "evidence_summary": "International trials/approvals for chronic hepatitis B/C and immune adjuvant uses; quality variable by era and region. E3."}
)
# Fix chelation to not use chronic pain - use a metal toxicity condition
CONDITIONS_EVIDENCE.append(
    {"id": "cond-lead", "name": "Lead Poisoning / Heavy Metal Toxicity", "icd_code": "T56.0",
     "description": "Documented lead or heavy metal poisoning — labeled chelation population."}
)
PROCEDURE_INDICATIONS_FILL = [p for p in PROCEDURE_INDICATIONS_FILL if p["id"] != "pi-chelation"]
PROCEDURE_INDICATIONS_FILL.append(
    {"id": "pi-chelation-lead", "procedure_id": "proc-chelation", "condition_id": "cond-lead",
     "evidence_grade": EG.E1,
     "evidence_summary": "EDTA/DMSA chelation is standard for confirmed lead and selected metal poisonings. E1 for labeled toxicity; off-label 'detox' is not E1."}
)


def C(name, city=None, url=None, type_="clinic", notes=None):
    d = {"name": name, "type": type_}
    if city:
        d["city"] = city
    if url:
        d["url"] = url
    if notes:
        d["notes"] = notes
    return d


# Keyed by (procedure_id, jurisdiction_id) → list of clinic dicts
# Prefer official directories + major named centers with public URLs.
EXAMPLE_CLINICS = {
    # Psilocybin Oregon
    ("proc-psilocybin-trd", "jur-us-or"): [
        C("Oregon Psilocybin Services — Licensee Directory", url="https://psilocybin.oregon.gov/license-directory", type_="directory",
          notes="Official OHA directory of licensed service centers/facilitators (verify currently operational)."),
        C("Chariot", city="Portland, OR", url="https://www.chariotspace.com", type_="service_center"),
        C("7 Gates Sanctuary", city="Portland, OR", url="https://7gatessanctuary.com", type_="service_center"),
        C("Epic Healing Eugene (first licensed center, 2023)", city="Eugene, OR", type_="service_center",
          notes="Historically first OPS center; confirm current license status."),
    ],
    ("proc-psilocybin-eol", "jur-us-or"): [
        C("Oregon Psilocybin Services — Licensee Directory", url="https://psilocybin.oregon.gov/license-directory", type_="directory"),
    ],
    ("proc-psilocybin-trd", "jur-jm"): [
        C("MycoMeditations", city="Treasure Beach, Jamaica", url="https://www.mycomeditations.com", type_="retreat",
          notes="Long-running retreat operator; not a government medical license framework."),
    ],
    ("proc-psilocybin-trd", "jur-au"): [
        C("TGA Authorized Prescriber psychiatrists (clinic list varies)", city="Australia", type_="directory",
          notes="Access only via authorized psychiatrists under TGA framework — search RANZCP / local authorized prescribers."),
    ],
    ("proc-mdma-ptsd", "jur-au"): [
        C("TGA Authorized Prescriber pathway for MDMA-AT", city="Australia", type_="directory",
          notes="Authorized psychiatrist programs only; not walk-in clinics."),
    ],
    # Ketamine
    ("proc-ketamine-depression", "jur-us-federal"): [
        C("American Society of Ketamine Physicians clinic finder", url="https://askp.org", type_="directory"),
        C("Spravato (esketamine) certified REMS treatment centers", url="https://www.spravato.com", type_="directory",
          notes="Manufacturer locator for REMS-certified sites."),
    ],
    ("proc-ketamine-depression", "jur-us-or"): [
        C("Portland / Eugene ketamine clinics (multiple independent)", city="Oregon", type_="clinic",
          notes="Search ASKP directory; standards vary."),
    ],
    ("proc-ketamine-assisted-psychotherapy", "jur-us-federal"): [
        C("ASKP / KAP clinic directory", url="https://askp.org", type_="directory"),
    ],
    # MAID
    ("proc-maid", "jur-ca"): [
        C("Health Canada MAID information & provincial care pathways", url="https://www.canada.ca/en/health-canada/services/medical-assistance-dying.html", type_="directory"),
    ],
    ("proc-maid", "jur-ch"): [
        C("Dignitas", city="Zurich area, Switzerland", url="https://www.dignitas.ch", type_="organization"),
        C("Pegasos Swiss Association", city="Basel area", url="https://pegasos-association.com", type_="organization"),
        C("EXIT (Swiss residents)", url="https://www.exit.ch", type_="organization"),
    ],
    # CAR-T / gene
    ("proc-stem-car-t", "jur-us-federal"): [
        C("BMT InfoNet Directory of CAR T-cell Therapy Centers", url="https://bmtinfonet.org/directory-car-t-cell-therapy-centers", type_="directory"),
        C("Mayo Clinic CAR-T Cell Therapy Program", city="Rochester / multi-site", url="https://www.mayoclinic.org/departments-centers/car-t-cell-therapy-program", type_="hospital"),
        C("MD Anderson CARTOX / CAR T program", city="Houston, TX", url="https://www.mdanderson.org/treatment-options/car-t-cell-therapy.html", type_="hospital"),
        C("UCLA Health CAR T program", city="Los Angeles, CA", url="https://www.uclahealth.org/cancer/cancer-services/car-t-cell-therapy", type_="hospital"),
    ],
    ("proc-gene-crispr", "jur-us-federal"): [
        C("Authorized Casgevy treatment centers (Vertex/CRISPR locator)", url="https://www.casgevy.com", type_="directory"),
        C("NIH / ClinicalTrials.gov gene editing trials", url="https://clinicaltrials.gov", type_="directory"),
    ],
    ("proc-gene-aa9", "jur-us-federal"): [
        C("Zolgensma treatment center network (Novartis)", url="https://www.zolgensma.com", type_="directory"),
        C("Children's Hospital of Philadelphia (gene therapy programs)", city="Philadelphia, PA", url="https://www.chop.edu", type_="hospital"),
    ],
    ("proc-gene-aa9", "jur-de"): [
        C("German university SMA / gene therapy centers (e.g. via DGKJ networks)", city="Germany", type_="directory",
          notes="Referral through pediatric neurology; center list via national SMA networks."),
    ],
    ("proc-til-melanoma", "jur-us-federal"): [
        C("Amtagvi (lifileucel) authorized treatment centers", url="https://www.amtagvi.com", type_="directory"),
        C("NCI-designated cancer centers with TIL programs", url="https://www.cancer.gov", type_="directory"),
    ],
    # Switzerland psychedelics
    ("proc-lsd-anxiety", "jur-ch"): [
        C("BAG exceptional authorization treating psychiatrists", city="Switzerland", type_="directory",
          notes="Individual compassionate-use permits via Swiss Federal Office of Public Health — not walk-in."),
    ],
    # Canada SAP
    ("proc-psilocybin-trd", "jur-ca"): [
        C("TheraPsil (patient navigation / advocacy)", url="https://therapsil.ca", type_="organization"),
        C("Health Canada Special Access Programme", url="https://www.canada.ca/en/health-canada/services/drugs-health-products/special-access-programme-drugs.html", type_="directory"),
    ],
    # Mexico tourism
    ("proc-stem-msc", "jur-mx"): [
        C("COFEPRIS-registered hospital verification (required diligence)", url="https://www.gob.mx/cofepris", type_="directory",
          notes="Many Tijuana/Cancún clinics advertise MSCs — verify registration and outcomes independently."),
    ],
    ("proc-ibogaine-addiction", "jur-mx"): [
        C("GITA clinical guidelines / provider network (voluntary)", url="https://www.ibogainealliance.org", type_="directory",
          notes="Prefer medically supervised clinics with continuous cardiac monitoring; quality highly variable."),
    ],
    # IVF
    ("proc-repro-ivf", "jur-us-federal"): [
        C("SART clinic finder (US IVF clinics)", url="https://www.sartcorsonline.com", type_="directory"),
        C("CDC ART success rates", url="https://www.cdc.gov/art", type_="directory"),
    ],
    ("proc-repro-ivf", "jur-mx"): [
        C("Major private fertility centers in CDMX / Cancún / Guadalajara", city="Mexico", type_="clinic",
          notes="Prefer clinics with international accreditation (ISO/CAP) and transparent outcomes."),
    ],
    ("proc-egg-freezing", "jur-us-federal"): [
        C("SART clinic finder", url="https://www.sartcorsonline.com", type_="directory"),
    ],
    ("proc-egg-freezing", "jur-es"): [
        C("IVI / Next Fertility and other Spanish ART groups", city="Spain", type_="clinic",
          notes="Spain is a major EU fertility tourism destination — compare clinic success rates."),
    ],
    ("proc-mito-replacement", "jur-uk"): [
        C("HFEA-licensed mitochondrial donation (Newcastle program lineage)", city="UK", url="https://www.hfea.gov.uk", type_="directory",
          notes="Only HFEA-licensed clinics; primary global regulated pathway."),
    ],
    ("proc-repro-surrogacy", "jur-ca"): [
        C("Canadian Fertility & Andrology Society resources", url="https://cfas.ca", type_="directory"),
        C("Provincial parentage / surrogacy legal counsel directories", city="Canada", type_="directory"),
    ],
    # TMS / neuromodulation
    ("proc-tms-depression", "jur-us-federal"): [
        C("Clinical TMS Society provider directory", url="https://www.clinicaltmssociety.org", type_="directory"),
        C("Hospital outpatient neurostimulation programs (academic centers)", type_="hospital"),
    ],
    ("proc-tms-ocd", "jur-us-federal"): [
        C("BrainsWay / deep TMS clinic locator", url="https://www.brainsway.com", type_="directory"),
    ],
    ("proc-dbs-parkinson", "jur-us-federal"): [
        C("Parkinson's Foundation Center of Excellence directory", url="https://www.parkinson.org", type_="directory"),
        C("Mayo Clinic DBS program", url="https://www.mayoclinic.org", type_="hospital"),
    ],
    ("proc-fus-tremor", "jur-us-federal"): [
        C("Insightec Exablate treatment center locator", url="https://insightec.com", type_="directory"),
    ],
    ("proc-vns-depression", "jur-us-federal"): [
        C("LivaNova VNS Therapy depression centers", url="https://www.livanova.com", type_="directory"),
    ],
    # Proton
    ("proc-proton-therapy", "jur-us-federal"): [
        C("National Association for Proton Therapy center map", url="https://www.proton-therapy.org", type_="directory"),
        C("MD Anderson Proton Therapy Center", city="Houston, TX", url="https://www.mdanderson.org", type_="hospital"),
    ],
    ("proc-proton-therapy", "jur-de"): [
        C("Heidelberg Ion Beam Therapy Center (HIT) and other German particle centers", city="Germany", type_="hospital"),
    ],
    ("proc-proton-therapy", "jur-jp"): [
        C("Japanese particle therapy facilities (NCC, university hospitals)", city="Japan", type_="directory",
          notes="Japan has high particle-therapy density — referral via oncology."),
    ],
    # Lecanemab
    ("proc-lecanemab", "jur-us-federal"): [
        C("Leqembi infusion sites / specialty memory clinics", url="https://www.leqembi.com", type_="directory"),
        C("Alzheimer's Association trial/treatment finder", url="https://www.alz.org", type_="directory"),
    ],
    # Cannabis
    ("proc-medical-cannabis", "jur-ca"): [
        C("Health Canada licensed producers / medical document pathway", url="https://www.canada.ca/en/health-canada/services/drugs-medication/cannabis.html", type_="directory"),
    ],
    ("proc-medical-cannabis", "jur-us-ca"): [
        C("California Department of Cannabis Control license search", url="https://cannabis.ca.gov", type_="directory"),
    ],
    ("proc-medical-cannabis", "jur-de"): [
        C("German pharmacies dispensing medical cannabis (physician prescription)", city="Germany", type_="pharmacy",
          notes="Since 2024 reforms, prescribing is simpler; still physician-led."),
    ],
    ("proc-medical-cannabis", "jur-uk"): [
        C("Specialist private medical cannabis clinics (e.g. Sapphire, Alternaleaf — verify CQC)", city="UK", type_="clinic",
          notes="Private specialist Rx model; NHS rare."),
    ],
    # HBOT / FMT / PRP
    ("proc-hbot", "jur-us-federal"): [
        C("Undersea & Hyperbaric Medical Society facility resources", url="https://www.uhms.org", type_="directory"),
    ],
    ("proc-fmt", "jur-us-federal"): [
        C("OpenBiome / FDA-cleared microbiota product pathways", url="https://www.openbiome.org", type_="organization"),
        C("Academic GI programs offering FMT for rCDI", type_="hospital"),
    ],
    ("proc-prp-therapy", "jur-us-federal"): [
        C("AAOS / sports medicine clinic networks offering PRP", type_="directory",
          notes="Widely available; ask about device kit and evidence for your indication."),
    ],
    # Longevity / peptides
    ("proc-repurposed-rapamycin", "jur-us-federal"): [
        C("AgelessRx / Healthspan-type longevity telemedicine (examples)", type_="telehealth",
          notes="Verify physician licensing in your state; monitoring labs essential."),
    ],
    ("proc-metformin-longevity", "jur-us-federal"): [
        C("Primary care / longevity clinics prescribing off-label metformin", type_="clinic",
          notes="Any licensed prescriber can prescribe; not a specialty drug."),
    ],
    ("proc-nad-iv", "jur-us-federal"): [
        C("Functional medicine / IV therapy clinics (variable quality)", type_="clinic",
          notes="No FDA approval for anti-aging claims; verify sterile compounding."),
    ],
    # Switzerland Dignitas already; Prospera
    ("proc-gene-crispr", "jur-hn-prospera"): [
        C("Minicircle / Próspera biotech operators", city="Roatán, Honduras", url="https://minicircle.io", type_="clinic",
          notes="Experimental; ZEDE legal status contested — extreme diligence."),
    ],
    ("proc-stem-msc", "jur-hn-prospera"): [
        C("GARM Clinic and other Roatán regenerative operators", city="Roatán", type_="clinic",
          notes="Marketing claims vary; verify credentials and product characterization."),
    ],
    # Photoimmunotherapy Japan
    ("proc-photoimmunotherapy", "jur-jp"): [
        C("Japanese approved head & neck oncology centers offering NIR-PIT", city="Japan", type_="hospital",
          notes="Akalux/ASP-1929 pathway — specialist referral."),
    ],
    # Semaglutide
    ("proc-repurposed-semaglutide", "jur-us-federal"): [
        C("Primary care, endocrinology, and telehealth obesity clinics", type_="clinic"),
        C("Manufacturer savings / pharmacy channels (Ozempic, Wegovy, Mounjaro, Zepbound)", type_="pharmacy"),
    ],
    # SGLT2
    ("proc-sglt2-hf", "jur-us-federal"): [
        C("Cardiology / primary care (guideline-directed medical therapy)", type_="clinic"),
    ],
    # PFA
    ("proc-pef-ablation", "jur-us-federal"): [
        C("Hospital EP labs offering Farapulse / PulseSelect / Affera systems", type_="hospital",
          notes="Ask electrophysiology programs which PFA platform they use."),
    ],
    # TRT
    ("proc-trt", "jur-us-federal"): [
        C("Endocrinology / urology clinics; men's health telehealth", type_="clinic",
          notes="Prefer documented hypogonadism labs and monitoring — avoid unregulated 'TRT mills'."),
    ],
    # Ibogaine Mexico already; ayahuasca Brazil
    ("proc-ayahuasca", "jur-br"): [
        C("Santo Daime / UDV recognized religious centers", city="Brazil", type_="religious",
          notes="Religious legal framework — not medical tourism clinics."),
    ],
    # Long COVID apheresis Germany
    ("proc-apheresis-longcovid", "jur-de"): [
        C("Specialized German apheresis / nephrology clinics advertising HELP or immunoadsorption", city="Germany", type_="clinic",
          notes="Evidence for PASC still limited; demand published protocols and labs."),
    ],
    # DBS India
    ("proc-dbs-parkinson", "jur-in"): [
        C("Major neurosurgery hospitals in Delhi, Mumbai, Bangalore, Chennai", city="India", type_="hospital",
          notes="Compare surgeon DBS volume and device brands; medical tourism packages common."),
    ],
    # UK MRT already; Australia TGA already
}


def all_conditions_evidence():
    return list(CONDITIONS_EVIDENCE)


def all_indications_fill():
    seen = set()
    out = []
    for p in PROCEDURE_INDICATIONS_FILL:
        if p["id"] in seen:
            continue
        seen.add(p["id"])
        out.append(p)
    return out


def all_example_clinics():
    return dict(EXAMPLE_CLINICS)
