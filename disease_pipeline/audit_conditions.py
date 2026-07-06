#!/usr/bin/env python3
"""Audit RepurpOS conditions for duplicates and missing biomarkers."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data" / "disease-intelligence"
LINKS_PATH = ROOT / "disease_pipeline" / "seeds" / "site_links.json"

from disease_pipeline.published_conditions import (
    DUPLICATE_SLUGS,
    biomarker_count,
    is_publishable,
)


def load_rows() -> list[dict]:
    links = json.loads(LINKS_PATH.read_text(encoding="utf-8"))
    rows = []
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = data["slug"]
        alts = data.get("alterations", [])
        summary = data.get("summary", {})
        type_counts = summary.get("alteration_counts_by_type", {})
        type_b = sum(1 for a in alts if a.get("type") == "B") or type_counts.get("B", 0)
        rows.append(
            {
                "path": path,
                "slug": slug,
                "name": data["condition"]["shortName"],
                "identifiers": data.get("identifiers", {}),
                "alt_count": summary.get("alteration_count", len(alts)),
                "type_b": type_b,
                "has_biomarker_link": bool(links.get(slug, {}).get("biomarker_html")),
            }
        )
    return rows


def main() -> int:
    rows = load_rows()
    print(f"Total conditions: {len(rows)}\n")

    print("=== Planned duplicate removals ===")
    for dup, keep in DUPLICATE_SLUGS.items():
        dup_row = next((r for r in rows if r["slug"] == dup), None)
        keep_row = next((r for r in rows if r["slug"] == keep), None)
        if dup_row and keep_row:
            print(
                f"DROP {dup} ({dup_row['alt_count']} alts) "
                f"-> keep {keep} ({keep_row['alt_count']} alts)"
            )

    print("\n=== Zero alterations ===")
    for row in rows:
        if row["alt_count"] == 0:
            print(f"{row['slug']} | {row['name']}")

    print("\n=== No biomarker atlas link ===")
    for row in rows:
        if not is_publishable({"slug": row["slug"], "summary": {"alteration_count": row["alt_count"]}, "alterations": []}):
            continue
        if not row["has_biomarker_link"]:
            print(f"{row['slug']} | {row['name']} | alts={row['alt_count']}")

    for label, key in [
        ("MONDO", "mondo_id"),
        ("EFO", "efo_id"),
        ("MESH", "mesh_id"),
    ]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            value = row["identifiers"].get(key)
            if value:
                grouped[value].append(row)
        dupes = {k: v for k, v in grouped.items() if len(v) > 1}
        if dupes:
            print(f"\n=== Duplicate {label} IDs ===")
            for value, group in sorted(dupes.items()):
                print(value, "->", [(g["slug"], g["alt_count"]) for g in group])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())