#!/usr/bin/env python3
"""Apply the October 2026 claim-verification results to the state-law cells.

Reads data/verification/results/state-*.jsonl (schema A in
data/verification/PROTOCOL.md) and rewrites data/cells/<jur>/<layer>.yaml:

  confirmed / corrected / ambiguous -> value, citation, deep source_url,
      evidence_quote, source_type, confidence, verified_on, verification_status
  unsupported (or no result)          -> verification_status: unsupported;
      the pages render "Not verified" and the composite index skips it

Provenance is recorded honestly: verified_by names the AI-assisted
verification pass, not a person.  Re-runnable; prints a summary and writes
data/verification/state-summary.json.

    python scripts/apply_verification.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CELLS = ROOT / "data" / "cells"
RESULTS = ROOT / "data" / "verification" / "results"
SOURCE_ID = "osmf_verification_2026_10"
VERIFIED_BY = "OSMF verification pass 2026-10 (AI-assisted; quoted source)"
TYPE_MAP = {
    "primary_statute": "primary_statute",
    "official_list": "agency_guidance",
    "regulator": "agency_guidance",
    "secondary_tracker": "secondary_tracker",
    "peer_reviewed": "secondary_tracker",
    "news": "secondary_tracker",
}


FAILED = set()
_failed_file = ROOT / "data" / "verification" / "quote-audit-failed.jsonl"
if _failed_file.exists():
    for _l in _failed_file.read_text(encoding="utf-8").splitlines():
        if _l.strip():
            _r = json.loads(_l)
            FAILED.add((_r["key"], _r["url"], _r["quote"][:200]))


def coerce(value, dtype, allowed):
    """Return (ok, value) with value coerced to the registry type."""
    if dtype == "bool":
        if isinstance(value, bool):
            return True, value
        if isinstance(value, str) and value.lower() in ("true", "false", "yes", "no"):
            return True, value.lower() in ("true", "yes")
        return False, value
    if dtype == "int":
        try:
            return True, int(value)
        except (TypeError, ValueError):
            return False, value
    if dtype == "enum":
        return (value in (allowed or [])), value
    if dtype == "date":
        return (isinstance(value, str) and len(value) == 10), value
    return (value is not None and str(value).strip() != ""), value


def load_results() -> dict:
    out = {}
    # original batches first, then targeted re-runs (pharm2-*, rerun-*), which win
    files = sorted(RESULTS.glob("state-*.jsonl")) + sorted(RESULTS.glob("pharm2-*.jsonl")) + sorted(RESULTS.glob("rerun-*.jsonl"))
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                print(f"  skip malformed line {f.name}:{n}", file=sys.stderr)
                continue
            if r.get("key"):
                out[r["key"]] = r   # last write wins (agents may re-emit after fixes)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    reg = yaml.safe_load((ROOT / "schemas" / "layer-registry.yaml").read_text(encoding="utf-8"))
    layers = reg.get("layers", reg)
    layers = layers if isinstance(layers, list) else list(layers.values())
    dimdef = {(L["id"], d["id"]): d for L in layers for d in L.get("dimensions", [])}
    results = load_results()
    stats, changes = Counter(), []
    for path in sorted(CELLS.glob("*/*.yaml")):
        cell = yaml.safe_load(path.read_text(encoding="utf-8"))
        dirty = False
        for dim in cell.get("dimensions", []):
            key = f"{cell['jurisdiction']}|{cell['layer']}|{dim['id']}"
            r = results.get(key)
            dd = dimdef.get((cell["layer"], dim["id"]), {})
            verdict = (r or {}).get("verdict", "missing")
            usable = (verdict in ("confirmed", "corrected", "ambiguous")
                      and r.get("evidence_url", "").startswith("http")
                      and r.get("evidence_quote")
                      and (key, r.get("evidence_url"), (r.get("evidence_quote") or "")[:200]) not in FAILED)
            if usable:
                ok, val = coerce(r.get("value"), dd.get("type"), dd.get("values"))
                usable = ok
            new = dict(dim)
            if usable:
                if val != dim.get("value"):
                    changes.append({"key": key, "from": dim.get("value"), "to": val, "verdict": verdict,
                                    "evidence_url": r["evidence_url"]})
                stype = TYPE_MAP.get(r.get("source_type"), "secondary_tracker")
                new.update({
                    "value": val,
                    "citation": r.get("citation") or r.get("evidence_title") or "Source",
                    "source_id": SOURCE_ID,
                    "source_url": r["evidence_url"],
                    "source_type": stype,
                    "evidence_quote": r["evidence_quote"],
                    "verified_on": r.get("as_of") or "2026-10-09",
                    "verified_by": VERIFIED_BY,
                    "confidence": "high" if (stype != "secondary_tracker" and verdict != "ambiguous") else "medium",
                    "verification_status": verdict,
                })
                if r.get("notes"):
                    new["note"] = r["notes"]
                elif verdict == "corrected":
                    new.pop("note", None)
                stats[verdict] += 1
            else:
                new.update({
                    "verification_status": "unsupported",
                    "citation": "Not verified: no adequate source found in the October 2026 review",
                    "source_id": SOURCE_ID,
                    "source_url": "https://research.opensourcemed.info/maps/methodology.html",
                    "source_type": "secondary_tracker",
                    "verified_on": "2026-10-09",
                    "verified_by": VERIFIED_BY,
                    "confidence": "derived",
                })
                new.pop("evidence_quote", None)
                if r and r.get("notes"):
                    new["note"] = r["notes"]
                stats["unsupported" if verdict != "missing" else "no_result"] += 1
            if new != dim:
                dim.clear(); dim.update(new); dirty = True
        if dirty and not args.dry_run:
            path.write_text(yaml.safe_dump(cell, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8")
    summary = {"counts": dict(stats), "value_changes": changes}
    if not args.dry_run:
        (ROOT / "data" / "verification" / "state-summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({"counts": dict(stats), "value_changes": len(changes)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
