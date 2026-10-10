#!/usr/bin/env python3
"""Check that every evidence quote in the verification results appears on
its cited page.

For each (url, quote) pair it fetches the page once (cached on disk), strips
markup, normalises whitespace/quotes/case, and looks for the quote: exact
substring first, then a token-window match (>= 85% of the quote's words in
order within a window), which tolerates ellipses and whitespace changes.

Outcome per pair: found | not_found | unfetchable (blocked/PDF/timeouts).
Writes data/verification/quote-check-<batch>.json and prints a summary.

    python scripts/check_quotes.py results/state-compacts.jsonl [...]
"""
from __future__ import annotations

import concurrent.futures as cf
import hashlib
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VER = ROOT / "data" / "verification"
CACHE = VER / ".page-cache"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def norm(s: str) -> str:
    s = html.unescape(s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace(" ", " ").replace("§", " § ")
    s = re.sub(r"[^\w§$%.'\-]+", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def fetch(url: str) -> str | None:
    CACHE.mkdir(exist_ok=True)
    key = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".txt")
    if key.exists():
        t = key.read_text(encoding="utf-8")
        return None if t == "\0UNFETCHABLE" else t
    text = None
    raw, ctype = None, ""
    archive = "web.archive.org" in url
    ua = "osmf-quote-check/1.0 (+https://research.opensourcemed.info/maps/methodology.html)" if archive else UA
    for attempt in range(4 if archive else 2):   # the Internet Archive is slow and rate-limits bursts
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "*/*"})
            with urllib.request.urlopen(req, timeout=75) as r:
                raw = r.read(8_000_000)
                ctype = r.headers.get("Content-Type", "")
            break
        except urllib.error.HTTPError as e:
            raw = None
            if e.code == 429:
                time.sleep(15 * (attempt + 1))
            elif e.code in (404, 403, 410):
                break
        except Exception:
            raw = None
    try:
        if raw is None:
            raise IOError("fetch failed")
        if "pdf" in ctype or url.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader  # optional
                text = " ".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(raw)).pages)
            except Exception:
                text = None
        else:
            body = raw.decode("utf-8", errors="replace")
            body = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", body, flags=re.S | re.I)
            text = re.sub(r"<[^>]+>", " ", body)
    except Exception:
        text = None
    if text:                          # never cache failures: they are often transient
        key.write_text(text, encoding="utf-8")
    return text


def contains(page: str, quote: str) -> bool:
    if _contains(page, quote):
        return True
    # Map/table rows are often quoted as "State (bill): status ..." where the
    # page keys the row by state code; retry without the leading state label.
    m = re.match(r"^\s*[A-Z][A-Za-z .]{1,30}\s*\((.+?)\)\s*:?\s*(.*)$", quote, re.S)
    if m:
        return _contains(page, f"{m.group(1)} {m.group(2)}")
    m = re.match(r"^\s*[A-Z]{2}\s*:\s*(.+)$", quote, re.S)   # "AK: No pending ..."
    return bool(m) and _contains(page, m.group(1))


def _contains(page: str, quote: str) -> bool:
    p, q = norm(page), norm(quote)
    if not q:
        return False
    if q in p:
        return True
    # tolerate ellipses / small edits: ordered token match inside a window
    parts = [x for x in re.split(r"\s*\.\.\.\s*|\s*…\s*", q) if x]
    if parts and all(part in p for part in parts):
        return True
    qt, pt = q.split(), p.split()
    if len(qt) < 4:
        return False
    need = int(len(qt) * 0.85 + 0.999)
    first = qt[0]
    for i, tok in enumerate(pt):
        if tok != first:
            continue
        j, hit = i, 0
        for w in qt:
            k = j
            while k < min(len(pt), i + len(qt) * 2) and pt[k] != w:
                k += 1
            if k < min(len(pt), i + len(qt) * 2):
                hit += 1; j = k + 1
        if hit >= need:
            return True
    return False


def rendered_corpus(urls: list[str]) -> dict[str, str]:
    """Render pages in Chrome and collect the page text plus every text-like
    network response (JSON, JS, data files) and frame.  Interactive maps keep
    their state-by-state facts in such files (e.g. IMLCC map.js, NLC
    NewNurseCompactData.txt), so a quote that is not in the static HTML may
    still be genuinely on the page."""
    out: dict[str, str] = {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return out
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        for url in urls:
            ctx = b.new_context(user_agent=UA)
            pg = ctx.new_page(); bodies = []
            def on_resp(r, bodies=bodies):
                try:
                    ct = r.headers.get("content-type") or ""
                    if any(t in ct for t in ("json", "javascript", "html", "text", "xml")):
                        bodies.append(r.text())
                except Exception:
                    pass
            pg.on("response", on_resp)
            try:
                pg.goto(url, wait_until="networkidle", timeout=60000); pg.wait_for_timeout(2500)
                bodies.append(pg.inner_text("body"))
                for fr in pg.frames:
                    try: bodies.append(fr.inner_text("body"))
                    except Exception: pass
            except Exception:
                pass
            out[url] = "\n".join(bodies)
            ctx.close()
        b.close()
    return out


def pairs_from(line: dict):
    if line.get("evidence_url"):
        yield line.get("key") or line.get("id"), line["evidence_url"], line.get("evidence_quote") or ""
    for e in line.get("evidence") or []:
        if isinstance(e, dict) and e.get("url"):
            yield line.get("id") or line.get("key"), e["url"], e.get("quote") or ""


def main() -> int:
    files = [Path(a) if Path(a).is_absolute() else VER / a for a in sys.argv[1:]]
    for f in files:
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        pairs = [p for r in rows if r.get("verdict", "x") != "unsupported" for p in pairs_from(r)]
        urls = sorted({u for _, u, _ in pairs})
        with cf.ThreadPoolExecutor(8) as ex:
            pages = dict(zip(urls, ex.map(fetch, urls)))
        out = {"found": [], "not_found": [], "unfetchable": []}
        pending = []
        for key, url, quote in pairs:
            page = pages.get(url)
            if page is not None and contains(page, quote):
                out["found"].append({"key": key, "url": url, "via": "static"})
            else:
                pending.append((key, url, quote))
        # second pass: rendered page + its data files, for anything not found statically
        rendered = rendered_corpus(sorted({u for _, u, _ in pending})) if pending else {}
        # third source: the Internet Archive copy, for pages that block bots
        # (Mercatus, NCSL, Justia...) or that the agent read via Wayback
        # any URL whose quote is still unmatched (bot-challenge pages are not
        # empty, so emptiness is not a reliable "blocked" signal)
        blocked = sorted({u for _, u, q in pending if not contains(rendered.get(u) or "", q)})
        with cf.ThreadPoolExecutor(2) as ex:
            archived = dict(zip(blocked, ex.map(lambda u: fetch(u if "web.archive.org" in u else
                                                              f"https://web.archive.org/web/2026id_/{u}"), blocked)))
        for key, url, quote in pending:
            corpus = (rendered.get(url) or "") + " " + (archived.get(url) or "")
            if len(norm(corpus)) >= 1500 and contains(corpus, quote):
                out["found"].append({"key": key, "url": url, "via": "archive" if url in archived and contains(archived.get(url) or "", quote) else "rendered"})
            elif len(norm(corpus)) < 1500 and len(norm(pages.get(url) or "")) < 1500:
                out["unfetchable"].append({"key": key, "url": url})
            else:
                out["not_found"].append({"key": key, "url": url, "quote": quote[:200]})
        (VER / f"quote-check-{f.stem}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        n = len(pairs)
        print(f"{f.stem}: {n} quotes | found {len(out['found'])} | NOT FOUND {len(out['not_found'])} | "
              f"unfetchable {len(out['unfetchable'])} | distinct urls {len(urls)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
