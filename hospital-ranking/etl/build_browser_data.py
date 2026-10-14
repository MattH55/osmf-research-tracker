#!/usr/bin/env python3
"""
Build static JSON data files for the US price browser page (docs/browse.html).

Reads the observation store (data/observations/*.jsonl) and emits:
  docs/data/summary.json               per-procedure counts + price stats
  docs/data/procedures/{slug}.json     one row per hospital for that procedure

Same contract as the app (etl/price_contract.py): only prices published in
hospital MRFs; nothing modelled or estimated; no out-of-pocket figures. Each
hospital appears once per procedure with its headline figure: the published
discounted cash price when there is one, otherwise the median payer-negotiated
rate (price_type says which). Values outside the shared bounds (<= $0,
>= $500,000, sentinels, below the procedure floor) never reach the store, and
any that did would be dropped here, not shown.

USAGE:
  python etl/build_browser_data.py
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from price_contract import PRICE_CEILING, ROOT, CodeIndex, atomic_write_text, read_json, valid_amount  # noqa: E402
from migrate_to_observation_store import procedure_slug  # noqa: E402

OBS_DIR = ROOT / "data" / "observations"
OUT_DIR = ROOT / "docs" / "data"
PROC_OUT_DIR = OUT_DIR / "procedures"
HOSPITALS_JSON = ROOT / "data" / "cms" / "hospitals.json"
OBS_FILES = [OBS_DIR / "us-mrf-trilliant.jsonl", OBS_DIR / "us-mrf-direct.jsonl"]
SOURCE_PRIORITY = {"adapter:direct_hospital_mrf_v2": 0, "adapter:trilliant_oria_v2": 1}


def load_observations() -> list[dict]:
    out = []
    for path in OBS_FILES:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                out.extend(json.loads(line) for line in f if line.strip())
    return out


def main() -> int:
    codes = CodeIndex()
    hospitals = {h["id"]: h for h in read_json(HOSPITALS_JSON, []) or []}
    observations = load_observations()
    print(f"Loaded {len(observations)} observations")

    # headline per (facility, procedure): direct MRF before Trilliant; cash before negotiated
    best: dict[tuple[str, str], dict] = {}
    dropped = 0
    for o in observations:
        pid = o.get("procedure_id")
        if pid not in codes.by_id or o.get("is_estimate"):
            dropped += 1
            continue
        if valid_amount(o.get("amount_usd"), codes.floor(pid)) is None:
            dropped += 1
            continue
        rank = (SOURCE_PRIORITY.get(o["provenance"].get("extracted_by"), 9),
                0 if o["price_type"] == "discounted_cash" else 1)
        key = (o["facility_id"], pid)
        if key not in best or rank < best[key][0]:
            best[key] = (rank, o)

    by_proc: dict[str, list[dict]] = defaultdict(list)
    for (_fid, pid), (_rank, o) in best.items():
        h = hospitals.get(o["facility_id"], {})
        prov = o["provenance"]
        by_proc[pid].append({
            "facility_id": o["facility_id"],
            "facility_name": h.get("name") or o["facility_id"],
            "amount_usd": o["amount_usd"],
            "amount_low": o.get("amount_low"),
            "amount_high": o.get("amount_high"),
            "price_type": o["price_type"],
            "payer_count": o.get("payer_count"),
            "scope": o["scope"],
            "matched_codes": o["matched_codes"],
            "completeness_score": o["bundle"]["completeness_score"],
            "bundle_includes": o["bundle"]["includes"],
            "observation_date": o["observation_date"],
            "stale": o["stale"],
            "source_url": prov.get("source_url"),
            "source_dataset": prov.get("source_dataset"),
            "source_type": prov.get("source_type"),
            "zip": h.get("zip"),
            "city": h.get("city"),
            "state": h.get("state"),
            "outlier": False,
        })

    PROC_OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in PROC_OUT_DIR.glob("*.json"):
        old.unlink()

    summary = []
    for p in codes.procedures:
        pid = p["id"]
        rows = sorted(by_proc.get(pid, []), key=lambda r: (r["amount_usd"], r["facility_id"]))
        if not rows:
            continue
        slug = procedure_slug(pid)
        atomic_write_text(PROC_OUT_DIR / f"{slug}.json", json.dumps(rows, ensure_ascii=False))
        prices = [r["amount_usd"] for r in rows]
        trim_n = int(len(prices) * 0.025)
        trimmed = prices[trim_n:len(prices) - trim_n] if trim_n else prices
        summary.append({
            "slug": slug,
            "procedure_id": pid,
            "count": len(prices),
            "trimmed_count": len(trimmed),
            "total_rows": len(rows),
            "cash_rows": sum(1 for r in rows if r["price_type"] == "discounted_cash"),
            "negotiated_rows": sum(1 for r in rows if r["price_type"] == "negotiated"),
            "outliers_excluded": 0,
            "trimmed_excluded": len(prices) - len(trimmed),
            "min_usd": round(min(trimmed), 2),
            "median_usd": round(statistics.median(trimmed), 2),
            "max_usd": round(max(trimmed), 2),
            "mean_usd": round(statistics.mean(trimmed), 2),
            "with_zip": sum(1 for r in rows if r["zip"]),
            "scope": p["scope"],
            "cpt_codes": p.get("cptCodes") or [],
            "drg_codes": p.get("drgCodes") or [],
            "mixed_scope": False,
            "multi_cpt": len(p.get("cptCodes") or []) > 1,
            "code_source": p.get("codeSource"),
        })
    summary.sort(key=lambda x: (-x["count"], x["slug"]))

    out = {
        "generated_from": "data/observations/*.jsonl (prices published in hospital MRFs; Trilliant ORIA parse or direct download)",
        "total_observations": len(observations),
        "total_hospital_procedure_rows": sum(s["count"] for s in summary),
        "total_procedures": len(summary),
        "total_cms_hospitals": len(hospitals),
        "hospitals_with_prices": len({k[0] for k in best}),
        "total_outliers_excluded_from_stats": 0,
        "observations_dropped": dropped,
        "outlier_note": (
            f"Values <= $0, >= ${PRICE_CEILING:,}, sentinel values such as 999999999, and values below "
            "each procedure's plausibility floor are removed in the ETL and recorded in "
            "data/cms/quarantine.json; none are shown here."
        ),
        "trim_note": (
            "For every procedure, the bottom 2.5% and top 2.5% of prices (5% total) are excluded from "
            "the median/mean/min/max and the histogram. Trimmed rows stay in the table."
        ),
        "comparability_note": (
            "Each procedure is priced at exactly one scope from exactly one code: inpatient procedures "
            "by their MS-DRG (whole facility stay), outpatient and imaging procedures by the facility "
            "CPT/HCPCS line. Rows show the hospital's published discounted cash price where it has one, "
            "otherwise the median of its published payer-negotiated dollar rates (price_type). Physician "
            "and anesthesia fees are billed separately and are not included."
        ),
        "estimates_note": "No figure on this page is modelled or estimated.",
        "international_data_available": False,
        "international_data_note": (
            "International facility adapters exist as code (etl/adapters/) but have not collected any "
            "price data. No international observations exist yet."
        ),
        "procedures": summary,
    }
    atomic_write_text(OUT_DIR / "summary.json", json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote {len(summary)} procedure files and summary to {OUT_DIR} ({dropped} observations dropped)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
