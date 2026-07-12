#!/usr/bin/env python3
"""Build right-to-try.html from disease-intelligence data."""
import json
from pathlib import Path

def build_right_to_try():
    data_dir = Path(__file__).parent.parent / "data" / "disease-intelligence"
    html_dir = Path(__file__).parent.parent / "disease-intelligence"

    # Load all disease JSON files
    diseases = []

    for json_file in sorted(data_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))

            # Extract relevant fields
            disease = {
                "name": data.get("condition", {}).get("name", json_file.stem),
                "slug": data.get("condition", {}).get("slug", json_file.stem),
                "mondo_id": data.get("identifiers", {}).get("mondo_id", "N/A"),
                "genes": data.get("summary", {}).get("alteration_count", 0),
                "agents": 0,
                "has_agents": False
            }

            # Count therapeutic agents from the merged field
            therapeutic_counts = data.get("summary", {}).get("therapeutic_counts", {})
            if therapeutic_counts:
                disease["agents"] = therapeutic_counts.get("merged", 0)
                disease["has_agents"] = disease["agents"] > 0

            diseases.append(disease)

        except Exception as e:
            print(f"Error reading {json_file}: {e}")

    # Sort by agent count (ascending) so least-treated diseases appear first
    diseases.sort(key=lambda d: d["agents"])

    # Generate JavaScript data
    diseases_json = json.dumps(diseases, indent=2)

    # Read template
    template_path = html_dir / "right-to-try.html"
    if not template_path.exists():
        print(f"Template not found at {template_path}")
        return

    template = template_path.read_text(encoding="utf-8")

    # Replace the empty diseases array with populated data
    js_section = f"""
// Disease data populated from RepurpOS database
const diseases = {diseases_json};
"""

    # Replace the old diseases declaration
    updated = template.replace(
        "// Disease data - will be populated from RepurpOS database\nconst diseases = [];",
        js_section
    )

    # Write updated HTML
    template_path.write_text(updated, encoding="utf-8")

    min_agents = min([d["agents"] for d in diseases]) if diseases else 0
    max_agents = max([d["agents"] for d in diseases]) if diseases else 0

    print(f"Built right-to-try.html with {len(diseases)} disease profiles")
    print(f"  - Agent range: {min_agents} to {max_agents}")
    print(f"  - Sorted by therapeutic availability (ascending)")
    print(f"  - Note: Curated has_approved_therapy field pending — showing all diseases")

if __name__ == "__main__":
    build_right_to_try()
