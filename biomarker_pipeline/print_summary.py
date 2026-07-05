#!/usr/bin/env python3
"""Print a human-readable summary of a completed batch run."""
import json
import pathlib
import sys

results_dir = pathlib.Path(__file__).parent / "results" / "biomarkers"
summary_path = results_dir / "run_summary.json"

if not summary_path.exists():
    print(f"No run_summary.json found at {summary_path}")
    print("Run the pipeline first: python -m biomarker_pipeline.run_for_diseases --skip-llm")
    sys.exit(1)

summary = json.loads(summary_path.read_text(encoding="utf-8"))

total_agents = 0
total_biomarkers = 0
total_failed = 0

for disease in summary:
    print(f"\n{'='*64}")
    print(f"  {disease['disease']}")
    print(f"{'='*64}")
    if "error" in disease:
        print(f"  ERROR: {disease['error']}")
        continue

    for bm in disease.get("biomarkers", []):
        if bm.get("skipped"):
            print(f"  {bm['biomarker']:<12}  SKIPPED (already exists)")
            continue
        if "error" in bm:
            print(f"  {bm['biomarker']:<12}  FAILED — {bm['error']}")
            total_failed += 1
            continue

        path = pathlib.Path(bm.get("path", ""))
        if not path.exists():
            print(f"  {bm['biomarker']:<12}  MISSING output file")
            total_failed += 1
            continue

        data = json.loads(path.read_text(encoding="utf-8"))
        agents = data.get("agents", [])
        total_agents += len(agents)
        total_biomarkers += 1

        by_tier: dict[str, list[str]] = {}
        for a in agents:
            by_tier.setdefault(a["evidence_tier"], []).append(a["agent_name"])

        tier_str = "  ".join(
            f"{t[0].upper()}: {len(by_tier[t])}"
            for t in ["clinical", "mechanistic", "correlative"]
            if t in by_tier
        )
        print(f"  {bm['biomarker']:<12}  {len(agents):>3} agents  [{tier_str}]")

        # Top 5 agents (clinical first, then mechanistic)
        top = by_tier.get("clinical", []) or by_tier.get("mechanistic", [])
        for name in top[:5]:
            print(f"              -> {name}")

print(f"\n{'='*64}")
print(f"  TOTALS")
print(f"{'='*64}")
print(f"  Diseases processed : {len(summary)}")
print(f"  Biomarkers done    : {total_biomarkers}")
print(f"  Biomarkers failed  : {total_failed}")
print(f"  Total unique agents: {total_agents}")
print(f"  Results directory  : {results_dir}")
