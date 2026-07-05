"""Stage 3 — Literature mining.

Sources: PubMed (E-utilities) + Europe PMC REST API.
Returns up to `max_results` deduplicated abstracts as plain dicts with
keys: pmid, title, abstract, source.

Results cached for 7 days (literature changes faster than DB records).
"""
import asyncio
import logging
import xml.etree.ElementTree as ET

import httpx

from .cache import cache_get, cache_set
from .models import NormalizedBiomarker

log = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EPMC_URL    = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _pubmed_query(norm: NormalizedBiomarker) -> str:
    symbol = norm.symbol or norm.input_name
    # Take up to 5 synonyms to keep the query manageable
    names = list({symbol} | set(norm.synonyms or []))[:5]
    term_clause = " OR ".join(f'"{n}"' for n in names)
    return (
        f"({term_clause}) AND "
        f'("{symbol}"[Pharmacological Action] OR "{symbol}"/antagonists and inhibitors[mesh] '
        f'OR "{symbol}"/drug effects[mesh] OR "{symbol}"/agonists[mesh] '
        f'OR (drug[tiab] AND "{symbol}") OR (inhibitor[tiab] AND "{symbol}"))'
    )


async def _esearch_pmids(
    query: str,
    client: httpx.AsyncClient,
    api_key: str,
    max_results: int,
) -> list[str]:
    params: dict = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "json",
        "sort": "relevance",
    }
    if api_key:
        params["api_key"] = api_key
    try:
        r = await client.get(ESEARCH_URL, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        log.warning("[PubMed esearch] failed: %s", e)
        return []


async def _efetch_abstracts(
    pmids: list[str],
    client: httpx.AsyncClient,
    api_key: str,
) -> list[dict]:
    if not pmids:
        return []
    params: dict = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "xml",
        "retmode": "xml",
    }
    if api_key:
        params["api_key"] = api_key
    try:
        r = await client.get(EFETCH_URL, params=params, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        articles: list[dict] = []
        for art in root.findall(".//PubmedArticle"):
            pmid_el  = art.find(".//PMID")
            title_el = art.find(".//ArticleTitle")
            abs_els  = art.findall(".//AbstractText")
            pmid     = pmid_el.text  if pmid_el  is not None else ""
            title    = title_el.text if title_el is not None else ""
            abstract = " ".join((el.text or "") for el in abs_els).strip()
            if pmid and abstract:
                articles.append({"pmid": pmid, "title": title, "abstract": abstract, "source": "PubMed"})
        return articles
    except Exception as e:
        log.warning("[PubMed efetch] failed: %s", e)
        return []


async def _epmc_search(
    norm: NormalizedBiomarker,
    client: httpx.AsyncClient,
    max_results: int,
) -> list[dict]:
    symbol = norm.symbol or norm.input_name
    query = (
        f'"{symbol}" AND (drug OR inhibitor OR treatment OR therapeutic) '
        f'AND HAS_ABSTRACT:Y'
    )
    params = {
        "query": query,
        "resultType": "core",
        "format": "json",
        "pageSize": str(min(max_results, 50)),
        "sort": "CITED desc",
    }
    try:
        r = await client.get(EPMC_URL, params=params, timeout=15)
        r.raise_for_status()
        results = r.json().get("resultList", {}).get("result", [])
        articles: list[dict] = []
        for res in results:
            pmid     = str(res.get("pmid") or res.get("id") or "")
            title    = res.get("title", "")
            abstract = res.get("abstractText", "")
            if abstract:
                articles.append({"pmid": pmid, "title": title, "abstract": abstract, "source": "EuropePMC"})
        return articles
    except Exception as e:
        log.warning("[EuropePMC] failed: %s", e)
        return []


async def mine_literature(
    norm: NormalizedBiomarker,
    client: httpx.AsyncClient,
    ncbi_api_key: str = "",
    max_results: int = 50,
) -> tuple[list[dict], list[str]]:
    cache_key = f"{norm.symbol or norm.input_name}:{max_results}"
    cached = cache_get("stage3", cache_key, ttl_days=7)
    if cached is not None:
        log.debug("Stage3 cache hit: %s", norm.symbol)
        return cached["abstracts"], cached["notes"]

    query = _pubmed_query(norm)
    pmids_coro  = _esearch_pmids(query, client, ncbi_api_key, max_results)
    epmc_coro   = _epmc_search(norm, client, max_results // 2)
    pmids, epmc = await asyncio.gather(pmids_coro, epmc_coro)

    pubmed = await _efetch_abstracts(pmids[:max_results], client, ncbi_api_key)

    # Merge; PubMed takes priority for duplicates
    seen: set[str] = set()
    abstracts: list[dict] = []
    for art in pubmed + epmc:
        pid = art.get("pmid", "")
        key = pid or art.get("title", "")[:80]
        if key and key in seen:
            continue
        seen.add(key)
        abstracts.append(art)

    abstracts = abstracts[:max_results]
    notes: list[str] = [
        f"Literature search returned {len(abstracts)} abstracts (capped at {max_results})."
    ]
    if not ncbi_api_key:
        notes.append("NCBI_API_KEY not set — E-utilities rate-limited to 3 req/s.")

    cache_set("stage3", cache_key, {"abstracts": abstracts, "notes": notes})
    log.info("[Stage3] %s → %d abstracts", norm.symbol, len(abstracts))
    return abstracts, notes
