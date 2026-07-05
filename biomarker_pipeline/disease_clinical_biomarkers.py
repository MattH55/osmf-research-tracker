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
    ],
    "COPD": [
        "FEV1", "FEV1/FVC ratio", "Blood Eosinophil Count",
        "Alpha-1 Antitrypsin", "Fibrinogen", "CRP",
    ],
    "Asthma": [
        "Fractional Exhaled Nitric Oxide (FeNO)", "Blood Eosinophil Count",
        "Total IgE", "Periostin", "Sputum Eosinophils",
    ],
    "Osteoarthritis": [
        "CRP", "Cartilage Oligomeric Matrix Protein (COMP)",
        "Urinary CTX-II", "Hyaluronic Acid", "MMP-3",
    ],
    "Low Back Pain": [
        "CRP", "ESR", "IL-6",
    ],
    "Rheumatoid Arthritis": [
        "Rheumatoid Factor", "Anti-CCP Antibodies", "ESR", "CRP", "IL-6",
    ],
    "Alzheimer's Disease and Other Dementias": [
        "Amyloid-beta 42/40 ratio", "Phosphorylated Tau (p-tau181)",
        "Total Tau", "Neurofilament Light Chain (NfL)", "GFAP",
    ],
    "Multiple Sclerosis": [
        "CSF Oligoclonal Bands", "Neurofilament Light Chain (NfL)", "GFAP",
        "CSF IgG Index",
    ],
    "Epilepsy": [
        "Prolactin", "Neuron-Specific Enolase (NSE)", "S100B",
    ],
    "Migraine": [
        "Calcitonin Gene-Related Peptide (CGRP)", "Serum Magnesium",
    ],
    "Major Depressive Disorder": [
        "Cortisol", "CRP", "BDNF", "IL-6",
    ],
    "Inflammatory Bowel Disease (Crohn's/UC)": [
        "Fecal Calprotectin", "CRP", "ESR", "ASCA Antibodies", "ANCA Antibodies",
    ],
    "GERD (Gastroesophageal Reflux Disease)": [
        "Salivary Pepsin", "Esophageal Acid Exposure Time",
    ],
    "Hepatitis C": [
        "HCV RNA Viral Load", "ALT", "AST", "FIB-4 Index",
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
