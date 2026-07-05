"""Module 1 — Disease identifier normalization."""
from __future__ import annotations

import json
import logging
import re

import aiohttp

from ..cache import cache_get, cache_set
from ..config import MONARCH_API, OPEN_TARGETS_URL, ORPHANET_OLS_URL, OXO_URL, SEEDS_PATH
from ..http_util import get_json, graphql, post_json
from ..models import DiseaseIdentifiers

log = logging.getLogger(__name__)


def seed_key(disease_name: str) -> str:
    s = disease_name.lower().strip()
    s = re.sub(r"\s*\([^)]*\)", "", s)
    for suffix in (" mellitus", " (essential)", " / post-acute sequelae (pacvs)"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    s = re.sub(r"[^\w\s/-]", "", s)
    s = re.sub(r"[\s_/]+", " ", s).strip()
    return s


def _load_seeds() -> dict[str, dict]:
    if not SEEDS_PATH.exists():
        return {}
    try:
        return json.loads(SEEDS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to load seeds: %s", e)
        return {}


async def _ot_text_search(name: str, session: aiohttp.ClientSession) -> dict | None:
    ck = f"ot_search:{name.lower()}"
    cached = cache_get("normalize", ck)
    if cached is not None:
        return cached

    query = """
    query Search($query: String!) {
      search(queryString: $query, entityNames: ["disease"], page: {index: 0, size: 1}) {
        hits {
          id
          name
          entity
        }
      }
    }
    """
    data = await graphql(session, OPEN_TARGETS_URL, query, {"query": name})
    hits = (data.get("data") or {}).get("search", {}).get("hits") or []
    if not hits:
        return None
    result = {"id": hits[0].get("id"), "name": hits[0].get("name")}
    cache_set("normalize", ck, result)
    return result


async def _oxo_crossmap(efo_id: str, session: aiohttp.ClientSession) -> dict[str, str]:
    ck = f"oxo:{efo_id}"
    cached = cache_get("normalize", ck)
    if cached is not None:
        return cached

    payload = {"ids": [efo_id], "mappingTargetSet": ["OMIM", "MeSH", "UMLS", "MONDO"]}
    try:
        data = await post_json(session, f"{OXO_URL}/search", payload)
    except Exception as e:
        log.warning("OxO crossmap failed for %s: %s", efo_id, e)
        return {}
    if not data:
        return {}
    mapped: dict[str, str] = {}
    for entry in data.get("result", {}).get(efo_id, {}).get("mapping", {}).get("mappedIds", []):
        prefix = entry.get("prefix", "")
        target = entry.get("id", "")
        if prefix and target:
            mapped[prefix] = target
    cache_set("normalize", ck, mapped)
    return mapped


async def _ordo_orpha(disease_name: str, session: aiohttp.ClientSession) -> str | None:
    ck = f"orpha_search:{disease_name.lower()}"
    cached = cache_get("normalize", ck)
    if cached is not None:
        return cached.get("orpha_id")

    params = {"q": disease_name, "ontology": "ordo", "rows": 5}
    data = await get_json(session, f"{ORPHANET_OLS_URL}/search", params=params)
    docs = data.get("response", {}).get("docs", [])
    orpha_id = None
    for doc in docs:
        obo_id = doc.get("obo_id", "")
        if obo_id.startswith("Orphanet:"):
            orpha_id = obo_id.replace("Orphanet:", "ORPHA:")
            break
    cache_set("normalize", ck, {"orpha_id": orpha_id})
    return orpha_id


async def _mondo_from_monarch(efo_id: str, session: aiohttp.ClientSession) -> str | None:
    params = {"object": efo_id, "predicate": "skos:exactMatch", "limit": 5}
    try:
        data = await get_json(session, f"{MONARCH_API}/association", params=params)
        for item in data.get("items", []):
            subj = item.get("subject", "")
            if subj.startswith("MONDO:"):
                return subj
    except Exception as e:
        log.debug("Monarch lookup failed: %s", e)
    return None


async def normalize_disease(disease_name: str, session: aiohttp.ClientSession) -> DiseaseIdentifiers:
    key = seed_key(disease_name)
    seeds = _load_seeds()
    if key in seeds:
        log.info("Seeds hit for '%s' → %s", disease_name, key)
        row = seeds[key]
        return DiseaseIdentifiers(
            name=row.get("name", disease_name),
            mondo_id=row.get("mondo_id"),
            efo_id=row.get("efo_id"),
            omim_id=row.get("omim_id"),
            orpha_id=row.get("orpha_id"),
            mesh_id=row.get("mesh_id"),
            umls_cui=row.get("umls_cui"),
        )

    log.info("Resolving identifiers via API for '%s'", disease_name)
    ot_hit = await _ot_text_search(disease_name, session)
    if not ot_hit or not ot_hit.get("id"):
        log.warning("Open Targets search returned no hit for '%s'", disease_name)
        return DiseaseIdentifiers(name=disease_name)

    raw_id = ot_hit["id"]
    canonical_name = ot_hit.get("name") or disease_name
    efo_id: str | None = None
    mondo_id: str | None = None
    if raw_id.startswith("MONDO_"):
        mondo_id = raw_id.replace("_", ":", 1)
    else:
        efo_id = raw_id

    crossmap_id = raw_id
    mapped = await _oxo_crossmap(crossmap_id, session)
    orpha_id = await _ordo_orpha(canonical_name, session)
    if not mondo_id:
        mondo_id = mapped.get("MONDO") or await _mondo_from_monarch(crossmap_id, session)
    elif mapped.get("MONDO"):
        mondo_id = mapped["MONDO"]

    ids = DiseaseIdentifiers(
        name=canonical_name,
        mondo_id=mondo_id,
        efo_id=efo_id,
        omim_id=mapped.get("OMIM"),
        orpha_id=orpha_id,
        mesh_id=mapped.get("MeSH"),
        umls_cui=mapped.get("UMLS"),
    )

    missing = [f for f in ("efo_id", "umls_cui", "mesh_id", "omim_id") if not getattr(ids, f)]
    if missing:
        log.warning("Missing identifiers for '%s': %s", canonical_name, ", ".join(missing))

    return ids