"""
Curated standard-of-care and WHO-recognized therapeutic agents per NTD.
Prioritized over Open Targets clinical-pipeline hits in pipeline.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Agent:
    drug: str
    type: str
    max_phase: int
    approved: bool
    moa: str
    source: str = "WHO EML / standard of care"

    def as_dict(self) -> dict:
        return {
            "drug": self.drug,
            "type": self.type,
            "max_phase": self.max_phase,
            "approved": self.approved,
            "moa": self.moa,
            "source": self.source,
            "drug_id": None,
            "target": None,
        }


def _a(drug, typ, phase=4, approved=True, moa="", source="WHO EML / standard of care"):
    return Agent(drug, typ, phase, approved, moa, source)


# key -> list[Agent]  (keys match ntd_registry.NTD.key)
SOC_THERAPEUTICS: dict[str, list[Agent]] = {
    "buruli_ulcer": [
        _a("Rifampicin + clarithromycin", "Antibiotic combination", moa="Mycobacterial RNA polymerase / protein synthesis inhibition"),
        _a("Streptomycin + rifampicin", "Antibiotic combination", moa="Alternative WHO regimen"),
    ],
    "chagas": [
        _a("Benznidazole", "Antiparasitic", moa="Nitroreductase-activated trypanocidal nitroimidazole"),
        _a("Nifurtimox", "Antiparasitic", moa="Nitrofuran trypanocide"),
        _a("Fexinidazole", "Antiparasitic", phase=2, approved=False, moa="Oral nitroimidazole (investigational Chagas)", source="DNDi / clinical pipeline"),
    ],
    "dengue": [
        _a("Supportive care (fluids, analgesia)", "Supportive", moa="No disease-specific antiviral; fluid resuscitation for severe dengue"),
        _a("Dengue tetravalent vaccine (Qdenga/TAK-003)", "Vaccine", moa="Live attenuated tetravalent dengue vaccine", source="WHO / approved vaccines"),
        _a("Dengvaxia (CYD-TDV)", "Vaccine", moa="Recombinant chimeric yellow fever–dengue vaccine (serostatus restrictions)", source="WHO SAGE"),
    ],
    "chikungunya": [
        _a("Supportive care (NSAIDs, rest)", "Supportive", moa="No approved antiviral; symptomatic arthritis management"),
        _a("Chloroquine / hydroxychloroquine", "Antimalarial", phase=2, approved=False, moa="Investigational for chronic arthralgia", source="Clinical trials"),
        _a("Vimkunya (VLA1553) vaccine", "Vaccine", phase=3, approved=False, moa="Live-attenuated chikungunya vaccine (FDA 2025)", source="Clinical pipeline"),
    ],
    "dracunculiasis": [
        _a("No chemotherapeutic agent", "Prevention", phase=0, approved=False, moa="Manual worm extraction + water filtration; near-eradication", source="WHO GWEP"),
    ],
    "echinococcosis": [
        _a("Albendazole", "Anthelmintic", moa="Microtubule inhibitor; cysticidal adjunct to PAIR/surgery"),
        _a("Mebendazole", "Anthelmintic", moa="Alternative benzimidazole"),
        _a("Praziquantel", "Anthelmintic", moa="Limited role; species-dependent"),
    ],
    "foodborne_trematodiases": [
        _a("Praziquantel", "Anthelmintic", moa="Opisthorchiasis, clonorchiasis, paragonimiasis"),
        _a("Triclabendazole", "Anthelmintic", moa="Fascioliasis (liver fluke)"),
    ],
    "hat": [
        _a("Pentamidine", "Antiparasitic", moa="First-stage T. b. gambiense (hemolymphatic)"),
        _a("Suramin", "Antiparasitic", moa="First-stage T. b. rhodesiense"),
        _a("Eflornithine (DFMO)", "Antiparasitic", moa="Second-stage T. b. gambiense (CNS)"),
        _a("Melarsoprol", "Antiparasitic", moa="Second-stage (both subspecies; toxic arsenical)"),
        _a("Fexinidazole", "Antiparasitic", moa="Oral regimen for T. b. gambiense (first- and second-stage)", source="WHO 2019"),
        _a("Nifurtimox–eflornithine combination (NECT)", "Antiparasitic", moa="Second-stage T. b. gambiense"),
    ],
    "leishmaniasis": [
        _a("Liposomal amphotericin B", "Antiparasitic", moa="First-line visceral leishmaniasis (South Asia, Africa)"),
        _a("Miltefosine", "Antiparasitic", moa="Oral alkyl phospholipid for VL and CL"),
        _a("Paromomycin", "Antiparasitic", moa="Aminoglycoside for VL (combination regimens)"),
        _a("Pentavalent antimonials (meglumine antimoniate)", "Antiparasitic", moa="Historic first-line; resistance in parts of India"),
        _a("Sodium stibogluconate", "Antiparasitic", moa="Pentavalent antimonial"),
    ],
    "leprosy": [
        _a("Rifampicin", "Antibiotic", moa="MDT backbone"),
        _a("Dapsone", "Antibiotic", moa="MDT component"),
        _a("Clofazimine", "Antibiotic", moa="MDT component; anti-inflammatory"),
        _a("Ofloxacin / minocycline / clarithromycin", "Antibiotic", phase=3, moa="Single-dose rifapentine-based regimens (investigational simplification)", source="WHO trials"),
    ],
    "lymphatic_filariasis": [
        _a("Ivermectin + albendazole", "Anthelmintic combination", moa="Mass drug administration (W. bancrofti, Brugia)"),
        _a("Diethylcarbamazine (DEC)", "Anthelmintic", moa="Alternative MDA (Loa loa–free areas)"),
        _a("Doxycycline (anti-Wolbachia)", "Antibiotic", moa="Targets endosymbiont in filarial worms"),
    ],
    "mycetoma": [
        _a("Itraconazole", "Antifungal", moa="Eumycetoma (fungal)"),
        _a("Ketoconazole", "Antifungal", moa="Alternative azole"),
        _a("Amoxicillin–clavulanate + gentamicin", "Antibiotic combination", moa="Actinomycetoma (bacterial)"),
    ],
    "noma": [
        _a("Amoxicillin–clavulanate", "Antibiotic", moa="Acute necrotizing infection"),
        _a("Metronidazole", "Antibiotic", moa="Anaerobic coverage"),
        _a("Nutritional rehabilitation + surgery", "Supportive", moa="Survivor reconstruction", source="WHO / MSF protocols"),
    ],
    "onchocerciasis": [
        _a("Ivermectin", "Anthelmintic", moa="Microfilaricidal; annual/biannual MDA"),
        _a("Moxidectin", "Anthelmintic", moa="Alternative microfilaricide (FDA-approved)"),
    ],
    "rabies": [
        _a("Rabies vaccine (post-exposure)", "Vaccine", moa="Active immunization after exposure"),
        _a("Rabies immunoglobulin (RIG)", "Immunoglobulin", moa="Passive immunity for category III exposures"),
        _a("Wound washing + rabies vaccine", "Prevention bundle", moa="WHO PEP protocol", source="WHO rabies guidelines"),
    ],
    "scabies": [
        _a("Permethrin 5% cream", "Topical scabicide", moa="First-line topical treatment"),
        _a("Ivermectin (oral)", "Anthelmintic", moa="Mass drug administration and crusted scabies"),
        _a("Benzyl benzoate 25%", "Topical scabicide", moa="Alternative topical"),
    ],
    "schistosomiasis": [
        _a("Praziquantel", "Anthelmintic", moa="Broad schistosomicide; MDA backbone"),
        _a("Oxamniquine", "Anthelmintic", moa="S. mansoni (limited use)"),
    ],
    "sth": [
        _a("Albendazole", "Anthelmintic", moa="Ascariasis, hookworm, trichuriasis MDA"),
        _a("Mebendazole", "Anthelmintic", moa="Alternative benzimidazole"),
        _a("Ivermectin", "Anthelmintic", moa="Strongyloides; combination MDA"),
        _a("Moxidectin", "Anthelmintic", moa="Hookworm (investigational MDA)", source="Clinical trials"),
    ],
    "snakebite": [
        _a("Species-specific antivenom", "Antivenom", moa="Immunoglobulin neutralization of venom toxins"),
        _a("Supportive care (airway, fluids, antitetanus)", "Supportive", moa="No single drug; antivenom is definitive", source="WHO snakebite strategy"),
    ],
    "cysticercosis": [
        _a("Albendazole", "Anthelmintic", moa="Cysticidal for parenchymal neurocysticercosis"),
        _a("Praziquantel", "Anthelmintic", moa="Alternative cysticidal (with caution)"),
        _a("Antiepileptic drugs (e.g. carbamazepine)", "Anticonvulsant", moa="Seizure control in neurocysticercosis-related epilepsy"),
    ],
    "trachoma": [
        _a("Azithromycin (mass drug administration)", "Antibiotic", moa="WHO SAFE strategy — antibiotic arm"),
        _a("Tetracycline eye ointment", "Antibiotic", moa="Alternative topical MDA"),
        _a("Trichiasis surgery", "Surgical", phase=4, moa="SAFE surgery component for trichiasis", source="WHO trachoma"),
    ],
    "yaws": [
        _a("Azithromycin (single dose)", "Antibiotic", moa="WHO yaws eradication strategy"),
        _a("Benzathine penicillin G", "Antibiotic", moa="Alternative single-dose injection"),
    ],
}


def get_soc(key: str) -> list[dict]:
    return [a.as_dict() for a in SOC_THERAPEUTICS.get(key, [])]


def normalize_name(name: str) -> str:
    return (name or "").upper().replace("–", "-").strip()