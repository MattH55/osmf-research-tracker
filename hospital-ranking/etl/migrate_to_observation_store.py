#!/usr/bin/env python3
"""
Convert the published US MRF price rows into the price observation store.

  data/cms/trilliant-prices.json -> data/observations/us-mrf-trilliant.jsonl
  data/cms/mrf-prices.json       -> data/observations/us-mrf-direct.jsonl

One observation per published amount: a "discounted_cash" observation when the
row has a cash median, and a "negotiated" observation when it has a negotiated
median. Gross charges are not turned into observations (a list price is not a
price anyone is quoted). Rows that break the price contract are not migrated.

Every observation carries procedure_id, scope, match_type, matched_codes, the
source hash, the source date (never the build date) and the row's stale flag.
IDs are deterministic (UUIDv5 of source + facility + procedure + price type) and
output is sorted, so re-running on the same input gives byte-identical files.

USAGE:
  python etl/migrate_to_observation_store.py [--source all|trilliant|direct]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from price_contract import (  # noqa: E402
    CMS_DIR,
    ROOT,
    CodeIndex,
    atomic_write_text,
    contract_problems,
    deterministic_uuid,
    load_hospitals,
    read_json,
)

OBS_DIR = ROOT / "data" / "observations"
TRILLIANT_PRICES = CMS_DIR / "trilliant-prices.json"
MRF_PRICES = CMS_DIR / "mrf-prices.json"

# proc id -> observation slug (kept for docs/data file names used by docs/browse.html)
PROC_ID_ALIASES = {
    "proc-knee-replacement": "tka",
    "proc-hip-replacement": "tha",
    "proc-cataract-surgery": "cataract",
    "proc-shoulder-replacement": "shoulder",
}


def procedure_slug(proc_id: str) -> str:
    return PROC_ID_ALIASES.get(proc_id, proc_id.replace("proc-", ""))


def row_to_observations(row: dict, adapter: str) -> list[dict]:
    source_url = row.get("mrfUrl") or row.get("sourceDataset")
    vintage = row["priceVintage"]
    retrieved = row.get("sourceRetrievedAt") or f"{vintage}T00:00:00Z"
    scope = row["scope"]
    includes = ["facility_fee"] + (["inpatient_nights"] if scope == "inpatient_stay" else [])
    out: list[dict] = []
    for price_type, med, low, high in (
        ("discounted_cash", row.get("cashMedian"), row.get("cashLow"), row.get("cashHigh")),
        ("negotiated", row.get("negotiatedMedian"), row.get("negotiatedLow"), row.get("negotiatedHigh")),
    ):
        if med is None:
            continue
        obs = {
            "observation_id": deterministic_uuid(row.get("sourceDataset") or source_url, row["hospitalId"],
                                                 row["procedureId"], price_type),
            "facility_id": row["hospitalId"],
            "procedure_id": row["procedureId"],
            "procedure_slug": procedure_slug(row["procedureId"]),
            "price_type": price_type,
            "amount_native": float(med),
            "amount_low": float(low) if low is not None else None,
            "amount_high": float(high) if high is not None else None,
            "currency": "USD",
            "fx_rate_to_usd": 1.0,
            "fx_rate_date": vintage,
            "amount_usd": float(med),
            "scope": scope,
            "match_type": row["matchType"],
            "matched_codes": row["matchedCodes"],
            "payer_count": row.get("payerCount") if price_type == "negotiated" else None,
            "bundle": {
                "includes": includes,
                "inpatient_nights": None,
                "physio_sessions": None,
                "device_brand": None,
                "explicitly_excludes": ["surgeon_fee", "anesthesia"],
                "completeness_score": 0.45,
            },
            "is_advertised_minimum": False,
            "is_estimate": False,
            "stale": bool(row.get("stale")),
            "provenance": {
                "source_type": "mrf",
                "source_url": source_url,
                "source_document_hash": row.get("sourceDocumentHash"),
                "source_dataset": row.get("sourceDataset"),
                "retrieved_at": retrieved,
                "extracted_by": f"adapter:{adapter}",
                "confidence": 0.9,
            },
            "observation_date": vintage,
            "price_row_id": row.get("id"),
            "notes": f"Facility: {row.get('sourceFacilityName') or row['hospitalId']}",
        }
        out.append(obs)
    return out


def migrate(src: Path, dest: Path, adapter: str, codes: CodeIndex, hospitals_by_id: dict) -> int:
    rows = read_json(src, []) or []
    obs: list[dict] = []
    skipped = 0
    for r in rows:
        if contract_problems(r, codes, hospitals_by_id):
            skipped += 1
            continue
        obs.extend(row_to_observations(r, adapter))
    obs.sort(key=lambda o: (o["facility_id"], o["procedure_id"], o["price_type"]))
    OBS_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(dest, "".join(json.dumps(o, ensure_ascii=False) + "\n" for o in obs))
    print(f"{src.name}: {len(rows)} rows -> {len(obs)} observations ({skipped} rows failed the contract) -> {dest}")
    return 1 if skipped else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Convert MRF price rows to observation store")
    ap.add_argument("--source", choices=["all", "trilliant", "direct"], default="all")
    args = ap.parse_args()
    codes = CodeIndex()
    hospitals_by_id = {h["id"]: h for h in load_hospitals()}
    rc = 0
    if args.source in ("all", "trilliant"):
        rc |= migrate(TRILLIANT_PRICES, OBS_DIR / "us-mrf-trilliant.jsonl", "trilliant_oria_v2", codes, hospitals_by_id)
    if args.source in ("all", "direct"):
        rc |= migrate(MRF_PRICES, OBS_DIR / "us-mrf-direct.jsonl", "direct_hospital_mrf_v2", codes, hospitals_by_id)
    print("Validate with: python etl/priceos_validate.py --strict")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
