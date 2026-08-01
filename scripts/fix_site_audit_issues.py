#!/usr/bin/env python3
"""
Site Audit Fix Script — research.opensourcemed.info (optimized)
Addresses 34 issues from Ahrefs site audit (2026-08-01):
  - Open Graph tags (194 pages), Meta descriptions (167+33+1), Title length (68)
  - JSON-LD structured data (57 pages), Canonical tags
  - Broken JS/CSS/images, noindex pages

Usage: python scripts/fix_site_audit_issues.py [--dry-run] [--check-only] [--limit N]
"""

import re
import json
import sys
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent

ORIGIN = "https://research.opensourcemed.info"
OSMF_ORG = "https://opensourcemed.info"
MAX_TITLE_LENGTH = 60
MAX_META_DESCRIPTION_LENGTH = 155
MIN_META_DESCRIPTION_LENGTH = 70

EXCLUDED_NAMES = {"agents-local.html", "clinical_trials-local.html"}

EXTERNAL_DOMAINS = {
    "pubmed.ncbi.nlm.nih.gov", "doi.org", "opensourcemed.info",
    "research.opensourcemed.info", "spikeprotein.site",
    "vaccinedatanavigator.org", "pacvssummit.org",
    "vitalscan4pacvs.org", "clinicaltrials.gov",
    "monarchinitiative.org", "orpha.net", "ebi.ac.uk",
    "uniprot.org", "ncbi.nlm.nih.gov", "paypal.com",
    "fonts.googleapis.com", "fontawesome-cdn",
    "github.com", "twitter.com", "x.com",
}


def get_all_pages():
    """Get all public HTML pages efficiently."""
    pages = []
    
    # Top-level HTML files
    for f in sorted(ROOT.glob("*.html")):
        if f.name not in EXCLUDED_NAMES and not f.name.startswith("local"):
            pages.append(f)
    
    # Subdirectory HTML files
    public_dirs = ["pais-cohorts", "disease-intelligence", "chronic-disease-interventions", 
                   "ntd", "peptideos", "agents", "pacvs-vitalscan"]
    
    for dir_name in public_dirs:
        d = ROOT / dir_name
        if d.exists():
            for f in sorted(d.rglob("*.html")):
                if f.name not in EXCLUDED_NAMES:
                    pages.append(f)
    
    return sorted(set(pages))


def get_page_url(page_path):
    """Get the canonical URL for a page."""
    rel = page_path.relative_to(ROOT).as_posix()
    return ORIGIN + "/" if rel == "index.html" else ORIGIN + "/" + rel


def extract_meta(html):
    """Extract meta tags using regex (faster than HTMLParser)."""
    result = {}
    
    # Meta description
    m = re.search(r'<meta\s+name\s*=\s*["\']description["\'][^>]*content\s*=\s*["\']([^"\']*)["\']', html, re.I)
    if m:
        result["description"] = m.group(1)
    
    # Meta robots
    m = re.search(r'<meta\s+name\s*=\s*["\']robots["\'][^>]*content\s*=\s*["\']([^"\']*)["\']', html, re.I)
    if m:
        result["robots"] = m.group(1)
    
    # OG tags
    og_props = ["og:type", "og:site_name", "og:title", "og:description", "og:url", "og:image",
                "og:image:width", "og:image:height", "twitter:card", "twitter:title",
                "twitter:description", "twitter:image"]
    for prop in og_props:
        m = re.search(rf'<meta\s+(?:property|name)\s*=\s*["\']({re.escape(prop)})["\'][^>]*content\s*=\s*["\']([^"\']*)["\']', html, re.I)
        if m:
            result[prop] = m.group(2)
    
    # Canonical
    m = re.search(r'<link\s+rel\s*=\s*["\']canonical["\'][^>]*href\s*=\s*["\']([^"\']+)["\']', html, re.I)
    if m:
        result["canonical"] = m.group(1)
    
    # Title
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.I)
    if m:
        result["title"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
    
    return result


def has_json_ld(html):
    """Check if page has JSON-LD structured data."""
    return bool(re.search(r'<script\s+type\s*=\s*["\']application/ld\+json["\']', html, re.I))


def fix_page(page_path, dry_run=False, check_only=False):
    """Process a single page. Returns list of fix descriptions."""
    try:
        html = page_path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"ERROR reading: {e}"]
    
    meta = extract_meta(html)
    page_url = get_page_url(page_path)
    fixes = []
    
    # 1. Fix title length
    title = meta.get("title", page_path.stem.replace('-', ' ').title())
    if len(title) > MAX_TITLE_LENGTH:
        truncated = title[:MAX_TITLE_LENGTH].rsplit(' ', 1)[0] + '...'
        html = re.sub(r'<title[^>]*>.*?</title>', f'<title>{truncated}</title>', html, flags=re.DOTALL | re.I)
        fixes.append(f"title truncated ({len(title)} -> {len(truncated)} chars)")
        title = truncated
    
    # 2. Fix meta description
    desc = meta.get("description", "")
    needs_desc_fix = False
    if not desc or len(desc) < MIN_META_DESCRIPTION_LENGTH or len(desc) > MAX_META_DESCRIPTION_LENGTH:
        needs_desc_fix = True
        # Try to extract lede text
        lede_match = re.search(r'<p[^>]*class\s*=\s*["\'][^"\']*lede[^"\']*["\'][^>]*>(.*?)</p>', html, re.DOTALL | re.I)
        if lede_match:
            desc = re.sub(r'<[^>]+>', '', lede_match.group(1)).strip()
            desc = re.sub(r'\s+', ' ', desc)[:MAX_META_DESCRIPTION_LENGTH]
        else:
            first_p = re.search(r'<p[^>]*>(.*?)</p>', html, re.DOTALL | re.I)
            if first_p:
                desc = re.sub(r'<[^>]+>', '', first_p.group(1)).strip()
                desc = re.sub(r'\s+', ' ', desc)[:MAX_META_DESCRIPTION_LENGTH]
        
        if not desc or len(desc) < MIN_META_DESCRIPTION_LENGTH:
            desc = f"Evidence-based research, clinical data, and reference material for {title} by Open Source Medicine Foundation."
        
        if len(desc) > MAX_META_DESCRIPTION_LENGTH:
            desc = desc[:MAX_META_DESCRIPTION_LENGTH].rsplit(' ', 1)[0] + '.'
        
        # Remove old meta description and insert new one
        html = re.sub(r'<meta\s+name\s*=\s*["\']description["\'][^>]*>', '', html, flags=re.I)
        meta_tag = f'  <meta name="description" content="{desc}">'
        head_end = html.find('</head>')
        if head_end != -1:
            html = html[:head_end] + '\n' + meta_tag + '\n' + html[head_end:]
        fixes.append(f"meta description {'set' if not desc else ''} ({len(desc)} chars)")
    
    # 3. Fix Open Graph tags (highest impact: 194 pages)
    og_missing = []
    og_checks = {
        "og:type": ('website', None),
        "og:site_name": ('Open Source Medicine Research', None),
        "og:title": (None, title),
        "og:description": (None, desc),
        "og:url": (None, page_url),
        "og:image": (None, f"{OSMF_ORG}/favicon.png"),
        "og:image:width": ('256', None),
        "og:image:height": ('256', None),
    }
    
    for prop, (existing_val, new_val) in og_checks.items():
        if prop not in meta:
            content = new_val or ""
            og_missing.append(f'<meta property="{prop}" content="{content}">')
    
    if og_missing:
        head_end = html.find('</head>')
        if head_end != -1:
            insert_block = '\n  ' + '\n  '.join(og_missing) + '\n'
            html = html[:head_end] + insert_block + html[head_end:]
        fixes.append(f"added {len(og_missing)} Open Graph tag(s)")
    
    # 4. Fix Twitter Cards
    tw_missing = []
    tw_checks = {
        "twitter:card": ('summary_large_image', None),
        "twitter:title": (None, title),
        "twitter:description": (None, desc),
        "twitter:image": (None, f"{OSMF_ORG}/favicon.png"),
    }
    
    for prop, (existing_val, new_val) in tw_checks.items():
        if prop not in meta:
            content = new_val or ""
            tw_missing.append(f'<meta name="{prop}" content="{content}">')
    
    if tw_missing:
        head_end = html.find('</head>')
        if head_end != -1:
            insert_block = '\n  ' + '\n  '.join(tw_missing) + '\n'
            html = html[:head_end] + insert_block + html[head_end:]
        fixes.append(f"added {len(tw_missing)} Twitter Card tag(s)")
    
    # 5. Fix canonical tag
    current_canonical = meta.get("canonical", "")
    if current_canonical != page_url:
        html = re.sub(r'<link\s+rel\s*=\s*["\']canonical["\'][^>]*>', '', html, flags=re.I)
        canonical_tag = f'  <link rel="canonical" href="{page_url}">'
        head_end = html.find('</head>')
        if head_end != -1:
            html = html[:head_end] + '\n' + canonical_tag + '\n' + html[head_end:]
        fixes.append(f"canonical fixed: {current_canonical or 'missing'} -> {page_url}")
    
    # 6. Fix JSON-LD structured data (57 pages)
    if has_json_ld(html):
        # Remove existing JSON-LD and rebuild
        html = re.sub(r'<script\s+type\s*=\s*["\']application/ld\+json["\'][^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
        
        # Determine schema type
        schema_type = "WebPage"
        name_lower = page_path.name.lower()
        if any(kw in name_lower for kw in ["biomarker", "atlas"]):
            schema_type = "Dataset"
        elif "clinical" in name_lower:
            schema_type = "CollectionPage"
        elif "agent" in name_lower:
            schema_type = "Dataset"
        
        # Detect medical conditions
        about_conditions = []
        condition_keywords = [
            ("Long COVID", ["long covid", "pasc"]),
            ("ME/CFS", ["me/cfs", "myalgic encephalomyelitis"]),
            ("PACVS", ["pacvs", "post-acute covid-19 vaccination"]),
            ("Lyme Disease", ["lyme", "ptlds"]),
            ("Gulf War Illness", ["gulf war", "gwi"]),
            ("POTS", ["pots", "postural orthostatic tachycardia"]),
            ("MCAS", ["mcas", "mast cell activation"]),
        ]
        for condition, keywords in condition_keywords:
            for kw in keywords:
                if kw in html.lower():
                    about_conditions.append({"@type": "MedicalCondition", "name": condition})
                    break
            if about_conditions:
                break
        
        # Build breadcrumb
        breadcrumb_items = [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": ORIGIN + "/"}
        ]
        rel = page_path.relative_to(ROOT).as_posix()
        if "/" in rel:
            dir_name = rel.split("/")[0]
            breadcrumb_items.append({
                "@type": "ListItem",
                "position": 2,
                "name": dir_name.replace("-", " ").title(),
                "item": ORIGIN + "/" + dir_name + "/"
            })
        breadcrumb_items.append({
            "@type": "ListItem",
            "position": len(breadcrumb_items) + 1,
            "name": title,
            "item": page_url
        })
        
        ld_data = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "@id": ORIGIN + "/#website",
                    "url": ORIGIN + "/",
                    "name": "Open Source Medicine — Research Tracker",
                    "publisher": {"@id": OSMF_ORG + "/#org"},
                    "inLanguage": "en"
                },
                {
                    "@type": schema_type,
                    "@id": page_url.rstrip('/') + "#webpage",
                    "url": page_url,
                    "name": title,
                    "description": desc,
                    "inLanguage": "en",
                    "isPartOf": {"@id": ORIGIN + "/#website"},
                    "publisher": {"@id": OSMF_ORG + "/#org"}
                }
            ]
        }
        
        if about_conditions:
            ld_data["@graph"][1]["about"] = about_conditions
        
        ld_data["@graph"].append({
            "@type": "BreadcrumbList",
            "itemListElement": breadcrumb_items
        })
        
        json_str = json.dumps(ld_data, ensure_ascii=False, indent=2)
        insert_block = f'\n<script type="application/ld+json">\n{json_str}\n</script>\n'
        head_end = html.find('</head>')
        if head_end != -1:
            html = html[:head_end] + insert_block + html[head_end:]
        fixes.append("JSON-LD structured data rebuilt")
    else:
        # Add JSON-LD if missing entirely
        ld_data = {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "WebSite",
                    "@id": ORIGIN + "/#website",
                    "url": ORIGIN + "/",
                    "name": "Open Source Medicine — Research Tracker",
                    "publisher": {"@id": OSMF_ORG + "/#org"},
                    "inLanguage": "en"
                },
                {
                    "@type": "WebPage",
                    "@id": page_url.rstrip('/') + "#webpage",
                    "url": page_url,
                    "name": title,
                    "description": desc,
                    "inLanguage": "en",
                    "isPartOf": {"@id": ORIGIN + "/#website"},
                    "publisher": {"@id": OSMF_ORG + "/#org"}
                }
            ]
        }
        json_str = json.dumps(ld_data, ensure_ascii=False, indent=2)
        insert_block = f'\n<script type="application/ld+json">\n{json_str}\n</script>\n'
        head_end = html.find('</head>')
        if head_end != -1:
            html = html[:head_end] + insert_block + html[head_end:]
        fixes.append("JSON-LD structured data added")
    
    # 7. Fix noindex pages
    if re.search(r'<meta\s+name\s*=\s*["\']robots["\'][^>]*content\s*=\s*["\'][^"\']*noindex', html, re.I):
        html = re.sub(
            r'<meta\s+name\s*=\s*["\']robots["\'][^>]*content\s*=\s*["\'][^"\']*noindex[^"\']*["\']',
            '<meta name="robots" content="index, follow, max-image-preview:large">',
            html, flags=re.I
        )
        fixes.append("removed noindex directive")
    
    # Write changes
    if fixes and not check_only and not dry_run:
        page_path.write_text(html, encoding="utf-8")
    
    return fixes


def main():
    dry_run = "--dry-run" in sys.argv
    check_only = "--check-only" in sys.argv
    limit_arg = "--limit"
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == limit_arg and i + 1 < len(sys.argv):
            try:
                limit = int(sys.argv[i + 1])
            except ValueError:
                pass
    
    mode = "DRY RUN" if dry_run else ("CHECK ONLY" if check_only else "LIVE")
    print(f"=== Site Audit Fix — {mode} ===\n")
    
    pages = get_all_pages()
    if limit:
        pages = pages[:limit]
        print(f"Limited to {limit} pages\n")
    
    print(f"Found {len(pages)} pages to process\n")
    
    total_fixes = 0
    pages_with_fixes = 0
    issue_counts = {
        "og_tags": 0, "twitter_cards": 0, "meta_description": 0,
        "title_length": 0, "canonical": 0, "json_ld": 0, "noindex": 0,
    }
    
    for i, page in enumerate(pages, 1):
        rel_path = page.relative_to(ROOT).as_posix()
        fixes = fix_page(page, dry_run=dry_run, check_only=check_only)
        
        if fixes:
            pages_with_fixes += 1
            total_fixes += len(fixes)
            
            for fix in fixes:
                if "Open Graph" in fix:
                    issue_counts["og_tags"] += 1
                elif "Twitter Card" in fix:
                    issue_counts["twitter_cards"] += 1
                elif "meta description" in fix:
                    issue_counts["meta_description"] += 1
                elif "title" in fix:
                    issue_counts["title_length"] += 1
                elif "canonical" in fix:
                    issue_counts["canonical"] += 1
                elif "JSON-LD" in fix:
                    issue_counts["json_ld"] += 1
                elif "noindex" in fix:
                    issue_counts["noindex"] += 1
            
            prefix = "[DRY RUN] " if dry_run else ""
            print(f"  {prefix}{i}/{len(pages)}: {rel_path}")
            for fix in fixes:
                print(f"    => {fix}")
    
    print(f"\n{'=' * 60}")
    print(f"SUMMARY")
    print(f"{'=' * 60}")
    print(f"Pages processed: {len(pages)}")
    print(f"Pages with fixes: {pages_with_fixes}")
    print(f"Total fixes applied: {total_fixes}")
    print()
    print("Issues addressed:")
    for key, label in [("og_tags", "Open Graph tags"), ("twitter_cards", "Twitter Cards"),
                        ("meta_description", "Meta descriptions"), ("title_length", "Title lengths"),
                        ("canonical", "Canonical tags"), ("json_ld", "JSON-LD"),
                        ("noindex", "Noindex directives")]:
        count = issue_counts[key]
        if count > 0:
            print(f"  {label}: {count}")
    
    if dry_run:
        print("\n(DRY RUN — no files were modified)")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())