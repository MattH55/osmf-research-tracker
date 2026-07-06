"""KNApSAcK Family — plant metabolites by disease."""
from __future__ import annotations

import logging
import re

import aiohttp

from ....config import BROWSER_USER_AGENT, HTTP_TIMEOUT

log = logging.getLogger(__name__)

KNAPSACK_BASE = "http://www.knapsackfamily.com"


async def query_disease(disease_name: str, session: aiohttp.ClientSession) -> list[dict]:
    url = f"{KNAPSACK_BASE}/disease/result.php"
    try:
        async with session.get(
            url,
            params={"sname": "human diseases", "word": disease_name},
            headers={"User-Agent": BROWSER_USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                return []
            html = await resp.text(errors="replace")
    except Exception as e:
        log.debug("[KNApSAcK] failed: %s", e)
        return []

    rows = []
    for line in html.splitlines():
        if "<td" not in line.lower():
            continue
        cells = re.findall(r"<td[^>]*>([^<]+)</td>", line, re.I)
        if len(cells) >= 3:
            rows.append({
                "knapsack_id": cells[0].strip(),
                "metabolite_name": cells[1].strip(),
                "source_species": cells[2].strip() if len(cells) > 2 else "",
                "reference": cells[-1].strip() if len(cells) > 3 else "",
                "source": "KNApSAcK",
            })
    return rows[:80]