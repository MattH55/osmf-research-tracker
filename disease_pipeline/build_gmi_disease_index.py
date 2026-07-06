#!/usr/bin/env python3
"""Build GreenMedInfo disease slug index from /greenmed/display/disease."""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.adapters.natural_products.gmi_disease_index import refresh_gmi_disease_index
from disease_pipeline.http_util import default_session

log = logging.getLogger(__name__)


async def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    async with default_session() as session:
        slugs = await refresh_gmi_disease_index(session, use_cache=False)
    log.info("Wrote %d disease slugs to seeds/gmi_disease_index.json", len(slugs))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))