"""Stage 3b — Marker-vs-disease literature mining (for real biomarker atlases).

Distinct from stage3_literature.py, which searches for drug-repurposing
evidence (agent affecting a gene). This stage searches for evidence of the
marker's *level in the disease state relative to healthy controls* — the
question the biomarkers.schema.json atlas format actually needs answered.

Sources: PubMed (E-utilities) + Europe PMC REST API, same as stage3.
Also extracts first author / year / journal / DOI so citations can be built
in the "Author et al. YEAR" format used by the existing 5 atlases.

Results cached for 7 days under the 'stage3b' namespace (separate from
stage3's cache so the two query types never collide).
"""
import asyncio
import logging
import xml.etree.ElementTree as ET

import httpx

from .cache import cache_get, cache_set
from .models import MarkerLiteratureRef, NormalizedBiomarker

log = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH_URL  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EPMC_URL    = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

_LEVEL_TERMS = (
    "elevated[tiab] OR increased[tiab] OR decreased[tiab] OR reduced[tiab] "
    "OR levels[tiab] OR biomarker[tiab] OR upregulated[tiab] OR downregulated[tiab]"
)


def _pubmed_query(norm: NormalizedBiomarker, disease_name: str) -> str:
    symbol = norm.symbol or norm.input_name
    names = list({symbol} | set(norm.synonyms or []))[:5]
    term_clause = " OR ".join(f'"{n}"' for n in names)
    return f'({term_clause}) AND "{disease_name}"[tiab] AND ({_LEVEL_TERMS})'


def _epmc_query(norm: NormalizedBiomarker, disease_name: str) -> str:
    symbol = norm.symbol or norm.input_name
    return f'"{symbol}" AND "{disease_name}" AND (elevated OR increased OR decreased OR levels) AND HAS_ABSTRACT:Y'


def _first_author(art) -> str | None:
    author_list = art.find(".//AuthorList")
    if author_list is None:
        return None
    first = author_list.find("Author")
    if first is None:
        return None
    last = first.find("LastName")
    return last.text if last is not None else None


def _pub_year(art) -> str | None:
    for path in (".//PubDate/Year", ".//PubDate/MedlineDate"):
        el = art.find(path)
        if el is not None and el.text:
            # MedlineDate can be "2023 Jan-Feb" — take the leading year token
            return el.text.strip()[:4]
    return None


def _doi(art) -> str | None:
    for aid in art.findall(".//ArticleIdList/ArticleId"):
        if aid.get("IdType") == "doi" and aid.text:
            return aid.text.strip()
    for eloc in art.findall(".//ELocationID"):
        if eloc.get("EIdType") == "doi" and eloc.text:
            return eloc.text.strip()
    return None


async def _esearch_pmids(query: str, client: httpx.AsyncClient, api_key: str, max_results: int) -> list[str]:
    params: dict = {"db": "pubmed", "term": query, "retmax": str(max_results), "retmode": "json", "sort": "relevance"}
    if api_key:
        params["api_key"] = api_key
    try:
        r = await client.get(ESEARCH_URL, params=params, timeout=15)
        r.raise_for_status()
        return r.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        log.warning("[Stage3b PubMed esearch] failed: %s", e)
        return []


async def _efetch_marker_refs(pmids: list[str], client: httpx.AsyncClient, api_key: str) -> list[MarkerLiteratureRef]:
    if not pmids:
        return []
    params: dict = {"db": "pubmed", "id": ",".join(pmids), "rettype": "xml", "retmode": "xml"}
    if api_key:
        params["api_key"] = api_key
    try:
        r = await client.get(EFETCH_URL, params=params, timeout=30)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        refs: list[MarkerLiteratureRef] = []
        for art in root.findall(".//PubmedArticle"):
            pmid_el  = art.find(".//PMID")
            title_el = art.find(".//ArticleTitle")
            abs_els  = art.findall(".//AbstractText")
            journal_el = art.find(".//Journal/Title")
            pmid     = pmid_el.text  if pmid_el  is not None else ""
            title    = title_el.text if title_el is not None else ""
            abstract = " ".join((el.text or "") for el in abs_els).strip()
            if pmid and abstract:
                refs.append(MarkerLiteratureRef(
                    pmid=pmid,
                    title=title or "",
                    abstract=abstract,
                    source="PubMed",
                    first_author=_first_author(art),
                    pub_year=_pub_year(art),
                    journal=journal_el.text if journal_el is not None else None,
                    doi=_doi(art),
                ))
        return refs
    except Exception as e:
        log.warning("[Stage3b PubMed efetch] failed: %s", e)
        return []


async def _epmc_search(norm: NormalizedBiomarker, disease_name: str, client: httpx.AsyncClient, max_results: int) -> list[MarkerLiteratureRef]:
    params = {
        "query": _epmc_query(norm, disease_name),
        "resultType": "core",
        "format": "json",
        "pageSize": str(min(max_results, 50)),
        "sort": "CITED desc",
    }
    try:
        r = await client.get(EPMC_URL, params=params, timeout=15)
        r.raise_for_status()
        results = r.json().get("resultList", {}).get("result", [])
        refs: list[MarkerLiteratureRef] = []
        for res in results:
            pmid = str(res.get("pmid") or res.get("id") or "")
            abstract = res.get("abstractText", "")
            if not abstract:
                continue
            author_string = res.get("authorString", "")
            first_author = author_string.split(",")[0].split(" ")[0] if author_string else None
            refs.append(MarkerLiteratureRef(
                pmid=pmid,
                title=res.get("title", ""),
                abstract=abstract,
                source="EuropePMC",
                first_author=first_author,
                pub_year=str(res.get("pubYear")) if res.get("pubYear") else None,
                journal=res.get("journalTitle"),
                doi=res.get("doi"),
            ))
        return refs
    except Exception as e:
        log.warning("[Stage3b EuropePMC] failed: %s", e)
        return []


async def mine_marker_literature(
    norm: NormalizedBiomarker,
    disease_name: str,
    client: httpx.AsyncClient,
    ncbi_api_key: str = "",
    max_results: int = 30,
) -> tuple[list[MarkerLiteratureRef], list[str]]:
    cache_key = f"{norm.symbol or norm.input_name}:{disease_name}:{max_results}"
    cached = cache_get("stage3b", cache_key, ttl_days=7)
    if cached is not None:
        log.debug("Stage3b cache hit: %s / %s", norm.symbol, disease_name)
        return [MarkerLiteratureRef(**r) for r in cached["refs"]], cached["notes"]

    query = _pubmed_query(norm, disease_name)
    pmids_coro = _esearch_pmids(query, client, ncbi_api_key, max_results)
    epmc_coro  = _epmc_search(norm, disease_name, client, max_results // 2)
    pmids, epmc = await asyncio.gather(pmids_coro, epmc_coro)

    pubmed = await _efetch_marker_refs(pmids[:max_results], client, ncbi_api_key)

    seen: set[str] = set()
    refs: list[MarkerLiteratureRef] = []
    for ref in pubmed + epmc:
        key = ref.pmid or ref.title[:80]
        if key and key in seen:
            continue
        seen.add(key)
        refs.append(ref)

    refs = refs[:max_results]
    notes = [f"Stage3b marker-vs-disease search returned {len(refs)} refs for {norm.symbol}/{disease_name}."]
    if not ncbi_api_key:
        notes.append("NCBI_API_KEY not set — E-utilities rate-limited to 3 req/s.")

    cache_set("stage3b", cache_key, {"refs": [r.model_dump() for r in refs], "notes": notes})
    log.info("[Stage3b] %s / %s → %d refs", norm.symbol, disease_name, len(refs))
    return refs, notes
