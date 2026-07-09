"""
Curated standard-of-care and WHO-recognized therapeutic agents per NTD.
Organized by clinical stage; tagged with published vs pipeline evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

STAGES = ("vector_control", "prevention", "acute", "post_infectious")
STAGE_LABELS = {
    "vector_control": "Vector & transmission control",
    "prevention": "Prevention",
    "acute": "Acute phase",
    "post_infectious": "Post-infectious phase",
}


@dataclass
class Agent:
    drug: str
    type: str
    max_phase: int
    approved: bool
    moa: str
    source: str = "WHO EML / standard of care"
    stage: str = "acute"
    evidence: str = "published"

    def as_dict(self) -> dict:
        return {
            "drug": self.drug,
            "type": self.type,
            "max_phase": self.max_phase,
            "approved": self.approved,
            "moa": self.moa,
            "source": self.source,
            "stage": self.stage,
            "evidence": self.evidence,
            "drug_id": None,
            "target": None,
        }


def _a(
    drug,
    typ,
    phase=4,
    approved=True,
    moa="",
    source="WHO EML / standard of care",
    stage="acute",
    evidence=None,
):
    if evidence is None:
        if approved or phase >= 4:
            evidence = "published"
        elif phase >= 2:
            evidence = "pipeline"
        else:
            evidence = "preliminary"
    return Agent(drug, typ, phase, approved, moa, source, stage, evidence)


# key -> list[Agent]  (keys match ntd_registry disease keys)
SOC_THERAPEUTICS: dict[str, list[Agent]] = {
    "buruli_ulcer": [
        _a("Environmental wound care & early detection", "Prevention", stage="prevention", moa="Reduce M. ulcerans exposure; community surveillance"),
        _a("Rifampicin + clarithromycin", "Antibiotic combination", stage="acute", moa="Mycobacterial RNA polymerase / protein synthesis inhibition"),
        _a("Streptomycin + rifampicin", "Antibiotic combination", stage="acute", moa="Alternative WHO regimen"),
        _a("Physiotherapy & surgery for contractures", "Rehabilitation", stage="post_infectious", moa="Functional limitation after healing", source="WHO Buruli ulcer"),
    ],
    "chagas": [
        _a("Triatomine vector control (IRS, housing improvement)", "Vector control", stage="vector_control", moa="Reduce T. cruzi transmission", source="WHO Chagas"),
        _a("Blood/tissue screening", "Prevention", stage="prevention", moa="Prevent transfusion/transplant transmission"),
        _a("Benznidazole", "Antiparasitic", stage="acute", moa="Nitroreductase-activated trypanocidal nitroimidazole"),
        _a("Nifurtimox", "Antiparasitic", stage="acute", moa="Nitrofuran trypanocide"),
        _a("Fexinidazole", "Antiparasitic", phase=2, approved=False, stage="acute", moa="Oral nitroimidazole (investigational Chagas)", source="DNDi / clinical pipeline"),
        _a("Cardiac & digestive megasyndrome management", "Supportive", stage="post_infectious", moa="Pacemaker, surgery, symptomatic care for chronic Chagas", source="WHO Chagas"),
    ],
    "dengue": [
        _a("Aedes aegypti / albopictus source reduction", "Vector control", stage="vector_control", moa="Eliminate breeding sites; community mobilization", source="WHO dengue guidelines"),
        _a("Larvicides (temephos, Bacillus thuringiensis israelensis)", "Vector control", stage="vector_control", moa="Treat water-storage containers and habitats", source="WHO"),
        _a("Wolbachia-infected mosquito deployment", "Vector control", phase=3, approved=False, stage="vector_control", moa="Population replacement reduces dengue transmission", source="Published field trials; WHO/TDR", evidence="published"),
        _a("Personal repellents & protective clothing", "Prevention", stage="prevention", moa="Reduce Aedes exposure during outbreaks"),
        _a("Dengue tetravalent vaccine (Qdenga/TAK-003)", "Vaccine", stage="prevention", moa="Live attenuated tetravalent dengue vaccine", source="WHO / approved vaccines"),
        _a("Dengvaxia (CYD-TDV)", "Vaccine", stage="prevention", moa="Recombinant chimeric yellow fever–dengue vaccine (serostatus restrictions)", source="WHO SAGE"),
        _a("Supportive care (IV fluids, hemodynamic monitoring)", "Supportive", stage="acute", moa="No approved antiviral; fluid resuscitation for severe dengue"),
        _a("Paracetamol (avoid NSAIDs & aspirin)", "Supportive", stage="acute", moa="Fever/analgesia without bleeding risk", source="WHO dengue"),
        _a("Blood component therapy", "Supportive", stage="acute", moa="Severe dengue hemorrhage / plasma leakage"),
        _a("Graduated activity & fatigue rehabilitation", "Rehabilitation", stage="post_infectious", moa="Post-dengue fatigue syndrome management", source="Seet 2007; Garcia 2011"),
    ],
    "chikungunya": [
        _a("Aedes vector control (source reduction, larvicides)", "Vector control", stage="vector_control", moa="Same vectors as dengue; integrated control", source="WHO"),
        _a("Vimkunya (VLA1553) vaccine", "Vaccine", phase=3, approved=True, stage="prevention", moa="Live-attenuated chikungunya vaccine (FDA 2025)", source="FDA / published trials"),
        _a("Travel & exposure precautions", "Prevention", stage="prevention", moa="Repellents, outbreak avoidance"),
        _a("Supportive care (rest, fluids)", "Supportive", stage="acute", moa="No approved antiviral; symptomatic management"),
        _a("NSAIDs for acute arthralgia", "Analgesic", stage="acute", moa="First-line acute joint pain", source="WHO chikungunya"),
        _a("Methotrexate / short corticosteroids", "Immunomodulator", stage="post_infectious", moa="Chronic inflammatory rheumatism refractory to NSAIDs", source="Published cohorts"),
        _a("Hydroxychloroquine", "Antimalarial", phase=2, approved=False, stage="post_infectious", moa="Investigational for chronic arthralgia", source="Clinical trials", evidence="pipeline"),
        _a("Physiotherapy & joint rehabilitation", "Rehabilitation", stage="post_infectious", moa="Persistent arthralgia and disability"),
    ],
    "dracunculiasis": [
        _a("Guinea worm case containment & water filtration", "Vector control", stage="vector_control", moa="Prevent Cyclops ingestion; pipe filters", source="WHO GWEP"),
        _a("Safe water supply education", "Prevention", stage="prevention", moa="Near-eradication via behavioral prevention"),
        _a("Manual worm extraction & wound care", "Supportive", phase=0, approved=False, stage="acute", moa="No chemotherapeutic agent; gradual removal", source="WHO GWEP"),
    ],
    "echinococcosis": [
        _a("Dog deworming & slaughter hygiene", "Vector control", stage="vector_control", moa="Break Echinococcus granulosus cycle", source="WHO"),
        _a("Albendazole", "Anthelmintic", stage="acute", moa="Microtubule inhibitor; cysticidal adjunct to PAIR/surgery"),
        _a("Mebendazole", "Anthelmintic", stage="acute", moa="Alternative benzimidazole"),
        _a("PAIR / surgery", "Procedure", stage="acute", moa="Percutaneous aspiration-injection-reaspiration or resection"),
        _a("Long-term cyst surveillance", "Supportive", stage="post_infectious", moa="Recurrence monitoring after treatment", source="WHO echinococcosis"),
    ],
    "foodborne_trematodiases": [
        _a("Food safety & cooking education", "Prevention", stage="prevention", moa="Prevent raw-fish / aquatic plant ingestion"),
        _a("Praziquantel", "Anthelmintic", stage="acute", moa="Opisthorchiasis, clonorchiasis, paragonimiasis"),
        _a("Triclabendazole", "Anthelmintic", stage="acute", moa="Fascioliasis (liver fluke)"),
        _a("Cholangiocarcinoma surveillance (Opisthorchis/Clonorchis)", "Oncology follow-up", stage="post_infectious", moa="Chronic biliary sequelae", source="IARC; WHO"),
    ],
    "hat": [
        _a("Tsetse fly control (traps, insecticide)", "Vector control", stage="vector_control", moa="Reduce Glossina transmission", source="WHO HAT"),
        _a("Pentamidine", "Antiparasitic", stage="acute", moa="First-stage T. b. gambiense (hemolymphatic)"),
        _a("Suramin", "Antiparasitic", stage="acute", moa="First-stage T. b. rhodesiense"),
        _a("Eflornithine (DFMO)", "Antiparasitic", stage="acute", moa="Second-stage T. b. gambiense (CNS)"),
        _a("Melarsoprol", "Antiparasitic", stage="acute", moa="Second-stage (both subspecies; toxic arsenical)"),
        _a("Fexinidazole", "Antiparasitic", stage="acute", moa="Oral regimen for T. b. gambiense (first- and second-stage)", source="WHO 2019"),
        _a("Nifurtimox–eflornithine combination (NECT)", "Antiparasitic", stage="acute", moa="Second-stage T. b. gambiense"),
        _a("Neuropsychiatric rehabilitation", "Rehabilitation", stage="post_infectious", moa="Sleep-cycle & cognitive sequelae post-CNS disease", source="WHO HAT"),
    ],
    "leishmaniasis": [
        _a("Sandfly vector control (IRS, bed nets)", "Vector control", stage="vector_control", moa="Reduce Phlebotomus / Lutzomyia transmission", source="WHO leishmaniasis"),
        _a("Liposomal amphotericin B", "Antiparasitic", stage="acute", moa="First-line visceral leishmaniasis (South Asia, Africa)"),
        _a("Miltefosine", "Antiparasitic", stage="acute", moa="Oral alkyl phospholipid for VL and CL"),
        _a("Paromomycin", "Antiparasitic", stage="acute", moa="Aminoglycoside for VL (combination regimens)"),
        _a("Pentavalent antimonials (meglumine antimoniate)", "Antiparasitic", stage="acute", moa="Historic first-line; resistance in parts of India"),
        _a("Sodium stibogluconate", "Antiparasitic", stage="acute", moa="Pentavalent antimonial"),
        _a("PKDL management (liposomal amphotericin B, miltefosine)", "Antiparasitic", stage="post_infectious", moa="Post-kala-azar dermal leishmaniasis after VL cure", source="WHO; Zijlstra 2003"),
    ],
    "leprosy": [
        _a("Contact tracing & BCG in high-risk contacts", "Prevention", stage="prevention", moa="Reduce transmission in endemic settings", source="WHO leprosy"),
        _a("Rifampicin", "Antibiotic", stage="acute", moa="MDT backbone"),
        _a("Dapsone", "Antibiotic", stage="acute", moa="MDT component"),
        _a("Clofazimine", "Antibiotic", stage="acute", moa="MDT component; anti-inflammatory"),
        _a("Ofloxacin / minocycline / clarithromycin", "Antibiotic", phase=3, stage="acute", moa="Single-dose rifapentine-based regimens (investigational simplification)", source="WHO trials"),
        _a("Reaction management (prednisolone, thalidomide for ENL)", "Immunomodulator", stage="post_infectious", moa="Type-1 and ENL reactions; neuropathy care", source="WHO leprosy"),
    ],
    "lymphatic_filariasis": [
        _a("Mosquito vector control", "Vector control", stage="vector_control", moa="Reduce Culex / Anopheles / Aedes transmission", source="WHO LF"),
        _a("Ivermectin + albendazole", "Anthelmintic combination", stage="prevention", moa="Mass drug administration (W. bancrofti, Brugia)"),
        _a("Diethylcarbamazine (DEC)", "Anthelmintic", stage="prevention", moa="Alternative MDA (Loa loa–free areas)"),
        _a("Doxycycline (anti-Wolbachia)", "Antibiotic", stage="acute", moa="Targets endosymbiont in filarial worms"),
        _a("Lymphoedema management (hygiene, compression)", "Rehabilitation", stage="post_infectious", moa="Chronic elephantiasis / hydrocele care", source="WHO LF morbidity management"),
    ],
    "mycetoma": [
        _a("Footwear & wound protection", "Prevention", stage="prevention", moa="Reduce traumatic inoculation in endemic areas"),
        _a("Itraconazole", "Antifungal", stage="acute", moa="Eumycetoma (fungal)"),
        _a("Ketoconazole", "Antifungal", stage="acute", moa="Alternative azole"),
        _a("Amoxicillin–clavulanate + gentamicin", "Antibiotic combination", stage="acute", moa="Actinomycetoma (bacterial)"),
        _a("Surgical debridement & amputation (advanced)", "Surgery", stage="post_infectious", moa="Chronic destructive disease", source="WHO mycetoma"),
    ],
    "noma": [
        _a("Nutrition & oral hygiene programs", "Prevention", stage="prevention", moa="Malnutrition is major risk factor", source="WHO / MSF"),
        _a("Amoxicillin–clavulanate", "Antibiotic", stage="acute", moa="Acute necrotizing infection"),
        _a("Metronidazole", "Antibiotic", stage="acute", moa="Anaerobic coverage"),
        _a("Nutritional rehabilitation + reconstructive surgery", "Supportive", stage="post_infectious", moa="Survivor reconstruction", source="WHO / MSF protocols"),
    ],
    "onchocerciasis": [
        _a("Simulium vector control (larviciding)", "Vector control", stage="vector_control", moa="Blackfly breeding-site treatment", source="WHO onchocerciasis"),
        _a("Ivermectin", "Anthelmintic", stage="prevention", moa="Microfilaricidal; annual/biannual MDA"),
        _a("Moxidectin", "Anthelmintic", stage="prevention", moa="Alternative microfilaricide (FDA-approved)"),
        _a("Skin & eye disease management", "Supportive", stage="post_infectious", moa="Chronic dermatitis, vision rehabilitation", source="WHO"),
    ],
    "rabies": [
        _a("Dog & wildlife vaccination (oral rabies vaccine)", "Vector control", stage="vector_control", moa="Population immunity in reservoir species", source="WHO rabies"),
        _a("Pre-exposure prophylaxis (PrEP)", "Vaccine", stage="prevention", moa="High-risk occupational / travel vaccination"),
        _a("Rabies vaccine (post-exposure)", "Vaccine", stage="prevention", moa="Active immunization after exposure"),
        _a("Rabies immunoglobulin (RIG)", "Immunoglobulin", stage="prevention", moa="Passive immunity for category III exposures"),
        _a("Wound washing (soap, povidone-iodine)", "Prevention", stage="prevention", moa="WHO PEP protocol first step", source="WHO rabies guidelines"),
        _a("Palliative supportive care (symptomatic)", "Supportive", phase=0, approved=False, stage="acute", moa="Uniformly fatal once neurological symptoms appear", source="WHO"),
    ],
    "scabies": [
        _a("Permethrin 5% cream", "Topical scabicide", stage="acute", moa="First-line topical treatment"),
        _a("Ivermectin (oral)", "Anthelmintic", stage="acute", moa="Mass drug administration and crusted scabies"),
        _a("Benzyl benzoate 25%", "Topical scabicide", stage="acute", moa="Alternative topical"),
        _a("Household/contact treatment", "Prevention", stage="prevention", moa="Simultaneous treatment of contacts"),
        _a("Secondary bacterial infection treatment", "Antibiotic", stage="post_infectious", moa="Post-streptococcal sequelae prevention", source="Romani 2015 Lancet ID"),
    ],
    "schistosomiasis": [
        _a("Snail control & safe water access", "Vector control", stage="vector_control", moa="Reduce Bulinus / Biomphalaria intermediate hosts", source="WHO schistosomiasis"),
        _a("Praziquantel", "Anthelmintic", stage="prevention", moa="Broad schistosomicide; MDA backbone"),
        _a("Oxamniquine", "Anthelmintic", stage="acute", moa="S. mansoni (limited use)"),
        _a("Chronic fibrosis & bladder cancer surveillance", "Oncology follow-up", stage="post_infectious", moa="Hepatic/urogenital sequelae", source="Colley 2014 Lancet"),
    ],
    "sth": [
        _a("Sanitation & hygiene (WASH)", "Prevention", stage="prevention", moa="Reduce soil contamination with infective eggs/larvae", source="WHO STH"),
        _a("Albendazole", "Anthelmintic", stage="prevention", moa="Ascariasis, hookworm, trichuriasis MDA"),
        _a("Mebendazole", "Anthelmintic", stage="prevention", moa="Alternative benzimidazole"),
        _a("Ivermectin", "Anthelmintic", stage="acute", moa="Strongyloides; combination MDA"),
        _a("Moxidectin", "Anthelmintic", phase=2, approved=False, stage="prevention", moa="Hookworm (investigational MDA)", source="Clinical trials", evidence="pipeline"),
        _a("Iron supplementation & nutritional rehab", "Supportive", stage="post_infectious", moa="Chronic anaemia and growth impairment in children", source="WHO STH"),
    ],
    "snakebite": [
        _a("Habitat modification & protective footwear", "Prevention", stage="prevention", moa="Reduce human–snake contact", source="WHO snakebite strategy"),
        _a("Species-specific antivenom", "Antivenom", stage="acute", moa="Immunoglobulin neutralization of venom toxins"),
        _a("Supportive care (airway, fluids, antitetanus)", "Supportive", stage="acute", moa="Antivenom is definitive; supportive adjuncts", source="WHO snakebite strategy"),
        _a("CKD, amputation & pain rehabilitation", "Rehabilitation", stage="post_infectious", moa="Chronic post-envenoming disability", source="Waiddyanatha 2022"),
    ],
    "cysticercosis": [
        _a("Taenia solium control (pig management, sanitation)", "Vector control", stage="vector_control", moa="Break pig–human transmission cycle", source="WHO"),
        _a("Albendazole", "Anthelmintic", stage="acute", moa="Cysticidal for parenchymal neurocysticercosis"),
        _a("Praziquantel", "Anthelmintic", stage="acute", moa="Alternative cysticidal (with caution)"),
        _a("Antiepileptic drugs (e.g. carbamazepine)", "Anticonvulsant", stage="post_infectious", moa="Seizure control in neurocysticercosis-related epilepsy"),
    ],
    "trachoma": [
        _a("Facial cleanliness & environmental improvement (F&E)", "Prevention", stage="prevention", moa="WHO SAFE strategy — hygiene/environment arm"),
        _a("Azithromycin (mass drug administration)", "Antibiotic", stage="prevention", moa="WHO SAFE strategy — antibiotic arm"),
        _a("Tetracycline eye ointment", "Antibiotic", stage="acute", moa="Alternative topical treatment"),
        _a("Trichiasis surgery", "Surgical", stage="post_infectious", moa="SAFE surgery component for trichiasis", source="WHO trachoma"),
    ],
    "yaws": [
        _a("Azithromycin (single dose)", "Antibiotic", stage="acute", moa="WHO yaws eradication strategy"),
        _a("Benzathine penicillin G", "Antibiotic", stage="acute", moa="Alternative single-dose injection"),
        _a("Active case finding & contact treatment", "Prevention", stage="prevention", moa="Interrupt transmission", source="WHO yaws eradication"),
        _a("Bone & cartilage lesion management", "Supportive", stage="post_infectious", moa="Late destructive yaws (gangosa)", source="WHO"),
    ],
    # --- Supplemental viral diseases (not WHO NTD list) ---
    "measles": [
        _a("MMR / measles-rubella vaccination", "Vaccine", stage="prevention", moa="Live attenuated vaccine; herd immunity backbone", source="WHO measles elimination"),
        _a("Vitamin A supplementation (endemic/deficient settings)", "Micronutrient", stage="prevention", moa="Reduces mortality and complications in children", source="WHO measles"),
        _a("Supportive care (fluids, fever control)", "Supportive", stage="acute", moa="No antiviral standard of care"),
        _a("Vitamin A (acute illness)", "Micronutrient", stage="acute", moa="WHO-recommended twice-daily dosing in severe measles", source="WHO"),
        _a("Antibiotics for bacterial superinfection", "Antibiotic", stage="acute", moa="Pneumonia, otitis media complications"),
        _a("SSPE surveillance & supportive neurology", "Supportive", stage="post_infectious", moa="Subacute sclerosing panencephalitis (rare late sequela)", source="WHO; Campbell 2019"),
        _a("Bronchiectasis & pulmonary rehab", "Rehabilitation", stage="post_infectious", moa="Post-measles chronic lung disease in survivors", source="Published case series"),
    ],
    "yellow_fever": [
        _a("Aedes / Haemagogus vector control", "Vector control", stage="vector_control", moa="Urban & sylvatic transmission reduction", source="WHO yellow fever"),
        _a("Yellow fever 17D vaccine", "Vaccine", stage="prevention", moa="Live attenuated; single dose lifelong immunity in most", source="WHO EML"),
        _a("Supportive care (avoid aspirin/NSAIDs)", "Supportive", stage="acute", moa="No specific antiviral; hepatorenal support"),
        _a("Liver failure & hemorrhage management", "Supportive", stage="acute", moa="Severe viscerotropic disease"),
        _a("Post-vaccine adverse event monitoring", "Surveillance", stage="post_infectious", moa="Rare YEL-AND / YEL-AVD after vaccination", source="WHO"),
    ],
    "zika": [
        _a("Aedes vector control (integrated with dengue)", "Vector control", stage="vector_control", moa="Reduce Aedes aegypti/albopictus populations", source="WHO Zika"),
        _a("Pregnancy exposure avoidance & condom use", "Prevention", stage="prevention", moa="Prevent congenital Zika syndrome", source="WHO"),
        _a("Supportive care (rest, fluids, analgesia)", "Supportive", stage="acute", moa="No approved antiviral"),
        _a("Guillain-Barré syndrome management (IVIG, plasmapheresis)", "Immunotherapy", stage="post_infectious", moa="Post-infectious neuropathy", source="WHO; Cao-Lormeau 2016"),
        _a("Congenital Zika syndrome multidisciplinary care", "Rehabilitation", stage="post_infectious", moa="Microcephaly, developmental support", source="WHO PAHO"),
    ],
}


def get_soc(key: str) -> list[dict]:
    return [a.as_dict() for a in SOC_THERAPEUTICS.get(key, [])]


def normalize_name(name: str) -> str:
    return (name or "").upper().replace("–", "-").strip()


def infer_evidence(d: dict) -> str:
    if d.get("evidence"):
        return d["evidence"]
    src = (d.get("source") or "").lower()
    if "open targets" in src:
        return "pipeline"
    if d.get("approved") or (d.get("max_phase") or 0) >= 4:
        return "published"
    if (d.get("max_phase") or 0) >= 2:
        return "pipeline"
    return "preliminary"