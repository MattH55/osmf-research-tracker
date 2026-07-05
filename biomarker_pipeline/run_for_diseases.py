#!/usr/bin/env python3
"""
Batch runner — reads cure_vs_chronic_batch1.csv and runs the biomarker
discovery pipeline for each disease's key biomarkers.

Results land in:
    research-tracker/biomarker_pipeline/results/biomarkers/{disease-slug}/{GENE}.json

A summary JSON is written to:
    research-tracker/biomarker_pipeline/results/biomarkers/run_summary.json

Usage:
    # from research-tracker/ directory:
    python -m biomarker_pipeline.run_for_diseases
    python -m biomarker_pipeline.run_for_diseases --csv ../../cure_vs_chronic_batch1.csv
    python -m biomarker_pipeline.run_for_diseases --skip-llm --skip-existing

Environment variables:
    NCBI_API_KEY        — optional NCBI E-utilities key
    ANTHROPIC_API_KEY   — required for Stage 4 LLM extraction
"""
import argparse
import asyncio
import csv
import json
import logging
import os
import re
import sys
from pathlib import Path

# Support both `python run_for_diseases.py` and `python -m biomarker_pipeline.run_for_diseases`
_PACKAGE_ROOT = Path(__file__).parent.parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

from biomarker_pipeline.disease_biomarkers import get_biomarkers_for_disease
from biomarker_pipeline.run_pipeline import find_agents_for_biomarker, _configure_logging

log = logging.getLogger(__name__)

# Default CSV path: two directories above this file (project root)
DEFAULT_CSV  = Path(__file__).parent.parent.parent / "cure_vs_chronic_batch1.csv"
RESULTS_DIR  = Path(__file__).parent / "results" / "biomarkers"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def _process_disease(
    disease: str,
    ncbi_key: str,
    anthropic_key: str,
    skip_llm: bool,
    skip_existing: bool,
) -> dict:
    biomarkers = get_biomarkers_for_disease(disease)
    if not biomarkers:
        log.warning("No biomarkers mapped for disease: '%s'", disease)
        return {"disease": disease, "biomarkers": [], "error": "no biomarker mapping"}

    disease_dir = RESULTS_DIR / _slug(disease)
    disease_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for bm in biomarkers:
        out_path = disease_dir / f"{bm}.json"
        if skip_existing and out_path.exists():
            log.info("  SKIP existing: %s / %s", disease, bm)
            results.append({"biomarker": bm, "skipped": True, "path": str(out_path)})
            continue

        log.info("  Processing %s / %s", disease, bm)
        try:
            output = await find_agents_for_biomarker(
                biomarker=bm,
                ncbi_api_key=ncbi_key,
                anthropic_api_key=anthropic_key,
                skip_llm=skip_llm,
            )
            out_path.write_text(output.model_dump_json(indent=2), encoding="utf-8")
            results.append({
                "biomarker": bm,
                "agents_found": len(output.agents),
                "path": str(out_path),
            })
            log.info("    → %d agents written to %s", len(output.agents), out_path.name)
        except Exception as e:
            log.error("    FAILED %s / %s: %s", disease, bm, e)
            results.append({"biomarker": bm, "error": str(e)})

        # Polite delay between biomarkers
        await asyncio.sleep(1.5)

    return {"disease": disease, "biomarkers": results}


async def _main(args: argparse.Namespace) -> None:
    csv_path = Path(args.csv)
    if not csv_path.exists():
        log.error("CSV not found: %s", csv_path)
        sys.exit(1)

    diseases: list[str] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            disease = (row.get("disease") or "").strip()
            if disease:
                diseases.append(disease)

    log.info("Found %d diseases in %s", len(diseases), csv_path.name)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    ncbi_key      = os.environ.get("NCBI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not anthropic_key and not args.skip_llm:
        log.warning(
            "ANTHROPIC_API_KEY not set — Stage 4 will be skipped for all diseases.  "
            "Pass --skip-llm to suppress this warning."
        )

    summary: list[dict] = []
    for disease in diseases:
        log.info("=" * 64)
        log.info("Disease: %s", disease)
        result = await _process_disease(
            disease,
            ncbi_key=ncbi_key,
            anthropic_key=anthropic_key,
            skip_llm=args.skip_llm,
            skip_existing=args.skip_existing,
        )
        summary.append(result)
        # Courtesy delay between diseases
        await asyncio.sleep(2)

    summary_path = RESULTS_DIR / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("Run complete.  Summary: %s", summary_path)

    total_agents = sum(
        b.get("agents_found", 0)
        for d in summary
        for b in d.get("biomarkers", [])
        if isinstance(b, dict)
    )
    log.info("Total agents found across all diseases: %d", total_agents)


def main() -> None:
    _configure_logging()

    parser = argparse.ArgumentParser(
        description="Run biomarker pipeline for all diseases in cure_vs_chronic_batch1.csv"
    )
    parser.add_argument(
        "--csv",
        default=str(DEFAULT_CSV),
        help=f"Path to disease CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument("--skip-llm", action="store_true", help="Skip Stage 4 LLM extraction")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip biomarkers that already have an output JSON",
    )
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
