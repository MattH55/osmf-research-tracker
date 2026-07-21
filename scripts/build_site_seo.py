#!/usr/bin/env python3
"""Apply baseline technical SEO to the public research tracker and build its sitemap.

This deliberately only fills absent page metadata.  Hand-authored titles,
descriptions, canonical URLs, and rich structured data remain authoritative.
Run after any generator that writes HTML:

    python scripts/build_site_seo.py
    python scripts/build_site_seo.py --check
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://research.opensourcemed.info"
PUBLIC_DIRS = ("pais-cohorts", "chronic-disease-interventions", "disease-intelligence", "ntd")
EXCLUDED_DIRS = {"hospital-ranking", "med-freedom-map", "tools", "data", "config", "files"}
EXCLUDED_NAMES = {"agents-local.html", "clinical_trials-local.html"}


def public_pages() -> list[Path]:
    pages = []
    for page in ROOT.glob("*.html"):
        if page.name not in EXCLUDED_NAMES:
            pages.append(page)
    for name in PUBLIC_DIRS:
        directory = ROOT / name
        if directory.exists():
            pages.extend(directory.rglob("*.html"))
    return sorted(set(pages))


def url_for(page: Path) -> str:
    rel = page.relative_to(ROOT).as_posix()
    return ORIGIN + "/" + ("" if rel == "index.html" else rel)


def text_content(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def page_title(markup: str, page: Path) -> str:
    match = re.search(r"<title\b[^>]*>(.*?)</title\s*>", markup, re.I | re.S)
    if match and text_content(match.group(1)):
        return text_content(match.group(1))
    match = re.search(r"<h1\b[^>]*>(.*?)</h1\s*>", markup, re.I | re.S)
    if match and text_content(match.group(1)):
        return text_content(match.group(1)) + " | Open Source Medicine Research"
    return page.stem.replace("-", " ").title() + " | Open Source Medicine Research"


def page_description(markup: str, title: str) -> str:
    match = re.search(r"<p\b[^>]*>(.*?)</p\s*>", markup, re.I | re.S)
    description = text_content(match.group(1)) if match else ""
    if len(description) < 40:
        description = f"Evidence-focused research, clinical data, and reference material: {title}."
    return description[:157].rstrip(" ,;:-")


def has(markup: str, pattern: str) -> bool:
    return bool(re.search(pattern, markup, re.I | re.S))


def add_to_head(markup: str, tags: list[str]) -> str:
    if not tags:
        return markup
    return re.sub(r"</head\s*>", "\n  " + "\n  ".join(tags) + "\n</head>", markup, count=1, flags=re.I)


def is_redirect(markup: str) -> bool:
    return has(markup, r"<meta\b[^>]*http-equiv\s*=\s*['\"]?refresh")


def patch_page(page: Path, check: bool) -> tuple[bool, bool]:
    markup = page.read_text(encoding="utf-8")
    title = page_title(markup, page)
    canonical = url_for(page)
    redirect = is_redirect(markup)
    tags: list[str] = []
    redirect_robot_changed = False
    if redirect and has(markup, r"<meta\b[^>]*\bname\s*=\s*['\"]?robots\b"):
        updated = re.sub(
            r"<meta\b(?=[^>]*\bname\s*=\s*['\"]?robots\b)[^>]*>",
            '<meta name="robots" content="noindex, follow">', markup, count=1, flags=re.I)
        if updated != markup:
            markup = updated
            redirect_robot_changed = True
    if not has(markup, r"<meta\b[^>]*\bname\s*=\s*['\"]?description\b"):
        tags.append(f'<meta name="description" content="{html.escape(page_description(markup, title), quote=True)}">')
    if not has(markup, r"<meta\b[^>]*\bname\s*=\s*['\"]?robots\b"):
        tags.append('<meta name="robots" content="noindex, follow"' if redirect else '<meta name="robots" content="index, follow, max-image-preview:large">')
    if not has(markup, r"<link\b[^>]*\brel\s*=\s*['\"]?canonical\b"):
        tags.append(f'<link rel="canonical" href="{canonical}">')
    if not has(markup, r"<meta\b[^>]*\bproperty\s*=\s*['\"]?og:title\b"):
        tags.extend([
            '<meta property="og:type" content="website">',
            '<meta property="og:site_name" content="Open Source Medicine Research">',
            f'<meta property="og:title" content="{html.escape(title, quote=True)}">',
            f'<meta property="og:description" content="{html.escape(page_description(markup, title), quote=True)}">',
            f'<meta property="og:url" content="{canonical}">',
            '<meta name="twitter:card" content="summary">',
        ])
    if not has(markup, r"application/ld\+json") and not redirect:
        data = {"@context": "https://schema.org", "@type": "WebPage", "name": title,
                "url": canonical, "description": page_description(markup, title), "inLanguage": "en"}
        tags.append('<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + '</script>')
    if not tags:
        if redirect_robot_changed and not check:
            page.write_text(markup, encoding="utf-8")
        return redirect_robot_changed, redirect
    if check:
        return True, redirect
    page.write_text(add_to_head(markup, tags), encoding="utf-8")
    return True, redirect


def build_sitemap(pages: list[Path], redirects: set[Path], check: bool) -> bool:
    today = date.today().isoformat()
    urls = [page for page in pages if page not in redirects]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in urls:
        lines.extend(["  <url>", f"    <loc>{url_for(page)}</loc>", f"    <lastmod>{today}</lastmod>", "  </url>"])
    lines.append("</urlset>")
    output = "\n".join(lines) + "\n"
    target = ROOT / "sitemap.xml"
    changed = not target.exists() or target.read_text(encoding="utf-8") != output
    if changed and not check:
        target.write_text(output, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report stale metadata without writing")
    args = parser.parse_args()
    pages = public_pages()
    redirects: set[Path] = set()
    changed = []
    for page in pages:
        needs_update, redirect = patch_page(page, args.check)
        if redirect:
            redirects.add(page)
        if needs_update:
            changed.append(page.relative_to(ROOT).as_posix())
    sitemap_changed = build_sitemap(pages, redirects, args.check)
    print(f"SEO checked: {len(pages)} public pages; {len(changed)} metadata updates; sitemap {'updated' if sitemap_changed else 'current'}.")
    if args.check and (changed or sitemap_changed):
        for item in changed:
            print(f"  stale metadata: {item}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
