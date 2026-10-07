#!/usr/bin/env python3
"""
Build the compact index consumed by tools/repurposing-explorer.html.

Reads (via scripts/lib/repurposing_data.py):
  data/disease-intelligence/*.json, data/therapeutic_agents.json,
  data/clinical_trials/clinical_trials_current.json, data/disease-agent-pairs.json,
  data/agent-literature/*.json, data/vocab/*, data/condition-categories.json

Writes:
  js/generated/repurposing-index.json

Usage: python scripts/build_repurposing_index.py
"""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.lib.repurposing_data import build_records, SCORE_DOC, TIER_LABEL  # noqa: E402

OUT = ROOT / "js" / "generated" / "repurposing-index.json"


def main():
    conditions, records = build_records(verbose=True)
    rows_per_cond = {}
    for r in records:
        rows_per_cond[r["disease_slug"]] = rows_per_cond.get(r["disease_slug"], 0) + 1

    cond_list = []
    for slug, c in sorted(conditions.items(), key=lambda kv: (kv[1]["track"] != "post-viral", kv[1]["short"].lower())):
        cond_list.append({
            "s": slug,
            "n": c["name"],
            "short": c["short"],
            "track": c["track"],
            "cat": c["category_label"],
            "url": c["url"],
            "nCand": c["n_candidates"],
            "nRows": rows_per_cond.get(slug, 0),
            "mondo": c["mondo_id"],
        })

    rows = []
    for r in records:
        tb = r["trial_breakdown"]
        rows.append({
            "d": r["disease_slug"],
            "a": r["agent_slug"],
            "n": r["agent_name"],
            "ty": r["agent_type"],
            "tyr": r["agent_type_raw"] if r["agent_type_raw"] != r["agent_type"] else "",
            "m": r["mechanism"][:160],
            "ph": r["phase_label"],
            "ap": 1 if r["approved_any"] else 0,
            "tier": r["tier"],
            "sc": r["score"],
            "sp": r["score_parts"],
            "tb": [tb["total"], tb["recruiting"], tb["active"], tb["completed"], tb["other"]],
            "ph3": sum(1 for t in r["trials"] if t["phase"] in ("PHASE3", "PHASE4")),
            "lit": len(r["literature"]),
            "lb": r["lit_breakdown"],
            "au": r["agent_url"],
            "pu": r["pair_url"],
            "src": r["source_track"],
            "ext": [{"l": l.get("label", "Link"), "u": l["url"]} for l in r["external_links"][:1]],
        })

    payload = {
        "generated": date.today().isoformat(),
        "score_doc": SCORE_DOC,
        "tier_labels": TIER_LABEL,
        "conditions": cond_list,
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(rows)} rows, {len(cond_list)} conditions)")


if __name__ == "__main__":
    main()
