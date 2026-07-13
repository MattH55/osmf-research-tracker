#!/usr/bin/env python3
"""
Build static JSON data files for the US price browser page.

Reads the real observation store (data/observations/*.jsonl) and emits:
  docs/data/summary.json                — per-procedure counts + price stats
  docs/data/procedures/{slug}.json       — every real observation for that procedure

No fabricated data. No international data (none exists yet — see
etl/adapters/, which currently fail against robots.txt on every target site).
This only publishes what's actually in the observation store.

USAGE:
  python etl/build_browser_data.py
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBS_DIR = ROOT / "data" / "observations"
OUT_DIR = ROOT / "docs" / "data"
PROC_OUT_DIR = OUT_DIR / "procedures"

OBS_FILES = [
    OBS_DIR / "us-mrf-trilliant.jsonl",
    OBS_DIR / "us-mrf-direct.jsonl",
]


def load_observations() -> list[dict]:
    observations = []
    for path in OBS_FILES:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                observations.append(json.loads(line))
    return observations


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROC_OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading observations…")
    observations = load_observations()
    print(f"Loaded {len(observations)} real observations")

    by_procedure: dict[str, list[dict]] = defaultdict(list)
    for obs in observations:
        by_procedure[obs["procedure_slug"]].append(obs)

    summary = []
    for slug, rows in sorted(by_procedure.items()):
        prices = [r["amount_usd"] for r in rows if r.get("amount_usd") is not None]
        if not prices:
            continue
        prices.sort()

        # Compact rows for the per-procedure file: only what the UI needs
        compact_rows = []
        for r in rows:
            prov = r.get("provenance", {})
            compact_rows.append({
                "facility_id": r.get("facility_id"),
                "facility_name": (r.get("notes") or "").replace("Migrated from Trilliant. Facility: ", "").replace("Migrated from direct_hospital_mrf. Facility: ", ""),
                "amount_usd": r.get("amount_usd"),
                "price_type": r.get("price_type"),
                "completeness_score": (r.get("bundle") or {}).get("completeness_score"),
                "bundle_includes": (r.get("bundle") or {}).get("includes", []),
                "observation_date": r.get("observation_date"),
                "stale": r.get("stale", False),
                "source_url": prov.get("source_url"),
                "source_type": prov.get("source_type"),
            })
        compact_rows.sort(key=lambda x: x["amount_usd"])

        proc_file = PROC_OUT_DIR / f"{slug}.json"
        proc_file.write_text(json.dumps(compact_rows), encoding="utf-8")

        summary.append({
            "slug": slug,
            "count": len(prices),
            "min_usd": round(min(prices), 2),
            "median_usd": round(statistics.median(prices), 2),
            "max_usd": round(max(prices), 2),
            "mean_usd": round(statistics.mean(prices), 2),
        })

    summary.sort(key=lambda x: -x["count"])

    summary_out = {
        "generated_from": "data/observations/*.jsonl (real US MRF/Trilliant data)",
        "total_observations": len(observations),
        "total_procedures": len(summary),
        "international_data_available": False,
        "international_data_note": (
            "International facility adapters exist as code (etl/adapters/) but have "
            "not successfully collected any real price data — all target sites "
            "disallow the scraped paths via robots.txt. No international "
            "observations exist in this system yet."
        ),
        "procedures": summary,
    }

    (OUT_DIR / "summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")

    print(f"\nWrote {len(summary)} procedure files to {PROC_OUT_DIR}")
    print(f"Wrote summary to {OUT_DIR / 'summary.json'}")
    print(f"\nTotal real observations published: {len(observations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
