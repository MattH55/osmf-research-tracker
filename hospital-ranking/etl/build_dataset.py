#!/usr/bin/env python3
"""
Build full U.S. hospital dataset from CMS + Census ZIP centroids.

Outputs:
  data/cms/hospitals.json      — all CMS hospitals (~5,400)
  data/cms/zip-centroids.json  — U.S. ZIP → lat/lng (~33,000)
  data/cms/meta.json           — vintage, counts, sources

USAGE:
  python etl/build_dataset.py
  python etl/build_dataset.py --types acute,critical  # filter hospital types
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cms"

CMS_HOSPITAL_CSV = (
    "https://data.cms.gov/provider-data/api/1/datastore/query/"
    "xubh-q36u/0/download?format=csv"
)
# U.S. ZIP centroids (open dataset)
ZIP_CENTROIDS_CSV = (
    "https://raw.githubusercontent.com/midwire/free_zipcode_data/"
    "master/all_us_zipcodes.csv"
)

TYPE_FILTER_DEFAULT = {
    "acute": "Acute Care Hospitals",
    "critical": "Critical Access Hospitals",
    "children": "Childrens",
    "rural_er": "Rural Emergency Hospital",
    "va": "Acute Care - Veterans Administration",
    "dod": "Acute Care - Department of Defense",
    "psych": "Psychiatric",
    "longterm": "Long-term",
}

INCLUDE_ALL_TYPES = set(TYPE_FILTER_DEFAULT.values())


def fetch_bytes(url: str, timeout: int = 180) -> bytes:
    with urlopen(url, timeout=timeout) as resp:
        return resp.read()


def parse_float(value: str) -> float | None:
    v = (value or "").strip()
    if not v or v.lower() in ("not available", "n/a", "null", ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_int(value: str) -> int | None:
    v = parse_float(value)
    return int(v) if v is not None else None


def measure_ratio(worse: str, better: str, total: str) -> float | None:
    """Higher = worse performance. Returns 0–100 approximate 'worse %' of measures."""
    t = parse_int(total)
    if not t or t <= 0:
        return None
    w = parse_int(worse) or 0
    b = parse_int(better) or 0
    # scale: more 'worse' vs 'better' → higher rate
    return round(100 * w / t, 1)


def stars_to_safety_score(worse: str, better: str, total: str) -> float | None:
    """Map CMS measure counts to a 1–5 style safety proxy."""
    t = parse_int(total)
    if not t or t <= 0:
        return None
    b = parse_int(better) or 0
    w = parse_int(worse) or 0
    # 5 = all better, 1 = all worse
    score = 1 + 4 * (b / t) if t else None
    if w > b:
        score = max(1.0, (score or 3) - 0.5 * (w - b) / t)
    return round(min(5.0, max(1.0, score or 0)), 1) if score else None


def load_zip_centroids() -> dict[str, dict]:
    print("Downloading U.S. ZIP centroids …")
    text = fetch_bytes(ZIP_CENTROIDS_CSV).decode("utf-8", errors="replace")
    reader = csv.DictReader(text.splitlines())
    out: dict[str, dict] = {}
    for row in reader:
        zcta = (row.get("code") or "").strip()[:5].zfill(5)
        lat = parse_float(row.get("lat") or "")
        lng = parse_float(row.get("lon") or "")
        if not zcta or lat is None or lng is None:
            continue
        if zcta not in out:
            out[zcta] = {
                "lat": lat,
                "lng": lng,
                "city": (row.get("city") or "").strip(),
                "state": (row.get("state") or "").strip()[:2],
            }
    print(f"  {len(out):,} ZIP centroids loaded")
    return out


def normalize_hospital(row: dict, zips: dict[str, dict]) -> dict | None:
    provider_id = (row.get("Facility ID") or "").strip()
    name = (row.get("Facility Name") or "").strip()
    if not provider_id or not name:
        return None

    zip_code = (row.get("ZIP Code") or "").replace(" ", "")[:5].zfill(5)
    z = zips.get(zip_code)
    lat = z["lat"] if z else 0.0
    lng = z["lng"] if z else 0.0

    return {
        "id": f"hosp-cms-{provider_id}",
        "cmsProviderId": provider_id,
        "name": name,
        "address": (row.get("Address") or "").strip(),
        "city": (row.get("City/Town") or "").strip(),
        "state": (row.get("State") or "").strip()[:2],
        "zip": zip_code,
        "phone": (row.get("Telephone Number") or "").strip(),
        "hospitalType": (row.get("Hospital Type") or "").strip(),
        "ownership": (row.get("Hospital Ownership") or "").strip(),
        "emergencyServices": (row.get("Emergency Services") or "").strip(),
        "latitude": lat,
        "longitude": lng,
        "cmsOverallStars": parse_float(row.get("Hospital overall rating")),
        "hcahpsSummary": None,
        "readmissionRate": measure_ratio(
            row.get("Count of READM Measures Worse", ""),
            row.get("Count of READM Measures Better", ""),
            row.get("Count of Facility READM Measures", ""),
        ),
        "mortalityRate": measure_ratio(
            row.get("Count of MORT Measures Worse", ""),
            row.get("Count of MORT Measures Better", ""),
            row.get("Count of Facility MORT Measures", ""),
        ),
        "safetyRating": stars_to_safety_score(
            row.get("Count of Safety Measures Worse", ""),
            row.get("Count of Safety Measures Better", ""),
            row.get("Count of Facility Safety Measures", ""),
        ),
        "dataVintage": date.today().isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--types",
        default="all",
        help="Comma-separated: acute,critical,children,rural_er,va,dod,psych,longterm or 'all'",
    )
    args = ap.parse_args()

    if args.types == "all":
        allowed = INCLUDE_ALL_TYPES
    else:
        keys = [k.strip() for k in args.types.split(",")]
        allowed = {TYPE_FILTER_DEFAULT[k] for k in keys if k in TYPE_FILTER_DEFAULT}

    zips = load_zip_centroids()

    print(f"Fetching CMS hospitals …")
    csv_text = fetch_bytes(CMS_HOSPITAL_CSV).decode("utf-8", errors="replace")
    rows = list(csv.DictReader(csv_text.splitlines()))

    hospitals = []
    skipped_type = 0
    for row in rows:
        htype = (row.get("Hospital Type") or "").strip()
        if htype not in allowed:
            skipped_type += 1
            continue
        h = normalize_hospital(row, zips)
        if h:
            hospitals.append(h)

    hospitals.sort(key=lambda h: (h["state"], h["name"]))

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "hospitals.json").write_text(
        json.dumps(hospitals, separators=(",", ":")),
        encoding="utf-8",
    )
    (OUT / "zip-centroids.json").write_text(
        json.dumps(zips, separators=(",", ":")),
        encoding="utf-8",
    )
    meta = {
        "hospitalCount": len(hospitals),
        "zipCount": len(zips),
        "cmsSource": CMS_HOSPITAL_CSV,
        "hospitalTypes": sorted(allowed),
        "skippedByType": skipped_type,
        "builtAt": date.today().isoformat(),
        "priceNote": "Procedure prices require MRF/Turquoise ingestion; quality data from CMS.",
    }
    (OUT / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    h_size = (OUT / "hospitals.json").stat().st_size / 1_048_576
    z_size = (OUT / "zip-centroids.json").stat().st_size / 1_048_576
    print(f"Wrote {len(hospitals):,} hospitals ({h_size:.1f} MB)")
    print(f"Wrote {len(zips):,} ZIP centroids ({z_size:.1f} MB)")
    print(f"Output: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())