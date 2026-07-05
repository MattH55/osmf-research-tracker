#!/usr/bin/env python3
"""Print Open Targets disease hits for pilot diseases."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_PACKAGE = Path(__file__).parent.parent
if str(_PACKAGE.parent) not in sys.path:
    sys.path.insert(0, str(_PACKAGE.parent))

from disease_pipeline.config import OPEN_TARGETS_URL
from disease_pipeline.http_util import default_session, graphql

NAMES = [
    "Asthma",
    "COPD",
    "Hypertension (essential)",
    "Chronic Kidney Disease",
    "Major Depressive Disorder",
]

QUERY = """
query Search($query: String!) {
  search(queryString: $query, entityNames: ["disease"], page: {index: 0, size: 3}) {
    hits { id name }
  }
}
"""


async def main() -> None:
    async with default_session() as session:
        for name in NAMES:
            data = await graphql(session, OPEN_TARGETS_URL, QUERY, {"query": name})
            hits = (data.get("data") or {}).get("search", {}).get("hits") or []
            print(f"\n{name}:")
            for h in hits:
                print(f"  {h.get('id')}  {h.get('name')}")


if __name__ == "__main__":
    asyncio.run(main())