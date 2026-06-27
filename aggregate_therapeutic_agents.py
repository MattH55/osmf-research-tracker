#!/usr/bin/env python3
"""
Therapeutic Agents Aggregator Agent

Scans:
- PubMed literature data (data/*.json)
- Clinical Trials data (clinical_trials/data/*.json)

Extracts, normalizes, and aggregates information about therapeutic agents
being studied for PACVS, Long COVID/PASC, ME/CFS, etc.

Outputs:
- data/therapeutic_agents.json (structured aggregate)
- Optionally generates static HTML or works with agents.html

Run: python aggregate_therapeutic_agents.py
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any
from llm_agent_prompts import get_clinical_notes_prompt

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
CLINICAL_DIR = BASE_DIR / "clinical_trials" / "data"
OUT_FILE = DATA_DIR / "therapeutic_agents.json"

# Canonical condition categories (collapse synonyms)
CANONICAL_CATEGORIES = [
    "Long COVID",
    "PACVS",
    "ME/CFS",
    "Gulf War Illness",
    "Lyme",
    "MCAS",
    "POTS",
    "Other Post-Viral (Post-infectious cough, Q-fever fatigue syndrome, Post-dengue fatigue, Chikungunya post-infectious, Parvovirus B19 GBS, Mycoplasma pneumoniae neurological, Herpes encephalitis sequelae, RIME, etc.)"
]

CONDITION_NORMALIZE_MAP = {
    "Long COVID": ["long covid", "pasc", "post-acute sequelae", "long covid / pasc", "pasc / long covid", "long covid fatigue", "long covid treatment", "long covid prevention", "long covid cognition", "long covid / me-cfs"],
    "PACVS": ["pacvs", "pacs", "post-acute covid vaccination", "vax", "longvax", "pacvs / longvax", "pacs/pacvs", "post vaccine syndrome"],
    "ME/CFS": ["me/cfs", "myalgic encephalomyelitis", "chronic fatigue syndrome", "me-cfs"],
    "Gulf War Illness": ["gulf war", "gwi", "gulf war illness"],
    "Lyme": ["lyme", "ptlds", "post-treatment lyme", "chronic lyme"],
    "MCAS": ["mcas", "mast cell activation", "mastocytosis", "mcas phenotype", "mast cell"],
    "POTS": ["pots", "dysautonomia", "orthostatic", "pots / long", "pots (hyperadrenergic)", "postural orthostatic tachycardia"],
    "Other Post-Viral (Post-infectious cough, Q-fever fatigue syndrome, Post-dengue fatigue, Chikungunya post-infectious, Parvovirus B19 GBS, Mycoplasma pneumoniae neurological, Herpes encephalitis sequelae, RIME, etc.)": ["post-infectious", "q-fever", "chikungunya", "dengue", "parvovirus", "mycoplasma", "herpes", "ebv", "cmv", "rime", "guillain", "hemophagocytic"]
}

def normalize_condition(raw: str) -> str:
    if not raw:
        return "Other Post-Viral (Post-infectious cough, Q-fever fatigue syndrome, Post-dengue fatigue, Chikungunya post-infectious, Parvovirus B19 GBS, Mycoplasma pneumoniae neurological, Herpes encephalitis sequelae, RIME, etc.)"
    r = raw.lower().strip()
    for canon, keywords in CONDITION_NORMALIZE_MAP.items():
        if any(kw in r for kw in keywords):
            return canon
    # fallback bucket
    if any(x in r for x in ["post", "infectious", "viral"]):
        return "Other Post-Viral (Post-infectious cough, Q-fever fatigue syndrome, Post-dengue fatigue, Chikungunya post-infectious, Parvovirus B19 GBS, Mycoplasma pneumoniae neurological, Herpes encephalitis sequelae, RIME, etc.)"
    return raw

# Enrichment for therapeutic agents (PubChem, safety, dosing from studies/trials)
# Expand this map for more agents as data is reviewed. Fallbacks use name-based PubChem search + note.
AGENT_ENRICH = {
    "Paxlovid (Nirmatrelvir/Ritonavir)": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/155903259",
        "Safety": "Strong CYP3A4 inhibitor (ritonavir component) → many drug interactions. Renal dose adjustment required. Common: dysgeusia, diarrhea. Not recommended in severe hepatic impairment.",
        "Dosing": "Nirmatrelvir 300 mg + ritonavir 100 mg BID for 5 days (standard); some Long COVID trials used similar 5-day courses."
    },
    "N-Acetylcysteine (NAC)": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/12035",
        "Safety": "Excellent safety profile. GI upset (nausea, vomiting, diarrhea) at high doses. Rare bronchospasm with inhalation. Safe in pregnancy at standard doses.",
        "Dosing": "600–1800 mg/day divided doses (e.g. 600 mg TID); durations in studies 4–12 weeks."
    },
    "Low-dose naltrexone (LDN)": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/5360515",
        "Safety": "Very safe at 1–4.5 mg. Avoid with opioids (blocks effect, may precipitate withdrawal). Start low (0.5 mg) and titrate to minimize vivid dreams/insomnia.",
        "Dosing": "1–4.5 mg at bedtime; titrate from 0.5 mg over weeks; ongoing trials use 4.5 mg for 8–16+ weeks."
    },
    "Metformin": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/4091",
        "Safety": "GI side effects (diarrhea, nausea) common initially. Risk of B12 deficiency long-term; lactic acidosis rare (avoid in severe renal/hepatic disease, contrast).",
        "Dosing": "500–2000 mg/day (extended release often better tolerated); prevention trials used during acute infection ~14 days; treatment studies 8–12+ weeks."
    },
    "Fluvoxamine": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/3406",
        "Safety": "Nausea, insomnia, somnolence; significant CYP1A2 and CYP2C19 interactions. Avoid in combination with thioridazine, pimozide. Monitor for serotonin syndrome if combined with other serotonergics.",
        "Dosing": "50–100 mg/day (often 100 mg); short courses (10–15 days) in early studies; some PASC protocols 4–8 weeks."
    },
    "Rituximab": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/5104",
        "Safety": "Infusion reactions, serious infections (including PML risk), hepatitis B reactivation, hypogammaglobulinemia. Requires specialist oversight, screening, monitoring.",
        "Dosing": "Typical rheumatology regimens 1000 mg IV x2 (2 weeks apart) or 375 mg/m² weekly x4; ME/CFS trials used similar; repeat as needed."
    },
    "Creatine monohydrate": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/586",
        "Safety": "Generally safe. Possible weight gain (water), GI upset, muscle cramps. Caution in renal disease; ensure hydration.",
        "Dosing": "5 g daily (some protocols 20 g/day loading 5–7 days then 5 g); 8–24 weeks in cognitive/fatigue RCTs."
    },
    "Ivabradine": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/132999",
        "Safety": "Bradycardia, visual phosphenes (luminous phenomena), headache. Contraindicated in sick sinus, severe hypotension, acute decompensated HF. Monitor HR.",
        "Dosing": "2.5–7.5 mg twice daily; titrate to HR; durations in POTS/autonomic studies 4–12 weeks or longer."
    },
    "Pyridostigmine": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/4991",
        "Safety": "Cholinergic side effects (GI cramping, diarrhea, salivation, sweating, bradycardia). Avoid in asthma, mechanical obstruction. Overdose risk cholinergic crisis.",
        "Dosing": "30–60 mg TID (sometimes 30 mg); titrate; study durations often 4–8 weeks for hemodynamic assessment."
    },
    "Coenzyme Q10 (CoQ10)": {
        "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/5281915",
        "Safety": "Very safe; mild GI upset rare. May interact with warfarin (monitor INR). Ubiquinol form preferred for absorption.",
        "Dosing": "100–300 mg/day (often 200 mg); 8–12+ weeks in fatigue studies."
    }
}

def enrich_agent(name: str) -> dict:
    base = AGENT_ENRICH.get(name, {})
    if not base:
        safe_name = name.split('(')[0].strip().replace(' ', '%20')
        base = {
            "PubChem": f"https://pubchem.ncbi.nlm.nih.gov/#query={safe_name}",
            "Safety": "Limited specific safety data in these populations. Review full prescribing information and consult specialist. Many agents used off-label or investigational.",
            "Dosing": "See linked studies/trials for reported doses and durations; typical protocols vary widely."
        }
    return base

# Focused scope for literature/trial loading (expanded)
TARGET_CONDITIONS = [
    "PACVS – Post-Acute COVID-19 Vaccination Syndrome",
    "Long COVID – Post-Acute Sequelae of COVID-19",
    "ME/CFS – Myalgic Encephalomyelitis / Chronic Fatigue Syndrome",
    "POTS / Dysautonomia",
    "MCAS (Mast Cell Activation Syndrome)",
    "Gulf War Illness",
    "Lyme / PTLDS",
    "Other Post-Viral"
]

CONDITION_KEYWORDS = {
    "PACVS – Post-Acute COVID-19 Vaccination Syndrome": ["pacvs", "post-acute covid vaccination", "post acute covid vaccination", "vaccine long covid", "post vaccine syndrome"],
    "Long COVID – Post-Acute Sequelae of COVID-19": ["long covid", "pasc", "post-acute sequelae of sars-cov-2", "post acute covid syndrome"],
    "ME/CFS – Myalgic Encephalomyelitis / Chronic Fatigue Syndrome": ["me/cfs", "myalgic encephalomyelitis", "chronic fatigue syndrome"],
    "POTS / Dysautonomia": ["pots", "postural orthostatic tachycardia syndrome", "dysautonomia"],
    "MCAS (Mast Cell Activation Syndrome)": ["mcas", "mast cell activation syndrome", "mast cell activation"],
    "Gulf War Illness": ["gulf war", "gwi", "gulf war illness"],
    "Lyme / PTLDS": ["lyme", "ptlds", "post-treatment lyme"],
    "Other Post-Viral": ["post-infectious", "q-fever", "chikungunya", "dengue post", "parvovirus", "mycoplasma post", "herpes encephalitis", "rime"]
}

# Filter out non-therapeutic "agents"
NON_THERAPEUTIC = {"active control", "usual care", "placebo", "wait-list", "blood sample", "patient questionnaires", "education and strategies intervention", "mindfulness skills intervention", "structured pacing", "multimodal intervention", "mind body intervention", "classical treatment", "control group", "atmospheric air", "education and strategies", "get started", "one step at a time", "sodium chloride", "11c-ps13", "radio", "0.9%"}

# Strong normalization map for known relevant agents in these diseases
AGENT_ALIASES = {
    "sirolimus": "Sirolimus (low-dose Rapamycin)",
    "rapamycin": "Sirolimus (low-dose Rapamycin)",
    "low dose sirolimus": "Sirolimus (low-dose Rapamycin)",
    "low-dose sirolimus": "Sirolimus (low-dose Rapamycin)",
    "nac": "N-Acetylcysteine (NAC)",
    "n-acetylcysteine": "N-Acetylcysteine (NAC)",
    "n acetylcysteine": "N-Acetylcysteine (NAC)",
    "metformin": "Metformin",
    "fluvoxamine": "Fluvoxamine",
    "guanfacine": "Guanfacine",
    "ivig": "Intravenous Immunoglobulin (IVIG)",
    "intravenous immunoglobulin": "Intravenous Immunoglobulin (IVIG)",
    "ldn": "Low-Dose Naltrexone (LDN)",
    "low dose naltrexone": "Low-Dose Naltrexone (LDN)",
    "low-dose naltrexone": "Low-Dose Naltrexone (LDN)",
    "paxlovid": "Paxlovid (Nirmatrelvir + Ritonavir)",
    "nirmatrelvir": "Paxlovid (Nirmatrelvir + Ritonavir)",
    "coq10": "Coenzyme Q10 (CoQ10)",
    "coenzyme q10": "Coenzyme Q10 (CoQ10)",
    "ubiquinone": "Coenzyme Q10 (CoQ10)",
    "methylene blue": "Methylene Blue",
    "bc 007": "BC 007 (Aptamer)",
    "bc007": "BC 007 (Aptamer)",
    "hyperbaric oxygen": "Hyperbaric Oxygen Therapy (HBOT)",
    "hbot": "Hyperbaric Oxygen Therapy (HBOT)",
    "vitamin b1": "Thiamine (Vitamin B1)",
    "thiamine": "Thiamine (Vitamin B1)",
}

# Known candidate agents (helps discovery)
KNOWN_AGENTS = list(AGENT_ALIASES.keys()) + [
    "sirolimus", "metformin", "fluvoxamine", "paxlovid", "ivig",
    "ldn", "naltrexone", "guanfacine", "nac", "coq10", "methylene blue",
    "bc007", "rapamycin", "hydroxychloroquine", "ivermectin", "azithromycin",
    "montelukast", "atovaquone", "probenecid", "arnica", "curcumin", "quercetin",
    "low dose naltrexone", "iv immunoglobulin", "hyperbaric", "thiamine", "vitamin d",
    "omega 3", "curcumin", "quercetin", "melatonin", "statins", "ace inhibitors"
]

# Therapeutic keywords to identify promising studies for LLM extraction
THERAPEUTIC_KEYWORDS = [
    "treatment", "therapy", "efficacy", "administered", "treated with", 
    "intervention", "trial of", "use of", "supplementation with", "repurposed",
    "drug", "medication", "supplement", "agent", "protocol"
]

# Classification tags
TYPE_KEYWORDS = {
    "Drug (Pharmaceutical)": ["sirolimus", "rapamycin", "metformin", "fluvoxamine", "paxlovid", "azithromycin", "hydroxychloroquine", "ivermectin", "naltrexone", "tirzepatide", "statins"],
    "Supplement / Nutraceutical": ["nac", "coq10", "thiamine", "vitamin", "curcumin", "quercetin", "omega", "melatonin"],
    "Medical Device": ["device", "hyperbaric", "hbot", "hi-ox", "pascal", "pro2", "vagus", "vr", "virtual reality"],
    "Behavioral / Protocol / Exercise": ["pacing", "rehabilitation", "exercise", "mind body", "mindfulness", "self-management", "education", "acupuncture", "chiropractic", "intervention", "active control"],
    "Biologic / Immunotherapy": ["ivig", "immunoglobulin"],
}

MECHANISM_TAGS = {
    "Metabolic / Mitochondrial": ["metabolic", "mitochondria", "mitochondrial", "lactate", "energy", "fat oxidation", "glycolysis", "coq10"],
    "Immunomodulatory": ["immune", "immunomodulat", "sirolimus", "rapamycin", "ivig", "immunoglobulin", "ldn", "naltrexone"],
    "Antiviral / Persistence": ["persistence", "viral reservoir", "antiviral", "paxlovid"],
    "Neurological / Autonomic": ["autonomic", "dysautonomia", "pots", "brain fog", "cognitive", "vagus"],
    "Anti-inflammatory": ["anti-inflammatory", "inflammation", "nf-kb", "fluvoxamine"],
    "Repurposed Drug": ["repurposed", "off-label"],
}

def normalize_agent(name: str) -> str:
    """Return canonical name for an agent."""
    name = name.lower().strip()
    # Remove common fluff
    name = re.sub(r'\s*\(.*?\)\s*$', '', name)
    name = re.sub(r'\s+', ' ', name)
    for alias, canonical in AGENT_ALIASES.items():
        if alias in name:
            return canonical
    # Title case fallback
    return name.title()

def extract_agents_from_text(text: str) -> List[str]:
    """Improved heuristic extraction from title or abstract."""
    text_lower = text.lower()
    found = set()
    for candidate in KNOWN_AGENTS:
        if candidate in text_lower:
            found.add(normalize_agent(candidate))
    return sorted(found)

def is_therapeutic_study(title: str, abstract: str) -> bool:
    """Quick filter: is this study likely discussing a therapeutic intervention?"""
    text = (title + " " + abstract).lower()
    return any(kw in text for kw in THERAPEUTIC_KEYWORDS)

def classify_intervention(name: str, context: str = "", trial_phase: str = None, trial_size: str = None, primary_purpose: str = None, enrollment_type: str = None, sponsor_type: str = None) -> tuple:
    """Classify an intervention by type and mechanism tags. Extended with trial attributes."""
    text = (name + " " + context).lower()
    types = []
    for tag, kws in TYPE_KEYWORDS.items():
        if any(kw in text for kw in kws):
            types.append(tag)
    if not types:
        types = ["Other / Unclassified"]

    mechanisms = []
    for tag, kws in MECHANISM_TAGS.items():
        if any(kw in text for kw in kws):
            mechanisms.append(tag)
    if not mechanisms:
        mechanisms = ["Unknown / General"]

    # Add trial-specific tags if provided (for the agent)
    trial_tags = []
    if trial_phase and trial_phase != "N/A":
        trial_tags.append(trial_phase)
    if trial_size:
        trial_tags.append(trial_size)
    if primary_purpose and primary_purpose != "N/A":
        trial_tags.append(f"Primary Purpose: {primary_purpose.title()}")
    if enrollment_type and enrollment_type != "N/A":
        trial_tags.append(f"Enrollment: {enrollment_type.title()}")
    if sponsor_type and sponsor_type != "Unknown":
        sponsor_label = sponsor_type.replace("_", " ").title()
        trial_tags.append(f"Sponsor Type: {sponsor_label}")

    return types, mechanisms, trial_tags

def determine_evidence_level(num_studies: int, num_trials: int, has_high_phase: bool = False) -> str:
    """Standardized Evidence Level based on data volume and quality."""
    if has_high_phase or (num_trials >= 2 and num_studies >= 5):
        return "Moderate"
    elif num_trials >= 1 or num_studies >= 3:
        return "Preliminary"
    elif num_studies >= 1:
        return "Anecdotal"
    else:
        return "Theoretical"

def load_literature() -> List[Dict[str, Any]]:
    """Load all PubMed studies, limited to the 5 target conditions."""
    studies = []
    for f in DATA_DIR.glob("*.json"):
        data = json.load(open(f, encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        file_cond = data.get("condition", "")
        for s in data.get("studies", []):
            text = (s.get("title", "") + " " + s.get("abstract", "")).lower()
            matched = []
            for cond_name, kws in CONDITION_KEYWORDS.items():
                if any(kw in text for kw in kws) or cond_name.lower() in file_cond.lower():
                    matched.append(cond_name)
            if matched:
                studies.append({
                    "source": "pubmed",
                    "pmid": s.get("pmid"),
                    "title": s.get("title", ""),
                    "abstract": s.get("abstract", ""),
                    "pub_date": s.get("pub_date"),
                    "journal": s.get("journal"),
                    "conditions": matched,
                    "source_page": data.get("key", ""),
                })
    return studies

def load_trials() -> List[Dict[str, Any]]:
    """Load clinical trials data, limited to target conditions."""
    trials = []
    f = CLINICAL_DIR / "clinical_trials_current.json"
    if f.exists():
        data = json.load(open(f, encoding="utf-8"))
        for t in data.get("trials", []):
            mapped = t.get("mapped_conditions", [])
            # Only keep if intersects with our 5 (flexible match)
            keep = False
            for m in mapped:
                ml = m.lower()
                for tc in TARGET_CONDITIONS:
                    tcl = tc.lower()
                    if "long covid" in ml and "long covid" in tcl:
                        keep = True
                    elif "me/cfs" in ml or "chronic fatigue" in ml:
                        if "me/cfs" in tcl or "chronic fatigue" in tcl:
                            keep = True
                    elif "pots" in ml or "dysautonomia" in ml:
                        if "pots" in tcl or "dysautonomia" in tcl:
                            keep = True
                    elif "mcas" in ml or "mast cell" in ml:
                        if "mcas" in tcl or "mast cell" in tcl:
                            keep = True
                    elif "pacvs" in ml:
                        if "pacvs" in tcl:
                            keep = True
            if keep or not mapped:  # keep if no mapped but to be strict, or for demo
                trials.append({
                    "source": "clinicaltrials",
                    "nct_id": t.get("nct_id"),
                    "title": t.get("title", ""),
                    "status": t.get("status"),
                    "phase": t.get("phase"),
                    "agents": t.get("agents", []),
                    "mapped_conditions": mapped,
                    "size_category": t.get("size_category"),
                    "primary_purpose": t.get("primary_purpose"),
                    "enrollment_type": t.get("enrollment_type"),
                    "sponsor_type": t.get("sponsor_type"),
                    "start_date": t.get("start_date", "Unknown"),
                    "completion_date": t.get("completion_date", "Unknown"),
                    "primary_completion_date": t.get("primary_completion_date", "Unknown"),
                    "last_updated": t.get("last_updated", "Unknown"),
                })
    return trials

def load_pacvs_evidence_csv() -> List[Dict[str, Any]]:
    """Load high-quality PACVS evidence map as additional source for agents."""
    csv_path = BASE_DIR / 'clinical_trials' / 'PACVS_Evidence_Map.csv'
    entries = []
    if csv_path.exists():
        import csv
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append({
                    'source': 'pacvs_evidence_map',
                    'Therapy': row.get('Therapy', '').strip(),
                    'Primary Condition': row.get('Primary Condition', '').strip(),
                    'Category': row.get('Category', '').strip(),
                    'Evidence Level': row.get('Evidence Level', '').strip(),
                    'Key Finding': row.get('Key Finding', '').strip(),
                    'DOI / Source': row.get('DOI / Source', '').strip(),
                })
    return entries


# =============================================================================
# LLM PROMPT FOR BETTER AGENT EXTRACTION (Task 1 improvement)
# =============================================================================

LLM_AGENT_EXTRACTION_SYSTEM = """You are a precise medical research assistant specializing in post-viral syndromes (PACVS, Long COVID/PASC, ME/CFS).

Extract all therapeutic agents (drugs, supplements, biologics, devices with therapeutic intent, or protocols) explicitly tested or discussed as treatment in the provided paper abstract or title.

Return ONLY valid JSON in this exact format:
{
  "agents": [
    {
      "name": "Normalized name (e.g. 'Sirolimus (low-dose)' or 'N-Acetylcysteine (NAC)')",
      "confidence": "high|medium|low",
      "excerpt": "Short quote from the text where it is mentioned as a treatment"
    }
  ]
}

Rules:
- Only include things being used as potential treatments/therapies.
- Normalize names using common generic names + important qualifiers.
- Ignore diagnostic tests, biomarkers, or questionnaires unless they are the intervention.
- If no clear therapeutic agents, return empty "agents" array.
"""

def get_llm_prompt_for_study(study: dict) -> str:
    """Generate a ready-to-paste prompt for an LLM (Grok, Claude, GPT, etc.)."""
    text = f"Title: {study.get('title', '')}\n\nAbstract: {study.get('abstract', '')[:2500]}"
    return f"""{LLM_AGENT_EXTRACTION_SYSTEM}

Input study:
{text}

Return only the JSON."""


def parse_llm_agent_output(json_text: str) -> List[dict]:
    """Helper to safely parse LLM JSON output for agents."""
    try:
        data = json.loads(json_text)
        return data.get("agents", [])
    except Exception:
        return []

def aggregate(llm_prepare: bool = False, llm_results_file: str = None):
    print("Loading literature...")
    lit = load_literature()
    print(f"  {len(lit)} studies")

    print("Loading clinical trials...")
    trials = load_trials()
    print(f"  {len(trials)} trials")

    agent_map: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "canonical_name": "",
        "aliases": set(),
        "conditions": set(),
        "studies": [],
        "trials": [],
        "types": set(),
        "mechanisms": set(),
        "trial_types": set(),  # e.g. Phase 2, Phase 3
        "trial_sizes": set(),  # e.g. Small Trial, Large Trial
        "total_mentions": 0,
    })

    # Process literature with improved therapeutic filtering
    therapeutic_studies = []
    for study in lit:
        text = f"{study['title']} {study['abstract']}"
        if not is_therapeutic_study(study['title'], study['abstract']):
            continue
        extracted = extract_agents_from_text(text)
        if extracted:
            therapeutic_studies.append(study)
            for agent in extracted:
                if agent.lower().strip() in NON_THERAPEUTIC:
                    continue
                rec = agent_map[agent]
                rec["canonical_name"] = agent
                rec["aliases"].add(agent)
                for c in study.get("conditions", []):
                    rec["conditions"].add(normalize_condition(c))
                rec["studies"].append({
                    "pmid": study["pmid"],
                    "title": study["title"][:140],
                    "pub_date": study.get("pub_date"),
                    "excerpt": study["abstract"][:300] + "..." if study.get("abstract") else "",
                    "source_page": study.get("source_page", ""),
                })
                types, mechs, _ = classify_intervention(agent, study.get("title", "") + " " + study.get("abstract", ""))
                rec["types"].update(types)
                rec["mechanisms"].update(mechs)
                rec["total_mentions"] += 1

    if llm_prepare:
        print(f"\n🔬 LLM Preparation Mode")
        print(f"Found {len(therapeutic_studies)} studies that appear to discuss treatments.")
        print("Generating prompts for better agent extraction...")

        prompts = []
        for study in therapeutic_studies[:30]:  # limit to avoid too much output
            prompt = get_llm_prompt_for_study(study)
            prompts.append({
                "pmid": study["pmid"],
                "title": study["title"][:100],
                "prompt": prompt
            })

        out_path = DATA_DIR / "llm_agent_prompts.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2)
        print(f"✅ Saved {len(prompts)} LLM prompts to {out_path}")
        print("   → Feed these to Grok / Claude / GPT and save the JSON responses.")
        print("   → Then run with --ingest-llm llm_agent_prompts_results.json")
        return

    # Ingest LLM results if provided (improves extraction quality)
    if llm_results_file:
        print(f"\n🧠 Ingesting LLM results from {llm_results_file} ...")
        try:
            llm_data = json.load(open(llm_results_file, encoding="utf-8"))
            for item in llm_data:
                pmid = item.get("pmid")
                llm_agents = parse_llm_agent_output(item.get("llm_output", "{}"))
                for ag in llm_agents:
                    agent = normalize_agent(ag.get("name", ""))
                    if not agent:
                        continue
                    rec = agent_map[agent]
                    rec["canonical_name"] = agent
                    rec["aliases"].add(agent)
                    # We would need to re-match the study, for simplicity we note it
                    rec["studies"].append({
                        "pmid": pmid,
                        "title": "[LLM extracted] " + ag.get("excerpt", "")[:100],
                        "pub_date": "",
                        "excerpt": ag.get("excerpt", ""),
                    })
                    rec["total_mentions"] += 1
            print("   LLM results merged.")
        except Exception as e:
            print(f"   Failed to ingest LLM results: {e}")

    # Process trials (these have pre-extracted agents)
    skip_agents = set(NON_THERAPEUTIC) | {"wait-list", "blood sample", "patient questionnaires", "control group", "classical treatment", "atmospheric air", "education and strategies intervention", "mindfulness skills intervention", "structured pacing", "multimodal intervention", "mind body intervention", "active control", "usual care", "exercise", "acupuncture", "beet", "nitrate", "pet/ct", "ml per", "course", "intention", "protocol"}
    for t in trials:
        for raw_agent in t.get("agents", []):
            if raw_agent.lower().strip() in skip_agents:
                continue
            agent = normalize_agent(raw_agent)
            rec = agent_map[agent]
            rec["canonical_name"] = agent
            for c in t.get("mapped_conditions", []):
                rec["conditions"].add(normalize_condition(c))
            rec["trials"].append({
                "nct_id": t["nct_id"],
                "title": t["title"][:140],
                "status": t.get("status"),
                "phase": t.get("phase"),
                "size_category": t.get("size_category"),
                "start_date": t.get("start_date", "Unknown"),
                "completion_date": t.get("completion_date", "Unknown"),
                "primary_completion_date": t.get("primary_completion_date", "Unknown"),
                "last_updated": t.get("last_updated", "Unknown"),
            })
            types, mechs, trial_tags = classify_intervention(
                agent, 
                t.get("title", ""), 
                trial_phase=t.get("phase"),
                trial_size=t.get("size_category"),
                primary_purpose=t.get("primary_purpose"),
                enrollment_type=t.get("enrollment_type"),
                sponsor_type=t.get("sponsor_type")
            )
            rec["types"].update(types)
            rec["mechanisms"].update(mechs)
            for tt in trial_tags:
                if "Primary Purpose" in tt or "Enrollment" in tt or "Sponsor Type" in tt:
                    # add to mechanisms or separate, but for now merge into mechanisms for display
                    rec["mechanisms"].add(tt)
                else:
                    if "PHASE" in tt.upper() or "Trial" in tt:
                        rec["trial_types"].add(tt)
                    else:
                        rec["trial_sizes"].add(tt)
            phase = t.get("phase", "")
            if phase and phase != "N/A":
                rec["trial_types"].add(phase)
            if t.get("size_category"):
                rec["trial_sizes"].add(t["size_category"])
            rec["total_mentions"] += 1

    # Process PACVS Evidence Map CSV (authoritative source for PACVS)
    csv_entries = load_pacvs_evidence_csv()
    print(f'  Processing {len(csv_entries)} entries from PACVS Evidence Map')
    for entry in csv_entries:
        raw = entry.get('Therapy', '')
        if not raw or raw.lower().strip() in NON_THERAPEUTIC:
            continue
        agent = normalize_agent(raw)
        rec = agent_map[agent]
        rec["canonical_name"] = agent
        # Primary condition from CSV
        pc = entry.get('Primary Condition', '')
        if pc:
            rec["conditions"].add(normalize_condition(pc))
        # Evidence Level from CSV
        ev = entry.get('Evidence Level', '')
        if ev:
            rec["Evidence Level"] = ev
        # Key Finding for studies/references
        finding = entry.get('Key Finding', '')
        if finding:
            rec["studies"].append({
                "title": finding[:150],
                "pub_date": "",
                "excerpt": finding,
                "source": "PACVS Evidence Map"
            })
        # DOI
        doi = entry.get('DOI / Source', '')
        if doi:
            if "Key Studies / References" not in rec or not isinstance(rec.get("Key Studies / References"), list):
                rec["Key Studies / References"] = []
            rec["Key Studies / References"].append(doi)
        rec["total_mentions"] += 1

    # Finalize
    results = []
    for name, rec in sorted(agent_map.items()):
        num_studies = len(rec["studies"])
        num_trials = len(rec["trials"])
        has_high_phase = any("3" in t.get("phase", "") or "4" in t.get("phase", "") for t in rec["trials"])
        evidence = determine_evidence_level(num_studies, num_trials, has_high_phase)

        # Ongoing Research: active/non-completed trials
        ongoing = [tr for tr in rec["trials"] if tr.get("status", "").upper() not in ["COMPLETED", "TERMINATED", "WITHDRAWN", "SUSPENDED"]]
        ongoing_str = ", ".join([tr["nct_id"] for tr in ongoing[:3]]) if ongoing else "None currently listed"

        # Key references: top studies
        key_refs = [f"PMID:{s['pmid']}" for s in rec["studies"][:3] if s.get("pmid")]

        # Basic clinical notes (can be expanded manually later)
        notes = "Review full texts and consult specialists. Many agents are off-label or experimental in these conditions."

        # Normalize conditions into canonical buckets (collapse synonyms)
        norm_conditions = sorted({normalize_condition(c) for c in rec["conditions"]})

        # Enrich with PubChem, safety, dosing
        enrich = enrich_agent(rec["canonical_name"])

        results.append({
            "Therapeutic Agent": rec["canonical_name"],
            "Primary Conditions": norm_conditions,
            "Proposed Mechanism": ", ".join(sorted(rec["mechanisms"])[:4]) or "Not specified",
            "Evidence Level": evidence,
            "Key Studies / References": key_refs or ["See linked studies"],
            "Ongoing Research": ongoing_str,
            "Clinical Notes": notes,
            "Last Updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            # New enriched fields for agents page
            "PubChem": enrich.get("PubChem", ""),
            "Safety": enrich.get("Safety", ""),
            "Dosing": enrich.get("Dosing", ""),
            # Keep internal for UI
            "aliases": sorted(rec["aliases"]),
            "studies": rec["studies"][:5],
            "trials": rec["trials"][:5],
            "total_mentions": rec["total_mentions"],
            "types": sorted(rec["types"]) or ["Other / Unclassified"],
            "mechanisms": sorted(rec["mechanisms"]) or ["Unknown / General"],
            "trial_types": sorted(rec["trial_types"]) or [],
            "trial_sizes": sorted(rec["trial_sizes"]) or [],
        })

    # Save JSON
    OUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "count": len(results),
            "agents": results
        }, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Aggregated {len(results)} therapeutic agents")
    print(f"   Saved to {OUT_FILE}")

    # Also update the HTML viewer timestamp (simple touch)
    html_viewer = BASE_DIR / "agents.html"
    if html_viewer.exists():
        print("   agents.html will reflect the new data on next load.")

    # Print top agents for quick view
    print("\nTop agents by mentions:")
    for a in sorted(results, key=lambda x: -x.get("total_mentions", 0))[:8]:
        print(f"  - {a.get('Therapeutic Agent', a.get('name', 'Unknown'))}: {a.get('total_mentions', 0)} mentions, {len(a.get('trials', []))} trials")

    # NEW: Support for LLM-generated Clinical Notes
    if llm_prepare:
        # already handled above for agents extraction
        pass
    # The prepare-clinical-notes will be handled if user wants prompts for notes


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Therapeutic Agents Aggregator with optional LLM step")
    parser.add_argument("--llm-prepare", action="store_true", help="Prepare prompts for LLM agent extraction")
    parser.add_argument("--ingest-llm", metavar="FILE", help="Ingest JSON file containing LLM outputs")
    parser.add_argument("--prepare-clinical-notes", action="store_true", help="Prepare LLM prompts to generate Clinical Notes for current agents")
    parser.add_argument("--ingest-clinical-notes", metavar="FILE", help="Ingest JSON with LLM-generated Clinical Notes and update data")
    args = parser.parse_args()

    if args.prepare_clinical_notes:
        # Prepare prompts for clinical notes
        with open(OUT_FILE) as f:
            current = json.load(f)
        prompts = []
        for agent in current.get('agents', []):
            p = get_clinical_notes_prompt(agent)
            prompts.append({
                "Therapeutic Agent": agent.get('Therapeutic Agent', agent.get('name')),
                "prompt": p
            })
        outp = DATA_DIR / "llm_clinical_notes_prompts.json"
        with open(outp, "w", encoding="utf-8") as f:
            json.dump(prompts, f, indent=2)
        print(f"✅ Saved {len(prompts)} prompts for Clinical Notes to {outp}")
        print("   Use an LLM to generate notes and save as list of {'Therapeutic Agent': , 'clinical_notes': '...' }")
        exit(0)

    if args.ingest_clinical_notes:
        with open(args.ingest_clinical_notes) as f:
            notes_data = json.load(f)
        with open(OUT_FILE) as f:
            current = json.load(f)
        notes_map = {item.get('Therapeutic Agent'): item.get('clinical_notes') for item in notes_data}
        updated = 0
        for a in current.get('agents', []):
            key = a.get('Therapeutic Agent', a.get('name'))
            if key in notes_map and notes_map[key]:
                a['Clinical Notes'] = notes_map[key]
                updated += 1
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
        print(f"✅ Updated Clinical Notes for {updated} agents from {args.ingest_clinical_notes}")
        exit(0)

    aggregate(llm_prepare=args.llm_prepare, llm_results_file=args.ingest_llm)