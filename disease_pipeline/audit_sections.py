#!/usr/bin/env python3
"""Audit disease pages for natural agents and blank sections."""
from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).parent.parent / "data" / "disease-intelligence"

SECTION_KEYS = (
    "alterations",
    "direct",
    "via_biomarker",
    "natural_agents",
    "merged",
    "natural_products",
)


def main() -> None:
    rows = []
    for p in sorted(DATA.glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        s = d.get("summary", {})
        tc = s.get("therapeutic_counts", {})
        ther = d.get("therapeutics", {})
        sections = {
            "alterations": s.get("alteration_count", len(d.get("alterations", []))),
            "direct": tc.get("direct", len(ther.get("direct", []))),
            "via_biomarker": tc.get("via_biomarker", len(ther.get("via_biomarker", []))),
            "natural_agents": tc.get("natural", len(ther.get("natural", []))),
            "merged": tc.get("merged", len(ther.get("merged_ranked", []))),
            "natural_products": s.get("natural_product_count", len(d.get("natural_products", []))),
        }
        blanks = [k for k, v in sections.items() if v == 0]
        rows.append({
            "name": d["condition"]["shortName"],
            "full_name": d["condition"]["name"],
            "slug": d["slug"],
            "sections": sections,
            "blanks": blanks,
        })

    with_natural = [r for r in rows if r["sections"]["natural_agents"] > 0]
    complete = [r for r in with_natural if not r["blanks"]]

    print(f"Diseases WITH OSMF natural agents: {len(with_natural)}")
    print(f"Natural agents + NO blank sections: {len(complete)}\n")

    if complete:
        print("=" * 72)
        print("COMPLETE LIST (natural agents present, all sections populated)")
        print("=" * 72)
        for r in sorted(complete, key=lambda x: x["name"].lower()):
            sec = r["sections"]
            print(f"\n{r['name']}  ({r['slug']})")
            print(f"  Alterations: {sec['alterations']}")
            print(f"  Direct drugs: {sec['direct']}")
            print(f"  Via biomarker: {sec['via_biomarker']}")
            print(f"  Natural agents (OSMF): {sec['natural_agents']}")
            print(f"  Merged ranked: {sec['merged']}")
            print(f"  Natural products (pipeline): {sec['natural_products']}")

    if with_natural:
        incomplete = [r for r in with_natural if r["blanks"]]
        if incomplete:
            print("\n" + "=" * 72)
            print("NATURAL AGENTS BUT HAS BLANK SECTIONS")
            print("=" * 72)
            for r in sorted(incomplete, key=lambda x: x["name"].lower()):
                print(f"  {r['name']}: blank -> {', '.join(r['blanks'])}")


if __name__ == "__main__":
    main()