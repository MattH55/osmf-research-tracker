#!/usr/bin/env python3
"""Crawl internal href/src links in generated and root pages and report ones
that do not resolve on disk. Run from repo root:

    python scripts/check_generated_links.py [dir ...]
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent
ORIGIN = "https://research.opensourcemed.info"
DEFAULT_DIRS = [".", "biomarkers", "compare", "trials", "pairs", "digest", "reports", "tools", "embed"]
LINK_RE = re.compile(r"""(?:href|src)\s*=\s*["']([^"'#]+)(?:#[^"']*)?["']""", re.I)


def pages(dirs: list[str]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        base = ROOT / d
        if not base.exists():
            continue
        out.extend(base.glob("*.html") if d == "." else base.rglob("*.html"))
    return sorted(set(out))


def resolve(page: Path, link: str) -> Path | None:
    link = link.strip()
    if link.startswith(ORIGIN):
        link = link[len(ORIGIN):] or "/"
    if re.match(r"^[a-z]+:", link) or link.startswith("//"):
        return None  # external
    path = unquote(urlsplit(link).path)
    if not path:
        return None
    target = (ROOT / path.lstrip("/")) if path.startswith("/") else (page.parent / path)
    if path.endswith("/"):
        target = target / "index.html"
    return target


def main() -> int:
    dirs = sys.argv[1:] or DEFAULT_DIRS
    broken: Counter[str] = Counter()
    examples: dict[str, str] = {}
    n_pages = n_links = 0
    for page in pages(dirs):
        n_pages += 1
        markup = page.read_text(encoding="utf-8", errors="replace")
        for link in LINK_RE.findall(markup):
            target = resolve(page, link)
            if target is None:
                continue
            n_links += 1
            if not target.exists():
                key = link
                broken[key] += 1
                examples.setdefault(key, page.relative_to(ROOT).as_posix())
    print(f"pages: {n_pages}  internal links: {n_links}  broken targets: {len(broken)} ({sum(broken.values())} occurrences)")
    for link, count in broken.most_common(60):
        print(f"  {count:5d}  {link}   e.g. {examples[link]}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
