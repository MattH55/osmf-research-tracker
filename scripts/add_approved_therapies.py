#!/usr/bin/env python3
"""Add approved therapies section to disease pages."""
import json
from pathlib import Path
from collections import defaultdict

data_dir = Path("data/disease-intelligence")
html_dir = Path("disease-intelligence")

updated_count = 0

for json_file in sorted(data_dir.glob("*.json")):
    try:
        data = json.loads(json_file.read_text(encoding='utf-8'))
        disease_name = data.get("condition", {}).get("name", json_file.stem)
        slug = json_file.stem

        # Find corresponding HTML file
        html_file = html_dir / f"{slug}.html"
        if not html_file.exists():
            continue

        therapeutics = data.get("therapeutics", {})

        # Separate by phase
        phase_4_agents = []
        phase_1_3_agents = defaultdict(list)

        if isinstance(therapeutics, dict):
            for section in ['via_biomarker', 'direct', 'clinical_trials']:
                agents = therapeutics.get(section, [])
                if isinstance(agents, list):
                    for agent in agents:
                        if isinstance(agent, dict):
                            phase = agent.get('max_phase')
                            phase_label = agent.get('phase_label', '')
                            agent_name = agent.get('name', 'Unknown')
                            mechanism = agent.get('mechanism', 'Unknown mechanism')

                            if phase == 4 or 'Approved' in phase_label:
                                phase_4_agents.append({
                                    'name': agent_name,
                                    'mechanism': mechanism,
                                    'section': section
                                })
                            elif phase in [1, 2, 3]:
                                phase_label_str = phase_label or f"Phase {phase}"
                                phase_1_3_agents[phase_label_str].append({
                                    'name': agent_name,
                                    'mechanism': mechanism
                                })

        if not phase_4_agents:
            continue  # Skip diseases with no approved therapy

        # Read HTML
        html_content = html_file.read_text(encoding='utf-8')

        # Check if section already exists
        if 'id="approved-therapies"' in html_content:
            continue  # Already updated

        # Create approved therapies section
        section_html = f'''
    <section id="approved-therapies">
      <h2 class="section-title">FDA-Approved Therapies</h2>
      <p class="section-sub">Phase 4 agents with regulatory approval for this indication</p>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr>
            <th>Drug Name</th><th>Mechanism</th><th>Type</th>
          </tr></thead>
          <tbody>
'''

        for agent in sorted(phase_4_agents, key=lambda x: x['name']):
            agent_type = "Clinical trial" if agent['section'] == 'clinical_trials' else \
                        "Gene-targeted" if agent['section'] == 'via_biomarker' else "Direct"
            section_html += f'''            <tr>
              <td class="name-cell"><strong>{agent['name']}</strong></td>
              <td>{agent['mechanism']}</td>
              <td><span class="type-badge" style="background:#22c55e">{agent_type}</span></td>
            </tr>
'''

        section_html += '''          </tbody>
        </table>
      </div>
    </section>

'''

        # Find insertion point: before Therapeutics section
        therapeutics_marker = '    <section id="therapeutics">'
        if therapeutics_marker in html_content:
            insert_pos = html_content.find(therapeutics_marker)
            new_html = html_content[:insert_pos] + section_html + html_content[insert_pos:]
            html_file.write_text(new_html, encoding='utf-8')
            updated_count += 1
            print(f"Updated {disease_name}: {len(phase_4_agents)} approved agents")

    except Exception as e:
        print(f"Error processing {json_file.name}: {e}")

print(f"\nTotal pages updated: {updated_count}")
