"""NP-4b — PubChem compound standardization."""
from __future__ import annotations

import logging
from urllib.parse import quote

import aiohttp

from ...cache import cache_get, cache_set
from ...config import PUBCHEM_BASE
from ...http_util import get_json

log = logging.getLogger(__name__)


async def pubchem_search_by_name(name: str, session: aiohttp.ClientSession) -> dict | None:
    ck = f"name:{name.lower()}"
    cached = cache_get("pubchem_np", ck)
    if cached is not None:
        return cached if cached else None

    encoded = quote(name, safe="")
    url = f"{PUBCHEM_BASE}/compound/name/{encoded}/JSON"
    try:
        data = await get_json(session, url)
        if not data:
            cache_set("pubchem_np", ck, {})
            return None
        compounds = (data.get("PC_Compounds") or [{}])[0]
        cid = str(compounds.get("id", {}).get("id", {}).get("cid", ""))
        props = {}
        for block in compounds.get("props", []):
            urn = block.get("urn", {})
            label = urn.get("label", "")
            value = (block.get("value") or {}).get("sval") or (block.get("value") or {}).get("fval")
            if label == "IUPAC Name":
                props["iupac_name"] = value
            elif label == "Molecular Formula":
                props["formula"] = value
            elif label == "InChIKey":
                props["inchikey"] = value
            elif label == "Canonical SMILES":
                props["smiles"] = value

        syn_data = await get_json(session, f"{PUBCHEM_BASE}/compound/cid/{cid}/synonyms/JSON")
        synonyms: list[str] = []
        if syn_data:
            info = (syn_data.get("InformationList") or {}).get("Information") or []
            if info:
                synonyms = info[0].get("Synonym", [])[:50]

        result = {
            "cid": cid,
            "iupac_name": props.get("iupac_name") or name,
            "formula": props.get("formula"),
            "inchikey": props.get("inchikey"),
            "smiles": props.get("smiles"),
            "synonyms": synonyms,
        }
        cache_set("pubchem_np", ck, result)
        return result
    except Exception as e:
        log.debug("[PubChem] search failed for '%s': %s", name[:40], e)
        cache_set("pubchem_np", ck, {})
        return None


async def pubchem_get_bioassay_count(cid: str, session: aiohttp.ClientSession) -> int:
    if not cid:
        return 0
    ck = f"assay:{cid}"
    cached = cache_get("pubchem_np", ck)
    if cached is not None:
        return int(cached.get("count", 0))

    try:
        data = await get_json(session, f"{PUBCHEM_BASE}/compound/cid/{cid}/assaysummary/JSON")
        if not data:
            return 0
        rows = (data.get("AssaySummaries") or {}).get("AssaySummary") or []
        count = len(rows) if isinstance(rows, list) else 0
        cache_set("pubchem_np", ck, {"count": count})
        return count
    except Exception as e:
        log.debug("[PubChem] bioassay count failed for CID %s: %s", cid, e)
        return 0


async def pubchem_get_safety_annotations(cid: str, session: aiohttp.ClientSession) -> dict:
    if not cid:
        return {"safety_notes": "", "ghs_hazards": []}

    ck = f"safety:{cid}"
    cached = cache_get("pubchem_np", ck)
    if cached is not None:
        return cached

    result = {"safety_notes": "", "ghs_hazards": []}
    try:
        data = await get_json(session, f"{PUBCHEM_BASE}/compound/cid/{cid}/JSON")
        if data:
            desc = (data.get("PC_Compounds") or [{}])[0]
            for section in desc.get("props", []):
                urn = (section.get("urn") or {}).get("label", "")
                if "GHS" in urn or "Hazard" in urn:
                    val = (section.get("value") or {}).get("sval", "")
                    if val:
                        result["ghs_hazards"].append(val)
        cache_set("pubchem_np", ck, result)
    except Exception as e:
        log.debug("[PubChem] safety failed for CID %s: %s", cid, e)
    return result