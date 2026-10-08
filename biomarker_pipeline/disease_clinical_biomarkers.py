"""
Real clinical/lab biomarkers per disease — distinct from disease_biomarkers.py,
which maps diseases to pharmacologically actionable GENE TARGETS (drug
discovery panel: what a drug could hit) rather than biomarkers (what's
actually measured in a patient to characterize disease state).

The two panels overlap only incidentally (e.g. ADIPOQ/adiponectin, DPP4 are
both a drug target and a measurable serum biomarker). Most drug-target genes
here (GLP1R, INSR, SLC5A2, JAK1/2/3...) are not lab tests anyone orders — and
most real biomarkers (HbA1c, FeNO, fecal calprotectin, eGFR) are not druggable
gene targets. This file is the input to the biomarker-atlas curation pipeline
(stage1_normalize -> stage3b_marker_literature -> stage4b_marker_direction ->
export_atlas_schema), which asks "is this marker elevated/reduced in the
disease vs. healthy controls" — a question that only makes sense for an
actual measured biomarker, not a drug target gene.

Uses the same canonical disease names / DISEASE_ALIASES as
disease_biomarkers.py so both panels can be looked up from one disease name.
"""

DISEASE_CLINICAL_BIOMARKERS: dict[str, list[str]] = {

    "Type 2 Diabetes": [
        "HbA1c", "Fasting Plasma Glucose", "Fasting Insulin", "HOMA-IR",
        "C-Peptide", "Adiponectin", "Triglycerides", "hsCRP",
    ],
    "Type 1 Diabetes": [
        "HbA1c", "C-Peptide", "GAD65 autoantibodies", "IA-2 autoantibodies",
        "ZnT8 autoantibodies", "Fasting Plasma Glucose",
    ],
    "Hypertension": [
        "Plasma Renin Activity", "Aldosterone", "NT-proBNP",
        "Urinary Albumin-Creatinine Ratio", "Homocysteine",
        "Uric Acid",
        "High-Sensitivity CRP",
        "Endothelin-1",
        "Asymmetric Dimethylarginine (ADMA)",
        "Cystatin C",
    ],
    "Chronic Kidney Disease": [
        "eGFR", "Serum Creatinine", "Urinary Albumin-Creatinine Ratio",
        "Cystatin C", "Parathyroid Hormone", "Serum Phosphate",
    ],
    "NAFLD / MASH (Metabolic-Associated Steatohepatitis)": [
        "ALT", "AST", "GGT", "FIB-4 Index", "Cytokeratin-18 (CK-18)", "Ferritin",
    ],
    "Atrial Fibrillation": [
        "NT-proBNP", "High-Sensitivity Troponin", "CRP", "D-dimer",
        "Galectin-3",
        "Growth Differentiation Factor-15 (GDF-15)",
        "Interleukin-6",
        "Fibrinogen",
        "Mid-Regional pro-Atrial Natriuretic Peptide (MR-proANP)",
    ],
    "COPD": [
        "FEV1", "FEV1/FVC ratio", "Blood Eosinophil Count",
        "Alpha-1 Antitrypsin", "Fibrinogen", "CRP",
    ],
    "Asthma": [
        "Fractional Exhaled Nitric Oxide (FeNO)", "Blood Eosinophil Count",
        "Total IgE", "Periostin", "Sputum Eosinophils",
        "Interleukin-5",
        "Interleukin-13",
        "Eotaxin",
        "Urinary Leukotriene E4",
        "25-Hydroxyvitamin D",
    ],
    "Osteoarthritis": [
        "CRP", "Cartilage Oligomeric Matrix Protein (COMP)",
        "Urinary CTX-II", "Hyaluronic Acid", "MMP-3",
    ],
    "Low Back Pain": [
        "CRP", "ESR", "IL-6",
        "TNF-alpha",
        "Interleukin-1 beta",
        "25-Hydroxyvitamin D",
        "Substance P",
        "Brain-Derived Neurotrophic Factor (BDNF)",
        "Matrix Metalloproteinase-3 (MMP-3)",
    ],
    "Rheumatoid Arthritis": [
        "Rheumatoid Factor", "Anti-CCP Antibodies", "ESR", "CRP", "IL-6",
    ],
    "Alzheimer's Disease and Other Dementias": [
        "Amyloid-beta 42/40 ratio", "Phosphorylated Tau (p-tau181)",
        "Total Tau", "Neurofilament Light Chain (NfL)", "GFAP",
        "Plasma p-tau217",
        "CSF Amyloid-beta 42",
        "YKL-40",
        "Neurogranin",
        "Homocysteine",
        "Plasma Amyloid-beta 42",
    ],
    "Multiple Sclerosis": [
        "CSF Oligoclonal Bands", "Neurofilament Light Chain (NfL)", "GFAP",
        "CSF IgG Index",
        "CSF Kappa Free Light Chains",
        "YKL-40",
        "25-Hydroxyvitamin D",
        "CXCL13",
        "Osteopontin",
    ],
    "Epilepsy": [
        "Prolactin", "Neuron-Specific Enolase (NSE)", "S100B",
        "Creatine Kinase",
        "Lactate",
        "Ammonia",
        "Interleukin-6",
        "High-Mobility Group Box 1 (HMGB1)",
        "GFAP",
        "Neurofilament Light Chain (NfL)",
    ],
    "Migraine": [
        "Calcitonin Gene-Related Peptide (CGRP)", "Serum Magnesium",
        "Pituitary Adenylate Cyclase-Activating Polypeptide (PACAP-38)",
        "25-Hydroxyvitamin D",
        "Homocysteine",
        "High-Sensitivity CRP",
        "Interleukin-6",
        "Glutamate",
        "Nitric Oxide Metabolites",
        "Serotonin",
        "Neurofilament Light Chain (NfL)",
        "Serum Ferritin",
    ],
    "Major Depressive Disorder": [
        "Cortisol", "CRP", "BDNF", "IL-6",
        "TNF-alpha",
        "Interleukin-1 beta",
        "Kynurenine/Tryptophan Ratio",
        "Dehydroepiandrosterone Sulfate (DHEA-S)",
        "25-Hydroxyvitamin D",
        "Homocysteine",
        "Insulin-like Growth Factor-1 (IGF-1)",
    ],
    "Inflammatory Bowel Disease (Crohn's/UC)": [
        "Fecal Calprotectin", "CRP", "ESR", "ASCA Antibodies", "ANCA Antibodies",
    ],
    "GERD (Gastroesophageal Reflux Disease)": [
        "Salivary Pepsin", "Esophageal Acid Exposure Time",
        "Pepsinogen I",
        "Gastrin-17",
        "Mean Nocturnal Baseline Impedance",
        "Salivary Epidermal Growth Factor (EGF)",
        "Interleukin-8",
    ],
    "Hepatitis C": [
        "HCV RNA Viral Load", "ALT", "AST", "FIB-4 Index",
        "Hyaluronic Acid",
        "Alpha-Fetoprotein",
        "Platelet Count",
        "Gamma-Glutamyl Transferase (GGT)",
        "Cryoglobulins",
    ],
    "Hypothyroidism": [
        "TSH", "Free T4", "Free T3", "Anti-TPO Antibodies",
        "Anti-Thyroglobulin Antibodies",
    ],
}


def get_clinical_biomarkers_for_disease(disease: str) -> list[str]:
    # Reuse disease_biomarkers.py's alias table so both panels resolve from
    # the same set of input disease-name spellings.
    from .disease_biomarkers import DISEASE_ALIASES

    key = disease.strip().lower()
    canonical = DISEASE_ALIASES.get(key, disease)
    return DISEASE_CLINICAL_BIOMARKERS.get(canonical, [])
