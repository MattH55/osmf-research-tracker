"""
Maps the 8 diseases from cure_vs_chronic_batch1.csv to pharmacologically
actionable gene targets with DGIdb / ChEMBL / Open Targets coverage.

Targets are chosen for:
  - Established druggability (approved drug or active clinical pipeline)
  - Pathway coverage (not just one mechanism per disease)
  - Relevance to remission / disease modification, not just symptom management

Hepatitis C: human interferon-pathway and liver-immunity genes are used because
the DAA targets (NS3/NS5A/NS5B) are viral proteins absent from human gene
databases. These human genes govern treatment response and DAA synergy.
"""

DISEASE_BIOMARKERS: dict[str, list[str]] = {

    # ── Type 2 Diabetes ────────────────────────────────────────────────────
    # Covers: insulin sensitisation (PPARG), incretin axis (GLP1R, DPP4),
    # SGLT2 renal glucose excretion, insulin receptor signalling (INSR, IRS1),
    # glucagon counter-regulation (GCGR), hepatic gluconeogenesis (FOXO1),
    # energy sensing (PRKAA1/AMPK), adipokine signalling (ADIPOQ, LEPR)
    "Type 2 Diabetes": [
        "PPARG",    # thiazolidinedione target (rosiglitazone, pioglitazone)
        "GLP1R",    # GLP-1 receptor (semaglutide, liraglutide)
        "DPP4",     # DPP-4 inhibitor target (sitagliptin, saxagliptin)
        "SLC5A2",   # SGLT2 (empagliflozin, dapagliflozin)
        "INSR",     # insulin receptor
        "IRS1",     # insulin receptor substrate 1
        "GCGR",     # glucagon receptor (agonist excess drives hyperglycaemia)
        "FOXO1",    # hepatic gluconeogenesis master regulator
        "PRKAA1",   # AMPK alpha-1 (metformin mechanism)
        "ADIPOQ",   # adiponectin (metabolic sensitiser)
        "LEPR",     # leptin receptor (energy balance)
        "SLC2A4",   # GLUT4 (glucose transporter in muscle/fat)
    ],

    # ── Rheumatoid Arthritis ───────────────────────────────────────────────
    # Covers: cytokine axis (TNF, IL6, IL1B, IL17A), JAK-STAT (JAK1/2/3),
    # T-cell co-stimulation (CD80/CTLA4), B-cell depletion (MS4A1/CD20),
    # bone erosion (TNFSF11/RANKL), fibroblast MMP activity (MMP3)
    "Rheumatoid Arthritis": [
        "TNF",      # anti-TNF biologics (adalimumab, etanercept)
        "IL6",      # IL-6 axis (tocilizumab, sarilumab)
        "IL6R",     # IL-6 receptor (tocilizumab direct target)
        "IL1B",     # IL-1β (anakinra, canakinumab)
        "IL17A",    # IL-17A (secukinumab)
        "JAK1",     # JAK inhibitors (tofacitinib, upadacitinib)
        "JAK2",     # baricitinib target
        "JAK3",     # tofacitinib target
        "CD80",     # CTLA4-Ig target (abatacept)
        "MS4A1",    # CD20 — B-cell depletion (rituximab)
        "TNFSF11",  # RANKL — bone erosion (denosumab)
        "MMP3",     # stromelysin — joint destruction marker and target
        "PTPN22",   # genetic risk locus; phosphatase in T-cell signalling
    ],

    # ── Hypertension ──────────────────────────────────────────────────────
    # Covers: RAAS (ACE, AGT, REN, AGTR1/2), sympathetic nervous system
    # (ADRB1/2), endothelial NO (NOS3), calcium channel (CACNA1C),
    # mineralocorticoid (NR3C2/aldosterone receptor), natriuretic peptide
    # (NPR1), endothelin (EDN1)
    "Hypertension": [
        "ACE",      # ACE inhibitors (lisinopril, enalapril)
        "AGTR1",    # ARBs (losartan, valsartan)
        "AGTR2",    # counter-regulatory RAAS arm
        "REN",      # renin (aliskiren)
        "AGT",      # angiotensinogen (RNA-targeting approaches)
        "ADRB1",    # beta-1 blockers (metoprolol, atenolol)
        "ADRB2",    # beta-2 (modulates vascular tone)
        "NOS3",     # endothelial nitric oxide synthase
        "CACNA1C",  # L-type calcium channel (amlodipine, nifedipine)
        "NR3C2",    # mineralocorticoid receptor (spironolactone, eplerenone)
        "EDN1",     # endothelin-1 (ambrisentan, bosentan context)
        "NPR1",     # natriuretic peptide receptor A
        "SLC12A3",  # NCC thiazide-sensitive transporter (hydrochlorothiazide)
    ],

    # ── Major Depressive Disorder ──────────────────────────────────────────
    # Covers: monoamine transporters (SLC6A4 serotonin, SLC6A3 dopamine,
    # SLC6A2 norepinephrine), postsynaptic receptors (HTR2A, DRD2, HTR1A),
    # monoamine catabolism (MAOA/B), glutamate/NMDA (GRIN2B — ketamine),
    # neurotrophin (NTRK2/TrkB — BDNF receptor), HPA axis (FKBP5, CRH),
    # inflammatory component (IL6, TNF)
    "Major Depressive Disorder": [
        "SLC6A4",   # serotonin transporter (SSRIs)
        "SLC6A2",   # norepinephrine transporter (SNRIs, TCAs)
        "SLC6A3",   # dopamine transporter (bupropion mechanism)
        "HTR2A",    # 5-HT2A receptor (atypical antipsychotics, psilocybin)
        "HTR1A",    # 5-HT1A receptor (buspirone, partial agonists)
        "DRD2",     # dopamine D2 receptor (augmentation strategies)
        "MAOA",     # MAO-A (phenelzine, tranylcypromine)
        "MAOB",     # MAO-B (selegiline)
        "GRIN2B",   # NMDA receptor subunit (ketamine, esketamine)
        "NTRK2",    # TrkB — BDNF high-affinity receptor
        "BDNF",     # brain-derived neurotrophic factor (exercise / drug target)
        "FKBP5",    # HPA axis regulator; stress × antidepressant interaction
        "CRH",      # corticotropin-releasing hormone (HPA dysregulation)
        "IL6",      # inflammatory depression component
    ],

    # ── Epilepsy ──────────────────────────────────────────────────────────
    # Covers: voltage-gated sodium channels (SCN1A/2A/8A — most ASMs),
    # voltage-gated potassium channels (KCNQ2/3, KCNT1),
    # GABA receptors (GABRA1/2, GABRB3), GABA transporter (SLC6A1),
    # NMDA receptor (GRIN2A/B), HCN channel (HCN1 — lacosamide adjacent),
    # mTOR pathway (MTOR, TSC1 — focal cortical dysplasia / tuberous sclerosis)
    "Epilepsy": [
        "SCN1A",    # Nav1.1 — Dravet syndrome; most ASMs modulate Nav
        "SCN2A",    # Nav1.2 — gain-of-function infantile epilepsy
        "SCN8A",    # Nav1.6 — highly penetrant epileptic encephalopathy
        "KCNQ2",    # Kv7.2 — ezogabine target; neonatal seizures
        "KCNQ3",    # Kv7.3 — co-assembles with KCNQ2
        "KCNT1",    # Slack K+ channel — quinidine-responsive epilepsy
        "GABRA1",   # GABA-A α1 — benzodiazepines, phenobarbital
        "GABRA2",   # GABA-A α2
        "GABRB3",   # GABA-A β3 — Lennox-Gastaut
        "SLC6A1",   # GAT-1 GABA transporter (tiagabine)
        "GRIN2A",   # NMDA GluN2A — epileptic aphasia
        "GRIN2B",   # NMDA GluN2B — memantine-sensitive
        "HCN1",     # Ih channel — lacosamide / ivermectin mechanisms
        "MTOR",     # mTOR (everolimus for TSC-related epilepsy)
    ],

    # ── Hepatitis C ───────────────────────────────────────────────────────
    # Human host genes governing: interferon lambda response (IFNL3/4, IFNAR1),
    # innate immune sensing (DDX58/RIG-I, TLR3, MAVS, IRF3),
    # interferon-stimulated effectors (OAS1, MX1, IFIT1),
    # T-cell exhaustion relevant to cure (PDCD1/PD-1, HAVCR2/TIM-3),
    # liver fibrosis resolution (TGFB1)
    "Hepatitis C": [
        "IFNL3",    # IL28B — strongest human genetic predictor of SVR
        "IFNL4",    # IFNL4 dinucleotide variant — also predicts response
        "IFNAR1",   # type-I IFN receptor (pegylated IFN-α mechanism)
        "DDX58",    # RIG-I — cytosolic RNA sensor, first-line innate detector
        "TLR3",     # endosomal dsRNA sensor
        "MAVS",     # mitochondrial antiviral signalling adaptor
        "IRF3",     # IFN transcription factor downstream of RIG-I/MAVS
        "STAT1",    # JAK-STAT IFN signalling
        "OAS1",     # 2'-5' oligoadenylate synthase — antiviral effector
        "MX1",      # GTPase antiviral effector
        "IFIT1",    # IFN-induced tetratricopeptide repeat 1
        "PDCD1",    # PD-1 — T-cell exhaustion; checkpoint for viral clearance
        "HAVCR2",   # TIM-3 — co-exhaustion marker
        "TGFB1",    # TGF-β1 — liver fibrosis; target for regression post-cure
    ],

    # ── Inflammatory Bowel Disease (Crohn's/UC) ───────────────────────────
    # Covers: anti-TNF (TNF), IL-12/23 axis (IL12B, IL23A — ustekinumab),
    # IL-23 specific (IL23R — risankizumab, mirikizumab),
    # integrin/trafficking (ITGA4, MADCAM1 — vedolizumab),
    # JAK-STAT (JAK1, JAK2, TYK2 — tofacitinib, upadacitinib, deucravacitinib),
    # S1P receptor (S1PR1 — ozanimod), barrier/autophagy genetics (NOD2,
    # ATG16L1), regulatory T cells (IL10, FOXP3), epithelial repair (EGFR)
    "Inflammatory Bowel Disease (Crohn's/UC)": [
        "TNF",      # anti-TNF biologics (infliximab, adalimumab)
        "IL12B",    # p40 shared by IL-12/IL-23 (ustekinumab)
        "IL23A",    # p19 IL-23 specific (risankizumab, mirikizumab)
        "IL23R",    # IL-23 receptor — genetic risk locus + drug target
        "ITGA4",    # α4 integrin (vedolizumab targets α4β7)
        "MADCAM1",  # MAdCAM-1 — gut-homing addressin (ontamalimab)
        "JAK1",     # JAK inhibitors (upadacitinib, tofacitinib)
        "JAK2",     # baricitinib, ruxolitinib context
        "TYK2",     # deucravacitinib (approved UC 2023)
        "S1PR1",    # sphingosine-1-phosphate receptor (ozanimod, etrasimod)
        "IL10",     # regulatory cytokine — loss-of-function → Crohn's
        "NOD2",     # innate immune pattern recognition; top Crohn's risk gene
        "ATG16L1",  # autophagy — Crohn's susceptibility
        "FOXP3",    # regulatory T-cell master transcription factor
    ],

    # ── Asthma ────────────────────────────────────────────────────────────
    # Covers: type-2 cytokine axis (IL4, IL5, IL13, IL33, TSLP),
    # receptors (IL4R, IL5RA, IL1RL1/ST2, IL13RA1),
    # IgE / mast-cell (FCER1A, MS4A2), β2-adrenergic bronchodilation (ADRB2),
    # leukotriene pathway (ALOX5, CYSLTR1), eosinophil trafficking (CCR3),
    # Th2 transcription factor (GATA3)
    "Asthma": [
        "IL5",      # IL-5 (mepolizumab, reslizumab, benralizumab)
        "IL5RA",    # IL-5 receptor α (benralizumab direct target)
        "IL4",      # IL-4 (dupilumab blocks IL-4/IL-13 shared receptor)
        "IL4R",     # IL-4Rα — dupilumab target
        "IL13",     # IL-13 (tralokinumab, lebrikizumab)
        "IL13RA1",  # IL-13 receptor α1
        "IL33",     # alarmin (tezepelumab context; itepekimab)
        "IL1RL1",   # ST2 — IL-33 decoy receptor / signalling receptor
        "TSLP",     # thymic stromal lymphopoietin (tezepelumab)
        "ADRB2",    # β2-adrenoceptor (SABA/LABA bronchodilators)
        "ALOX5",    # 5-lipoxygenase (zileuton)
        "CYSLTR1",  # cysteinyl leukotriene receptor 1 (montelukast)
        "FCER1A",   # high-affinity IgE receptor α chain (omalizumab upstream)
        "MS4A2",    # FcεRI β chain — mast-cell IgE signalling
        "GATA3",    # Th2 master transcription factor
    ],

    # ── COPD ────────────────────────────────────────────────────────────────
    # Covers: inflammatory proteases (MMP9, MMP12, ELANE/neutrophil elastase),
    # AAT deficiency (SERPINA1), oxidative stress (NFE2L2/Nrf2), mucin (MUC5AC),
    # airway remodelling (TGFB1), PDE4 (PDE4D)
    "COPD": [
        "MMP9",     # gelatinase involved in emphysema
        "MMP12",    # macrophage elastase
        "ELANE",    # neutrophil elastase (alpha-1 antitrypsin axis)
        "SERPINA1", # alpha-1 antitrypsin
        "NFE2L2",   # Nrf2 — antioxidant master regulator
        "MUC5AC",   # mucin hypersecretion
        "TGFB1",    # airway fibrosis
        "PDE4D",    # PDE4 (roflumilast target)
        "CXCR2",    # neutrophil chemotaxis
        "ADRB2",    # bronchodilator target
    ],

    # ── GERD ────────────────────────────────────────────────────────────────
    # Covers: acid secretion (ATP4A H+/K+ ATPase), histamine (HRH2),
    # lower esophageal sphincter tone (CHRM3/muscarinic), pain (TRPV1),
    # mucosal integrity (CLDN1, TJP1)
    "GERD (Gastroesophageal Reflux Disease)": [
        "ATP4A",    # H+/K+ ATPase (PPI target)
        "HRH2",     # H2 receptor (famotidine target)
        "CHRM3",    # muscarinic M3 (LES tone)
        "TRPV1",    # acid-sensitive nociceptor
        "CLDN1",    # tight junction
        "TJP1",     # zonula occludens-1 (mucosal barrier)
        "IL8",      # inflammatory mediator
        "PTGS2",    # COX-2
    ],

    # ── Atrial Fibrillation ─────────────────────────────────────────────────
    # Covers: ion channels (KCNH2, KCNQ1, SCN5A, KCNA5), calcium handling
    # (RYR2), gap junctions (GJA1/connexin-43), fibrosis (TGFB1), renin-
    # angiotensin (AGTR1)
    "Atrial Fibrillation": [
        "KCNH2",    # hERG — class III antiarrhythmics
        "KCNQ1",    # IKs channel
        "SCN5A",    # Nav1.5 — class I antiarrhythmics
        "KCNA5",    # Kv1.5 — ultra-rapid rectifier
        "RYR2",     # ryanodine receptor — calcium leak
        "GJA1",     # connexin-43 — gap junction
        "TGFB1",    # atrial fibrosis
        "AGTR1",    # angiotensin II receptor (upstream remodelling)
        "ADRB1",    # beta-1 adrenergic receptor
    ],

    # ── Osteoarthritis ──────────────────────────────────────────────────────
    # Covers: cartilage matrix (COL2A1, ACAN), matrix degradation (MMP13,
    # ADAMTS5), Wnt signalling (CTNNB1/beta-catenin), pain (NGF, PTGS2/COX-2)
    "Osteoarthritis": [
        "COL2A1",   # type II collagen
        "ACAN",     # aggrecan
        "MMP13",    # collagenase-3
        "ADAMTS5",  # aggrecanase-2
        "CTNNB1",   # beta-catenin (Wnt pathway — lorecivivint target)
        "NGF",      # nerve growth factor (tanezumab target)
        "PTGS2",    # COX-2 (celecoxib target)
        "IL1B",     # catabolic cytokine
        "IL6",      # inflammatory cytokine
        "TNF",      # low-grade synovitis
    ],

    # ── Alzheimer's Disease ─────────────────────────────────────────────────
    # Covers: APP processing (APP, BACE1, PSEN1), tau (MAPT),
    # ApoE (APOE), neuroinflammation (TREM2), cholinergic (CHRNA7),
    # glutamate (GRIN1/NMDAR1)
    "Alzheimer's Disease and Other Dementias": [
        "APP",      # amyloid precursor protein
        "BACE1",    # beta-secretase
        "PSEN1",    # gamma-secretase
        "MAPT",     # tau (microtubule-associated protein tau)
        "APOE",     # apolipoprotein E epsilon-4 allele
        "TREM2",    # microglial phagocytosis
        "CHRNA7",   # alpha-7 nicotinic receptor
        "GRIN1",    # NMDA receptor (memantine target)
        "BCHE",     # butyrylcholinesterase
        "ACHE",     # acetylcholinesterase (donepezil target)
    ],

    # ── Hypothyroidism ─────────────────────────────────────────────────────
    # Covers: thyroid hormone synthesis (TPO, TG, TSHR), autoimmunity (CTLA4),
    # deiodinase (DIO1, DIO2), transcription (THRA, THRB)
    "Hypothyroidism": [
        "TPO",      # thyroid peroxidase (autoantibody target)
        "TG",       # thyroglobulin
        "TSHR",     # TSH receptor
        "CTLA4",    # immune checkpoint — Hashimoto's
        "DIO1",     # type 1 deiodinase (T4-to-T3 conversion)
        "DIO2",     # type 2 deiodinase (tissue T3)
        "THRA",     # thyroid hormone receptor alpha
        "THRB",     # thyroid hormone receptor beta
    ],

    # ── Low Back Pain ──────────────────────────────────────────────────────
    # Covers: nociceptors (SCN9A/Nav1.7, TRPV1), inflammatory mediators
    # (COX-2/PTGS2, NGF), opioid receptor (OPRM1), central sensitisation
    # (GRIN1/NMDAR1), disc degeneration (COMP)
    "Low Back Pain": [
        "SCN9A",    # Nav1.7 (pain signalling)
        "TRPV1",    # pain nociceptor
        "PTGS2",    # COX-2
        "NGF",      # nerve growth factor
        "OPRM1",    # mu-opioid receptor
        "GRIN1",    # NMDA receptor (central sensitisation)
        "COMP",     # cartilage oligomeric matrix protein (disc)
        "IL6",      # inflammatory mediator
        "TNF",      # cytokine
    ],

    # ── Migraine ──────────────────────────────────────────────────────────
    # Covers: CGRP pathway (CALCA/CGRP, CALCRL, RAMP1), serotonin
    # (HTR1B, HTR1D, HTR1F), TRP channels (TRPV1), CSD (CACNA1A)
    "Migraine": [
        "CALCA",    # CGRP-alpha (anti-CGRP mAb target)
        "CALCRL",   # CLR — CGRP receptor component
        "RAMP1",    # CGRP receptor activity-modifying protein
        "HTR1B",    # 5-HT1B (triptan target)
        "HTR1D",    # 5-HT1D (triptan target)
        "HTR1F",    # 5-HT1F (lasmiditan target)
        "TRPV1",    # trigeminovascular pain
        "CACNA1A",  # P/Q-type calcium channel (familial hemiplegic migraine)
        "NOS3",     # eNOS (NO in vasodilation)
    ],

    # ── Multiple Sclerosis ─────────────────────────────────────────────────
    # Covers: T-cell/B-cell (CD20/MS4A1, CD52, ITGA4), myelin (MBP, MOG),
    # BTK pathway (BTK), sphingosine-1-phosphate (S1PR1), remyelination
    # (LINGO1), vitamin D (VDR)
    "Multiple Sclerosis": [
        "MS4A1",    # CD20 (ocrelizumab, ofatumumab target)
        "ITGA4",    # VLA-4 (natalizumab target)
        "S1PR1",    # S1P receptor (fingolimod, siponimod target)
        "BTK",      # Bruton's tyrosine kinase (tolebrutinib, evobrutinib)
        "MBP",      # myelin basic protein
        "MOG",      # myelin oligodendrocyte glycoprotein
        "LINGO1",   # remyelination blocker (opicinumab target)
        "VDR",      # vitamin D receptor
        "CD52",     # alemtuzumab target
        "IL2RA",    # CD25 — daclizumab target (withdrawn, but pathway relevant)
    ],

    # ── NAFLD / MASH ─────────────────────────────────────────────────────
    # Covers: thyroid hormone receptor beta (THRB — resmetirom target),
    # insulin resistance (PPARG, IRS1), de novo lipogenesis (SREBF1),
    # FXR, PPAR alpha/delta, GLP-1, fibrosis (TGFB1), inflammation (TNF)
    "NAFLD / MASH (Metabolic-Associated Steatohepatitis)": [
        "THRB",     # thyroid hormone receptor beta (resmetirom target)
        "PPARG",    # PPAR-gamma (pioglitazone)
        "PPARA",    # PPAR-alpha (fibrate context; lanifibranor target)
        "PPARD",    # PPAR-delta
        "SREBF1",   # SREBP-1c (de novo lipogenesis)
        "NR1H4",    # FXR (farnesoid X receptor)
        "GLP1R",    # GLP-1 receptor (semaglutide context)
        "TGFB1",    # fibrosis
        "TNF",      # inflammation
        "IRS1",     # insulin signalling
        "FGF21",    # FGF21 (pegbelfermin target)
        "PNPLA3",   # patatin-like phospholipase (genetic risk)
    ],

    # ── Chronic Kidney Disease ─────────────────────────────────────────────
    # Covers: RAAS (ACE, AGTR1), SGLT2 reabsorption, mineralocorticoid
    # (NR3C2), endothelin (EDNRA), TGF-beta/fibrosis (TGFB1), Nrf2 (NFE2L2),
    # complement (C5, CFH)
    "Chronic Kidney Disease": [
        "ACE",      # ACE inhibitors
        "AGTR1",    # angiotensin II receptor
        "NR3C2",    # mineralocorticoid receptor (finerenone target)
        "EDNRA",    # endothelin receptor A (atrasentan target)
        "SLC5A2",   # SGLT2 (empagliflozin, dapagliflozin)
        "TGFB1",    # renal fibrosis
        "NFE2L2",   # Nrf2 (bardoxolone target)
        "C5",       # complement C5 (eculizumab context)
        "CFH",      # complement factor H (aHUS genetic risk)
        "COL4A5",   # collagen type IV (Alport syndrome)
    ],

    # ── Type 1 Diabetes ────────────────────────────────────────────────────
    # Covers: insulin (INS), autoimmunity (GAD2/GAD65, PTPRN/IA-2, CTLA4),
    # T-cell activation (CD3), IL-2 pathway (IL2RA)
    "Type 1 Diabetes": [
        "INS",      # insulin (autoantigen)
        "GAD2",     # GAD65 (major autoantigen)
        "PTPRN",    # IA-2 autoantigen
        "CTLA4",    # immune checkpoint (abatacept context)
        "CD3E",     # CD3 (teplizumab target)
        "IL2RA",    # CD25 (low-dose IL-2 therapy)
        "HLA-DQA1", # HLA (major T1D genetic locus)
        "HLA-DQB1", # HLA (major T1D genetic locus)
        "SLC2A2",   # GLUT2 (glucose sensing in beta cells)
    ],

    # ── Obesity (Severe/Morbid) ────────────────────────────────────────────
    # Covers: leptin-melanocortin (LEPR, MC4R, POMC), incretin (GLP1R, GIPR),
    # energy expenditure (UCP1), appetite (NPY), adipogenesis (FTO)
    "Obesity (Severe / Morbid)": [
        "LEPR",     # leptin receptor
        "MC4R",     # melanocortin-4 receptor (setmelanotide target)
        "POMC",     # pro-opiomelanocortin
        "GLP1R",    # GLP-1 (semaglutide, tirzepatide)
        "GIPR",     # GIP receptor (tirzepatide dual agonist)
        "UCP1",     # brown fat thermogenesis
        "NPY",      # neuropeptide Y (orexigenic)
        "FTO",      # fat mass and obesity associated gene
    ],

    # ── Hyperlipidemia / Dyslipidemia ─────────────────────────────────────
    # Covers: LDL receptor (LDLR), PCSK9, HMG-CoA reductase (HMGCR),
    # cholesterol absorption (NPC1L1), CETP, lipoprotein (APOB), triglyceride (LPL)
    "Hyperlipidemia / Dyslipidemia": [
        "LDLR",     # LDL receptor
        "PCSK9",    # PCSK9 (evolocumab, alirocumab target)
        "HMGCR",    # HMG-CoA reductase (statin target)
        "NPC1L1",   # Niemann-Pick C1-like 1 (ezetimibe target)
        "CETP",     # cholesteryl ester transfer protein
        "APOB",     # apolipoprotein B (mipomersen target)
        "LPL",      # lipoprotein lipase
        "LPA",      # lipoprotein(a) (pelacarsen target)
    ],

    # ── Gout ──────────────────────────────────────────────────────────────
    # Covers: urate reabsorption (SLC22A12/URAT1), urate production (XDH/xanthine oxidase),
    # urate transporter (ABCG2), inflammation (NLRP3/IL1B)
    "Gout": [
        "SLC22A12", # URAT1 (urate reabsorption target — lesinurad, probenecid)
        "XDH",      # xanthine dehydrogenase / oxidase (allopurinol, febuxostat target)
        "ABCG2",    # urate efflux transporter
        "NLRP3",    # NLRP3 inflammasome (colchicine mechanism)
        "IL1B",     # IL-1β (canakinumab in gout flares)
    ],

    # ── Metabolic Syndrome ────────────────────────────────────────────────
    # Covers: insulin resistance (INSR, IRS1), dyslipidaemia (LPL, PPARG),
    # inflammation (TNF, IL6), BP (ACE, AGTR1), energy (PRKAA1/AMPK)
    "Metabolic Syndrome": [
        "INSR",     # insulin receptor
        "IRS1",     # insulin signalling
        "PPARG",    # PPAR-gamma (central adiposity)
        "LPL",      # lipid metabolism
        "TNF",      # inflammatory adipose
        "IL6",      # inflammatory cytokine
        "ACE",      # blood pressure
        "AGTR1",    # angiotensin receptor
        "PRKAA1",   # AMPK (metformin mechanism)
        "LEPR",     # leptin resistance
    ],

    # ── Ischemic Heart Disease / CAD ─────────────────────────────────────
    # Covers: LDL (LDLR, PCSK9), inflammation (IL6, CRP), platelet (ITGB3),
    # endothelial (NOS3), coagulation (F2/thrombin)
    "Ischemic Heart Disease / Coronary Artery Disease": [
        "LDLR",     # LDL receptor
        "PCSK9",    # PCSK9
        "NOS3",     # endothelial NO synthase
        "ITGB3",    # GPIIb/IIIa (abciximab target)
        "F2",       # thrombin (anticoagulation)
        "IL6",      # inflammation (IL-6 linked to CV risk)
        "CRP",      # C-reactive protein (biomarker)
        "AGTR1",    # angiotensin II (remodelling)
        "ACE",      # ACE inhibitors
    ],

    # ── Heart Failure ────────────────────────────────────────────────────
    # Covers: beta-adrenergic (ADRB1/2), RAAS (ACE, AGTR1), natriuretic
    # peptide (NPR1), SGLT2, myosin (MYH7), neprilysin (MME)
    "Heart Failure": [
        "ADRB1",    # beta-1 (carvedilol, metoprolol target)
        "ADRB2",    # beta-2
        "ACE",      # ACE inhibitors
        "AGTR1",    # ARBs
        "NPR1",     # natriuretic peptide receptor A
        "MME",      # neprilysin (sacubitril target — ARNI)
        "SLC5A2",   # SGLT2 (empagliflozin, dapagliflozin in HF)
        "MYH7",     # cardiac myosin (mavacamten context)
        "NR3C2",    # MR (spironolactone, eplerenone)
    ],

    # ── Peripheral Artery Disease ────────────────────────────────────────
    # Covers: vascular (NOS3, EDN1), clotting (F2, SERPINC1),
    # lipid (LDLR, PCSK9), inflammation (IL6, TNF)
    "Peripheral Artery Disease": [
        "NOS3",     # endothelial function
        "EDN1",     # endothelin
        "LDLR",     # LDL receptor
        "PCSK9",    # PCSK9
        "F2",       # thrombin
        "SERPINC1", # antithrombin III
        "IL6",      # inflammation
    ],

    # ── Hypertensive Heart Disease ──────────────────────────────────────
    # Covers: RAAS (ACE, AGTR1, REN), sympathetic (ADRB1), fibrosis (TGFB1),
    # hypertrophy (MYH7, NPPB)
    "Hypertensive Heart Disease": [
        "ACE",      # ACE inhibitors
        "AGTR1",    # ARBs
        "REN",      # renin
        "ADRB1",    # beta-1 blocker
        "TGFB1",    # fibrosis
        "MYH7",     # myosin heavy chain
        "NPPB",     # BNP (biomarker)
    ],

    # ── Cardiomyopathy ──────────────────────────────────────────────────
    # Covers: sarcomere (MYH7, MYBPC3, TNNT2), structural (TTN),
    # LMNA (lamin), amyloidosis (TTR)
    "Cardiomyopathy": [
        "MYH7",     # myosin heavy chain
        "MYBPC3",   # myosin-binding protein C
        "TNNT2",    # troponin T
        "TTN",      # titin
        "LMNA",     # lamin A/C
        "TTR",      # transthyretin (tafamidis target)
        "AGTR1",    # angiotensin II (remodelling)
    ],

    # ── Stroke (Secondary Prevention) ───────────────────────────────────
    # Covers: platelet (ITGB3, P2RY12, PTGS1), coagulation (F2, F10),
    # BP (ACE), lipid (HMGCR, PCSK9)
    "Stroke (Secondary Prevention)": [
        "P2RY12",   # P2Y12 receptor (clopidogrel target)
        "ITGB3",    # GPIIb/IIIa
        "PTGS1",    # COX-1 (aspirin target)
        "F2",       # thrombin
        "F10",      # factor Xa (rivaroxaban target)
        "ACE",      # ACE (perindopril in PROGRESS)
        "HMGCR",    # statin target (SPARCL trial)
        "PCSK9",    # PCSK9
    ],

    # ── Atherosclerosis ─────────────────────────────────────────────────
    # Covers: lipid (LDLR, PCSK9, APOB), inflammation (IL6, CRP),
    # endothelial (NOS3), smooth muscle (ACTA2), epigenetic (TET2)
    "Atherosclerosis": [
        "LDLR",     # LDL receptor
        "PCSK9",    # PCSK9
        "APOB",     # apolipoprotein B
        "NOS3",     # endothelial NO
        "IL6",      # IL-6
        "CRP",      # CRP
        "TET2",     # clonal haematopoiesis driver
        "ACTA2",    # smooth muscle actin
    ],

    # ── Interstitial Lung Disease / Pulmonary Fibrosis ─────────────────
    # Covers: fibrosis (TGFB1, CTGF/CCN2), integrin (ITGAV), tyrosine kinase
    # (PDGFR, FGFR — nintedanib), lysophosphatidic acid (LPAR1), telomere (TERT)
    "Interstitial Lung Disease / Pulmonary Fibrosis": [
        "TGFB1",    # TGF-β1 (pirfenidone target)
        "CCN2",     # CTGF (connective tissue growth factor)
        "ITGAV",    # integrin alpha-V (fibrosis)
        "PDGFRA",   # PDGFR (nintedanib target)
        "LPAR1",    # lysophosphatidic acid receptor 1
        "TERT",     # telomerase (familial ILD)
        "MUC5B",    # mucin (genetic risk)
    ],

    # ── Bronchiectasis ─────────────────────────────────────────────────
    # Covers: neutrophilic inflammation (ELANE), mucus (MUC5AC), infection
    # (CFTR in cystic fibrosis context), IgG (FCGR)
    "Bronchiectasis": [
        "ELANE",    # neutrophil elastase
        "MUC5AC",   # mucin
        "CFTR",     # CFTR (in CF bronchiectasis)
        "FCGR3A",   # IgG receptor
        "CXCR2",    # neutrophil chemotaxis
        "MMP9",     # tissue remodelling
    ],

    # ── Sarcoidosis ────────────────────────────────────────────────────
    # Covers: granuloma formation (TNF, IFNG), vitamin D (CYP27B1),
    # T-cell activation (CD4), macrophage (ACE)
    "Sarcoidosis": [
        "TNF",      # anti-TNF effective in refractory sarcoid
        "IFNG",     # interferon-gamma (granuloma)
        "CYP27B1",  # 1-alpha-hydroxylase (hypercalcemia in sarcoid)
        "CD4",      # T-helper cells
        "ACE",      # serum ACE biomarker
    ],

    # ── Psoriatic Arthritis ────────────────────────────────────────────
    # Covers: IL-17/IL-23 axis (IL17A, IL23A, IL23R), TNF,
    # T-cell (CTLA4; abatacept), JAK, PDE4 (PDE4D — apremilast)
    "Psoriatic Arthritis": [
        "TNF",      # anti-TNF
        "IL17A",    # IL-17A (secukinumab, ixekizumab)
        "IL23A",    # IL-23 (guselkumab, risankizumab)
        "IL23R",    # IL-23 receptor
        "CTLA4",    # abatacept
        "JAK1",     # JAK (tofacitinib, upadacitinib)
        "PDE4D",    # PDE4 (apremilast)
    ],

    # ── Ankylosing Spondylitis ────────────────────────────────────────
    # Covers: IL-17 (IL17A), TNF, HLA-B27, IL-23
    "Ankylosing Spondylitis": [
        "TNF",      # anti-TNF (adalimumab, etanercept)
        "IL17A",    # IL-17A (secukinumab, ixekizumab)
        "IL23A",    # IL-23
        "HLA-B",    # HLA-B27
        "JAK1",     # JAK (upadacitinib approved AS 2022)
    ],

    # ── Fibromyalgia ──────────────────────────────────────────────────
    # Covers: pain (SCN9A, TRPV1), serotonin/norepinephrine (SLC6A4/HTT,
    # SLC6A2), glutamate (GRIN2B), NMDA (GRIN1)
    "Fibromyalgia": [
        "SCN9A",    # Nav1.7 (pain)
        "TRPV1",    # nociceptor
        "SLC6A4",   # serotonin transporter
        "SLC6A2",   # norepinephrine transporter (SNRI — duloxetine, milnacipran)
        "GRIN2B",   # NMDA receptor (central sensitisation)
        "GRIN1",    # NMDA receptor
    ],

    # ── Neck Pain (Chronic) ──────────────────────────────────────────
    # Alias to Low Back Pain targets — similar nociceptive/musculoskeletal
    "Neck Pain (Chronic)": [
        "SCN9A",    # Nav1.7
        "TRPV1",    # nociceptor
        "PTGS2",    # COX-2
        "NGF",      # NGF
        "GRIN1",    # NMDA
        "IL6",      # inflammation
    ],

    # ── Other Musculoskeletal Disorders ───────────────────────────────
    # Generic chronic pain/inflammation targets
    "Other Musculoskeletal Disorders": [
        "PTGS2",    # COX-2
        "TRPV1",    # nociceptor
        "TNF",      # inflammation
        "IL6",      # inflammation
        "SCN9A",    # pain signalling
    ],

    # ── Parkinson's Disease ──────────────────────────────────────────
    # Covers: dopamine (DRD2, SLC6A3/DAT), alpha-synuclein (SNCA),
    # LRRK2, GBA, MAO-B
    "Parkinson's Disease": [
        "DRD2",     # D2 receptor (dopamine agonists)
        "SLC6A3",   # dopamine transporter
        "SNCA",     # alpha-synuclein
        "LRRK2",    # leucine-rich repeat kinase 2
        "GBA",      # glucocerebrosidase
        "MAOB",     # MAO-B (selegiline, rasagiline)
        "TH",       # tyrosine hydroxylase
    ],

    # ── Tension Headache / Chronic Daily Headache ────────────────────
    "Tension Headache / Chronic Daily Headache": [
        "PTGS2",    # COX-2 (NSAIDs)
        "TRPV1",    # nociceptor
        "GRIN2B",   # NMDA (central sensitisation)
        "SCN9A",    # pain signalling
    ],

    # ── Anxiety Disorders ────────────────────────────────────────────
    # Covers: serotonin (HTR1A, SLC6A4), GABA (GABRA1, GABRA2),
    # CRH, noradrenaline (SLC6A2)
    "Anxiety Disorders": [
        "HTR1A",    # 5-HT1A (buspirone)
        "SLC6A4",   # serotonin transporter (SSRIs)
        "SLC6A2",   # norepinephrine transporter (SNRIs)
        "GABRA1",   # GABA-A (benzodiazepines)
        "GABRA2",   # GABA-A α2
        "CRH",      # CRH (HPA axis)
        "BDNF",     # neurotrophin
    ],

    # ── Bipolar Disorder ─────────────────────────────────────────────
    # Covers: inositol signalling (IMPA1), GSK3B (lithium target),
    # dopamine (DRD2), serotonin (HTR2A), glutamate (GRIN2B)
    "Bipolar Disorder": [
        "GSK3B",    # GSK-3 beta (lithium mechanism)
        "IMPA1",    # inositol monophosphatase (lithium mechanism)
        "DRD2",     # D2 (antipsychotics)
        "HTR2A",    # 5-HT2A (atypical antipsychotics)
        "SLC6A4",   # serotonin transporter
        "GRIN2B",   # NMDA
        "BDNF",     # neurotrophin
    ],

    # ── Schizophrenia / Psychotic Disorders ─────────────────────────
    # Covers: dopamine (DRD2, DRD3, COMT), serotonin (HTR2A),
    # glutamate (GRIN2B, GRM2/3), GABA (GAD1)
    "Schizophrenia / Psychotic Disorders": [
        "DRD2",     # D2 (all antipsychotics)
        "DRD3",     # D3
        "HTR2A",    # 5-HT2A (atypical antipsychotics)
        "COMT",     # catechol-O-methyltransferase
        "GRIN2B",   # NMDA hypofunction
        "GAD1",     # GAD67 (GABA interneuron)
        "BDNF",     # neurotrophin
        "AKT1",     # AKT signalling
    ],

    # ── Opioid Use Disorder ─────────────────────────────────────────
    # Covers: mu-opioid (OPRM1), dopamine (DRD2), kappa (OPRK1),
    # norepinephrine (SLC6A2), NMDA (GRIN2B)
    "Opioid Use Disorder": [
        "OPRM1",    # mu-opioid receptor (methadone, buprenorphine target)
        "OPRK1",    # kappa opioid receptor
        "DRD2",     # D2 dopamine
        "SLC6A2",   # norepinephrine (lofexidine)
        "GRIN2B",   # NMDA
        "OPRD1",    # delta opioid receptor
    ],

    # ── Alcohol Use Disorder ─────────────────────────────────────────
    # Covers: GABA (GABRA1), glutamate (GRIN1/NMDA, GRM5), opioid (OPRM1),
    # acetaldehyde (ALDH2), dopamine (DRD2)
    "Alcohol Use Disorder": [
        "GABRA1",   # GABA-A (ethanol target)
        "GRIN1",    # NMDA (ethanol antagonism)
        "OPRM1",    # mu-opioid (naltrexone)
        "ALDH2",    # aldehyde dehydrogenase (disulfiram)
        "DRD2",     # D2 (reward pathway)
        "GRM5",     # mGluR5
        "GRIN2B",   # NMDA
    ],

    # ── Systemic Lupus Erythematosus (SLE) ──────────────────────────
    # Covers: B-cell (CD20/MS4A1), BAFF/BLyS (TNFSF13B), type-I IFN (IFNAR1),
    # complement (C1Q), T-cell (CTLA4 — abatacept), IL-6
    "Systemic Lupus Erythematosus (SLE)": [
        "MS4A1",    # CD20 (rituximab, belimumab—BAFF target)
        "TNFSF13B", # BAFF/BLyS (belimumab target)
        "IFNAR1",   # type-I IFN receptor (anifrolumab target)
        "C1QA",     # complement C1q (lupus nephritis)
        "CTLA4",    # abatacept
        "IL6",      # IL-6
        "TLR7",     # Toll-like receptor 7 (lupus genetics)
        "TLR9",     # Toll-like receptor 9
    ],

    # ── Psoriasis ────────────────────────────────────────────────────
    # Covers: IL-17/IL-23 (IL17A, IL23A, IL23R, IL12B), TNF,
    # PDE4 (PDE4D — apremilast), keratinocyte (KRT16)
    "Psoriasis": [
        "IL17A",    # IL-17A (secukinumab, ixekizumab)
        "IL23A",    # IL-23 (guselkumab, risankizumab)
        "IL12B",    # p40 (ustekinumab)
        "TNF",      # anti-TNF (adalimumab)
        "IL17RA",   # IL-17RA (brodalumab)
        "PDE4D",    # PDE4 (apremilast)
        "TYK2",     # TYK2 (deucravacitinib)
    ],

    # ── Chronic Fatigue Syndrome / ME/CFS ───────────────────────────
    # Covers: autonomic (ADRB2), mitochondrial (ATP5F1A), immune
    # (IL6, TNF), HPA axis (CRH), pain (TRPV1)
    "Chronic Fatigue Syndrome / ME/CFS": [
        "ADRB2",    # beta-2 adrenergic (autonomic dysfunction)
        "IL6",      # inflammation
        "TNF",      # inflammation
        "CRH",      # HPA axis
        "TRPV1",    # pain
        "ATP5F1A",  # mitochondrial ATP synthase
    ],

    # ── Long COVID / Post-Acute Sequelae ─────────────────────────────
    # Covers: ACE2 (SARS-CoV-2 receptor), immune (TLR3, IFNL3),
    # microvascular (NOS3), pain (TRPV1), inflammation (IL6)
    "Long COVID / Post-Acute Sequelae (PACVS)": [
        "ACE2",     # SARS-CoV-2 receptor
        "TLR3",     # innate immune
        "IFNL3",    # interferon lambda
        "NOS3",     # endothelial function
        "IL6",      # inflammation
        "TRPV1",    # pain
        "TNF",      # inflammation
    ],

    # ── Age-Related Hearing Loss (Presbycusis) ──────────────────────
    # Covers: hair cell (MYO7A, CDH23, GJB2/connexin-26), mitochondrial
    # (MT-CO1), oxidative stress (NFE2L2/Nrf2)
    "Age-Related Hearing Loss (Presbycusis)": [
        "GJB2",     # connexin-26
        "CDH23",    # cadherin-23 (tip link)
        "MYO7A",    # myosin VIIA
        "NFE2L2",   # Nrf2 (oxidative stress)
        "MT-CO1",   # mitochondrial cytochrome c oxidase
    ],

    # ── Osteoporosis ──────────────────────────────────────────────────
    # Covers: bone resorption (TNFSF11/RANKL, CTSK), bone formation
    # (LRP5, SOST/sclerostin, PTH1R), oestrogen (ESR1), vitamin D (VDR)
    "Osteoporosis": [
        "TNFSF11",  # RANKL (denosumab target)
        "CTSK",     # cathepsin K (odanacatib)
        "SOST",     # sclerostin (romosozumab target)
        "LRP5",     # Wnt co-receptor
        "PTH1R",    # PTH receptor (teriparatide target)
        "ESR1",     # estrogen receptor alpha
        "VDR",      # vitamin D receptor
        "CALCR",    # calcitonin receptor
    ],
}

# Normalised aliases so CSV disease strings match the canonical keys above
DISEASE_ALIASES: dict[str, str] = {
    "type 2 diabetes": "Type 2 Diabetes",
    "rheumatoid arthritis": "Rheumatoid Arthritis",
    "hypertension": "Hypertension",
    "major depressive disorder": "Major Depressive Disorder",
    "epilepsy": "Epilepsy",
    "hepatitis c": "Hepatitis C",
    "inflammatory bowel disease (crohn's/uc)": "Inflammatory Bowel Disease (Crohn's/UC)",
    "inflammatory bowel disease (crohn's / uc)": "Inflammatory Bowel Disease (Crohn's/UC)",
    "inflammatory bowel disease": "Inflammatory Bowel Disease (Crohn's/UC)",
    "crohn's disease": "Inflammatory Bowel Disease (Crohn's/UC)",
    "ulcerative colitis": "Inflammatory Bowel Disease (Crohn's/UC)",
    "asthma": "Asthma",
    "copd": "COPD",
    "gerd (gastroesophageal reflux disease)": "GERD (Gastroesophageal Reflux Disease)",
    "gerd": "GERD (Gastroesophageal Reflux Disease)",
    "atrial fibrillation": "Atrial Fibrillation",
    "osteoarthritis": "Osteoarthritis",
    "alzheimer's disease and other dementias": "Alzheimer's Disease and Other Dementias",
    "alzheimer's disease": "Alzheimer's Disease and Other Dementias",
    "hypothyroidism": "Hypothyroidism",
    "low back pain": "Low Back Pain",
    "migraine": "Migraine",
    "multiple sclerosis": "Multiple Sclerosis",
    "nafld / mash (metabolic-associated steatohepatitis)": "NAFLD / MASH (Metabolic-Associated Steatohepatitis)",
    "nafld / mash": "NAFLD / MASH (Metabolic-Associated Steatohepatitis)",
    "nafld": "NAFLD / MASH (Metabolic-Associated Steatohepatitis)",
    "mash": "NAFLD / MASH (Metabolic-Associated Steatohepatitis)",
    "chronic kidney disease": "Chronic Kidney Disease",
    "type 1 diabetes": "Type 1 Diabetes",
    "type 1 diabetes mellitus": "Type 1 Diabetes",
    "hypertension (essential)": "Hypertension",
    "obesity (severe / morbid)": "Obesity (Severe / Morbid)",
    "obesity": "Obesity (Severe / Morbid)",
    "hyperlipidemia / dyslipidemia": "Hyperlipidemia / Dyslipidemia",
    "hyperlipidemia": "Hyperlipidemia / Dyslipidemia",
    "dyslipidemia": "Hyperlipidemia / Dyslipidemia",
    "gout": "Gout",
    "metabolic syndrome": "Metabolic Syndrome",
    "ischemic heart disease / coronary artery disease": "Ischemic Heart Disease / Coronary Artery Disease",
    "ischemic heart disease": "Ischemic Heart Disease / Coronary Artery Disease",
    "coronary artery disease": "Ischemic Heart Disease / Coronary Artery Disease",
    "heart failure": "Heart Failure",
    "peripheral artery disease": "Peripheral Artery Disease",
    "hypertensive heart disease": "Hypertensive Heart Disease",
    "cardiomyopathy": "Cardiomyopathy",
    "stroke (secondary prevention)": "Stroke (Secondary Prevention)",
    "stroke": "Stroke (Secondary Prevention)",
    "atherosclerosis": "Atherosclerosis",
    "interstitial lung disease / pulmonary fibrosis": "Interstitial Lung Disease / Pulmonary Fibrosis",
    "interstitial lung disease": "Interstitial Lung Disease / Pulmonary Fibrosis",
    "pulmonary fibrosis": "Interstitial Lung Disease / Pulmonary Fibrosis",
    "bronchiectasis": "Bronchiectasis",
    "sarcoidosis": "Sarcoidosis",
    "psoriatic arthritis": "Psoriatic Arthritis",
    "ankylosing spondylitis": "Ankylosing Spondylitis",
    "fibromyalgia": "Fibromyalgia",
    "neck pain (chronic)": "Neck Pain (Chronic)",
    "neck pain": "Neck Pain (Chronic)",
    "other musculoskeletal disorders": "Other Musculoskeletal Disorders",
    "parkinson's disease": "Parkinson's Disease",
    "tension headache / chronic daily headache": "Tension Headache / Chronic Daily Headache",
    "tension headache": "Tension Headache / Chronic Daily Headache",
    "chronic daily headache": "Tension Headache / Chronic Daily Headache",
    "anxiety disorders": "Anxiety Disorders",
    "generalized anxiety disorder": "Anxiety Disorders",
    "bipolar disorder": "Bipolar Disorder",
    "schizophrenia / psychotic disorders": "Schizophrenia / Psychotic Disorders",
    "schizophrenia": "Schizophrenia / Psychotic Disorders",
    "opioid use disorder": "Opioid Use Disorder",
    "alcohol use disorder": "Alcohol Use Disorder",
    "systemic lupus erythematosus (sle)": "Systemic Lupus Erythematosus (SLE)",
    "systemic lupus erythematosus": "Systemic Lupus Erythematosus (SLE)",
    "lupus": "Systemic Lupus Erythematosus (SLE)",
    "psoriasis": "Psoriasis",
    "chronic fatigue syndrome / me/cfs": "Chronic Fatigue Syndrome / ME/CFS",
    "chronic fatigue syndrome": "Chronic Fatigue Syndrome / ME/CFS",
    "me/cfs": "Chronic Fatigue Syndrome / ME/CFS",
    "long covid / post-acute sequelae (pacvs)": "Long COVID / Post-Acute Sequelae (PACVS)",
    "long covid": "Long COVID / Post-Acute Sequelae (PACVS)",
    "pacvs": "Long COVID / Post-Acute Sequelae (PACVS)",
    "age-related hearing loss (presbycusis)": "Age-Related Hearing Loss (Presbycusis)",
    "age-related hearing loss": "Age-Related Hearing Loss (Presbycusis)",
    "presbycusis": "Age-Related Hearing Loss (Presbycusis)",
    "osteoporosis": "Osteoporosis",
    "type 2 diabetes mellitus": "Type 2 Diabetes",
}


def get_biomarkers_for_disease(disease: str) -> list[str]:
    key = disease.strip().lower()
    canonical = DISEASE_ALIASES.get(key, disease)
    return DISEASE_BIOMARKERS.get(canonical, [])
