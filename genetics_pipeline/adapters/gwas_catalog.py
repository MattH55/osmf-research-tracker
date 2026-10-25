"""GWAS Catalog client — module 2/3 (study discovery + association ingest).

EBI endpoints the original build spec assumed that are now gone (ToolUniverse
#642, #640), none of which is called here:
  - the old bulk summary-statistics REST API (HTTP 410 on every path)
  - the legacy REST API (/gwas/rest/api/studies, .../associations), which
    used to serve curated per-study top hits and now also returns HTTP 410
  - the eQTL Catalogue REST API (retired outright)

What works and is used:
  - the documented REST API v2 (/gwas/rest/api/v2) for studies-by-PubMed-ID
    and curated association queries. Its records are snake_case
    (accession_id, pubmed_id, p_value, or_value, ci_lower, ci_upper,
    snp_allele=[{rs_id, effect_allele}], locations=["chr:pos"], ...), not the
    legacy camelCase. Unknown query parameters are ignored rather than
    rejected, so results are re-filtered client-side on the requested key.
  - the camelCase v2 service (/gwas/api/v2) for study_v2() metadata and
    EFO/MONDO trait mapping (unchanged)
"""
from __future__ import annotations

import httpx

from ..config import GWAS_CATALOG_REST_V2_BASE, GWAS_CATALOG_V2_BASE


class RetiredEndpointError(RuntimeError):
    """Raised when an endpoint this pipeline relies on returns 404/410 or is unreachable."""


def check_connectivity() -> dict:
    """Start-of-run check (spec section 4): probe every GWAS Catalog endpoint
    the adapters call and return {name: {"url", "status"}} with the real HTTP
    status. The caller records this in the manifest, then calls
    raise_if_retired() so a 404/410 fails loudly rather than producing an
    empty build."""
    results = {}
    for name, url in {
        "gwas_catalog_v2_studies": f"{GWAS_CATALOG_V2_BASE}/studies?size=1",
        "gwas_catalog_rest_v2_studies": f"{GWAS_CATALOG_REST_V2_BASE}/studies?size=1",
        "gwas_catalog_rest_v2_associations": f"{GWAS_CATALOG_REST_V2_BASE}/associations?size=1",
    }.items():
        results[name] = probe(url)
    return results


def probe(url: str) -> dict:
    try:
        return {"url": url, "status": httpx.get(url, timeout=30).status_code}
    except httpx.HTTPError as exc:
        return {"url": url, "status": None, "error": f"{type(exc).__name__}: {exc}"}


def raise_if_retired(results: dict) -> None:
    for name, r in results.items():
        if r["status"] is None:
            raise RetiredEndpointError(f"{name} unreachable at {r['url']}: {r['error']}")
        if r["status"] in (404, 410):
            raise RetiredEndpointError(f"{name} returned {r['status']} at {r['url']}")


def find_studies_by_pubmed_id(pubmed_id: str) -> list[dict]:
    resp = httpx.get(
        f"{GWAS_CATALOG_REST_V2_BASE}/studies",
        params={"pubmed_id": pubmed_id, "size": 200},
        timeout=30,
    )
    resp.raise_for_status()
    studies = resp.json().get("_embedded", {}).get("studies", [])
    return [s for s in studies if str(s.get("pubmed_id")) == str(pubmed_id)]


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
        f"{GWAS_CATALOG_REST_V2_BASE}/associations",
        params={"accession_id": accession_id, "size": size},
        timeout=30,
    )
    resp.raise_for_status()
    associations = resp.json().get("_embedded", {}).get("associations", [])
    return [a for a in associations if a.get("accession_id") == accession_id]
