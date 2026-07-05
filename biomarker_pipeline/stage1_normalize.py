"""Stage 1 — Identifier normalisation.

Resolves a biomarker name (gene symbol, protein name, or metabolite) to
canonical identifiers: HGNC symbol, UniProt accession, Ensembl gene ID, and
a list of known synonyms.

Lookup order:
  1. UniProt (human genes/proteins)
  2. HGNC (gene symbol fallback)
  3. PubChem (small-molecule metabolite fallback)
  4. Return bare name if nothing resolves
"""
import logging
import httpx

from .models import NormalizedBiomarker
from .cache import cache_get, cache_set

log = logging.getLogger(__name__)

UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
HGNC_SEARCH    = "https://rest.genenames.org/search/symbol/{symbol}"
PUBCHEM_NAME   = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/JSON"


async def _try_uniprot(name: str, client: httpx.AsyncClient) -> dict | None:
    params = {
        # reviewed:true restricts to Swiss-Prot (canonical) entries
        "query": f"gene_exact:{name} AND organism_id:9606 AND reviewed:true",
        "format": "json",
        "fields": "accession,gene_names,xref_ensembl",
        "size": "1",
    }
    try:
        r = await client.get(UNIPROT_SEARCH, params=params, timeout=12)
        r.raise_for_status()
        results = r.json().get("results", [])
        if not results:
            return None
        entry = results[0]
        accession = entry.get("primaryAccession", "")
        genes = entry.get("genes", [])
        symbol = (
            genes[0]["geneName"]["value"]
            if genes and "geneName" in genes[0]
            else name
        )
        synonyms: list[str] = []
        for g in genes:
            synonyms.extend(s["value"] for s in g.get("synonyms", []))
            synonyms.extend(o["value"] for o in g.get("orderedLocusNames", []))
        # UniProt Ensembl xrefs have transcript IDs in `id` (ENST*);
        # the gene ID (ENSG*) is nested in properties under key "GeneId".
        ensembl_id = ""
        for xref in entry.get("uniProtKBCrossReferences", []):
            if xref.get("database") == "Ensembl":
                for prop in xref.get("properties", []):
                    if prop.get("key") == "GeneId" and not ensembl_id:
                        ensembl_id = prop["value"].split(".")[0]
                if ensembl_id:
                    break
        return {
            "symbol": symbol,
            "uniprot_id": accession,
            "ensembl_id": ensembl_id,
            "synonyms": synonyms,
            "entity_type": "gene",
        }
    except Exception as e:
        log.debug("UniProt lookup failed for %s: %s", name, e)
        return None


async def _try_hgnc(name: str, client: httpx.AsyncClient) -> dict | None:
    url = HGNC_SEARCH.format(symbol=name)
    try:
        r = await client.get(url, headers={"Accept": "application/json"}, timeout=10)
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        if not docs:
            return None
        doc = docs[0]
        return {
            "symbol": doc.get("symbol", name),
            "ensembl_id": doc.get("ensembl_gene_id", ""),
            "synonyms": doc.get("alias_symbol", []) + doc.get("prev_symbol", []),
            "entity_type": "gene",
        }
    except Exception as e:
        log.debug("HGNC lookup failed for %s: %s", name, e)
        return None


async def _try_pubchem(name: str, client: httpx.AsyncClient) -> dict | None:
    url = PUBCHEM_NAME.format(name=name)
    try:
        r = await client.get(url, timeout=10)
        r.raise_for_status()
        compounds = r.json().get("PC_Compounds", [])
        if not compounds:
            return None
        return {"symbol": name, "entity_type": "metabolite", "synonyms": [name]}
    except Exception as e:
        log.debug("PubChem lookup failed for %s: %s", name, e)
        return None


async def normalize_biomarker(name: str, client: httpx.AsyncClient) -> NormalizedBiomarker:
    cached = cache_get("stage1", name)
    if cached:
        log.debug("Stage1 cache hit: %s", name)
        return NormalizedBiomarker(**cached)

    result = await _try_uniprot(name, client)
    if result is None:
        result = await _try_hgnc(name, client)
    if result is None:
        result = await _try_pubchem(name, client)

    if result:
        norm = NormalizedBiomarker(
            input_name=name,
            symbol=result.get("symbol", name),
            uniprot_id=result.get("uniprot_id"),
            ensembl_id=result.get("ensembl_id"),
            synonyms=list({name} | set(result.get("synonyms", []))),
            entity_type=result.get("entity_type", "gene"),
        )
    else:
        log.warning("No external identifier found for '%s'; proceeding with raw name.", name)
        norm = NormalizedBiomarker(
            input_name=name,
            symbol=name,
            synonyms=[name],
            entity_type="gene",
        )

    cache_set("stage1", name, norm.model_dump())
    return norm
