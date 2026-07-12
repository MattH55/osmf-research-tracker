#!/usr/bin/env python3
"""Build right-to-try.html from disease-intelligence data - unmet medical needs only."""
import json
from pathlib import Path
from collections import defaultdict

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
                                        'mechanism': agent.get('mechanism', 'Unknown'),
                                        'phase': phase,
                                        'phase_label': phase_label,
                                        'source': agent.get('source'),
                                        'evidence_tier': agent.get('evidence_tier')
                                    })

            # Only include diseases WITHOUT Phase 4 agents (unmet medical needs)
            # Include both those with Phase 1-3 agents AND those with 0 agents at all
            if 4 not in phases:
                # Extract relevant fields
                disease = {
                    "name": data.get("condition", {}).get("name", json_file.stem),
                    "slug": data.get("condition", {}).get("slug", json_file.stem),
                    "mondo_id": data.get("identifiers", {}).get("mondo_id", "N/A"),
                    "genes": data.get("summary", {}).get("alteration_count", 0),
                    "phases": {
                        "phase_1": phases.get(1, 0),
                        "phase_2": phases.get(2, 0),
                        "phase_3": phases.get(3, 0),
                    },
                    "total_agents": sum(phases.values()),
                    "most_advanced": max(phases.keys()) if phases else 0,
                }

                # Get top Phase 2-3 agents (most promising)
                promising = []
                for phase in [3, 2, 1]:
                    agents = agents_by_phase[phase]
                    for agent in agents[:2]:  # Top 2 per phase
                        promising.append({
                            'name': agent['name'],
                            'phase': agent['phase'],
                            'mechanism': agent['mechanism']
                        })
                    if len(promising) >= 5:
                        break

                disease["promising_agents"] = promising

                diseases.append(disease)

        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")

    # Sort by most advanced phase, then by total agents (descending)
    diseases.sort(key=lambda d: (-d["most_advanced"], -d["total_agents"]))

    # Generate JavaScript data
    diseases_json = json.dumps(diseases, indent=2)

    # Read template
    template_path = html_dir / "right-to-try.html"
    if not template_path.exists():
        print(f"Template not found at {template_path}")
        return

    template = template_path.read_text(encoding="utf-8")

    # Replace the old diseases declaration
    js_section = f"""
// Disease data: unmet medical needs (no Phase 4 approved agents) from RepurpOS
const diseases = {diseases_json};
"""

    updated = template.replace(
        "// Disease data populated from RepurpOS database\nconst diseases = [];",
        js_section
    )

    # Also update the filter button count
    updated = updated.replace(
        'data-filter="all">All Diseases (106)</button>',
        f'data-filter="all">All ({len(diseases)}) Unmet Needs</button>'
    )

    # Write updated HTML
    template_path.write_text(updated, encoding="utf-8")

    print(f"Built right-to-try.html with {len(diseases)} unmet medical needs (no Phase 4 agents)")
    if diseases:
        print(f"\nDiseases included:")
        for d in diseases:
            phases_str = ", ".join(f"Phase {p}: {d['phases'][f'phase_{p}']}"
                                   for p in [3, 2, 1] if d['phases'][f'phase_{p}'] > 0)
            print(f"  - {d['name']}: {phases_str} ({d['total_agents']} total)")
            if d['promising_agents']:
                print(f"    Top promising: {', '.join(a['name'] for a in d['promising_agents'][:3])}")

if __name__ == "__main__":
    build_right_to_try()
