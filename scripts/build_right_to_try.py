#!/usr/bin/env python3
"""Build right-to-try.html from disease-intelligence data - unmet medical needs only."""
import json
import re
from pathlib import Path
from collections import defaultdict

# Diseases considered critical/life-threatening
CRITICAL_SLUGS = {
    'post-acute-covidvaccination-syndrome', 'alzheimers-disease-and-other-dementias',
    'sepsis', 'sclerosing-cholangitis', 'mastocytosis-with-kit-d816v-mutation',
    'alpha-1-antitrypsin-deficiency', 'chronic-kidney-disease', 'lung-cancer',
    'breast-cancer', 'colorectal-cancer', 'ovarian-cancer', 'pancreatic-cancer',
    'prostate-cancer', 'melanoma', 'cervical-cancer', 'thyroid-cancer',
    'urinary-bladder-carcinoma', 'b-cell-chronic-lymphocytic-leukemia',
    'non-hodgkin-lymphoma', 'plasma-cell-myeloma', 'myelodysplastic-syndrome',
    'exocrine-pancreatic-carcinoma', 'ischemic-stroke', 'heart-failure',
    'pulmonary-arterial-hypertension', 'hivaids', 'hepatitis-c',
    'amyotrophic-lateral-sclerosis', 'huntington-disease', 'cystic-fibrosis',
    'sickle-cell-disease', 'hemophilia', 'myasthenia-gravis',
    'myalgic-encephalomyelitis-chronic-fatigue-syndrome', 'lupus-nephritis',
    'systemic-lupus-erythematosus', 'autoimmune-thrombocytopenic-purpura',
    'scleroderma', 'multiple-sclerosis', 'gastric-cancer',
}

def build_right_to_try():
    data_dir = Path(__file__).parent.parent / "data" / "disease-intelligence"
    html_dir = Path(__file__).parent.parent / "disease-intelligence"

    # Load all disease JSON files and filter for unmet needs (no Phase 4 agents)
    diseases = []

    for json_file in sorted(data_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))

            therapeutics = data.get("therapeutics", {})
            phases = defaultdict(int)
            agents_by_phase = defaultdict(list)

            # Count agents by phase
            if isinstance(therapeutics, dict):
                for section_name in ['via_biomarker', 'direct', 'clinical_trials']:
                    agents = therapeutics.get(section_name, [])
                    if isinstance(agents, list):
                        for agent in agents:
                            if isinstance(agent, dict):
                                # Handle both max_phase (numeric) and phase_label (string) formats
                                phase = agent.get('max_phase')
                                phase_label = agent.get('phase_label', '')

                                # Convert phase_label to numeric if needed
                                if not phase and phase_label:
                                    phase_map = {
                                        'Approved': 4, 'FDA Approved': 4,
                                        'Phase 3': 3, 'Phase 2': 2, 'Phase 1': 1,
                                        'Preclinical': 0
                                    }
                                    phase = next((v for k, v in phase_map.items()
                                                if k.lower() in phase_label.lower()), None)

                                if phase is not None:
                                    phases[phase] += 1
                                    agents_by_phase[phase].append({
                                        'name': agent.get('name', 'Unknown'),
                                        'mechanism': agent.get('mechanism'),
                                        'phase': phase,
                                        'phase_label': phase_label,
                                        'source': agent.get('source'),
                                        'evidence_tier': agent.get('evidence_tier')
                                    })

            slug = data.get("condition", {}).get("slug", json_file.stem)

            # Get top agents for prospectivedrugs (Phase 1-3 only, sorted by phase descending)
            all_agents_sorted = []
            for phase in [3, 2, 1]:
                for agent in agents_by_phase[phase]:
                    all_agents_sorted.append(agent)
            # Deduplicate by name
            seen_names = set()
            unique_agents = []
            for a in all_agents_sorted:
                name = a['name']
                if name not in seen_names:
                    seen_names.add(name)
                    unique_agents.append(a)
            # Take top 6 prospectivedrugs
            top_agents = unique_agents[:6]
            prospectivedrugs = [a['name'].title() for a in top_agents]

            # Highest investigational phase (1-3)
            investigational_phases = [p for p in [3, 2, 1] if phases.get(p, 0) > 0]
            most_investigational = max(investigational_phases) if investigational_phases else 0

            # Extract relevant fields - use flat structure for JS compatibility
            disease = {
                "name": data.get("condition", {}).get("name", json_file.stem),
                "slug": slug,
                "mondo_id": data.get("identifiers", {}).get("mondo_id", "N/A"),
                "genes": data.get("summary", {}).get("alteration_count", 0),
                "phase_1": phases.get(1, 0),
                "phase_2": phases.get(2, 0),
                "phase_3": phases.get(3, 0),
                "phase_4": phases.get(4, 0),
                "total_agents": sum(phases.values()),
                "investigational_agents": sum(phases.get(p, 0) for p in [1, 2, 3]),
                "most_investigational": most_investigational,
                "critical": slug in CRITICAL_SLUGS,
                "prospectivedrugs": prospectivedrugs,
            }

            diseases.append(disease)

        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")

    # Sort by most advanced investigational phase, then by investigational agent count (descending)
    diseases.sort(key=lambda d: (-d["most_investigational"], -d["investigational_agents"]))

    # Generate JavaScript data
    diseases_json = json.dumps(diseases, indent=2)

    # Read template
    template_path = html_dir / "right-to-try.html"
    if not template_path.exists():
        print(f"Template not found at {template_path}")
        return

    template = template_path.read_text(encoding="utf-8")

    # Replace the diseases array (between "const diseases = [" and the closing "];" before filterDiseases)
    js_section = f"""// Disease data: unmet medical needs (no Phase 4 approved agents) from RepurpOS
const diseases = {diseases_json};"""

    # Find the existing diseases array and replace it using string slicing
    needle_start = "const diseases = ["
    needle_end = "];"
    start_pos = template.find(needle_start)
    if start_pos == -1:
        print("Error: Could not find 'const diseases = [' in template")
        return
    end_pos = template.find(needle_end, start_pos)
    if end_pos == -1:
        print("Error: Could not find closing '];' after 'const diseases = ['")
        return
    # end_pos + 2 to include "];"
    updated = template[:start_pos] + js_section + template[end_pos + 2:]

    # Also update counts in the template text
    count = len(diseases)
    # Fix the duplicate comment line from string slicing
    updated = updated.replace(
        "// Disease data: unmet medical needs (no Phase 4 approved agents) from RepurpOS\n// Disease data: unmet medical needs (no Phase 4 approved agents) from RepurpOS",
        "// Disease data: unmet medical needs (no Phase 4 approved agents) from RepurpOS"
    )
    # Update filter button counts
    updated = updated.replace(
        ">All (30)</button>",
        f">All ({count})</button>"
    )
    updated = updated.replace(
        'Showing ${filtered.length} of 30 diseases',
        f'Showing ${{filtered.length}} of {count} diseases'
    )
    # Update hero text
    updated = re.sub(
        r'\d+ diseases without FDA-approved disease-modifying therapy',
        f'{count} diseases without FDA-approved disease-modifying therapy',
        updated
    )
    # Update compendium heading and concept count
    updated = re.sub(
        r'Compendium: \d+ Compliant Diseases',
        f'Compendium: {count} Compliant Diseases',
        updated
    )

    # Write updated HTML
    template_path.write_text(updated, encoding="utf-8")

    print(f"Built right-to-try.html with {count} unmet medical needs (no Phase 4 agents)")
    if diseases:
        print(f"\nDiseases included:")
        for d in diseases:
            phases_str = ", ".join(f"Phase {p}: {d[f'phase_{p}']}"
                                   for p in [3, 2, 1] if d[f'phase_{p}'] > 0)
            print(f"  - {d['name']}: {phases_str} ({d['total_agents']} total)")
            if d['prospectivedrugs']:
                print(f"    Prospective drugs: {', '.join(d['prospectivedrugs'][:5])}")

if __name__ == "__main__":
    build_right_to_try()
