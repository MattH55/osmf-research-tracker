#!/usr/bin/env python3
"""
Migrate existing US MRF prices to the new price observation store format.

Converts trilliant-prices.json and mrf-prices.json into data/observations/
as newline-delimited JSON files.

USAGE:
  python etl/migrate_to_observation_store.py
  python etl/migrate_to_observation_store.py --source trilliant
  python etl/migrate_to_observation_store.py --source direct
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CMS_DIR = DATA_DIR / "cms"
OBS_DIR = DATA_DIR / "observations"

TRILLIANT_PRICES = CMS_DIR / "trilliant-prices.json"
MRF_PRICES = CMS_DIR / "mrf-prices.json"
HOSPITALS_JSON = CMS_DIR / "hospitals.json"


def map_price_type_from_legacy(legacy_price: dict) -> str:
    """Map legacy price fields to canonical price_type."""
    source = legacy_price.get("priceSource", "")
    if "cash" in str(legacy_price.get("cashLow", "")).lower() or legacy_price.get("cashMedian"):
        return "discounted_cash"
    if legacy_price.get("negotiatedMedian"):
        return "negotiated"
    return "unknown"


def legacy_trilliant_to_observation(row: dict, hospitals_lookup: dict, source: str = "trilliant") -> dict:
    """Convert a legacy Trilliant price row to a price observation."""
    cms_id = row.get("cmsProviderId")
    facility_id = f"hosp-cms-{cms_id}" if cms_id else row.get("hospitalId")

    # Always facility-only (professional fees not included in hospital MRFs)
    bundle_includes = ["facility_fee"]

    obs_date = row.get("priceVintage")
    if not obs_date or obs_date == "":
        obs_date = date.today().isoformat()

    return {
        "observation_id": str(uuid.uuid4()),
        "facility_id": facility_id,
        "procedure_slug": map_procedure_id_to_slug(row.get("procedureId", "")),
        "price_type": "discounted_cash",
        "amount_native": float(row.get("cashMedian") or 0),
        "currency": "USD",
        "fx_rate_to_usd": 1.0,
        "fx_rate_date": obs_date,
        "amount_usd": float(row.get("cashMedian") or 0),
        "bundle": {
            "includes": bundle_includes,
            "inpatient_nights": None,
            "physio_sessions": None,
            "device_brand": None,
            "explicitly_excludes": ["surgeon_fee", "anesthesia"],
            "completeness_score": 0.45,
        },
        "is_advertised_minimum": False,
        "is_estimate": False,
        "stale": False,
        "provenance": {
            "source_type": "mrf",
            "source_url": row.get("mrfUrl", ""),
            "source_document_hash": None,
            "retrieved_at": obs_date + "T00:00:00Z",
            "extracted_by": f"adapter:{source}_v1",
            "confidence": 0.9,
        },
        "observation_date": obs_date,
        "notes": f"Migrated from {source.title()}. Facility: {row.get('trilliantFacility', row.get('hospitalId'))}",
    }


def map_procedure_id_to_slug(proc_id: str) -> str:
    """Map legacy procedure ID to new slug."""
    mapping = {
        "proc-knee-replacement": "tka",
        "proc-hip-replacement": "tha",
        "proc-cataract-surgery": "cataract",
        "proc-shoulder-replacement": "shoulder",
        # Add more as needed
    }
    return mapping.get(proc_id, proc_id.replace("proc-", ""))


def migrate_trilliant(hospitals_lookup: dict) -> int:
    """Migrate Trilliant prices to observation store."""
    if not TRILLIANT_PRICES.exists():
        print(f"File not found: {TRILLIANT_PRICES}")
        return 1

    print(f"Loading {TRILLIANT_PRICES}…")
    prices = json.loads(TRILLIANT_PRICES.read_text(encoding="utf-8"))

    OBS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OBS_DIR / "us-mrf-trilliant.jsonl"

    written = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for i, price in enumerate(prices):
            if i % 1000 == 0:
                print(f"  [{i}/{len(prices)}] Converting…")
            obs = legacy_trilliant_to_observation(price, hospitals_lookup)
            out.write(json.dumps(obs) + "\n")
            written += 1

    print(f"Wrote {written} observations to {out_path}")
    return 0


def migrate_direct_mrf(hospitals_lookup: dict) -> int:
    """Migrate direct MRF scrape prices to observation store."""
    if not MRF_PRICES.exists():
        print(f"File not found: {MRF_PRICES} (skipping)")
        return 0

    print(f"Loading {MRF_PRICES}…")
    prices = json.loads(MRF_PRICES.read_text(encoding="utf-8"))

    OBS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OBS_DIR / "us-mrf-direct.jsonl"

    written = 0
    with open(out_path, "w", encoding="utf-8") as out:
        for i, price in enumerate(prices):
            if i % 100 == 0:
                print(f"  [{i}/{len(prices)}] Converting…")
            obs = legacy_trilliant_to_observation(price, hospitals_lookup, source="direct_hospital_mrf")
            out.write(json.dumps(obs) + "\n")
            written += 1

    print(f"Wrote {written} observations to {out_path}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate legacy MRF prices to observation store")
    ap.add_argument(
        "--source",
        choices=["all", "trilliant", "direct"],
        default="all",
        help="Which source to migrate",
    )
    args = ap.parse_args()

    # Load hospitals for reference
    if not HOSPITALS_JSON.exists():
        print(f"Warning: {HOSPITALS_JSON} not found; FK validation will be limited")
        hospitals_lookup = {}
    else:
        hospitals_lookup = {h.get("cmsProviderId"): h for h in json.loads(HOSPITALS_JSON.read_text())}

    if args.source in ("all", "trilliant"):
        rc = migrate_trilliant(hospitals_lookup)
        if rc != 0:
            return rc

    if args.source in ("all", "direct"):
        rc = migrate_direct_mrf(hospitals_lookup)
        if rc != 0:
            return rc

    print(f"\nMigration complete. Data ready at {OBS_DIR}/")
    print(f"Validate with: python etl/priceos_validate.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
