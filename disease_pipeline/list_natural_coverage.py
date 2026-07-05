#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "disease-intelligence"


def main() -> None:
    rows = []
    for p in sorted(DATA.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        s = d["summary"]
        tc = s.get("therapeutic_counts", {})
        review = tc.get("natural", 0)
        pipeline = s.get("natural_product_count", len(d.get("natural_products", [])))
        if not review and not pipeline:
            continue
        if review and pipeline:
            source = "both"
        elif review:
            source = "review only"
        else:
            source = "pipeline only"
        rows.append({
            "name": d["condition"]["shortName"],
            "slug": d["slug"],
            "review": review,
            "pipeline": pipeline,
            "source": source,
        })

    rows.sort(key=lambda r: (-(r["review"] + r["pipeline"]), r["name"].lower()))

    print(f"Diseases with natural products (pipeline and/or OSMF review): {len(rows)}\n")
    print(f"{'Disease':<42} {'Review':>6} {'Pipeline':>8}  Source")
    print("-" * 72)
    for r in rows:
        print(f"{r['name']:<42} {r['review']:>6} {r['pipeline']:>8}  {r['source']}")

    review_only = sum(1 for r in rows if r["source"] == "review only")
    pipeline_only = sum(1 for r in rows if r["source"] == "pipeline only")
    both = sum(1 for r in rows if r["source"] == "both")
    print(f"\nBreakdown: {both} both · {pipeline_only} pipeline only · {review_only} review only")


if __name__ == "__main__":
    main()