"""
opentargets.py — GraphQL client for Open Targets Platform v4.
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
            r = requests.post(
                OT_URL,
                json={"query": query, "variables": variables},
                headers=_HEADERS,
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
            if "errors" in data:
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
query Search($query: String!) {
  search(queryString: $query, entityNames: ["disease"], page: {index: 0, size: 5}) {
    hits { id name entity }
  }
}
"""


def resolve_disease(name: str) -> Optional[str]:
    data = _post(_SEARCH, {"query": name})
    hits = (data.get("search") or {}).get("hits") or []
    for h in hits:
        if h.get("entity") == "disease" and h.get("id"):
            return h["id"]
    return None


_KNOWN_DRUGS = """
query DiseaseKnownDrugs($efoId: String!) {
  disease(efoId: $efoId) {
    id
    name
    drugAndClinicalCandidates {
      rows {
        id
        maxClinicalStage
        drug { id name drugType }
      }
    }
  }
}
"""


def _phase_to_int(stage: str | None) -> int:
    if not stage:
        return 0
    s = str(stage).upper()
    if "APPROVED" in s or "PHASE_IV" in s or "PHASE 4" in s:
        return 4
    if "PHASE_III" in s or "PHASE 3" in s:
        return 3
    if "PHASE_II" in s or "PHASE 2" in s:
        return 2
    if "PHASE_I" in s or "PHASE 1" in s:
        return 1
    return 0


def known_drugs(efo_id: str, size: int = 50) -> list[dict]:
    data = _post(_KNOWN_DRUGS, {"efoId": efo_id})
    disease = data.get("disease") or {}
    rows = (disease.get("drugAndClinicalCandidates") or {}).get("rows") or []
    seen, out = set(), []
    for row in rows:
        drug = row.get("drug") or {}
        did = drug.get("id")
        if not did or did in seen:
            continue
        seen.add(did)
        phase = _phase_to_int(row.get("maxClinicalStage"))
        out.append({
            "drug_id": did,
            "drug": drug.get("name"),
            "approved": phase >= 4,
            "type": drug.get("drugType"),
            "max_phase": phase,
            "moa": None,
            "target": None,
        })
    out.sort(key=lambda d: (d["approved"], d["max_phase"] or 0), reverse=True)
    return out[:size]


_ASSOC_TARGETS = """
query Targets($efoId: String!) {
  disease(efoId: $efoId) {
    id
    associatedTargets(page: {index: 0, size: 15}) {
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
    data = _post(_ASSOC_TARGETS, {"efoId": efo_id})
    disease = data.get("disease") or {}
    at = disease.get("associatedTargets") or {}
    out = []
    for row in (at.get("rows") or [])[:n]:
        tgt = row.get("target") or {}
        out.append({
            "target_id": tgt.get("id"),
            "symbol": tgt.get("approvedSymbol"),
            "name": tgt.get("approvedName"),
            "score": round(row.get("score") or 0.0, 4),
        })
    return out