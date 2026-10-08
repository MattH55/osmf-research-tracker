#!/usr/bin/env python3
"""Repair metadata that scripts/fix_site_audit_issues.py cut at a fixed length.

That script sliced <title> and twitter:title at 60 characters and the meta
description at 155, splitting words and HTML entities ("&amp" with no
semicolon) and leaving fragments like "... Biomarker Atlas |".  It left
og:title alone, so the full title is usually still on the page.

Repairs, per page:
  * <title>       <- og:title when the current title is a cut-off prefix of it
  * twitter:title <- same rule
  * description   <- og:description when the current one ends in "..." and
                     og:description is the longer, same-opening text
  * og/twitter:description <- meta description when they hold navigation
                     text ("← All cohorts ...")
  * any title still ending in a dangling "—", "|", "&", "&amp" or "-" is
    trimmed back to the last complete phrase

    python scripts/fix_truncated_meta.py            # apply
    python scripts/fix_truncated_meta.py --dry-run
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIRS = (
    "pais-cohorts", "disease-intelligence", "ntd", "biomarkers", "compare",
    "trials", "pairs", "digest", "reports", "tools", "embed",
)
# chronic-disease-interventions is handled by seo_disease_pages.py
EXCLUDED_NAMES = {"agents-local.html", "clinical_trials-local.html"}
DANGLING = ("—", "–", "|", "&", "&amp", "-", ",", ":", "·")


def pages() -> list[Path]:
    out = [p for p in ROOT.glob("*.html") if p.name not in EXCLUDED_NAMES and not p.name.startswith("local")]
    for d in PUBLIC_DIRS:
        out += [p for p in (ROOT / d).rglob("*.html") if p.name not in EXCLUDED_NAMES]
    return sorted(out)


def attr(markup: str, pattern: str) -> str | None:
    m = re.search(pattern, markup, re.I | re.S)
    return html.unescape(m.group(1)) if m else None


def set_attr(markup: str, pattern: str, value: str) -> str:
    def repl(m: re.Match) -> str:
        return m.group(0).replace(m.group(1), html.escape(value, quote=True), 1)
    return re.sub(pattern, repl, markup, count=1, flags=re.I | re.S)


def cut_prefix(short: str, full: str) -> bool:
    """True if `short` looks like `full` chopped at a fixed length."""
    if not short or not full or len(full) <= len(short):
        return False
    s = short.rstrip(" .").rstrip()
    for d in DANGLING:
        if s.endswith(d):
            s = s[: -len(d)].rstrip()
    return len(s) >= 12 and full.startswith(s)


def trim_dangling(title: str) -> str:
    t = title.strip()
    changed = True
    while changed:
        changed = False
        for d in DANGLING:
            if t.endswith(d):
                t = t[: -len(d)].rstrip()
                changed = True
    return t


T_TITLE = r"<title>(.*?)</title>"
T_OG_TITLE = r'<meta property="og:title" content="([^"]*)"'
T_TW_TITLE = r'<meta name="twitter:title" content="([^"]*)"'
T_DESC = r'<meta name="description" content="([^"]*)"'
T_OG_DESC = r'<meta property="og:description" content="([^"]*)"'
T_TW_DESC = r'<meta name="twitter:description" content="([^"]*)"'


def repair(page: Path, dry: bool) -> list[str]:
    markup = page.read_text(encoding="utf-8")
    original = markup
    notes: list[str] = []

    title = attr(markup, T_TITLE) or ""
    og_title = attr(markup, T_OG_TITLE) or ""
    tw_title = attr(markup, T_TW_TITLE) or ""

    if cut_prefix(title, og_title):
        markup = set_attr(markup, T_TITLE, og_title)
        title = og_title
        notes.append("title<-og")
    elif trim_dangling(title) != title.strip():
        title = trim_dangling(title)
        markup = set_attr(markup, T_TITLE, title)
        notes.append("title trimmed")

    if tw_title and (cut_prefix(tw_title, title) or trim_dangling(tw_title) != tw_title.strip()):
        markup = set_attr(markup, T_TW_TITLE, title)
        notes.append("twitter:title")

    desc = attr(markup, T_DESC) or ""
    og_desc = attr(markup, T_OG_DESC) or ""
    tw_desc = attr(markup, T_TW_DESC) or ""

    if desc.endswith("...") and len(og_desc) > len(desc) - 3 and og_desc[:40] == desc[:40]:
        full = og_desc
        if len(full) > 160:
            full = full[:160].rsplit(" ", 1)[0].rstrip(",;:") + "."
        markup = set_attr(markup, T_DESC, full)
        desc = full
        notes.append("desc<-og")

    for label, pat, val in (("og:description", T_OG_DESC, og_desc), ("twitter:description", T_TW_DESC, tw_desc)):
        if val and (val.startswith("←") or val.endswith("...")) and desc and not desc.endswith("..."):
            markup = set_attr(markup, pat, desc)
            notes.append(label)

    if markup != original and not dry:
        page.write_text(markup, encoding="utf-8")
    return notes


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    changed = 0
    for p in pages():
        notes = repair(p, args.dry_run)
        if notes:
            changed += 1
            print(f"{p.relative_to(ROOT)}: {', '.join(notes)}")
    print(f"\n{changed} pages {'would change' if args.dry_run else 'repaired'}")


if __name__ == "__main__":
    main()
