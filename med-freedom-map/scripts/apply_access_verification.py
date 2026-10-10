#!/usr/bin/env python3
"""Apply October 2026 verification results to procedure × jurisdiction records.

Reads data/verification/results/access-*.jsonl (schema B) and
results/access-meta.jsonl (schema C) and updates backend/medfreedom.db, the
source of data/med-freedom/access-public.json (re-export with
scripts/publish_med_freedom_static.py from the repo root).

Rules (see data/verification/PROTOCOL.md):
  * structured fields: confirmed/corrected/ambiguous -> value; unsupported ->
    NULL (legal_status -> UNKNOWN), so no unsupported claim is published
  * text fields: keep | rewrite (new text) | remove (NULL)
  * cost: confirmed/corrected keeps the sourced range; remove -> NULL
  * sources: replaced by the evidence list (url, title, quote, supports)
  * verification_json: per-field verdicts, shown on the page
  * a record with NO result is left untouched and listed, so a failed batch
    never silently deletes content

    python scripts/apply_access_verification.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "backend" / "medfreedom.db"
RESULTS = ROOT / "data" / "verification" / "results"
VERIFIED_ON = "2026-10-09"
VERIFIED_BY = "OSMF verification pass 2026-10 (AI-assisted; quoted sources)"

STRUCT = ["legal_status", "access_pathway", "regulatory_authority", "legal_basis", "oversight_quality"]
TEXT = ["access_pathway_details", "eligibility_requirements", "provider_requirements", "residency_travel_notes",
        "risk_notes", "oversight_notes", "cost_notes", "arbitrage_summary"]
ENUMS = {
    "legal_status": {"FULLY_APPROVED", "APPROVED_ON_LABEL", "APPROVED_OFF_LABEL", "PERMITTED_EXPANDED_ACCESS",
                     "RIGHT_TO_TRY", "CLINICAL_TRIAL_ONLY", "PHYSICIAN_DISCRETION_GRAY", "REGULATED_THERAPY",
                     "UNREGULATED_PERMITTED", "DECRIMINALIZED", "DECRIMINALIZED_NO_SUPPLY", "PROHIBITED", "NOT_AUTHORISED", "UNKNOWN"},
    "access_pathway": {"STANDARD_PRESCRIPTION", "OFF_LABEL_PRESCRIPTION", "COMPOUNDING", "EXPANDED_ACCESS",
                       "RIGHT_TO_TRY", "CLINICAL_TRIAL_ENROLLMENT", "LICENSED_PROVIDER_REGIME", "PERSONAL_IMPORT",
                       "MEDICAL_TOURISM_CASH", "OVER_THE_COUNTER", "NONE"},
    "oversight_quality": {"REGULATED_HIGH", "REGULATED_MODERATE", "HIGH", "MEDIUM", "LOW", "MINIMAL", "VARIABLE"},
}


def load(*patterns: str) -> dict:
    """Later patterns win: first-pass batches, then country-grouped re-runs."""
    out = {}
    files = [f for pat in patterns for f in sorted(RESULTS.glob(pat))]
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("id"):
                out[r["id"]] = r
    return out


FAILED = set()
_failed_file = ROOT / "data" / "verification" / "quote-audit-failed.jsonl"
if _failed_file.exists():
    for _l in _failed_file.read_text(encoding="utf-8").splitlines():
        if _l.strip():
            _r = json.loads(_l)
            FAILED.add((_r["key"], _r["url"], _r["quote"][:200]))


def good_evidence(ev, rid=None) -> list:
    """Evidence with a deep URL and a quote that was not refuted by the audit."""
    keep = []
    for e in ev or []:
        if rid and isinstance(e, dict) and (rid, e.get("url"), (e.get("quote") or "")[:200]) in FAILED:
            continue
        if isinstance(e, dict) and str(e.get("url", "")).startswith("http") and e.get("quote"):
            keep.append({"url": e["url"], "title": e.get("title") or e["url"], "quote": e["quote"],
                         "supports": e.get("supports") or []})
    return keep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cols = {r[1] for r in con.execute("pragma table_info(access_records)")}
    if "verification_json" not in cols and not args.dry_run:
        con.execute("alter table access_records add column verification_json text")
    for t in ("procedures", "jurisdictions"):
        tcols = {r[1] for r in con.execute(f"pragma table_info({t})")}
        if "verification_json" not in tcols and not args.dry_run:
            con.execute(f"alter table {t} add column verification_json text")

    results = load("access-[0-9]*.jsonl", "rerun-access-*.jsonl")
    # a re-run only replaces a first-pass record when it found support for it
    first = load("access-[0-9]*.jsonl")
    for rid, r in list(results.items()):
        if (r.get("legal_status") or {}).get("verdict") == "unsupported" and rid in first:
            results[rid] = first[rid]
    stats, missing = Counter(), []
    for row in con.execute("select * from access_records").fetchall():
        r = results.get(row["id"])
        if not r:
            missing.append(row["id"]); continue
        ev = good_evidence(r.get("evidence"), row["id"])
        upd, ver = {}, {}

        def backed(field: str) -> bool:
            # a field needs surviving evidence that names it (or generic evidence)
            return any((not e["supports"]) or field in e["supports"] for e in ev)
        for f in STRUCT:
            v = r.get(f) or {}
            verdict = v.get("verdict", "unsupported")
            val = v.get("value")
            if verdict in ("confirmed", "corrected", "ambiguous") and ev and backed(f) and val not in (None, ""):
                if f in ENUMS and val not in ENUMS[f]:
                    verdict, val = "unsupported", None
            else:
                verdict, val = "unsupported", None
            if verdict == "unsupported":
                val = "UNKNOWN" if f == "legal_status" else None
            upd[f] = val; ver[f] = verdict; stats[f"{f}:{verdict}"] += 1
        cost = r.get("cost") or {}
        if cost.get("verdict") in ("confirmed", "corrected") and ev and any(backed(k) for k in ("cost", "estimated_cost_range_usd", "price_usd", "cost_notes")) and cost.get("estimated_cost_range_usd"):
            upd["estimated_cost_range_usd"] = cost["estimated_cost_range_usd"]
            upd["price_usd"] = cost.get("price_usd")
            ver["cost"] = cost["verdict"]
        else:
            upd["estimated_cost_range_usd"] = None; upd["price_usd"] = None; upd["total_access_cost_usd"] = None
            ver["cost"] = "removed"
        stats[f"cost:{ver['cost']}"] += 1
        for f in TEXT:
            t = (r.get("text") or {}).get(f) or {}
            action = t.get("action", "remove")
            if action == "keep" and ev:
                ver[f] = "confirmed"
            elif action == "rewrite" and t.get("text") and ev:
                upd[f] = t["text"]; ver[f] = "rewritten"
            else:
                upd[f] = None; ver[f] = "removed"
            stats[f"text:{ver[f]}"] += 1
        upd["sources"] = json.dumps(ev, ensure_ascii=False)
        upd["last_verified"] = VERIFIED_ON
        upd["verified_by"] = VERIFIED_BY
        upd["verification_json"] = json.dumps({"fields": ver, "notes": r.get("notes")}, ensure_ascii=False)
        if not args.dry_run:
            sets = ", ".join(f"{k} = ?" for k in upd)
            con.execute(f"update access_records set {sets} where id = ?", [*upd.values(), row["id"]])

    meta = load("access-meta.jsonl")
    for table, fields in (("procedures", ["description", "typical_us_cost_range"]), ("jurisdictions", ["general_notes"])):
        for row in con.execute(f"select id from {table}").fetchall():
            r = meta.get(row["id"])
            if not r:
                missing.append(f"{table}:{row['id']}"); continue
            ev = good_evidence(r.get("evidence"), row["id"]); upd, ver = {}, {}
            for f in fields:
                t = r.get(f) or {}
                action = t.get("action", "remove")
                if action == "keep" and ev:
                    ver[f] = "confirmed"
                elif action == "rewrite" and t.get("text") and ev:
                    upd[f] = t["text"]; ver[f] = "rewritten"
                else:
                    upd[f] = None; ver[f] = "removed"
                stats[f"{table}.{f}:{ver[f]}"] += 1
            upd["verification_json"] = json.dumps({"fields": ver, "evidence": ev}, ensure_ascii=False)
            if not args.dry_run:
                sets = ", ".join(f"{k} = ?" for k in upd)
                con.execute(f"update {table} set {sets} where id = ?", [*upd.values(), row["id"]])
    if not args.dry_run:
        con.commit()
    summary = {"counts": dict(sorted(stats.items())), "missing_results": missing}
    (ROOT / "data" / "verification" / "access-summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({"records_with_results": len(results), "missing": len(missing)}, indent=1))
    for k, v in sorted(stats.items()):
        print(f"  {k:45s} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
