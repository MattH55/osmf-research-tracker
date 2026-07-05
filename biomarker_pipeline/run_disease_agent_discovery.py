#!/usr/bin/env python3
"""Run disease-level agent discovery (search FROM the disease, not from a
gene panel) and write results/disease_agents/{slug}.json.

Usage (from research-tracker/):
    python -m biomarker_pipeline.run_disease_agent_discovery --disease "Asthma" --slug asthma
"""
import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).parent.parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

import httpx

from biomarker_pipeline.run_pipeline import _configure_logging
from biomarker_pipeline.stage_disease_agents import find_agents_for_disease

log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results" / "disease_agents"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def _main(args: argparse.Namespace) -> None:
    slug = args.slug or _slug(args.disease)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(
        headers={"User-Agent": "OSMF-BiomarkerAtlasPipeline/0.1 (research@opensourcemed.info)"},
        follow_redirects=True,
        timeout=30,
    ) as client:
        output = await find_agents_for_disease(args.disease, client, max_trials=args.max_trials)

    out_path = RESULTS_DIR / f"{slug}.json"
    out_path.write_text(output.model_dump_json(indent=2), encoding="utf-8")
    log.info(
        "%s → %d candidate agents (%d with trial evidence, %d with Open Targets target) → %s",
        args.disease,
        len(output.candidates),
        sum(1 for c in output.candidates if c.trial_evidence),
        sum(1 for c in output.candidates if c.target_genes),
        out_path,
    )
    for note in output.coverage_notes:
        log.info("  note: %s", note)


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Disease-level agent discovery (not gene-first)")
    parser.add_argument("--disease", required=True, help='Canonical disease name, e.g. "Asthma"')
    parser.add_argument("--slug", default=None)
    parser.add_argument("--max-trials", type=int, default=100)
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
