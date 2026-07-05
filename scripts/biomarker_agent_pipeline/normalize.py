"""Stage 1: biomarker identifier normalization."""
from __future__ import annotations

import re
import urllib.parse

from .config import ncbi_api_key
from .http_util import request_json
from .models import NormalizedBiomarker

UNIPROT_SEARCH = "https://rest.uniprot.org/uniprotkb/search"
HGNC_SEARCH = "https://rest.genenames.org/fetch/symbol/{symbol}"
ENSEMBL_LOOKUP = "https://rest.ensembl.org/lookup/symbol/homo_sapiens/{symbol}"
PUBCHEM_NAME = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/cids/JSON"
CHEBI_SEARCH = "https://www.ebi.ac.uk/ols/api/search"
NCBI_ESARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


def _clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


def _strip_parentheticals(name: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", name).strip()


def _gene_like(name: str) -> bool:
    core = _strip_parentheticals(name)
    if re.search(r"\b(IL|TNF|CRP|IFN|CXCL|CCL|GFAP|BDNF|LDH|ESR)\b", core, re.I):
        return True
    if re.match(r"^[A-Z][A-Z0-9-]{1,12}$", core.replace(" ", "")):
        return True
    return bool(re.search(r"\b(protein|receptor|cytokine|antibody|factor|enzyme)\b", core, re.I))


def _metabolite_like(name: str) -> bool:
    return bool(
        re.search(
            r"\b(acid|ine|ate|ose|ol|amide|ine|lactate|glucose|ferritin|homocysteine|ceramide|metabolite)\b",
            name,
            re.I,
        )
    )


def _ncbi_params(extra: dict) -> dict:
    params = {"tool": "OSMF-BiomarkerAgentPipeline", "email": "research@opensourcemed.info", **extra}
    key = ncbi_api_key()
    if key:
        params["api_key"] = key
    return params


def _mesh_synonyms(term: str) -> list[str]:
    try:
        params = _ncbi_params({"db": "mesh", "term": term, "retmax": "5", "retmode": "json"})
        data = request_json("ncbi_mesh", term, "GET", NCBI_ESARCH, params=params)
        ids = data.get("esearchresult", {}).get("idlist", [])
        return [f"MeSH:{mid}" for mid in ids[:3]]
    except Exception:
        return []


def _uniprot_resolve(name: str) -> dict | None:
    queries = [
        f"gene_exact:{name} AND organism_id:9606",
        f"{name} AND organism_id:9606",
    ]
    for q in queries:
        params = {"query": q, "format": "json", "size": 3}
        data = request_json("uniprot", q, "GET", UNIPROT_SEARCH, params=params)
        results = data.get("results", [])
        if not results:
            continue
        best = results[0]
        genes = best.get("genes") or []
        symbol = None
        for g in genes:
            gn = g.get("geneName", {})
            if gn.get("value"):
                symbol = gn["value"]
                break
        syns = []
        for g in genes:
            for syn in g.get("synonyms", []):
                if syn.get("value"):
                    syns.append(syn["value"])
        desc = (best.get("proteinDescription") or {}).get("recommendedName", {})
        full = (desc.get("fullName") or {}).get("value")
        if full:
            syns.append(full)
        return {
            "uniprot_id": best.get("primaryAccession"),
            "symbol": symbol or name.upper(),
            "synonyms": list(dict.fromkeys([s for s in syns if s])),
        }
    return None


def _hgnc_symbol(symbol: str) -> str | None:
    try:
        url = HGNC_SEARCH.format(symbol=urllib.parse.quote(symbol))
        data = request_json("hgnc", symbol, "GET", url, headers={"Accept": "application/json"})
        docs = data.get("response", {}).get("docs", [])
        return docs[0].get("symbol") if docs else None
    except Exception:
        return None


def _ensembl_id(symbol: str) -> str | None:
    try:
        url = ENSEMBL_LOOKUP.format(symbol=urllib.parse.quote(symbol))
        data = request_json("ensembl", symbol, "GET", url, headers={"Content-Type": "application/json"})
        return data.get("id")
    except Exception:
        return None


def _pubchem_cid(name: str) -> str | None:
    try:
        url = PUBCHEM_NAME.format(name=urllib.parse.quote(name))
        data = request_json("pubchem", name, "GET", url)
        cids = data.get("IdentifierList", {}).get("CID", [])
        return str(cids[0]) if cids else None
    except Exception:
        return None


def _chebi_id(name: str) -> str | None:
    try:
        params = {"q": name, "ontology": "chebi", "rows": 3}
        data = request_json("chebi", name, "GET", CHEBI_SEARCH, params=params)
        docs = data.get("response", {}).get("docs", [])
        return docs[0].get("obo_id") if docs else None
    except Exception:
        return None


def normalize_biomarker(biomarker: str) -> NormalizedBiomarker:
    raw = _clean_name(biomarker)
    base = _strip_parentheticals(raw)
    notes: list[str] = []
    synonyms = list(dict.fromkeys([raw, base] + re.split(r"[,;/]+", base)))

    entity_type = "unknown"
    if _gene_like(base):
        entity_type = "protein"
    elif _metabolite_like(base):
        entity_type = "metabolite"

    symbol = None
    uniprot_id = None
    ensembl_id = None
    chebi_id = None
    pubchem_cid = None

    # Try extracting gene symbol from parentheses e.g. Interleukin-6 (IL-6)
    paren = re.findall(r"\(([^)]+)\)", raw)
    candidates = [base] + paren + [_strip_parentheticals(s) for s in synonyms]
    gene_candidates = []
    for c in candidates:
        c = c.strip()
        if not c:
            continue
        compact = re.sub(r"[^A-Za-z0-9]", "", c).upper()
        if 2 <= len(compact) <= 12:
            gene_candidates.append(compact)
        gene_candidates.append(c)

    for cand in dict.fromkeys(gene_candidates):
        up = _uniprot_resolve(cand)
        if up:
            symbol = up["symbol"]
            uniprot_id = up["uniprot_id"]
            synonyms.extend(up.get("synonyms", []))
            entity_type = "gene" if symbol else "protein"
            break

    if not symbol and entity_type == "metabolite":
        chebi_id = _chebi_id(base)
        pubchem_cid = _pubchem_cid(base)
        if chebi_id:
            notes.append(f"Resolved metabolite via ChEBI {chebi_id}")
        if pubchem_cid:
            notes.append(f"Resolved metabolite via PubChem CID {pubchem_cid}")

    if symbol:
        official = _hgnc_symbol(symbol)
        if official:
            symbol = official
        ensembl_id = _ensembl_id(symbol)

    synonyms.extend(_mesh_synonyms(base))
    synonyms = list(dict.fromkeys([s for s in synonyms if s and len(s) >= 2]))[:20]

    if not uniprot_id and not chebi_id and not pubchem_cid:
        notes.append("Limited structured ID resolution; literature queries will use synonym expansion.")

    return NormalizedBiomarker(
        input=raw,
        symbol=symbol,
        uniprot_id=uniprot_id,
        ensembl_id=ensembl_id,
        chebi_id=chebi_id,
        pubchem_cid=pubchem_cid,
        synonyms=synonyms,
        entity_type=entity_type if (uniprot_id or symbol) else entity_type,
        resolution_notes=notes,
    )