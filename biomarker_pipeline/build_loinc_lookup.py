#!/usr/bin/env python3
"""Seed loinc_lookup.json by extracting name -> {loinc, testType} pairs already
curated across the 5 existing atlas JSONs in data/biomarkers/*.json.

No network calls — this is a one-time local extraction so export_atlas_schema.py
can reuse LOINC codes for markers that recur across conditions (e.g. IL-6, CRP)
without re-curating them by hand for every new disease.

Usage (from research-tracker/):
    python -m biomarker_pipeline.build_loinc_lookup
"""
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data" / "biomarkers"
OUT_PATH = Path(__file__).parent / "loinc_lookup.json"

ATLAS_FILES = ["pacvs.json", "long-covid.json", "me-cfs.json", "lyme.json", "gulf-war-illness.json"]


def _keys_for(marker: dict) -> set[str]:
    keys = set()
    name = (marker.get("name") or "").strip().lower()
    alt = (marker.get("alternateName") or "").strip().lower()
    if name:
        keys.add(name)
    # Also index the parenthesized abbreviation, e.g. "Interleukin-6 (IL-6)" -> "il-6"
    if "(" in name and name.endswith(")"):
        abbrev = name[name.rfind("(") + 1 : -1].strip().lower()
        if abbrev:
            keys.add(abbrev)
    return keys


def main() -> None:
    lookup: dict[str, dict] = {}
    total_markers = 0
    for filename in ATLAS_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for marker in data.get("markers", []):
            total_markers += 1
            loinc = marker.get("loinc")
            test_type = marker.get("testType")
            if not loinc:
                continue
            entry = {"loinc": loinc, "testType": test_type, "canonicalName": marker.get("name")}
            for key in _keys_for(marker):
                # First writer wins; conflicting LOINC codes for the same name across
                # conditions are rare but possible (assay variants) — keep the first.
                lookup.setdefault(key, entry)

    OUT_PATH.write_text(json.dumps(lookup, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Scanned {total_markers} markers across {len(ATLAS_FILES)} atlases.")
    print(f"Wrote {len(lookup)} name -> LOINC lookup entries to {OUT_PATH}")


if __name__ == "__main__":
    main()
