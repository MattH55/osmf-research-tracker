#!/usr/bin/env python3
"""
OSMF Research Tracker - SEO Retrofit Script
Retrofits research.opensourcemed.info for:
  - Canonical OSMF Organization reference (no local duplications)
  - Shared Website entity
  - Appropriate schema types (Dataset, CollectionPage, MedicalWebPage, etc.)
  - Entity hierarchy: pages -> Website -> OSMF Organization
  - BreadcrumbList schema
  - Shared OSMF network component
  - Shared OSMF footer
  - Standardized metadata template
  - Updated sitemap index
  - Updated robots.txt

Usage: python scripts/retrofit_seo.py [--dry-run]
"""

import os
import re
import json
import sys
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Canonical OSMF Organization reference ──
OSMF_ORG_REF = '{"@id":"https://opensourcemed.info/#org"}'

# ── Shared Website entity JSON ──
WEBSITE_JSONLD = '''{
      "@type":"WebSite",
      "@id":"https://research.opensourcemed.info/#website",
      "url":"https://research.opensourcemed.info/",
      "name":"Open Source Medicine Research",
      "publisher":{"@id":"https://opensourcemed.info/#org"}
    }'''

# ── Shared OSMF Network Component HTML ──
OSMF_NETWORK_HTML = '''<!-- OSMF Network Component -->
<section class="osmf-network-banner">
  <div class="osmf-network-inner">
    <h2 class="osmf-network-title">Part of the Open Source Medicine Foundation Network</h2>
    <div class="osmf-network-sites">
      <div class="osmf-network-site">
        <a href="https://opensourcemed.info" target="_blank" rel="noopener"><strong>Open Source Medicine Foundation</strong></a>
        <span>The OSMF hub — advancing open-source biomedical research infrastructure, tools, and evidence synthesis.</span>
      </div>
      <div class="osmf-network-site">
        <a href="https://spikeprotein.site" target="_blank" rel="noopener"><strong>SpikeProtein.site</strong></a>
        <span>Database and research resource on SARS-CoV-2 spike protein biology, persistence, and clinical implications.</span>
      </div>
      <div class="osmf-network-site">
        <a href="https://vaccinedatanavigator.org" target="_blank" rel="noopener"><strong>Vaccine Data Navigator</strong></a>
        <span>Open-access navigation tool for vaccine adverse event reporting and surveillance data.</span>
      </div>
      <div class="osmf-network-site">
        <a href="https://vitalscan4pacvs.org" target="_blank" rel="noopener"><strong>VitalScan4PACVS</strong></a>
        <span>Remote physiological monitoring study for post-acute COVID-19 vaccination syndrome.</span>
      </div>
      <div class="osmf-network-site">
        <a href="https://pacvssummit.org" target="_blank" rel="noopener"><strong>PACVS Research Summit</strong></a>
        <span>Annual summit convening researchers, clinicians, and patients on PACVS science.</span>
      </div>
    </div>
  </div>
</section>'''

# ── Shared Footer HTML ──
SHARED_FOOTER_HTML = '''<footer class="osmf-network-footer">
  <div class="osmf-network-inner">
    <div class="footer-brand">Open Source Medicine Foundation</div>
    <div class="footer-links">
      <a href="https://opensourcemed.info">Open Source Medicine Foundation</a>
      <a href="https://research.opensourcemed.info/">Research Platform</a>
      <a href="https://spikeprotein.site">SpikeProtein.site</a>
      <a href="https://vaccinedatanavigator.org">Vaccine Data Navigator</a>
      <a href="https://vitalscan4pacvs.org">VitalScan4PACVS</a>
      <a href="https://pacvssummit.org">PACVS Research Summit</a>
      <a href="https://opensourcemed.substack.com">Substack</a>
      <a href="https://opensourcemed.info/#contact">Contact</a>
    </div>
    <div class="footer-note">Automated daily via GitHub Actions + pymed. Data from PubMed (NLM). Not medical advice.</div>
  </div>
</footer>'''


def find_footer_tag_end(html):
    """Find the </footer> closing tag, returning the position after it."""
    idx = html.rfind('</footer>')
    if idx == -1:
        return html.rfind('</body>')
    return idx + len('</footer>')


def replace_footer_section(html):
    """Replace old footer + any content after it until </body> with OSMF network + shared footer."""
    # Find the last <footer in the document
    pos = html.rfind('<footer')
    if pos == -1:
        # No footer, insert before </body>
        body_end = html.rfind('</body>')
        if body_end == -1:
            return html
        before = html[:body_end]
        after = html[body_end:]
        return before + '\n' + OSMF_NETWORK_HTML + '\n' + SHARED_FOOTER_HTML + '\n' + after

    # Find the matching </footer>
    footer_end = html.find('</footer>', pos)
    if footer_end == -1:
        return html

    # Replace from <footer to </footer> with network + new footer
    before = html[:pos]
    # Also strip any existing network banner section
    # Remove old banner if present
    banner_start = before.rfind('<!-- OSMF Network Component -->')
    if banner_start != -1:
        banner_end = before.find('</section>', banner_start)
        if banner_end != -1:
            before = before[:banner_start] + before[banner_end + len('</section>'):]

    after = html[footer_end + len('</footer>'):]
    return before + '\n' + OSMF_NETWORK_HTML + '\n' + SHARED_FOOTER_HTML + '\n' + after


def fix_organization_in_jsonld(jsonld_str):
    """Replace any local Organization definitions with @id reference."""
    # Pattern: "publisher":{"@type":"Organization","name":"Open Source Medicine Foundation","url":"https://opensourcemed.info"}
    # Replace with: "publisher":{"@id":"https://opensourcemed.info/#org"}

    # Match publisher with local Organization definition (with or without trailing /)
    pattern = r'"publisher"\s*:\s*\{\s*"@type"\s*:\s*"Organization"\s*,\s*"name"\s*:\s*"Open Source Medicine Foundation"\s*,\s*"url"\s*:\s*"https://opensourcemed\.info/?\"?\s*\}'
    replacement = '"publisher":{"@id":"https://opensourcemed.info/#org"}'
    jsonld_str = re.sub(pattern, replacement, jsonld_str)
    return jsonld_str


def update_page_jsonld(html, page_url, page_name, page_desc, schema_type="MedicalWebPage",
                       about_conditions=None, breadcrumb_items=None, is_homepage=False,
                       extra_properties=None):
    """
    Update or add JSON-LD structured data to a page.
    Strips ALL existing ld+json blocks and inserts a single canonical @graph block.
    """
    # Remove ALL existing JSON-LD script blocks
    jsonld_pattern = r'<script\s+type="application/ld\+json">.*?</script>'
    html = re.sub(jsonld_pattern, '', html, flags=re.DOTALL)

    # Build the canonical @graph structure
    page_item = {
        "@type": schema_type,
        "@id": page_url.rstrip('/') + "#webpage",
        "url": page_url,
        "name": page_name,
        "description": page_desc,
        "inLanguage": "en",
        "isPartOf": {"@id": "https://research.opensourcemed.info/#website"},
        "publisher": {"@id": "https://opensourcemed.info/#org"}
    }

    if about_conditions:
        page_item["about"] = about_conditions

    if extra_properties:
        page_item.update(extra_properties)

    graph_items = [
        json.dumps(json.loads(WEBSITE_JSONLD.strip())),
        json.dumps(page_item)
    ]

    if breadcrumb_items:
        graph_items.append(json.dumps(breadcrumb_items))

    new_jsonld = '{\n"@context":"https://schema.org",\n"@graph":[\n' + ',\n'.join(graph_items) + '\n]\n}'

    # Insert before </head>
    head_end = html.find('</head>')
    if head_end != -1:
        html = html[:head_end] + '\n<script type="application/ld+json">\n' + new_jsonld + '\n</script>\n' + html[head_end:]

    return html


def add_favicon_metadata(html, page_path):
    """Ensure favicon and theme-color are present."""
    if '<link rel="icon"' not in html:
        depth = page_path.count(os.sep) if os.sep in page_path else 0
        favicon_href = '../favicon.png' if depth > 0 else 'favicon.png'
        head_end = html.find('</head>')
        if head_end != -1:
            html = html[:head_end] + f'\n  <link rel="icon" href="{favicon_href}" type="image/png">\n  <meta name="theme-color" content="#0e1444">\n' + html[head_end:]
    if '<meta name="theme-color"' not in html:
        head_end = html.find('</head>')
        if head_end != -1:
            html = html[:head_end] + '\n  <meta name="theme-color" content="#0e1444">\n' + html[head_end:]
    return html


def update_disease_tracker_page(filepath, page_name, condition_name, page_slug):
    """Update a disease research tracker page (MedicalWebPage)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    page_url = f"https://research.opensourcemed.info/{page_slug}.html"

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://research.opensourcemed.info/"},
            {"@type": "ListItem", "position": 2, "name": page_name, "item": page_url}
        ]
    }

    about = {"@type": "MedicalCondition", "name": condition_name}

    html = update_page_jsonld(html, page_url, f"{page_name} Research Tracker",
                              f"Automated daily feed of peer-reviewed PubMed research on {condition_name}.",
                              "MedicalWebPage", [about], breadcrumb)

    html = replace_footer_section(html)
    html = add_favicon_metadata(html, filepath)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ Updated disease tracker: {filepath}")


def update_biomarker_atlas_hub(filepath):
    """Update the biomarker atlas hub page (CollectionPage)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    page_url = "https://research.opensourcemed.info/biomarker-atlas.html"

    # Find the BIOMARKER_HUB_JSONLD markers
    start_marker = "<!-- BIOMARKER_HUB_JSONLD_START -->"
    end_marker = "<!-- BIOMARKER_HUB_JSONLD_END -->"
    start = html.find(start_marker)
    end = html.find(end_marker)

    if start != -1 and end != -1:
        # Replace the JSON-LD block
        breadcrumb = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://research.opensourcemed.info/"},
                {"@type": "ListItem", "position": 2, "name": "Biomarker Atlases", "item": page_url}
            ]
        }

        new_jsonld = '''{
      "@context":"https://schema.org",
      "@graph":[
        ''' + WEBSITE_JSONLD + ''',
        {
          "@type":"CollectionPage",
          "@id":"https://research.opensourcemed.info/biomarker-atlas.html#webpage",
          "url":"https://research.opensourcemed.info/biomarker-atlas.html",
          "name":"Biomarker Atlas Hub",
          "description":"Searchable peer-reviewed biomarker databases with DOI citations and LOINC codes — curated literature syntheses by condition.",
          "dateModified":"''' + datetime.utcnow().strftime('%Y-%m-%d') + '''",
          "inLanguage":"en",
          "isPartOf":{"@id":"https://research.opensourcemed.info/#website"},
          "publisher":{"@id":"https://opensourcemed.info/#org"},
          "keywords":["biomarker atlas","biomarker database","peer-reviewed biomarkers","chronic illness biomarkers","blood test alterations","searchable biomarker reference"],
          "hasPart":[
            {"@type":"MedicalWebPage","name":"Long COVID Biomarker Atlas","url":"https://research.opensourcemed.info/long-covid-biomarkers.html"},
            {"@type":"MedicalWebPage","name":"PACVS Biomarker Atlas","url":"https://research.opensourcemed.info/pacvs-biomarkers.html"},
            {"@type":"MedicalWebPage","name":"ME/CFS Biomarker Atlas","url":"https://research.opensourcemed.info/me-cfs-biomarkers.html"},
            {"@type":"MedicalWebPage","name":"Lyme Disease Biomarker Atlas","url":"https://research.opensourcemed.info/lyme-biomarkers.html"},
            {"@type":"MedicalWebPage","name":"Gulf War Illness Biomarker Atlas","url":"https://research.opensourcemed.info/gulf-war-illness-biomarkers.html"}
          ]
        },
        ''' + json.dumps(breadcrumb) + '''
      ]
    }'''

        html = html[:start + len(start_marker)] + '\n    <script type="application/ld+json">\n' + new_jsonld + '\n    </script>\n    ' + html[end:]

    html = replace_footer_section(html)
    html = add_favicon_metadata(html, filepath)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ Updated biomarker hub: {filepath}")


def update_biomarker_page(filepath, page_name, condition_name, page_slug):
    """Update an individual biomarker atlas page (Dataset)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    page_url = f"https://research.opensourcemed.info/{page_slug}-biomarkers.html"

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://research.opensourcemed.info/"},
            {"@type": "ListItem", "position": 2, "name": "Biomarker Atlases", "item": "https://research.opensourcemed.info/biomarker-atlas.html"},
            {"@type": "ListItem", "position": 3, "name": f"{page_name} Biomarkers", "item": page_url}
        ]
    }

    extra = {
        "dateModified": datetime.utcnow().strftime('%Y-%m-%d'),
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "keywords": [f"{condition_name.lower()} biomarkers", "blood tests", "laboratory markers", "diagnostic markers"],
        "creator": {"@id": "https://opensourcemed.info/#org"}
    }

    html = update_page_jsonld(html, page_url, f"{page_name} Biomarker Atlas",
                              f"Peer-reviewed biomarker database for {condition_name} — literature-synthesized blood test, cytokine, and metabolite alterations with DOI citations and LOINC codes.",
                              "Dataset", None, breadcrumb, extra_properties=extra)

    html = replace_footer_section(html)
    html = add_favicon_metadata(html, filepath)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ Updated biomarker page: {filepath}")


def update_clinical_trials_page(filepath):
    """Update the clinical trials tracker page (CollectionPage)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    page_url = "https://research.opensourcemed.info/clinical_trials.html"

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://research.opensourcemed.info/"},
            {"@type": "ListItem", "position": 2, "name": "Clinical Trials", "item": page_url}
        ]
    }

    about = [
        {"@type": "MedicalCondition", "name": "Long COVID"},
        {"@type": "MedicalCondition", "name": "Post-Acute COVID-19 Vaccination Syndrome", "alternateName": "PACVS"},
        {"@type": "MedicalCondition", "name": "Myalgic Encephalomyelitis", "alternateName": "ME/CFS"}
    ]

    html = update_page_jsonld(html, page_url, "Post-Viral Clinical Trials Tracker",
                              "Tracker of interventional clinical trials for PACVS, Long COVID, ME/CFS, Chronic Lyme, Gulf War Illness, and related post-viral conditions. Data sourced from ClinicalTrials.gov.",
                              "CollectionPage", about, breadcrumb)

    html = replace_footer_section(html)
    html = add_favicon_metadata(html, filepath)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ Updated clinical trials: {filepath}")


def update_agents_page(filepath):
    """Update the therapeutic agents page (CollectionPage)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    page_url = "https://research.opensourcemed.info/agents.html"

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://research.opensourcemed.info/"},
            {"@type": "ListItem", "position": 2, "name": "Therapeutic Agents", "item": page_url}
        ]
    }

    html = update_page_jsonld(html, page_url, "Therapeutic Agents Tracker",
                              "Cross-condition synthesis of therapeutic agents being studied for post-viral and chronic conditions, with evidence levels and linked trial data.",
                              "CollectionPage", None, breadcrumb)

    html = replace_footer_section(html)
    html = add_favicon_metadata(html, filepath)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ Updated agents page: {filepath}")


def update_biomarker_index_page(filepath):
    """Update the biomarker index page (CollectionPage)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    page_url = "https://research.opensourcemed.info/biomarker-index.html"

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://research.opensourcemed.info/"},
            {"@type": "ListItem", "position": 2, "name": "Biomarker Index", "item": page_url}
        ]
    }

    html = update_page_jsonld(html, page_url, "Biomarker Index",
                              "Cross-condition searchable index of every curated biomarker across all Open Source Medicine Foundation condition atlases.",
                              "CollectionPage", None, breadcrumb)

    html = replace_footer_section(html)
    html = add_favicon_metadata(html, filepath)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ Updated biomarker index: {filepath}")


def update_simple_page(filepath, page_name, page_slug, schema_type="MedicalWebPage",
                       about_conditions=None, depth=0):
    """Update a simple page with standardized JSON-LD and footer."""
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    page_url = f"https://research.opensourcemed.info/{page_slug}.html"

    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://research.opensourcemed.info/"},
            {"@type": "ListItem", "position": 2, "name": page_name, "item": page_url}
        ]
    }

    extra = {}
    if schema_type == "Dataset":
        extra["dateModified"] = datetime.utcnow().strftime('%Y-%m-%d')
        extra["license"] = "https://creativecommons.org/licenses/by/4.0/"

    html = update_page_jsonld(html, page_url, page_name,
                              f"Research data for {page_name} on the Open Source Medicine Research platform.",
                              schema_type, about_conditions, breadcrumb, extra_properties=extra if extra else None)

    html = replace_footer_section(html)
    html = add_favicon_metadata(html, filepath)

    # Fix CSS paths for pages in subdirectories
    if depth > 0:
        prefix = '../' * depth
        html = html.replace('href="tracker.css"', f'href="{prefix}tracker.css"')
        html = html.replace('href="css/', f'href="{prefix}css/')
        html = html.replace('src="js/', f'src="{prefix}js/')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"  ✓ Updated: {filepath}")


def generate_sitemap_index():
    """Generate a new sitemap index with separate category sitemaps."""
    today = datetime.utcnow().strftime('%Y-%m-%d')

    # Collect pages
    root_files = {f for f in os.listdir(ROOT) if f.endswith('.html') and os.path.isfile(ROOT / f)}

    # Category classification
    pages = []
    diseases = []
    clinical_trials = []
    biomarkers_list = []
    datasets = []

    for f in sorted(root_files):
        url = f"https://research.opensourcemed.info/{f}"
        if f == 'index.html':
            pages.append((url, 'daily', '1.0'))
        elif '-biomarkers.html' in f:
            biomarkers_list.append((url, 'weekly', '0.9'))
        elif f in ('pacvs.html', 'long-covid.html', 'me-cfs.html', 'lyme.html', 'gulf-war-illness.html', 'other-post-viral.html'):
            diseases.append((url, 'daily', '0.9'))
        elif f == 'clinical_trials.html':
            clinical_trials.append((url, 'weekly', '0.8'))
        elif f == 'biomarker-atlas.html':
            pages.append((url, 'weekly', '0.95'))
        elif f == 'biomarker-index.html':
            pages.append((url, 'weekly', '0.85'))
        else:
            pages.append((url, 'weekly', '0.7'))

    # Generate sitemap index XML
    sitemap_index = '''<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://research.opensourcemed.info/pages.xml</loc>
    <lastmod>''' + today + '''</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://research.opensourcemed.info/diseases.xml</loc>
    <lastmod>''' + today + '''</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://research.opensourcemed.info/biomarkers.xml</loc>
    <lastmod>''' + today + '''</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://research.opensourcemed.info/clinical-trials.xml</loc>
    <lastmod>''' + today + '''</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://research.opensourcemed.info/datasets.xml</loc>
    <lastmod>''' + today + '''</lastmod>
  </sitemap>
</sitemapindex>'''

    def generate_sitemap(name, entries):
        xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for url, changefreq, priority in entries:
            xml += f'  <url>\n    <loc>{url}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>{changefreq}</changefreq>\n    <priority>{priority}</priority>\n  </url>\n'
        xml += '</urlset>'
        return xml

    # Write files
    with open(ROOT / 'sitemap.xml', 'w', encoding='utf-8') as f:
        f.write(sitemap_index)
    with open(ROOT / 'pages.xml', 'w', encoding='utf-8') as f:
        f.write(generate_sitemap('pages', pages))
    with open(ROOT / 'diseases.xml', 'w', encoding='utf-8') as f:
        f.write(generate_sitemap('diseases', diseases))
    with open(ROOT / 'biomarkers.xml', 'w', encoding='utf-8') as f:
        f.write(generate_sitemap('biomarkers', biomarkers_list))
    with open(ROOT / 'clinical-trials.xml', 'w', encoding='utf-8') as f:
        f.write(generate_sitemap('clinical-trials', clinical_trials))
    with open(ROOT / 'datasets.xml', 'w', encoding='utf-8') as f:
        f.write(generate_sitemap('datasets', datasets))

    print("\n✓ Sitemap index generated: sitemap.xml")
    print("  - pages.xml")
    print("  - diseases.xml")
    print("  - biomarkers.xml")
    print("  - clinical-trials.xml")
    print("  - datasets.xml")


def update_robots_txt():
    """Update robots.txt with sitemap index reference and crawl directives."""
    robots_content = '''User-agent: *
Allow: /
Disallow: /*?*

Sitemap: https://research.opensourcemed.info/sitemap.xml

# Crawl-delay for polite crawling
Crawl-delay: 10
'''
    with open(ROOT / 'robots.txt', 'w', encoding='utf-8') as f:
        f.write(robots_content)
    print("\n✓ robots.txt updated")


def main():
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print("=== DRY RUN - No files will be modified ===\n")

    print("OSMF Research Tracker - SEO Retrofit")
    print("=" * 60)

    # ── 1. Core manually-edited pages ──
    print("\n📄 Updating core pages...")

    # Disease tracker pages (MedicalWebPage)
    disease_pages = [
        ('pacvs.html', 'PACVS', 'Post-Acute COVID-19 Vaccination Syndrome'),
        ('long-covid.html', 'Long COVID', 'Long COVID (PASC)'),
        ('me-cfs.html', 'ME/CFS', 'Myalgic Encephalomyelitis / Chronic Fatigue Syndrome'),
        ('lyme.html', 'Lyme / PTLDS', 'Lyme Disease / Post-Treatment Lyme Disease Syndrome'),
        ('gulf-war-illness.html', 'Gulf War Illness', 'Gulf War Illness'),
        ('other-post-viral.html', 'Other Post-Viral', 'Other Post-Viral Syndromes'),
    ]

    for filename, page_name, condition_name in disease_pages:
        filepath = ROOT / filename
        if filepath.exists():
            page_slug = filename.replace('.html', '')
            if not dry_run:
                update_disease_tracker_page(str(filepath), page_name, condition_name, page_slug)
            else:
                print(f"  [DRY RUN] Would update: {filename}")

    # Biomarker atlas hub (CollectionPage)
    hub_path = ROOT / 'biomarker-atlas.html'
    if hub_path.exists():
        if not dry_run:
            update_biomarker_atlas_hub(str(hub_path))
        else:
            print("  [DRY RUN] Would update: biomarker-atlas.html")

    # Individual biomarker atlas pages (Dataset)
    biomarker_conditions = [
        ('long-covid', 'Long COVID', 'Long COVID (PASC)'),
        ('pacvs', 'PACVS', 'Post-Acute COVID-19 Vaccination Syndrome'),
        ('me-cfs', 'ME/CFS', 'Myalgic Encephalomyelitis / Chronic Fatigue Syndrome'),
        ('lyme', 'Lyme / PTLDS', 'Lyme Disease'),
        ('gulf-war-illness', 'Gulf War Illness', 'Gulf War Illness'),
        ('asthma', 'Asthma', 'Asthma'),
        ('type-2-diabetes', 'Type 2 Diabetes', 'Type 2 Diabetes'),
        ('type-1-diabetes', 'Type 1 Diabetes', 'Type 1 Diabetes'),
        ('hypertension', 'Hypertension', 'Hypertension'),
        ('chronic-kidney-disease', 'Chronic Kidney Disease', 'Chronic Kidney Disease'),
        ('nafld-mash-metabolic-associated-steatohepatitis', 'NAFLD/MASH', 'NAFLD / MASH (Metabolic-Associated Steatohepatitis)'),
        ('atrial-fibrillation', 'Atrial Fibrillation', 'Atrial Fibrillation'),
        ('copd', 'COPD', 'Chronic Obstructive Pulmonary Disease'),
        ('osteoarthritis', 'Osteoarthritis', 'Osteoarthritis'),
        ('low-back-pain', 'Low Back Pain', 'Low Back Pain'),
        ('rheumatoid-arthritis', 'Rheumatoid Arthritis', 'Rheumatoid Arthritis'),
        ('alzheimer-s-disease-and-other-dementias', "Alzheimer's Disease", "Alzheimer's Disease and Other Dementias"),
        ('multiple-sclerosis', 'Multiple Sclerosis', 'Multiple Sclerosis'),
        ('epilepsy', 'Epilepsy', 'Epilepsy'),
        ('migraine', 'Migraine', 'Migraine'),
        ('major-depressive-disorder', 'Major Depressive Disorder', 'Major Depressive Disorder'),
        ('inflammatory-bowel-disease-crohn-s-uc', 'IBD (Crohn\'s / UC)', 'Inflammatory Bowel Disease (Crohn\'s / UC)'),
        ('gerd-gastroesophageal-reflux-disease', 'GERD', 'Gastroesophageal Reflux Disease'),
        ('hepatitis-c', 'Hepatitis C', 'Hepatitis C'),
        ('hypothyroidism', 'Hypothyroidism', 'Hypothyroidism'),
    ]

    print("\n📊 Updating biomarker atlas pages...")
    for slug, name, condition in biomarker_conditions:
        filepath = ROOT / f'{slug}-biomarkers.html'
        if filepath.exists():
            if not dry_run:
                update_biomarker_page(str(filepath), name, condition, slug)
            else:
                print(f"  [DRY RUN] Would update: {slug}-biomarkers.html")

    # Clinical trials
    ct_path = ROOT / 'clinical_trials.html'
    if ct_path.exists():
        if not dry_run:
            update_clinical_trials_page(str(ct_path))
        else:
            print("  [DRY RUN] Would update: clinical_trials.html")

    # Agents
    agents_path = ROOT / 'agents.html'
    if agents_path.exists():
        if not dry_run:
            update_agents_page(str(agents_path))
        else:
            print("  [DRY RUN] Would update: agents.html")

    # Biomarker index
    bi_path = ROOT / 'biomarker-index.html'
    if bi_path.exists():
        if not dry_run:
            update_biomarker_index_page(str(bi_path))
        else:
            print("  [DRY RUN] Would update: biomarker-index.html")

    # ── 2. Disease intelligence pages ──
    print("\n🧠 Updating disease intelligence / RepurpOS pages...")
    di_dir = ROOT / 'disease-intelligence'
    if di_dir.exists():
        for f in sorted(os.listdir(di_dir)):
            if f.endswith('.html'):
                filepath = di_dir / f
                page_slug = f.replace('.html', '')
                # Derive human-readable name
                name = page_slug.replace('-', ' ').title()
                if not dry_run:
                    update_simple_page(str(filepath), name, f'disease-intelligence/{page_slug}',
                                      "Dataset" if f == 'index.html' else "MedicalWebPage", depth=0)
                else:
                    print(f"  [DRY RUN] Would update: disease-intelligence/{f}")

    # ── 3. Chronic disease interventions pages ──
    print("\n💊 Updating chronic disease interventions pages...")
    cdi_dir = ROOT / 'chronic-disease-interventions'
    if cdi_dir.exists():
        for f in sorted(os.listdir(cdi_dir)):
            if f.endswith('.html'):
                filepath = cdi_dir / f
                page_slug = f.replace('.html', '')
                name = page_slug.replace('-', ' ').title()
                if not dry_run:
                    update_simple_page(str(filepath), name, f'chronic-disease-interventions/{page_slug}',
                                      "CollectionPage" if f == 'index.html' else "MedicalWebPage", depth=0)
                else:
                    print(f"  [DRY RUN] Would update: chronic-disease-interventions/{f}")

    # ── 4. Generate sitemap ──
    if not dry_run:
        print("\n🗺️ Generating sitemap index...")
        generate_sitemap_index()
    else:
        print("\n[DRY RUN] Would generate sitemap index")

    # ── 5. Update robots.txt ──
    if not dry_run:
        update_robots_txt()
    else:
        print("[DRY RUN] Would update robots.txt")

    print("\n" + "=" * 60)
    print("✅ SEO Retrofit complete!")
    if dry_run:
        print("   (DRY RUN - no files were modified)")
        print("   Run without --dry-run to apply changes.")
    else:
        print("   - JSON-LD updated on all pages")
        print("   - Organization references canonical OSMF org")
        print("   - Website entity established")
        print("   - BreadcrumbList added site-wide")
        print("   - Shared OSMF network component deployed")
        print("   - Shared OSMF footer deployed")
        print("   - Sitemap index generated")
        print("   - robots.txt optimized")


if __name__ == '__main__':
    main()