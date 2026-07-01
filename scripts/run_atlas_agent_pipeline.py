#!/usr/bin/env python3
"""Run agent discovery pipeline for all biomarkers in atlas JSON files."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from biomarker_agent_pipeline.pipeline import find_agents_for_biomarker

BIOMARKER_DIR = ROOT / "data" / "biomarkers"
OUT = ROOT / "data" / "biomarkers" / "agent-discovery.json"
SLUGS = ["long-covid", "pacvs", "me-cfs", "lyme", "gulf-war-illness"]


def marker_id(slug: str, name: str) -> str:
    base = name.lower().replace(" ", "-")
    import re

    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return f"{slug}:{base}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="Run one atlas slug only")
    parser.add_argument("--limit", type=int, default=0, help="Max markers (0 = all)")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between markers")
    args = parser.parse_args()

    slugs = [args.slug] if args.slug else SLUGS
    entries = []
    for slug in slugs:
        atlas = json.loads((BIOMARKER_DIR / f"{slug}.json").read_text(encoding="utf-8"))
        for m in atlas.get("markers", []):
            entries.append((slug, m))

    if args.limit:
        entries = entries[: args.limit]

    results = {}
    for i, (slug, marker) in enumerate(entries, 1):
        mid = marker_id(slug, marker["name"])
        print(f"[{i}/{len(entries)}] {mid}")
        try:
            payload = find_agents_for_biomarker(marker["name"])
            results[mid] = {
                "markerId": mid,
                "markerName": marker["name"],
                "slug": slug,
                "pipeline": payload,
            }
        except Exception as err:
            results[mid] = {"markerId": mid, "error": str(err)}
        time.sleep(args.delay)

    out = {
        "generated": time.strftime("%Y-%m-%d"),
        "count": len(results),
        "markerAgents": results,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {OUT} ({len(results)} markers)")


if __name__ == "__main__":
    main()