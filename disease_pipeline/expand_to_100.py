#!/usr/bin/env python3
"""Expand RepurpOS to the canonical 100-disease list from disease_db_100.json."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.main import _configure_logging
from disease_pipeline.options import options_for_phase
from disease_pipeline.output.web_export import to_web_json, web_slug
from disease_pipeline.output.generate_html import write_page
from disease_pipeline.pipeline import build_batch, build_disease_page
from disease_pipeline.published_conditions import biomarker_count, is_publishable
from disease_pipeline.publish_site import main as publish_site

SEEDS_DIR = Path(__file__).parent / "seeds"
DEFAULT_DB = SEEDS_DIR / "disease_db_100.json"
DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"

# Map disease_db_100 label -> Open Targets / pipeline query name.
QUERY_OVERRIDES: dict[str, str] = {
    "Hypertension": "Essential Hypertension",
    "COPD": "Chronic Obstructive Pulmonary Disease",
    "Migraine": "Migraine Disorder",
    "GERD (Gastroesophageal Reflux Disease)": "Gastroesophageal Reflux Disease",
    "NAFLD / MASH (Metabolic-Associated Steatohepatitis)": "Metabolic Dysfunction-Associated Steatohepatitis",
    "ME/CFS (Myalgic Encephalomyelitis / Chronic Fatigue Syndrome)": "Myalgic Encephalomyelitis / Chronic Fatigue Syndrome",
    "Long COVID / Post-Acute COVID Sequelae (PACVS)": "Post-Acute COVID/Vaccination Syndrome",
    "Post-Acute COVID/Vaccination Syndrome": "Post-Acute COVID/Vaccination Syndrome",
    "Stroke (Ischaemic / Cerebrovascular Disease)": "Ischemic Stroke",
    "Psoriasis (Plaque)": "Psoriasis Vulgaris",
    "Psoriasis (Nail / Palmoplantar)": "Psoriasis Vulgaris",
    "Anxiety Disorders": "Anxiety",
    "Atopic Dermatitis (Eczema)": "Atopic Eczema",
    "Insomnia / Sleep Disorders": "Insomnia",
    "PCOS (Polycystic Ovary Syndrome)": "Polycystic Ovary Syndrome",
    "Peripheral Artery Disease (PAD)": "Peripheral Arterial Disease",
    "Ankylosing Spondylitis / Axial Spondyloarthropathy": "Ankylosing Spondylitis",
    "Peripheral Neuropathy (Diabetic Peripheral Neuropathy)": "Diabetic Neuropathy",
    "Pulmonary Arterial Hypertension (PAH)": "Pulmonary Arterial Hypertension",
    "Lyme Disease / Post-Treatment Lyme Disease Syndrome (PTLDS)": "Lyme Disease",
    "Obstructive Sleep Apnoea (OSA)": "Obstructive Sleep Apnea",
    "Benign Prostatic Hyperplasia (BPH)": "Benign Prostatic Hyperplasia",
    "Long COVID / Post-Acute COVID Sequelae (PACVS)": "Post-Acute COVID/Vaccination Syndrome",
    "Non-Hodgkin Lymphoma (NHL)": "Non-Hodgkin Lymphoma",
    "Chronic Lymphocytic Leukaemia (CLL)": "Chronic Lymphocytic Leukemia",
    "Haemophilia A / B": "Hemophilia",
    "Chronic Venous Insufficiency / Venous Leg Ulcers": "Chronic Venous Insufficiency",
    "Thyroid Cancer (Well-Differentiated)": "Thyroid Cancer",
    "Deep Vein Thrombosis / Pulmonary Embolism (VTE)": "Venous Thromboembolism",
    "Myelodysplastic Syndromes (MDS)": "Myelodysplastic Syndrome",
    "Polycystic Kidney Disease (ADPKD)": "Polycystic Kidney Disease",
    "Inflammatory Myopathies (Dermatomyositis / PM / IBM)": "Dermatomyositis",
    "Restless Legs Syndrome (RLS)": "Restless Legs Syndrome",
    "Overactive Bladder (OAB)": "Overactive Bladder",
    "Kidney Stones (Nephrolithiasis)": "Kidney Stones",
    "Interstitial Cystitis / Bladder Pain Syndrome (IC/BPS)": "Interstitial Cystitis",
    "Myasthenia Gravis (MG)": "Myasthenia Gravis",
    "Amyotrophic Lateral Sclerosis (ALS)": "Amyotrophic Lateral Sclerosis",
    "Huntington's Disease": "Huntington Disease",
    "Polycythaemia Vera / Myeloproliferative Neoplasms": "Polycythemia Vera",
    "Immune Thrombocytopaenia (ITP)": "Immune Thrombocytopenia",
    "Chronic Urticaria (CSU)": "Chronic Spontaneous Urticaria",
    "Coeliac Disease (Refractory / RCD)": "Celiac Disease",
    "Alpha-1 Antitrypsin Deficiency (AATD)": "Alpha-1 Antitrypsin Deficiency",
    "Primary Sclerosing Cholangitis (PSC)": "Primary Sclerosing Cholangitis",
    "Inflammatory Bowel Disease (Crohn's / UC)": "Inflammatory Bowel Disease",
    "Alcohol Use Disorder": "Alcohol Abuse",
    "Type 2 Diabetes": "Type 2 Diabetes Mellitus",
    "Type 1 Diabetes": "Type 1 Diabetes Mellitus",
    "Parkinson's Disease": "Parkinson Disease",
    "ADHD": "Attention Deficit-Hyperactivity Disorder",
    "Irritable Bowel Syndrome (IBS)": "Irritable Bowel Syndrome",
    "Systemic Lupus Erythematosus (SLE)": "Systemic Lupus Erythematosus",
    "Age-Related Macular Degeneration (AMD)": "Age-Related Macular Degeneration",
}

# Labels that share an existing RepurpOS slug (dedupe within the 100 list).
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
    "Pancreatic Cancer": "exocrine-pancreatic-carcinoma",
    "Bladder Cancer": "urinary-bladder-carcinoma",
    "Chronic Lymphocytic Leukaemia (CLL)": "b-cell-chronic-lymphocytic-leukemia",
    "Hepatitis B": "hepatitis-b-virus-infection",
    "Obstructive Sleep Apnoea (OSA)": "obstructive-sleep-apnea-syndrome",
    "Acne Vulgaris": "acne",
    "Polycythaemia Vera / Myeloproliferative Neoplasms": "acquired-polycythemia-vera",
    "Primary Sclerosing Cholangitis (PSC)": "sclerosing-cholangitis",
    "Alpha-1 Antitrypsin Deficiency (AATD)": "alpha-1-antitrypsin-deficiency",
}

log = logging.getLogger(__name__)


def _norm(text: str) -> str:
    return " ".join(text.lower().replace("/", " ").replace("-", " ").split())


def _covers_query(query: str, have: dict[str, dict], *, hint: str | None = None) -> bool:
    if hint and hint in have and biomarker_count(have[hint]) > 0:
        return True
    slug = web_slug(query)
    if slug in have and biomarker_count(have[slug]) > 0:
        return True
    qn = _norm(query)
    for data in have.values():
        if not is_publishable(data):
            continue
        for raw in (
            data["condition"].get("name", ""),
            data["condition"].get("shortName", ""),
            data["slug"].replace("-", " "),
        ):
            n = _norm(raw)
            if not n:
                continue
            if qn == n:
                return True
    return False


def load_db(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [row["disease"] for row in payload["diseases"]]


def query_name(label: str) -> str:
    return QUERY_OVERRIDES.get(label, label)


def existing_slugs() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in DATA_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        out[data["slug"]] = data
    return out


def build_plan(db_path: Path) -> tuple[list[str], list[str], dict[str, str]]:
    """Return (unique_queries_to_build, all_labels, label_to_query)."""
    labels = load_db(db_path)
    have = existing_slugs()
    label_to_query = {label: query_name(label) for label in labels}

    # Unique pipeline queries required for the 100 labels.
    needed_queries: list[str] = []
    seen_queries: set[str] = set()
    for label in labels:
        q = label_to_query[label]
        hint = CANONICAL_SLUG_HINTS.get(label)
        if _covers_query(q, have, hint=hint):
            continue
        if q not in seen_queries:
            seen_queries.add(q)
            needed_queries.append(q)
    return needed_queries, labels, label_to_query


async def run_build(
    queries: list[str],
    *,
    phase: int,
    concurrency: int,
    timeout: float,
    dry_run: bool,
) -> list[str]:
    if not queries:
        log.info("No new diseases to build")
        return []

    if dry_run:
        for q in queries:
            log.info("Would build: %s", q)
        return queries

    opts = options_for_phase(
        phase,
        batch_concurrency=concurrency,
        disease_timeout_sec=timeout,
        skip_hmdb=True,
    )
    built: list[str] = []
    for name in queries:
        try:
            page = await build_disease_page(name, opts)
            web = to_web_json(page, cap_display=True)
            if biomarker_count(web) <= 0:
                log.warning("Skip %s — zero biomarkers after build", name)
                continue
            out = DATA_DIR / f"{web['slug']}.json"
            out.write_text(json.dumps(web, indent=2, ensure_ascii=False), encoding="utf-8")
            write_page(web, HTML_DIR)
            built.append(name)
            log.info("Published %s -> %s (%d biomarkers)", name, web["slug"], biomarker_count(web))
        except Exception as exc:
            log.error("Failed %s: %s", name, exc)
    return built


def sync_seed_file(source: Path) -> Path:
    SEEDS_DIR.mkdir(parents=True, exist_ok=True)
    dest = SEEDS_DIR / "disease_db_100.json"
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    return dest


def write_manifest(labels: list[str], label_to_query: dict[str, str]) -> Path:
    have = existing_slugs()
    rows = []
    for label in labels:
        q = label_to_query[label]
        hint = CANONICAL_SLUG_HINTS.get(label)
        slug = hint
        if not slug:
            slug = web_slug(q)
        if slug not in have or biomarker_count(have[slug]) <= 0:
            for data in have.values():
                if not is_publishable(data):
                    continue
                for raw in (
                    data["condition"].get("name", ""),
                    data["condition"].get("shortName", ""),
                ):
                    if _norm(raw) == _norm(q):
                        slug = data["slug"]
                        break
        rows.append(
            {
                "label": label,
                "query": q,
                "slug": slug,
                "in_repurpos": bool(slug and slug in have and biomarker_count(have[slug]) > 0),
            }
        )
    out = SEEDS_DIR / "disease_db_100_manifest.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand RepurpOS to disease_db_100.json")
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="Path to disease_db_100.json",
    )
    parser.add_argument("--phase", type=int, default=6, choices=[1, 2, 3, 4, 5, 6, 7])
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    _configure_logging(args.verbose)
    db_path = sync_seed_file(args.db if args.db.exists() else Path(r"C:/Users/matth/Downloads/disease_db_100.json"))
    queries, labels, label_to_query = build_plan(db_path)
    log.info("100-disease list: %d labels, %d unique queries to build", len(labels), len(queries))
    for q in queries:
        log.info("  + %s", q)

    if args.plan_only or args.dry_run:
        write_manifest(labels, label_to_query)
        if args.dry_run:
            return 0
        return 0

    asyncio.run(
        run_build(
            queries,
            phase=args.phase,
            concurrency=args.concurrency,
            timeout=args.timeout,
            dry_run=False,
        )
    )
    write_manifest(labels, label_to_query)
    publish_site()
    have = [p for p in DATA_DIR.glob("*.json") if is_publishable(json.loads(p.read_text(encoding="utf-8")))]
    log.info("RepurpOS now has %d publishable conditions", len(have))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())