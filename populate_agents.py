#!/usr/bin/env python3
"""
Re-populate therapeutic_agents.json cleanly for the 5 conditions.
Uses PACVS_Evidence_Map.csv as high-quality source + filtered literature + trials.
"""
import json
import csv
import glob
from datetime import datetime, timezone
from collections import defaultdict

print("Building clean therapeutic agents for the 5 conditions...")

TARGET = {
    'PACVS': 'PACVS – Post-Acute COVID-19 Vaccination Syndrome',
    'Long COVID': 'Long COVID – Post-Acute Sequelae of COVID-19',
    'ME/CFS': 'ME/CFS – Myalgic Encephalomyelitis / Chronic Fatigue Syndrome',
    'POTS': 'POTS / Dysautonomia',
    'MCAS': 'MCAS (Mast Cell Activation Syndrome)'
}

NON_THERAPEUTIC = {
    "active control", "usual care", "placebo", "wait-list", "blood sample",
    "patient questionnaires", "education and strategies intervention",
    "mindfulness skills intervention", "structured pacing",
    "multimodal intervention", "mind body intervention", "classical treatment",
    "control group", "atmospheric air", "get started", "one step at a time",
    "sodium chloride", "11c-ps13", "radio", "0.9%", "assigned interventions"
}

agents = {}

# 1. High-quality source: PACVS_Evidence_Map.csv
csv_path = 'clinical_trials/PACVS_Evidence_Map.csv'
if glob.glob(csv_path):
    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['Therapy'].strip()
            if not name: continue
            key = name.lower()
            agents[key] = {
                'Therapeutic Agent': name,
                'Primary Conditions': [TARGET['PACVS']],
                'Proposed Mechanism': row.get('Category', 'See source'),
                'Evidence Level': row.get('Evidence Level', 'Preliminary'),
                'Key Studies / References': [row.get('DOI / Source', '')] if row.get('DOI / Source') else [],
                'Ongoing Research': 'See PACVS Evidence Map',
                'Clinical Notes': row.get('Key Finding', 'Review source document.')[:400],
                'Last Updated': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                'studies': [],
                'trials': [],
                'aliases': [],
                'types': [],
                'mechanisms': [],
                'trial_types': [],
                'trial_sizes': []
            }
print(f"Loaded {len(agents)} from PACVS Evidence Map")

# 2. Clinical trials (filter to 5 conditions + real agents)
try:
    with open('clinical_trials/data/clinical_trials_current.json', encoding='utf-8') as f:
        ct_data = json.load(f)
    added = 0
    for t in ct_data.get('trials', []):
        mapped = t.get('mapped_conditions', [])
        # Map to our 5
        matched_conds = []
        for m in mapped:
            ml = m.lower()
            if 'long covid' in ml or 'pasc' in ml:
                matched_conds.append(TARGET['Long COVID'])
            elif 'me/cfs' in ml or 'chronic fatigue' in ml:
                matched_conds.append(TARGET['ME/CFS'])
            elif 'pots' in ml or 'dysautonomia' in ml:
                matched_conds.append(TARGET['POTS'])
            elif 'mcas' in ml or 'mast cell' in ml:
                matched_conds.append(TARGET['MCAS'])
            elif 'pacvs' in ml:
                matched_conds.append(TARGET['PACVS'])
        if not matched_conds:
            continue
        for agent_name in t.get('agents', []):
            if not agent_name or len(agent_name) < 3: continue
            lower = agent_name.lower()
            if any(x in lower for x in NON_THERAPEUTIC):
                continue
            key = agent_name.lower()
            if key not in agents:
                agents[key] = {
                    'Therapeutic Agent': agent_name,
                    'Primary Conditions': [],
                    'Proposed Mechanism': 'See trial',
                    'Evidence Level': 'Preliminary',
                    'Key Studies / References': [],
                    'Ongoing Research': t.get('status', '') if t.get('status','').upper() not in ['COMPLETED','TERMINATED'] else '',
                    'Clinical Notes': 'See linked trial for details and cautions.',
                    'Last Updated': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                    'studies': [],
                    'trials': [],
                    'aliases': [],
                    'types': [],
                    'mechanisms': [],
                    'trial_types': [],
                    'trial_sizes': []
                }
            ag = agents[key]
            for c in matched_conds:
                if c not in ag['Primary Conditions']:
                    ag['Primary Conditions'].append(c)
            ag['trials'].append({
                'nct_id': t['nct_id'],
                'title': t['title'][:120],
                'status': t.get('status'),
                'phase': t.get('phase'),
                'start_date': t.get('start_date'),
                'completion_date': t.get('completion_date')
            })
            if t.get('phase'): ag['trial_types'].append(t['phase'])
            if t.get('size_category'): ag['trial_sizes'].append(t['size_category'])
            added += 1
    print(f"Processed trials, added/updated agents from trials")
except Exception as e:
    print("Trials load issue:", str(e)[:80])

print(f"After trials: {len(agents)} agents")

# 3. Literature for the 5 conditions (use existing JSONs + simple extraction)
lit_map = {
    'pacvs.json': TARGET['PACVS'],
    'long-covid.json': TARGET['Long COVID'],
    'me-cfs.json': TARGET['ME/CFS']
}

# Basic agent candidates (expandable)
CANDIDATES = [
    'sirolimus', 'rapamycin', 'metformin', 'fluvoxamine', 'paxlovid', 'nac', 'n-acetylcysteine',
    'ldn', 'low-dose naltrexone', 'ivig', 'coq10', 'hb ot', 'hyperbaric', 'ivabradine',
    'midodrine', 'fludrocortisone', 'pyridostigmine', 'montelukast', 'ketotifen', 'cromolyn',
    'aspirin', 'creatine', 'nmn', 'taurine', 'l-arginine', 'l-citrulline', 'l-glutamine',
    'l-serine', 'alcar', 'lumbrokinase', 'nattokinase', 'maraviroc', 'pravastatin', 'rituximab',
    'exercise', 'pacing', 'acupuncture', 'mind body', 'cognitive', 'rehabilitation', 'probiotic',
    'vitamin d', 'thiamine', 'omega-3', 'curcumin', 'quercetin'
]

for fname, cond_name in lit_map.items():
    try:
        with open(f'data/{fname}', encoding='utf-8') as f:
            lit = json.load(f)
        for s in lit.get('studies', []):
            text = (s.get('title','') + ' ' + s.get('abstract','')).lower()
            found = []
            for cand in CANDIDATES:
                if cand in text:
                    found.append(cand)
            for fnd in found:
                norm = fnd.replace('-',' ').title()
                key = norm.lower()
                if key not in agents:
                    agents[key] = {
                        'Therapeutic Agent': norm,
                        'Primary Conditions': [],
                        'Proposed Mechanism': 'From literature abstract',
                        'Evidence Level': 'Preliminary',
                        'Key Studies / References': [f"PMID:{s.get('pmid')}"],
                        'Ongoing Research': '',
                        'Clinical Notes': 'Review full text. Potential benefit based on publication.',
                        'Last Updated': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
                        'studies': [],
                        'trials': [],
                        'aliases': [],
                        'types': [],
                        'mechanisms': [],
                        'trial_types': [],
                        'trial_sizes': []
                    }
                ag = agents[key]
                if cond_name not in ag['Primary Conditions']:
                    ag['Primary Conditions'].append(cond_name)
                ag['studies'].append({
                    'pmid': s.get('pmid'),
                    'title': s.get('title','')[:120],
                    'pub_date': s.get('pub_date'),
                    'excerpt': s.get('abstract','')[:250]
                })
    except Exception as e:
        print('Lit error', fname, ':', str(e)[:60])

print(f"After literature: {len(agents)} agents")

# Final save
final = {
    'last_updated': datetime.now(timezone.utc).isoformat(),
    'count': len(agents),
    'agents': list(agents.values())
}

with open('data/therapeutic_agents.json', 'w', encoding='utf-8') as f:
    json.dump(final, f, indent=2, ensure_ascii=False)

print(f"Saved {len(agents)} agents to data/therapeutic_agents.json")
print("Done.")
