"""Europe PMC client — module 2 (study discovery), used for the manual/literature
sweep leg of discovery (GWAS Catalog + OT study index cover the catalogued leg).
"""
from __future__ import annotations

import httpx

from ..config import EUROPEPMC_BASE


def search(query: str, page_size: int = 15, sort: str | None = "P_PDATE_D desc") -> dict:
    params = {"query": query, "format": "json", "pageSize": page_size}
    if sort:
        params["sort"] = sort
    resp = httpx.get(f"{EUROPEPMC_BASE}/search", params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def hit_count(query: str) -> int:
    return search(query, page_size=1).get("hitCount", 0)


def titles(query: str, page_size: int = 15) -> list[dict]:
    data = search(query, page_size=page_size)
    return [
        {"pmid": r.get("pmid") or r.get("id"), "year": r.get("pubYear"), "title": r.get("title")}
        for r in data.get("resultList", {}).get("result", [])
    ]
