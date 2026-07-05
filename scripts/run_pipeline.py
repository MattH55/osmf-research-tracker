#!/usr/bin/env python3
"""CLI: python scripts/run_pipeline.py --biomarker "Interleukin-6 (IL-6)" --output results/il6.json"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from biomarker_agent_pipeline.config import RESULTS_DIR
from biomarker_agent_pipeline.pipeline import find_agents_for_biomarker


def main():
    parser = argparse.ArgumentParser(description="Biomarker → therapeutic agent discovery pipeline")
    parser.add_argument("--biomarker", required=True, help="Biomarker name (gene/protein/metabolite)")
    parser.add_argument("--output", help="Output JSON path (default: data/agent-pipeline/results/<slug>.json)")
    parser.add_argument("--skip-literature", action="store_true", help="Structured databases only (faster)")
    args = parser.parse_args()

    result = find_agents_for_biomarker(args.biomarker, skip_literature=args.skip_literature)

    if args.output:
        out = Path(args.output)
    else:
        slug = "".join(c if c.isalnum() else "-" for c in args.biomarker.lower()).strip("-")[:80]
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        out = RESULTS_DIR / f"{slug}.json"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"  {len(result.get('agents', []))} agents, tiers: ", end="")
    tiers = {}
    for a in result.get("agents", []):
        tiers[a["evidence_tier"]] = tiers.get(a["evidence_tier"], 0) + 1
    print(tiers)
    if result.get("coverage_notes"):
        print("Coverage notes:")
        for n in result["coverage_notes"]:
            print(f"  - {n}")


if __name__ == "__main__":
    main()