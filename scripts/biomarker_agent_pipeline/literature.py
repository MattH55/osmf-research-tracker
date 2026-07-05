"""Stage 3: literature mining — PubMed, Europe PMC, Semantic Scholar."""
from __future__ import annotations

import re
import time
import urllib.parse

from .config import LITERATURE_MAX_ABSTRACTS, PUBMED_RATE_LIMIT_S, ncbi_api_key
from .http_util import request_json
from .models import NormalizedBiomarker

NCBI_ESARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
NCBI_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"


def _ncbi_params(extra: dict) -> dict:
    params = {"tool": "OSMF-BiomarkerAgentPipeline", "email": "research@opensourcemed.info", **extra}
    key = ncbi_api_key()
    if key:
        params["api_key"] = key
    return params


def _quote_term(term: str) -> str:
    safe = term.replace('"', "")
    return f'"{safe}"' if " " in safe or "-" in safe else safe


def build_pubmed_queries(norm: NormalizedBiomarker) -> list[str]:
    terms = norm.synonyms[:6] or [norm.input]
    queries = []
    for term in terms[:4]:
        t = _quote_term(term)
        queries.append(
            f"({t}[Title/Abstract]) AND "
            f"({t}[MeSH Terms] OR {t}[Title/Abstract]) AND "
            "(Drug Therapy[MeSH] OR therapeutic use[MeSH] OR antagonists and inhibitors[MeSH] "
            "OR agonists[MeSH] OR drug effects[MeSH])"
        )
        queries.append(f"({t}[Title/Abstract]) AND (clinical trial[pt] OR randomized controlled trial[pt])")
    return list(dict.fromkeys(queries))[:6]


def pubmed_search(query: str, retmax: int = 40) -> list[str]:
    params = _ncbi_params({"db": "pubmed", "term": query, "retmax": str(retmax), "retmode": "json"})
    data = request_json("pubmed_esearch", query, "GET", NCBI_ESARCH, params=params)
    time.sleep(PUBMED_RATE_LIMIT_S)
    return data.get("esearchresult", {}).get("idlist", [])


def pubmed_fetch_abstracts(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    params = _ncbi_params(
        {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }
    )
    import httpx

    with httpx.Client(timeout=30) as client:
        resp = client.get(NCBI_EFETCH, params=params)
        resp.raise_for_status()
        xml = resp.text
    time.sleep(PUBMED_RATE_LIMIT_S)

    articles = []
    blocks = re.split(r"<PubmedArticle>", xml)[1:]
    for block in blocks:
        pmid_m = re.search(r"<PMID[^>]*>(\d+)</PMID>", block)
        title_m = re.search(r"<ArticleTitle>(.*?)</ArticleTitle>", block, re.S)
        abstract_parts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", block, re.S)
        if not pmid_m:
            continue
        title = re.sub(r"<[^>]+>", "", title_m.group(1)) if title_m else ""
        abstract = " ".join(re.sub(r"<[^>]+>", "", p) for p in abstract_parts)
        articles.append(
            {
                "pmid": pmid_m.group(1),
                "title": title.strip(),
                "abstract": abstract.strip(),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid_m.group(1)}/",
                "source": "PubMed",
            }
        )
    return articles


def europe_pmc_search(norm: NormalizedBiomarker, limit: int = 30) -> list[dict]:
    term = norm.synonyms[0] if norm.synonyms else norm.input
    query = f'({term}) AND (drug OR inhibitor OR agonist OR treatment OR therapy)'
    params = {
        "query": query,
        "format": "json",
        "pageSize": str(limit),
        "resultType": "core",
    }
    try:
        data = request_json("europepmc", query, "GET", EPMC_SEARCH, params=params)
    except Exception:
        return []
    out = []
    for r in data.get("resultList", {}).get("result", []):
        pmid = r.get("pmid") or r.get("id")
        abstract = r.get("abstractText") or ""
        if not abstract:
            continue
        out.append(
            {
                "pmid": str(pmid),
                "title": r.get("title", ""),
                "abstract": abstract,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if r.get("pmid") else r.get("fullTextUrl", ""),
                "source": "EuropePMC",
                "cited_by": r.get("citedByCount", 0),
            }
        )
    return out


def semantic_scholar_search(norm: NormalizedBiomarker, limit: int = 20) -> list[dict]:
    term = norm.synonyms[0] if norm.synonyms else norm.input
    query = f"{term} biomarker drug treatment"
    params = {"query": query, "limit": limit, "fields": "title,abstract,externalIds,citationCount,year"}
    try:
        data = request_json("semanticscholar", query, "GET", S2_SEARCH, params=params)
    except Exception:
        return []
    out = []
    for p in data.get("data", []):
        abstract = p.get("abstract") or ""
        if len(abstract) < 40:
            continue
        pmid = (p.get("externalIds") or {}).get("PubMed")
        out.append(
            {
                "pmid": str(pmid) if pmid else None,
                "title": p.get("title", ""),
                "abstract": abstract,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                "source": "SemanticScholar",
                "cited_by": p.get("citationCount", 0),
            }
        )
    return out


def mine_literature(norm: NormalizedBiomarker) -> tuple[list[dict], list[str]]:
    notes: list[str] = []
    pmid_set: set[str] = set()
    articles: list[dict] = []

    for q in build_pubmed_queries(norm):
        try:
            for pmid in pubmed_search(q, retmax=25):
                pmid_set.add(pmid)
        except Exception as err:
            notes.append(f"PubMed query failed: {err}")

    if pmid_set:
        fetched = pubmed_fetch_abstracts(list(pmid_set)[:LITERATURE_MAX_ABSTRACTS])
        articles.extend(fetched)

    epmc = europe_pmc_search(norm, limit=25)
    for a in epmc:
        if a["pmid"] and a["pmid"] not in {x.get("pmid") for x in articles}:
            articles.append(a)

    s2 = semantic_scholar_search(norm, limit=15)
    for a in s2:
        key = a.get("pmid") or a.get("title")
        if key and key not in {x.get("pmid") or x.get("title") for x in articles}:
            articles.append(a)

    # Rank: recency proxy via cited_by, prefer longer abstracts
    articles.sort(key=lambda x: (x.get("cited_by", 0), len(x.get("abstract", ""))), reverse=True)
    articles = articles[:LITERATURE_MAX_ABSTRACTS]
    notes.append(f"Literature search capped at {LITERATURE_MAX_ABSTRACTS} abstracts ({len(articles)} retained).")
    return articles, notes