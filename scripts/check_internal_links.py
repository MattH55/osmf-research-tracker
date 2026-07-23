#!/usr/bin/env python3
"""
Ticket 7 — Internal-link CI check.

Crawls generated output directories, builds a link graph from <a href> tags,
and validates that every indexable page (not noindex-flagged) has:
  - >= 3 inbound links from other pages in the graph
  - >= 3 outbound internal links

Usage: python scripts/check_internal_links.py [--quiet]
  Non-zero exit on orphan pages among indexable pages.
  Prints list of orphan pages and summary.
"""

import os, sys, re, json
from pathlib import Path
from collections import defaultdict
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent

# Directories to crawl (relative to ROOT)
CRAWL_DIRS = [
    "pais-cohorts",
    "disease-intelligence",
    "agents",
    "chronic-disease-interventions",
    "ntd",
]

# Top-level files that are also index pages
TOP_LEVEL_PAGES = [
    "index.html",
    "pais-cohorts.html",
    "pais-susceptibility.html",
    "agents.html",
    "candidate-therapeutics.html",
    "therapeutics-atlas.html",
    "biomarker-atlas.html",
    "clinical_trials.html",
]

MIN_INBOUND = 3
MIN_OUTBOUND = 3

EXTERNAL_DOMAINS = {
    "pubmed.ncbi.nlm.nih.gov",
    "doi.org",
    "opensourcemed.info",
    "research.opensourcemed.info",
    "spikeprotein.site",
    "vaccinedatanavigator.org",
    "pacvssummit.org",
    "clinicaltrials.gov",
    "monarchinitiative.org",
    "orpha.net",
    "ebi.ac.uk",
    "uniprot.org",
    "ncbi.nlm.nih.gov",
}


def extract_links(html_path: Path) -> list[str]:
    """Extract all href values from <a> tags in an HTML file."""
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    # Find all <a href="..."> tags
    hrefs = re.findall(r'<a\s[^>]*href\s*=\s*["\']([^"\']+)["\']', text, re.IGNORECASE)
    return hrefs


def is_noindex(html_path: Path) -> bool:
    """Check if the page has <meta name='robots' content='noindex...'>."""
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    return bool(re.search(r'<meta\s+name\s*=\s*["\']robots["\'].*?content\s*=\s*["\']noindex', text, re.IGNORECASE))


def normalize_href(href: str, page_path: str) -> str:
    """Normalize an href to a canonical key that matches a crawled page path."""
    href = href.strip()
    # Remove fragment
    if "#" in href:
        href = href.split("#")[0]
    # Remove query string
    if "?" in href:
        href = href.split("?")[0]

    # Absolute URLs
    if href.startswith("http://") or href.startswith("https://"):
        parsed = urlparse(href)
        domain = parsed.netloc.lower()
        # Only count as internal if domain is research.opensourcemed.info
        if "research.opensourcemed.info" not in domain and "localhost" not in domain:
            return ""  # external
        href = parsed.path

    # Resolve relative paths
    page_dir = os.path.dirname(page_path)
    if href.startswith("/"):
        resolved = href.lstrip("/")
    else:
        resolved = os.path.normpath(os.path.join(page_dir, href)).replace("\\", "/")

    # Strip trailing index.html
    if resolved.endswith("/index.html"):
        resolved = resolved[:-10]
    if resolved.endswith("/"):
        resolved += "index.html"

    return resolved.lstrip("/")


def crawl_and_build_graph() -> tuple[dict[str, set[str]], dict[str, bool], set[str]]:
    """Crawl all pages and build: outlinks, is_indexable, all_pages."""
    outlinks: dict[str, set[str]] = {}  # page_key -> set of target page keys
    all_pages: set[str] = set()
    noindex_pages: dict[str, bool] = {}

    for dir_name in CRAWL_DIRS:
        d = ROOT / dir_name
        if not d.exists():
            continue
        for fp in sorted(d.rglob("*.html")):
            page_key = str(fp.relative_to(ROOT)).replace("\\", "/")
            all_pages.add(page_key)
            noindex_pages[page_key] = is_noindex(fp)
            links = extract_links(fp)
            normalized = set()
            for href in links:
                target = normalize_href(href, page_key)
                if target:
                    normalized.add(target)
            outlinks[page_key] = normalized

    # Add top-level pages
    for page_name in TOP_LEVEL_PAGES:
        fp = ROOT / page_name
        if fp.exists():
            page_key = page_name
            all_pages.add(page_key)
            noindex_pages[page_key] = is_noindex(fp)
            links = extract_links(fp)
            normalized = set()
            for href in links:
                target = normalize_href(href, page_key)
                if target:
                    normalized.add(target)
            outlinks[page_key] = normalized

    return outlinks, noindex_pages, all_pages


def check_link_graph(outlinks: dict, noindex_pages: dict, all_pages: set) -> tuple[list, list]:
    """Check inbound and outbound link requirements. Returns (orphan_pages, low_outbound_pages)."""
    # Build inbound index
    inbound: dict[str, set[str]] = defaultdict(set)
    for source, targets in outlinks.items():
        for target in targets:
            inbound[target].add(source)

    indexable_pages = {p for p in all_pages if not noindex_pages.get(p, False)}

    orphan_pages = []
    low_outbound_pages = []

    for page in sorted(indexable_pages):
        # Inbound check
        in_count = len(inbound.get(page, set()))
        if in_count < MIN_INBOUND:
            orphan_pages.append((page, in_count))

        # Outbound check (only count links to known internal pages)
        out = outlinks.get(page, set())
        out_internal = out & all_pages
        out_count = len(out_internal)
        if out_count < MIN_OUTBOUND:
            low_outbound_pages.append((page, out_count))

    return orphan_pages, low_outbound_pages


def main():
    quiet = "--quiet" in sys.argv

    outlinks, noindex_pages, all_pages = crawl_and_build_graph()
    indexable_pages = {p for p in all_pages if not noindex_pages.get(p, False)}
    noindex_count = len(all_pages) - len(indexable_pages)

    if not quiet:
        print(f"Crawled {len(all_pages)} pages ({len(indexable_pages)} indexable, {noindex_count} noindex)")
        print()

    orphan_pages, low_outbound_pages = check_link_graph(outlinks, noindex_pages, all_pages)

    exit_code = 0

    if orphan_pages:
        print(f"ORPHAN pages (< {MIN_INBOUND} inbound links among indexable pages):")
        for page, count in orphan_pages:
            print(f"  [{count} inbound] {page}")
        print()
        exit_code = 1

    if low_outbound_pages:
        print(f"LOW OUTBOUND pages (< {MIN_OUTBOUND} internal outbound links):")
        for page, count in low_outbound_pages:
            print(f"  [{count} outbound internal] {page}")
        print()
        exit_code = 1

    if not orphan_pages and not low_outbound_pages:
        print("All indexable pages have sufficient internal links.")
    else:
        print(f"Summary: {len(orphan_pages)} orphan pages, {len(low_outbound_pages)} low-outbound pages")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()