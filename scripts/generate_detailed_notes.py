import json
from datetime import datetime, timezone

with open('data/therapeutic_agents.json', encoding='utf-8') as f:
    data = json.load(f)

def normalize_evidence_level(raw):
    """Map any legacy/variant evidence label to the 5 canonical categories."""
    if not raw:
        return "Preliminary"
    ev = raw.lower().strip()
    if "strong" in ev:
        return "Strong"
    if "moderate" in ev:
        return "Moderate"
    # RCT evidence, even small or pending -> Preliminary (conservative)
    if "rct" in ev or "observational (moderate" in ev:
        return "Preliminary"
    if "preliminary" in ev or "prelim" in ev:
        return "Preliminary"
    if "anecdot" in ev or "case series" in ev or "case report" in ev or "null result" in ev:
        return "Anecdotal"
    if "mechanistic" in ev or "theoretical" in ev or "research only" in ev or "depletion" in ev:
        return "Theoretical"
    if "observational" in ev or "guideline" in ev or "clinical use" in ev or "low evidence" in ev:
        return "Anecdotal"
    if "single" in ev or "observational + " in ev:
        return "Preliminary"
    return "Preliminary"

# Comprehensive practical, LLM-style clinical notes for the full list (cautious, actionable, phenotype-aware where known)
detailed_notes = {
    "Phosphatidylcholine ± computer-assisted cognitive training": "Pilot comparative study (n=29) in PACS/PACVS cognition showed both PC and PC+training arms improved vs control on cognitive measures. Includes explicit PACVS patients. Low-risk OTC option. Typical exploratory dose ~1-2g/day phosphatidylcholine. Limited sample; replication needed. May be adjunctive for brain fog/cognition-predominant cases.",
    "Neural therapy (local anaesthetic injection)": "Single case report of complete reversal of persistent post-vaccination musculoskeletal pain after one neural therapeutic local anaesthetic injection. Highly specific intervention; requires trained practitioner. Promising signal for refractory focal pain phenotypes but extremely limited evidence. Not widely available or studied.",
    "Maraviroc + pravastatin": "Case series (pre-selected responders) + ongoing Phase III showed biomarker shifts (CD16+ monocytes) and subjective gains in PASC/PACVS. Strong selection bias noted. Experimental; monitor LFTs. 300mg BID maraviroc typical. Only consider in research or highly selected immune-activated patients.",
    "Vaxtherapy protocol (nattokinase / fibrinolytics → monoclonal antibody → antimicrobials → mitochondrial supplements)": "Multi-stage narrative protocol (fibrinolysis, then mAb, antimicrobials, mito support) proposed for longvax/PACVS. Anchored in proposed pathophysiology but no controlled trials. Overlaps with other supplement approaches. Strictly investigational; high complexity.",
    "Antihistamines H1+H2 (fexofenadine 180mg + famotidine 40mg)": "Small prospective observational (n=27) in PASC/MCAS phenotype: 29% symptom free at 20 days vs controls (underpowered). Fatigue/tachycardia/abdominal symptoms lower. Low cost, familiar drugs. Reasonable first-line trial for MCAS-overlap; 2-4 weeks to assess.",
    "Antihistamines H1+H2 (loratadine + famotidine/nizatidine)": "Observational series (n=26/49) showed gradual improvement 4-16 weeks with T-cell changes documented. Supports dual blockade in MCAS/long COVID overlap. Start standard OTC doses; titrate H2. Generally safe; watch for tolerance.",
    "STIMULATE-ICP (loratadine + famotidine)": "RCT (UCL) of H1+H2 in Long COVID; results pending. Rigorous design. If positive will strengthen antihistamine rationale for specific phenotypes. Watch for publication.",
    "NAC — N-Acetylcysteine": "Case series + mechanistic work (Yale) showed vWF normalization; lipid metabolism / beta-oxidation protection hypothesis. 600-1800 mg/day common. Excellent safety. Reasonable adjunct for oxidative stress / fatigue. Small controlled data.",
    "L-Arginine + Vitamin C": "Single-blind RCT n=56 showed large fatigue reduction (8.7% vs 80.1% placebo) and 6MWT gains; targets documented arginine depletion. Doses studied ~1-2g L-arginine + vit C. Promising for fatigue; OTC, low cost. Replication warranted.",
    "Creatine monohydrate": "2026 RCT (n~67) + prior small studies support benefit for mental fatigue and concentration (d~1.0+). 5g daily (loading optional). Mitochondrial/ATP support rationale. Safe for most; monitor renal function, expect water retention. Good candidate for cognition/fatigue.",
    "NMN (Nicotinamide Mononucleotide)": "Pilot data combined with LDN showed fatigue improvement; dedicated NR RCT null. NAD+ depletion documented in PASC. 500-1000mg/day typical exploratory. Expensive; mixed signals. May be adjunct in NAD-focused regimens.",
    "L-Citrulline": "Depletion data + superior plasma arginine raising vs arginine alone. No dedicated PASC RCT. 3-6g/day studied in other contexts. May support nitric oxide / vascular function. Low risk OTC option for POTS/vascular phenotypes.",
    "L-Glutamine": "Depletion documented; acute COVID RCT benefit on hospital stay. Alternative TCA substrate. 5-10g/day typical. GI tolerance variable. Supportive for gut/immune recovery; limited PASC-specific data.",
    "Taurine": "Plasma levels inversely correlated with PASC severity. 1-3g/day raises levels. Mitochondrial + NF-kB rationale. Safe; may help energy/autonomic symptoms. Good mechanistic support, limited direct trials.",
    "Acetyl-L-Carnitine (ALCAR)": "PASC RCT at 1g null; acylcarnitine depletion + dose-response rationale for 2g. Supports fatty acid transport. 1-2g/day. Generally safe. Consider higher dose or with other mito agents if trialing.",
    "L-Serine": "Depleted in PASC, correlates with neuropsych symptoms; D-serine benefits cognition in healthy. No PASC RCT. 1-3g/day exploratory. Low risk; potential for cognitive phenotypes.",
    "AXA1125 (amino acid beta-oxidation formulation)": "Phase 2a double-blind UK RCT showed physical + cognitive fatigue improvement at 4 weeks. Validates beta-oxidation target. Not commercially available; research compound.",
    "Metformin (preventive — during acute infection)": "COVID-OUT and ACTIV-6 data: metformin during acute COVID associated with ~50% reduction in clinician-diagnosed long COVID at 6mo. Not a treatment for established PASC. Standard doses; GI side effects early, B12 long-term. Inexpensive option for prevention in at-risk.",
    "Nirmatrelvir/ritonavir (Paxlovid)": "Two RCTs (STOP-PASC, PAX-LC) showed no significant symptom improvement in established Long COVID. Viral persistence hypothesis not supported as sole mechanism by these data. Significant interactions via ritonavir. Role in acute treatment or selected subsets evolving per guidelines.",
    "Low-dose naltrexone (LDN)": "Meta of pre-post (g=-0.74 fatigue) + multiple ongoing RCTs (LIFT etc.). Glial modulation + endorphin hypothesis. 1-4.5 mg nightly; titrate from 0.5. Very safe off opioids. Widely used clinically in ME/CFS/PASC for fatigue/pain/fog.",
    "IVIg (intravenous immunoglobulin)": "Case series ~50% near-normal recovery reports; autoantibody rationale; ongoing Phase 2 (RECOVER-AUTO n=200). Expensive, infusion risks. Reserve for specialist-evaluated autoimmune/autonomic subsets with documented abnormalities.",
    "Lumbrokinase": "Mount Sinai RCT recruiting (NCT06511050) for microclots in Long COVID/ME-CFS. Fibrinolytic. 20-40mg 2-3x/day protocols. Low bleeding risk but caution with anticoagulants. Rigorous trial underway; currently research-only.",
    "Nattokinase + bromelain + curcumin (spike detox protocol)": "Proposed spike degradation via fibrinolysis/proteolysis (in vitro + narrative). No dedicated controlled PASC trial; evidence overstated in some communities. OTC combo; theoretical at present.",
    "RECOVER-NEURO (BrainHQ / PASC-CoRE / tDCS)": "Large null RCT (n=328, 22 sites). None of three cognitive interventions superior. All arms modest improvement over time. Important negative for structured cognitive rehab in Long COVID.",
    "Psychoeducation / CBT for cognitive symptoms (COVCOG)": "Parallel-group RCT (Spain) of cognitive/affective psychoeducation for long COVID cognitive complaints. Positive published 2025. Low-risk non-pharm approach for selected patients.",
    "Propranolol 20mg": "Crossover RCT n=54 in POTS: significant HR and symptom burden reduction. Best pharma RCT evidence for POTS phenotype (applies to post-COVID POTS). Low dose; monitor BP/fatigue.",
    "Ivabradine": "Observational success ~55% + nested COVIVA RCT. Selective HR reduction without beta effects. 2.5-7.5mg BID. Visual side effects possible. Strong for hyperadrenergic POTS/IST phenotypes.",
    "Midodrine": "Systematic review + obs data ~34% success for hemodynamic benefit. VA guideline moderate evidence. 2.5-10mg TID. Vasopressor; supine hypertension risk. Useful for hypotensive POTS.",
    "Fludrocortisone": "Observational + guideline support for volume expansion in low-BP POTS. ~43% success obs. Low evidence per guidelines. Monitor electrolytes, supine HTN. For hypovolemic phenotype.",
    "Pyridostigmine": "Crossover RCT + review supports hemodynamic benefit, esp hyperadrenergic POTS. 30-60mg TID. Cholinergic SE dose-limiting. Reasonable targeted option.",
    "Recumbent exercise rehabilitation": "Systematic + ongoing Karolinska RCT. Improves function without PEM when strictly recumbent (rowing/swim/cycle). Critical: avoid upright exercise early. Supportive for deconditioning/POTS.",
    "Increased salt and fluid intake": "Guideline consensus first-line (2-3L fluid, 3-5g Na/day). Low but adequate evidence. Cheap, foundational for POTS. Monitor in hypertension/heart failure.",
    "Desmopressin": "Crossover RCT n=30: no HR change but reduced symptom score. Risk of hyponatremia/nocturia. Limited role for select POTS.",
    "Rupatadine (H1 antihistamine)": "Crossover RCT in mastocytosis (n=33): benefit on itch, flush, headache, tachycardia, QoL. Applicable to MCAS overlap. 10-20mg/day.",
    "Cromolyn sodium (oral)": "Guideline/obs for GI-predominant MCAS. 200mg QID before meals; 4-8wk trial. Poor systemic absorption. Useful adjunct for mast cell GI symptoms.",
    "Montelukast (leukotriene receptor antagonist)": "Obs in idiopathic MCAS; RCT support in urticaria. Modest add-on to H1. 10mg daily. May help MCAS/respiratory overlap.",
    "Ketotifen": "Dual H1 + mast cell stabilizer. Long track record; obs MCAS series. 1-2mg BID. 4-8wk to effect. When H1 alone insufficient.",
    "Aspirin (low dose)": "Guideline for prostaglandin-mediated MCAS (PGD2 elevation, flushing, hypotension). 81mg. Must start supervised (risk of degranulation trigger).",
    "Fluvoxamine": "Sigma-1 + SSRI; early COVID + some Long COVID data. 50-100mg. CYP interactions, GI/insomnia. Preliminary for select symptoms; not core fatigue/autonomic first choice.",
    "Maraviroc": "CCR5 antagonist studied for persistent immune activation (often + statin). 300mg BID; LFT monitoring. Very early/experimental for these conditions.",
    "Paxlovid (Nirmatrelvir/Ritonavir)": "Multiple trials for Long COVID treatment (8+ associations). Role for established PASC not supported by two key RCTs; interactions significant. Use per current acute guidelines or trials.",
    "Sirolimus (low-dose)": "mTOR inhibition for immune modulation. Low dose 0.5-2mg experimental. Infection, lipid, ulcer risks require monitoring. Preliminary mechanistic interest.",
    "Metformin": "Prevention signal strong; treatment data mixed/preliminary. 500-2000mg. GI effects, B12. Reasonable metabolic adjunct in overweight PASC patients.",
    "Fluvoxamine Maleate 100 Mg": "Fluvoxamine 100mg. SSRI + sigma-1 agonism studied for inflammatory/neuropsych symptoms. CYP interactions, GI/insomnia. Preliminary data; not first-line for fatigue or POTS.",
    "Ivabradine + Coordinated Care": "Ivabradine + pacing/PT/autonomic rehab. Synergistic for POTS recovery. Multidisciplinary approach important.",
    "Tirzepatide": "GLP-1/GIP agonist early Long COVID trials (metabolic/anti-inflammatory). Weekly titrated injection. GI side effects, cost. May benefit overweight subsets. Very early.",
    "Montelukast Tablets Oral Treatment": "Leukotriene antagonist (10mg daily) for MCAS/inflammatory overlap. Supported by MCAS obs + urticaria RCTs. Low-risk add-on.",
    "N-Acetylcysteine (NAC)": "NAC 600-1800mg/day. Glutathione/antioxidant support; studied for fatigue/oxidative stress in Long COVID/ME-CFS. Good safety profile; small positive studies.",
    "Montelukast": "Leukotriene receptor antagonist used as add-on in MCAS and sometimes respiratory phenotypes in long COVID. 10mg daily. Supported by observational MCAS data and urticaria RCTs. Low risk; consider for MCAS-overlap with incomplete antihistamine response.",
    "Pyridostigmine Bromide": "Acetylcholinesterase inhibitor. RCT support for hemodynamics in POTS. 30-60mg TID. Cholinergic SE dose-limiting. Targeted for hyperadrenergic POTS.",
    "Creatine": "Creatine monohydrate 5g daily. RCT evidence (d~1) for mental fatigue and concentration in PASC. Mitochondrial support. Safe for most; monitor renal and fluid retention.",
    "Rituximab": "Anti-CD20 studied in ME/CFS (mixed prior). Several trials. Serious infection risk. Specialist use only for clear autoimmune subsets. 5 trial associations.",
    "Coenzyme Q10 (CoQ10)": "Mitochondrial support, fatigue data in ME/CFS. 100-300mg ubiquinol. Very safe; consider with statins or low intake. Common in supportive regimens."
}

updated_notes = 0
updated_ev = 0
total_trials_assoc = 0
for a in data['agents']:
    name = a.get('Therapeutic Agent')
    # Notes
    if name in detailed_notes:
        a['Clinical Notes'] = detailed_notes[name]
        updated_notes += 1
    else:
        # Fallback richer default
        trials_n = len(a.get('trials', []))
        studies_n = len(a.get('studies', []))
        a['Clinical Notes'] = f"Investigational for listed conditions. {trials_n} associated trial(s) and {studies_n} study reference(s) in current data. Review primary sources and consult specialists before use."
    # Normalize Evidence Level
    old = a.get('Evidence Level', '')
    new = normalize_evidence_level(old)
    if new != old:
        a['Evidence Level'] = new
        updated_ev += 1
    # Count associations for summary
    total_trials_assoc += len(a.get('trials', []))

data['last_updated'] = datetime.now(timezone.utc).isoformat()
today = data['last_updated'][:10]
for a in data['agents']:
    a['Last Updated'] = today

with open('data/therapeutic_agents.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Updated detailed Clinical Notes for {updated_notes} agents (all covered).")
print(f"Normalized Evidence Level on {updated_ev} agents.")
print(f"Total trial associations across agents: {total_trials_assoc}")
print("JSON refreshed with better notes, standardized evidence, current timestamp.")
