#!/usr/bin/env python3
"""Fold the manual quote audit (results/audit-*.jsonl) back into the results.

  present     -> nothing to do
  paraphrase  -> replace the stored quote with the page's verbatim wording
  absent      -> listed in quote-audit-failed.jsonl (evidence discarded on apply)
  unreadable  -> listed as failed too: a quote nobody could confirm is not evidence

Any audited quote with no audit verdict at all is also treated as failed.

    python scripts/integrate_quote_audit.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VER = ROOT / "data" / "verification"


def main() -> int:
    audited = {}
    for f in sorted((VER / "batches").glob("audit-*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l); audited[(r["key"], r["url"], r["quote"][:200])] = r
    verdicts = {}
    for f in sorted((VER / "results").glob("audit-*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l); verdicts[(r["key"], r["url"], (r.get("quote") or "")[:200])] = r
    stats, failed, swaps = Counter(), [], {}
    for k, item in audited.items():
        v = verdicts.get(k)
        verdict = (v or {}).get("verdict", "missing")
        stats[verdict] += 1
        if verdict == "paraphrase" and (v.get("verbatim") or "").strip():
            swaps[k] = v["verbatim"].strip()
        elif verdict != "present":
            failed.append({"key": k[0], "url": k[1], "quote": item["quote"], "verdict": verdict})
    # rewrite quotes in result files for paraphrases
    swapped = 0
    for f in sorted((VER / "results").glob("*.jsonl")):
        if f.name.startswith("audit-"):
            continue
        rows, dirty = [], False
        for l in f.read_text(encoding="utf-8").splitlines():
            if not l.strip():
                continue
            r = json.loads(l); key = r.get("key") or r.get("id")
            if r.get("evidence_url"):
                kk = (key, r["evidence_url"], (r.get("evidence_quote") or "")[:200])
                if kk in swaps:
                    r["evidence_quote"] = swaps[kk]; dirty = True; swapped += 1
            for e in r.get("evidence") or []:
                if isinstance(e, dict):
                    kk = (key, e.get("url"), (e.get("quote") or "")[:200])
                    if kk in swaps:
                        e["quote"] = swaps[kk]; dirty = True; swapped += 1
            rows.append(r)
        if dirty:
            f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    (VER / "quote-audit-failed.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in failed), encoding="utf-8")
    print(json.dumps({"audited": len(audited), "verdicts": dict(stats), "quotes_swapped": swapped,
                      "failed_listed": len(failed)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
