#!/usr/bin/env python3
"""Convert the dark-mode disease page families to the light OSMF theme, in place.

    python scripts/restyle_disease_pages.py            # all families
    python scripts/restyle_disease_pages.py --check    # report pages that would change
    python scripts/restyle_disease_pages.py ntd/dengue.html ...

Targets chronic-disease-interventions/, disease-intelligence/ and ntd/. Only pages
built from the old dark templates (or already restyled) are touched; redirect
stubs and hand-built light pages are skipped. Idempotent: safe to run after every
regeneration and before scripts/apply_osmf_ui.py. The transformation itself lives
in disease_pipeline/light_theme.py, which the generators also call.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from disease_pipeline.light_theme import THEME_MARK, restyle_html  # noqa: E402

DIRS = ("chronic-disease-interventions", "disease-intelligence", "ntd")


def eligible(markup: str) -> bool:
    return THEME_MARK in markup or "--bg:#0a0e1a" in markup.replace(" ", "")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", help="specific pages (default: every page in the three directories)")
    ap.add_argument("--check", action="store_true", help="list pages that would change, write nothing")
    args = ap.parse_args()

    pages = [ROOT / p for p in args.paths] if args.paths else [p for d in DIRS for p in sorted((ROOT / d).glob("*.html"))]
    changed = skipped = 0
    for page in pages:
        markup = page.read_text(encoding="utf-8")
        if not eligible(markup):
            skipped += 1
            continue
        new = restyle_html(markup)
        if new != markup:
            changed += 1
            if args.check:
                print(page.relative_to(ROOT))
            else:
                eol = "\r\n" if b"\r\n" in page.read_bytes()[:4096] else "\n"
                page.write_text(new, encoding="utf-8", newline=eol)
    verb = "would change" if args.check else "restyled"
    print(f"{verb} {changed} page(s); {skipped} skipped (not a dark-template page)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
