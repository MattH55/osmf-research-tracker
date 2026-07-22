#!/usr/bin/env python3
"""Apply baseline + medical technical SEO to the public research tracker and build its sitemap.

Fills absent metadata across all public HTML pages: canonical URLs, Open Graph, Twitter Cards,
structured data (WebSite + MedicalWebPage + MedicalCondition + BreadcrumbList where applicable).

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
SITE_NAME = "Open Source Medicine — Research Tracker"
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


def has(markup: str, pattern: str) -> bool:
    return bool(re.search(pattern, markup, re.I | re.S))


def is_redirect(markup: str) -> bool:
    return has(markup, r"<meta\b[^>]*http-equiv\s*=\s*['\"]?refresh")


def page_title(markup: str, page: Path) -> str:
    match = re.search(r"<title\b[^>]*>(.*?)</title\s*>", markup, re.I | re.S)
    if match and text_content(match.group(1)):
        return text_content(match.group(1))
    match = re.search(r"<h1\b[^>]*>(.*?)</h1\s*>", markup, re.I | re.S)
    if match and text_content(match.group(1)):
        return text_content(match.group(1)) + " | Open Source Medicine Research"
    return page.stem.replace("-", " ").title() + " | Open Source Medicine Research"


def page_description(markup: str, title: str) -> str:
    """Extract a meaningful description, preferring lede/intro paragraphs over anything else."""
    # try to find a "lede" class paragraph
    match = re.search(r'<p\b[^>]*\bclass\s*=\s*[\'"]?[^\'">]*lede[^\'">]*[\'"]?\s*[^>]*>(.*?)</p\s*>', markup, re.I | re.S)
    if match:
        desc = text_content(match.group(1))
        if len(desc) >= 50:
            return desc[:157].rstrip(" ,;:-")
    # try meta description already present (hand-authored)
    match = re.search(r'<meta\b[^>]*\bname\s*=\s*[\'"]?description[\'"]?\s*[^>]*\bcontent\s*=\s*[\'"]([^\'"]+)[\'"]', markup, re.I | re.S)
    if match:
        desc = text_content(match.group(1))
        if len(desc) >= 40:
            return desc[:157].rstrip(" ,;:-")
    # try first meaningful paragraph (skip nav / header-like paras)
    for match in re.finditer(r"<p\b[^>]*>(.*?)</p\s*>", markup, re.I | re.S):
        desc = text_content(match.group(1))
        if len(desc) >= 50:
            return desc[:157].rstrip(" ,;:-")
    # fallback
    description = f"Evidence-focused research, clinical data, and reference material: {title}."
    return description[:157].rstrip(" ,;:-")


def breadcrumb_items(page: Path) -> list[dict]:
    """Return schema.org BreadcrumbList items for this page's URL path."""
    rel = page.relative_to(ROOT).as_posix()
    if rel == "index.html":
        return [{"@type": "ListItem", "position": 1, "name": "Home", "item": ORIGIN + "/"}]
    parts = rel.split("/")
    items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": ORIGIN + "/"}]
    if parts[-1] == "index.html":
        parts = parts[:-1]
    pos = 2
    for i, segment in enumerate(parts):
        if segment.endswith(".html"):
            segment = segment[:-5]
        name = segment.replace("-", " ").title()
        url = ORIGIN + "/" + "/".join(parts[:i + 1])
        items.append({"@type": "ListItem", "position": pos, "name": name, "item": url})
        pos += 1
    return items


def detect_medical_conditions(markup: str) -> list[dict]:
    """Detect medical conditions mentioned in the page for richer schema."""
    conditions = []
    patterns = {
        "Long COVID": ["long.covid", "PASC", "post-acute sequelae of COVID"],
        "ME/CFS": ["me.cfs", "myalgic encephalomyelitis", "chronic fatigue syndrome", "ME/CFS", "CFS"],
        "PACVS": ["PACVS", "post-acute COVID-19 vaccination syndrome", "post-vaccination syndrome"],
        "POTS": ["POTS", "postural orthostatic tachycardia", "dysautonomia"],
        "MCAS": ["MCAS", "mast cell activation syndrome"],
        "Gulf War Illness": ["gulf.war.illness", "GWI", "gulf war syndrome"],
        "Lyme Disease": ["lyme", "PTLDS", "post-treatment lyme", "borreliosis"],
        "Post-Polio Syndrome": ["post.polio", "polio"],
        "Fibromyalgia": ["fibromyalgia", "chronic widespread pain"],
        "Post-Sepsis Syndrome": ["post.sepsis", "PICS", "post-intensive care"],
        "Type 2 Diabetes": ["type.2.diabetes"],
        "Rheumatoid Arthritis": ["rheumatoid arthritis"],
        "Major Depressive Disorder": ["major depressive disorder"],
        "Alzheimer": ["alzheimer", "dementia"],
        "Multiple Sclerosis": ["multiple sclerosis"],
        "Asthma": ["asthma"],
        "COPD": ["copd", "chronic obstructive pulmonary"],
        "Chronic Kidney Disease": ["chronic kidney disease", "CKD"],
        "Epilepsy": ["epilepsy"],
    }
    for condition, terms in patterns.items():
        for term in terms:
            if has(markup, term):
                conditions.append({"@type": "MedicalCondition", "name": condition})
                break
    return conditions[:5]  # Google recommends ≤5 about nodes


def structured_data(page: Path, markup: str, title: str, description: str) -> str:
    """Generate rich JSON-LD for the page — medical where applicable."""
    canonical = url_for(page)
    breadcrumb = breadcrumb_items(page)
    # base WebSite + WebPage
    base = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "@id": ORIGIN + "/#website",
                "url": ORIGIN + "/",
                "name": SITE_NAME,
                "description": "Open-access research tracker for post-viral and chronic complex conditions — Long COVID, PACVS, ME/CFS, Lyme, Gulf War Illness, and more. Daily PubMed feeds, cohort database, biomarker atlases, and therapeutic-agent evidence synthesis.",
                "publisher": {"@id": "https://opensourcemed.info/#org"},
                "inLanguage": "en",
            },
            {
                "@type": "WebPage",
                "@id": canonical + "#webpage",
                "url": canonical,
                "name": title,
                "description": description,
                "inLanguage": "en",
                "isPartOf": {"@id": ORIGIN + "/#website"},
                "publisher": {"@id": "https://opensourcemed.info/#org"},
            },
            {"@type": "BreadcrumbList", "itemListElement": breadcrumb},
        ],
    }
    # medical enrichment
    conditions = detect_medical_conditions(markup)
    if conditions:
        wp = base["@graph"][1]  # WebPage node
        wp["about"] = conditions
        wp["@type"] = "MedicalWebPage"
    return '<script type="application/ld+json">' + json.dumps(base, ensure_ascii=False, separators=(",", ":")) + '</script>'


def og_image_path(page: Path) -> str:
    """Find the best OG image — prefer a local headshot/logo, fall back to favicon."""
    headshot = ROOT / "Halma_Headshot.png"
    if headshot.exists():
        return "https://opensourcemed.info/favicon.png"  # default — keep existing
    return "https://opensourcemed.info/favicon.png"


def add_to_head(markup: str, tags: list[str]) -> str:
    if not tags:
        return markup
    return re.sub(r"</head\s*>", "\n  " + "\n  ".join(tags) + "\n</head>", markup, count=1, flags=re.I)


def patch_page(page: Path, check: bool) -> tuple[bool, bool]:
    markup = page.read_text(encoding="utf-8")
    title = page_title(markup, page)
    description = page_description(markup, title)
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
        tags.append(f'<meta name="description" content="{html.escape(description, quote=True)}">')
    if not has(markup, r"<meta\b[^>]*\bname\s*=\s*['\"]?robots\b"):
        tags.append('<meta name="robots" content="noindex, follow"' if redirect else '<meta name="robots" content="index, follow, max-image-preview:large">')
    if not has(markup, r"<link\b[^>]*\brel\s*=\s*['\"]?canonical\b"):
        tags.append(f'<link rel="canonical" href="{canonical}">')

    # Open Graph
    if not has(markup, r"<meta\b[^>]*\bproperty\s*=\s*['\"]?og:title\b"):
        tags.extend([
            '<meta property="og:type" content="website">',
            '<meta property="og:site_name" content="Open Source Medicine Research">',
            f'<meta property="og:title" content="{html.escape(title, quote=True)}">',
            f'<meta property="og:description" content="{html.escape(description, quote=True)}">',
            f'<meta property="og:url" content="{canonical}">',
            f'<meta property="og:image" content="{og_image_path(page)}">',
            '<meta property="og:image:width" content="256">',
            '<meta property="og:image:height" content="256">',
        ])
    if not has(markup, r"<meta\b[^>]*\bname\s*=\s*['\"]?twitter:card\b"):
        tags.extend([
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{html.escape(title, quote=True)}">',
            f'<meta name="twitter:description" content="{html.escape(description, quote=True)}">',
            f'<meta name="twitter:image" content="{og_image_path(page)}">',
        ])

    # Structured data — always replace if missing or if it was a bare auto-generated WebPage
    if not has(markup, r"application/ld\+json") and not redirect:
        tags.append(structured_data(page, markup, title, description))

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

    def priority_for(page: Path) -> float:
        rel = page.relative_to(ROOT).as_posix()
        if rel == "index.html":
            return 1.0
        if rel.endswith("index.html"):
            return 0.9
        if not any(rel.startswith(d + "/") for d in PUBLIC_DIRS):
            return 0.8  # top-level condition pages
        return 0.6  # generated detail pages

    def changefreq_for(page: Path) -> str:
        rel = page.relative_to(ROOT).as_posix()
        if any(rel.endswith(x) for x in [".html", "index.html"]) and not any(
            rel.startswith(d + "/") for d in PUBLIC_DIRS
        ):
            return "daily"
        return "weekly"

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in urls:
        lines.extend([
            "  <url>",
            f"    <loc>{url_for(page)}</loc>",
            f"    <lastmod>{today}</lastmod>",
            f"    <changefreq>{changefreq_for(page)}</changefreq>",
            f"    <priority>{priority_for(page):.1f}</priority>",
            "  </url>",
        ])
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