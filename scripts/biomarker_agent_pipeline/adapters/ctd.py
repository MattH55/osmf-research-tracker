"""CTD (Comparative Toxicogenomics Database) adapter via batch query API."""
from __future__ import annotations

import csv
import io

from ..http_util import request_json
from ..models import NormalizedBiomarker, RawHit

CTD_BATCH = "https://ctdbase.org/tools/batchQuery.go"


def query_ctd(norm: NormalizedBiomarker) -> list[RawHit]:
    if not norm.symbol:
        return []
    # CTD returns TSV for chemical-gene interactions
    params = {
        "inputType": "gene",
        "inputTerms": norm.symbol,
        "report": "cgixns",
        "format": "tsv",
    }
    try:
        import httpx

        with httpx.Client(timeout=15) as client:
            resp = client.get(CTD_BATCH, params=params)
            resp.raise_for_status()
            text = resp.text
    except Exception:
        return []

    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    hits: list[RawHit] = []
    seen = set()
    for row in reader:
        chem = row.get("ChemicalName") or row.get("Chemical Name")
        if not chem:
            continue
        key = chem.lower()
        if key in seen:
            continue
        seen.add(key)
        interaction = row.get("Interaction") or row.get("InteractionActions") or ""
        direction = "unclear"
        low = interaction.lower()
        if "decreases" in low or "downregulates" in low:
            direction = "decreases"
        elif "increases" in low or "upregulates" in low:
            direction = "increases"
        hits.append(
            RawHit(
                agent=chem,
                agent_id=row.get("CasRN") or row.get("ChemicalID"),
                interaction_type=interaction[:120] if interaction else None,
                direction_hint=direction,
                source="CTD",
                source_url="https://ctdbase.org/",
                raw=dict(row),
            )
        )
    return hits[:80]