#!/usr/bin/env python3
"""Add Right to Try Relevance section to disease pages."""
import json
import re
from pathlib import Path

def get_right_to_try_data():
    """Extract right-to-try data from the HTML file."""
    html_path = Path(__file__).parent.parent / "disease-intelligence" / "right-to-try.html"

    if not html_path.exists():
        print(f"Error: {html_path} not found")
        return {}

    html = html_path.read_text(encoding="utf-8")

    # Extract the diseases JSON array from the HTML
    match = re.search(r'const diseases = (\[[\s\S]*?\]);', html)
    if not match:
        print("Error: Could not find diseases array in right-to-try.html")
        return {}

    try:
        diseases_data = json.loads(match.group(1))
        return {d['slug']: d for d in diseases_data}
    except json.JSONDecodeError as e:
        print(f"Error parsing diseases JSON: {e}")
        return {}

def get_disease_slug_from_file(html_path):
    """Extract disease slug from HTML file (usually in title or canonical URL)."""
    html = html_path.read_text(encoding="utf-8")

    # Try to extract from canonical URL
    match = re.search(r'<link rel="canonical" href="[^"]*disease-intelligence/([^/]+)\.html"', html)
    if match:
        return match.group(1)

    # Fallback: use filename
    return html_path.stem

def generate_rtt_section(disease_data):
    """Generate HTML for the Right to Try Relevance section."""

    phase_info = []
    for phase in [3, 2, 1]:
        count = disease_data.get(f'phase_{phase}', 0)
        if count > 0:
            phase_info.append(f"Phase {phase}: {count}")

    phases_str = ", ".join(phase_info) if phase_info else "No investigational agents"

    prospective_drugs = disease_data.get('prospectivedrugs', [])
    drugs_display = ", ".join(prospective_drugs[:6]) if prospective_drugs else "None identified"

    is_critical = disease_data.get('critical', False)
    critical_badge = '<span style="background:rgba(239,68,68,.2);color:#fca5a5;font-size:.7rem;padding:4px 8px;border-radius:4px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-left:.5rem;">Critical</span>' if is_critical else ""

    html = f'''
    <div class="overview-card" style="border-color:rgba(74,158,255,.3);background:rgba(74,158,255,.04);">
      <h2 style="display:flex;align-items:center;">
        <span style="color:var(--accent);">Right to Try Relevance</span>
        {critical_badge}
      </h2>

      <div style="margin-bottom:1rem;">
        <div style="font-size:.85rem;color:var(--muted);line-height:1.6;">
          <strong style="color:var(--text);">Eligibility:</strong> This disease meets the federal and state right-to-try legal standard (21 U.S.C. § 360bbb-0a and Montana SB 535): it lacks disease-modifying therapy with indication-specific FDA approval. Patients with {disease_data.get('name', 'this condition')} may be eligible to access investigational therapies outside of clinical trials under right-to-try frameworks.
        </div>
      </div>

      <div class="stat-grid" style="margin-bottom:1rem;">
        <div class="stat-cell">
          <div class="label">Investigational Agents</div>
          <div class="value" style="font-size:1.1rem;">{disease_data.get('investigational_agents', 0)}</div>
          <div style="font-size:.75rem;color:var(--muted);margin-top:.25rem;">{phases_str}</div>
        </div>
        <div class="stat-cell">
          <div class="label">Most Advanced Phase</div>
          <div class="value" style="font-size:1.1rem;">Phase {disease_data.get('most_investigational', '?')}</div>
          <div style="font-size:.75rem;color:var(--muted);margin-top:.25rem;">Highest dev. stage</div>
        </div>
        <div class="stat-cell">
          <div class="label">Gene Targets</div>
          <div class="value" style="font-size:1.1rem;">{disease_data.get('genes', 0)}</div>
          <div style="font-size:.75rem;color:var(--muted);margin-top:.25rem;">Actionable</div>
        </div>
      </div>

      <div style="background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem;margin-bottom:1rem;">
        <div style="font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:.5rem;font-weight:600;">Pipeline Compounds (Top 6)</div>
        <div style="font-size:.9rem;color:var(--text);line-height:1.6;">{drugs_display}</div>
      </div>

      <div style="font-size:.85rem;color:var(--muted);line-height:1.6;">
        <strong style="color:var(--text);">Legal Standard:</strong> Right-to-try requires the disease lacks "adequate approved therapy for that specific disease" (not symptom-management drugs). This distinction means a disease with antidepressants available still qualifies if no FDA approval exists for THAT disease indication.
      </div>

      <a href="right-to-try.html" style="display:inline-block;margin-top:1rem;padding:.6rem 1.25rem;background:var(--accent);color:var(--bg);text-decoration:none;border-radius:6px;font-size:.85rem;font-weight:600;transition:all .2s;" onmouseover="this.style.opacity='0.9'" onmouseout="this.style.opacity='1';">View Right-to-Try Compendium</a>
    </div>
'''
    return html

def add_rtt_section_to_disease(html_path, disease_data):
    """Add Right to Try section to a disease page."""
    html = html_path.read_text(encoding="utf-8")

    # Find where to inject the section - before the first h2.section-title
    match = re.search(r'(<h2 class="section-title")', html)

    if not match:
        print(f"  Warning: Could not find injection point in {html_path.name}, skipping")
        return False

    rtt_section = generate_rtt_section(disease_data)

    # Insert before the match
    insert_pos = match.start()
    updated_html = html[:insert_pos] + rtt_section + '\n\n    ' + html[insert_pos:]

    html_path.write_text(updated_html, encoding="utf-8")
    return True

def add_sections_to_all_diseases():
    """Add Right to Try Relevance sections to all disease pages."""
    disease_dir = Path(__file__).parent.parent / "disease-intelligence"
    rtt_data = get_right_to_try_data()

    if not rtt_data:
        print("Error: No right-to-try data found")
        return

    print(f"Found {len(rtt_data)} diseases in right-to-try registry\n")

    added_count = 0
    skipped_count = 0

    # Process all HTML files in disease-intelligence directory
    for html_file in sorted(disease_dir.glob("*.html")):
        # Skip the right-to-try.html itself and redirect pages
        if html_file.name == "right-to-try.html":
            continue
        if html_file.name.startswith("index.html"):
            continue

        slug = get_disease_slug_from_file(html_file)

        if slug in rtt_data:
            if add_rtt_section_to_disease(html_file, rtt_data[slug]):
                print(f"[OK] {html_file.name} - {rtt_data[slug]['name']}")
                added_count += 1
            else:
                skipped_count += 1
        else:
            # Check if it's a redirect page
            content = html_file.read_text(encoding="utf-8")
            if "meta http-equiv=\"refresh\"" in content:
                # Extract the redirect target
                match = re.search(r'<meta http-equiv="refresh" content="[^"]*url=([^"]+)"', content)
                if match:
                    redirect_file = match.group(1)
                    # Try to get slug from redirect target
                    redirect_slug = redirect_file.replace('.html', '')
                    if redirect_slug in rtt_data:
                        if add_rtt_section_to_disease(html_file, rtt_data[redirect_slug]):
                            print(f"[OK] {html_file.name} (redirect) - {rtt_data[redirect_slug]['name']}")
                            added_count += 1

    print(f"\nAdded Right to Try sections to {added_count} disease pages")
    if skipped_count > 0:
        print(f"Skipped {skipped_count} pages (injection point not found)")

if __name__ == "__main__":
    add_sections_to_all_diseases()
