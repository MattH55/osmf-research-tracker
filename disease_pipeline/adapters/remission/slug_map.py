"""Map disease_db_100 labels to RepurpOS slugs."""
from __future__ import annotations

import json
from pathlib import Path

from ...config import PACKAGE_DIR
from ...output.web_export import web_slug

MANIFEST_PATH = PACKAGE_DIR / "seeds" / "disease_db_100_manifest.json"

# Reuse expand_to_100 canonical hints when manifest slug is missing.
CANONICAL_SLUG_HINTS: dict[str, str] = {
    "Psoriasis (Nail / Palmoplantar)": "psoriasis-vulgaris",
    "Stroke (Ischaemic / Cerebrovascular Disease)": "ischemic-stroke",
    "Long COVID / Post-Acute COVID Sequelae (PACVS)": "post-acute-covidvaccination-syndrome",
    "ME/CFS (Myalgic Encephalomyelitis / Chronic Fatigue Syndrome)": "myalgic-encephalomyelitis-chronic-fatigue-syndrome",
    "Ankylosing Spondylitis / Axial Spondyloarthropathy": "ankylosing-spondylitis",
    "Insomnia / Sleep Disorders": "insomnia",
    "Coeliac Disease (Refractory / RCD)": "celiac-disease",
    "Peripheral Neuropathy (Diabetic Peripheral Neuropathy)": "diabetic-neuropathy",
    "Multiple Myeloma": "plasma-cell-myeloma",
    "Kidney Stones (Nephrolithiasis)": "nephrolithiasis",
    "Immune Thrombocytopaenia (ITP)": "autoimmune-thrombocytopenic-purpura",
    "Chronic Urticaria (CSU)": "chronic-idiopathic-urticaria",
    "Type 2 Diabetes": "type-2-diabetes",
    "Rheumatoid Arthritis": "rheumatoid-arthritis",
    "Major Depressive Disorder": "major-depressive-disorder",
    "Inflammatory Bowel Disease (Crohn's / UC)": "inflammatory-bowel-disease",
    "COPD": "chronic-obstructive-pulmonary-disease",
    "GERD (Gastroesophageal Reflux Disease)": "gastroesophageal-reflux-disease",
    "Alzheimer's Disease and Other Dementias": "alzheimers-disease-and-other-dementias",
    "Parkinson's Disease": "parkinson-disease",
    "Hepatitis C": "hepatitis-c",
    "Asthma": "asthma",
    "Hypertension": "essential-hypertension",
}

_label_to_slug: dict[str, str] | None = None
_slug_to_label: dict[str, str] | None = None


def load_label_slug_map() -> dict[str, str]:
    global _label_to_slug
    if _label_to_slug is not None:
        return _label_to_slug

    mapping: dict[str, str] = {}
    if MANIFEST_PATH.exists():
        for row in json.loads(MANIFEST_PATH.read_text(encoding="utf-8")):
            label = row.get("label", "")
            slug = row.get("slug", "")
            if label and slug:
                mapping[label] = slug

    for label, slug in CANONICAL_SLUG_HINTS.items():
        mapping.setdefault(label, slug)

    _label_to_slug = mapping
    return mapping


def label_for_slug(slug: str) -> str | None:
    global _slug_to_label
    if _slug_to_label is None:
        _slug_to_label = {v: k for k, v in load_label_slug_map().items()}
    return _slug_to_label.get(slug)


def slug_for_label(label: str) -> str:
    m = load_label_slug_map()
    if label in m:
        return m[label]
    if label in CANONICAL_SLUG_HINTS:
        return CANONICAL_SLUG_HINTS[label]
    return web_slug(label)