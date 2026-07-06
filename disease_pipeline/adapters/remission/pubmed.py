"""Layer 2 — PubMed systematic review remission extraction."""
from __future__ import annotations

import json
import logging
import re
import xml.etree.ElementTree as ET

import aiohttp

from ...config import PUBMED_URL, get_anthropic_api_key, get_ncbi_api_key
from ...http_util import get_json

log = logging.getLogger(__name__)

REMISSION_QUERY_TEMPLATE = """
("{mesh_term}"[MeSH Terms] OR "{disease_name}"[Title/Abstract]) AND (
  "remission"[tiab] OR "remission rate"[tiab] OR
  "spontaneous remission"[tiab] OR "drug-free remission"[tiab] OR
  "chronicity"[tiab] OR "chronic course"[tiab] OR
  "natural history"[tiab] OR "relapse rate"[tiab] OR
  "recurrence rate"[tiab]
) AND (
  "Systematic Review"[pt] OR "Meta-Analysis"[pt]
)
"""

EXTRACTION_PROMPT = """You are extracting remission and chronicity data from a clinical systematic review abstract.
Disease: {disease_name}

Abstract:
{abstract_text}

Extract any of these values if reported, using the EXACT disease-specific definitions in the abstract:
{{
  "spontaneous_remission_rate": "rate/proportion without treatment, with timeframe",
  "treatment_remission_rate": "rate with standard-of-care treatment, with timeframe and treatment",
  "drug_free_remission_rate": "rate of maintained remission after stopping treatment",
  "chronicity_rate": "proportion developing chronic course (>X months/years)",
  "relapse_rate_after_remission": "relapse rate after achieving remission, with timeframe",
  "remission_definition_used": "the specific criteria used to define remission in this study",
  "population": "who was studied",
  "follow_up_duration": "how long patients were followed",
  "confidence": "high/medium/low"
}}

Return null for any field not reported. Return ONLY JSON.
"""


async def _esearch(query: str, session: aiohttp.ClientSession, *, max_results: int = 15) -> list[str]:
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "json",
    }
    key = get_ncbi_api_key()
    if key:
        params["api_key"] = key
    data = await get_json(session, f"{PUBMED_URL}/esearch.fcgi", params=params)
    if not data:
        return []
    return (data.get("esearchresult") or {}).get("idlist", [])


async def _efetch_abstracts(pmids: list[str], session: aiohttp.ClientSession) -> list[dict]:
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    key = get_ncbi_api_key()
    if key:
        params["api_key"] = key
    async with session.get(f"{PUBMED_URL}/efetch.fcgi", params=params) as resp:
        if resp.status != 200:
            return []
        xml_text = await resp.text(errors="replace")

    records: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return records

    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else ""
        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""
        parts = []
        for abs_el in article.findall(".//AbstractText"):
            parts.append("".join(abs_el.itertext()))
        abstract = " ".join(parts)
        pub_types = [
            pt.text for pt in article.findall(".//PublicationType") if pt.text
        ]
        records.append({
            "pmid": pmid,
            "title": title,
            "abstract": abstract,
            "publication_types": pub_types,
        })
    return records


async def _llm_extract(abstract: str, disease_name: str) -> dict | None:
    api_key = get_anthropic_api_key()
    if not api_key or not abstract.strip():
        return None
    prompt = EXTRACTION_PROMPT.format(disease_name=disease_name, abstract_text=abstract[:6000])
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text if msg.content else ""
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
    except Exception as e:
        log.debug("[Remission PubMed] LLM extract failed: %s", e)
    return None


async def search_and_extract(
    disease_name: str,
    mesh_id: str | None,
    session: aiohttp.ClientSession,
    *,
    max_results: int = 8,
    use_llm: bool = True,
) -> list[dict]:
    mesh_term = mesh_id.replace("D", "") if mesh_id and mesh_id.startswith("D") else (mesh_id or disease_name)
    if mesh_id and mesh_id.startswith("D"):
        mesh_term = mesh_id
    query = REMISSION_QUERY_TEMPLATE.format(
        mesh_term=mesh_id or disease_name,
        disease_name=disease_name,
    ).strip()

    pmids = await _esearch(query, session, max_results=max_results)
    articles = await _efetch_abstracts(pmids, session)
    extractions: list[dict] = []

    for art in articles:
        row: dict = {
            "pmid": art["pmid"],
            "title": art["title"],
            "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{art['pmid']}/",
            "publication_types": art.get("publication_types", []),
            "source": "PubMed",
            "data_tier": "systematic_review",
        }
        if use_llm and get_anthropic_api_key():
            extracted = await _llm_extract(art.get("abstract", ""), disease_name)
            if extracted:
                row["extracted"] = extracted
        extractions.append(row)

    log.info("[Remission PubMed] %d SR/MA hits for '%s'", len(extractions), disease_name)
    return extractions