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
HOSPITALS_JSON = ROOT / "data" / "cms" / "hospitals.json"

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


def load_facility_locations() -> dict[str, dict]:
    """facility_id -> {zip, city, state} from real CMS hospital directory."""
    if not HOSPITALS_JSON.exists():
        return {}
    hospitals = json.loads(HOSPITALS_JSON.read_text(encoding="utf-8"))
    lookup = {}
    for h in hospitals:
        fid = h.get("id")
        if not fid:
            continue
        lookup[fid] = {
            "zip": h.get("zip"),
            "city": h.get("city"),
            "state": h.get("state"),
        }
    return lookup


OUTLIER_CEILING_USD = 500_000  # no legitimate single-procedure cash price should exceed this
SENTINEL_VALUES = {999999999.0, 999999.0}


def is_outlier(amount_usd: float | None) -> bool:
    """Flag obviously corrupt values from upstream MRF parsing (sentinels, decimal
    errors) so they can be excluded from stats/histograms without being hidden
    from the table. See docs/us-data-inventory.md — this is a known upstream
    Trilliant extraction defect, not something fabricated or corrected here."""
    if amount_usd is None:
        return True
    if amount_usd in SENTINEL_VALUES:
        return True
    if amount_usd <= 0 or amount_usd >= OUTLIER_CEILING_USD:
        return True
    return False


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROC_OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading observations…")
    observations = load_observations()
    print(f"Loaded {len(observations)} real observations")

    print("Loading facility locations (zip/city/state)…")
    locations = load_facility_locations()
    print(f"Loaded locations for {len(locations)} facilities")

    by_procedure: dict[str, list[dict]] = defaultdict(list)
    for obs in observations:
        by_procedure[obs["procedure_slug"]].append(obs)

    summary = []
    total_outliers = 0
    for slug, rows in sorted(by_procedure.items()):
        # Compact rows for the per-procedure file: only what the UI needs
        compact_rows = []
        for r in rows:
            prov = r.get("provenance", {})
            loc = locations.get(r.get("facility_id"), {})
            outlier = is_outlier(r.get("amount_usd"))
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
                "zip": loc.get("zip"),
                "city": loc.get("city"),
                "state": loc.get("state"),
                "outlier": outlier,
            })
        compact_rows.sort(key=lambda x: x["amount_usd"])

        # Stats are computed ONLY from non-outlier rows so a single corrupt
        # value (e.g. a $999,999,999 sentinel) can't distort the median or
        # blow out the histogram range. Outlier rows stay in the row list —
        # nothing is deleted or hidden, only excluded from aggregate stats.
        prices = [r["amount_usd"] for r in compact_rows if not r["outlier"]]
        n_outliers = sum(1 for r in compact_rows if r["outlier"])
        total_outliers += n_outliers
        if not prices:
            continue
        prices.sort()

        proc_file = PROC_OUT_DIR / f"{slug}.json"
        proc_file.write_text(json.dumps(compact_rows), encoding="utf-8")

        matched_zip = sum(1 for r in compact_rows if r["zip"])
        summary.append({
            "slug": slug,
            "count": len(prices),
            "total_rows": len(compact_rows),
            "outliers_excluded": n_outliers,
            "min_usd": round(min(prices), 2),
            "median_usd": round(statistics.median(prices), 2),
            "max_usd": round(max(prices), 2),
            "mean_usd": round(statistics.mean(prices), 2),
            "with_zip": matched_zip,
        })

    summary.sort(key=lambda x: -x["count"])

    summary_out = {
        "generated_from": "data/observations/*.jsonl (real US MRF/Trilliant data)",
        "total_observations": len(observations),
        "total_procedures": len(summary),
        "total_cms_hospitals": len(locations),
        "total_outliers_excluded_from_stats": total_outliers,
        "outlier_note": (
            f"{total_outliers} observations were excluded from median/min/max/mean "
            f"and histogram calculations because their price is <= $0 or >= "
            f"${OUTLIER_CEILING_USD:,} (a known upstream Trilliant extraction "
            f"defect — e.g. a literal 999999999 sentinel, or a decimal-shift error "
            f"producing an $8M colonoscopy). These rows are NOT deleted — they "
            f"remain visible in the table with an outlier badge."
        ),
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
