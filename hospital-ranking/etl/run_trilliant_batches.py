#!/usr/bin/env python3
"""
Run Trilliant ORIA ingest in resumable batches until the full index is processed.

Each batch downloads per-hospital parsed DuckDB files (at most 4 at a time),
saves a compact extract per hospital under data/trilliant/extracts, deletes the
DuckDB file, and merges the batch's rows into trilliant-prices.json. Progress is
checkpointed in data/cms/trilliant-progress.json after every batch:
  * nextOffset    first index entry not yet attempted (advances only from what
                  the ingest recorded, never by assumption);
  * failedSlugs   entries that failed (network, disk_low, read error) with the
                  reason, retried in the retry passes at the end.

Free disk is checked before every batch (and before every download inside a
batch); below --min-free-gb (default 40) the run stops cleanly and can resume.

After the run, `python etl/ingest_trilliant.py --rescan-cache` rebuilds every
output from the extracts in one deterministic pass.

USAGE:
  python etl/run_trilliant_batches.py --reset-progress --batch-size 250 --workers 4
  python etl/run_trilliant_batches.py --resume
  python etl/run_trilliant_batches.py --retry-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INGEST = ROOT / "etl" / "ingest_trilliant.py"
META = ROOT / "data" / "cms" / "trilliant-meta.json"
PROGRESS = ROOT / "data" / "cms" / "trilliant-progress.json"
INDEX_CACHE = ROOT / "data" / "trilliant" / "oria-search-index.json"
ORIA_INDEX_URL = "https://oria-data.trillianthealth.com/search-index.json"
INDEX_MAX_AGE_DAYS = 7
MAX_WORKERS = 4
EXIT_DISK_LOW = 3

sys.path.insert(0, str(ROOT / "etl"))
from price_contract import atomic_write_text, dump_json  # noqa: E402


def free_gb() -> float:
    return shutil.disk_usage(str(ROOT)).free / 1024 ** 3


def index_age_days() -> float | None:
    if not INDEX_CACHE.exists():
        return None
    return (time.time() - INDEX_CACHE.stat().st_mtime) / 86400


def refresh_index() -> None:
    import urllib.request

    print("Refreshing ORIA search index…", flush=True)
    req = urllib.request.Request(ORIA_INDEX_URL, headers={"User-Agent": "OpenSourceMed-HospitalCompare/1.0"})
    last = None
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                text = resp.read().decode("utf-8")
            json.loads(text)
            atomic_write_text(INDEX_CACHE, text)
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(5 * 2 ** attempt)
    raise RuntimeError(f"could not refresh ORIA index: {last}")


def load_index() -> list[dict]:
    if not INDEX_CACHE.exists():
        refresh_index()
    return json.loads(INDEX_CACHE.read_text(encoding="utf-8"))


def order_hash(index: list[dict]) -> str:
    # Same as ingest_trilliant.index_order_hash
    return hashlib.sha256("\n".join(e.get("id", "") for e in index).encode("utf-8")).hexdigest()[:24]


def read_progress() -> dict | None:
    if not PROGRESS.exists():
        return None
    try:
        return json.loads(PROGRESS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def reset_progress() -> None:
    """Back up the old progress file and start this run from offset 0."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = None
    if PROGRESS.exists():
        backup = PROGRESS.with_name(f"trilliant-progress-backup-{stamp}.json")
        shutil.copy2(PROGRESS, backup)
        print(f"Backed up old progress file → {backup.name}")
    age = index_age_days()
    if age is None or age > INDEX_MAX_AGE_DAYS:
        refresh_index()
    index = load_index()
    atomic_write_text(PROGRESS, dump_json({
        "nextOffset": 0,
        "oriaIndexTotal": len(index),
        "oriaIndexOrderHash": order_hash(index),
        "failedSlugs": {},
        "notCompletedSlugs": [],
        "runStartedAt": stamp,
        "resetFrom": backup.name if backup else None,
    }))
    print(f"Progress reset: nextOffset 0 of {len(index)} index entries.")


def ingest_cmd(workers: int, min_free_gb: float, extra: list[str]) -> list[str]:
    return [sys.executable, str(INGEST), "--oria", "--append", "--force",
            f"--workers={workers}", f"--min-free-gb={min_free_gb}", *extra]


def run_with_retries(cmd: list[str], retries: int, label: str) -> int:
    rc = 1
    for attempt in range(1, retries + 1):
        rc = subprocess.call(cmd)
        if rc in (0, EXIT_DISK_LOW):
            return rc
        if attempt < retries:
            wait = 15 * 2 ** (attempt - 1)
            print(f"{label} failed (exit {rc}). Retry {attempt}/{retries - 1} in {wait}s…",
                  file=sys.stderr, flush=True)
            time.sleep(wait)
    return rc


def print_totals() -> None:
    if META.exists():
        meta = json.loads(META.read_text(encoding="utf-8"))
        print(f"Running total: {meta.get('priceCount')} prices, "
              f"{meta.get('cmsHospitalsWithPrices')} CMS hospitals", flush=True)


def retry_pass(args, rounds: int) -> int:
    for rnd in range(1, rounds + 1):
        prog = read_progress() or {}
        failed = prog.get("failedSlugs") or {}
        if not failed:
            print("No failed slugs to retry.")
            return 0
        if free_gb() < args.min_free_gb:
            print(f"Free disk {free_gb():.1f} GB < {args.min_free_gb} GB: not retrying.", file=sys.stderr)
            return EXIT_DISK_LOW
        print(f"\n=== Retry round {rnd}: {len(failed)} failed slug(s) | free {free_gb():.1f} GB ===",
              flush=True)
        rc = run_with_retries(ingest_cmd(args.workers, args.min_free_gb, ["--retry-failed"]),
                              args.retries, f"Retry round {rnd}")
        print_totals()
        if rc != 0:
            return rc
        time.sleep(30 * rnd)
    left = (read_progress() or {}).get("failedSlugs") or {}
    if left:
        print(f"{len(left)} slug(s) still failing after {rounds} retry round(s); see failedSlugs.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=250)
    ap.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"concurrent downloads (max {MAX_WORKERS})")
    ap.add_argument("--start-offset", type=int, default=-1, help="-1 = use progress file")
    ap.add_argument("--max-batches", type=int, default=0, help="0 = run until index exhausted")
    ap.add_argument("--resume", action="store_true", help="Start at nextOffset from the progress file")
    ap.add_argument("--reset-progress", action="store_true",
                    help="Back up the progress file and start a new run at offset 0")
    ap.add_argument("--retries", type=int, default=3, help="Re-runs of a batch whose process crashed")
    ap.add_argument("--retry-rounds", type=int, default=2, help="Retry passes over failedSlugs at the end")
    ap.add_argument("--retry-only", action="store_true", help="Only run the failedSlugs retry passes")
    ap.add_argument("--min-free-gb", type=float, default=40.0)
    args = ap.parse_args()
    args.workers = max(1, min(args.workers, MAX_WORKERS))

    if args.reset_progress:
        reset_progress()
    if args.retry_only:
        return retry_pass(args, args.retry_rounds)

    progress = read_progress()
    extra_offset_flags: list[str] = []
    if args.start_offset >= 0 and not args.resume:
        offset = args.start_offset
        extra_offset_flags = ["--force-offset"]
    elif progress and progress.get("nextOffset") is not None:
        offset = int(progress["nextOffset"])
        print(f"Resuming from progress file: offset {offset}")
    else:
        offset = 0
        print("No progress file found — starting at offset 0")

    age = index_age_days()
    if age is not None and age > INDEX_MAX_AGE_DAYS:
        print(f"Note: ORIA index is {age:.0f} days old. It is not refreshed mid-run because offsets "
              f"depend on its order; use --reset-progress to start over on a fresh index.")
    index = load_index()
    total = len(index)
    if progress and progress.get("oriaIndexOrderHash") and progress["oriaIndexOrderHash"] != order_hash(index):
        print("ORIA index order differs from the one this run started with; refusing to resume "
              "(offsets would skip or repeat). Use --reset-progress.", file=sys.stderr)
        return 1

    print(f"ORIA index: {total} hospitals. Batch size {args.batch_size}. Workers {args.workers}. "
          f"Min free disk {args.min_free_gb} GB.")
    print(f"Remaining: ~{max(total - offset, 0)} index entries from offset {offset}", flush=True)

    batch_num = 0
    while offset < total:
        if args.max_batches and batch_num >= args.max_batches:
            print(f"Stopped after {batch_num} batch(es) (--max-batches).")
            return 0
        fg = free_gb()
        if fg < args.min_free_gb:
            print(f"\nFree disk {fg:.1f} GB < {args.min_free_gb} GB: stopping cleanly at offset {offset}. "
                  f"Free space, then resume with --resume.", file=sys.stderr)
            return EXIT_DISK_LOW
        batch_num += 1
        print(f"\n=== Batch {batch_num}: offset={offset} limit={args.batch_size} | free {fg:.1f} GB "
              f"| {time.strftime('%H:%M:%S')} ===", flush=True)
        cmd = ingest_cmd(args.workers, args.min_free_gb,
                         [f"--offset={offset}", f"--limit={args.batch_size}", *extra_offset_flags])
        rc = run_with_retries(cmd, args.retries, f"Batch at offset {offset}")
        extra_offset_flags = []
        if rc == EXIT_DISK_LOW:
            print(f"Disk under {args.min_free_gb} GB before batch start; stopping cleanly.", file=sys.stderr)
            return rc
        if rc != 0:
            print(f"\nBatch failed at offset {offset}. Resume with:\n"
                  f"  python etl/run_trilliant_batches.py --resume", file=sys.stderr)
            return rc
        print_totals()

        # Advance from what the batch actually recorded, never by assumption.
        progress = read_progress() or {}
        next_offset = progress.get("nextOffset")
        if next_offset is None or int(next_offset) <= offset:
            print(f"Progress file did not advance past offset {offset}; stopping.", file=sys.stderr)
            return 1
        failed = progress.get("failedSlugs") or {}
        if failed:
            print(f"  {len(failed)} index entries awaiting retry (failedSlugs)")
        if (progress.get("lastBatch") or {}).get("diskLowStop"):
            print("Disk guard tripped during the batch; stopping cleanly. Resume with --resume.",
                  file=sys.stderr)
            return EXIT_DISK_LOW
        offset = int(next_offset)

    print("\nIndex exhausted; retrying failed entries.")
    return retry_pass(args, args.retry_rounds)


if __name__ == "__main__":
    raise SystemExit(main())
