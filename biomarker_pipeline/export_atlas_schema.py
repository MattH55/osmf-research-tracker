#!/usr/bin/env python3
"""Transform Stage 3b/4b output into a biomarkers.schema.json-shaped
data/biomarkers/{slug}.json, the same format used by the 5 existing atlases
(PACVS, ME/CFS, Long COVID, Lyme, Gulf War Illness).

Reads:
    biomarker_pipeline/results/atlas/{slug}/{GENE}.json   (MarkerAtlasCandidate)
    biomarker_pipeline/loinc_lookup.json

Writes:
    data/biomarkers/{slug}.json

Only markers with at least one direction claim that has BOTH a citation and a
DOI are included — the schema requires reference.citation/reference.doi for
every marker, and a marker with an "unclear"-only or citation-less claim set
isn't ready for publication. Markers that don't clear this bar are recorded
in coverage_notes so it's visible what's still missing, not silently dropped.

Usage (from research-tracker/):
    python -m biomarker_pipeline.export_atlas_schema --slug asthma --disease "Asthma"
"""
import argparse
import json
import logging
import re
from collections import Counter
from datetime import date
from pathlib import Path

from .models import MarkerAtlasCandidate

log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results" / "atlas"
LOINC_PATH  = Path(__file__).parent / "loinc_lookup.json"
DATA_DIR    = Path(__file__).parent.parent / "data" / "biomarkers"

# Keyword -> category heuristic. Checked in order; first match wins.
# Mirrors the category vocabulary already used by the 5 existing atlases
# (inflammatory/metabolic/coagulation/vascular/neurological/immune/
# proteomic/lipidomic/microbiome/viral) plus 'receptor'/'other' for
# pharmacologic targets that don't fit those buckets.
#
# Two rule sets: _CLINICAL_CATEGORY_RULES matches on real biomarker names
# (full words/phrases like "HbA1c", "eGFR", "Rheumatoid Factor" — checked
# first since gene-symbol patterns below would otherwise false-positive on
# short substrings), _CATEGORY_RULES matches gene-symbol-shaped names (short,
# anchored, all-caps patterns) for markers exported via --marker-source gene.
_CLINICAL_CATEGORY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"HbA1c|Fasting Plasma Glucose|Fasting Insulin|HOMA-IR|C-Peptide|Adiponectin|Triglycerides|Autoantibod", re.I), "metabolic"),
    (re.compile(r"eGFR|Creatinine|Cystatin C|Albumin-Creatinine|Parathyroid Hormone|Phosphate", re.I), "renal"),
    (re.compile(r"\bALT\b|\bAST\b|\bGGT\b|FIB-4|Cytokeratin-18|HCV RNA", re.I), "hepatic"),
    (re.compile(r"TSH|Free T4|Free T3|Anti-TPO|Anti-Thyroglobulin|Aldosterone|Cortisol|Renin", re.I), "endocrine"),
    (re.compile(r"Troponin|NT-proBNP|D-dimer", re.I), "cardiac"),
    (re.compile(r"FEV1|FVC|DLCO|Eosinophil|Total IgE|Periostin|Nitric Oxide|Sputum|Alpha-1 Antitrypsin", re.I), "pulmonary"),
    (re.compile(r"Amyloid|Tau|Neurofilament|GFAP|Oligoclonal|CGRP|Prolactin|Neuron-Specific Enolase|S100B|Magnesium", re.I), "neurological"),
    (re.compile(r"Rheumatoid Factor|Anti-CCP|ANCA|ASCA|Calprotectin", re.I), "immune"),
    (re.compile(r"\bCRP\b|hsCRP|\bESR\b|Fibrinogen|\bIL-?\d", re.I), "inflammatory"),
    (re.compile(r"COMP|CTX-II|Hyaluronic Acid|MMP-3", re.I), "musculoskeletal"),
    (re.compile(r"Pepsin|Acid Exposure", re.I), "gastrointestinal"),
    (re.compile(r"\bBDNF\b", re.I), "neurological"),
]

_CATEGORY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^(IL\d|TNF|CRP|IFN|NLRP)", re.I), "inflammatory"),
    (re.compile(r"^(INSR|IRS1|PPARG|GLP1R|DPP4|SLC5A2|SLC2A4|GCGR|FOXO1|PRKAA1|ADIPOQ|LEPR)$", re.I), "metabolic"),
    (re.compile(r"^(F2|F5|F7|F9|F10|VWF|PLAT|SERPINE1)$", re.I), "coagulation"),
    (re.compile(r"^(NOS3|EDN1|ACE|AGT|REN|VEGFA)$", re.I), "vascular"),
    (re.compile(r"^(BDNF|GRIN|GABRA|SNCA|APP|MAPT|CHRNA)", re.I), "neurological"),
    (re.compile(r"^(JAK|STAT|CD\d|MS4A1|CTLA4|HLA)", re.I), "immune"),
    (re.compile(r"R$|RA$|RA1$|R1$|R2$", re.I), "receptor"),
]


def _classify_category(symbol: str) -> str:
    for pattern, category in _CLINICAL_CATEGORY_RULES:
        if pattern.search(symbol):
            return category
    for pattern, category in _CATEGORY_RULES:
        if pattern.search(symbol):
            return category
    return "other"


_CATEGORY_LABELS = {
    "inflammatory": "Inflammatory",
    "metabolic": "Metabolic",
    "coagulation": "Coagulation",
    "vascular": "Vascular",
    "neurological": "Neurological",
    "immune": "Immune",
    "renal": "Renal",
    "hepatic": "Hepatic",
    "endocrine": "Endocrine",
    "cardiac": "Cardiac",
    "pulmonary": "Pulmonary",
    "musculoskeletal": "Musculoskeletal",
    "gastrointestinal": "Gastrointestinal",
    "receptor": "Receptor / Pharmacologic Target",
    "other": "Other",
}


def _load_loinc_lookup() -> dict:
    if not LOINC_PATH.exists():
        return {}
    return json.loads(LOINC_PATH.read_text(encoding="utf-8"))


def _lookup_loinc(symbol: str, synonyms: list[str], loinc_lookup: dict) -> tuple[str | None, str | None]:
    candidates = [symbol.lower()] + [s.lower() for s in synonyms]
    for key in candidates:
        entry = loinc_lookup.get(key)
        if entry:
            return entry.get("loinc"), entry.get("testType")
    return None, None


def _pick_marker_entry(candidate: MarkerAtlasCandidate, loinc_lookup: dict) -> dict | None:
    usable = [c for c in candidate.claims if c.citation and c.doi and c.direction != "unclear"]
    if not usable:
        return None

    directions = Counter(c.direction for c in usable)
    top_direction, top_count = directions.most_common(1)[0]
    direction = top_direction if top_count == len(usable) or len(directions) == 1 else "mixed"

    best = usable[0]
    loinc, test_type = _lookup_loinc(candidate.symbol, candidate.synonyms, loinc_lookup)

    entry = {
        "name": candidate.symbol,
        "alternateName": candidate.synonyms[0] if candidate.synonyms else candidate.symbol,
        "direction": direction,
        "category": _classify_category(candidate.symbol),
        "comparison": best.comparison_population or "HC",
        "symptoms": best.symptoms or "",
        "reference": {
            "citation": best.citation,
            "doi": best.doi,
        },
    }
    if test_type:
        entry["testType"] = test_type
    if loinc:
        entry["loinc"] = loinc
    return entry


def build_atlas(slug: str, disease_name: str) -> tuple[dict, list[str]]:
    candidates_dir = RESULTS_DIR / slug
    loinc_lookup = _load_loinc_lookup()
    coverage_notes: list[str] = []

    markers: list[dict] = []
    if not candidates_dir.exists():
        coverage_notes.append(f"No Stage 3b/4b results found at {candidates_dir}.")
    else:
        for path in sorted(candidates_dir.glob("*.json")):
            candidate = MarkerAtlasCandidate(**json.loads(path.read_text(encoding="utf-8")))
            entry = _pick_marker_entry(candidate, loinc_lookup)
            if entry:
                markers.append(entry)
            else:
                coverage_notes.append(
                    f"{candidate.symbol}: no claim with both citation and DOI — excluded pending curation."
                )

    categories_used = sorted({m["category"] for m in markers})
    categories = {c: _CATEGORY_LABELS.get(c, c.title()) for c in categories_used}

    atlas = {
        "slug": slug,
        "id": f"{slug}-biomarkers",
        "condition": {
            "name": disease_name,
            "shortName": disease_name,
            "alternateNames": [],
        },
        "page": {
            "title": f"{disease_name} Biomarker Atlas | Blood Tests & Molecular Alterations",
            "breadcrumbName": f"{disease_name} Biomarkers",
            "description": (
                f"Searchable atlas of {disease_name} biomarkers, from peer-reviewed literature "
                f"comparing patient levels vs. healthy controls."
            ),
            "keywords": [f"{disease_name} biomarkers", f"{disease_name} blood tests", "biomarker atlas", "biomarker database"],
            "canonical": f"https://research.opensourcemed.info/{slug}-biomarkers.html",
            "hero": f"Molecular alterations reported in {disease_name} compared to healthy controls, from peer-reviewed literature.",
            "dateModified": date.today().isoformat(),
        },
        "categories": categories,
        "filters": categories_used,
        "markers": markers,
    }
    return atlas, coverage_notes


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Export Stage 3b/4b results into biomarkers.schema.json format")
    parser.add_argument("--slug", required=True, help="URL slug, e.g. asthma")
    parser.add_argument("--disease", required=True, help="Canonical disease name, e.g. Asthma")
    parser.add_argument("--output", default=None, help="Output path (default: data/biomarkers/{slug}.json)")
    args = parser.parse_args()

    atlas, notes = build_atlas(args.slug, args.disease)
    for note in notes:
        log.warning(note)

    out_path = Path(args.output) if args.output else DATA_DIR / f"{args.slug}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(atlas, indent=2), encoding="utf-8")
    log.info("Wrote %d markers to %s (%d excluded pending curation)", len(atlas["markers"]), out_path, len(notes))


if __name__ == "__main__":
    main()
