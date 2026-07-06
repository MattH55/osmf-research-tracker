#!/usr/bin/env python3
"""Build seeds/gbd_cause_map.json from IHME GBD cause API + disease manifest."""
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

from disease_pipeline.adapters.remission.gbd import lookup_cause_id
from disease_pipeline.http_util import default_session

SEEDS = Path(__file__).parent / "seeds"
MANIFEST = SEEDS / "disease_db_100_manifest.json"
OUT = SEEDS / "gbd_cause_map.json"

log = logging.getLogger(__name__)


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max diseases to query (0=all)")
    args = parser.parse_args()

    if not MANIFEST.exists():
        log.error("Missing %s", MANIFEST)
        return 1

    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    by_slug: dict[str, int] = {}
    if OUT.exists():
        existing = json.loads(OUT.read_text(encoding="utf-8"))
        by_slug = {k: int(v) for k, v in existing.get("by_slug", {}).items()}

    async with default_session() as session:
        for i, row in enumerate(rows):
            if args.limit and i >= args.limit:
                break
            slug = row.get("slug", "")
            query = row.get("query") or row.get("label", "")
            if not slug or slug in by_slug:
                continue
            cause_id = await lookup_cause_id(query, session)
            if cause_id:
                by_slug[slug] = cause_id
                log.info("%s -> cause_id %d", slug, cause_id)
            await asyncio.sleep(0.3)

    payload = {"source": "IHME GBD API", "by_slug": by_slug}
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("Wrote %d mappings to %s", len(by_slug), OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))