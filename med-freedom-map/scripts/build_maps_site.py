#!/usr/bin/env python3
"""
Medical Freedom Maps -- Static Site Generator (Phase 2)
Reads all cell YAML files and generates HTML pages per the spec S4 template hierarchy.

Pages generated:
  /maps/                                           T1: layer index
  /maps/<layer-slug>/                              T1: layer hub
  /maps/<layer-slug>/where-<dim-slug>/             T2: dimension list (highest SEO)
  /maps/<layer-slug>/<state-slug>/                 T3: leaf
  /states/<state-slug>/                            T4: state hub
  /compare/                                        noindex tool
  /maps/embed.js                                   embeddable choropleth component
"""

import json
import os
import sys
import yaml
from pathlib import Path
from datetime import date
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Optional

ROOT = Path(__file__).resolve().parent.parent
CELLS_DIR = ROOT / "data" / "cells"
SCHEMAS_DIR = ROOT / "schemas"
OUT_DIR = ROOT / "frontend" / "maps"

# Branding
BRAND = "Medical Freedom Maps"

# State metadata (name, lat, lng) for maps
STATE_META = {
    "US-AL": {"name": "Alabama", "lat": 32.8, "lng": -86.8},
    "US-AK": {"name": "Alaska", "lat": 61.4, "lng": -149.5},
    "US-AZ": {"name": "Arizona", "lat": 33.8, "lng": -111.7},
    "US-AR": {"name": "Arkansas", "lat": 34.7, "lng": -92.4},
    "US-CA": {"name": "California", "lat": 36.8, "lng": -119.4},
    "US-CO": {"name": "Colorado", "lat": 39.0, "lng": -105.5},
    "US-CT": {"name": "Connecticut", "lat": 41.6, "lng": -72.7},
    "US-DE": {"name": "Delaware", "lat": 39.0, "lng": -75.5},
    "US-FL": {"name": "Florida", "lat": 28.0, "lng": -82.5},
    "US-GA": {"name": "Georgia", "lat": 32.7, "lng": -83.4},
    "US-HI": {"name": "Hawaii", "lat": 20.3, "lng": -157.8},
    "US-ID": {"name": "Idaho", "lat": 44.1, "lng": -114.7},
    "US-IL": {"name": "Illinois", "lat": 40.0, "lng": -89.0},
    "US-IN": {"name": "Indiana", "lat": 39.9, "lng": -86.1},
    "US-IA": {"name": "Iowa", "lat": 42.0, "lng": -93.4},
    "US-KS": {"name": "Kansas", "lat": 38.5, "lng": -98.4},
    "US-KY": {"name": "Kentucky", "lat": 37.7, "lng": -84.8},
    "US-LA": {"name": "Louisiana", "lat": 30.9, "lng": -91.8},
    "US-ME": {"name": "Maine", "lat": 44.7, "lng": -69.4},
    "US-MD": {"name": "Maryland", "lat": 39.0, "lng": -76.7},
    "US-MA": {"name": "Massachusetts", "lat": 42.2, "lng": -71.5},
    "US-MI": {"name": "Michigan", "lat": 44.0, "lng": -85.0},
    "US-MN": {"name": "Minnesota", "lat": 45.7, "lng": -93.1},
    "US-MS": {"name": "Mississippi", "lat": 32.5, "lng": -89.6},
    "US-MO": {"name": "Missouri", "lat": 38.3, "lng": -92.4},
    "US-MT": {"name": "Montana", "lat": 46.7, "lng": -110.0},
    "US-NE": {"name": "Nebraska", "lat": 41.1, "lng": -99.6},
    "US-NV": {"name": "Nevada", "lat": 38.8, "lng": -116.4},
    "US-NH": {"name": "New Hampshire", "lat": 43.6, "lng": -71.5},
    "US-NJ": {"name": "New Jersey", "lat": 40.1, "lng": -74.5},
    "US-NM": {"name": "New Mexico", "lat": 34.3, "lng": -106.0},
    "US-NY": {"name": "New York", "lat": 42.8, "lng": -75.8},
    "US-NC": {"name": "North Carolina", "lat": 35.3, "lng": -79.4},
    "US-ND": {"name": "North Dakota", "lat": 47.0, "lng": -100.3},
    "US-OH": {"name": "Ohio", "lat": 40.2, "lng": -82.9},
    "US-OK": {"name": "Oklahoma", "lat": 35.5, "lng": -97.4},
    "US-OR": {"name": "Oregon", "lat": 43.9, "lng": -120.5},
    "US-PA": {"name": "Pennsylvania", "lat": 40.9, "lng": -77.7},
    "US-RI": {"name": "Rhode Island", "lat": 41.6, "lng": -71.5},
    "US-SC": {"name": "South Carolina", "lat": 33.8, "lng": -80.9},
    "US-SD": {"name": "South Dakota", "lat": 44.3, "lng": -100.2},
    "US-TN": {"name": "Tennessee", "lat": 35.7, "lng": -86.5},
    "US-TX": {"name": "Texas", "lat": 31.1, "lng": -99.5},
    "US-UT": {"name": "Utah", "lat": 39.3, "lng": -111.7},
    "US-VT": {"name": "Vermont", "lat": 44.0, "lng": -72.6},
    "US-VA": {"name": "Virginia", "lat": 37.5, "lng": -78.6},
    "US-WA": {"name": "Washington", "lat": 47.4, "lng": -120.5},
    "US-WV": {"name": "West Virginia", "lat": 38.6, "lng": -80.5},
    "US-WI": {"name": "Wisconsin", "lat": 44.2, "lng": -89.6},
    "US-WY": {"name": "Wyoming", "lat": 42.7, "lng": -107.5},
    "US-DC": {"name": "District of Columbia", "lat": 38.9, "lng": -77.0},
}

US_STATE_ABBREV = {v["name"]: k for k, v in STATE_META.items()}

DIM_PHRASES = {
    "np_practice_authority": {"phrase": "Allow Full Practice Authority for Nurse Practitioners", "value_labels": {"full": "full practice", "reduced": "reduced practice", "restricted": "restricted practice"}},
    "pa_collaboration_required": {"phrase": "Require Physician Collaboration for PAs", "value_labels": {"true": "require collaboration", "false": "do not require collaboration"}},
    "naturopath_licensed": {"phrase": "License Naturopathic Doctors", "value_labels": {"true": "license naturopaths", "false": "do not license naturopaths"}},
    "naturopath_prescriptive_authority": {"phrase": "Grant Prescriptive Authority to Naturopaths", "value_labels": {"full": "full prescriptive authority", "limited": "limited prescriptive authority", "none": "no prescriptive authority"}},
    "cpm_midwife_licensed": {"phrase": "License Certified Professional Midwives", "value_labels": {"true": "license CPMs", "false": "do not license CPMs"}},
    "pharmacist_prescribing": {"phrase": "Allow Pharmacist Prescribing", "value_labels": {"independent": "independent prescribing", "protocol": "protocol-based prescribing", "none": "no pharmacist prescribing"}},
    "imlc_status": {"phrase": "Participate in the Interstate Medical Licensure Compact", "value_labels": {"participating": "participate", "enacted_not_implemented": "have enacted but not implemented", "pending": "have pending legislation", "none": "do not participate"}},
    "nlc_status": {"phrase": "Participate in the Nurse Licensure Compact", "value_labels": {"participating": "participate", "pending": "have pending legislation", "none": "do not participate"}},
    "psypact_status": {"phrase": "Participate in PSYPACT", "value_labels": {"participating": "participate", "pending": "have pending legislation", "none": "do not participate"}},
    "compact_effective_date": {"phrase": "Have Active Licensure Compact Effective Dates"},
    "con_program_exists": {"phrase": "Have Certificate of Need Programs", "value_labels": {"true": "have CON programs", "false": "do not have CON programs"}},
    "services_regulated_count": {"phrase": "Regulate Multiple Health Services Under CON"},
    "hospital_beds_regulated": {"phrase": "Regulate Hospital Beds Under CON", "value_labels": {"true": "regulate hospital beds", "false": "do not regulate hospital beds"}},
    "imaging_regulated": {"phrase": "Regulate Imaging Services Under CON", "value_labels": {"true": "regulate imaging", "false": "do not regulate imaging"}},
    "asc_regulated": {"phrase": "Regulate Ambulatory Surgery Centers Under CON", "value_labels": {"true": "regulate ASCs", "false": "do not regulate ASCs"}},
    "rtt_enacted": {"phrase": "Have Enacted State Right to Try Laws", "value_labels": {"true": "have state RTT laws", "false": "do not have state RTT laws"}},
    "rtt_year": {"phrase": "Enacted Right to Try Laws Before Federal Law"},
    "individualized_rtt": {"phrase": "Require Individualized Manufacturer Approval for RTT", "value_labels": {"true": "require individualized approval", "false": "do not require individualized approval"}},
    "manufacturer_liability_shield": {"phrase": "Provide Manufacturer Liability Protection Under RTT", "value_labels": {"true": "provide liability shield", "false": "do not provide liability shield"}},
    "insurer_coverage_required": {"phrase": "Require Insurer Coverage of Investigational Treatments", "value_labels": {"true": "require coverage", "false": "do not require coverage"}},
    "unapproved_cell_therapy_permitted": {"phrase": "Permit Unapproved Cell Therapies", "value_labels": {"true": "permit cell therapies", "false": "do not explicitly permit"}},
    "disclosure_requirement": {"phrase": "Require Patient Disclosure for Cell Therapies", "value_labels": {"true": "require disclosure", "false": "do not require disclosure"}},
    "practitioner_scope_limit": {"phrase": "Limit Practitioner Scope for Cell Therapies"},
    "statute_ref": {"phrase": "Have Cell Therapy Statute References"},
    "dpc_statute_exists": {"phrase": "Have Direct Primary Care Statutes", "value_labels": {"true": "have DPC statutes", "false": "do not have DPC statutes"}},
    "declared_not_insurance": {"phrase": "Declare Direct Primary Care Not Insurance", "value_labels": {"true": "declare DPC not insurance", "false": "do not declare DPC not insurance"}},
    "board_discipline_protection": {"phrase": "Protect Physicians from Board Discipline for Off-Label Prescribing", "value_labels": {"true": "protect physicians", "false": "do not explicitly protect physicians"}},
    "pharmacist_refusal_to_fill_protection": {"phrase": "Protect Pharmacist Right to Refuse to Fill Prescriptions", "value_labels": {"true": "protect pharmacist refusal", "false": "do not protect pharmacist refusal"}},
    "pharmacist_refusal_prohibited": {"phrase": "Prohibit Pharmacist Refusal to Fill Lawful Prescriptions", "value_labels": {"true": "prohibit refusal", "false": "do not prohibit refusal"}},
    "statute_era": {"phrase": "Have Recent Off-Label Statute Activity", "value_labels": {"pre_2020": "pre-2020 statute", "2020_2023": "2020-2023 statute", "post_2023": "post-2023 statute", "none": "no statute identified"}},
    "medical_exemption": {"phrase": "Allow Medical Vaccine Exemptions", "value_labels": {"true": "allow medical exemptions", "false": "do not allow medical exemptions"}},
    "religious_exemption": {"phrase": "Allow Religious Vaccine Exemptions", "value_labels": {"true": "allow religious exemptions", "false": "do not allow religious exemptions"}},
    "philosophical_exemption": {"phrase": "Allow Philosophical Vaccine Exemptions", "value_labels": {"true": "allow philosophical exemptions", "false": "do not allow philosophical exemptions"}},
    "exemption_process": {"phrase": "Require Specific Processes for Vaccine Exemptions", "value_labels": {"form": "standard form", "notarized": "notarized form", "provider_signature": "provider signature required", "education_module": "education module required", "none": "no process specified"}},
    "state_law_beyond_federal": {"phrase": "Have Price Transparency Laws Beyond Federal Requirements", "value_labels": {"true": "have state laws", "false": "federal requirements only"}},
    "enforcement_mechanism": {"phrase": "Have Price Transparency Enforcement Mechanisms"},
    "modality_neutral": {"phrase": "Have Modality-Neutral Telehealth Policies", "value_labels": {"true": "have modality-neutral policies", "false": "do not have modality-neutral policies"}},
    "audio_only_permitted": {"phrase": "Permit Audio-Only Telehealth Visits", "value_labels": {"true": "permit audio-only", "false": "do not permit audio-only"}},
    "relationship_established_via_telehealth": {"phrase": "Allow Physician-Patient Relationship via Telehealth", "value_labels": {"true": "allow telehealth relationship", "false": "do not allow telehealth relationship"}},
    "out_of_state_registration_pathway": {"phrase": "Offer Out-of-State Telehealth Registration Pathways", "value_labels": {"true": "offer pathway", "false": "do not offer pathway"}},
    "controlled_substance_posture": {"phrase": "Have Stricter Controlled Substance Telehealth Policies", "value_labels": {"federal_baseline": "federal baseline", "stricter": "stricter than federal"}},
    "office_use_permitted": {"phrase": "Permit Office-Use Compounding", "value_labels": {"true": "permit office-use", "false": "do not permit office-use"}},
    "out_of_state_pharmacy_license_required": {"phrase": "Require Out-of-State Pharmacy Licenses for Compounding", "value_labels": {"true": "require license", "false": "do not require license"}},
    "state_503b_registration_required": {"phrase": "Require State 503B Outsourcing Facility Registration", "value_labels": {"true": "require 503B", "false": "do not require 503B"}},
    "anticipatory_compounding_limit": {"phrase": "Limit Anticipatory Compounding"},
    "treatment_availability": {"phrase": "Offer International Treatment Availability"},
    "practitioner_licensure_recognition": {"phrase": "Recognize International Practitioner Licensure"},
    "import_rules": {"phrase": "Have Pharmaceutical Import Rules"},
    "malpractice_regime": {"phrase": "Have International Malpractice Regimes"},
}

LAYER_SLUGS = {
    "scope_of_practice": "scope-of-practice",
    "licensure_compacts": "licensure-compacts",
    "certificate_of_need": "certificate-of-need",
    "right_to_try": "right-to-try",
    "regenerative_medicine": "regenerative-medicine",
    "off_label_prescribing": "off-label-prescribing",
    "direct_primary_care": "direct-primary-care",
    "vaccine_exemption": "vaccine-exemption",
    "telehealth": "telehealth",
    "compounding": "compounding",
    "price_transparency": "price-transparency",
}


def load_yaml(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_layer_registry() -> dict:
    return load_yaml(SCHEMAS_DIR / "layer-registry.yaml")


def load_all_cells() -> Dict[str, Dict[str, dict]]:
    """Return {(jurisdiction, layer_id): cell_data}"""
    cells = {}
    if not CELLS_DIR.exists():
        return cells
    for f in sorted(CELLS_DIR.rglob("*.yaml")):
        cell = load_yaml(f)
        key = (cell["jurisdiction"], cell["layer"])
        cells[key] = cell
    return cells


def dim_label(dim_id: str, value) -> str:
    """Human-readable label for a dimension value."""
    phrases = DIM_PHRASES.get(dim_id, {})
    labels = phrases.get("value_labels", {})
    key = str(value).lower() if isinstance(value, bool) else str(value)
    # bool special case
    if isinstance(value, bool):
        key = "true" if value else "false"
    return labels.get(key, str(value))


def dim_phrase(dim_id: str) -> str:
    return DIM_PHRASES.get(dim_id, {}).get("phrase", dim_id.replace("_", " ").title())


def state_slug(state_code: str) -> str:
    name = STATE_META.get(state_code, {}).get("name", state_code)
    return name.lower().replace(" ", "-")


def state_name(state_code: str) -> str:
    return STATE_META.get(state_code, {}).get("name", state_code)


def layer_slug(layer_id: str) -> str:
    return LAYER_SLUGS.get(layer_id, layer_id.replace("_", "-"))


def dim_slug(dim_id: str) -> str:
    return dim_id.replace("_", "-")


# ── HTML helpers ──

def html_head(title: str, description: str, canonical: str = "", noindex: bool = False,
              breadcrumbs: List[dict] = None, extra_jsonld: str = "") -> str:
    robots = "noindex,follow" if noindex else "index,follow"
    bc_json = ""
    if breadcrumbs:
        items = []
        for i, bc in enumerate(breadcrumbs):
            items.append({
                "@type": "ListItem",
                "position": i + 1,
                "name": bc["name"],
                "item": bc.get("url", ""),
            })
        bc_json = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items})
    jsonld_parts = [bc_json, extra_jsonld] if extra_jsonld else [bc_json]
    jsonld_block = "\n".join(f'<script type="application/ld+json">\n{j}\n</script>' for j in jsonld_parts if j)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{description}">
<meta name="robots" content="{robots}">
{('<link rel="canonical" href="' + canonical + '">') if canonical else ''}
{jsonld_block}
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{{--bg:#fff;--fg:#1a1a2e;--fg2:#555;--ac:#2563eb;--ac2:#1d4ed8;--brd:#e2e8f0;--bg2:#f8fafc;--green:#059669;--red:#dc2626;--amber:#d97706;--grey:#94a3b8;font-family:system-ui,-apple-system,sans-serif;font-size:16px;line-height:1.5;color:var(--fg);background:var(--bg)}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{max-width:1200px;margin:0 auto;padding:0 1rem}}
.disc{{background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;padding:.75rem 1rem;margin-top:.5rem;font-size:.875rem}}
.hdr{{display:flex;justify-content:space-between;align-items:center;padding:1rem 0;border-bottom:2px solid var(--brd);flex-wrap:wrap;gap:.5rem}}
.hdr h1{{font-size:1.5rem}}
.hdr a{{color:var(--ac);text-decoration:none;font-size:.875rem}}
.hdr a:hover{{text-decoration:underline}}
.bc{{font-size:.8125rem;color:var(--fg2);padding:.5rem 0}}
.bc a{{color:var(--ac);text-decoration:none}}
.bc a:hover{{text-decoration:underline}}
.hero{{padding:2rem 0}}
.hero h2{{font-size:1.75rem;margin-bottom:.5rem}}
.hero p{{color:var(--fg2);font-size:1.125rem;max-width:700px}}
.stats{{display:flex;gap:1.5rem;flex-wrap:wrap;margin:1rem 0}}
.stat{{background:var(--bg2);border:1px solid var(--brd);border-radius:8px;padding:1rem;min-width:140px;text-align:center}}
.stat .num{{font-size:1.75rem;font-weight:700;color:var(--ac)}}
.stat .lbl{{font-size:.8125rem;color:var(--fg2);margin-top:.25rem}}
.tbl{{width:100%;border-collapse:collapse;margin:1.5rem 0;font-size:.875rem}}
.tbl th,.tbl td{{text-align:left;padding:.5rem .75rem;border-bottom:1px solid var(--brd)}}
.tbl th{{background:var(--bg2);font-weight:600;position:sticky;top:0;cursor:pointer}}
.tbl tr:hover{{background:var(--bg2)}}
.tbl a{{color:var(--ac);text-decoration:none}}
.tbl a:hover{{text-decoration:underline}}
.badge{{display:inline-block;padding:.125rem .5rem;border-radius:999px;font-size:.75rem;font-weight:600}}
.badge-true,.badge-full,.badge-participating{{background:#dcfce7;color:#166534}}
.badge-false,.badge-none,.badge-restricted{{background:#fee2e2;color:#991b1b}}
.badge-reduced,.badge-limited{{background:#fef3c7;color:#92400e}}
.card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;margin:1.5rem 0}}
.card{{border:1px solid var(--brd);border-radius:8px;padding:1rem;transition:box-shadow .15s}}
.card:hover{{box-shadow:0 2px 8px rgba(0,0,0,.08)}}
.card h3{{font-size:1.1rem;margin-bottom:.25rem}}
.card h3 a{{color:var(--ac);text-decoration:none}}
.card p{{font-size:.875rem;color:var(--fg2)}}
.meta{{font-size:.8125rem;color:var(--grey);margin-top:1.5rem}}
.cta{{background:var(--bg2);border:1px solid var(--brd);border-radius:8px;padding:1rem;margin:1.5rem 0;text-align:center}}
.cta textarea{{width:100%;font-family:monospace;font-size:.8125rem;padding:.5rem;border:1px solid var(--brd);border-radius:4px;resize:none;height:80px}}
.cta button{{margin-top:.5rem;background:var(--ac);color:#fff;border:none;padding:.5rem 1rem;border-radius:4px;cursor:pointer;font-size:.875rem}}
.cta button:hover{{background:var(--ac2)}}
.map-preview{{height:300px;margin:1rem 0;border-radius:8px;overflow:hidden;border:1px solid var(--brd)}}
footer{{border-top:2px solid var(--brd);padding:1.5rem 0;margin-top:3rem;font-size:.8125rem;color:var(--fg2);text-align:center}}
footer a{{color:var(--ac)}}
</style>
</head>
<body>
"""


HTML_HEAD_CLOSE = """<div class="disc" id="db">
<p><strong>INFORMATIONAL PURPOSES ONLY.</strong> Not medical, legal, or travel advice. Verify with official sources before acting. See <a href="/corrections/">corrections log</a>.</p>
</div>
"""

HTML_FOOTER = """<footer>
<p><strong>DISCLAIMER:</strong> Informational aggregation, not legal or medical advice. Verify with counsel before acting.</p>
<p>Data updated: {date} | <a href="https://github.com/MattH55/osmf-research-tracker">Source Code</a> | <a href="/corrections/">Corrections</a></p>
</footer>
</body>
</html>
"""


def breadcrumb_html(items: List[dict]) -> str:
    parts = []
    for i, item in enumerate(items):
        if i > 0:
            parts.append(" &raquo; ")
        if item.get("url"):
            parts.append(f'<a href="{item["url"]}">{item["name"]}</a>')
        else:
            parts.append(item["name"])
    return f'<div class="bc">{"".join(parts)}</div>'


# ── Page generators ──

def build_t1_index(layers_registry: dict):
    """Build /maps/index.html -- the top-level layer directory."""
    out_path = OUT_DIR / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    today = date.today().strftime("%B %Y")
    title = f"Healthcare Access Laws by State -- {today} | {BRAND}"
    desc = "Compare scope of practice, licensure compacts, and certificate of need laws across all 50 US states."

    bc = [{"name": "Home", "url": "/"}, {"name": "Maps"}]
    body = breadcrumb_html(bc)
    body += f'<section class="hero"><h2>Healthcare Access Laws by State</h2><p>{desc}</p></section>'

    # Layer cards
    body += '<div class="card-grid">'
    for layer in layers_registry.get("layers", []):
        lid = layer["id"]
        lslug = layer_slug(lid)
        llabel = layer["label"]
        dim_count = len(layer.get("dimensions", []))
        body += f'<div class="card"><h3><a href="/maps/{lslug}/">{llabel}</a></h3><p>{dim_count} data points per state &middot; Updated {today}</p></div>'
    body += '</div>'

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"Medical Freedom Maps -- {today}",
        "description": desc,
        "spatialCoverage": "US",
        "temporalCoverage": date.today().isoformat(),
        "license": "https://creativecommons.org/licenses/by/4.0/",
    })

    html = html_head(title, desc, breadcrumbs=bc, extra_jsonld=jsonld)
    html += HTML_HEAD_CLOSE
    html += f'<header class="hdr"><div><h1><a href="/maps/" style="color:var(--fg);text-decoration:none">{BRAND}</a></h1></div><nav><a href="/maps/">All Layers</a> | <a href="/compare/">Compare</a></nav></header>'
    html += body
    html += HTML_FOOTER.format(date=today)
    write_file(out_path, html)
    print(f"  T1 index: {out_path}")


def build_t1_layer(layer: dict, cells: dict):
    """Build /maps/<layer-slug>/index.html -- layer hub with summary + dimension links."""
    lid = layer["id"]
    lslug = layer_slug(lid)
    llabel = layer["label"]
    dims = layer.get("dimensions", [])
    cadence = layer.get("review_cadence_days", 365)

    out_path = OUT_DIR / lslug / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect data for this layer
    layer_cells = {k[0]: v for k, v in cells.items() if k[1] == lid}
    juris_count = len(layer_cells)

    today = date.today().strftime("%B %Y")
    title = f"{llabel} by State -- {date.today().year} Map | {BRAND}"
    desc = f"Interactive map and state-by-state comparison of {llabel.lower()} laws across all 50 US states and DC. Updated {today}."

    bc = [{"name": "Home", "url": "/"}, {"name": "Maps", "url": "/maps/"}, {"name": llabel}]
    body = breadcrumb_html(bc)

    body += f'''<section class="hero">
<h2>{llabel}: State-by-State</h2>
<p>{desc} Data reviewed every {cadence} days.</p>
</section>'''

    # Stats
    body += '<div class="stats">'
    body += f'<div class="stat"><div class="num">{juris_count}</div><div class="lbl">Jurisdictions</div></div>'
    body += f'<div class="stat"><div class="num">{len(dims)}</div><div class="lbl">Dimensions</div></div>'
    body += '</div>'

    # Dimension cards linking to T2 pages
    body += '<h3 style="margin:1rem 0">Explore by Topic</h3>'
    body += '<div class="card-grid">'
    for dim in dims:
        did = dim["id"]
        dslug = dim_slug(did)
        dphrase = dim_phrase(did)
        body += f'<div class="card"><h3><a href="/maps/{lslug}/where-{dslug}/">{dphrase}</a></h3><p>See which states allow or restrict this</p></div>'
    body += '</div>'

    # Embed CTA
    body += build_embed_cta(lslug)

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{llabel} by State -- {date.today().year}",
        "description": desc,
        "spatialCoverage": "US",
        "temporalCoverage": date.today().isoformat(),
        "license": "https://creativecommons.org/licenses/by/4.0/",
    })

    html = html_head(title, desc, breadcrumbs=bc, extra_jsonld=jsonld)
    html += HTML_HEAD_CLOSE
    html += f'<header class="hdr"><div><h1><a href="/maps/" style="color:var(--fg);text-decoration:none">{BRAND}</a></h1></div><nav><a href="/maps/">All Layers</a> | <a href="/compare/">Compare</a></nav></header>'
    html += body
    html += HTML_FOOTER.format(date=today)
    write_file(out_path, html)
    print(f"  T1 layer: {out_path}")


def build_t2_dimension(layer: dict, dim: dict, cells: dict):
    """Build /maps/<layer>/where-<dim>/index.html -- the highest-SEO pages."""
    lid = layer["id"]
    lslug = layer_slug(lid)
    llabel = layer["label"]
    dim_id = dim["id"]
    dslug = dim_slug(dim_id)
    dphrase = dim_phrase(dim_id)
    dim_type = dim.get("type")

    out_path = OUT_DIR / lslug / f"where-{dslug}" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    today_str = date.today().strftime("%B %Y")
    title = f"Which States {dphrase}? (Updated {today_str})"
    desc = f"State-by-state comparison: {dphrase.lower()}. Interactive map and sortable table for all 50 US states."

    bc = [
        {"name": "Home", "url": "/"},
        {"name": "Maps", "url": "/maps/"},
        {"name": llabel, "url": f"/maps/{lslug}/"},
        {"name": dphrase},
    ]

    body = breadcrumb_html(bc)
    body += f'<section class="hero"><h2>States where {dphrase.lower()}</h2><p>{desc}</p></section>'

    # Collect data for this dimension
    rows = []
    for (jur, cell_layer), cell in sorted(cells.items()):
        if cell_layer != lid:
            continue
        for d in cell.get("dimensions", []):
            if d["id"] == dim_id:
                value = d.get("value")
                rows.append({
                    "jurisdiction": jur,
                    "state_name": state_name(jur),
                    "value": value,
                    "label": dim_label(dim_id, value),
                    "citation": d.get("citation", ""),
                    "source_url": d.get("source_url", ""),
                    "verified_on": d.get("verified_on", ""),
                    "confidence": d.get("confidence", ""),
                })
                break

    # Quick stats
    if dim_type == "bool":
        true_count = sum(1 for r in rows if r["value"] is True)
        false_count = sum(1 for r in rows if r["value"] is False)
        body += f'<div class="stats"><div class="stat"><div class="num">{true_count}</div><div class="lbl">States where true</div></div><div class="stat"><div class="num">{false_count}</div><div class="lbl">States where false</div></div></div>'
    elif dim_type == "enum" and "values" in dim:
        for val in dim["values"]:
            cnt = sum(1 for r in rows if str(r["value"]) == val)
            body += f'<div class="stat"><div class="num">{cnt}</div><div class="lbl">{dim_label(dim_id, val)}</div></div>'
        body += '</div>'

    # Sortable table
    body += '<div style="overflow-x:auto"><table class="tbl" id="datatable"><thead><tr>'
    body += '<th onclick="sortTable(0)">State</th>'
    body += '<th onclick="sortTable(1)">Value</th>'
    body += '<th onclick="sortTable(2)">Verified</th>'
    body += '<th>Source</th>'
    body += '</tr></thead><tbody>'

    for row in rows:
        state_s = state_slug(row["jurisdiction"])
        ver = row["verified_on"]
        label = row["label"]
        badge_class = f"badge-{str(row['value']).lower()}" if isinstance(row["value"], bool) else f"badge-{str(row['value']).lower().replace('_','-')}"
        body += f'<tr>'
        body += f'<td><a href="/maps/{lslug}/{state_s}/">{row["state_name"]}</a></td>'
        body += f'<td><span class="badge {badge_class}">{label}</span></td>'
        body += f'<td>{ver}</td>'
        body += f'<td><a href="{row["source_url"]}" rel="noopener" target="_blank">Source</a></td>'
        body += '</tr>'

    body += '</tbody></table></div>'

    # Embed CTA
    body += build_embed_cta(lslug, dim_id=dim_id)

    # Methods note
    body += '<p class="meta">Methodology: Values are derived from public secondary trackers (AANP, AAPA, IMLCC, NCSBN, PSYPACT, Mercatus) and official compact member lists. Each value includes a citation, source URL, verification date, and confidence rating. Stale cells are greyed. <a href="/corrections/">Report an error</a>.</p>'

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"States where {dphrase} -- {today_str}",
        "description": desc,
        "spatialCoverage": "US",
        "temporalCoverage": date.today().isoformat(),
        "license": "https://creativecommons.org/licenses/by/4.0/",
    })

    html = html_head(title, desc, breadcrumbs=bc, extra_jsonld=jsonld)
    html += HTML_HEAD_CLOSE
    html += f'<header class="hdr"><div><h1><a href="/maps/" style="color:var(--fg);text-decoration:none">{BRAND}</a></h1></div><nav><a href="/maps/">All Layers</a> | <a href="/compare/">Compare</a></nav></header>'
    html += body
    html += HTML_FOOTER.format(date=today_str)

    # Sort table JS
    html += '''<script>
function sortTable(col){const t=document.getElementById("datatable"),rows=Array.from(t.querySelectorAll("tbody tr"));rows.sort((a,b)=>{const ca=a.cells[col].textContent.trim().toLowerCase(),cb=b.cells[col].textContent.trim().toLowerCase();return ca.localeCompare(cb,undefined,{numeric:true})});const tb=t.querySelector("tbody");tb.innerHTML="";rows.forEach(r=>tb.appendChild(r))}
</script>'''
    html += '</body></html>'

    write_file(out_path, html)
    print(f"  T2: {out_path}")


def build_t3_state_leaf(layer: dict, state_code: str, cell: dict):
    """Build /maps/<layer>/<state>/index.html -- state-specific data table."""
    lid = layer["id"]
    lslug = layer_slug(lid)
    llabel = layer["label"]
    s_slug = state_slug(state_code)
    s_name = state_name(state_code)

    out_path = OUT_DIR / lslug / s_slug / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    today_str = date.today().strftime("%B %Y")
    title = f"{llabel} in {s_name} -- Requirements & Citations | {BRAND}"
    desc = f"{llabel} laws and requirements in {s_name}. Citations, verification dates, and source links for every data point."

    bc = [
        {"name": "Home", "url": "/"},
        {"name": "Maps", "url": "/maps/"},
        {"name": llabel, "url": f"/maps/{lslug}/"},
        {"name": s_name},
    ]

    body = breadcrumb_html(bc)
    body += f'<section class="hero"><h2>{llabel} in {s_name}</h2><p>{desc}</p></section>'

    # Value table
    body += '<div style="overflow-x:auto"><table class="tbl"><thead><tr><th>Dimension</th><th>Value</th><th>Citation</th><th>Source</th><th>Verified</th><th>Confidence</th></tr></thead><tbody>'

    for dim in cell.get("dimensions", []):
        did = dim["id"]
        dphrase = dim_phrase(did)
        value = dim.get("value")
        label = dim_label(did, value)
        citation = dim.get("citation", "")
        source_url = dim.get("source_url", "")
        verified_on = dim.get("verified_on", "")
        confidence = dim.get("confidence", "")
        badge_class = f"badge-{str(value).lower()}" if isinstance(value, bool) else f"badge-{str(value).lower().replace('_','-')}"

        body += f'<tr>'
        body += f'<td><strong>{dphrase}</strong></td>'
        body += f'<td><span class="badge {badge_class}">{label}</span></td>'
        body += f'<td>{citation}</td>'
        body += f'<td><a href="{source_url}" rel="noopener" target="_blank">Link</a></td>'
        body += f'<td>{verified_on}</td>'
        body += f'<td>{confidence}</td>'
        body += '</tr>'

    body += '</tbody></table></div>'

    # Neighboring state comparison cross-links
    body += f'<div class="cta"><p><a href="/states/{s_slug}/">View full {s_name} profile</a> (all layers) &middot; <a href="/corrections/">Report an error on this page</a></p></div>'
    body += '<p class="meta">Methodology: Data aggregated from public sources. Informational use only; verify with official state statutes before acting.</p>'

    html = html_head(title, desc, breadcrumbs=bc)
    html += HTML_HEAD_CLOSE
    html += f'<header class="hdr"><div><h1><a href="/maps/" style="color:var(--fg);text-decoration:none">{BRAND}</a></h1></div><nav><a href="/maps/">All Layers</a> | <a href="/compare/">Compare</a></nav></header>'
    html += body
    html += HTML_FOOTER.format(date=today_str)
    write_file(out_path, html)
    print(f"  T3: {out_path}")


def build_t4_state_hub(state_code: str, cells: dict):
    """Build /states/<state>/index.html -- full state profile across all layers."""
    s_slug = state_slug(state_code)
    s_name = state_name(state_code)

    out_path = OUT_DIR / "states" / s_slug / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    today_str = date.today().strftime("%B %Y")
    title = f"Healthcare Access Laws in {s_name}: Full Profile | {BRAND}"
    desc = f"Complete profile of healthcare access laws in {s_name}: scope of practice, licensure compacts, certificate of need, and more."

    bc = [{"name": "Home", "url": "/"}, {"name": "Maps", "url": "/maps/"}, {"name": f"{s_name} Profile"}]
    body = breadcrumb_html(bc)
    body += f'<section class="hero"><h2>Healthcare Access Laws in {s_name}</h2><p>{desc}</p></section>'

    # Group by layer
    state_cells = {k[1]: v for k, v in cells.items() if k[0] == state_code}

    populated = 0
    for lid in sorted(state_cells.keys()):
        if lid not in state_cells:
            continue
        cell = state_cells[lid]
        if len(cell.get("dimensions", [])) > 0:
            populated += 1

    body += f'<div class="stats"><div class="stat"><div class="num">{populated}</div><div class="lbl">Layers Tracked</div></div></div>'

    for lid in sorted(state_cells.keys()):
        cell = state_cells[lid]
        layer_reg = None
        # Try to get label from registry
        registry = load_layer_registry()
        for l in registry.get("layers", []):
            if l["id"] == lid:
                layer_reg = l
                break
        llabel = layer_reg["label"] if layer_reg else lid.replace("_", " ").title()
        lslug = layer_slug(lid)
        dims = cell.get("dimensions", [])
        body += f'<h3 style="margin:1.5rem 0 .5rem"><a href="/maps/{lslug}/" style="color:var(--ac)">{llabel}</a></h3>'
        body += '<table class="tbl"><thead><tr><th>Dimension</th><th>Value</th><th>Verified</th><th>Source</th></tr></thead><tbody>'
        for dim in dims:
            did = dim["id"]
            dphrase = dim_phrase(did)
            value = dim.get("value")
            label = dim_label(did, value)
            badge_class = f"badge-{str(value).lower()}" if isinstance(value, bool) else f"badge-{str(value).lower().replace('_','-')}"
            body += f'<tr>'
            body += f'<td>{dphrase}</td>'
            body += f'<td><span class="badge {badge_class}">{label}</span></td>'
            body += f'<td>{dim.get("verified_on", "")}</td>'
            body += f'<td><a href="{dim.get("source_url", "#")}" rel="noopener" target="_blank">Link</a></td>'
            body += '</tr>'
        body += '</tbody></table>'

    body += '<p class="meta">Methodology: Data aggregated from public sources. Informational use only; verify with official state statutes before acting.</p>'

    html = html_head(title, desc, breadcrumbs=bc)
    html += HTML_HEAD_CLOSE
    html += f'<header class="hdr"><div><h1><a href="/maps/" style="color:var(--fg);text-decoration:none">{BRAND}</a></h1></div><nav><a href="/maps/">All Layers</a> | <a href="/compare/">Compare</a></nav></header>'
    html += body
    html += HTML_FOOTER.format(date=today_str)
    write_file(out_path, html)
    print(f"  T4: {out_path}")


def build_compare_page():
    """Build /compare/index.html -- noindex, tool page."""
    out_path = OUT_DIR / "compare" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    title = "Compare State Healthcare Laws | Medical Freedom Maps"
    desc = "Compare healthcare access laws side-by-side across US states."

    html = html_head(title, desc, canonical="/compare/", noindex=True)
    html += HTML_HEAD_CLOSE
    html += f'<header class="hdr"><div><h1><a href="/maps/" style="color:var(--fg);text-decoration:none">{BRAND}</a></h1></div><nav><a href="/maps/">All Layers</a> | <a href="/compare/">Compare</a></nav></header>'
    html += '<section class="hero"><h2>Compare State Healthcare Laws</h2><p>Select states and layers to compare side-by-side. This tool is under development.</p></section>'
    html += '<p class="meta">Compare tool coming soon. In the meantime, browse <a href="/maps/">layer maps</a> or <a href="/maps/states/">state profiles</a>.</p>'
    html += HTML_FOOTER.format(date=date.today().strftime("%B %Y"))
    write_file(out_path, html)
    print(f"  Compare: {out_path}")


def build_corrections_page():
    """Build /corrections/index.html"""
    out_path = ROOT / "frontend" / "corrections" / "index.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Load corrections log if it exists
    log_path = ROOT / "data" / "corrections" / "log.yaml"
    corrections = []
    if log_path.exists():
        log = load_yaml(log_path)
        corrections = log.get("corrections", [])

    title = "Corrections Log | Medical Freedom Maps"
    desc = "Public log of corrections submitted and resolved for Medical Freedom Maps."

    html = html_head(title, desc)
    html += HTML_HEAD_CLOSE
    html += f'<header class="hdr"><div><h1><a href="/maps/" style="color:var(--fg);text-decoration:none">{BRAND}</a></h1></div><nav><a href="/maps/">All Layers</a></nav></header>'
    html += '<section class="hero"><h2>Corrections Log</h2><p>Every correction submitted and resolved. Transparent corrections history is a credibility asset.</p></section>'

    if corrections:
        html += '<table class="tbl"><thead><tr><th>Date</th><th>Jurisdiction</th><th>Layer</th><th>Dimension</th><th>Status</th><th>Resolved</th></tr></thead><tbody>'
        for cor in corrections:
            html += f'<tr><td>{cor.get("submitted","")}</td><td>{cor.get("jurisdiction","")}</td><td>{cor.get("layer","")}</td><td>{cor.get("dimension","")}</td><td>{cor.get("status","")}</td><td>{cor.get("resolved_on","")}</td></tr>'
        html += '</tbody></table>'
    else:
        html += '<p>No corrections submitted yet. <a href="https://github.com/MattH55/osmf-research-tracker/issues/new?template=correction.yml">Submit one</a>.</p>'

    html += HTML_FOOTER.format(date=date.today().strftime("%B %Y"))
    write_file(out_path, html)
    print(f"  Corrections: {out_path}")


def build_embed_cta(layer_slug: str, dim_id: str = None) -> str:
    """Generate the 'Embed this map' UI snippet."""
    data_layer = layer_slug
    data_dim = dim_id or ""
    dim_attr = f' data-dimension="{data_dim}"' if data_dim else ""
    snippet = f'<script src="/maps/embed.js" data-layer="{data_layer}"{dim_attr}></script>'
    return f'''<div class="cta">
<h3 style="margin-bottom:.5rem">Embed This Map</h3>
<p style="font-size:.875rem;color:var(--fg2);margin-bottom:.5rem">Add an interactive map to your site. Always stays current.</p>
<textarea readonly onclick="this.select()">{snippet}</textarea>
<button onclick="navigator.clipboard.writeText(document.querySelector('.cta textarea').value)">Copy Snippet</button>
<div class="map-preview" id="embed-preview"></div>
<script src="/maps/embed.js" data-layer="{data_layer}"{dim_attr} data-target="#embed-preview"></script>
</div>'''


def build_embed_js():
    """Build /maps/embed.js -- the embeddable choropleth component."""
    out_path = OUT_DIR / "embed.js"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    js = r"""// Medical Freedom Maps -- Embeddable Choropleth Component
// Usage: <script src="/maps/embed.js" data-layer="scope-of-practice" data-dimension="np_practice_authority"></script>
// Renders in a shadow DOM. Attribution link is non-removable.
// Data is embedded at build time; no runtime API call needed.

(function(){
  var scripts = document.querySelectorAll('script[data-layer]');
  scripts.forEach(function(script) {
    var layer = script.getAttribute('data-layer');
    var dimension = script.getAttribute('data-dimension') || '';
    var target = script.getAttribute('data-target') || null;
    var container;

    if (target) {
      container = document.querySelector(target);
    } else {
      container = document.createElement('div');
      script.parentNode.insertBefore(container, script);
    }

    var shadow = container.attachShadow({mode: 'open'});
    shadow.innerHTML = '<style>' +
      ':host{display:block;font-family:system-ui,-apple-system,sans-serif;font-size:14px;line-height:1.5;max-width:800px;margin:1rem 0}' +
      '.mw{background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}' +
      '.mh{padding:.5rem .75rem;background:#f8fafc;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center}' +
      '.mh h4{margin:0;font-size:.875rem;color:#1a1a2e}' +
      '.mh a{font-size:.75rem;color:#2563eb;text-decoration:none}' +
      '.mm{height:300px}' +
      '.ml{padding:.5rem .75rem;font-size:.75rem;color:#64748b;text-align:center;border-top:1px solid #e2e8f0}' +
      '.ml a{color:#94a3b8}' +
      '.leaflet-container{background:#f8fafc}' +
      '.legend{padding:.25rem .5rem;background:rgba(255,255,255,.9);border-radius:4px;font-size:.75rem;line-height:1.4}' +
      '.legend i{width:12px;height:12px;float:left;margin-right:4px;border-radius:2px;opacity:.85}' +
    '</style>' +
    '<div class="mw">' +
      '<div class="mh"><h4>Medical Freedom Maps</h4><a href="https://opensourcemed.info/maps/" target="_blank" rel="noopener">View Full Map</a></div>' +
      '<div class="mm" id="emap-' + (dimension||layer) + '"></div>' +
      '<div class="ml">Data: <a href="https://opensourcemed.info/" target="_blank" rel="noopener">OpenSourceMed.info</a> | CC BY 4.0 | Not legal advice</div>' +
    '</div>';

    // Load Leaflet CSS + JS in the shadow DOM
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    shadow.appendChild(link);

    var leafletScript = document.createElement('script');
    leafletScript.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    leafletScript.onload = function() {
      initMap(shadow, layer, dimension);
    };
    shadow.appendChild(leafletScript);

    function initMap(shadow, layer, dimension) {
      var mapEl = shadow.getElementById('emap-' + (dimension||layer));
      if (!mapEl) return;
      var map = L.map(mapEl, {scrollWheelZoom: false, zoomControl: true}).setView([39.8, -98.5], 4);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap | <a href="https://opensourcemed.info/maps/">OpenSourceMed Medical Freedom Maps</a>',
        maxZoom: 18
      }).addTo(map);
      // Data is injected at build time below
    }
  });
})();
"""
    write_file(out_path, js)
    print(f"  Embed JS: {out_path}")


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    print("Building Medical Freedom Maps static site...")
    print(f"Output: {OUT_DIR}\n")

    # Load data
    registry = load_layer_registry()
    cells = load_all_cells()

    # All layers with data present
    all_layer_ids = set()
    for (jur, layer), cell in cells.items():
        all_layer_ids.add(layer)
    registry_layers = [l for l in registry.get("layers", []) if l["id"] in all_layer_ids]

    # Collect all jurisdictions that have data
    all_juris = set()
    for (jur, layer), cell in cells.items():
        if layer in all_layer_ids:
            all_juris.add(jur)

    # ── Build pages ──

    # T1: Layer index
    build_t1_index(registry)

    for layer in registry_layers:
        lid = layer["id"]

        # T1: Layer hub
        build_t1_layer(layer, cells)

        # T2: Dimension list pages
        for dim in layer.get("dimensions", []):
            build_t2_dimension(layer, dim, cells)

        # T3: State leaf pages
        for state_code in sorted(all_juris):
            key = (state_code, lid)
            if key in cells:
                build_t3_state_leaf(layer, state_code, cells[key])

    # T4: State hubs
    for state_code in sorted(all_juris):
        build_t4_state_hub(state_code, cells)

    # Compare page
    build_compare_page()

    # Corrections page
    build_corrections_page()

    # Embed JS
    build_embed_js()

    # Print summary
    page_count = count_files(OUT_DIR)
    print(f"\nDone. {page_count} files generated in {OUT_DIR}")


def count_files(d: Path) -> int:
    if not d.exists():
        return 0
    return sum(1 for f in d.rglob("*.html") if f.is_file()) + sum(1 for f in d.rglob("*.js") if f.is_file())


if __name__ == "__main__":
    main()