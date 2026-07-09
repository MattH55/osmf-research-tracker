#!/usr/bin/env python3
"""
CMS Hospital Quality data importer (skeleton).

Downloads hospital star ratings and HCAHPS summaries from data.cms.gov
and normalizes into hospitals.json / PostgreSQL.

USAGE (after configuring dataset URLs):
  python etl/cms_quality.py --out ../data/seed/hospitals.json

Primary datasets (update UUIDs when CMS rotates):
  - Hospital General Information:
    https://data.cms.gov/provider-data/dataset/xubh-q36u
  - HCAHPS Hospital:
    https://data.cms.gov/provider-data/dataset/dgck-syeh

Schedule: quarterly or on CMS release (cron / Airflow).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from urllib.request import urlopen

# CMS Socrata CSV export endpoints — verify before production runs
HOSPITAL_INFO_CSV = (
    "https://data.cms.gov/provider-data/api/1/datastore/query/"
    "xubh-q36u/0/download?format=csv"
)


def fetch_csv(url: str) -> list[dict]:
    """Fetch CMS CSV; returns list of row dicts."""
    with urlopen(url, timeout=120) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return list(csv.DictReader(text.splitlines()))


def parse_stars(value: str) -> float | None:
    v = (value or "").strip()
    if not v or v.lower() in ("not available", "n/a", ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def normalize_row(row: dict) -> dict | None:
    """Map CMS Hospital General Information row → our hospital schema."""
    provider_id = row.get("Facility ID") or row.get("Provider ID")
    name = row.get("Facility Name") or row.get("Hospital Name")
    if not provider_id or not name:
        return None

    zip_code = (row.get("ZIP Code") or "")[:5].zfill(5)
    return {
        "id": f"hosp-cms-{provider_id}",
        "cmsProviderId": provider_id,
        "name": name.strip(),
        "address": (row.get("Address") or "").strip(),
        "city": (row.get("City/Town") or row.get("City") or "").strip(),
        "state": (row.get("State") or "").strip()[:2],
        "zip": zip_code,
        "phone": (row.get("Telephone Number") or row.get("Phone Number") or "").strip(),
        "website": None,
        "shoppableUrl": None,
        "latitude": 0.0,
        "longitude": 0.0,
        "cmsOverallStars": parse_stars(row.get("Hospital overall rating", "")),
        "hcahpsSummary": parse_stars(row.get("Patient experience national comparison", "")),
        "readmissionRate": parse_stars(row.get("Readmission national comparison", "")),
        "mortalityRate": None,
        "safetyRating": parse_stars(row.get("Safety national comparison", "")),
        "dataVintage": date.today().isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Import CMS hospital quality data")
    ap.add_argument("--out", type=Path, default=Path("data/seed/hospitals_cms.json"))
    ap.add_argument("--dry-run", action="store_true", help="Fetch but do not write")
    ap.add_argument("--limit", type=int, default=0, help="Max rows (0 = all)")
    args = ap.parse_args()

    print(f"Fetching CMS hospital data from {HOSPITAL_INFO_CSV} ...")
    try:
        rows = fetch_csv(HOSPITAL_INFO_CSV)
    except Exception as e:
        print(f"ERROR: CMS fetch failed: {e}", file=sys.stderr)
        print("Tip: CMS URLs change — update HOSPITAL_INFO_CSV in this script.", file=sys.stderr)
        return 1

    hospitals = []
    for row in rows:
        h = normalize_row(row)
        if h:
            hospitals.append(h)
        if args.limit and len(hospitals) >= args.limit:
            break

    print(f"Normalized {len(hospitals)} hospitals")
    if args.dry_run:
        print(json.dumps(hospitals[:3], indent=2))
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(hospitals, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())