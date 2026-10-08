"""GWAS Catalog client — module 2/3 (study discovery + association ingest).

Two EBI endpoints the original build spec assumed are gone (ToolUniverse
#642, #640): the old GWAS Catalog bulk summary-statistics REST API returns
HTTP 410 on every path, and the eQTL Catalogue REST API has been retired
outright. Neither is called here.

What still works and is used:
  - the v2 API (/gwas/api/v2) for study metadata and EFO/MONDO trait mapping
  - the legacy per-study REST API (/gwas/rest/api) for curated top-hit
    associations of a specific accession, which is a different endpoint
    from the retired bulk summary-statistics API
"""
from __future__ import annotations

import httpx

from ..config import GWAS_CATALOG_LEGACY_BASE, GWAS_CATALOG_V2_BASE


class RetiredEndpointError(RuntimeError):
    """Raised if code ever tries to call the confirmed-410 bulk summary-stats API."""


def check_connectivity() -> dict:
    """Start-of-run check (spec section 4): fail loudly on 410/404 rather than
    producing an empty build."""
    results = {}
    for name, url in {
        "v2_studies": f"{GWAS_CATALOG_V2_BASE}/studies?size=1",
        "legacy_studies": f"{GWAS_CATALOG_LEGACY_BASE}/studies?size=1",
    }.items():
        resp = httpx.get(url, timeout=20)
        results[name] = resp.status_code
        if resp.status_code in (404, 410):
            raise RetiredEndpointError(f"{name} returned {resp.status_code} at {url}")
    return results


def find_studies_by_pubmed_id(pubmed_id: str) -> list[dict]:
    resp = httpx.get(
        f"{GWAS_CATALOG_LEGACY_BASE}/studies/search/findByPublicationIdPubmedId",
        params={"pubmedId": pubmed_id},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json().get("_embedded", {}).get("studies", [])


def study_v2(accession_id: str) -> dict:
    resp = httpx.get(
        f"{GWAS_CATALOG_V2_BASE}/studies",
        params={"accessionId": accession_id},
        timeout=20,
    )
    resp.raise_for_status()
    studies = resp.json().get("_embedded", {}).get("studies", [])
    return studies[0] if studies else {}


def top_associations(accession_id: str, size: int = 200) -> list[dict]:
    resp = httpx.get(
        f"{GWAS_CATALOG_LEGACY_BASE}/studies/{accession_id}/associations",
        params={"projection": "associationBySnp", "size": size},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("_embedded", {}).get("associations", [])
