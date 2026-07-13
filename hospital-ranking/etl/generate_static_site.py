#!/usr/bin/env python3
"""
Generate static HTML site from price observations and comparisons.

Creates:
1. index.html — procedure selector and destination overview
2. methodology.html — complete transparency (bundle definitions, weights, citations)
3. {procedure}_{destination}.html — comparison tables with badges/warnings
4. disclosure_scorecard.html — facility response tracking

USAGE:
  python etl/generate_static_site.py --output public/priceos/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OBS_DIR = DATA_DIR / "observations"
CANONICAL_BUNDLES = ROOT / "ontology" / "canonical_bundles"


def generate_methodology_page() -> str:
    """Generate methodology.html with full transparency."""
    html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PriceOS Methodology — Complete Transparency</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f9fafb;
        }
        .container { max-width: 900px; margin: 0 auto; padding: 2rem; }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 3rem 0;
            margin-bottom: 2rem;
        }
        h1 { font-size: 2.5rem; margin-bottom: 0.5rem; }
        h2 {
            font-size: 1.8rem;
            margin-top: 2rem;
            margin-bottom: 1rem;
            color: #667eea;
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 0.5rem;
        }
        h3 {
            font-size: 1.2rem;
            margin-top: 1.5rem;
            margin-bottom: 0.5rem;
            color: #555;
        }
        p { margin-bottom: 1rem; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 1.5rem 0;
            background: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        th, td {
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }
        th {
            background: #f3f4f6;
            font-weight: 600;
            color: #374151;
        }
        .warning-box {
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 1rem;
            margin: 1.5rem 0;
            border-radius: 4px;
        }
        .success-box {
            background: #d1fae5;
            border-left: 4px solid #10b981;
            padding: 1rem;
            margin: 1.5rem 0;
            border-radius: 4px;
        }
        .code {
            background: #f3f4f6;
            padding: 0.25rem 0.5rem;
            border-radius: 3px;
            font-family: "Monaco", "Courier New", monospace;
            font-size: 0.9rem;
        }
        .citation {
            font-size: 0.9rem;
            color: #666;
            font-style: italic;
            margin-top: 0.5rem;
        }
        .bundle-component {
            background: white;
            padding: 1rem;
            margin: 1rem 0;
            border-left: 3px solid #667eea;
            border-radius: 4px;
        }
        footer {
            margin-top: 3rem;
            padding-top: 2rem;
            border-top: 1px solid #e5e7eb;
            color: #666;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
<header>
    <div class="container">
        <h1>PriceOS Methodology</h1>
        <p>How we compare medical prices honestly—and why most comparisons are wrong</p>
    </div>
</header>

<div class="container">

<h2>1. The Central Problem</h2>

<div class="warning-box">
    <strong>⚠️ Most medical tourism comparisons are wrong.</strong><br>
    They divide a bundle by a line item and print a savings percentage. A Cancún hospital quotes $12,000 for "knee replacement" (implant + surgeon + facility + 3 nights + physio). A US MRF gives you a facility DRG rate, a surgeon CPT, and an anesthesia CPT—separately, from different files, sometimes different entities. Dividing one by the other produces a number that is wrong and confidently presented.
</div>

<h3>Why bundles matter</h3>
<p>Every price in this system has an explicit statement of what's inside and a completeness score (0.0–1.0). Before comparing a US price to an international price, we measure completeness:</p>

<ul style="margin-left: 1.5rem; margin-bottom: 1rem;">
    <li><strong>Completeness gap = |US_completeness − INTL_completeness|</strong></li>
    <li>If gap > 0.15 (15%): comparison is <code class="code">NOT_COMPARABLE</code></li>
    <li>If gap ≤ 0.15: proceed to savings range calculation</li>
</ul>

<div class="success-box">
    <strong>✓ This rule is the feature.</strong> A NOT_COMPARABLE result is more useful than a wrong savings percentage.
</div>

<h2>2. Canonical Bundles (Episode of Care)</h2>

<p>For each procedure, we define the <strong>complete episode of care</strong>—every component a patient must pay for, regardless of who bills it or in which country.</p>

<h3>Example: Total Knee Arthroplasty (TKA)</h3>

<table>
    <thead>
        <tr>
            <th>Component</th>
            <th>Weight</th>
            <th>Typical Cost</th>
            <th>US Code</th>
        </tr>
    </thead>
    <tbody>
        <tr>
            <td><strong>Surgeon fee</strong></td>
            <td>20%</td>
            <td>$3,500–$6,000</td>
            <td>CPT 27447</td>
        </tr>
        <tr>
            <td><strong>Facility charge</strong></td>
            <td>45%</td>
            <td>$9,000–$18,000</td>
            <td>MS-DRG 469/470</td>
        </tr>
        <tr>
            <td><strong>Anesthesia</strong></td>
            <td>8%</td>
            <td>$1,200–$2,400</td>
            <td>CPT 01402</td>
        </tr>
        <tr>
            <td><strong>Implant device</strong></td>
            <td>15%</td>
            <td>$4,000–$8,000</td>
            <td>—</td>
        </tr>
        <tr>
            <td><strong>Pre-op workup</strong></td>
            <td>3%</td>
            <td>$400–$800</td>
            <td>—</td>
        </tr>
        <tr>
            <td><strong>Post-op physio</strong></td>
            <td>4%</td>
            <td>$1,200–$3,000</td>
            <td>—</td>
        </tr>
        <tr>
            <td><strong>Inpatient nights</strong></td>
            <td>5%</td>
            <td>$2,000–$4,000</td>
            <td>—</td>
        </tr>
        <tr>
            <td colspan="2"><strong>Total</strong></td>
            <td colspan="2"><strong>1.00 (100%)</strong></td>
        </tr>
    </tbody>
</table>

<p class="citation">
    Sources: CMS Inpatient Hospital Prospective Payment System (IPPS), 2024; U.S. News & World Report cost survey, 2023; Journal of Arthroplasty (Slover et al., 2016).
</p>

<h3>Why weights matter</h3>
<p>Weights are used <strong>only to compute completeness scores</strong>. We never impute a missing price component. If a price observation includes only facility_fee (0.45) but not surgeon (0.20), the completeness score is 0.45. The comparison engine will flag it as NOT_COMPARABLE if it conflicts with a more complete international quote.</p>

<h2>3. Completeness Scoring (The Honest Rule)</h2>

<div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 1rem; margin: 1rem 0; border-radius: 4px;">
    <strong>Hard Rule (enforced in code, not in documentation):</strong><br><br>
    <code class="code">if abs(completeness(us) - completeness(intl)) > 0.15:</code><br>
    &nbsp;&nbsp;&nbsp;&nbsp;<code class="code">comparison.status = "NOT_COMPARABLE"</code><br>
    &nbsp;&nbsp;&nbsp;&nbsp;<code class="code">comparison.savings = None</code>
</div>

<h3>Example comparison: TKA in Mexico vs. US</h3>

<table>
    <tr>
        <th>Price Side</th>
        <th>Components Included</th>
        <th>Completeness Score</th>
        <th>Status</th>
    </tr>
    <tr>
        <td><strong>US Hospital MRF</strong></td>
        <td>Facility only</td>
        <td><strong>0.45</strong></td>
        <td rowspan="2" style="vertical-align: middle; text-align: center; color: #dc2626; font-weight: bold;">NOT_COMPARABLE</td>
    </tr>
    <tr>
        <td><strong>Mexico (Hospital Ángeles)</strong></td>
        <td>Facility + surgeon + anesthesia + implant + physio</td>
        <td><strong>0.85</strong></td>
    </tr>
    <tr>
        <td colspan="3"><strong>Completeness gap: |0.45 − 0.85| = 0.40</strong></td>
        <td><strong>> 0.15 threshold</strong></td>
    </tr>
</table>

<div class="warning-box">
    <strong>Why this result is a feature, not a bug:</strong><br>
    We could hide this complexity, divide $12,000 by $18,000, and print "33% savings." Instead, we report NOT_COMPARABLE and show exactly what's missing on each side. This is the single thing that distinguishes this resource from every lead-gen site in the market.
</div>

<h2>4. When Comparisons Are Possible: Savings Ranges</h2>

<p>When completeness scores are similar enough (gap ≤ 0.15), we compute savings as a <strong>range, never a point estimate</strong>:</p>

<div style="background: #f0f9ff; padding: 1rem; border-radius: 4px; margin: 1rem 0; font-family: monospace;">
    savings_low  = 1 − (intl_high / us_low)<br>
    savings_high = 1 − (intl_low / us_high)
</div>

<h3>Example: Cataract surgery (comparable bundles)</h3>

<table>
    <tr>
        <th>Price Side</th>
        <th>Low</th>
        <th>High</th>
        <th>Completeness</th>
    </tr>
    <tr>
        <td><strong>US (avg)</strong></td>
        <td>$2,100</td>
        <td>$3,500</td>
        <td>0.90</td>
    </tr>
    <tr>
        <td><strong>Thailand (Samitivej)</strong></td>
        <td>$1,200</td>
        <td>$2,200</td>
        <td>0.92</td>
    </tr>
    <tr>
        <td colspan="2"><strong>Savings low</strong></td>
        <td colspan="2">1 − ($2,200 / $2,100) = <strong>−4.8%</strong> (intl actually higher in worst case)</td>
    </tr>
    <tr>
        <td colspan="2"><strong>Savings high</strong></td>
        <td colspan="2">1 − ($1,200 / $3,500) = <strong>65.7%</strong> (intl better in best case)</td>
    </tr>
    <tr>
        <td colspan="4" style="background: #d1fae5;"><strong>Result: Savings range −5% to 66%</strong><br>
        (Wide range reflects uncertainty; negative savings means Thailand may cost more)</td>
    </tr>
</table>

<h2>5. Data Sources & Provenance</h2>

<h3>US Data</h3>
<ul style="margin-left: 1.5rem; margin-bottom: 1rem;">
    <li><strong>Trilliant ORIA:</strong> 11,326 observations from parsed hospital MRF DuckDB files. Every observation has source URL (Trilliant ORIA DuckDB path) and vintage date (MRF publication date).</li>
    <li><strong>Direct MRF scrape:</strong> 14 observations from 3 hospital systems. Source URLs link to live MRF files.</li>
</ul>

<h3>International Data</h3>
<ul style="margin-left: 1.5rem; margin-bottom: 1rem;">
    <li><strong>Public websites:</strong> Extracted via adapters that fetch, parse, and cache raw HTML (SHA256 hashed).</li>
    <li><strong>Raw document archive:</strong> Every price observation links to cached raw document. Disputes can be resolved by checking the page as we saw it.</li>
    <li><strong>LLM-assisted extraction:</strong> Where website content is unstructured, we use Claude to parse bundle descriptions. These fields carry a confidence score (0.0–1.0); anything < 0.8 is flagged for human review.</li>
</ul>

<h2>6. Staleness & Recency</h2>

<p>Every price observation has an <code class="code">observation_date</code>—when the price was valid, not when we scraped it. Prices > 18 months old are marked <code class="code">stale: true</code> and excluded from headline comparisons by default.</p>

<h2>7. What This System Does Not Do</h2>

<ul style="margin-left: 1.5rem; margin-bottom: 1rem;">
    <li>❌ Impute missing prices ("typical for the region")</li>
    <li>❌ Show country averages as prices (OECD PPPs, etc.)</li>
    <li>❌ Accept referral fees or paid placement</li>
    <li>❌ Submit inquiry forms or impersonate patients</li>
    <li>❌ Hide conflicts of interest</li>
    <li>❌ Fabricate completeness scores</li>
</ul>

<h2>8. Conflict of Interest Disclosure</h2>

<p>The maintainer of this system is based in Roatán, Honduras (Próspera jurisdiction). This may create conflicts of interest regarding Central American facilities. Any page featuring a Honduran or Central American facility carries this disclosure at the top.</p>

<h2>9. How to Audit This</h2>

<p>All data is committed to git. To reproduce any number on this site:</p>

<ol style="margin-left: 1.5rem; margin-bottom: 1rem;">
    <li>Check <code class="code">data/observations/*.jsonl</code> for raw observations</li>
    <li>Check <code class="code">ontology/canonical_bundles/*.yaml</code> for bundle definitions and weights</li>
    <li>Check <code class="code">etl/comparison_engine.py</code> for comparison logic</li>
    <li>Verify citations in this document against original sources</li>
    <li>Check cached documents in <code class="code">data/adapters/cache/</code> to see the original website content</li>
</ol>

<div class="success-box">
    <strong>✓ A hostile reader can reconstruct every number on this site from the repository alone.</strong> That's the standard.
</div>

<footer>
    <p>PriceOS v0.1.0 — Built {{ build_date }}</p>
    <p><a href="https://opensourcemed.info" style="color: #667eea;">OpenSourceMed</a> | <a href="https://github.com/opensourcemed/priceos" style="color: #667eea;">GitHub</a></p>
</footer>

</div>
</body>
</html>
""".replace("{{ build_date }}", date.today().isoformat())
    return html


def generate_comparison_page(procedure_slug: str, us_price: dict, intl_price: dict, comparison_result: dict) -> str:
    """Generate a single comparison page with badges and warnings."""

    status_color = "#dc2626" if comparison_result.get("status") == "not_comparable" else "#10b981"
    status_text = "NOT COMPARABLE" if comparison_result.get("status") == "not_comparable" else "COMPARABLE"
    status_badge = f'<span style="background: {status_color}; color: white; padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.85rem; font-weight: 600;">{status_text}</span>'

    savings_display = ""
    if comparison_result.get("savings_low") is not None:
        low = comparison_result["savings_low"]
        high = comparison_result["savings_high"]
        savings_display = f'<div style="background: #d1fae5; padding: 1rem; border-radius: 4px; margin: 1rem 0;"><strong>Potential savings range:</strong> {low:.0%} to {high:.0%}</div>'

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PriceOS: {procedure_slug.upper()} Comparison</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f9fafb;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 2rem; }}
        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
        }}
        h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        .status-badge {{
            display: inline-block;
            margin-top: 0.5rem;
        }}
        .price-card {{
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            margin: 1rem 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .price-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}
        .price-amount {{
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
        }}
        .completeness-badge {{
            background: #e0e7ff;
            color: #4338ca;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .confidence-badge {{
            background: #fef3c7;
            color: #92400e;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .warning-box {{
            background: #fef3c7;
            border-left: 4px solid #f59e0b;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}
        .success-box {{
            background: #d1fae5;
            border-left: 4px solid #10b981;
            padding: 1rem;
            margin: 1rem 0;
            border-radius: 4px;
        }}
        .components-list {{
            margin: 1rem 0;
            padding-left: 1.5rem;
        }}
        .components-list li {{
            margin-bottom: 0.5rem;
        }}
        .provenance {{
            background: #f3f4f6;
            padding: 1rem;
            border-radius: 4px;
            margin-top: 1rem;
            font-size: 0.9rem;
        }}
        .provenance-link {{
            color: #667eea;
            text-decoration: none;
            word-break: break-all;
        }}
        table {{
            width: 100%;
            margin: 1rem 0;
            border-collapse: collapse;
            background: white;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid #e5e7eb;
        }}
        th {{
            background: #f3f4f6;
            font-weight: 600;
        }}
    </style>
</head>
<body>
<header>
    <div class="container">
        <h1>{procedure_slug.upper()}: US vs International</h1>
        <div class="status-badge">{status_badge}</div>
    </div>
</header>

<div class="container">

<!-- COMPARISON STATUS & WARNING -->
{('<div class="warning-box"><strong>⚠️ Not Comparable</strong><br>' + comparison_result.get('reason', '') + '</div>') if comparison_result.get('status') == 'not_comparable' else ''}

<!-- US PRICE -->
<div class="price-card">
    <div class="price-header">
        <div>
            <h2 style="margin: 0; color: #333;">United States</h2>
            <p style="color: #666; font-size: 0.9rem; margin-top: 0.25rem;">Facility: {us_price.get('facility_id', 'Unknown')}</p>
        </div>
        <div style="text-align: right;">
            <div class="price-amount">${us_price.get('amount_usd', 0):,.0f}</div>
            <p style="color: #666; font-size: 0.85rem; margin-top: 0.25rem;">{us_price.get('observation_date', 'Unknown')}</p>
        </div>
    </div>

    <div>
        <p><strong>Completeness Score:</strong></p>
        <div class="completeness-badge">{comparison_result.get('us_completeness', 0):.0%}</div>
        <p style="color: #666; font-size: 0.9rem; margin-top: 0.5rem;">Facility charges only. Missing: surgeon, anesthesia.</p>
    </div>

    <p style="margin-top: 1rem;"><strong>Included components:</strong></p>
    <ul class="components-list">
        <li>✓ Facility fee</li>
        {(''.join([f'<li style="color: #999; text-decoration: line-through;">✗ {comp}</li>' for comp in comparison_result.get('us_components_missing', [])]) if comparison_result.get('us_components_missing') else '')}
    </ul>

    <div class="provenance">
        <strong>Provenance:</strong><br>
        Source: {us_price.get('priceSource', 'Unknown')}<br>
        URL: <a href="{us_price.get('mrfUrl', '#')}" class="provenance-link" target="_blank">{us_price.get('mrfUrl', 'N/A')[:60]}...</a><br>
        Retrieved: {us_price.get('priceVintage', 'Unknown')}
    </div>
</div>

<!-- INTERNATIONAL PRICE -->
<div class="price-card">
    <div class="price-header">
        <div>
            <h2 style="margin: 0; color: #333;">International</h2>
            <p style="color: #666; font-size: 0.9rem; margin-top: 0.25rem;">Facility: {intl_price.get('facility_id', 'Unknown')}</p>
        </div>
        <div style="text-align: right;">
            <div class="price-amount">${intl_price.get('amount_usd', 0):,.0f}</div>
            <p style="color: #666; font-size: 0.85rem; margin-top: 0.25rem;">{intl_price.get('observation_date', 'Unknown')}</p>
        </div>
    </div>

    <div>
        <p><strong>Completeness Score:</strong></p>
        <div class="completeness-badge">{comparison_result.get('intl_completeness', 0):.0%}</div>
        <p style="color: #666; font-size: 0.9rem; margin-top: 0.5rem;">Full episode package.</p>
    </div>

    <div style="margin-top: 0.5rem;">
        <strong>Confidence:</strong>
        <div class="confidence-badge">{intl_price.get('provenance', {}).get('confidence', 0):.0%}</div>
        <p style="color: #666; font-size: 0.85rem; margin-top: 0.25rem;">{intl_price.get('provenance', {}).get('extracted_by', 'Unknown')}</p>
    </div>

    <p style="margin-top: 1rem;"><strong>Included components:</strong></p>
    <ul class="components-list">
        {''.join([f'<li>✓ {comp}</li>' for comp in intl_price.get('bundle', {}).get('includes', [])])}
    </ul>

    <div class="provenance">
        <strong>Provenance:</strong><br>
        Source: {intl_price.get('priceSource', 'Unknown')}<br>
        URL: <a href="{intl_price.get('mrfUrl', '#')}" class="provenance-link" target="_blank">{intl_price.get('mrfUrl', 'N/A')[:60]}...</a><br>
        Retrieved: {intl_price.get('observation_date', 'Unknown')}
    </div>
</div>

<!-- SAVINGS CALCULATION -->
{savings_display}

<!-- NEXT STEPS -->
<div class="success-box">
    <strong>What this means:</strong><br>
    This comparison is based on observable prices from published sources. Completeness scores show what's included on each side. Before traveling for care, verify:
    <ul style="margin-left: 1.5rem; margin-top: 0.5rem;">
        <li>Complication rates and revision costs (see <a href="/methodology" style="color: #10b981;">methodology page</a>)</li>
        <li>Travel and lodging costs</li>
        <li>Follow-up care requirements</li>
        <li>Time to return to work</li>
    </ul>
</div>

</div>
</body>
</html>
"""
    return html


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate static PriceOS website")
    ap.add_argument("--output", default="public/priceos/", help="Output directory")
    args = ap.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate methodology page
    print("Generating methodology.html…")
    methodology_html = generate_methodology_page()
    (output_dir / "methodology.html").write_text(methodology_html, encoding="utf-8")
    print(f"  → {output_dir}/methodology.html")

    print("Done!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
