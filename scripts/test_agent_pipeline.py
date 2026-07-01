#!/usr/bin/env python3
"""Golden tests for biomarker agent pipeline."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from biomarker_agent_pipeline.pipeline import find_agents_for_biomarker

GOLDEN = [
    {
        "biomarker": "Interleukin-6 (IL-6)",
        "expect_agents": ["tocilizumab", "siltuximab", "ziltivekimab", "cisplatin", "sirukumab"],
        "expect_tier": "mechanistic",
    },
]


def main():
    failed = 0
    for case in GOLDEN:
        print(f"Testing {case['biomarker']}…")
        result = find_agents_for_biomarker(case["biomarker"])
        agents = [a["agent_name"].lower() for a in result.get("agents", [])]
        hits = [e for e in case["expect_agents"] if any(e in a for a in agents)]
        if not hits:
            print(f"  FAIL: expected one of {case['expect_agents']} in {agents[:15]}")
            failed += 1
        else:
            print(f"  OK: matched {hits}")
        if case.get("expect_tier"):
            tiers = {a["evidence_tier"] for a in result.get("agents", [])}
            if case["expect_tier"] not in tiers:
                print(f"  WARN: tier {case['expect_tier']} not in {tiers}")
        print(f"  agents={len(result.get('agents', []))} notes={len(result.get('coverage_notes', []))}")
    if failed:
        sys.exit(1)
    print("All golden tests passed.")


if __name__ == "__main__":
    main()