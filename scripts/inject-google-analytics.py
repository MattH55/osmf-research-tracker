#!/usr/bin/env python3
"""Insert Google Analytics gtag snippet into every HTML page under the repo."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from disease_pipeline.site_nav import GOOGLE_ANALYTICS_ID, GOOGLE_ANALYTICS_SNIPPET

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def inject(html: str) -> str | None:
    if GOOGLE_ANALYTICS_ID in html:
        return None
    return re.sub(
        r"(<head[^>]*>)",
        r"\1\n" + GOOGLE_ANALYTICS_SNIPPET,
        html,
        count=1,
        flags=re.IGNORECASE,
    )


def main() -> int:
    changed = 0
    skipped = 0
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        updated = inject(text)
        if updated is None:
            skipped += 1
            continue
        path.write_text(updated, encoding="utf-8")
        changed += 1
        print(f"  {path.relative_to(ROOT)}")
    print(f"Updated {changed} HTML files ({skipped} already had analytics).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())