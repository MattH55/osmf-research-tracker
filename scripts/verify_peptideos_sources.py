#!/usr/bin/env python3
"""Check every PeptideOS citation against its source of record.

  DOI   -> Crossref title must match the recorded title
  PMID  -> PubMed (E-utilities) title must match
  NCT   -> ClinicalTrials.gov brief or official title must match
  regulatory / WADA quote -> must appear on the cited page (static fetch, then Internet Archive copy)

Writes peptideos/data/source-check.json. build_peptideos.py refuses to publish while
any DOI/PMID/NCT failure is listed. Quotes that cannot be confirmed are listed as
`quote_unconfirmed` for manual audit (many regulator pages are script-rendered).

    python scripts/verify_peptideos_sources.py [slug ...]
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from peptideos_lib import DATA, PEP, PRIMARY_DOMAINS, host_ok  # noqa: E402

OUT = PEP / "data" / "source-check.json"
_RENDER_LOCK = threading.Lock()
BROWSER_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
UA = {"User-Agent": "OSMF-PeptideOS-verifier/1.0 (mailto:contact@opensourcemed.info)"}


def norm(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    # keep non-Latin text (PMDA Japanese, Greek letters); drop accents and punctuation only
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[\W_]+", " ", s.lower()).strip()


def same(a: str, b: str) -> bool:
    a, b = norm(a), norm(b)
    return bool(a) and (a == b or SequenceMatcher(None, a, b).ratio() >= 0.93)


def get(url: str, timeout=40) -> bytes:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                body = r.read()
            if body:
                return body
            # some sites (WADA) answer an empty 202 bot challenge unless the client looks like a browser
            with urllib.request.urlopen(urllib.request.Request(url, headers=BROWSER_UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 2:
                time.sleep(5 * (attempt + 1)); continue
            raise


def doi_title(doi: str) -> str:
    j = json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))
    t = j["message"].get("title") or [""]
    return t[0]


def pmid_title(pmid) -> str:
    j = json.loads(get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id={pmid}"))
    return j["result"][str(pmid)]["title"]


def nct_titles(nct: str) -> list[str]:
    j = json.loads(get(f"https://clinicaltrials.gov/api/v2/studies/{nct}?fields=IdentificationModule"))
    m = j["protocolSection"]["identificationModule"]
    return [m.get("briefTitle", ""), m.get("officialTitle", "")]


def as_text(raw: bytes) -> str:
    if raw[:5] == b"%PDF-":
        import io
        from pypdf import PdfReader
        return " ".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(raw)).pages)
    if raw[:2] == b"PK":  # xlsx (PMDA approval lists)
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True)
        return " ".join(str(c) for ws in wb for row in ws.iter_rows(values_only=True) for c in row if c)
    return raw.decode("utf-8", "ignore")


def found(q: str, text: str) -> bool:
    text = norm(text)
    if q in text:
        return True
    # tolerate a mangled word or two (PDF hyphenation, table cells): 80% of 6-word windows present
    words = q.split()
    wins = [" ".join(words[i:i + 6]) for i in range(0, max(1, len(words) - 5), 3)]
    return bool(wins) and sum(w in text for w in wins) / len(wins) >= 0.8


_RENDER_CACHE: dict[str, str] = {}


def rendered(url: str) -> str:
    """Script-rendered pages and bot-shy PDFs (WADA, EMA, Health Canada): fetch once through Chrome."""
    if url in _RENDER_CACHE:
        return _RENDER_CACHE[url]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)  # temp profile, removed on close
        try:
            ctx = b.new_context()
            if url.lower().split("?")[0].endswith(".pdf"):
                home = "/".join(url.split("/")[:3]) + "/"
                pg = ctx.new_page()
                pg.goto(home, wait_until="domcontentloaded", timeout=90000)
                text = as_text(ctx.request.get(url, timeout=90000).body())
            else:
                pg = ctx.new_page()
                pg.goto(url, wait_until="networkidle", timeout=90000)
                pg.wait_for_timeout(8000)  # legislation.gov.au streams the instrument into a blob: frame
                text = " ".join(f.evaluate("() => document.body ? document.body.innerText : ''") for f in pg.frames)
        finally:
            b.close()
    _RENDER_CACHE[url] = text
    return text


def quote_on_page(url: str, quote: str) -> bool:
    q = norm(quote)
    if not q:
        return False
    for u in (url, "https://web.archive.org/web/2026id_/" + url):
        try:
            if found(q, as_text(get(u, timeout=60))):
                return True
        except Exception:
            continue
    try:
        with _RENDER_LOCK:
            return found(q, rendered(url))
    except Exception:
        return False


def check(rec: dict) -> dict:
    slug, fails, unconf, ok = rec["slug"], [], [], 0
    cites = []
    for ev in rec.get("evidence") or []:
        cites += ev.get("citations") or []
    cites += [s["citation"] for s in (rec.get("safety") or {}).get("known_signals") or [] if s.get("citation")]
    for c in cites:
        try:
            if c.get("doi"):
                t = doi_title(c["doi"])
                if same(t, c["title"]): ok += 1
                else: fails.append({"slug": slug, "what": f"DOI {c['doi']} title mismatch: recorded '{c['title'][:80]}' vs Crossref '{t[:80]}'"})
            elif c.get("url"):
                if not host_ok(c["url"], PRIMARY_DOMAINS):
                    fails.append({"slug": slug, "what": f"non-DOI citation must be a primary regulator page: {c['url']}"})
                elif quote_on_page(c["url"], c["title"]): ok += 1
                else: unconf.append({"slug": slug, "jurisdiction": "citation", "url": c["url"], "quote": c["title"]})
            elif c.get("pmid"):
                t = pmid_title(c["pmid"])
                if same(t, c["title"]): ok += 1
                else: fails.append({"slug": slug, "what": f"PMID {c['pmid']} title mismatch: '{c['title'][:80]}' vs '{t[:80]}'"})
        except Exception as ex:
            fails.append({"slug": slug, "what": f"citation {c.get('doi') or c.get('pmid')} did not resolve ({ex.__class__.__name__}: {str(ex)[:60]})"})
    for t in rec.get("trials") or []:
        try:
            if any(same(x, t["title"]) for x in nct_titles(t["nct"])): ok += 1
            else: fails.append({"slug": slug, "what": f"{t['nct']} title mismatch: '{t['title'][:80]}'"})
        except Exception as ex:
            fails.append({"slug": slug, "what": f"{t['nct']} did not resolve ({ex.__class__.__name__})"})
    quotes = [(r["source_url"], r["quote"], r["jurisdiction"]) for r in rec.get("regulatory") or []]
    if rec.get("sport"):
        quotes.append((rec["sport"]["source_url"], rec["sport"].get("quote", ""), "WADA"))
    for url, q, j in quotes:
        if quote_on_page(url, q): ok += 1
        else: unconf.append({"slug": slug, "jurisdiction": j, "url": url, "quote": q})
    return {"slug": slug, "ok": ok, "failures": fails, "quote_unconfirmed": unconf}


def main() -> int:
    only = set(sys.argv[1:])
    recs = [yaml.safe_load(f.read_text(encoding="utf-8")) for f in sorted(DATA.glob("*.yaml"))]
    recs = [r for r in recs if not only or r["slug"] in only]
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    per = {x["slug"]: x for x in prev.get("records", [])}
    with ThreadPoolExecutor(4) as ex:
        for res in ex.map(check, recs):
            per[res["slug"]] = res
            print(f"{res['slug']:22} ok={res['ok']:3} fail={len(res['failures'])} quote?={len(res['quote_unconfirmed'])}")
    manual = prev.get("manual_quote_confirmations", [])
    confirmed = {(m["slug"], m["url"]) for m in manual}
    recs_out = sorted(per.values(), key=lambda x: x["slug"])
    out = {"checked": date.today().isoformat(), "records": recs_out,
           "failures": [f for r in recs_out for f in r["failures"]],
           "quote_unconfirmed": [q for r in recs_out for q in r["quote_unconfirmed"] if (q["slug"], q["url"]) not in confirmed],
           "manual_quote_confirmations": manual}
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(out['failures'])} hard failures, {len(out['quote_unconfirmed'])} quotes need manual confirmation -> {OUT}")
    return 1 if out["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
