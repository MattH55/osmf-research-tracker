#!/usr/bin/env python3
"""Normalize disease display names in JSON seeds and intelligence exports."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.adapters.remission.slug_map import display_names_for_slug, label_for_slug, slug_for_label
from disease_pipeline.display_names import apply_canonical_names
from disease_pipeline.display_np_names import apply_np_names_to_web_data
from disease_pipeline.np_publications import enrich_disease_publications

log = logging.getLogger(__name__)

DATA_DIR = _ROOT / "data" / "disease-intelligence"
DB100_PATH = Path(__file__).parent / "seeds" / "disease_db_100.json"
ATLAS_DIR = _ROOT / "data" / "biomarkers"


def normalize_intelligence_json() -> int:
    n = 0
    for path in sorted(DATA_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        before = (data.get("condition", {}).get("shortName"), data.get("condition", {}).get("name"))
        np_before = [np.get("name") for np in data.get("natural_products", [])]
        apply_canonical_names(data)
        apply_np_names_to_web_data(data)
        pub_changed = enrich_disease_publications(data, refresh_gmi=True)
        after = (data.get("condition", {}).get("shortName"), data.get("condition", {}).get("name"))
        np_after = [np.get("name") for np in data.get("natural_products", [])]
        if before != after or np_before != np_after or pub_changed:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info("%s: %r -> %r", path.stem, before, after)
            n += 1
    return n


def normalize_db100() -> int:
    if not DB100_PATH.exists():
        return 0
    payload = json.loads(DB100_PATH.read_text(encoding="utf-8"))
    n = 0
    for entry in payload.get("diseases", []):
        label = (entry.get("disease") or "").strip()
        if not label:
            continue
        slug = slug_for_label(label)
        canonical = label_for_slug(slug)
        if canonical and canonical != label:
            log.info("db100 %s: %r -> %r", slug, label, canonical)
            entry["disease"] = canonical
            n += 1
    if n:
        DB100_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return n


def normalize_atlas_json() -> int:
    n = 0
    for path in sorted(ATLAS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "markers" not in data or "condition" not in data:
            continue
        slug = data.get("slug", path.stem)
        if not slug or slug in ("commercial-links", "consumable-links"):
            continue
        cond = data.get("condition", {})
        if not cond.get("name"):
            continue
        short, full = display_names_for_slug(
            slug,
            fallback_short=cond.get("name"),
            fallback_full=cond.get("name"),
        )
        before = cond.get("name")
        if before != short:
            cond["name"] = short
            page = data.get("page", {})
            if page.get("title"):
                page["title"] = page["title"].replace(before, short)
            if page.get("hero") and before:
                page["hero"] = page["hero"].replace(before, short)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            log.info("atlas %s: %r -> %r", slug, before, short)
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Normalize disease display capitalization")
    parser.add_argument("--db100-only", action="store_true")
    parser.add_argument("--atlas-only", action="store_true")
    args = parser.parse_args(argv)

    total = 0
    if not args.db100_only and not args.atlas_only:
        total += normalize_intelligence_json()
    if not args.atlas_only:
        total += normalize_db100()
    if not args.db100_only:
        total += normalize_atlas_json()

    log.info("Updated %d records", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())