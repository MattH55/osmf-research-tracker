#!/usr/bin/env python3
"""
Build full U.S. hospital dataset from CMS + Census geography.

Outputs:
  data/cms/hospitals.json      — all CMS hospitals (~5,400)
  data/cms/zip-centroids.json  — U.S. ZCTA internal points (Census Gazetteer, ~33,800)
  data/cms/meta.json           — vintage, counts, sources

USAGE:
  python etl/build_dataset.py
  python etl/build_dataset.py --types acute,critical  # filter hospital types
  python etl/build_dataset.py --regeocode             # re-place existing hospitals only

Locations: ZIP points are Census Gazetteer ZCTA internal points (PO-box-only ZIPs have no
ZCTA and are reported as unknown, never guessed). Hospitals are geocoded from their CMS
street address with the Census batch geocoder, falling back to the ZCTA point; the method
is recorded per hospital in `geocodeSource`.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import time
import uuid
import zipfile
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cms"

CMS_HOSPITAL_CSV = (
    "https://data.cms.gov/provider-data/api/1/datastore/query/"
    "xubh-q36u/0/download?format=csv"
)
CMS_HOSPITAL_METADATA = (
    "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/xubh-q36u"
)
# U.S. Census Bureau Gazetteer: ZCTA internal points (official)
GAZETTEER_ZCTA_ZIP = (
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/"
    "2024_Gazetteer/2024_Gaz_zcta_national.zip"
)
CENSUS_BATCH_GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
GEOCODE_BATCH = 2000

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
    """Census Gazetteer ZCTA internal points. No fallback: a failed download fails the build."""
    print("Downloading Census Gazetteer ZCTA file …")
    raw = fetch_bytes(GAZETTEER_ZCTA_ZIP)
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        text = zf.read(name).decode("utf-8", errors="replace")
    # Place names for display only (the Gazetteer has none); coordinates never come from here.
    names: dict[str, dict] = {}
    prev = OUT / "zip-centroids.json"
    if prev.exists():
        for z, v in json.loads(prev.read_text(encoding="utf-8")).items():
            names[z] = {"city": v.get("city", ""), "state": v.get("state", "")}
    out: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        zcta = row.get("GEOID", "")
        lat, lng = parse_float(row.get("INTPTLAT", "")), parse_float(row.get("INTPTLONG", ""))
        if len(zcta) != 5 or lat is None or lng is None:
            continue
        out[zcta] = {"lat": lat, "lng": lng, **names.get(zcta, {"city": "", "state": ""})}
    print(f"  {len(out):,} ZCTA points loaded")
    if len(out) < 30000:
        raise SystemExit(f"Gazetteer looks truncated ({len(out)} ZCTAs); refusing to write.")
    return dict(sorted(out.items()))


def cms_release_date() -> str:
    """CMS 'modified' date for the Hospital General Information dataset (the real vintage)."""
    meta = json.loads(fetch_bytes(CMS_HOSPITAL_METADATA, timeout=60))
    return str(meta.get("modified") or meta.get("released"))[:10]


def _census_batch(rows: list[tuple[str, ...]]) -> dict[str, tuple[float, float, str]]:
    """POST one batch to the Census geocoder. Returns id -> (lat, lng, match quality)."""
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"benchmark\"\r\n\r\nPublic_AR_Current\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"addressFile\"; filename=\"a.csv\"\r\n"
        f"Content-Type: text/csv\r\n\r\n{buf.getvalue()}\r\n--{boundary}--\r\n"
    ).encode("utf-8")
    req = Request(CENSUS_BATCH_GEOCODER, data=body,
                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urlopen(req, timeout=900) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    out = {}
    for rec in csv.reader(text.splitlines()):
        # id, input, Match/No_Match/Tie, Exact/Non_Exact, matched address, "lon,lat", tiger id, side
        if len(rec) >= 6 and rec[2] == "Match" and "," in rec[5]:
            lon, lat = (float(x) for x in rec[5].split(","))
            out[rec[0]] = (round(lat, 6), round(lon, 6), rec[3].lower())
    return out


def geocode_hospitals(hospitals: list[dict], zips: dict[str, dict]) -> dict[str, int]:
    """Address-level coordinates from the Census geocoder; ZCTA point as a recorded fallback."""
    rows = [(h["cmsProviderId"], h.get("address", ""), h.get("city", ""), h.get("state", ""), h.get("zip", ""))
            for h in hospitals]
    matched: dict[str, tuple[float, float, str]] = {}
    for i in range(0, len(rows), GEOCODE_BATCH):
        for attempt in range(3):
            try:
                matched.update(_census_batch(rows[i:i + GEOCODE_BATCH]))
                break
            except Exception as exc:  # transient Census outages
                print(f"  geocoder batch {i // GEOCODE_BATCH + 1} failed ({exc}); retry {attempt + 1}")
                time.sleep(10 * (attempt + 1))
        print(f"  geocoded {min(i + GEOCODE_BATCH, len(rows))}/{len(rows)} (matched so far {len(matched)})")
    counts = {"census_address": 0, "zcta_point": 0, "none": 0}
    for h in hospitals:
        m = matched.get(h["cmsProviderId"])
        z = zips.get(h.get("zip", ""))
        if m:
            h["latitude"], h["longitude"] = m[0], m[1]
            h["geocodeSource"] = f"census_address_{m[2]}"
            counts["census_address"] += 1
        elif z:
            h["latitude"], h["longitude"] = z["lat"], z["lng"]
            h["geocodeSource"] = "zcta_point"
            counts["zcta_point"] += 1
        else:
            h["latitude"], h["longitude"] = None, None
            h["geocodeSource"] = "none"
            counts["none"] += 1
    return counts


def normalize_hospital(row: dict, vintage: str) -> dict | None:
    provider_id = (row.get("Facility ID") or "").strip()
    name = (row.get("Facility Name") or "").strip()
    if not provider_id or not name:
        return None

    zip_code = (row.get("ZIP Code") or "").replace(" ", "")[:5].zfill(5)

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
        "latitude": None,  # set by geocode_hospitals()
        "longitude": None,
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
        "dataVintage": vintage,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--types",
        default="all",
        help="Comma-separated: acute,critical,children,rural_er,va,dod,psych,longterm or 'all'",
    )
    ap.add_argument("--regeocode", action="store_true",
                    help="Only rebuild ZIP points and hospital coordinates for the existing hospitals.json")
    args = ap.parse_args()

    if args.regeocode:
        zips = load_zip_centroids()
        hospitals = json.loads((OUT / "hospitals.json").read_text(encoding="utf-8"))
        counts = geocode_hospitals(hospitals, zips)
        (OUT / "hospitals.json").write_text(json.dumps(hospitals, separators=(",", ":")), encoding="utf-8")
        (OUT / "zip-centroids.json").write_text(json.dumps(zips, separators=(",", ":")), encoding="utf-8")
        meta = json.loads((OUT / "meta.json").read_text(encoding="utf-8"))
        meta.update({"zipCount": len(zips), "zipSource": GAZETTEER_ZCTA_ZIP,
                     "geocoder": CENSUS_BATCH_GEOCODER, "geocodeCounts": counts,
                     "geocodedAt": date.today().isoformat()})
        (OUT / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"Re-geocoded {len(hospitals):,} hospitals: {counts}")
        return 0

    if args.types == "all":
        allowed = INCLUDE_ALL_TYPES
    else:
        keys = [k.strip() for k in args.types.split(",")]
        allowed = {TYPE_FILTER_DEFAULT[k] for k in keys if k in TYPE_FILTER_DEFAULT}

    zips = load_zip_centroids()
    vintage = cms_release_date()

    print(f"Fetching CMS hospitals (release {vintage}) …")
    csv_text = fetch_bytes(CMS_HOSPITAL_CSV).decode("utf-8", errors="replace")
    rows = list(csv.DictReader(csv_text.splitlines()))

    hospitals = []
    skipped_type = 0
    for row in rows:
        htype = (row.get("Hospital Type") or "").strip()
        if htype not in allowed:
            skipped_type += 1
            continue
        h = normalize_hospital(row, vintage)
        if h:
            hospitals.append(h)

    hospitals.sort(key=lambda h: (h["state"], h["name"], h["cmsProviderId"]))
    counts = geocode_hospitals(hospitals, zips)

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
        "cmsReleaseDate": vintage,
        "zipSource": GAZETTEER_ZCTA_ZIP,
        "geocoder": CENSUS_BATCH_GEOCODER,
        "geocodeCounts": counts,
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