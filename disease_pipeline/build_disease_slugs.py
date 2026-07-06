#!/usr/bin/env python3
"""Build seeds/disease_slugs.json from GMI + Examine override maps."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent
SEEDS = ROOT / "seeds"
OUT = SEEDS / "disease_slugs.json"


def main() -> int:
    merged: dict[str, dict[str, str]] = {}
    gmi_path = SEEDS / "gmi_disease_slugs.json"
    ex_path = SEEDS / "examine_condition_slugs.json"
    if gmi_path.exists():
        for slug, gmi in json.loads(gmi_path.read_text(encoding="utf-8")).items():
            merged.setdefault(slug, {})["greenmedinfo"] = gmi
    if ex_path.exists():
        for slug, ex in json.loads(ex_path.read_text(encoding="utf-8")).items():
            merged.setdefault(slug, {})["examine"] = ex
    OUT.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"Wrote {len(merged)} disease slug entries to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())