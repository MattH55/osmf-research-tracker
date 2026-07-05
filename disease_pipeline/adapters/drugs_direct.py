"""Module 4 — Disease → direct therapeutic associations."""
from __future__ import annotations

import logging
import re

import aiohttp

from ..cache import cache_get, cache_set
from ..config import CHEMBL_URL, DGIDB_URL, OPEN_TARGETS_URL
from ..http_util import get_json, graphql
from ..models import DiseaseIdentifiers, EvidenceTier, Therapeutic
from ..options import PipelineOptions
from .ot_ids import ot_disease_id

log = logging.getLogger(__name__)

OT_DRUGS_QUERY = """
query DiseaseKnownDrugs($efoId: String!) {
  disease(efoId: $efoId) {
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

DGIDB_DISEASE_QUERY = """
query DiseaseDrugs($name: String!) {
  diseases(name: $name) {
    nodes {
      name
      drugInteractions {
        drug { name conceptId }
        interactionScore
      }
    }
  }
}
"""

_PHASE_MAP = {
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4,
    "PHASE1": 1, "PHASE2": 2, "PHASE3": 3, "PHASE4": 4,
    "PHASE_1": 1, "PHASE_2": 2, "PHASE_3": 3, "PHASE_4": 4,
}


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


def _phase_to_int(phase, status: str | None = None) -> int:
    if status and "approved" in str(status).lower():
        return 4
    if phase is None:
        return 0
    if isinstance(phase, (int, float)):
        return min(int(phase), 4)
    s = str(phase).upper()
    for label, val in _PHASE_MAP.items():
        if label in s:
            return val
    if "APPROVED" in s:
        return 4
    return 0


def _normalize_drug_type(raw: str | None) -> str:
    t = (raw or "").lower()
    if "antibody" in t or "protein" in t or "biologic" in t:
        return "biologic"
    if "gene" in t:
        return "gene_therapy"
    if "cell" in t:
        return "cell_therapy"
    return "small_molecule"


async def _open_targets_drugs(
    identifiers: DiseaseIdentifiers, session: aiohttp.ClientSession
) -> list[Therapeutic]:
    ot_id = ot_disease_id(identifiers)
    if not ot_id:
        return []

    ck = f"ot_drugs:{ot_id}"
    cached = cache_get("drugs_direct", ck)
    if cached is not None:
        return [Therapeutic(**t) for t in cached]

    try:
        data = await graphql(session, OPEN_TARGETS_URL, OT_DRUGS_QUERY, {"efoId": ot_id})
        rows = (data.get("data") or {}).get("disease", {}).get("drugAndClinicalCandidates", {}).get("rows", [])
    except Exception as e:
        log.warning("[Open Targets drugs] failed: %s", e)
        return []

    therapeutics: list[Therapeutic] = []
    for row in rows:
        drug = row.get("drug") or {}
        name = drug.get("name") or ""
        if not name:
            continue
        chembl_id = drug.get("id", "")
        stage = row.get("maxClinicalStage", "")
        max_phase = _phase_to_int(stage)
        if "APPROVED" in str(stage).upper() or "PHASE_IV" in str(stage).upper():
            max_phase = max(max_phase, 4)
        therapeutics.append(
            Therapeutic(
                canonical_id=chembl_id or _slug(name),
                name=name,
                drug_type=_normalize_drug_type(drug.get("drugType")),
                mechanism=None,
                max_phase=max_phase,
                approved_indications=[identifiers.name] if max_phase >= 4 else [],
                source_type="direct",
                sources=["Open Targets"],
                evidence_tier=EvidenceTier.A if max_phase >= 4 else EvidenceTier.B if max_phase >= 2 else EvidenceTier.C,
                chembl_id=chembl_id or None,
            )
        )

    if therapeutics:
        cache_set("drugs_direct", ck, [t.model_dump() for t in therapeutics])
    log.info("[Open Targets drugs] %s → %d", identifiers.name, len(therapeutics))
    return therapeutics


async def _dgidb_disease_drugs(
    identifiers: DiseaseIdentifiers, session: aiohttp.ClientSession
) -> list[Therapeutic]:
    ck = f"dgidb_disease:{identifiers.name.lower()}"
    cached = cache_get("drugs_direct", ck)
    if cached is not None:
        return [Therapeutic(**t) for t in cached]

    try:
        data = await graphql(session, DGIDB_URL, DGIDB_DISEASE_QUERY, {"name": identifiers.name})
        nodes = (data.get("data") or {}).get("diseases", {}).get("nodes", [])
    except Exception as e:
        log.warning("[DGIdb disease] failed: %s", e)
        return []

    therapeutics: list[Therapeutic] = []
    seen: set[str] = set()
    for node in nodes:
        for ix in node.get("drugInteractions", []):
            drug = ix.get("drug") or {}
            name = drug.get("name") or ""
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            concept = drug.get("conceptId", "")
            chembl_id = concept if concept.upper().startswith("CHEMBL") else None
            therapeutics.append(
                Therapeutic(
                    canonical_id=chembl_id or _slug(name),
                    name=name,
                    drug_type="small_molecule",
                    max_phase=2,
                    source_type="direct",
                    sources=["DGIdb"],
                    evidence_tier=EvidenceTier.C,
                    chembl_id=chembl_id,
                )
            )

    if therapeutics:
        cache_set("drugs_direct", ck, [t.model_dump() for t in therapeutics])
    return therapeutics


async def get_chembl_indication_drugs(
    mesh_id: str | None, session: aiohttp.ClientSession
) -> list[Therapeutic]:
    if not mesh_id:
        return []

    ck = f"chembl_mesh:{mesh_id}"
    cached = cache_get("drugs_direct", ck)
    if cached is not None:
        return [Therapeutic(**t) for t in cached]

    try:
        data = await get_json(
            session,
            f"{CHEMBL_URL}/drug_indication.json",
            params={"mesh_id": mesh_id, "format": "json", "limit": 100},
            timeout=30,
        )
    except Exception as e:
        log.warning("[ChEMBL indications] failed: %s", e)
        return []

    therapeutics: list[Therapeutic] = []
    seen: set[str] = set()
    for row in (data or {}).get("drug_indications", []):
        mol_chembl = row.get("molecule_chembl_id", "")
        if not mol_chembl or mol_chembl in seen:
            continue
        seen.add(mol_chembl)
        max_phase = int(float(row.get("max_phase_for_ind") or 0))
        therapeutics.append(
            Therapeutic(
                canonical_id=mol_chembl,
                name=mol_chembl,
                drug_type="small_molecule",
                max_phase=max_phase,
                source_type="direct",
                sources=["ChEMBL"],
                evidence_tier=EvidenceTier.B if max_phase >= 2 else EvidenceTier.C,
                chembl_id=mol_chembl,
            )
        )

    if therapeutics:
        cache_set("drugs_direct", ck, [t.model_dump() for t in therapeutics])
    log.info("[ChEMBL] mesh %s → %d drugs", mesh_id, len(therapeutics))
    return therapeutics


async def get_all(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    options: PipelineOptions,
) -> list[Therapeutic]:
    import asyncio

    tasks = [_open_targets_drugs(identifiers, session)]
    if options.includes(3):
        tasks.append(get_chembl_indication_drugs(identifiers.mesh_id, session))
        # DGIdb disease GraphQL endpoint removed in current API — skip

    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_drugs: list[Therapeutic] = []
    for r in results:
        if isinstance(r, list):
            if r:
                options.note_source(r[0].sources[0])
            all_drugs.extend(r)
        elif isinstance(r, Exception):
            log.warning("Direct drugs error: %s", r)
    return all_drugs


fetch_direct_therapeutics = get_all