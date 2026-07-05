"""ChEMBL bioactivity adapter."""
from __future__ import annotations

import json

from ..http_util import request_json
from ..models import NormalizedBiomarker, RawHit

CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"


def _target_id(uniprot: str) -> str | None:
    data = request_json(
        "chembl_target",
        uniprot,
        "GET",
        f"{CHEMBL}/target.json",
        params={"target_components__accession": uniprot, "limit": 1},
    )
    targets = data.get("targets", [])
    return targets[0]["target_chembl_id"] if targets else None


def query_chembl(norm: NormalizedBiomarker) -> list[RawHit]:
    if not norm.uniprot_id:
        return []
    tid = _target_id(norm.uniprot_id)
    if not tid:
        return []
    norm.chembl_target_id = tid
    data = request_json(
        "chembl_activity",
        tid,
        "GET",
        f"{CHEMBL}/activity.json",
        params={"target_chembl_id": tid, "limit": 100, "standard_type__in": "IC50,Ki,EC50"},
    )
    hits: list[RawHit] = []
    seen = set()
    for act in data.get("activities", []):
        mol = act.get("molecule_chembl_id")
        if not mol or mol in seen:
            continue
        seen.add(mol)
        name = act.get("molecule_pref_name") or mol
        measure = act.get("standard_type")
        action = act.get("action_type")
        if isinstance(action, dict):
            action = action.get("action_type") or action.get("description") or json.dumps(action)
        elif isinstance(action, list):
            action = ", ".join(str(a) for a in action)
        hits.append(
            RawHit(
                agent=name,
                agent_id=mol,
                interaction_type=str(action) if action else "binding",
                direction_hint="inhibits" if measure in {"IC50", "Ki"} else "modulates",
                source="ChEMBL",
                source_url=f"https://www.ebi.ac.uk/chembl/compound_report_card/{mol}/",
                potency={
                    "value": act.get("standard_value"),
                    "unit": act.get("standard_units"),
                    "measure": measure,
                },
                raw=act,
            )
        )
    return hits[:60]