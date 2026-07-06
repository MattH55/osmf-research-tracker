"""GreenMedInfo disease → therapeutic substance lookup."""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

import aiohttp

from ...models import DiseaseIdentifiers
from ...options import PipelineOptions
from .web_fetch import fetch_html

log = logging.getLogger(__name__)

GMI_BASE = "https://www.greenmedinfo.com"
_SUBSTANCE_RE = re.compile(
    r'href="https?://(?:www\.)?greenmedinfo\.com/substance/([^"]+)"[^>]*>\s*([^<]+?)\s*</a>',
    re.I,
)
_ARTICLE_RE = re.compile(
    r'class="gs-title[^"]*"[^>]*href="https?://(?:www\.)?greenmedinfo\.com/article/([^"]+)"[^>]*>\s*([^<]+?)\s*</a>',
    re.I,
)


def _gmi_query_name(disease_name: str) -> str:
    simplified = re.sub(
        r"\b(mellitus|disease|disorder|syndrome|condition)\b",
        "",
        disease_name,
        flags=re.I,
    )
    simplified = re.sub(r"\s+", " ", simplified).strip(" ,-")
    return simplified or disease_name


def gmi_search_url(disease_name: str) -> str:
    query = f"disease {_gmi_query_name(disease_name)}"
    return f"{GMI_BASE}/gmi-search?text={quote_plus(query)}"


def _parse_substances(html: str) -> list[dict]:
    seen: set[str] = set()
    records: list[dict] = []

    for slug, raw_name in _SUBSTANCE_RE.findall(html):
        slug = slug.strip("/")
        name = re.sub(r"\s+", " ", raw_name).strip()
        if not name or slug in seen:
            continue
        seen.add(slug)
        records.append({
            "name": name,
            "slug": slug,
            "url": f"{GMI_BASE}/substance/{slug}",
            "source": "GreenMedInfo",
        })

    if records:
        return records

    # Fallback: substance slugs without visible titles
    for slug in re.findall(r"/substance/([a-z0-9-]+)", html, re.I):
        if slug in seen:
            continue
        seen.add(slug)
        name = slug.replace("-", " ").title()
        records.append({
            "name": name,
            "slug": slug,
            "url": f"{GMI_BASE}/substance/{slug}",
            "source": "GreenMedInfo",
        })
    return records


def _article_snippets(html: str, limit: int = 5) -> list[str]:
    snippets: list[str] = []
    for _slug, title in _ARTICLE_RE.findall(html):
        clean = re.sub(r"\s+", " ", title).strip()
        if clean and clean not in snippets:
            snippets.append(clean)
        if len(snippets) >= limit:
            break
    return snippets


async def search_greenmedinfo_substances(
    identifiers: DiseaseIdentifiers,
    session: aiohttp.ClientSession,
    *,
    options: PipelineOptions | None = None,
) -> tuple[list[dict], str, list[dict]]:
    """Return substance records, GMI search URL, and article references."""
    opts = options or PipelineOptions()
    url = gmi_search_url(identifiers.name)
    html = await fetch_html(
        session,
        url,
        namespace="greenmedinfo",
        cache_key=url,
        use_cache=opts.use_cache,
    )
    if not html:
        return [], url, []

    records = _parse_substances(html)[:40]
    article_rows = []
    for slug, title in _ARTICLE_RE.findall(html)[:15]:
        clean = re.sub(r"\s+", " ", title).strip()
        if clean:
            article_rows.append({
                "title": clean,
                "url": f"{GMI_BASE}/article/{slug.strip('/')}",
            })
    articles = [a["title"] for a in article_rows]
    if articles and records:
        summary = "; ".join(articles[:3])
        for rec in records[:5]:
            rec.setdefault("key_findings", summary[:280])

    log.info("[GMI] %d substances for '%s'", len(records), identifiers.name)
    return records, url, article_rows