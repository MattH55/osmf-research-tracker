#!/usr/bin/env python3
"""Attach burden/funding stats to disease-intelligence JSON files."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.adapters.burden.loader import get_burden_for_slug
from disease_pipeline.output.generate_html import write_page

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich diseases with US burden/funding data")
    parser.add_argument("--slug")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    paths = sorted(DATA_DIR.glob("*.json"))
    if args.slug:
        paths = [p for p in paths if p.stem == args.slug]

    n = 0
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        slug = data.get("slug", path.stem)
        name = data.get("condition", {}).get("name", slug)
        burden = get_burden_for_slug(slug, name)
        if not burden:
            continue
        data["burden"] = burden
        summary = data.setdefault("summary", {})
        if "NIH RCDC" not in summary.get("sources_queried", []):
            summary.setdefault("sources_queried", []).append("NIH RCDC")
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if args.html:
            write_page(data, HTML_DIR)
        n += 1
        log.info("%s: funding=$%sM level=%s", slug, burden.get("nih_funding_millions_usd"), burden.get("funding_level"))

    log.info("Done: %d diseases with burden data", n)
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())