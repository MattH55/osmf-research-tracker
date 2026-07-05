"""NP-1 — PubMed clinical evidence search for natural products."""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET

import aiohttp

from ...config import PUBMED_URL, get_ncbi_api_key
from ...http_util import get_json
from ...models import DiseaseIdentifiers
from ...options import PipelineOptions

log = logging.getLogger(__name__)

NP_MESH_FILTER = """
(
  "Phytotherapy"[MeSH] OR
  "Dietary Supplements"[MeSH] OR
  "Plant Extracts"[MeSH] OR
  "Medicine, Herbal"[MeSH] OR
  "Biological Products"[MeSH] OR
  "Vitamins"[MeSH] OR
  "Minerals"[MeSH] OR
  "Probiotics"[MeSH]
)
"""

STUDY_TYPE_FILTER = """
(
  "Clinical Trial"[pt] OR
  "Randomized Controlled Trial"[pt] OR
  "Meta-Analysis"[pt] OR
  "Systematic Review"[pt] OR
  "Clinical Trial, Phase II"[pt] OR
  "Clinical Trial, Phase III"[pt]
)
"""


def classify_study_type(pub_types: list[str]) -> str:
    joined = " ".join(pub_types).lower()
    if "meta-analysis" in joined:
        return "meta_analysis"
    if "systematic review" in joined:
        return "systematic_review"
    if "randomized controlled trial" in joined:
        return "rct"
    if "clinical trial" in joined:
        return "clinical_trial"
    return "other"


def _parse_efetch_xml(xml_text: str) -> list[dict]:
    records: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        log.warning("[PubMed NP] XML parse error: %s", e)
        return records

    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else ""
        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""

        abstract_parts: list[str] = []
        for abs_el in article.findall(".//AbstractText"):
            label = abs_el.get("Label", "")
            text = "".join(abs_el.itertext())
            if label:
                abstract_parts.append(f"{label}: {text}")
            else:
                abstract_parts.append(text)
        abstract_text = " ".join(abstract_parts)

        pub_types = [
            pt.text for pt in article.findall(".//PublicationType") if pt.text
        ]
        year_el = article.find(".//PubDate/Year")
        year = int(year_el.text) if year_el is not None and year_el.text and year_el.text.isdigit() else None

        records.append({
            "pmid": pmid,
            "title": title,
            "abstract_text": abstract_text,
            "pub_types": pub_types,
            "study_type": classify_study_type(pub_types),
            "year": year,
        })
    return records


async def search_pubmed_np(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    max_results: int = 100,
    options: PipelineOptions | None = None,
) -> list[dict]:
    opts = options or PipelineOptions()
    mesh = identifiers.mesh_id
    if not mesh:
        log.info("[PubMed NP] No MeSH ID for '%s' — skipping", identifiers.name)
        return []

    query = f'"{mesh}"[MeSH Terms] AND {NP_MESH_FILTER} AND {STUDY_TYPE_FILTER}'
    params: dict[str, str] = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "json",
    }
    api_key = get_ncbi_api_key()
    if api_key:
        params["api_key"] = api_key

    try:
        search_data = await get_json(session, f"{PUBMED_URL}/esearch.fcgi", params=params)
        if not search_data:
            return []
        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        fetch_params: dict[str, str] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "abstract",
            "retmode": "xml",
        }
        if api_key:
            fetch_params["api_key"] = api_key

        async with session.get(
            f"{PUBMED_URL}/efetch.fcgi",
            params=fetch_params,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            resp.raise_for_status()
            xml_text = await resp.text()

        records = _parse_efetch_xml(xml_text)
        log.info("[PubMed NP] %d abstracts for '%s'", len(records), identifiers.name)
        return records
    except Exception as e:
        log.warning("[PubMed NP] search failed for '%s': %s", identifiers.name, e)
        return []