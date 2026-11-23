#!/usr/bin/env python3
"""Build js/generated/site-search.json: [title, url, type] for every public page.

Read by js/osmf-search.js (the header search box). Run after the page
generators; scripts/apply_osmf_ui.py calls it at the end of a full run.

    python scripts/build_search_index.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import apply_osmf_ui as ui

ROOT = ui.ROOT
OUT = ROOT / "js" / "generated" / "site-search.json"
EXTRA_DIRS = ("peptideos", "genetics", "maps")       # public sections with their own chrome
CONDITION_PAGES = {"long-covid.html", "me-cfs.html", "pacvs.html", "pots.html", "mcas.html", "lyme.html",
                   "gulf-war-illness.html", "other-post-viral.html", "post-viral-illness.html"}
TYPES = (("pairs/", "Condition + therapy"), ("agents/", "Therapy"), ("biomarkers/", "Biomarker"),
         ("trials/", "Trial"), ("compare/", "Comparison"), ("chronic-disease-interventions/", "Condition"),
         ("disease-intelligence/", "Condition"), ("tools/", "Tool"), ("nondrug/", "Therapy"),
         ("supplement-safety/", "Therapy"), ("peptideos/", "Therapy"), ("evidence-gaps/", "Report"),
         ("briefs/", "Report"), ("reports/", "Report"), ("digest/", "Report"), ("genetics/", "Tool"),
         ("maps/", "Access map"))
TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
SUFFIX_RE = re.compile(r"\s*(?:[|–—]|-(?= ))\s*(?:OSMF|Open Source Medicine|Research Tracker|PeptideOS)[^|–—]*$", re.I)


def page_type(rel: str) -> str:
    if rel in CONDITION_PAGES:
        return "Condition"
    for prefix, kind in TYPES:
        if rel.startswith(prefix):
            return kind
    return "Page"


def pages() -> list[Path]:
    found = list(ui.public_pages())
    for name in EXTRA_DIRS:
        base = ROOT / name
        if base.is_dir():
            found.extend(p for p in base.rglob("*.html") if not (ui.SKIP_PARTS & set(p.relative_to(ROOT).parts)))
    return found


def main() -> int:
    rows, seen = [], set()
    for page in sorted(pages()):
        rel = page.relative_to(ROOT).as_posix()
        if rel in ui.SKIP_REL or rel.startswith("embed/"):
            continue
        head = page.read_text(encoding="utf-8", errors="replace")[:6000]
        if ui.is_redirect(head) or re.search(r'name="robots"[^>]*noindex', head):
            continue
        m = TITLE_RE.search(head)
        if not m:
            continue
        title = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip()
        for _ in range(2):
            title = SUFFIX_RE.sub("", title).strip()
        url = "/" + (rel[:-len("index.html")] if rel.endswith("/index.html") or rel == "index.html" else rel)
        title = title.split(" | ")[0].replace(" -- ", ": ").strip()
        halves = title.split(" — ")
        if len(halves) == 2 and halves[0] == halves[1]:
            title = halves[0]
        if not title or url in seen:
            continue
        seen.add(url)
        rows.append([title, url, page_type(rel)])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8", newline="\n")
    print(f"search index: {len(rows)} pages, {OUT.stat().st_size // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
