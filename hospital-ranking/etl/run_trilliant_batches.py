#!/usr/bin/env python3
"""
Run Trilliant ORIA ingest in resumable batches until the full index is processed.

ORIA has ~7,600 completed hospitals. Each batch downloads parsed DuckDB files,
extracts our 24 procedure codes, and appends to trilliant-prices.json.

USAGE:
  python etl/run_trilliant_batches.py --batch-size 250 --workers 6
  python etl/run_trilliant_batches.py --batch-size 500 --start-offset 500 --max-batches 3
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INGEST = ROOT / "etl" / "ingest_trilliant.py"
META = ROOT / "data" / "cms" / "trilliant-meta.json"
ORIA_INDEX_URL = "https://oria-data.trillianthealth.com/search-index.json"


def index_size() -> int:
    import urllib.request

    req = urllib.request.Request(
        ORIA_INDEX_URL,
        headers={"User-Agent": "OpenSourceMed-HospitalCompare/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.load(resp)
    return len(data)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=250)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--start-offset", type=int, default=0)
    ap.add_argument("--max-batches", type=int, default=0, help="0 = run until index exhausted")
    args = ap.parse_args()

    total = index_size()
    offset = args.start_offset
    batch_num = 0

    print(f"ORIA index: {total} hospitals. Batch size {args.batch_size}.")

    while offset < total:
        if args.max_batches and batch_num >= args.max_batches:
            print(f"Stopped after {batch_num} batch(es) (--max-batches).")
            break

        batch_num += 1
        print(f"\n=== Batch {batch_num}: offset={offset} limit={args.batch_size} ===")
        cmd = [
            sys.executable,
            str(INGEST),
            "--oria",
            "--append",
            f"--offset={offset}",
            f"--limit={args.batch_size}",
            f"--workers={args.workers}",
        ]
        rc = subprocess.call(cmd)
        if rc != 0:
            print(f"Batch failed (exit {rc}) at offset {offset}", file=sys.stderr)
            return rc

        if META.exists():
            meta = json.loads(META.read_text(encoding="utf-8"))
            print(
                f"Running total: {meta.get('priceCount')} prices, "
                f"{meta.get('cmsHospitalsWithPrices')} CMS hospitals"
            )

        offset += args.batch_size

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())