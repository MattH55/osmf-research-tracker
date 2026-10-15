#!/usr/bin/env python3
"""
Ingest hospital prices directly from hospitals' own machine-readable files (MRFs),
published under 45 CFR Part 180 and listed in https://<hospital site>/cms-hpt.txt.

Per hospital (CCN) in data/cms/hospital-sites.json (see discover_hospital_sites.py):
  1. Fetch cms-hpt.txt from each candidate site's origin (https://host, then
     https://www.<domain>, then https://<domain>), honouring robots.txt.
  2. Keep ONLY entries whose location-name strictly matches this CCN through
     price_contract.StrictHospitalMatcher (an entry for another campus or a
     system-wide name is never attached).
  3. Stream-download each matched https MRF (hard size cap, disk guard), then
     stream-parse it (CSV tall/wide, JSON v2/v3; gzip/zip handled; JSON via ijson)
     keeping only lines whose explicit codes belong to data/seed/procedures.json.
  4. Write a compact extract data/mrf/extracts/<CCN>-<sha256(url)[:12]>.json.gz
     (candidate lines + provenance) and DELETE the downloaded file.

Outputs are always rebuilt from the extracts on disk, so a networked run and
--offline produce byte-identical data/cms/mrf-prices.json, mrf-meta.json and the
"hospital_mrf" section of data/cms/quarantine.json. All price rules come from
etl/price_contract.py (explicit code types, canonical scope, cash = discounted
cash only, dollar payer rates, bounds, vintage = the file's last_updated_on).

Resume (--batch): data/cms/mrf-progress.json holds {nextIndex, orderHash, failed,
done}. The order is the sorted CCN list of hospital-sites.json. Every entry before
nextIndex is in done or failed; a hospital is never skipped or processed twice in
a cycle. If discovery changes the order, progress is re-based by CCN (done/failed
are keyed by CCN, so nothing is skipped or repeated). When a cycle is complete a
new one starts after --new-cycle-after-days (MRFs are refreshed; unchanged files
cost one conditional GET).

USAGE:
  python etl/ingest_mrf_prices.py --batch --max-minutes 50 --workers 4 --min-free-gb 6
  python etl/ingest_mrf_prices.py --batch --limit 15 --max-minutes 25
  python etl/ingest_mrf_prices.py --hospital 330214
  python etl/ingest_mrf_prices.py --retry-failed --limit 20
  python etl/ingest_mrf_prices.py --offline          # rebuild outputs from extracts only
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import random
import re
import shutil
import sys
import threading
import time
import urllib.robotparser
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mrf_parsers import UnsupportedFormat, iter_mrf, looks_like_cms_hpt, parse_cms_hpt  # noqa: E402
from price_contract import (  # noqa: E402
    CMS_DIR,
    ROOT,
    CodeIndex,
    Quarantine,
    StrictHospitalMatcher,
    aggregate_lines,
    atomic_write_text,
    blocked_reason,
    contract_problems,
    deterministic_id,
    dump_json,
    is_stale,
    line_scope_problem,
    load_hospitals,
    order_row,
    parse_iso_date,
    read_json,
    read_json_gz,
    write_json_gz,
    write_quarantine_section,
)

MRF_DIR = ROOT / "data" / "mrf"
EXTRACT_DIR = MRF_DIR / "extracts"
DOWNLOAD_DIR = MRF_DIR / "downloads"
SITES_JSON = CMS_DIR / "hospital-sites.json"
PROGRESS_JSON = CMS_DIR / "mrf-progress.json"
OUT_PRICES = CMS_DIR / "mrf-prices.json"
OUT_META = CMS_DIR / "mrf-meta.json"
RUN_LOCK = CMS_DIR / ".mrf-ingest.lock"
QUARANTINE_SECTION = "hospital_mrf"
EXTRACT_VERSION = 1
MAX_WORKERS = 4
MAX_CANDIDATES = 4          # candidate websites tried per hospital
MAX_MRFS_PER_HOSPITAL = 4   # matched cms-hpt entries downloaded per hospital
HPT_MAX_BYTES = 5 * 1024 * 1024
HOST_MIN_INTERVAL = 1.0     # seconds between requests to one host
EXTRACT_NAME_RE = re.compile(r"^([0-9A-Z]{6})-([0-9a-f]{12})\.json\.gz$")
ROBOTS_AGENT = "OpenSourceMed-HospitalCompare"
USER_AGENT = ("OpenSourceMed-HospitalCompare/1.0 (+https://opensourcemed.info; contact@opensourcemed.info) "
              "hospital-price-transparency-ingest (45 CFR 180)")
DEDUPE_RULE = ("one row per CMS hospital + procedure: the most recent priceVintage wins, then more "
               "accepted MRF lines, then the lexically smallest mrfUrl; losers are quarantined as "
               "row:duplicate_superseded")


def log(msg: str) -> None:
    print(msg, flush=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================ errors

class Failure(Exception):
    """A per-hospital or per-file failure with a short machine reason."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail

    def text(self) -> str:
        return (f"{self.reason}: {self.detail}" if self.detail else self.reason)[:200]


class Aborted(Exception):
    """Hard time limit hit mid-download; the hospital is left unprocessed."""


class DiskLow(Exception):
    pass


# ============================================================ politeness

class HostGate:
    """At most one request in flight per host, and a pause between requests."""

    def __init__(self, min_interval: float = HOST_MIN_INTERVAL):
        self.locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self.last: dict[str, float] = {}
        self.meta = threading.Lock()
        self.min_interval = min_interval

    def hold(self, url: str):
        host = (urlparse(url).hostname or "").lower()
        with self.meta:
            lock = self.locks[host]
        gate = self

        class _Ctx:
            def __enter__(self_inner):
                lock.acquire()
                wait_s = gate.last.get(host, 0) + gate.min_interval - time.monotonic()
                if wait_s > 0:
                    time.sleep(wait_s)

            def __exit__(self_inner, *exc):
                gate.last[host] = time.monotonic()
                lock.release()
                return False

        return _Ctx()


def free_bytes() -> int:
    MRF_DIR.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(str(MRF_DIR)).free


class DiskGuard:
    """Refuse a download that would leave less than min_free bytes free, counting
    the expected size of downloads already in flight."""

    def __init__(self, min_free_gb: float):
        self.min_free = int(min_free_gb * 1024 ** 3)
        self.lock = threading.Lock()
        self.reserved = 0
        self.tripped = False

    def reserve(self, nbytes: int) -> bool:
        with self.lock:
            if free_bytes() - self.reserved - nbytes < self.min_free:
                self.tripped = True
                return False
            self.reserved += nbytes
            return True

    def release(self, nbytes: int) -> None:
        with self.lock:
            self.reserved = max(0, self.reserved - nbytes)


class Net:
    def __init__(self, gate: HostGate, guard: DiskGuard, max_bytes: int, abort: threading.Event):
        import requests

        self.requests = requests
        self.gate = gate
        self.guard = guard
        self.max_bytes = max_bytes
        self.abort = abort
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.robots_lock = threading.Lock()

    def _get(self, url: str, *, stream: bool = False, headers: dict | None = None, timeout=(20, 120),
             retries: int = 4):
        """GET with backoff on 429/5xx/connection errors. Caller holds the host gate."""
        h = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
        h.update(headers or {})
        last: Exception | None = None
        for attempt in range(retries):
            if self.abort.is_set():
                raise Aborted()
            try:
                r = self.requests.get(url, headers=h, stream=stream, timeout=timeout, allow_redirects=True)
            except self.requests.RequestException as exc:
                last = exc
                if attempt < retries - 1:
                    time.sleep(min(60, 2 * 2 ** attempt) * (0.75 + 0.5 * random.random()))
                    continue
                raise Failure("network_error", f"{type(exc).__name__}: {str(exc)[:120]}") from exc
            if r.status_code == 429 or r.status_code >= 500:
                r.close()
                last = Failure(f"http_{r.status_code}", url)
                if attempt < retries - 1:
                    ra = r.headers.get("Retry-After") or ""
                    wait_s = int(ra) if ra.isdigit() else 4 * 2 ** attempt
                    time.sleep(min(120, wait_s) * (0.75 + 0.5 * random.random()))
                    continue
                raise last
            return r
        raise last or Failure("network_error", url)  # pragma: no cover

    # ---------------------------------------------------- robots / cms-hpt

    def robots_allows(self, origin: str, url: str) -> bool:
        with self.robots_lock:
            if origin in self.robots:
                rp = self.robots[origin]
                return True if rp is None else rp.can_fetch(ROBOTS_AGENT, url)
        rp: urllib.robotparser.RobotFileParser | None = None
        try:
            with self.gate.hold(origin):
                r = self._get(origin + "/robots.txt", timeout=(15, 30), retries=2)
                try:
                    if r.status_code == 200 and "html" not in r.headers.get("Content-Type", "").lower():
                        rp = urllib.robotparser.RobotFileParser()
                        rp.parse(r.text[:500_000].splitlines())
                finally:
                    r.close()
        except (Failure, Aborted):
            rp = None  # unreachable or 5xx: the cms-hpt.txt request decides
        # Any 4xx or unparseable robots.txt = no restrictions (RFC 9309 2.3.1.3).
        with self.robots_lock:
            self.robots[origin] = rp
        return True if rp is None else rp.can_fetch(ROBOTS_AGENT, url)

    def fetch_cms_hpt(self, origin: str) -> str:
        url = origin + "/cms-hpt.txt"
        if not self.robots_allows(origin, url):
            raise Failure("robots_disallowed", origin)
        with self.gate.hold(url):
            r = self._get(url, stream=True, timeout=(15, 60), retries=3)
            try:
                if r.status_code != 200:
                    raise Failure("no_cms_hpt_txt", f"HTTP {r.status_code} {url}")
                if not str(r.url).startswith("https://"):
                    raise Failure("no_cms_hpt_txt", f"redirected off https: {r.url}")
                buf = b""
                for chunk in r.iter_content(65536):
                    buf += chunk
                    if len(buf) > HPT_MAX_BYTES:
                        raise Failure("no_cms_hpt_txt", "cms-hpt.txt too large")
                text = buf.decode(r.encoding or "utf-8", errors="replace")
            finally:
                r.close()
        if not looks_like_cms_hpt(text):
            raise Failure("no_cms_hpt_txt", f"not a cms-hpt.txt file: {url}")
        return text

    # ---------------------------------------------------- MRF download

    def download(self, url: str, dest: Path, cond: dict | None) -> dict:
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(".part")
        reserved = 0
        try:
            with self.gate.hold(url):
                r = self._get(url, stream=True, headers=cond or {}, timeout=(30, 300), retries=4)
                try:
                    if r.status_code == 304:
                        return {"status": "not_modified"}
                    if r.status_code != 200:
                        raise Failure("mrf_download_failed", f"HTTP {r.status_code}")
                    clen = r.headers.get("Content-Length")
                    encoded = bool(r.headers.get("Content-Encoding"))
                    expected = int(clen) if clen and clen.isdigit() else None
                    if expected and not encoded and expected > self.max_bytes:
                        raise Failure("mrf_too_large", f"{expected} bytes > cap {self.max_bytes}")
                    reserved = min(self.max_bytes, expected * (8 if encoded else 1)) if expected else self.max_bytes
                    if not self.guard.reserve(reserved):
                        reserved = 0
                        raise DiskLow()
                    h = hashlib.sha256()
                    n = 0
                    with open(part, "wb") as out:
                        for chunk in r.iter_content(1024 * 1024):
                            if self.abort.is_set():
                                raise Aborted()
                            n += len(chunk)
                            if n > self.max_bytes:
                                raise Failure("mrf_too_large", f"> cap {self.max_bytes} bytes")
                            h.update(chunk)
                            out.write(chunk)
                    if expected and not encoded and n != expected:
                        raise Failure("mrf_download_failed", f"truncated: {n} of {expected} bytes")
                    if n == 0:
                        raise Failure("mrf_download_failed", "empty file")
                    part.replace(dest)
                    return {"status": "ok", "sha256": h.hexdigest(), "bytes": n,
                            "etag": r.headers.get("ETag"), "lastModified": r.headers.get("Last-Modified")}
                except self.requests.RequestException as exc:
                    raise Failure("mrf_download_failed", f"{type(exc).__name__}: {str(exc)[:120]}") from exc
                finally:
                    r.close()
        finally:
            if part.exists():
                try:
                    part.unlink()
                except OSError:
                    pass
            if reserved:
                self.guard.release(reserved)


def origins_for(url: str) -> list[str]:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    if not host:
        return []
    bare = host[4:] if host.startswith("www.") else host
    # Registrable domain for subdomain sites (alaska.example.org -> example.org).
    labels = bare.split(".")
    keep = 3 if len(labels) >= 3 and labels[-1] == "us" else 2
    reg = ".".join(labels[-keep:])
    out: list[str] = []
    for h in (host, "www." + bare, bare, "www." + reg, reg):
        o = f"https://{h}"
        if o not in out:
            out.append(o)
    return out


# ============================================================ extracts

def codes_key(codes: CodeIndex) -> str:
    return deterministic_id("hospital-mrf-extract-filter", f"v{EXTRACT_VERSION}",
                            ",".join(sorted(codes.drg)), ",".join(sorted(codes.cpt)))


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def extract_path(ccn: str, url: str) -> Path:
    if not re.fullmatch(r"[0-9A-Z]{6}", ccn):
        raise ValueError(f"unsafe CCN {ccn!r}")
    return EXTRACT_DIR / f"{ccn}-{url_hash(url)}.json.gz"


def save_extract(path: Path, raw: dict) -> int:
    from price_contract import json_roundtrip

    path.parent.mkdir(parents=True, exist_ok=True)
    size = write_json_gz(path, raw)
    if read_json_gz(path) != json_roundtrip(raw):
        path.unlink(missing_ok=True)
        raise Failure("extract_write_error", f"read-back mismatch {path.name}")
    return size


def load_extract(path: Path, codes: CodeIndex) -> dict | str:
    """The extract dict, or a reason string if it is unusable."""
    try:
        raw = read_json_gz(path)
    except (OSError, EOFError, ValueError) as exc:
        return f"unreadable: {exc}"[:160]
    if not isinstance(raw, dict) or raw.get("extractVersion") != EXTRACT_VERSION:
        return "extract version mismatch"
    if raw.get("codesKey") != codes_key(codes):
        return "made for a different procedures.json code list; re-download needed"
    return raw


def make_keep(codes: CodeIndex):
    def keep(all_codes: str) -> bool:
        matches, problems = codes.match_all_codes(all_codes)
        return bool(matches or problems)
    return keep


META_KEEP = ("hospital_name", "last_updated_on", "version", "location_name", "license_number", "license_state")


def build_extract(path: Path, codes: CodeIndex, src: dict, dl: dict) -> dict:
    try:
        meta, lines, layout = iter_mrf(path, make_keep(codes))
    except UnsupportedFormat as exc:
        raise Failure("mrf_unsupported_format", str(exc)[:140]) from exc
    except Exception as exc:  # noqa: BLE001 - malformed CSV/JSON
        raise Failure("mrf_parse_error", f"{type(exc).__name__}: {str(exc)[:140]}") from exc
    return {
        "extractVersion": EXTRACT_VERSION,
        "codesKey": codes_key(codes),
        "ccn": src["ccn"],
        "mrfUrl": src["mrfUrl"],
        "cmsHptUrl": src["cmsHptUrl"],
        "sourcePageUrl": src.get("sourcePageUrl"),
        "locationName": src["locationName"],
        "hospitalMatch": src["hospitalMatch"],
        "retrievedAt": src["retrievedAt"],
        "sha256": dl["sha256"],
        "bytes": dl["bytes"],
        "etag": dl.get("etag"),
        "httpLastModified": dl.get("lastModified"),
        "layout": layout,
        "meta": {k: (str(meta[k])[:300] if meta.get(k) is not None else None) for k in META_KEEP},
        "lines": lines,
    }


# ============================================================ per hospital

class Ctx:
    def __init__(self, net: Net, codes: CodeIndex, matcher: StrictHospitalMatcher, by_ccn: dict,
                 sites: dict):
        self.net = net
        self.codes = codes
        self.matcher = matcher
        self.by_ccn = by_ccn
        self.sites = sites


def strict_match(matcher: StrictHospitalMatcher, hospital: dict, location_name: str) -> tuple[bool, str, str | None]:
    h, how = matcher.match([location_name], hospital.get("state") or "", {hospital.get("city") or ""},
                           {(hospital.get("zip") or "")[:5]})
    return bool(h and h["cmsProviderId"] == hospital["cmsProviderId"]), how, (h or {}).get("cmsProviderId")


def find_cms_hpt(ctx: Ctx, ccn: str, hospital: dict) -> tuple[str, list[dict], list[str]]:
    """(cms-hpt url, strictly matching entries, notes). Raises Failure if none."""
    notes: list[str] = []
    found_any = robots_blocked = False
    unmatched: list[str] = []
    seen_origins: set[str] = set()
    settled_sites: set[str] = set()
    for cand in (ctx.sites.get(ccn) or {}).get("candidates", [])[:MAX_CANDIDATES]:
        for origin in origins_for(cand["url"]):
            site = origin[len("https://"):]
            site = site[4:] if site.startswith("www.") else site
            if origin in seen_origins or site in settled_sites:
                continue
            seen_origins.add(origin)
            try:
                text = ctx.net.fetch_cms_hpt(origin)
            except Failure as f:
                if f.reason == "robots_disallowed":
                    robots_blocked = True
                    notes.append(f.text())
                    settled_sites.add(site)  # robots applies to this site under www./bare too
                continue
            found_any = True
            settled_sites.add(site)  # www./bare origins of this site serve the same file
            entries = parse_cms_hpt(text)
            hpt_url = origin + "/cms-hpt.txt"
            matched = []
            for e in entries:
                ok, how, other = strict_match(ctx.matcher, hospital, e.get("location_name") or "")
                if ok:
                    matched.append({**e, "hospitalMatch": how})
                else:
                    unmatched.append(e.get("location_name") or "")
            if matched:
                return hpt_url, matched, notes
    if found_any:
        sample = "; ".join(sorted(set(unmatched))[:3])
        raise Failure("no_strict_location_match", f"{len(unmatched)} entr(y/ies), e.g. {sample}")
    if robots_blocked:
        raise Failure("robots_disallowed", "; ".join(notes)[:150])
    raise Failure("no_cms_hpt_txt", f"{len(seen_origins)} origin(s) tried")


def process_hospital(ctx: Ctx, ccn: str) -> dict:
    hospital = ctx.by_ccn[ccn]
    try:
        hpt_url, entries, _notes = find_cms_hpt(ctx, ccn, hospital)
    except Failure as f:
        return {"status": "failed", "reason": f.text()}
    except Aborted:
        return {"status": "aborted"}
    urls: dict[str, dict] = {}
    skipped_http = 0
    for e in entries:
        u = (e.get("mrf_url") or "").strip()
        if not u.lower().startswith("https://"):
            skipped_http += 1
            continue
        urls.setdefault(u, e)
    if not urls:
        return {"status": "failed", "reason": f"mrf_url_not_https: {skipped_http} matched entr(y/ies)"}
    ok_files = unchanged = lines = 0
    errors: list[str] = []
    kept_extracts: set[str] = set()
    for url, e in sorted(urls.items())[:MAX_MRFS_PER_HOSPITAL]:
        ext_path = extract_path(ccn, url)
        kept_extracts.add(ext_path.name)
        prev = load_extract(ext_path, ctx.codes) if ext_path.exists() else None
        cond = {}
        if isinstance(prev, dict):
            if prev.get("etag"):
                cond["If-None-Match"] = prev["etag"]
            if prev.get("httpLastModified"):
                cond["If-Modified-Since"] = prev["httpLastModified"]
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = DOWNLOAD_DIR / f"{ccn}-{url_hash(url)}.mrf"
        try:
            retrieved = utc_now()
            dl = ctx.net.download(url, dest, cond)
            if dl["status"] == "not_modified":
                if isinstance(prev, dict) and prev.get("cmsHptUrl") == hpt_url \
                        and prev.get("locationName") == e.get("location_name"):
                    unchanged += 1
                    ok_files += 1
                    continue
                dl = ctx.net.download(url, dest, None)
            src = {"ccn": ccn, "mrfUrl": url, "cmsHptUrl": hpt_url, "sourcePageUrl": e.get("source_page_url"),
                   "locationName": e.get("location_name"), "hospitalMatch": e["hospitalMatch"],
                   "retrievedAt": retrieved}
            raw = build_extract(dest, ctx.codes, src, dl)
            save_extract(ext_path, raw)
            ok_files += 1
            lines += len(raw["lines"])
        except Aborted:
            return {"status": "aborted"}
        except DiskLow:
            return {"status": "failed", "reason": "disk_low: not downloaded (free space under limit)",
                    "diskLow": True}
        except Failure as f:
            errors.append(f.text())
        finally:
            dest.unlink(missing_ok=True)
    # Extracts of this hospital whose MRF is no longer listed in its cms-hpt.txt.
    for old in sorted(EXTRACT_DIR.glob(f"{ccn}-*.json.gz")) if EXTRACT_DIR.exists() else []:
        if old.name not in kept_extracts:
            old.unlink(missing_ok=True)
    if ok_files:
        rec = {"at": date.today().isoformat(), "cmsHpt": hpt_url, "mrfs": ok_files, "candidateLines": lines}
        if unchanged:
            rec["unchanged"] = unchanged
        if errors:
            rec["errors"] = errors[:3]
        if skipped_http:
            rec["skippedHttp"] = skipped_http
        return {"status": "done", "record": rec}
    return {"status": "failed", "reason": errors[0] if errors else "no_mrf_processed"}


# ============================================================ assembly (offline-reproducible)

def extract_rows(raw: dict, hospital: dict, codes: CodeIndex, q: Quarantine, name: str) -> list[dict]:
    meta = raw.get("meta") or {}
    vintage = parse_iso_date(meta.get("last_updated_on"))
    base = {"hospitalId": hospital["id"], "mrfUrl": raw["mrfUrl"], "file": name}
    accepted: dict[str, list[dict]] = defaultdict(list)
    for ln in raw.get("lines") or []:
        matches, problems = codes.match_all_codes(ln.get("all_codes"))
        sample = {**base, "line": ln.get("lineNo"), "description": ln.get("description"),
                  "allCodes": (ln.get("all_codes") or "")[:160]}
        if not matches:
            if problems:
                q.add("line:code_with_modifier_or_suffix", sample)
            continue
        procs = sorted({m[0] for m in matches})
        if len(procs) > 1:
            q.add("line:ambiguous_multiple_procedures", sample)
            continue
        pid = procs[0]
        sample["procedureId"] = pid
        prob = line_scope_problem(codes.scope(pid), ln.get("setting"), ln.get("billing_class"), ln.get("modifiers"))
        if prob:
            q.add(prob, sample)
            continue
        accepted[pid].append({**ln, "sample": sample, "labels": sorted({m[2] for m in matches}),
                              "types": sorted({m[1] for m in matches})})
    rows: list[dict] = []
    retrieved_day = (raw.get("retrievedAt") or "")[:10]
    for pid, lns in sorted(accepted.items()):
        if not vintage:
            q.add("row:missing_source_vintage", {**base, "procedureId": pid,
                                                 "lastUpdatedOn": meta.get("last_updated_on")})
            continue
        if retrieved_day and vintage > retrieved_day:
            q.add("row:vintage_after_retrieval", {**base, "procedureId": pid, "priceVintage": vintage,
                                                  "retrievedAt": raw.get("retrievedAt")})
            continue
        agg = aggregate_lines(lns, codes.floor(pid), q)
        types = sorted({t for ln in lns for t in ln["types"]})
        row = {
            "hospitalId": hospital["id"],
            "cmsProviderId": hospital["cmsProviderId"],
            "procedureId": pid,
            "priceSource": "hospital_mrf",
            "scope": codes.scope(pid),
            "matchType": "ms-drg" if "ms-drg" in types else ("cpt" if "cpt" in types else "hcpcs"),
            "matchedCodes": sorted({lab for ln in lns for lab in ln["labels"]}),
            **{k: agg[k] for k in ("cashLow", "cashMedian", "cashHigh", "negotiatedLow", "negotiatedMedian",
                                   "negotiatedHigh", "payerCount", "grossCharge", "lineCount")},
            "priceVintage": vintage,
            "stale": False,
            "mrfUrl": raw["mrfUrl"],
            "sourceDataset": raw.get("cmsHptUrl"),
            "sourceDocumentHash": f"sha256:{raw['sha256']}" if raw.get("sha256") else None,
            "sourceRetrievedAt": raw.get("retrievedAt"),
            "sourceFacilityName": raw.get("locationName"),
            "hospitalMatch": raw.get("hospitalMatch"),
        }
        row["id"] = deterministic_id(row["mrfUrl"], row["hospitalId"], pid)
        blocked = blocked_reason(hospital, pid, codes)
        if blocked:
            q.add(f"row:{blocked}", {**base, "procedureId": pid})
            continue
        if row["cashMedian"] is None and row["negotiatedMedian"] is None:
            q.add("row:no_valid_cash_or_negotiated_price", {**base, "procedureId": pid})
            continue
        rows.append(order_row(row))
    return rows


def assemble(extract_dir: Path, codes: CodeIndex, hospitals: list[dict]) -> tuple[list[dict], dict, Quarantine]:
    """Rows, meta and quarantine from the extracts alone (no network, no clock)."""
    by_ccn = {h["cmsProviderId"]: h for h in hospitals}
    hospitals_by_id = {h["id"]: h for h in hospitals}
    matcher = StrictHospitalMatcher(hospitals)
    q = Quarantine()
    rows: list[dict] = []
    used = 0
    retrieved_days: list[str] = []
    layouts: Counter = Counter()
    paths = sorted(extract_dir.glob("*.json.gz")) if extract_dir.exists() else []
    for p in paths:
        m = EXTRACT_NAME_RE.match(p.name)
        if not m:
            continue
        raw = load_extract(p, codes)
        if isinstance(raw, str):
            q.add("file:extract_unusable_needs_redownload", {"file": p.name, "why": raw})
            continue
        if raw.get("ccn") != m.group(1) or url_hash(raw.get("mrfUrl") or "") != m.group(2):
            q.add("file:extract_name_mismatch", {"file": p.name})
            continue
        h = by_ccn.get(raw["ccn"])
        if not h:
            q.add("file:hospital_not_in_cms_list", {"file": p.name, "ccn": raw["ccn"]})
            continue
        ok, how, other = strict_match(matcher, h, raw.get("locationName") or "")
        if not ok:
            q.add("file:cms_hpt_location_no_longer_matches",
                  {"file": p.name, "locationName": raw.get("locationName"), "resolvedTo": other, "why": how})
            continue
        if not str(raw.get("mrfUrl") or "").startswith("https://"):
            q.add("file:mrf_url_not_https", {"file": p.name, "mrfUrl": raw.get("mrfUrl")})
            continue
        used += 1
        layouts[raw.get("layout") or "unknown"] += 1
        if raw.get("retrievedAt"):
            retrieved_days.append(raw["retrievedAt"][:10])
        rows.extend(extract_rows(raw, h, codes, q, p.name))

    # Reference date = the latest retrieval date of the files read (a source date, not the build date).
    reference_date = max(retrieved_days, default=None)
    checked: list[dict] = []
    for r in rows:
        r["stale"] = is_stale(r["priceVintage"], reference_date)
        probs = contract_problems(r, codes, hospitals_by_id)
        if probs:
            q.add(f"row:contract_violation:{probs[0]}", {"hospitalId": r["hospitalId"],
                                                         "procedureId": r["procedureId"], "mrfUrl": r["mrfUrl"]})
        else:
            checked.append(r)

    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in checked:
        groups[(r["hospitalId"], r["procedureId"])].append(r)
    out: list[dict] = []
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda r: r["mrfUrl"])
        g.sort(key=lambda r: (r["priceVintage"], r.get("lineCount") or 0), reverse=True)
        out.append(g[0])
        for loser in g[1:]:
            q.add("row:duplicate_superseded", {"hospitalId": loser["hospitalId"], "procedureId": loser["procedureId"],
                                               "mrfUrl": loser["mrfUrl"], "keptMrfUrl": g[0]["mrfUrl"]})

    by_proc: Counter = Counter(r["procedureId"] for r in out)
    meta = {
        "source": "Hospitals' own CMS price transparency machine-readable files (45 CFR Part 180), "
                  "located through each hospital's cms-hpt.txt",
        "method": "cms-hpt.txt location-name strictly matched to the hospital's CCN; streamed MRF parse; "
                  "shared contract in etl/price_contract.py",
        "referenceDate": reference_date,
        "referenceDateRule": "latest retrieval date among the extracts read (not the build date)",
        "staleRule": "stale = priceVintage more than 18 months before referenceDate",
        "priceCount": len(out),
        "cmsHospitalsWithPrices": len({r["cmsProviderId"] for r in out}),
        "extractFiles": used,
        "extractLayouts": dict(sorted(layouts.items())),
        "rowsByProcedure": dict(sorted(by_proc.items())),
        "staleRows": sum(1 for r in out if r["stale"]),
        "contract": {
            "hospitalMatching": "a cms-hpt.txt entry is used only when its location-name resolves to this CCN "
                                "through price_contract.StrictHospitalMatcher (identical distinctive name tokens "
                                "+ same city/ZIP, or a strict token subset with >= 2 shared tokens in the same "
                                "city); re-checked at every rebuild",
            "codeMatching": "explicit MS-DRG:/CPT:/HCPCS: code types only; codes with suffixes/modifiers rejected",
            "scope": "one canonical scope per procedure; CPT/HCPCS lines must be billing_class facility and "
                     "setting outpatient or both; MS-DRG lines inpatient/both/unspecified and not professional",
            "cash": "discounted_cash only; gross charge never used as cash",
            "negotiated": "standard_charge_dollar per payer+plan, then median/min/max across plans; per diem and "
                          "percent-of-charges excluded; percentages/algorithms never converted",
            "bounds": "values <= 0, >= 500000, sentinels and values under the procedure floor dropped",
            "vintage": "the MRF's last_updated_on; missing, unparseable or after the retrieval date -> quarantined",
            "mrfUrl": "the https mrf-url listed in the hospital's cms-hpt.txt; sourceDataset = that cms-hpt.txt URL",
            "dedupe": DEDUPE_RULE,
        },
        "note": "Prices exactly as published by hospitals in their own files. Nothing is estimated.",
    }
    return out, meta, q


def write_outputs(codes: CodeIndex, hospitals: list[dict]) -> tuple[list[dict], dict, Quarantine]:
    rows, meta, q = assemble(EXTRACT_DIR, codes, hospitals)
    atomic_write_text(OUT_PRICES, dump_json(rows))
    atomic_write_text(OUT_META, dump_json(meta))
    write_quarantine_section(QUARANTINE_SECTION, q, {"referenceDate": meta["referenceDate"]})
    return rows, meta, q


# ============================================================ progress / batch

def order_hash(order: list[str]) -> str:
    return hashlib.sha256("\n".join(order).encode("utf-8")).hexdigest()[:16]


def advance(progress: dict, order: list[str]) -> None:
    i = int(progress.get("nextIndex") or 0)
    while i < len(order) and (order[i] in progress["done"] or order[i] in progress["failed"]):
        i += 1
    progress["nextIndex"] = i


def load_progress(order: list[str], reset: bool, new_cycle_days: int) -> dict:
    prog = read_json(PROGRESS_JSON, None) or {}
    fresh = {"nextIndex": 0, "orderHash": order_hash(order), "orderLength": len(order),
             "cycleStarted": date.today().isoformat(), "failed": {}, "done": {}}
    if reset or not prog:
        return fresh
    prog.setdefault("failed", {})
    prog.setdefault("done", {})
    prog.setdefault("nextIndex", 0)
    if prog.get("orderHash") != order_hash(order):
        # done/failed are keyed by CCN: re-basing cannot skip or repeat a hospital.
        log(f"hospital-sites.json order changed ({prog.get('orderLength')} -> {len(order)} hospitals); "
            f"re-basing progress by CCN.")
        prog["orderHash"] = order_hash(order)
        prog["orderLength"] = len(order)
        prog["nextIndex"] = 0
    else:
        n = int(prog["nextIndex"])
        gap = [c for c in order[:n] if c not in prog["done"] and c not in prog["failed"]]
        if n > len(order) or gap:
            raise SystemExit(f"mrf-progress.json is inconsistent: {len(gap)} hospital(s) before nextIndex {n} "
                             f"are neither done nor failed (e.g. {gap[:3]}). Refusing to skip them; "
                             f"run with --reset-progress.")
    advance(prog, order)
    if prog["nextIndex"] >= len(order) and new_cycle_days > 0:
        started = prog.get("cycleStarted") or "1970-01-01"
        if (date.today() - date.fromisoformat(started)).days >= new_cycle_days:
            log(f"Cycle started {started} is complete; starting a new cycle (extracts kept; unchanged "
                f"files cost one conditional GET).")
            return fresh
    return prog


def save_progress(prog: dict) -> None:
    out = dict(prog)
    out["failed"] = dict(sorted(prog["failed"].items()))
    out["done"] = dict(sorted(prog["done"].items()))
    atomic_write_text(PROGRESS_JSON, dump_json(out))


def acquire_lock(force: bool) -> bool:
    if RUN_LOCK.exists() and not force:
        log(f"Another MRF ingest may be running (lock {RUN_LOCK}); pass --force if not.")
        return False
    RUN_LOCK.write_text(str(os.getpid()), encoding="utf-8")
    atexit.register(lambda: RUN_LOCK.unlink(missing_ok=True))
    return True


def run_network(args, codes: CodeIndex, hospitals: list[dict]) -> tuple[dict, dict]:
    by_ccn = {h["cmsProviderId"]: h for h in hospitals}
    sites = read_json(SITES_JSON, {}) or {}
    order = sorted(c for c, e in sites.items() if c in by_ccn and e.get("candidates"))
    if not order:
        raise SystemExit(f"No hospitals with candidate sites in {SITES_JSON}; run discover_hospital_sites.py")
    prog = load_progress(order, args.reset_progress, args.new_cycle_after_days)

    if args.hospital:
        if args.hospital not in sites or args.hospital not in by_ccn:
            raise SystemExit(f"CCN {args.hospital} has no candidate site in {SITES_JSON}")
        queue = [args.hospital]
        mode = "hospital"
    elif args.retry_failed:
        queue = [c for c in sorted(prog["failed"]) if c in by_ccn and c in sites]
        mode = "retry-failed"
    else:
        queue = [c for c in order[prog["nextIndex"]:] if c not in prog["done"] and c not in prog["failed"]]
        mode = "batch"
    if args.limit:
        queue = queue[: args.limit]

    if free_bytes() < args.min_free_gb * 1024 ** 3:
        log(f"Free disk {free_bytes() / 1024 ** 3:.1f} GB is under --min-free-gb {args.min_free_gb}; not starting.")
        return prog, {"mode": mode, "attempted": 0, "diskLowStop": True}
    for stale in DOWNLOAD_DIR.glob("*") if DOWNLOAD_DIR.exists() else []:
        stale.unlink(missing_ok=True)

    abort = threading.Event()
    guard = DiskGuard(args.min_free_gb)
    net = Net(HostGate(), guard, int(args.max_file_gb * 1024 ** 3), abort)
    ctx = Ctx(net, codes, StrictHospitalMatcher(hospitals), by_ccn, sites)
    start = time.monotonic()
    soft = start + args.max_minutes * 60 if args.max_minutes else None
    hard = soft + args.grace_minutes * 60 if soft else None
    workers = max(1, min(args.workers, MAX_WORKERS))
    log(f"[{mode}] {len(queue)} hospital(s) queued of {len(order)} with candidate sites "
        f"(nextIndex {prog['nextIndex']}); workers {workers}; max file {args.max_file_gb} GB; "
        f"min free {args.min_free_gb} GB" + (f"; stop after {args.max_minutes} min" if soft else ""))

    stats: Counter = Counter()
    reasons: Counter = Counter()
    stopped = None
    it = iter(queue)
    in_flight: dict = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        while True:
            while len(in_flight) < workers and stopped is None:
                if soft and time.monotonic() >= soft:
                    stopped = "time"
                    break
                if guard.tripped:
                    stopped = "disk_low"
                    break
                ccn = next(it, None)
                if ccn is None:
                    break
                in_flight[pool.submit(process_hospital, ctx, ccn)] = ccn
            if not in_flight:
                break
            done_f, _ = wait(list(in_flight), timeout=15, return_when=FIRST_COMPLETED)
            if hard and time.monotonic() >= hard and not abort.is_set():
                log("Hard time limit reached: aborting in-flight downloads (those hospitals stay pending).")
                abort.set()
            for fut in done_f:
                ccn = in_flight.pop(fut)
                try:
                    res = fut.result()
                except Exception as exc:  # noqa: BLE001 - a bug for one hospital must not stop the batch
                    res = {"status": "failed", "reason": f"internal_error: {type(exc).__name__}: {str(exc)[:120]}"}
                st = res["status"]
                stats[st] += 1
                h = by_ccn[ccn]
                if st == "done":
                    prog["done"][ccn] = res["record"]
                    prog["failed"].pop(ccn, None)
                    log(f"  ok      {ccn} {h['name'][:48]}: {res['record']['mrfs']} file(s), "
                        f"{res['record']['candidateLines']} new candidate line(s)"
                        + (f", {res['record']['unchanged']} unchanged (304)" if res['record'].get('unchanged') else ""))
                elif st == "failed":
                    prog["failed"][ccn] = res["reason"]
                    prog["done"].pop(ccn, None)
                    reasons[res["reason"].split(":")[0]] += 1
                    log(f"  failed  {ccn} {h['name'][:48]}: {res['reason'][:110]}")
                else:
                    log(f"  aborted {ccn} {h['name'][:48]} (left pending)")
                advance(prog, order)
                save_progress(prog)
    run = {"mode": mode, "finishedAt": utc_now(), "attempted": sum(stats.values()), **dict(stats),
           "failedByReason": dict(sorted(reasons.items())), "stoppedBy": stopped or "queue_end",
           "minutes": round((time.monotonic() - start) / 60, 1),
           "freeGbAfter": round(free_bytes() / 1024 ** 3, 1)}
    if guard.tripped:
        log(f"Disk guard tripped: free space would drop under {args.min_free_gb} GB.")
    prog["lastRun"] = run
    return prog, run


def main() -> int:
    ap = argparse.ArgumentParser(description="Direct hospital MRF ingest (cms-hpt.txt -> MRF -> extract).")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--batch", action="store_true", help="process hospital-sites.json in order, resuming")
    mode.add_argument("--hospital", help="process one CCN (smoke test)")
    mode.add_argument("--retry-failed", action="store_true", help="retry the progress file's failed hospitals")
    mode.add_argument("--offline", action="store_true", help="rebuild outputs from data/mrf/extracts only")
    ap.add_argument("--limit", type=int, default=0, help="max hospitals this run")
    ap.add_argument("--max-minutes", type=float, default=0,
                    help="stop at the next hospital boundary after N minutes, checkpoint, exit 0")
    ap.add_argument("--grace-minutes", type=float, default=10,
                    help="after --max-minutes + this, abort in-flight downloads (hospital stays pending)")
    ap.add_argument("--workers", type=int, default=4, help=f"parallel hospitals (max {MAX_WORKERS})")
    ap.add_argument("--min-free-gb", type=float, default=40.0, help="never let a download drop free disk below this")
    ap.add_argument("--max-file-gb", type=float, default=3.0, help="skip MRFs larger than this")
    ap.add_argument("--reset-progress", action="store_true", help="start a new cycle (extracts are kept)")
    ap.add_argument("--new-cycle-after-days", type=int, default=30,
                    help="when a cycle is complete, start a new one after this many days (0 = never)")
    ap.add_argument("--force", action="store_true", help="ignore a leftover run lock")
    args = ap.parse_args()
    if args.workers > MAX_WORKERS:
        log(f"--workers capped at {MAX_WORKERS}")

    codes = CodeIndex()
    hospitals = load_hospitals()
    run = None
    if not args.offline:
        if not (args.batch or args.hospital or args.retry_failed):
            ap.error("choose one of --batch, --hospital CCN, --retry-failed or --offline")
        if not acquire_lock(args.force):
            return 1
        prog, run = run_network(args, codes, hospitals)
    rows, meta, q = write_outputs(codes, hospitals)
    if run is not None:
        prog["priceCount"] = len(rows)
        prog["cmsHospitalsWithPrices"] = meta["cmsHospitalsWithPrices"]
        save_progress(prog)
        log(f"\nRun: {json.dumps(run)}")
        log(f"Progress: nextIndex {prog['nextIndex']} / {prog['orderLength']}, done {len(prog['done'])}, "
            f"failed {len(prog['failed'])}")
    log(f"Wrote {len(rows)} hospital_mrf prices ({meta['cmsHospitalsWithPrices']} hospitals) from "
        f"{meta['extractFiles']} extract(s) -> {OUT_PRICES}")
    log("Quarantine: " + json.dumps(dict(sorted(q.counts.items()))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
