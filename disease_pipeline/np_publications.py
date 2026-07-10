"""Resolve supporting publication links for natural products."""
from __future__ import annotations

import re
from typing import Any

from .adapters.natural_products.normalize_np import load_np_synonyms_data
from .cache import cache_get

GMI_ARTICLE_LIMIT = 150
_GMI_BASE = "https://greenmedinfo.com"
_GMI_SUBSTANCE_RE = re.compile(r"greenmedinfo\.com/substance/([^/?#]+)", re.I)
_PUBMED_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.I)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_COMMON_TOKENS = frozenset({
    "acid", "extract", "oil", "seed", "root", "leaf", "herb", "supplement",
    "powder", "tablets", "capsule", "natural", "organic", "type", "syndrome",
    "disease", "disorder", "mellitus", "chronic", "acute", "patients", "treatment",
    "study", "human", "review", "analysis", "meta", "clinical", "trial",
})


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip()).lower()


def _tokenize(text: str) -> set[str]:
    return {tok for tok in _TOKEN_RE.findall((text or "").lower()) if len(tok) >= 4}


def _gmi_substance_slugs(external_links: list[dict] | None) -> set[str]:
    slugs: set[str] = set()
    for link in external_links or []:
        url = link.get("url") or ""
        match = _GMI_SUBSTANCE_RE.search(url)
        if match:
            slugs.add(match.group(1).lower())
    return slugs


def _np_match_tokens(np: dict, *, disease_name: str | None = None) -> set[str]:
    tokens: set[str] = set()
    names = [np.get("name", "")] + list(np.get("common_names") or [])
    for name in names:
        tokens |= _tokenize(name)

    for slug in _gmi_substance_slugs(np.get("external_links")):
        tokens |= _tokenize(slug.replace("-", " "))
        slug_parts = slug.split("-")
        if slug_parts:
            tokens.add(slug_parts[0])

    data = load_np_synonyms_data()
    for name in names:
        key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        meta = data.get(key)
        if not meta:
            continue
        for syn in meta.get("synonyms", []):
            tokens |= _tokenize(syn)
        tokens |= _tokenize(meta.get("canonical_name", ""))

    if disease_name:
        tokens -= _tokenize(disease_name)
    tokens -= _COMMON_TOKENS
    return tokens


def _slug_matches(article_slugs: set[str], np_slugs: set[str]) -> bool:
    if article_slugs & np_slugs:
        return True
    for article_slug in article_slugs:
        for np_slug in np_slugs:
            if article_slug.startswith(np_slug) or np_slug.startswith(article_slug):
                return True
            a_head = article_slug.split("-", 1)[0]
            n_head = np_slug.split("-", 1)[0]
            if len(a_head) >= 6 and a_head == n_head:
                return True
    return False


def _title_matches_tokens(title: str, tokens: set[str]) -> bool:
    if not tokens:
        return False
    norm_title = _normalize_title(title)
    title_tokens = _tokenize(norm_title)
    overlap = tokens & title_tokens
    if overlap:
        return True
    for token in sorted(tokens, key=len, reverse=True):
        if len(token) >= 5 and token in norm_title:
            return True
    return False


def _key_finding_snippets(key_findings: str | None, *, disease_name: str | None = None) -> list[str]:
    if not key_findings:
        return []
    disease_norm = _normalize_title(disease_name or "")
    snippets: list[str] = []
    for part in key_findings.split(";"):
        text = part.strip()
        if ": " in text:
            text = text.split(": ", 1)[1].strip()
        if not text:
            continue
        norm = _normalize_title(text)
        if disease_norm and (norm == disease_norm or norm in disease_norm or disease_norm in norm):
            continue
        if len(norm) < 20:
            continue
        snippets.append(norm)
    return snippets


def _pub_url(row: dict) -> str:
    return (row.get("pubmed_url") or row.get("url") or "").strip()


def _pub_key(row: dict) -> str:
    url = _pub_url(row)
    if url:
        pmid_match = _PUBMED_RE.search(url)
        if pmid_match:
            return f"pmid:{pmid_match.group(1)}"
        return f"url:{url.lower()}"
    title = _normalize_title(row.get("title", ""))
    return f"title:{title}" if title else ""


def _row_from_lit(lit: dict, *, default_source: str = "PubMed") -> dict | None:
    title = (lit.get("title") or "").strip()
    url = (lit.get("url") or "").strip()
    if not title and not url:
        return None
    if "greenmedinfo" in url.lower() and not lit.get("pmid") and not lit.get("pubmed_url"):
        return None
    pmid = lit.get("pmid")
    if not pmid and url:
        pmid_match = _PUBMED_RE.search(url)
        pmid = pmid_match.group(1) if pmid_match else None
    row = {
        "title": title or url,
        "url": url,
        "source": lit.get("publication_type_label") or lit.get("source") or default_source,
        "study_type": lit.get("publication_type_label") or lit.get("study_type"),
    }
    if pmid:
        row["pmid"] = pmid
        row["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        row["url"] = row["pubmed_url"]
    return row


def _lit_from_clinical_evidence(np: dict) -> list[dict]:
    pubs: list[dict] = []
    ev = np.get("clinical_evidence") or {}
    for lit in ev.get("literature") or []:
        row = _row_from_lit(lit)
        if row:
            pubs.append(row)
    return pubs


def _lit_from_extra_evidence(np: dict, extra_evidence: dict[str, dict] | None) -> list[dict]:
    if not extra_evidence:
        return []
    ev = extra_evidence.get(np.get("canonical_id", "")) or {}
    pubs: list[dict] = []
    for lit in ev.get("literature") or []:
        row = _row_from_lit(lit)
        if row:
            pubs.append(row)
    return pubs


def _lit_from_gmi_articles(
    np: dict,
    gmi_articles: list[dict] | None,
    *,
    disease_name: str | None = None,
) -> list[dict]:
    if not gmi_articles:
        return []

    substance_slugs = _gmi_substance_slugs(np.get("external_links"))
    tokens = _np_match_tokens(np, disease_name=disease_name)
    snippets = _key_finding_snippets(np.get("key_findings"), disease_name=disease_name)
    pubs: list[dict] = []

    for article in gmi_articles:
        title = (article.get("title") or "").strip()
        if not title:
            continue
        norm_title = _normalize_title(title)

        matched = False
        article_slugs = {s.lower() for s in article.get("substance_slugs") or []}
        if substance_slugs and _slug_matches(article_slugs, substance_slugs):
            matched = True
        elif tokens and _title_matches_tokens(title, tokens):
            matched = True
        elif snippets:
            for snippet in snippets:
                if snippet in norm_title or norm_title in snippet:
                    matched = True
                    break
                shorter, longer = sorted((snippet, norm_title), key=len)
                if len(shorter) >= 24 and longer.startswith(shorter[:24]):
                    matched = True
                    break

        if not matched:
            continue

        row = {
            "title": title,
            "url": article.get("pubmed_url") or article.get("url") or "",
            "source": "GreenMedInfo",
            "study_type": article.get("study_type"),
        }
        if article.get("pmid"):
            row["pmid"] = article["pmid"]
            row["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/"
            row["url"] = row["pubmed_url"]
        pubs.append(row)

    return pubs


def _lit_from_stored(np: dict) -> list[dict]:
    pubs: list[dict] = []
    for row in np.get("supporting_publications") or []:
        title = (row.get("title") or "").strip()
        url = _pub_url(row) or (row.get("url") or "").strip()
        if not title and not url:
            continue
        if "greenmedinfo" in url.lower() and not row.get("pubmed_url") and not row.get("pmid"):
            continue
        source = row.get("source") or "Reference"
        if source == "GreenMedInfo" or str(source).lower() == "greenmedinfo":
            source = row.get("study_type") or "Literature"
        out = {
            "title": title or url,
            "url": url,
            "source": source,
            "study_type": row.get("study_type"),
            "pmid": row.get("pmid"),
            "pubmed_url": row.get("pubmed_url"),
        }
        if out.get("pubmed_url"):
            out["url"] = out["pubmed_url"]
        elif "greenmedinfo" in out["url"].lower():
            continue
        pubs.append(out)
    return pubs


def refresh_gmi_articles_from_cache(
    disease_slug: str,
    disease_name: str,
    *,
    limit: int = GMI_ARTICLE_LIMIT,
) -> list[dict]:
    """Re-parse cached GreenMedInfo disease HTML with a higher article cap."""
    from .adapters.natural_products.gmi_disease_index import (
        load_gmi_disease_index,
        resolve_gmi_disease_slug,
    )
    from .adapters.natural_products.greenmedinfo_np import _parse_articles

    index = load_gmi_disease_index()
    gmi_slug = resolve_gmi_disease_slug(disease_slug, disease_name, index=index)
    if not gmi_slug:
        return []
    url = f"{_GMI_BASE}/disease/{gmi_slug}"
    html = cache_get("greenmedinfo", url, ttl_days=365)
    if not html:
        return []
    return _parse_articles(html, limit=limit)


def resolve_np_publications(
    np: dict,
    *,
    gmi_articles: list[dict] | None = None,
    extra_evidence: dict[str, dict] | None = None,
    disease_name: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return deduplicated supporting publications, preferring PubMed URLs."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source_rows in (
        _lit_from_stored(np),
        _lit_from_clinical_evidence(np),
        _lit_from_extra_evidence(np, extra_evidence),
        _lit_from_gmi_articles(np, gmi_articles, disease_name=disease_name),
    ):
        for row in source_rows:
            key = _pub_key(row)
            if not key or key in seen:
                continue
            seen.add(key)
            url = _pub_url(row) or row.get("url") or ""
            merged.append({
                "title": row.get("title") or url,
                "url": url,
                "source": row.get("source") or "Reference",
                "study_type": row.get("study_type"),
                "pmid": row.get("pmid"),
            })

    return merged[:limit]


def attach_supporting_publications(
    np_rows: list[dict],
    *,
    gmi_articles: list[dict] | None = None,
    extra_evidence: dict[str, dict] | None = None,
    disease_name: str | None = None,
    limit: int = 3,
) -> list[dict]:
    """Attach supporting_publications to each natural product row."""
    out: list[dict] = []
    for np in np_rows:
        row = dict(np)
        pubs = resolve_np_publications(
            np,
            gmi_articles=gmi_articles,
            extra_evidence=extra_evidence,
            disease_name=disease_name,
            limit=limit,
        )
        if pubs:
            row["supporting_publications"] = pubs
        elif "supporting_publications" in row:
            del row["supporting_publications"]
        out.append(row)
    return out


def enrich_disease_publications(
    data: dict,
    *,
    refresh_gmi: bool = True,
    limit: int = 3,
) -> bool:
    """Refresh GMI article index and supporting_publications on a disease blob."""
    summary = data.setdefault("summary", {})
    condition = data.get("condition") or {}
    disease_name = condition.get("name") or condition.get("shortName") or ""
    disease_slug = data.get("slug", "")

    changed = False
    gmi_articles = summary.get("gmi_articles") or []
    if refresh_gmi and disease_slug and disease_name:
        refreshed = refresh_gmi_articles_from_cache(disease_slug, disease_name)
        if refreshed and len(refreshed) > len(gmi_articles):
            summary["gmi_articles"] = refreshed
            gmi_articles = refreshed
            changed = True

    nps = data.get("natural_products") or []
    if not nps:
        return changed

    extra_evidence = data.get("natural_product_evidence") or {}
    enriched = attach_supporting_publications(
        nps,
        gmi_articles=gmi_articles,
        extra_evidence=extra_evidence,
        disease_name=disease_name,
        limit=limit,
    )

    before = [np.get("supporting_publications") for np in nps]
    after = [np.get("supporting_publications") for np in enriched]
    if before != after:
        data["natural_products"] = enriched
        changed = True
    return changed