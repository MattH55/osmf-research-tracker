"""NP name deduplication across 20 sources."""
from __future__ import annotations

import aiohttp

from ..natural_products import normalize_np as _np


def load_np_synonyms() -> dict[str, str]:
    return _np.load_np_synonyms()


async def normalize_name(
    raw_name: str,
    synonym_index: dict[str, str],
    session: aiohttp.ClientSession,
    *,
    resolve_external: bool = True,
) -> dict:
    return await _np.normalize_np_name(
        raw_name, synonym_index, session, resolve_external=resolve_external
    )


def canonical_key(norm: dict, raw_name: str) -> str:
    if norm.get("pubchem_cid"):
        return f"cid:{norm['pubchem_cid']}"
    name = norm.get("canonical_name") or raw_name
    return f"name:{name.lower()}"