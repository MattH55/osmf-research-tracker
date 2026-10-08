"""EBI Ontology Lookup Service client — module 1 (registry) term resolution.

Resolves a free-text phenotype label to an EFO/MONDO term. Used at build time
to check a curated phenotypes.csv mapping still resolves (fails loudly if a
term has gone obsolete), and can also be used to search for a mapping that
hasn't been curated yet.
"""
from __future__ import annotations

import httpx

from ..config import OLS_BASE


class ObsoleteTermError(RuntimeError):
    pass


def search(label: str, ontology: str = "efo,mondo", rows: int = 5) -> list[dict]:
    resp = httpx.get(
        f"{OLS_BASE}/search",
        params={"q": label, "ontology": ontology, "rows": rows},
        timeout=20,
    )
    resp.raise_for_status()
    docs = resp.json().get("response", {}).get("docs", [])
    return [{"obo_id": d.get("obo_id"), "label": d.get("label"), "ontology": d.get("ontology_name")} for d in docs]


def check_term_current(obo_id: str, ontology: str) -> bool:
    """Module 1 fails the build if a pinned term is marked obsolete in OLS."""
    prefix, local_id = obo_id.split(":", 1)
    iri = f"http://purl.obolibrary.org/obo/{prefix}_{local_id}"
    resp = httpx.get(
        f"{OLS_BASE}/ontologies/{ontology}/terms",
        params={"iri": iri},
        timeout=20,
    )
    resp.raise_for_status()
    terms = resp.json().get("_embedded", {}).get("terms", [])
    if not terms:
        raise ObsoleteTermError(f"{obo_id} not found in {ontology} — resolve before release")
    return not terms[0].get("is_obsolete", False)
