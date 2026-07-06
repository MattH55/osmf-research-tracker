#!/usr/bin/env python3
"""Download NIH RCDC table and build seeds/nih_rcdc_by_slug.json."""
from __future__ import annotations

import json
import logging
import re
import sys
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

SEEDS = Path(__file__).parent / "seeds"
XLSX_PATH = SEEDS / "rcdc_funding_summary.xlsx"
OUT = SEEDS / "nih_rcdc_by_slug.json"
MAP_OUT = SEEDS / "rcdc_slug_map.json"
MANIFEST = SEEDS / "disease_db_100_manifest.json"

log = logging.getLogger(__name__)

RCDC_EXPORT = "https://report.nih.gov/reportweb/api/categoricalspendingexport"
RCDC_DOWNLOAD = "https://report.nih.gov/reportweb/api/Download?path=files&filename="

# Manual slug → exact RCDC category name (from NIH export)
SLUG_OVERRIDES: dict[str, str] = {
    "type-2-diabetes": "Diabetes 5",
    "type-1-diabetes": "Diabetes 5",
    "essential-hypertension": "Hypertension",
    "major-depressive-disorder": "Depression",
    "chronic-obstructive-pulmonary-disease": "Chronic Obstructive Pulmonary Disease",
    "inflammatory-bowel-disease": "Inflammatory Bowel Disease",
    "alzheimers-disease-and-other-dementias": "Alzheimer's Disease",
    "myalgic-encephalomyelitis-chronic-fatigue-syndrome": "Chronic Fatigue Syndrome (ME/CFS)",
    "post-acute-covidvaccination-syndrome": "Post-Acute Sequelae of SARS-CoV-2 infection (PASC) including Long COVID 11",
    "celiac-disease": "Celiac Disease",
    "psoriasis-vulgaris": "Psoriasis",
    "ischemic-stroke": "Stroke",
    "migraine-disorder": "Migraine 16",
    "hivaids": "HIV/AIDS 8",
    "cancer": "Cancer 16",
    "lung-cancer": "Lung Cancer",
    "breast-cancer": "Breast Cancer",
    "prostate-cancer": "Prostate Cancer",
    "melanoma": "Skin Cancer",
    "insomnia": "Sleep Research",
    "obstructive-sleep-apnea-syndrome": "Sleep Research",
    "alcohol-abuse": "Alcoholism, Alcohol Use and Health 16",
    "opioid-use-disorder": "Opioid Misuse and Addiction 10, 16",
    "atopic-eczema": "Eczema / Atopic Dermatitis",
    "atrial-fibrillation": "Heart Disease",
    "heart-failure": "Heart Disease",
    "chronic-kidney-disease": "Kidney Disease",
    "age-related-macular-degeneration": "Macular Degeneration",
    "benign-prostatic-hyperplasia": "Prostate Disease",
    "rheumatoid-arthritis": "Rheumatoid Arthritis",
    "epilepsy": "Epilepsy",
    "hepatitis-c": "Hepatitis - C",
    "asthma": "Asthma",
    "osteoarthritis": "Osteoarthritis",
    "parkinson-disease": "Parkinson's Disease",
    "multiple-sclerosis": "Multiple Sclerosis",
    "fibromyalgia": "Fibromyalgia",
    "lupus": "Lupus",
    "endometriosis": "Endometriosis",
    "schizophrenia": "Schizophrenia",
    "bipolar-disorder": "Bipolar Disorder",
    "anxiety": "Anxiety Disorders",
    "sarcopenia": "Sarcopenia",
    "pancreatic-cancer": "Pancreatic Cancer",
    "colorectal-cancer": "Colorectal Cancer",
    "ovarian-cancer": "Ovarian Cancer",
    "liver-cancer": "Liver Cancer",
    "brain-cancer": "Brain Cancer",
    "stomach-cancer": "Stomach Cancer",
    "cervical-cancer": "Cervical Cancer",
    "uterine-cancer": "Uterine Cancer",
    "testicular-cancer": "Testicular Cancer",
    "esophageal-cancer": "Esophageal Cancer",
    "b-cell-chronic-lymphocytic-leukemia": "Childhood Leukemia",
    "sjögrens-syndrome": "Sjogren's Disease",
}


def _norm(text: str) -> str:
    text = re.sub(r"\s+\d+(\s*,\s*\d+)*\s*$", "", text)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def download_xlsx() -> None:
    req = urllib.request.Request(RCDC_EXPORT, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        filename = r.read().decode("utf-8").strip()
    url = RCDC_DOWNLOAD + filename
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=120) as r:
        XLSX_PATH.write_bytes(r.read())
    log.info("Downloaded %s (%d bytes)", XLSX_PATH, XLSX_PATH.stat().st_size)


def parse_rcdc() -> dict[str, dict]:
    try:
        import openpyxl
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl", "-q"])
        import openpyxl

    wb = openpyxl.load_workbook(XLSX_PATH, read_only=True)
    ws = wb["RCDCFundingSummary"]
    rows = list(ws.iter_rows(values_only=True))
    headers = [str(h).strip() if h is not None else "" for h in rows[2]]

    fy_col = None
    mortality_col = None
    prevalence_col = None
    for i, h in enumerate(headers):
        if h == "2025":
            fy_col = i
        elif "Mortality" in h:
            mortality_col = i
        elif "Prevalence" in h:
            prevalence_col = i

    by_category: dict[str, dict] = {}
    for row in rows[3:]:
        if not row or not row[0]:
            continue
        name = str(row[0]).strip()
        if not name or name.startswith("Total"):
            continue

        def _val(idx: int | None):
            if idx is None or idx >= len(row):
                return None
            v = row[idx]
            if v in (None, "", "+", "-"):
                return None
            return v

        funding = _val(fy_col)
        mortality = _val(mortality_col)
        prevalence = _val(prevalence_col)

        by_category[name] = {
            "rcdc_category": name,
            "nih_funding_millions_usd": funding,
            "nih_fiscal_year": 2025,
            "us_mortality": mortality,
            "us_prevalence": prevalence,
            "mortality_year": 2024,
            "source": "NIH RCDC / CDC NCHS",
        }
    return by_category


def _match_slug(label: str, query: str, slug: str, categories: dict[str, dict]) -> str | None:
    if slug in SLUG_OVERRIDES and SLUG_OVERRIDES[slug] in categories:
        return SLUG_OVERRIDES[slug]

    for candidate in (label, query, slug.replace("-", " ")):
        cn = _norm(candidate)
        best = None
        best_len = 0
        for cat in categories:
            cat_n = _norm(cat)
            if cat_n == cn:
                return cat
            if cat_n in cn or cn in cat_n:
                if len(cat_n) > best_len:
                    best = cat
                    best_len = len(cat_n)
        if best:
            return best
    return None


def map_slugs(categories: dict[str, dict]) -> tuple[dict[str, dict], dict[str, str]]:
    by_slug: dict[str, dict] = {}
    slug_map: dict[str, str] = {}

    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    else:
        manifest = []

    for entry in manifest:
        slug = entry.get("slug", "")
        label = entry.get("label", "")
        query = entry.get("query", label)
        if not slug:
            continue
        cat = _match_slug(label, query, slug, categories)
        if cat:
            slug_map[slug] = cat
            by_slug[slug] = dict(categories[cat])

    for slug, cat in SLUG_OVERRIDES.items():
        if cat in categories and slug not in by_slug:
            slug_map[slug] = cat
            by_slug[slug] = dict(categories[cat])

    return by_slug, slug_map


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    SEEDS.mkdir(parents=True, exist_ok=True)
    if not XLSX_PATH.exists() or XLSX_PATH.stat().st_size < 1000:
        download_xlsx()

    categories = parse_rcdc()
    by_slug, slug_map = map_slugs(categories)

    from disease_pipeline.adapters.burden.funding_level import enrich_corpus_funding_levels

    by_slug = enrich_corpus_funding_levels(by_slug)

    OUT.write_text(
        json.dumps({
            "source": "NIH RCDC categorical spending export",
            "generated_at": "2026-07-06",
            "by_slug": by_slug,
        }, indent=2),
        encoding="utf-8",
    )
    MAP_OUT.write_text(json.dumps(slug_map, indent=2), encoding="utf-8")
    log.info("Wrote %d slug mappings to %s", len(by_slug), OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())