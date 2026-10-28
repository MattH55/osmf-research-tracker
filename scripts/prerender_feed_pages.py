#!/usr/bin/env python3
"""Pre-render the condition feed pages (lyme.html, long-covid.html, ...).

Those pages fetch ./data/<key>.json in the browser, so a crawler (or a
visitor whose fetch fails) saw "Loading studies…" / "Failed to load data"
and no studies. This writes the most recent MAX_STUDIES studies and a short
summary computed from the same JSON straight into the HTML. The page's
script still replaces the list with the full, searchable one on load.

    python scripts/prerender_feed_pages.py            # every feed page
    python scripts/prerender_feed_pages.py lyme.html  # one page

Idempotent: content sits between OSMF_PRERENDER / OSMF_FEED_SUMMARY markers
and is replaced on each run. No network.
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_STUDIES = 30
EXCERPT = 380
P_START, P_END = "<!-- OSMF_PRERENDER_START -->", "<!-- OSMF_PRERENDER_END -->"
S_START, S_END = "<!-- OSMF_FEED_SUMMARY_START -->", "<!-- OSMF_FEED_SUMMARY_END -->"


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def fmt_day(iso: str) -> str:
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00")).date() if "T" in iso else date.fromisoformat(iso[:10])
        return f"{d:%b} {d.day}, {d.year}"
    except Exception:
        return iso[:10]


def card(s: dict) -> str:
    ab = s.get("abstract") or ""
    excerpt = ab if len(ab) <= EXCERPT else ab[:375] + "..."
    url = s.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{s.get('pmid')}/" if s.get("pmid") else "")
    return (f'<div class="study-card"><a href="{esc(url)}" target="_blank" rel="noopener" class="study-title">{esc(s.get("title"))}</a>'
            f'<div class="study-meta"><span>&#128197; {esc(s.get("pub_date") or "Date unknown")}</span><span class="study-meta-sep">•</span>'
            f'<span>{esc(s.get("journal") or "Journal unknown")}</span></div>'
            f'<div class="study-authors">{esc(s.get("authors") or "Authors not listed")}</div>'
            f'<div class="study-abstract-wrap"><span class="abstract-excerpt">{esc(excerpt)}</span></div>'
            f'<div class="study-footer"><a href="{esc(url)}" target="_blank" rel="noopener" class="btn-pubmed">View on PubMed ↗</a>'
            f'<span class="pmid-label">PMID: {esc(s.get("pmid"))}</span></div></div>')


def summary(label: str, studies: list[dict], updated: str, shown: int) -> str:
    dates = sorted(s["pub_date"][:10] for s in studies if re.match(r"\d{4}-\d{2}-\d{2}", s.get("pub_date") or ""))
    journals = Counter((s.get("journal") or "").strip() for s in studies if (s.get("journal") or "").strip())
    top = [(j, n) for j, n in journals.most_common(3) if n > 1]
    span = f", published between {fmt_day(dates[0])} and {fmt_day(dates[-1])}" if dates else ""
    jtxt = ""
    if top:
        parts = [f"<em>{esc(j)}</em> ({n})" for j, n in top]
        jtxt = (" Journals with the most studies in this set: "
                + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + ".")
    upd = f" List refreshed {fmt_day(updated)} from PubMed." if updated else ""
    return (f'{S_START}<p class="feed-summary"><strong>Latest research:</strong> this page tracks {len(studies)} '
            f'studies on {esc(label)} indexed in PubMed{span}. The {shown} most recent are listed below; '
            f'the search box filters the full list.{jtxt}{upd}</p>{S_END}')


def process(page: Path) -> str:
    markup = page.read_text(encoding="utf-8")
    m = re.search(r"const DATA_URL = '\./data/([a-z0-9-]+)\.json'", markup)
    if not m:
        return "not a feed page"
    data_path = ROOT / "data" / f"{m.group(1)}.json"
    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except Exception as e:
        return f"skipped ({data_path.name}: {e})"
    studies = [s for s in payload.get("studies", []) if isinstance(s, dict) and s.get("title")]
    if not studies:
        return "no studies"
    studies.sort(key=lambda s: s.get("pub_date") or "", reverse=True)
    shown = studies[:MAX_STUDIES]
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", markup, re.S)
    label = html.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip() if h1 else m.group(1)
    updated = payload.get("last_updated") or ""
    original = markup

    block = P_START + "".join(card(s) for s in shown) + P_END
    if P_START in markup:
        markup = re.sub(re.escape(P_START) + r".*?" + re.escape(P_END), lambda _: block, markup, count=1, flags=re.S)
    else:
        markup = markup.replace('<div id="studies-container"></div>', f'<div id="studies-container">{block}</div>', 1)

    summ = summary(label, studies, updated, len(shown))
    if S_START in markup:
        markup = re.sub(re.escape(S_START) + r".*?" + re.escape(S_END), lambda _: summ, markup, count=1, flags=re.S)
    else:
        markup = re.sub(r'(<p class="condition-desc">.*?</p>)', lambda mm: mm.group(1) + "\n\n    " + summ, markup, count=1, flags=re.S)

    markup = re.sub(r'<span id="study-count">[^<]*</span>', f'<span id="study-count">{len(studies)}</span>', markup, count=1)
    if updated:
        markup = re.sub(r'<span id="last-updated">[^<]*</span>', f'<span id="last-updated">• Updated {esc(fmt_day(updated))}</span>', markup, count=1)
    # keep the pre-rendered list visible while loading and if the fetch fails
    markup = markup.replace("loading.classList.remove('hidden'); container.innerHTML = '';",
                            "if (!container.children.length) loading.classList.remove('hidden');", 1)
    markup = markup.replace("catch(e){ console.error(e); loading.classList.add('hidden'); error.classList.remove('hidden'); }",
                            "catch(e){ console.error(e); loading.classList.add('hidden'); if (!container.children.length) error.classList.remove('hidden'); }", 1)
    markup = markup.replace("    loading.classList.remove('hidden');\n    container.innerHTML = '';\n",
                            "    if (!container.children.length) loading.classList.remove('hidden');\n", 1)
    markup = markup.replace("      loading.classList.add('hidden');\n      error.classList.remove('hidden');\n",
                            "      loading.classList.add('hidden');\n      if (!container.children.length) error.classList.remove('hidden');\n", 1)
    if ".feed-summary{" not in markup:
        markup = markup.replace("</head>", "<style>.feed-summary{font-size:.98rem;line-height:1.65;margin:0 0 1.2rem}</style>\n</head>", 1)
    if markup != original:
        page.write_text(markup, encoding="utf-8")
        return f"{len(shown)} of {len(studies)} studies pre-rendered"
    return "unchanged"


def main() -> None:
    names = sys.argv[1:]
    pages = [ROOT / n for n in names] if names else sorted(ROOT.glob("*.html"))
    for p in pages:
        if "const DATA_URL = './data/" in p.read_text(encoding="utf-8"):
            print(f"{p.name}: {process(p)}")


if __name__ == "__main__":
    main()
