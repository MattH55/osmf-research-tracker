"""Resolve supporting publication links for natural products."""
from __future__ import annotations

import re
from typing import Any

_GMI_SUBSTANCE_RE = re.compile(r"greenmedinfo\.com/substance/([^/?#]+)", re.I)
_PUBMED_RE = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.I)


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").strip()).lower()


def _gmi_substance_slugs(external_links: list[dict] | None) -> set[str]:
    slugs: set[str] = set()
    for link in external_links or []:
        url = link.get("url") or ""
        match = _GMI_SUBSTANCE_RE.search(url)
        if match:
            slugs.add(match.group(1).lower())
    return slugs


def _key_finding_snippets(key_findings: str | None) -> list[str]:
    if not key_findings:
        return []
    snippets: list[str] = []
    for part in key_findings.split(";"):
        text = part.strip()
        if ": " in text:
            text = text.split(": ", 1)[1].strip()
        if text:
            snippets.append(_normalize_title(text))
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


def _lit_from_clinical_evidence(np: dict) -> list[dict]:
    pubs: list[dict] = []
    ev = np.get("clinical_evidence") or {}
    for lit in ev.get("literature") or []:
        title = (lit.get("title") or "").strip()
        url = (lit.get("url") or "").strip()
        if not title and not url:
            continue
        pmid = lit.get("pmid")
        if not pmid and url:
            pmid_match = _PUBMED_RE.search(url)
            pmid = pmid_match.group(1) if pmid_match else None
        row = {
            "title": title or url,
            "url": url,
            "source": lit.get("publication_type_label") or "PubMed",
            "study_type": lit.get("publication_type_label"),
        }
        if pmid:
            row["pmid"] = pmid
            row["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        pubs.append(row)
    return pubs


def _lit_from_gmi_articles(
    np: dict,
    gmi_articles: list[dict] | None,
) -> list[dict]:
    if not gmi_articles:
        return []

    substance_slugs = _gmi_substance_slugs(np.get("external_links"))
    snippets = _key_finding_snippets(np.get("key_findings"))
    pubs: list[dict] = []

    for article in gmi_articles:
        title = (article.get("title") or "").strip()
        if not title:
            continue
        norm_title = _normalize_title(title)

        matched = False
        article_slugs = {s.lower() for s in article.get("substance_slugs") or []}
        if substance_slugs and article_slugs & substance_slugs:
            matched = True
        elif snippets:
            for snippet in snippets:
                if snippet in norm_title or norm_title in snippet:
                    matched = True
                    break
                # Prefix overlap for truncated GMI snippets in key_findings.
                shorter, longer = sorted((snippet, norm_title), key=len)
                if len(shorter) >= 24 and longer.startswith(shorter[:24]):
                    matched = True
                    break

        if not matched:
            continue

        row = {
            "title": title,
            "url": article.get("url") or "",
            "source": "GreenMedInfo",
            "study_type": article.get("study_type"),
        }
        if article.get("pmid"):
            row["pmid"] = article["pmid"]
        if article.get("pubmed_url"):
            row["pubmed_url"] = article["pubmed_url"]
        pubs.append(row)

    return pubs


def _lit_from_stored(np: dict) -> list[dict]:
    pubs: list[dict] = []
    for row in np.get("supporting_publications") or []:
        title = (row.get("title") or "").strip()
        url = _pub_url(row) or (row.get("url") or "").strip()
        if not title and not url:
            continue
        pubs.append({
            "title": title or url,
            "url": url,
            "source": row.get("source") or "Reference",
            "study_type": row.get("study_type"),
            "pmid": row.get("pmid"),
            "pubmed_url": row.get("pubmed_url"),
        })
    return pubs


def resolve_np_publications(
    np: dict,
    *,
    gmi_articles: list[dict] | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return deduplicated supporting publications, preferring PubMed URLs."""
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for source_rows in (
        _lit_from_stored(np),
        _lit_from_clinical_evidence(np),
        _lit_from_gmi_articles(np, gmi_articles),
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
    limit: int = 3,
) -> list[dict]:
    """Attach supporting_publications to each natural product row."""
    out: list[dict] = []
    for np in np_rows:
        row = dict(np)
        pubs = resolve_np_publications(np, gmi_articles=gmi_articles, limit=limit)
        if pubs:
            row["supporting_publications"] = pubs
        out.append(row)
    return out