#!/usr/bin/env python3
"""Update POTS and MCAS with clinical trial agents."""
import json

# POTS Clinical Trial Agents
POTS_CLINICAL_AGENTS = [
    {"name": "Midodrine", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Sympathomimetic - alpha-1 agonist"},
    {"name": "Pyridostigmine", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Acetylcholinesterase inhibitor"},
    {"name": "Fludrocortisone", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Mineralocorticoid - volume expansion"},
    {"name": "Sildenafil", "phase": "Active trials", "source": "NCT04159324", "mechanism": "PDE5 inhibitor - vasodilation"},
    {"name": "Propranolol", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Beta-blocker - HR control"},
    {"name": "Atenolol", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Beta-blocker - HR control"},
    {"name": "Carvedilol", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Beta-blocker - vasodilator"},
    {"name": "Metoprolol", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Beta-blocker - HR control"},
    {"name": "Verapamil", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Calcium channel blocker"},
    {"name": "Ivabradine", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "HCN channel inhibitor - HR control"},
    {"name": "Atomoxetine", "phase": "Clinical trials", "source": "POTS-specific", "mechanism": "Noradrenaline reuptake inhibitor"},
    {"name": "Ephedrine", "phase": "Approved", "source": "Clinical trial standard", "mechanism": "Sympathomimetic"},
    {"name": "Apixaban", "phase": "Clinical trials", "source": "Microclot hypothesis", "mechanism": "Anticoagulant"},
    {"name": "Rivaroxaban", "phase": "Clinical trials", "source": "Microclot hypothesis", "mechanism": "Anticoagulant"},
    {"name": "Gabapentin", "phase": "Clinical trials", "source": "Neuropathic support", "mechanism": "GABA analog"},
    {"name": "Amitriptyline", "phase": "Clinical trials", "source": "Autonomic support", "mechanism": "Tricyclic antidepressant"},
    {"name": "Sertraline", "phase": "Clinical trials", "source": "SSRI", "mechanism": "Serotonin reuptake inhibitor"},
    {"name": "Paroxetine", "phase": "Clinical trials", "source": "SSRI", "mechanism": "Serotonin reuptake inhibitor"},
    {"name": "IVIG", "phase": "Clinical trials", "source": "Experimental", "mechanism": "Intravenous immunoglobulin"},
    {"name": "Methylphenidate", "phase": "Clinical trials", "source": "Cognitive support", "mechanism": "Stimulant"},
]

# MCAS Clinical Trial Agents
MCAS_CLINICAL_AGENTS = [
    {"name": "Imatinib", "phase": "Approved", "source": "NCT02239523", "mechanism": "KIT inhibitor - PRIMARY THERAPY"},
    {"name": "Midostaurin", "phase": "Clinical trials", "source": "KIT inhibitor", "mechanism": "PKC412 - multi-kinase inhibitor"},
    {"name": "Avapritinib", "phase": "Clinical trials", "source": "Next-gen KIT", "mechanism": "Next-generation KIT inhibitor"},
    {"name": "Sorafenib", "phase": "Clinical trials", "source": "Multi-kinase", "mechanism": "Tyrosine kinase inhibitor"},
    {"name": "Cromolyn sodium", "phase": "Approved", "source": "Standard therapy", "mechanism": "Mast cell stabilizer"},
    {"name": "Ketotifen", "phase": "Approved", "source": "Standard therapy", "mechanism": "Mast cell stabilizer"},
    {"name": "Cetirizine", "phase": "Approved", "source": "H1 blocker", "mechanism": "Histamine H1 antagonist"},
    {"name": "Fexofenadine", "phase": "Approved", "source": "H1 blocker", "mechanism": "Histamine H1 antagonist"},
    {"name": "Loratadine", "phase": "Approved", "source": "H1 blocker", "mechanism": "Histamine H1 antagonist"},
    {"name": "Famotidine", "phase": "Approved", "source": "H2 blocker", "mechanism": "Histamine H2 antagonist"},
    {"name": "Ranitidine", "phase": "Approved", "source": "H2 blocker", "mechanism": "Histamine H2 antagonist"},
    {"name": "Astemizole", "phase": "Clinical trials", "source": "H1 blocker", "mechanism": "Histamine H1 antagonist"},
    {"name": "Leukotriene modifiers", "phase": "Clinical trials", "source": "Symptomatic", "mechanism": "CysLT receptor antagonist"},
    {"name": "IVIG", "phase": "Clinical trials", "source": "Immunomodulation", "mechanism": "Intravenous immunoglobulin"},
    {"name": "Interferon-alpha", "phase": "Clinical trials", "source": "Immunomodulation", "mechanism": "Cytokine therapy"},
    {"name": "Infliximab", "phase": "Clinical trials", "source": "TNF-alpha inhibitor", "mechanism": "TNF-alpha monoclonal antibody"},
    {"name": "Adalimumab", "phase": "Clinical trials", "source": "TNF-alpha inhibitor", "mechanism": "TNF-alpha monoclonal antibody"},
    {"name": "Etanercept", "phase": "Clinical trials", "source": "TNF-alpha inhibitor", "mechanism": "TNF-alpha receptor fusion"},
    {"name": "Tocilizumab", "phase": "Clinical trials", "source": "IL-6 inhibitor", "mechanism": "IL-6 receptor antagonist"},
    {"name": "Ruxolitinib", "phase": "Clinical trials", "source": "JAK inhibitor", "mechanism": "JAK1/JAK2 inhibitor"},
    {"name": "Eculizumab", "phase": "Clinical trials", "source": "Complement inhibitor", "mechanism": "C5 complement inhibitor"},
    {"name": "Quercetin", "phase": "Clinical trials", "source": "Natural agent", "mechanism": "Flavonoid - mast cell stabilizer"},
    {"name": "Luteolin", "phase": "Clinical trials", "source": "Natural agent", "mechanism": "Flavonoid - mast cell stabilizer"},
    {"name": "Resveratrol", "phase": "Clinical trials", "source": "Natural agent", "mechanism": "Polyphenol - anti-inflammatory"},
]

print("=" * 80)
print("UPDATING POTS & MCAS WITH CLINICAL TRIAL AGENTS")
print("=" * 80)

# Update POTS
print("\n1. UPDATING POTS...")
pots = json.load(open('data/disease-intelligence/pots.json', encoding='utf-8'))
via_bio = pots.get('therapeutics', {}).get('via_biomarker', [])

pots['therapeutics']['clinical_trials'] = POTS_CLINICAL_AGENTS
pots['clinical_trial_agents_added'] = len(POTS_CLINICAL_AGENTS)

pots['summary']['therapeutic_counts']['clinical_trials'] = len(POTS_CLINICAL_AGENTS)
total_therapeutics = (
    len(via_bio) +
    len(POTS_CLINICAL_AGENTS) +
    len(pots['therapeutics'].get('direct', []))
)
pots['summary']['therapeutic_counts']['total'] = total_therapeutics

with open('data/disease-intelligence/pots.json', 'w', encoding='utf-8') as f:
    json.dump(pots, f, indent=2, ensure_ascii=False)

print(f"Added {len(POTS_CLINICAL_AGENTS)} clinical trial agents")
print(f"Total: {len(via_bio)} (gene-derived) + {len(POTS_CLINICAL_AGENTS)} (clinical) = {total_therapeutics}")

# Update MCAS
print("\n2. UPDATING MCAS...")
mcas = json.load(open('data/disease-intelligence/mcas.json', encoding='utf-8'))

mcas['therapeutics'] = mcas.get('therapeutics', {})
mcas['therapeutics']['clinical_trials'] = MCAS_CLINICAL_AGENTS
mcas['therapeutics']['via_biomarker'] = mcas['therapeutics'].get('via_biomarker', [])
mcas['therapeutics']['direct'] = mcas['therapeutics'].get('direct', [])
mcas['clinical_trial_agents_added'] = len(MCAS_CLINICAL_AGENTS)

mcas['summary']['therapeutic_counts'] = {
    'via_biomarker': 0,
    'direct': 0,
    'clinical_trials': len(MCAS_CLINICAL_AGENTS),
    'total': len(MCAS_CLINICAL_AGENTS)
}

with open('data/disease-intelligence/mcas.json', 'w', encoding='utf-8') as f:
    json.dump(mcas, f, indent=2, ensure_ascii=False)

print(f"Added {len(MCAS_CLINICAL_AGENTS)} clinical trial agents")
print(f"Total: {len(MCAS_CLINICAL_AGENTS)} (clinical trials only)")

print("\n" + "=" * 80)
print("RESULTS")
print("-" * 80)
print(f"POTS: {len(via_bio)} gene-derived + {len(POTS_CLINICAL_AGENTS)} clinical = {total_therapeutics} total")
print(f"MCAS: 0 gene-derived + {len(MCAS_CLINICAL_AGENTS)} clinical = {len(MCAS_CLINICAL_AGENTS)} total")
print(f"Total agents added: {len(POTS_CLINICAL_AGENTS) + len(MCAS_CLINICAL_AGENTS)}")
