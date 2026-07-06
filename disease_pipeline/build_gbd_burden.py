#!/usr/bin/env python3
"""Fetch IHME GBD USA DALYs/deaths and write seeds/gbd_burden_usa.json."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.adapters.burden.gbd_burden import fetch_gbd_burden
from disease_pipeline.http_util import default_session

SEEDS = Path(__file__).parent / "seeds"
MANIFEST = SEEDS / "disease_db_100_manifest.json"
OUT = SEEDS / "gbd_burden_usa.json"

log = logging.getLogger(__name__)


async def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_slug: dict[str, dict] = {}
    if OUT.exists():
        existing = json.loads(OUT.read_text(encoding="utf-8"))
        by_slug = existing.get("by_slug", {})

    async with default_session() as session:
        for i, row in enumerate(rows):
            if args.limit and i >= args.limit:
                break
            slug = row.get("slug", "")
            query = row.get("query") or row.get("label", "")
            if not slug or slug in by_slug:
                continue
            burden = await fetch_gbd_burden(slug, query, session)
            if burden:
                by_slug[slug] = burden
                log.info("%s: DALYs=%s deaths=%s", slug, burden.get("us_dalys"), burden.get("us_deaths"))
            await asyncio.sleep(0.25)

    OUT.write_text(
        json.dumps({"source": "IHME GBD API", "by_slug": by_slug}, indent=2),
        encoding="utf-8",
    )
    log.info("Wrote %d entries to %s", len(by_slug), OUT)
    return 0 if by_slug else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))