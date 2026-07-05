"""Open Targets Platform adapter (v4 — drugAndClinicalCandidates)."""
from __future__ import annotations

from ..http_util import request_json
from ..models import NormalizedBiomarker, RawHit

OT_URL = "https://api.platform.opentargets.org/api/v4/graphql"

QUERY = """
query target($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    approvedSymbol
    drugAndClinicalCandidates {
      rows {
        maxClinicalStage
        drug { name id maximumClinicalStage }
      }
    }
  }
}
"""


def query_opentargets(norm: NormalizedBiomarker) -> list[RawHit]:
    if not norm.ensembl_id:
        return []
    data = request_json(
        "opentargets",
        norm.ensembl_id,
        "POST",
        OT_URL,
        json_body={"query": QUERY, "variables": {"ensemblId": norm.ensembl_id}},
        headers={"Content-Type": "application/json"},
    )
    target = (data.get("data") or {}).get("target") or {}
    rows = (target.get("drugAndClinicalCandidates") or {}).get("rows") or []
    hits: list[RawHit] = []
    for row in rows:
        drug = row.get("drug") or {}
        name = drug.get("name")
        if not name:
            continue
        hits.append(
            RawHit(
                agent=name,
                agent_id=drug.get("id"),
                interaction_type=f"clinical_stage:{row.get('maxClinicalStage') or drug.get('maximumClinicalStage')}",
                direction_hint="modulates",
                source="OpenTargets",
                source_url=f"https://platform.opentargets.org/target/{norm.ensembl_id}",
                raw=row,
            )
        )
    return hits