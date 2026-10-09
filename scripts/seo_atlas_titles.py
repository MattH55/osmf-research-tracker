#!/usr/bin/env python3
"""Search-intent titles and descriptions for the <slug>-biomarkers.html atlases.

Search Console (Oct 2026) showed "migraine biomarker test" landing at
position ~56 against an "X Biomarker Atlas | Blood Tests & Molecular
Alterations" title: "atlas" is our word, not the searcher's.  This rewrites
page.title / page.description in data/biomarkers/<slug>.json (so
generate_atlas_html.py and build-atlases.js keep them on regeneration) and
patches the same tags in the HTML.

    python scripts/seo_atlas_titles.py            # apply
    python scripts/seo_atlas_titles.py --dry-run  # report only
"""
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "biomarkers"
MAX_TITLE = 65
MAX_DESC = 158
NON_ATLAS = {"search-index", "agent-discovery", "outcome-ontology", "commercial-links",
             "consumable-links", "intervention-links", "trial-links"}

# Search-friendly short names where the data's condition name is long.
SHORT = {
    "gerd-gastroesophageal-reflux-disease": "GERD (Acid Reflux)",
    "inflammatory-bowel-disease-crohn-s-uc": "IBD (Crohn's & Colitis)",
    "nafld-mash-metabolic-associated-steatohepatitis": "Fatty Liver (NAFLD/MASH)",
    "alzheimer-s-disease-and-other-dementias": "Alzheimer's & Dementia",
    "copd": "COPD",
    "pacvs": "PACVS (Post-Vaccine Syndrome)",
    "gulf-war-illness": "Gulf War Illness",
    "lyme": "Chronic Lyme (PTLDS)",
}


def build_title(name: str, short: str, n: int) -> str:
    for who in (name, short):
        for pattern in (
            f"{who} Biomarkers: {n} Blood Tests & Lab Markers",
            f"{who} Biomarkers: {n} Blood & Lab Tests",
            f"{who} Biomarkers & Blood Tests ({n})",
        ):
            if len(pattern) <= MAX_TITLE:
                return pattern
    return f"{short} Biomarkers & Blood Tests"[:MAX_TITLE]


def build_desc(name: str, short: str, n: int) -> str:
    for tail in (
        "high or low, the comparison group and the source study for each.",
        "direction, comparison group and source for each.",
        "each with its source study.",
    ):
        for who in (name, short):
            desc = f"Which blood tests and biomarkers change in {who}? {n} markers from peer-reviewed studies: {tail}"
            if len(desc) <= MAX_DESC:
                return desc
    return f"{n} {short} biomarkers and blood tests from peer-reviewed studies, with sources."[:MAX_DESC]


def patch_html(markup: str, title: str, desc: str) -> str:
    t, d = html.escape(title, quote=True), html.escape(desc, quote=True)
    subs = [
        (r"<title>.*?</title>", f"<title>{t}</title>"),
        (r'<meta name="description" content="[^"]*"[^>]*>', f'<meta name="description" content="{d}">'),
        (r'<meta property="og:title" content="[^"]*"[^>]*>', f'<meta property="og:title" content="{t}">'),
        (r'<meta property="og:description" content="[^"]*"[^>]*>', f'<meta property="og:description" content="{d}">'),
        (r'<meta name="twitter:title" content="[^"]*"[^>]*>', f'<meta name="twitter:title" content="{t}">'),
        (r'<meta name="twitter:description" content="[^"]*"[^>]*>', f'<meta name="twitter:description" content="{d}">'),
    ]
    for pat, rep in subs:
        markup = re.sub(pat, lambda _m, rep=rep: rep, markup, count=1, flags=re.I | re.S)
    return markup


def dump_like(raw: bytes, data: dict) -> bytes:
    """Serialise data in the same style as the original file (indent, ASCII
    escaping, newline convention, trailing newline) so the diff only shows
    the fields that actually changed."""
    original = json.loads(raw)
    nl = b"\r\n" if b"\r\n" in raw else b"\n"
    trail = nl if raw.endswith(nl) else b""
    for indent in (2, 4, None):
        for ascii_ in (False, True):
            if json.dumps(original, ensure_ascii=ascii_, indent=indent).encode("utf-8").replace(b"\n", nl) + trail == raw:
                return json.dumps(data, ensure_ascii=ascii_, indent=indent).encode("utf-8").replace(b"\n", nl) + trail
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8").replace(b"\n", nl) + trail


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    changed = 0
    for path in sorted(DATA.glob("*.json")):
        slug = path.stem
        if slug in NON_ATLAS:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "markers" not in data or "page" not in data:
            continue
        page_html = ROOT / f"{slug}-biomarkers.html"
        name = data["condition"].get("shortName") or data["condition"]["name"]
        short = SHORT.get(slug, name)
        n = len(data["markers"])
        title, desc = build_title(name, short, n), build_desc(name, short, n)
        print(f"{slug}: [{len(title)}] {title}\n    [{len(desc)}] {desc}")
        if args.dry_run:
            continue
        if data["page"].get("title") != title or data["page"].get("description") != desc:
            data["page"]["title"], data["page"]["description"] = title, desc
            path.write_bytes(dump_like(path.read_bytes(), data))
            changed += 1
        if page_html.exists():
            markup = page_html.read_text(encoding="utf-8")
            new = patch_html(markup, title, desc)
            if new != markup:
                page_html.write_text(new, encoding="utf-8")
                changed += 1
    print(f"{changed} files updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
