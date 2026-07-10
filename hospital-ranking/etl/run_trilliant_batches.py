#!/usr/bin/env python3
"""
Run Trilliant ORIA ingest in resumable batches until the full index is processed.

ORIA has ~7,600 completed hospitals. Each batch downloads parsed DuckDB files,
extracts our 24 procedure codes, and appends to trilliant-prices.json.

USAGE:
  python etl/run_trilliant_batches.py --batch-size 250 --workers 4
  python etl/run_trilliant_batches.py --resume
  python etl/run_trilliant_batches.py --batch-size 250 --start-offset 1150 --max-batches 5
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INGEST = ROOT / "etl" / "ingest_trilliant.py"
META = ROOT / "data" / "cms" / "trilliant-meta.json"
PROGRESS = ROOT / "data" / "cms" / "trilliant-progress.json"
INDEX_CACHE = ROOT / "data" / "trilliant" / "oria-search-index.json"
ORIA_INDEX_URL = "https://oria-data.trillianthealth.com/search-index.json"


def index_size() -> int:
    if INDEX_CACHE.exists():
        return len(json.loads(INDEX_CACHE.read_text(encoding="utf-8")))
    import urllib.request

    req = urllib.request.Request(
        ORIA_INDEX_URL,
        headers={"User-Agent": "OpenSourceMed-HospitalCompare/1.0"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.load(resp)
    INDEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
    INDEX_CACHE.write_text(json.dumps(data), encoding="utf-8")
    return len(data)


def read_progress() -> dict | None:
    if not PROGRESS.exists():
        return None
    try:
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def run_batch(offset: int, batch_size: int, workers: int, retries: int) -> int:
    cmd = [
        sys.executable,
        str(INGEST),
        "--oria",
        "--append",
        "--force",
        f"--offset={offset}",
        f"--limit={batch_size}",
        f"--workers={workers}",
    ]
    for attempt in range(1, retries + 1):
        rc = subprocess.call(cmd)
        if rc == 0:
            return 0
        if attempt < retries:
            wait = 10 * attempt
            print(
                f"Batch at offset {offset} failed (exit {rc}). "
                f"Retry {attempt}/{retries - 1} in {wait}s…",
                file=sys.stderr,
            )
            time.sleep(wait)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=250)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--start-offset", type=int, default=-1, help="-1 = use progress file")
    ap.add_argument("--max-batches", type=int, default=0, help="0 = run until index exhausted")
    ap.add_argument(
        "--resume",
        action="store_true",
        help="Start at nextOffset from data/cms/trilliant-progress.json",
    )
    ap.add_argument("--retries", type=int, default=3, help="Retries per batch on network errors")
    args = ap.parse_args()

    progress = read_progress()
    if args.resume or args.start_offset < 0:
        if progress and progress.get("nextOffset") is not None:
            offset = int(progress["nextOffset"])
            print(f"Resuming from progress file: offset {offset}")
            if progress.get("priceCount"):
                print(
                    f"  Current totals: {progress['priceCount']} prices, "
                    f"{progress.get('cmsHospitalsWithPrices')} CMS hospitals"
                )
        else:
            offset = 0
            print("No progress file found — starting at offset 0")
    else:
        offset = args.start_offset

    total = index_size()
    batch_num = 0

    print(f"ORIA index: {total} hospitals. Batch size {args.batch_size}.")
    print(f"Remaining: ~{max(total - offset, 0)} index entries from offset {offset}")

    while offset < total:
        if args.max_batches and batch_num >= args.max_batches:
            print(f"Stopped after {batch_num} batch(es) (--max-batches).")
            break

        batch_num += 1
        print(f"\n=== Batch {batch_num}: offset={offset} limit={args.batch_size} ===")
        rc = run_batch(offset, args.batch_size, args.workers, args.retries)
        if rc != 0:
            print(
                f"\nBatch failed at offset {offset}. Resume with:\n"
                f"  python etl/run_trilliant_batches.py --resume\n"
                f"or:\n"
                f"  python etl/run_trilliant_batches.py --start-offset {offset} "
                f"--batch-size {args.batch_size} --workers {args.workers}",
                file=sys.stderr,
            )
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