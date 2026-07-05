#!/usr/bin/env python3
"""Populate seeds/disease_ids.json from live API resolution."""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path

import aiohttp

_PACKAGE = Path(__file__).parent.parent
if str(_PACKAGE.parent) not in sys.path:
    sys.path.insert(0, str(_PACKAGE.parent))

from disease_pipeline.adapters.normalize import normalize_disease, seed_key
from disease_pipeline.config import SEEDS_PATH
from disease_pipeline.http_util import default_session

log = logging.getLogger(__name__)

EXTRA_DISEASES = [
    "GERD (Gastroesophageal Reflux Disease)",
    "Hepatitis C",
    "Long COVID",
    "ME/CFS",
    "Lyme / PTLDS",
    "Gulf War Illness",
    "PACVS",
]


async def _resolve_all(names: list[str], delay: float) -> dict[str, dict]:
    seeds: dict[str, dict] = {}
    async with default_session() as session:
        for i, name in enumerate(names):
            log.info("[%d/%d] Resolving %s", i + 1, len(names), name)
            ids = await normalize_disease(name, session)
            key = seed_key(name)
            seeds[key] = {
                "name": ids.name,
                "mondo_id": ids.mondo_id,
                "efo_id": ids.efo_id,
                "omim_id": ids.omim_id,
                "orpha_id": ids.orpha_id,
                "mesh_id": ids.mesh_id,
                "umls_cui": ids.umls_cui,
            }
            if delay > 0:
                await asyncio.sleep(delay)
    return seeds


def _load_csv_diseases(csv_path: Path) -> list[str]:
    names: list[str] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            disease = row.get("disease", "").strip()
            if disease:
                names.append(disease)
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description="Build disease identifier seeds file")
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(__file__).parent.parent.parent / "cure_vs_chronic_50.csv",
    )
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API calls")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    names = _load_csv_diseases(args.csv)
    for extra in EXTRA_DISEASES:
        if extra not in names:
            names.append(extra)

    if SEEDS_PATH.exists():
        existing = json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    else:
        existing = {}

    seeds = asyncio.run(_resolve_all(names, args.delay))
    existing.update(seeds)

    if args.dry_run:
        print(json.dumps(existing, indent=2))
        return 0

    SEEDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEDS_PATH.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    log.info("Wrote %d entries to %s", len(existing), SEEDS_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())