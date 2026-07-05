"""NP-6 — Name normalization and synonym resolution."""
from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path

import aiohttp

from ...cache import cache_get, cache_set
from ...config import NP_SYNONYMS_PATH
from . import lotus as lotus_mod
from . import pubchem_np

log = logging.getLogger(__name__)

_SKIP_PATTERNS = (
    "placebo", "anti-vegf", "areds", "dosage-dependency", "versus", "patients",
    "enriched egg", "not enriched", "soft gel", "gummy", "ozonide", "ozonated",
)

_synonym_data: dict | None = None
_synonym_index: dict[str, str] | None = None


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


def load_np_synonyms_data() -> dict:
    global _synonym_data
    if _synonym_data is None:
        path = Path(NP_SYNONYMS_PATH)
        _synonym_data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _synonym_data


def load_np_synonyms() -> dict[str, str]:
    """Load synonym index: {synonym_lower: canonical_key}."""
    global _synonym_index
    if _synonym_index is not None:
        return _synonym_index

    data = load_np_synonyms_data()
    index: dict[str, str] = {}
    for canonical, meta in data.items():
        index[canonical.lower()] = canonical
        for syn in meta.get("synonyms", []):
            index[syn.lower()] = canonical
        cname = meta.get("canonical_name", "")
        if cname:
            index[cname.lower()] = canonical
    _synonym_index = index
    return index


def _meta_for_canonical(canonical_key: str) -> dict:
    return load_np_synonyms_data().get(canonical_key, {})


def _fuzzy_lookup(name: str, synonym_index: dict[str, str]) -> str | None:
    best_key: str | None = None
    best_score = 0.0
    data = load_np_synonyms_data()
    for canonical in data:
        candidates = [canonical, data[canonical].get("canonical_name", "")]
        candidates.extend(data[canonical].get("synonyms", []))
        for cand in candidates:
            if not cand:
                continue
            score = SequenceMatcher(None, name.lower(), cand.lower()).ratio()
            if score > best_score:
                best_score = score
                best_key = canonical
    if best_score >= 0.85 and best_key:
        return best_key
    return None


async def normalize_np_name(
    raw_name: str,
    synonym_index: dict[str, str],
    session: aiohttp.ClientSession,
) -> dict:
    cleaned = raw_name.strip()
    if not cleaned:
        return {"canonical_name": raw_name, "canonical_key": None, "resolved": False}

    lower = cleaned.lower()
    if any(p in lower for p in _SKIP_PATTERNS):
        return {"canonical_name": cleaned, "canonical_key": None, "resolved": False}
    ck = f"np_norm:{lower}"
    cached = cache_get("normalize_np", ck)
    if cached is not None:
        return cached

    canonical_key = synonym_index.get(lower)
    if not canonical_key:
        for part in re.split(r"[/+,;&]| and | plus ", lower):
            part = part.strip()
            if part and part in synonym_index:
                canonical_key = synonym_index[part]
                break
    if canonical_key:
        meta = _meta_for_canonical(canonical_key)
        result = {
            "canonical_name": meta.get("canonical_name", canonical_key.title()),
            "canonical_key": canonical_key,
            "pubchem_cid": meta.get("pubchem_cid"),
            "np_type": meta.get("np_type", "nutraceutical"),
            "source_plant": meta.get("source_plant"),
            "safety_tier": meta.get("safety_tier"),
            "known_interactions": meta.get("known_interactions", []),
            "resolved": True,
        }
        cache_set("normalize_np", ck, result)
        return result

    pubchem = await pubchem_np.pubchem_search_by_name(cleaned, session)
    if pubchem:
        cid = pubchem.get("cid")
        for syn in pubchem.get("synonyms", []):
            hit = synonym_index.get(syn.lower())
            if hit:
                meta = _meta_for_canonical(hit)
                result = {
                    "canonical_name": meta.get("canonical_name", hit.title()),
                    "canonical_key": hit,
                    "pubchem_cid": meta.get("pubchem_cid") or cid,
                    "np_type": meta.get("np_type", "food_compound"),
                    "source_plant": meta.get("source_plant"),
                    "safety_tier": meta.get("safety_tier"),
                    "known_interactions": meta.get("known_interactions", []),
                    "resolved": True,
                }
                cache_set("normalize_np", ck, result)
                return result
        result = {
            "canonical_name": pubchem.get("iupac_name") or cleaned,
            "canonical_key": _slug(cleaned),
            "pubchem_cid": cid,
            "np_type": "food_compound",
            "resolved": True,
        }
        cache_set("normalize_np", ck, result)
        return result

    lotus = await lotus_mod.lotus_search_by_name(cleaned, session)
    if lotus:
        for syn in [lotus.get("label", ""), cleaned]:
            hit = synonym_index.get(syn.lower())
            if hit:
                meta = _meta_for_canonical(hit)
                result = {
                    "canonical_name": meta.get("canonical_name", hit.title()),
                    "canonical_key": hit,
                    "pubchem_cid": meta.get("pubchem_cid"),
                    "np_type": meta.get("np_type", "botanical"),
                    "source_plant": meta.get("source_plant"),
                    "lotus_wikidata_id": lotus.get("wikidata_id"),
                    "safety_tier": meta.get("safety_tier"),
                    "known_interactions": meta.get("known_interactions", []),
                    "resolved": True,
                }
                cache_set("normalize_np", ck, result)
                return result
        result = {
            "canonical_name": lotus.get("label") or cleaned,
            "canonical_key": _slug(cleaned),
            "lotus_wikidata_id": lotus.get("wikidata_id"),
            "np_type": "botanical",
            "resolved": True,
        }
        cache_set("normalize_np", ck, result)
        return result

    fuzzy = _fuzzy_lookup(cleaned, synonym_index)
    if fuzzy:
        meta = _meta_for_canonical(fuzzy)
        result = {
            "canonical_name": meta.get("canonical_name", fuzzy.title()),
            "canonical_key": fuzzy,
            "pubchem_cid": meta.get("pubchem_cid"),
            "np_type": meta.get("np_type", "nutraceutical"),
            "source_plant": meta.get("source_plant"),
            "safety_tier": meta.get("safety_tier"),
            "known_interactions": meta.get("known_interactions", []),
            "resolved": True,
        }
        cache_set("normalize_np", ck, result)
        return result

    result = {"canonical_name": cleaned, "canonical_key": None, "resolved": False}
    cache_set("normalize_np", ck, result)
    return result