"""
opentargets.py
--------------
Thin GraphQL client for the Open Targets Platform.

Endpoint (verified live): https://api.platform.opentargets.org/api/v4/graphql

Provides:
  resolve_disease(name)          -> best EFO/MONDO id via the search index
  known_drugs(efo_id, size)      -> approved + clinical-stage drugs for the disease
  associated_targets(efo_id, n)  -> top drug-target hits by association score

All calls are defensive: timeouts, one retry, and forgiving JSON parsing so a
schema tweak degrades to empty results instead of crashing the pipeline.
"""

from __future__ import annotations
import time
from typing import Optional
import requests

OT_URL = "https://api.platform.opentargets.org/api/v4/graphql"
_HEADERS = {"Content-Type": "application/json"}


def _post(query: str, variables: dict, timeout: int = 30) -> dict:
    for attempt in range(2):
        try:
            r = requests.post(OT_URL, json={"query": query, "variables": variables},
                              headers=_HEADERS, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
                # surface but don't crash
                print(f"  [open-targets] GraphQL errors: {data['errors'][:1]}")
            return data.get("data", {}) or {}
        except Exception as e:
            if attempt == 0:
                time.sleep(1.5)
                continue
            print(f"  [open-targets] request failed: {e}")
            return {}
    return {}


_SEARCH = """
query Resolve($q: String!) {
  search(queryString: $q, entityNames: ["disease"], page: {index: 0, size: 5}) {
    hits { id name entity }
  }
}
"""

def resolve_disease(name: str) -> Optional[str]:
    """Return the top disease EFO/MONDO id for a free-text name, or None."""
    data = _post(_SEARCH, {"q": name})
    hits = (data.get("search") or {}).get("hits") or []
    for h in hits:
        if h.get("entity") == "disease" and h.get("id"):
            return h["id"]
    return None


_KNOWN_DRUGS = """
query Drugs($efoId: String!, $size: Int!) {
  disease(efoId: $efoId) {
    id
    name
    knownDrugs(size: $size) {
      count
      uniqueDrugs
      rows {
        phase
        status
        mechanismOfAction
        drug { id name isApproved drugType }
        target { approvedSymbol }
      }
    }
  }
}
"""

def known_drugs(efo_id: str, size: int = 50) -> list[dict]:
    """
    Approved + clinical-stage drugs linked to the disease (ChEMBL-sourced).
    Returns a de-duplicated list sorted by trial phase (approved/late first).
    """
    data = _post(_KNOWN_DRUGS, {"efoId": efo_id, "size": size})
    disease = data.get("disease") or {}
    kd = disease.get("knownDrugs") or {}
    rows = kd.get("rows") or []
    seen, out = set(), []
    for row in rows:
        drug = row.get("drug") or {}
        did = drug.get("id")
        if not did or did in seen:
            continue
        seen.add(did)
        out.append({
            "drug_id": did,
            "drug": drug.get("name"),
            "approved": bool(drug.get("isApproved")),
            "type": drug.get("drugType"),
            "max_phase": row.get("phase"),
            "moa": row.get("mechanismOfAction"),
            "target": (row.get("target") or {}).get("approvedSymbol"),
        })
    out.sort(key=lambda d: (d["approved"], d["max_phase"] or 0), reverse=True)
    return out


_ASSOC_TARGETS = """
query Targets($efoId: String!, $size: Int!) {
  disease(efoId: $efoId) {
    id
    associatedTargets(page: {index: 0, size: $size}) {
      count
      rows {
        score
        target { id approvedSymbol approvedName }
      }
    }
  }
}
"""

def associated_targets(efo_id: str, n: int = 15) -> list[dict]:
    """Top target-disease associations by overall score (potential drug targets)."""
    data = _post(_ASSOC_TARGETS, {"efoId": efo_id, "size": n})
    disease = data.get("disease") or {}
    at = disease.get("associatedTargets") or {}
    out = []
    for row in at.get("rows") or []:
        tgt = row.get("target") or {}
        out.append({
            "target_id": tgt.get("id"),
            "symbol": tgt.get("approvedSymbol"),
            "name": tgt.get("approvedName"),
            "score": round(row.get("score") or 0.0, 4),
        })
    return out
