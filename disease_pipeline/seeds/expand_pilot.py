#!/usr/bin/env python3
"""Resolve and add a small set of diseases to seeds/disease_ids.json."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

_PACKAGE = Path(__file__).parent.parent
if str(_PACKAGE.parent) not in sys.path:
    sys.path.insert(0, str(_PACKAGE.parent))

from disease_pipeline.adapters.normalize import normalize_disease, seed_key
from disease_pipeline.config import SEEDS_PATH
from disease_pipeline.http_util import default_session

PILOT = [
    "Asthma",
    "COPD",
    "Hypertension (essential)",
    "Chronic Kidney Disease",
    "Major Depressive Disorder",
]

log = logging.getLogger(__name__)


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    existing = json.loads(SEEDS_PATH.read_text(encoding="utf-8")) if SEEDS_PATH.exists() else {}
    async with default_session() as session:
        for name in PILOT:
            log.info("Resolving %s", name)
            ids = await normalize_disease(name, session)
            key = seed_key(name)
            existing[key] = {
                "name": ids.name,
                "mondo_id": ids.mondo_id,
                "efo_id": ids.efo_id,
                "omim_id": ids.omim_id,
                "orpha_id": ids.orpha_id,
                "mesh_id": ids.mesh_id,
                "umls_cui": ids.umls_cui,
            }
            await asyncio.sleep(0.5)
    SEEDS_PATH.write_text(json.dumps(existing, indent=2, sort_keys=True), encoding="utf-8")
    log.info("Wrote %d entries to %s", len(existing), SEEDS_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))