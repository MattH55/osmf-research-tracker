import json
from datetime import datetime, timezone

with open('data/therapeutic_agents.json', encoding='utf-8') as f:
    data = json.load(f)

# Improved LLM-style Clinical Notes (cautious, practical, evidence-based)
improved_notes = {
    "Creatine monohydrate": "Creatine has emerging RCT support for mental fatigue and cognition in Long COVID/PASC (effect sizes notable but small n). Typical studied dose: 5g/day (sometimes loading). Generally well tolerated; monitor for GI upset or water retention. May be reasonable to trial in fatigued patients with low dietary creatine intake. More data needed.",
    
    "Taurine": "Taurine levels appear depleted in PASC and correlate with severity. Supplementation is being tested in RCTs. Doses in studies often 1-3g/day. Appears safe; theoretical benefit for mitochondrial function and autonomic regulation. Consider in patients with low taurine status. Evidence still early.",
    
    "Low-dose naltrexone (LDN)": "LDN is commonly used off-label for ME/CFS and Long COVID fatigue at 1-4.5mg nightly. Multiple ongoing trials (e.g. LIFT). May modulate glial activation and reduce pain/fatigue. Generally very safe at low dose; start low and titrate. Avoid in patients on opioids. Promising preliminary data across post-viral syndromes.",
    
    "IVIg (intravenous immunoglobulin)": "Used in selected patients with POTS/autonomic dysfunction and evidence of immune dysregulation. Dosing regimens vary (e.g. 1-2 g/kg cycles). Expensive, requires infusion, risk of headache, thrombosis, anaphylaxis. Reserved for clear autoimmune phenotypes after specialist evaluation. Some positive observational data.",
    
    "Lumbrokinase": "Fibrinolytic enzyme studied for microclot dissolution in Long COVID/ME-CFS. Typical dose in protocols: 20-40mg 2-3x/day on empty stomach. Theoretical benefit for hypercoagulable states. Limited published human data in these conditions. Bleeding risk is low but monitor in patients with coagulopathy.",
    
    "Ivabradine": "Used for inappropriate sinus tachycardia and POTS in Long COVID. Reduces heart rate without lowering blood pressure. Doses often 2.5-7.5mg BID. Can cause luminous phenomena (visual). Good option when beta-blockers are not tolerated. Supported by observational + nested RCT data.",
    
    "Pyridostigmine": "Acetylcholinesterase inhibitor studied for autonomic dysfunction, especially hyperadrenergic POTS. Doses 30-60mg TID. May improve hemodynamics and fatigue. Side effects: cholinergic (GI, sweating, bradycardia). Useful in select patients; one RCT showed benefit.",
    
    "Fluvoxamine": "SSRI with sigma-1 receptor activity; studied for early COVID and some Long COVID symptoms. Doses in studies 50-100mg. Potential anti-inflammatory effects. Well tolerated but can cause nausea, insomnia, drug interactions (CYP1A2). Preliminary evidence; not first-line for core symptoms.",
    
    "Maraviroc": "CCR5 antagonist being studied in Long COVID (often with statins). Theoretical benefit for persistent immune activation. Dosing typically 300mg BID. Monitor liver enzymes. Very early data; experimental use only in research settings currently.",
    
    "Paxlovid (Nirmatrelvir + Ritonavir)": "Being evaluated for prevention/treatment of Long COVID symptoms. Standard 5-day antiviral course. Significant drug interactions (ritonavir). Renal adjustment needed. Some trials show symptom benefit in certain phenotypes. Use per current guidelines for acute infection; Long COVID role still under study.",
    
    "Sirolimus (low-dose)": "mTOR inhibitor explored for immune modulation in Long COVID. Low doses (e.g. 0.5-2mg) studied. Immunosuppressive risks require careful monitoring (infections, lipids, mouth ulcers). Interesting mechanistic rationale but limited high-quality data so far.",
    
    "Metformin": "Studied for prevention of Long COVID when used during acute infection (COVID-OUT trial). Also being looked at for ongoing symptoms. Usual doses 500-2000mg/day. GI side effects common; B12 monitoring long-term. Generally safe and cheap. Mixed but intriguing data.",
    
    "Fluvoxamine Maleate 100 Mg": "See Fluvoxamine above. Same profile.",
    
    "Ivabradine + Coordinated Care": "Combination approach in autonomic recovery protocols. See Ivabradine notes; coordinated care may include pacing, PT, etc. Synergistic potential in POTS phenotypes.",
    
    "Tirzepatide": "GLP-1/GIP agonist in trial for Long COVID (possible metabolic and anti-inflammatory effects). Weekly injection, titrated dosing. Significant GI side effects and cost. Early stage; metabolic benefits in overweight patients may be relevant. Watch for trial results.",
    
    "Montelukast Tablets Oral Treatment": "Leukotriene antagonist sometimes used for respiratory and inflammatory symptoms in Long COVID. 10mg daily. Generally well tolerated. Limited specific data; more commonly used for asthma/allergies. May help MCAS-overlap patients.",
    
    "N-Acetylcysteine (NAC)": "Antioxidant studied for glutathione support and symptom relief in Long COVID/ME-CFS. Doses 600-1800mg/day divided. Safe profile; possible GI upset. Some mechanistic rationale and small studies. Reasonable to consider, especially if oxidative stress suspected.",
    
    "Montelukast": "See Montelukast Tablets note above.",
    
    "Pyridostigmine Bromide": "See Pyridostigmine above. Same medication.",
    
    "Creatine": "See Creatine monohydrate above.",
    
    "Rituximab": "B-cell depleting monoclonal antibody studied in ME/CFS (mixed results historically). Used in autoimmune contexts. Serious infection risk, infusion reactions. Reserved for clear autoimmune cases under specialist care. Several ME/CFS trials exist with variable outcomes.",
    
    "Coenzyme Q10 (CoQ10)": "Mitochondrial support supplement commonly used in fatigue syndromes. Doses 100-300mg/day (ubiquinol form preferred). Very safe. Limited but positive data in ME/CFS for fatigue and oxidative stress. Often tried as part of mitochondrial support stacks."
}

updated = 0
for a in data['agents']:
    name = a.get('Therapeutic Agent')
    if name in improved_notes:
        a['Clinical Notes'] = improved_notes[name]
        updated += 1

data['last_updated'] = datetime.now(timezone.utc).isoformat()

with open('data/therapeutic_agents.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f'Updated Clinical Notes for {updated} agents.')
print('Data saved.')
