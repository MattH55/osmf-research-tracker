#!/usr/bin/env python3
"""
Run international facility adapters to ingest prices.

Fetches raw documents from facilities, extracts prices, writes to observation store.

USAGE:
  python etl/run_adapters.py --adapter hospital_angeles_mexico_v1
  python etl/run_adapters.py --list
  python etl/run_adapters.py --adapter hospital_angeles_mexico_v1 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OBS_DIR = DATA_DIR / "observations"

# Import adapters
from adapters import (
    HospitalAngelesMexicoV1,
    CimaCostaRicaV1,
    SamitivejThailandV1,
    ApolloIndiaV1,
    AmericanHospitalTurkeyV1,
    register_facility,
)

ADAPTER_CLASSES = {
    "hospital_angeles_mexico_v1": HospitalAngelesMexicoV1,
    "cima_costa_rica_v1": CimaCostaRicaV1,
    "samitivej_thailand_v1": SamitivejThailandV1,
    "apollo_india_v1": ApolloIndiaV1,
    "american_hospital_turkey_v1": AmericanHospitalTurkeyV1,
}


def run_adapter(adapter_name: str, dry_run: bool = False) -> int:
    """
    Run a single adapter.

    Args:
        adapter_name: Name of adapter to run
        dry_run: If True, fetch & extract but don't write to disk

    Returns:
        0 on success, 1 on error
    """
    if adapter_name not in ADAPTER_CLASSES:
        print(f"Unknown adapter: {adapter_name}", file=sys.stderr)
        return 1

    AdapterClass = ADAPTER_CLASSES[adapter_name]
    adapter = AdapterClass()

    print(f"\n{'='*60}")
    print(f"Running adapter: {adapter.facility_id}")
    print(f"Facility: {adapter.facility_name} ({adapter.country})")
    print(f"{'='*60}")

    # Register facility
    register_facility(adapter)
    print(f"Registered facility: {adapter.facility_id}")

    # Fetch
    print(f"\nFetching documents…")
    docs = adapter.fetch()
    if not docs:
        print("No documents fetched.", file=sys.stderr)
        return 1
    print(f"Fetched {len(docs)} document(s)")

    # Extract
    print(f"Extracting prices…")
    observations = adapter.extract(docs)
    if not observations:
        print("No prices extracted.", file=sys.stderr)
        return 1
    print(f"Extracted {len(observations)} price observation(s)")

    # Write to observation store
    if not dry_run:
        OBS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OBS_DIR / f"intl-{adapter.facility_id}.jsonl"

        with open(out_path, "w", encoding="utf-8") as f:
            for obs in observations:
                obs_dict = {
                    "observation_id": obs.observation_id,
                    "facility_id": obs.facility_id,
                    "procedure_slug": obs.procedure_slug,
                    "price_type": obs.price_type,
                    "amount_native": obs.amount_native,
                    "currency": obs.currency,
                    "fx_rate_to_usd": obs.fx_rate_to_usd,
                    "fx_rate_date": obs.fx_rate_date,
                    "amount_usd": obs.amount_usd,
                    "bundle": obs.bundle,
                    "is_advertised_minimum": obs.is_advertised_minimum,
                    "is_estimate": obs.is_estimate,
                    "provenance": obs.provenance,
                    "observation_date": obs.observation_date,
                    "notes": obs.notes,
                }
                f.write(json.dumps(obs_dict) + "\n")

        print(f"Wrote {len(observations)} observations to {out_path}")
    else:
        print(f"DRY RUN: Would write {len(observations)} observations")
        for obs in observations[:3]:
            print(f"  - {obs.facility_id} / {obs.procedure_slug} @ ${obs.amount_usd}")

    return 0


def list_adapters() -> int:
    """List available adapters."""
    print("Available adapters:")
    for name, cls in ADAPTER_CLASSES.items():
        adapter = cls()
        print(f"  {name}: {adapter.facility_name} ({adapter.country})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run international facility price adapters")
    ap.add_argument("--adapter", help="Adapter to run (e.g., hospital_angeles_mexico_v1)")
    ap.add_argument("--list", action="store_true", help="List available adapters")
    ap.add_argument("--dry-run", action="store_true", help="Fetch & extract but don't write to disk")
    args = ap.parse_args()

    if args.list:
        return list_adapters()

    if not args.adapter:
        ap.print_help()
        return 1

    return run_adapter(args.adapter, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
