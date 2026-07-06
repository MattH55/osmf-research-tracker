"""GreenMedInfo disease page → therapeutic substance lookup."""
from __future__ import annotations

import logging
import re
from collections import Counter
from urllib.parse import quote_plus

import aiohttp

from ...models import DiseaseIdentifiers
from ...options import PipelineOptions
from .gmi_disease_index import (
    gmi_disease_page_url,
    load_gmi_disease_index,
    refresh_gmi_disease_index,
    resolve_gmi_disease_slug,
)
from .web_fetch import fetch_html

log = logging.getLogger(__name__)

GMI_BASE = "https://greenmedinfo.com"
_SUBSTANCE_RE = re.compile(
    r'href="(?:https?://(?:www\.)?greenmedinfo\.com)?(/substance/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
_ARTICLE_BLOCK_RE = re.compile(r'<dt class="article[^"]*">(.*?)</dt>', re.S | re.I)
_ARTICLE_TITLE_RE = re.compile(
    r'<h2><a href="(/article/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
_PMID_RE = re.compile(r"pubmed/(\d+)", re.I)
_STUDY_TYPE_RE = re.compile(r"Study Type</b>\s*:\s*([^<]+)", re.I)


def gmi_search_fallback_url(disease_name: str) -> str:
    query = f"disease {disease_name}"
    return f"{GMI_BASE}/gmi-search?text={quote_plus(query)}"


def _parse_substances(html: str) -> list[dict]:
    counts: Counter[str] = Counter()
    names: dict[str, str] = {}

    for path, raw_name in _SUBSTANCE_RE.findall(html):
        slug = path.strip("/").removeprefix("substance/").strip("/")
        if not slug:
            continue
        name = re.sub(r"\s+", " ", raw_name).strip()
        counts[slug] += 1
        if name:
            names[slug] = name

    records: list[dict] = []
    for slug, count in counts.most_common(80):
        records.append({
            "name": names.get(slug, slug.replace("-", " ").title()),
            "slug": slug,
            "url": f"{GMI_BASE}/substance/{slug}",
            "source": "GreenMedInfo",
            "article_count": count,
        })
    return records


def _parse_articles(html: str, *, limit: int = 150) -> list[dict]:
    articles: list[dict] = []
    seen: set[str] = set()

    for block in _ARTICLE_BLOCK_RE.findall(html):
        title_match = _ARTICLE_TITLE_RE.search(block)
        if not title_match:
            continue
        article_path, title = title_match.groups()
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            continue

        pmid_match = _PMID_RE.search(block)
        pmid = pmid_match.group(1) if pmid_match else None
        study_match = _STUDY_TYPE_RE.search(block)
        study_type = study_match.group(1).strip() if study_match else None

        substance_slugs = [
            s.strip("/").removeprefix("substance/")
            for s in re.findall(r'href="(?:https?://(?:www\.)?greenmedinfo\.com)?/substance/([^"]+)"', block, re.I)
        ]

        key = pmid or article_path
        if key in seen:
            continue
        seen.add(key)

        article_slug = article_path.strip("/").removeprefix("article/")
        row = {
            "title": title,
            "url": f"{GMI_BASE}/article/{article_slug}",
            "pmid": pmid,
            "study_type": study_type,
            "substance_slugs": sorted(set(substance_slugs)),
        }
        if pmid:
            row["pubmed_url"] = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
        articles.append(row)
        if len(articles) >= limit:
            break
    return articles


def _attach_article_findings(records: list[dict], articles: list[dict]) -> None:
    by_slug: dict[str, list[str]] = {}
    for art in articles:
        snippet = art["title"]
        if art.get("study_type"):
            snippet = f"{art['study_type']}: {snippet}"
        for slug in art.get("substance_slugs", []):
            by_slug.setdefault(slug, []).append(snippet[:160])

    for rec in records:
        snippets = by_slug.get(rec["slug"], [])
        if snippets:
            rec["key_findings"] = "; ".join(snippets[:2])[:280]


async def search_greenmedinfo_substances(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    *,
    disease_slug: str = "",
    options: PipelineOptions | None = None,
) -> tuple[list[dict], str, list[dict]]:
    """Return substances and articles from the GMI disease page when available."""
    opts = options or PipelineOptions()
    index = load_gmi_disease_index()
    if not index and opts.use_cache:
        await refresh_gmi_disease_index(session, use_cache=opts.use_cache)
        index = load_gmi_disease_index()

    gmi_slug = resolve_gmi_disease_slug(disease_slug, identifiers.name, index=index)
    if gmi_slug:
        url = gmi_disease_page_url(gmi_slug)
    else:
        url = gmi_search_fallback_url(identifiers.name)
        log.info("[GMI] no disease page match for '%s' — using search fallback", identifiers.name)

    html = await fetch_html(
        session,
        url,
        namespace="greenmedinfo",
        cache_key=url,
        use_cache=opts.use_cache,
    )
    if not html:
        return [], url, []

    if "gmi-search" in url or "/gmi-search" in url:
        log.info("[GMI] search fallback for '%s' (no curated disease page)", identifiers.name)
        return [], url, []

    records = _parse_substances(html)
    articles = _parse_articles(html)
    _attach_article_findings(records, articles)

    log.info(
        "[GMI] %d substances, %d articles for '%s' (%s)",
        len(records),
        len(articles),
        identifiers.name,
        gmi_slug or "search",
    )
    return records, url, articles