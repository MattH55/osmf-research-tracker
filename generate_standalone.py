#!/usr/bin/env python3
"""Generate standalone HTML files with inlined JSON data so they work when opened directly (file://)."""
import json
from pathlib import Path

BASE = Path(__file__).parent

def make_agents_standalone():
    agents_path = BASE / "data" / "therapeutic_agents.json"
    html_path = BASE / "agents.html"
    out_path = BASE / "agents-local.html"

    agents_data = json.loads(agents_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    # Insert the embedded data right after <script>
    embedded_script = f"""<script>
const EMBEDDED_AGENTS_DATA = {json.dumps(agents_data, ensure_ascii=False)};
let allAgents = [];
"""

    # Replace the beginning of the script block
    html = html.replace("<script>\nlet allAgents = [];", embedded_script)

    # Replace the whole load function with a sync version that uses the embedded data
    old_load_start = "async function load() {"
    new_load_start = "function load() {"

    # Simpler: replace the fetch line with direct assignment
    html = html.replace(
        "    const res = await fetch('./data/therapeutic_agents.json');\n    if (!res.ok) throw new Error('HTTP ' + res.status);\n    const data = await res.json();",
        "    const data = EMBEDDED_AGENTS_DATA;"
    )
    html = html.replace("async function load()", "function load()")

    # Remove the catch message about server since this one is standalone
    html = html.replace(
        "metaEl.innerHTML = '<span style=\"color:#b91c1c;\">Failed to load data. See note above about using a local web server (python -m http.server).</span>';",
        "metaEl.innerHTML = '<span style=\"color:#b91c1c;\">Embedded data failed to initialize.</span>';"
    )

    out_path.write_text(html, encoding="utf-8")
    print(f"Created {out_path.name} (agents with inlined data)")

def make_trials_standalone():
    trials_path = BASE / "clinical_trials" / "data" / "clinical_trials_current.json"
    html_path = BASE / "clinical_trials.html"
    out_path = BASE / "clinical_trials-local.html"

    trials_data = json.loads(trials_path.read_text(encoding="utf-8"))
    html = html_path.read_text(encoding="utf-8")

    # Insert embedded data
    embedded_script = f"""<script>
const EMBEDDED_TRIALS_DATA = {json.dumps(trials_data, ensure_ascii=False)};
let allTrials = [];
"""

    html = html.replace("<script>\nlet allTrials = [];", embedded_script)

    # Replace the fetch part
    html = html.replace(
        "    const res = await fetch('./clinical_trials/data/clinical_trials_current.json');\n    if (!res.ok) throw new Error('HTTP ' + res.status);\n    const data = await res.json();",
        "    const data = EMBEDDED_TRIALS_DATA;"
    )
    html = html.replace("async function load()", "function load()")

    # Update the error message in catch
    html = html.replace(
        "metaEl.innerHTML = '<span style=\"color:#b91c1c; font-weight:600;\">Failed to load trial data.</span>';",
        "metaEl.innerHTML = '<span style=\"color:#b91c1c; font-weight:600;\">Embedded trials data failed.</span>';"
    )

    out_path.write_text(html, encoding="utf-8")
    print(f"Created {out_path.name} (trials with inlined data - larger file)")

if __name__ == "__main__":
    make_agents_standalone()
    make_trials_standalone()
    print("\nDone! You can now try double-clicking the -local.html files.")
    print("Note: clinical_trials-local.html will be several MB because of the embedded trial data.")
