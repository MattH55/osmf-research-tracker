#!/usr/bin/env python3
"""Run disease-level agent discovery (stage_disease_agents.py) for every
disease that has an existing chronic-disease-interventions/{slug}.html page,
then regenerate each page with the fresh results.

Slug <-> canonical disease name <-> CSV row name are three different strings
in this codebase (see the Type 2 Diabetes "Mellitus" mismatch caught during
the asthma/type-2-diabetes pilot) — this table is the single source of truth
mapping all three, built by cross-referencing disease_biomarkers.py's
canonical keys, cure_vs_chronic_50.csv's disease column, and the slugs
already on disk, so this never silently creates a duplicate/orphan page.

Usage (from research-tracker/):
    python -m biomarker_pipeline.run_all_disease_agents
    python -m biomarker_pipeline.run_all_disease_agents --skip-existing
"""
import argparse
import asyncio
import csv
import logging
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).parent.parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

import httpx

from biomarker_pipeline.generate_disease_pages import (
    CSV_PATH, OUTPUT_DIR, build_page, _fetch_trials, _load_disease_agents, _load_pipeline_results,
)
from biomarker_pipeline.run_pipeline import _configure_logging
from biomarker_pipeline.stage_disease_agents import find_agents_for_disease

log = logging.getLogger(__name__)

DISEASE_AGENTS_DIR = Path(__file__).parent / "results" / "disease_agents"

# (slug, canonical disease name for gene panel / agent search / page content,
#  CSV disease-column name for remission stats, or None if no CSV row exists)
DISEASES: list[tuple[str, str, str | None]] = [
    ("type-2-diabetes", "Type 2 Diabetes", "Type 2 Diabetes Mellitus"),
    ("type-1-diabetes", "Type 1 Diabetes", "Type 1 Diabetes Mellitus"),
    ("hypertension", "Hypertension", "Hypertension (essential)"),
    ("chronic-kidney-disease", "Chronic Kidney Disease", "Chronic Kidney Disease"),
    ("nafld-mash-metabolic-associated-steatohepatitis", "NAFLD / MASH (Metabolic-Associated Steatohepatitis)", "NAFLD / MASH (Metabolic-Associated Steatohepatitis)"),
    ("atrial-fibrillation", "Atrial Fibrillation", "Atrial Fibrillation"),
    ("copd", "COPD", "COPD"),
    ("asthma", "Asthma", "Asthma"),
    ("osteoarthritis", "Osteoarthritis", "Osteoarthritis"),
    ("low-back-pain", "Low Back Pain", "Low Back Pain"),
    ("rheumatoid-arthritis", "Rheumatoid Arthritis", "Rheumatoid Arthritis"),
    ("alzheimer-s-disease-and-other-dementias", "Alzheimer's Disease and Other Dementias", "Alzheimer's Disease and Other Dementias"),
    ("multiple-sclerosis", "Multiple Sclerosis", "Multiple Sclerosis"),
    ("epilepsy", "Epilepsy", "Epilepsy"),
    ("migraine", "Migraine", "Migraine"),
    ("major-depressive-disorder", "Major Depressive Disorder", "Major Depressive Disorder"),
    ("inflammatory-bowel-disease-crohn-s-uc", "Inflammatory Bowel Disease (Crohn's/UC)", "Inflammatory Bowel Disease (Crohn's/UC)"),
    ("gerd-gastroesophageal-reflux-disease", "GERD (Gastroesophageal Reflux Disease)", None),
    ("hepatitis-c", "Hepatitis C", None),
    ("hypothyroidism", "Hypothyroidism", "Hypothyroidism"),
]


def _load_csv_rows() -> dict[str, dict]:
    rows = {}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("disease", "").strip()
            if name:
                rows[name] = row
    return rows


async def _main(args: argparse.Namespace) -> None:
    csv_rows = _load_csv_rows()
    DISEASE_AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    summary: list[dict] = []

    async with httpx.AsyncClient(
        headers={"User-Agent": "OSMF-BiomarkerAtlasPipeline/0.1 (research@opensourcemed.info)"},
        follow_redirects=True,
        timeout=30,
    ) as client:
        for slug, disease, csv_name in DISEASES:
            out_json = DISEASE_AGENTS_DIR / f"{slug}.json"
            if args.skip_existing and out_json.exists():
                log.info("SKIP existing disease-agents: %s", slug)
            else:
                log.info("=" * 64)
                log.info("Disease-level agent discovery: %s (%s)", disease, slug)
                try:
                    output = await find_agents_for_disease(disease, client, max_trials=args.max_trials)
                    out_json.write_text(output.model_dump_json(indent=2), encoding="utf-8")
                    n_approved = sum(1 for c in output.candidates if c.approval_status == "Approved")
                    n_trial = sum(1 for c in output.candidates if c.trial_evidence)
                    log.info(
                        "  %d candidates (%d approved, %d with trial evidence)",
                        len(output.candidates), n_approved, n_trial,
                    )
                    summary.append({"slug": slug, "disease": disease, "candidates": len(output.candidates)})
                except Exception as e:
                    log.error("  FAILED: %s", e)
                    summary.append({"slug": slug, "disease": disease, "error": str(e)})
                await asyncio.sleep(1.5)  # courtesy delay

            if not args.skip_pages:
                log.info("  Regenerating page for %s", slug)
                csv_row = csv_rows.get(csv_name, {}) if csv_name else {}
                pipeline_data = _load_pipeline_results(disease)
                disease_agents = _load_disease_agents(disease)
                if args.skip_trials:
                    trials = []
                else:
                    trials = _fetch_trials(disease)
                    await asyncio.sleep(0.5)
                html = build_page(disease, csv_row, pipeline_data, trials, disease_agents)
                out_path = OUTPUT_DIR / f"{slug}.html"
                out_path.write_text(html, encoding="utf-8")
                log.info("  Written: %s", out_path)

    log.info("=" * 64)
    log.info("Done. %d diseases processed.", len(DISEASES))
    for s in summary:
        if "error" in s:
            log.warning("  %s: ERROR — %s", s["slug"], s["error"])
        else:
            log.info("  %s: %d candidates", s["slug"], s["candidates"])


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Run disease-level agent discovery for all 20 chronic-disease-interventions diseases")
    parser.add_argument("--max-trials", type=int, default=60)
    parser.add_argument("--skip-existing", action="store_true", help="Skip diseases that already have disease_agents results")
    parser.add_argument("--skip-pages", action="store_true", help="Only run discovery, don't regenerate HTML pages")
    parser.add_argument("--skip-trials", action="store_true", help="Skip live ClinicalTrials.gov fetch when regenerating pages")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
