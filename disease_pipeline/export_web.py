#!/usr/bin/env python3
"""Export pipeline JSON to web schema + HTML pages."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.output.generate_html import build_index_html, write_page
from disease_pipeline.output.web_export import from_spec_json

log = logging.getLogger(__name__)

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"
PIPELINE_OUT = Path(__file__).parent / "output"


def export_file(path: Path, *, write_html: bool = True, cap_display: bool = False) -> dict:
    spec = json.loads(path.read_text(encoding="utf-8"))
    web = from_spec_json(spec, cap_display=cap_display)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    json_path = DATA_DIR / f"{web['slug']}.json"
    json_path.write_text(json.dumps(web, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Wrote %s", json_path)
    if write_html:
        html_path = write_page(web, HTML_DIR)
        log.info("Wrote %s", html_path)
    return web


def main() -> int:
    parser = argparse.ArgumentParser(description="Export disease pipeline JSON to web format + HTML")
    parser.add_argument("inputs", nargs="*", help="Pipeline JSON files (default: disease_pipeline/output/*.json)")
    parser.add_argument("--no-html", action="store_true")
    parser.add_argument("--cap", action="store_true", help="Cap displayed lists (80 alts, 50 merged drugs)")
    parser.add_argument("--full", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    if args.inputs:
        paths = [Path(p) for p in args.inputs]
    else:
        paths = sorted(PIPELINE_OUT.glob("*.json"))
    paths = [p for p in paths if p.is_file() and p.name != "index.json"]

    web_pages: list[dict] = []
    for path in paths:
        if not path.exists():
            log.warning("Skip missing %s", path)
            continue
        try:
            web_pages.append(export_file(path, write_html=not args.no_html, cap_display=args.cap))
        except Exception as e:
            log.error("Failed %s: %s", path, e)

    if web_pages and not args.no_html:
        HTML_DIR.mkdir(parents=True, exist_ok=True)
        index_path = HTML_DIR / "index.html"
        index_path.write_text(build_index_html(web_pages), encoding="utf-8")
        log.info("Wrote index %s (%d diseases)", index_path, len(web_pages))

    return 0 if web_pages else 1


if __name__ == "__main__":
    raise SystemExit(main())