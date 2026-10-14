#!/usr/bin/env python3
"""
Ingest hospital prices from Trilliant Health ORIA parsed DuckDB files.

Trilliant parses each hospital's CMS-required machine-readable file (MRF) into
DuckDB (standard_charges + standard_charge_details). This script extracts the
procedures defined in data/seed/procedures.json under the contract in
etl/price_contract.py:

  * a line counts only when its all_codes field carries an explicit
    MS-DRG:<n> / CPT:<n> / HCPCS:<n> token for one of the procedure's codes
    (the typed ms_drg/cpt/hcpcs columns are NOT trusted on their own: in many
    files ms_drg holds APR-DRG, TRICARE DRG or revenue codes);
  * the line must be in the procedure's canonical scope (MS-DRG -> inpatient
    facility stay; CPT/HCPCS -> outpatient/both facility line, no modifier);
  * cash = the published discounted cash price only; negotiated = payer/plan
    rates published as dollars (per-diem and percent-of-charge methodologies
    excluded; percentages/algorithms are never converted by us); gross charge is
    reported separately and never substituted for cash;
  * the facility must match exactly one CMS hospital (exact CCN, or identical
    name tokens + city/ZIP, or identical name tokens + state when the file has
    no city and the name is unique in the state);
  * priceVintage comes from the file's last_updated_on; no date -> quarantined.

Sources (pick one):
  --rescan-cache        Rebuild from data/trilliant/extracts/*.json.gz plus any
                        data/trilliant/cache/*.duckdb still present (no downloads).
                        Output is byte-identical whichever of the two a slug comes from.
  --duckdb-dir PATH     Folder of per-hospital *.duckdb files
  --consolidated PATH   A single DuckDB with the same tables
  --oria                Download per-hospital files, extract, save the compact
                        extract, then delete the DuckDB file (disk-bounded)
  --convert-cache       Write an extract for every cached DuckDB file (verified
                        by read-back); with --delete-duckdb also delete the DuckDB

Extracts (data/trilliant/extracts/<slug>.json.gz) hold the raw inputs of the
rules, not their results: the source_metadata/hospitals provenance fields, every
standard_charges line that the candidate SQL filter selects for the current
procedures.json codes, and the dollar payer rates for those lines. All contract
rules run on top of them at assembly time, exactly as on a DuckDB file. Each
extract records the code-filter key it was made with; if procedures.json codes
change, the extract is refused and the slug must be downloaded again.

Disk: --oria refuses to start a download that would leave less than
--min-free-gb (default 40) free; such entries go to failedSlugs ("disk_low").

Every run REBUILDS trilliant-prices.json from the files it read, except --oria
--append which merges new rows into the existing file (same dedupe rule).
Rows from the previous file that are not reproduced are listed in
data/cms/quarantine.json ("row:previous_row_not_reproduced").

With --merge, also writes data/cms/mrf-prices.json combining direct hospital
MRF rows (hospital_mrf) with Trilliant rows; the direct hospital MRF row wins
when both exist for the same hospital+procedure.

USAGE:
  python etl/ingest_trilliant.py --rescan-cache
  python etl/ingest_trilliant.py --duckdb-dir data/trilliant/duckdb
  python etl/ingest_trilliant.py --oria --limit 50 --append
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
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from price_contract import (  # noqa: E402
    CMS_DIR,
    ROOT,
    FACILITY_KIND_WORDS,
    GENERIC_ONLY,
    CodeIndex,
    Quarantine,
    StrictHospitalMatcher,
    ZIP_RE,
    aggregate_lines,
    atomic_write_text,
    blocked_reason,
    contract_problems,
    deterministic_id,
    dump_json,
    is_stale,
    json_roundtrip,
    line_scope_problem,
    load_hospitals,
    name_tokens,
    order_row,
    parse_iso_date,
    read_json,
    read_json_gz,
    write_json_gz,
    write_quarantine_section,
)

TRILLIANT_DIR = ROOT / "data" / "trilliant"
CACHE_DIR = TRILLIANT_DIR / "cache"
EXTRACT_DIR = TRILLIANT_DIR / "extracts"
EXTRACT_VERSION = 1
SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]*$")
MAX_DOWNLOAD_WORKERS = 4
DEFAULT_MIN_FREE_GB = 40.0
MRF_PRICES_JSON = CMS_DIR / "mrf-prices.json"
OUT_PRICES = CMS_DIR / "trilliant-prices.json"
OUT_META = CMS_DIR / "trilliant-meta.json"
PROGRESS_JSON = CMS_DIR / "trilliant-progress.json"

ORIA_BASE = "https://oria-data.trillianthealth.com"
ORIA_INDEX_URL = f"{ORIA_BASE}/search-index.json"
ORIA_INDEX_CACHE = TRILLIANT_DIR / "oria-search-index.json"
ORIA_HOSPITAL_URL = ORIA_BASE + "/hospital/{slug}"
USER_AGENT = (
    "Mozilla/5.0 (compatible; OpenSourceMed-HospitalCompare/1.0; "
    "+https://opensourcemed.info; trilliant-orias-ingest)"
)
DUCKDB_PATH_RE = re.compile(r'(/data/store/[^"\']+_parsed\.duckdb)')
DEDUPE_RULE = (
    "one row per CMS hospital + procedure: the row from the source file with the most "
    "recent priceVintage wins; ties go to the file with more accepted MRF lines, then to "
    "the lexically smallest sourceDataset. Losers are quarantined as "
    "row:duplicate_superseded."
)
QUARANTINE_SECTION = "trilliant_mrf"


# ============================================================ network (--oria)

def backoff_sleep(attempt: int, base: float = 2.0, cap: float = 120.0) -> None:
    """Exponential backoff with jitter: ~2, 4, 8, 16 ... s (capped)."""
    time.sleep(min(cap, base * (2 ** attempt)) * (0.75 + 0.5 * random.random()))


def _retryable(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in (408, 425, 429) or exc.code >= 500
    return True


def fetch_text(url: str, timeout: int = 120, retries: int = 5) -> str:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries - 1 and _retryable(exc):
                backoff_sleep(attempt)
            else:
                break
    raise last_err  # type: ignore[misc]


def free_bytes() -> int:
    return shutil.disk_usage(str(ROOT)).free


class DiskGuard:
    """Refuse new downloads that would leave less than min_free bytes free.

    Accounts for downloads already in flight (their expected size is reserved
    until they finish), so concurrent workers cannot jointly overshoot.
    """

    def __init__(self, min_free_gb: float):
        self.min_free = int(min_free_gb * 1024 ** 3)
        self.lock = threading.Lock()
        self.reserved = 0
        self.tripped = False

    def reserve(self, nbytes: int) -> bool:
        with self.lock:
            if self.tripped:
                return False
            if free_bytes() - self.reserved - nbytes < self.min_free:
                self.tripped = True
                return False
            self.reserved += nbytes
            return True

    def release(self, nbytes: int) -> None:
        with self.lock:
            self.reserved = max(0, self.reserved - nbytes)


def load_oria_index(refresh: bool = False) -> list[dict]:
    if not refresh and ORIA_INDEX_CACHE.exists():
        return json.loads(ORIA_INDEX_CACHE.read_text(encoding="utf-8"))
    print("Fetching ORIA search index…")
    text = fetch_text(ORIA_INDEX_URL, timeout=180, retries=6)
    atomic_write_text(ORIA_INDEX_CACHE, text)
    return json.loads(text)


def load_index_by_slug() -> dict[str, dict]:
    if not ORIA_INDEX_CACHE.exists():
        return {}
    return {e["id"]: e for e in json.loads(ORIA_INDEX_CACHE.read_text(encoding="utf-8")) if e.get("id")}


def validate_duckdb(path: Path) -> bool:
    try:
        con = duckdb.connect(str(path), read_only=True)
        try:
            con.execute("SHOW TABLES").fetchall()
            return True
        finally:
            con.close()
    except duckdb.Error:
        return False


def download_file(url: str, dest: Path, timeout: int = 600, retries: int = 4) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Short temp name (Windows 260-char path limit with long slugs).
    part = dest.parent / f".p{os.getpid()}-{threading.get_ident() % 100000}.part"
    last_err: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:
                expected = resp.headers.get("Content-Length")
                n = 0
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    n += len(chunk)
            if expected and expected.isdigit() and int(expected) != n:
                raise OSError(f"truncated download: {n} of {expected} bytes")
            part.replace(dest)
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries - 1 and _retryable(exc):
                backoff_sleep(attempt, base=4.0)
            else:
                break
        finally:
            if part.exists():
                try:
                    part.unlink()
                except OSError:
                    pass
    raise last_err  # type: ignore[misc]


# ============================================================ extracts

def codes_key(codes: CodeIndex) -> str:
    """Identifies the candidate-line filter an extract was made with."""
    return deterministic_id("trilliant-extract-filter", f"v{EXTRACT_VERSION}",
                            ",".join(sorted(codes.drg)), ",".join(sorted(codes.cpt)))


def extract_path(slug: str) -> Path:
    if not SLUG_RE.match(slug):
        raise ValueError(f"unsafe ORIA slug: {slug!r}")
    return EXTRACT_DIR / f"{slug}.json.gz"


class ExtractUnusable(Exception):
    pass


def load_extract(path: Path, codes: CodeIndex) -> dict:
    try:
        raw = read_json_gz(path)
    except (OSError, EOFError, ValueError) as exc:
        raise ExtractUnusable(f"unreadable extract: {exc}"[:200]) from exc
    if not isinstance(raw, dict) or raw.get("extractVersion") != EXTRACT_VERSION:
        raise ExtractUnusable("extract version mismatch")
    if raw.get("codesKey") != codes_key(codes):
        raise ExtractUnusable("extract made for a different procedures.json code list; re-download needed")
    if raw.get("error"):
        raise ExtractUnusable(f"extract records a read error: {raw['error'].get('reason')}")
    return raw


def ensure_extract_dir() -> None:
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    gi = EXTRACT_DIR / ".gitignore"
    if not gi.exists():
        # data/trilliant/ must stay out of git; the repo .gitignore only lists cache/.
        gi.write_text("# generated per-hospital ORIA extracts; never commit\n*\n", encoding="utf-8")


def save_extract(raw: dict) -> int:
    """Write the extract and verify it reads back identical. Returns bytes on disk."""
    path = extract_path(raw["slug"])
    ensure_extract_dir()
    size = write_json_gz(path, raw)
    if read_json_gz(path) != raw:
        path.unlink(missing_ok=True)
        raise OSError(f"extract read-back mismatch for {raw['slug']}")
    return size


def fetch_entry(entry: dict, codes: CodeIndex, use_cache: bool, guard: DiskGuard,
                keep_duckdb: bool = False) -> tuple[str, dict | None, str | None]:
    """Get one ORIA hospital's extract: cached extract, else cached DuckDB, else download.

    Returns (slug, processed_extraction, error). After a successful download the
    compact extract is saved and the DuckDB file deleted (unless keep_duckdb).
    """
    slug = entry["id"]
    if entry.get("status") != "completed":
        return slug, None, "not_completed"
    try:
        ext_path = extract_path(slug)
    except ValueError as exc:
        return slug, None, f"bad_slug: {exc}"[:160]
    cache_path = CACHE_DIR / f"{slug}.duckdb"
    if use_cache and ext_path.exists():
        try:
            raw = load_extract(ext_path, codes)
            return slug, process_raw(raw, codes, entry), None
        except ExtractUnusable:
            pass  # fall through: rebuild from DuckDB / re-download
    have_duckdb = (use_cache and cache_path.exists() and cache_path.stat().st_size > 1000
                   and validate_duckdb(cache_path))
    reserved = 0
    try:
        if not have_duckdb:
            reserved = int(entry.get("duckdbSize") or 0) or 512 * 1024 ** 2
            if not guard.reserve(reserved):
                reserved = 0
                return slug, None, "disk_low: not downloaded (free space under limit)"
            try:
                html = fetch_text(ORIA_HOSPITAL_URL.format(slug=slug), timeout=60)
            except Exception as exc:  # noqa: BLE001
                return slug, None, f"index_page_error: {exc}"[:160]
            m = DUCKDB_PATH_RE.search(html)
            if not m:
                return slug, None, "no_duckdb_url"
            try:
                download_file(ORIA_BASE + m.group(1), cache_path)
            except Exception as exc:  # noqa: BLE001
                return slug, None, f"download_error: {exc}"[:160]
            if not validate_duckdb(cache_path):
                cache_path.unlink(missing_ok=True)
                return slug, None, "corrupt_duckdb"
        raw = read_raw(str(cache_path), codes)
        if raw.get("error"):
            # Never freeze a read error into an extract: drop the file, retry later.
            if not keep_duckdb:
                cache_path.unlink(missing_ok=True)
            return slug, None, f"extract_error: {raw['error'].get('message') or raw['error'].get('reason')}"[:160]
        try:
            save_extract(raw)
        except OSError as exc:
            return slug, None, f"extract_write_error: {exc}"[:160]
        if not keep_duckdb:
            cache_path.unlink(missing_ok=True)
        return slug, process_raw(raw, codes, entry), None
    finally:
        if reserved:
            guard.release(reserved)


# ============================================================ run lock

RUN_LOCK = CMS_DIR / ".trilliant-ingest.lock"


def acquire_run_lock(force: bool) -> bool:
    if RUN_LOCK.exists() and not force:
        print(f"Another Trilliant ingest may be running (lock: {RUN_LOCK}). Use --force if not.",
              file=sys.stderr)
        return False
    CMS_DIR.mkdir(parents=True, exist_ok=True)
    RUN_LOCK.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_run_lock() -> None:
    try:
        if RUN_LOCK.exists() and RUN_LOCK.read_text(encoding="utf-8").strip() == str(os.getpid()):
            RUN_LOCK.unlink()
    except OSError:
        pass


# ============================================================ extraction (one file)

def table_columns(con, table: str) -> set[str]:
    try:
        rows = con.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?", [table]
        ).fetchall()
        return {r[0] for r in rows}
    except duckdb.Error:
        return set()


def _col(cols: set[str], alias: str, name: str) -> str:
    return f"{alias}.{name} AS {name}" if name in cols else f"NULL AS {name}"


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if x is not None and str(x).strip()]
    s = str(v).strip()
    return [s] if s else []


def read_source(con) -> dict:
    meta: dict = {}
    sm_cols = table_columns(con, "source_metadata")
    if sm_cols:
        names = [n for n in ("mrf_url", "mrf_content_md5", "mrf_last_updated_on", "data_downloaded",
                             "package_db_path", "hpt_hospital_name", "source_page_url") if n in sm_cols]
        row = con.execute(f"SELECT {', '.join(names)} FROM source_metadata LIMIT 1").fetchone()
        if row:
            meta.update(dict(zip(names, row)))
    h_cols = table_columns(con, "hospitals")
    want = [n for n in ("hospital_id", "hospital_name", "location_name", "hospital_address",
                        "hospital_state", "last_updated_on", "license_number",
                        "enriched_hospital_city", "enriched_hospital_address") if n in h_cols]
    hosp_rows = con.execute(f"SELECT {', '.join(want)} FROM hospitals ORDER BY hospital_id").fetchall()
    meta["hospitals"] = [dict(zip(want, r)) for r in hosp_rows]
    return meta


def facility_identity(src: dict, index_entry: dict | None) -> dict:
    """Names / state / cities / ZIPs the source file states about its facility."""
    hospitals = src.get("hospitals") or []
    loc_names: list[str] = []
    hosp_names: list[str] = []
    states: set[str] = set()
    cities: set[str] = set()
    zips: set[str] = set()
    addresses: list[str] = []
    for h in hospitals:
        loc_names += _as_list(h.get("location_name"))
        hosp_names += _as_list(h.get("hospital_name"))
        if h.get("hospital_state"):
            states.add(str(h["hospital_state"]).strip().upper())
        addresses += _as_list(h.get("hospital_address")) + _as_list(h.get("enriched_hospital_address"))
        c = h.get("enriched_hospital_city")
        if c and str(c).strip().lower() != "not provided":
            cities.add(str(c))
    if index_entry:
        if index_entry.get("state"):
            states.add(str(index_entry["state"]).strip().upper())
        if index_entry.get("city") and index_entry["city"] != "Not provided":
            cities.add(index_entry["city"])
        if index_entry.get("address") and index_entry["address"] != "Not provided":
            addresses.append(index_entry["address"])
    for a in addresses:
        for z in ZIP_RE.findall(a):
            zips.add(z)
        m = re.search(r",\s*([A-Za-z .'\-]+?),?\s+[A-Z]{2}\s+\d{5}", a)
        if m:
            cities.add(m.group(1))
    hpt = src.get("hpt_hospital_name")
    if hpt:
        loc_names.append(str(hpt))
    loc_names = sorted(set(n for n in loc_names if n))
    return {
        "locationNames": loc_names,
        "hospitalNames": sorted(set(hosp_names)),
        "states": sorted(states),
        "cities": sorted(cities),
        "zips": sorted(zips),
        "addresses": sorted(set(addresses)),
    }


def candidate_where(codes: CodeIndex, sc_cols: set[str]) -> str:
    """SQL filter for candidate lines: any explicit or typed mention of our codes.

    Deliberately broad (typed columns included) so that lines the rules reject
    are still seen and quarantined with a reason.
    """
    all_drg = sorted(codes.drg)
    all_cpt = sorted(codes.cpt)
    alt = "|".join([str(int(d)) for d in all_drg] + all_cpt)
    pattern = rf"(MS-DRG|CPT|HCPCS)\s*:\s*0*({alt})"
    typed = []
    drg_variants = sorted(set(all_drg) | {str(int(d)) for d in all_drg})
    if "ms_drg" in sc_cols:
        typed.append("sc.ms_drg IN (" + ", ".join(f"'{d}'" for d in drg_variants) + ")")
    for c in ("cpt", "hcpcs"):
        if c in sc_cols:
            typed.append(f"sc.{c} IN (" + ", ".join(f"'{x}'" for x in all_cpt) + ")")
    where = f"regexp_matches(coalesce(sc.all_codes, ''), '{pattern}')"
    if typed:
        where = f"({where}) OR " + " OR ".join(typed)
    return where


LINE_FIELDS = ("description", "all_codes", "ms_drg", "cpt", "hcpcs", "setting", "billing_class",
               "modifiers", "discounted_cash", "gross_charge")
DETAIL_FIELDS = ("payer_name", "plan_name", "standard_charge_dollar", "methodology")


def read_raw(path_str: str, codes: CodeIndex) -> dict:
    """Read everything the contract rules need from one DuckDB file.

    The result is exactly what is stored as the extract (it is passed through a
    JSON round trip here), so rules applied to it give identical output whether
    the source was the DuckDB file or the saved extract.
    """
    raw: dict = {
        "extractVersion": EXTRACT_VERSION,
        "slug": Path(path_str).stem,
        "file": Path(path_str).name,
        "codesKey": codes_key(codes),
    }
    try:
        con = duckdb.connect(path_str, read_only=True)
    except duckdb.Error as exc:
        raw["error"] = {"reason": "file:source_file_unreadable", "message": str(exc)[:200]}
        return json_roundtrip(raw)
    try:
        raw["source"] = read_source(con)
        sc_cols = table_columns(con, "standard_charges")
        if "all_codes" not in sc_cols:
            raw["noAllCodesColumn"] = True
            return json_roundtrip(raw)
        sel = ", ".join(["sc.charge_id AS charge_id"] + [_col(sc_cols, "sc", f) for f in LINE_FIELDS])
        lines = con.execute(
            f"SELECT {sel} FROM standard_charges sc WHERE {candidate_where(codes, sc_cols)} "
            f"ORDER BY sc.charge_id"
        ).fetchall()
        raw["lines"] = {"cols": [d[0] for d in con.description], "rows": [list(r) for r in lines]}
        d_cols = table_columns(con, "standard_charge_details")
        raw["details"] = None
        if {"charge_id", "standard_charge_dollar"} <= d_cols:
            charge_ids = sorted({r[0] for r in lines if r[0] is not None})
            rows: list = []
            dcols = ["charge_id"] + list(DETAIL_FIELDS)
            if charge_ids:
                id_list = ", ".join(str(int(c)) for c in charge_ids)
                dsel = ", ".join(["d.charge_id AS charge_id"] + [_col(d_cols, "d", f) for f in DETAIL_FIELDS])
                # Total order (methodology last) so ties never reorder between runs.
                drows = con.execute(
                    f"SELECT {dsel} FROM standard_charge_details d "
                    f"WHERE d.charge_id IN ({id_list}) AND d.standard_charge_dollar IS NOT NULL "
                    f"ORDER BY d.charge_id, d.payer_name, d.plan_name, d.standard_charge_dollar, d.methodology"
                ).fetchall()
                dcols = [x[0] for x in con.description]
                rows = [list(r) for r in drows]
            raw["details"] = {"cols": dcols, "rows": rows}
    except duckdb.Error as exc:
        raw["error"] = {"reason": "file:duckdb_query_error", "message": str(exc)[:200]}
    finally:
        con.close()
    return json_roundtrip(raw)


def extract_file(path_str: str, code_cfg: dict, index_entry: dict | None) -> dict:
    """Extract per-procedure aggregates from one DuckDB file. Runs in a worker process."""
    codes = CodeIndex(code_cfg["procedures"])
    return process_raw(read_raw(path_str, codes), codes, index_entry)


def process_raw(raw: dict, codes: CodeIndex, index_entry: dict | None) -> dict:
    """Apply the contract's line rules to one source's raw extract."""
    q = Quarantine()
    slug = raw["slug"]
    out: dict = {"slug": slug, "file": raw["file"], "procs": {}, "quarantine": None}
    err = raw.get("error")
    if err and err.get("reason") == "file:source_file_unreadable":
        q.add("file:source_file_unreadable", {"file": raw["file"], "error": err.get("message")})
        out["quarantine"] = q.to_dict()
        out["error"] = "unreadable"
        return out
    if "source" not in raw:
        q.add("file:duckdb_query_error", {"file": out["file"], "error": (err or {}).get("message")})
        out["error"] = "query_error"
        out["quarantine"] = q.to_dict()
        return out
    try:
        src = raw["source"]
        out["identity"] = facility_identity(src, index_entry)
        hosp = (src.get("hospitals") or [{}])[0]
        vintage = parse_iso_date(hosp.get("last_updated_on")) or parse_iso_date(src.get("mrf_last_updated_on"))
        out["vintage"] = vintage
        out["downloaded"] = parse_iso_date(src.get("data_downloaded"))
        dl = str(src.get("data_downloaded") or "")
        m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})", dl)
        out["retrievedAt"] = f"{m.group(1)}T{m.group(2)}Z" if m else None
        mrf_url = src.get("mrf_url")
        out["mrfUrl"] = mrf_url if isinstance(mrf_url, str) and mrf_url.startswith("https://") else None
        out["mrfUrlRaw"] = mrf_url
        pkg = src.get("package_db_path")
        out["sourceDataset"] = (
            f"{ORIA_BASE}/data/store/{pkg}" if pkg and not str(pkg).startswith(("/", "\\")) and ":" not in str(pkg)
            else ORIA_HOSPITAL_URL.format(slug=slug)
        )
        md5 = src.get("mrf_content_md5")
        out["sourceDocumentHash"] = f"md5:{md5}" if md5 and re.fullmatch(r"[0-9a-fA-F]{32}", str(md5)) else None
        out["nHospitalRows"] = len(src.get("hospitals") or [])

        if raw.get("noAllCodesColumn"):
            q.add("file:no_all_codes_column", {"file": out["file"]})
            out["quarantine"] = q.to_dict()
            return out
        if "lines" not in raw:
            raise _RawQueryError()
        cols = raw["lines"]["cols"]
        lines = raw["lines"]["rows"]

        accepted: dict[str, list[dict]] = defaultdict(list)
        for raw_line in lines:
            line = dict(zip(cols, raw_line))
            sample = {
                "file": out["file"],
                "chargeId": line["charge_id"],
                "description": (line.get("description") or "")[:100],
                "allCodes": (line.get("all_codes") or "")[:160],
                "msDrgColumn": line.get("ms_drg"),
                "cptColumn": line.get("cpt"),
                "setting": line.get("setting"),
                "billingClass": line.get("billing_class"),
            }
            matches, problems = codes.match_all_codes(line.get("all_codes"))
            procs = sorted({m[0] for m in matches})
            if not matches:
                if problems:
                    q.add("line:code_with_modifier_or_suffix", sample)
                else:
                    q.add("line:code_type_not_explicit", sample)
                continue
            if len(procs) > 1:
                q.add("line:ambiguous_multiple_procedures", sample)
                continue
            proc_id = procs[0]
            scope = codes.scope(proc_id)
            sample["procedureId"] = proc_id
            prob = line_scope_problem(scope, line.get("setting"), line.get("billing_class"),
                                      line.get("modifiers"))
            if prob:
                q.add(prob, sample)
                continue
            accepted[proc_id].append({
                "chargeId": line["charge_id"],
                "cash": line.get("discounted_cash"),
                "gross": line.get("gross_charge"),
                "labels": sorted({m[2] for m in matches}),
                "types": sorted({m[1] for m in matches}),
                "sample": sample,
            })

        # payer-level dollar rates for accepted lines (details hold every candidate
        # line's rates in a total order; keep the accepted lines' rates, in order)
        if "details" not in raw:
            raise _RawQueryError()
        charge_ids = {ln["chargeId"] for lns in accepted.values() for ln in lns}
        rates_by_charge: dict = defaultdict(list)
        details = raw.get("details")
        if charge_ids and details is not None:
            dcols = details["cols"]
            for r in details["rows"]:
                if r[0] in charge_ids:
                    rates_by_charge[r[0]].append(dict(zip(dcols, r)))

        for proc_id, lns in sorted(accepted.items()):
            for ln in lns:
                ln["rates"] = [
                    {"payer": r.get("payer_name"), "plan": r.get("plan_name"),
                     "dollar": r.get("standard_charge_dollar"), "methodology": r.get("methodology")}
                    for r in rates_by_charge.get(ln["chargeId"], [])
                ]
            agg = aggregate_lines(lns, codes.floor(proc_id), q)
            types = sorted({t for ln in lns for t in ln["types"]})
            agg.update({
                "scope": codes.scope(proc_id),
                "matchType": "ms-drg" if "ms-drg" in types else ("cpt" if "cpt" in types else "hcpcs"),
                "matchedCodes": sorted({lab for ln in lns for lab in ln["labels"]}),
            })
            out["procs"][proc_id] = agg
    except _RawQueryError:
        q.add("file:duckdb_query_error", {"file": out["file"], "error": (err or {}).get("message")})
        out["error"] = "query_error"
        out["procs"] = {}
    out["quarantine"] = q.to_dict()
    return out


class _RawQueryError(Exception):
    """The DuckDB read stopped part-way (recorded in raw['error'])."""


# ============================================================ assembly

def resolve_hospital(ext: dict, matcher: StrictHospitalMatcher) -> tuple[dict | None, str]:
    ident = ext.get("identity") or {}
    states = ident.get("states") or []
    if len(states) != 1:
        return None, "no_state" if not states else "multiple_states_in_file"
    state = states[0]
    cities = set(ident.get("cities") or [])
    zips = set(ident.get("zips") or [])
    names = ident.get("locationNames") or []
    found: dict[str, tuple[dict, str]] = {}
    reasons: list[str] = []
    candidates = [[n] for n in names] if names else [[n] for n in ident.get("hospitalNames") or []]
    for cand in candidates:
        h, how = matcher.match(cand, state, cities, zips)
        if h:
            found.setdefault(h["cmsProviderId"], (h, how))
        else:
            reasons.append(how)
    if not found and names:
        # Location names did not resolve. Fall back to the file's hospital_name
        # only if the file names exactly one facility.
        # The location name may only differ from hospital_name by an abbreviation
        # (e.g. "BMH Tipton" vs "Baptist Memorial Hospital-Tipton"): at most one
        # extra non-generic token and no facility-kind word (rehab, behavioral...).
        loc_toks = name_tokens(names[0]) if names else frozenset()
        if ext.get("nHospitalRows") == 1 and len(names) <= 1:
            for n in ident.get("hospitalNames") or []:
                extra = loc_toks - name_tokens(n) - GENERIC_ONLY
                if len(extra) > 1 or (loc_toks & FACILITY_KIND_WORDS) - name_tokens(n):
                    reasons.append("location_name_differs_from_hospital_name")
                    continue
                h, how = matcher.match([n], state, cities, zips)
                if h:
                    found.setdefault(h["cmsProviderId"], (h, how + "(hospital_name)"))
                else:
                    reasons.append(how)
    if len(found) > 1:
        return None, "multi_facility_file_not_itemised"
    if found:
        return next(iter(found.values()))
    if "ambiguous_hospital_match" in reasons:
        return None, "ambiguous_hospital_match"
    if "location_name_differs_from_hospital_name" in reasons:
        return None, "location_name_differs_from_hospital_name"
    if "name_matched_but_city_or_uniqueness_failed" in reasons:
        return None, "name_matched_but_city_or_uniqueness_failed"
    return None, "no_strict_hospital_match"


def assemble(extractions: list[dict], matcher: StrictHospitalMatcher, codes: CodeIndex,
             hospitals_by_id: dict[str, dict], q: Quarantine) -> tuple[list[dict], str, dict]:
    downloaded = sorted(e["downloaded"] for e in extractions if e.get("downloaded"))
    vintages = sorted(e["vintage"] for e in extractions if e.get("vintage"))
    reference_date = downloaded[-1] if downloaded else (vintages[-1] if vintages else None)
    stats = defaultdict(int)
    candidates: list[dict] = []
    for ext in sorted(extractions, key=lambda e: e["file"]):
        q.merge(Quarantine.from_dict(ext.get("quarantine")))
        stats["files"] += 1
        if ext.get("error"):
            stats["filesWithErrors"] += 1
            continue
        if not ext["procs"]:
            stats["filesWithoutMatchingLines"] += 1
            continue
        base = {"file": ext["file"], "identity": {k: ext["identity"].get(k) for k in ("locationNames", "hospitalNames", "states", "cities", "zips")}}
        hosp, how = resolve_hospital(ext, matcher)
        if not hosp:
            stats["filesUnmatched"] += 1
            for pid in sorted(ext["procs"]):
                q.add(f"row:{how}", {**base, "procedureId": pid})
            continue
        stats["filesMatched"] += 1
        if not ext.get("vintage"):
            for pid in sorted(ext["procs"]):
                q.add("row:missing_source_vintage", {**base, "procedureId": pid})
            continue
        for pid, agg in sorted(ext["procs"].items()):
            cms_id = hosp["cmsProviderId"]
            row = {
                "hospitalId": f"hosp-cms-{cms_id}",
                "cmsProviderId": cms_id,
                "procedureId": pid,
                "priceSource": "trilliant_mrf",
                "scope": agg["scope"],
                "matchType": agg["matchType"],
                "matchedCodes": agg["matchedCodes"],
                "cashLow": agg["cashLow"],
                "cashMedian": agg["cashMedian"],
                "cashHigh": agg["cashHigh"],
                "negotiatedLow": agg["negotiatedLow"],
                "negotiatedMedian": agg["negotiatedMedian"],
                "negotiatedHigh": agg["negotiatedHigh"],
                "payerCount": agg["payerCount"],
                "grossCharge": agg["grossCharge"],
                "priceVintage": ext["vintage"],
                "stale": is_stale(ext["vintage"], reference_date),
                "mrfUrl": ext["mrfUrl"],
                "sourceDataset": ext["sourceDataset"],
                "sourceDocumentHash": ext["sourceDocumentHash"],
                "sourceRetrievedAt": ext.get("retrievedAt"),
                "sourceFacilityName": (ext["identity"].get("locationNames") or ext["identity"].get("hospitalNames") or [None])[0],
                "hospitalMatch": how,
                "lineCount": agg["lineCount"],
            }
            row["id"] = deterministic_id(row["sourceDataset"], row["hospitalId"], pid)
            sample = {**base, "hospitalId": row["hospitalId"], "hospitalName": hosp.get("name"),
                      "hospitalType": hosp.get("hospitalType"), "procedureId": pid,
                      "cashMedian": row["cashMedian"], "negotiatedMedian": row["negotiatedMedian"]}
            blocked = blocked_reason(hosp, pid, codes)
            if blocked:
                q.add(f"row:{blocked}", sample)
                continue
            if row["cashMedian"] is None and row["negotiatedMedian"] is None:
                q.add("row:no_valid_cash_or_negotiated_price", {**sample, "grossCharge": row["grossCharge"]})
                continue
            probs = contract_problems(row, codes, hospitals_by_id)
            if probs:
                q.add(f"row:contract_violation:{probs[0]}", sample)
                continue
            candidates.append(order_row(row))
    rows = dedupe(candidates, q)
    rows.sort(key=lambda r: (r["hospitalId"], r["procedureId"]))
    return rows, reference_date, dict(stats)


def dedupe(rows: list[dict], q: Quarantine) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        groups[(r["cmsProviderId"], r["procedureId"])].append(r)
    out: list[dict] = []
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda r: r["sourceDataset"] or "")
        g.sort(key=lambda r: (r["priceVintage"], r.get("lineCount") or 0), reverse=True)
        out.append(g[0])
        for loser in g[1:]:
            q.add("row:duplicate_superseded", {
                "hospitalId": loser["hospitalId"], "procedureId": loser["procedureId"],
                "sourceDataset": loser["sourceDataset"], "priceVintage": loser["priceVintage"],
                "keptSourceDataset": g[0]["sourceDataset"], "keptPriceVintage": g[0]["priceVintage"],
            })
    return out


def merge_rows(existing: list[dict], new: list[dict], q: Quarantine) -> list[dict]:
    return dedupe(existing + new, q)


def merge_price_lists(direct: list[dict], trilliant: list[dict]) -> list[dict]:
    """Direct hospital_mrf rows win over trilliant_mrf rows for the same hospital+procedure."""
    by_key: dict[tuple[str, str], dict] = {}
    for p in trilliant:
        by_key[(p.get("cmsProviderId") or p["hospitalId"], p["procedureId"])] = p
    for p in direct:
        by_key[(p.get("cmsProviderId") or p["hospitalId"], p["procedureId"])] = p
    return [by_key[k] for k in sorted(by_key)]


def extract_source(slug: str, ext_path: str | None, duck_path: str | None, prefer: str,
                   procedures: list[dict], index_entry: dict | None) -> dict:
    """Worker: processed extraction for one slug from its extract or DuckDB file.

    Returns {"slug", "file", "unusable": reason} when neither source can be used.
    """
    codes = CodeIndex(procedures)
    order = [("extract", ext_path), ("duckdb", duck_path)]
    if prefer == "duckdb":
        order.reverse()
    reasons = []
    for kind, p in order:
        if not p:
            continue
        if kind == "duckdb":
            return process_raw(read_raw(p, codes), codes, index_entry)
        try:
            return process_raw(load_extract(Path(p), codes), codes, index_entry)
        except ExtractUnusable as exc:
            reasons.append(str(exc))
    return {"slug": slug, "file": f"{slug}.duckdb", "unusable": "; ".join(reasons) or "no source"}


def run_extractions(sources: list[tuple[str, str | None, str | None]], codes: CodeIndex,
                    workers: int, prefer: str = "extract") -> list[dict]:
    """sources: (slug, extract_path, duckdb_path)."""
    index = load_index_by_slug()
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(extract_source, slug, e, d, prefer, codes.procedures, index.get(slug))
                for slug, e, d in sources]
        for i, f in enumerate(futs, 1):
            results.append(f.result())
            if i % 250 == 0 or i == len(futs):
                print(f"  extracted {i}/{len(futs)} sources", flush=True)
    return results


def rescan_sources() -> list[tuple[str, str | None, str | None]]:
    duck = {p.stem: str(p) for p in list_duckdb(CACHE_DIR)} if CACHE_DIR.exists() else {}
    ext = {}
    if EXTRACT_DIR.exists():
        ext = {p.name[: -len(".json.gz")]: str(p) for p in sorted(EXTRACT_DIR.glob("*.json.gz"))}
    return [(s, ext.get(s), duck.get(s)) for s in sorted(set(duck) | set(ext))]


def convert_one(path_str: str, procedures: list[dict], delete: bool) -> tuple[str, str, int]:
    """Worker: write the extract for one cached DuckDB file; optionally delete the DuckDB.

    The DuckDB is deleted only when the saved extract reads back identical and
    the rules give the identical extraction from both sources.
    """
    codes = CodeIndex(procedures)
    slug = Path(path_str).stem
    raw = read_raw(path_str, codes)
    if raw.get("error"):
        return slug, f"kept_duckdb_read_error: {raw['error'].get('message')}"[:200], 0
    try:
        size = save_extract(raw)
    except (OSError, ValueError) as exc:
        return slug, f"kept_duckdb_extract_write_error: {exc}"[:200], 0
    if delete:
        index = load_index_by_slug()
        from_duck = process_raw(raw, codes, index.get(slug))
        from_ext = process_raw(load_extract(extract_path(slug), codes), codes, index.get(slug))
        if json.dumps(from_duck, sort_keys=True) != json.dumps(from_ext, sort_keys=True):
            return slug, "kept_duckdb_extract_mismatch", size
        Path(path_str).unlink()
        return slug, "converted_deleted", size
    return slug, "converted_kept", size


def index_order_hash(index: list[dict]) -> str:
    return hashlib.sha256("\n".join(e.get("id", "") for e in index).encode("utf-8")).hexdigest()[:24]


def list_duckdb(directory: Path) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for f in sorted(directory.rglob("*.duckdb")):
        r = f.resolve()
        if f.is_file() and r not in seen:
            seen.add(r)
            out.append(f)
    return out


# ============================================================ main

def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest Trilliant ORIA MRF prices")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--consolidated", metavar="PATH")
    src.add_argument("--duckdb-dir", metavar="PATH")
    src.add_argument("--oria", action="store_true")
    src.add_argument("--rescan-cache", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="Max ORIA index entries this batch")
    ap.add_argument("--offset", type=int, default=0, help="ORIA index offset")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-cache", action="store_true", help="Re-download ORIA files")
    ap.add_argument("--append", action="store_true", help="(--oria) merge into existing output")
    ap.add_argument("--merge", action="store_true", help="Also write combined mrf-prices.json")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--refresh-index", action="store_true")
    src.add_argument("--convert-cache", action="store_true",
                     help="Write extracts for all cached DuckDB files (no price output)")
    ap.add_argument("--delete-duckdb", action="store_true",
                    help="(--convert-cache) delete each DuckDB once its extract is verified")
    ap.add_argument("--rescan-source", choices=("extract", "duckdb"), default="extract",
                    help="(--rescan-cache) which source to prefer when a slug has both")
    ap.add_argument("--retry-failed", action="store_true",
                    help="(--oria) process the progress file's failedSlugs instead of an offset slice")
    ap.add_argument("--force-offset", action="store_true",
                    help="(--oria) allow an --offset other than the progress file's nextOffset")
    ap.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB,
                    help="(--oria) never start a download that would leave less free disk than this")
    args = ap.parse_args()

    if args.force and RUN_LOCK.exists():
        RUN_LOCK.unlink(missing_ok=True)
    if not acquire_run_lock(args.force):
        return 1
    atexit.register(release_run_lock)

    codes = CodeIndex()
    if args.convert_cache:
        paths = list_duckdb(CACHE_DIR)
        print(f"Converting {len(paths)} cached DuckDB file(s) to extracts "
              f"({'deleting' if args.delete_duckdb else 'keeping'} DuckDB files)…", flush=True)
        ensure_extract_dir()
        statuses: dict[str, int] = defaultdict(int)
        total_size = 0
        kept: list[tuple[str, str]] = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(convert_one, str(p), codes.procedures, args.delete_duckdb) for p in paths]
            for i, f in enumerate(futs, 1):
                slug, status, size = f.result()
                statuses[status.split(":")[0]] += 1
                total_size += size
                if status.startswith("kept_duckdb"):
                    kept.append((slug, status))
                if i % 50 == 0 or i == len(futs):
                    print(f"  converted {i}/{len(futs)}", flush=True)
        print("Conversion:", json.dumps(dict(sorted(statuses.items()))),
              f"extract bytes written: {total_size}")
        for slug, status in kept:
            print(f"  KEPT {slug}: {status}")
        return 0 if not kept else 2

    hospitals = load_hospitals()
    hospitals_by_id = {h["id"]: h for h in hospitals}
    matcher = StrictHospitalMatcher(hospitals)
    previous = read_json(OUT_PRICES, []) or []
    q = Quarantine()
    progress = None
    unusable_failures: dict[str, str] = {}

    if args.consolidated:
        mode = "consolidated"
        p = Path(args.consolidated)
        extractions = run_extractions([(p.stem, None, str(p))], codes, args.workers, "duckdb")
    elif args.duckdb_dir:
        mode = "duckdb-dir"
        extractions = run_extractions([(p.stem, None, str(p)) for p in list_duckdb(Path(args.duckdb_dir))],
                                      codes, args.workers, "duckdb")
    elif args.rescan_cache:
        mode = "rescan-cache"
        sources = rescan_sources()
        n_ext = sum(1 for _, e, _d in sources if e)
        n_duck = sum(1 for _, _e, d in sources if d)
        print(f"Rescanning {len(sources)} source(s): {n_ext} extract(s), {n_duck} DuckDB file(s) "
              f"(prefer {args.rescan_source})…", flush=True)
        extractions = run_extractions(sources, codes, args.workers, args.rescan_source)
    else:
        mode = "oria"
        index = load_oria_index(refresh=args.refresh_index)
        prev_prog = read_json(PROGRESS_JSON, {}) or {}
        order_hash = index_order_hash(index)
        if prev_prog.get("oriaIndexOrderHash") and prev_prog["oriaIndexOrderHash"] != order_hash \
                and not args.force_offset:
            print("ORIA index order changed since this run's progress file was written; offsets "
                  "would skip or repeat entries. Reset progress (run_trilliant_batches.py "
                  "--reset-progress) or pass --force-offset.", file=sys.stderr)
            return 1
        if args.retry_failed:
            failed = prev_prog.get("failedSlugs") or {}
            batch = [e for e in index if e.get("id") in failed]
            if args.limit:
                batch = batch[: args.limit]
            start = end = None
            missing = sorted(set(failed) - {e.get("id") for e in index})
            if missing:
                print(f"  {len(missing)} failed slug(s) are no longer in the ORIA index: {missing[:5]}…")
            print(f"Retrying {len(batch)} failed ORIA entr(y/ies)…", flush=True)
        else:
            start = max(0, args.offset)
            expected = prev_prog.get("nextOffset")
            if expected is not None and int(expected) != start and not args.force_offset:
                print(f"--offset {start} != progress nextOffset {expected}: that would skip or repeat "
                      f"index entries. Pass --force-offset to override.", file=sys.stderr)
                return 1
            end = len(index) if not args.limit else min(len(index), start + args.limit)
            batch = index[start:end]
            print(f"Fetching ORIA entries {start}..{end - 1} of {len(index)}…", flush=True)
        if free_bytes() < args.min_free_gb * 1024 ** 3:
            print(f"Free disk {free_bytes() / 1024 ** 3:.1f} GB is under --min-free-gb "
                  f"{args.min_free_gb}; not starting.", file=sys.stderr)
            return 3
        # Partial downloads left by an interrupted run (we hold the run lock, so
        # nothing else is writing them).
        for stale in list(CACHE_DIR.glob(".p*.part")) if CACHE_DIR.exists() else []:
            stale.unlink(missing_ok=True)
        guard = DiskGuard(args.min_free_gb)
        workers = max(1, min(args.workers, MAX_DOWNLOAD_WORKERS))
        failures: dict[str, str] = {}
        ok_slugs: list[str] = []
        extractions = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for slug, ext, err in pool.map(lambda e: fetch_entry(e, codes, not args.no_cache, guard), batch):
                if err:
                    failures[slug] = err
                else:
                    ok_slugs.append(slug)
                    extractions.append(ext)
        retry = dict(prev_prog.get("failedSlugs") or {})
        for s in ok_slugs:
            retry.pop(s, None)
        retry.update({s: e for s, e in failures.items() if e != "not_completed"})
        not_completed = set(prev_prog.get("notCompletedSlugs") or [])
        not_completed |= {s for s, e in failures.items() if e == "not_completed"}
        not_completed -= set(ok_slugs)
        progress = dict(prev_prog)
        progress.update({
            "lastBatch": {"mode": "retry-failed" if args.retry_failed else "offset",
                          "offset": start, "end": end, "attempted": len(batch),
                          "ok": len(ok_slugs), "failed": len(failures),
                          "diskLowStop": guard.tripped,
                          "freeGbAfter": round(free_bytes() / 1024 ** 3, 1)},
            "oriaIndexTotal": len(index),
            "oriaIndexOrderHash": order_hash,
            # Every index entry in [start, end) was attempted exactly once; entries that
            # failed (incl. disk_low) are carried in failedSlugs for retry, never skipped.
            "failedSlugs": dict(sorted(retry.items())),
            "notCompletedSlugs": sorted(not_completed),
        })
        if not args.retry_failed:
            progress["nextOffset"] = end
        for s, e in sorted(failures.items()):
            q.add("file:oria_download_failed", {"slug": s, "error": e})
        if guard.tripped:
            print(f"Disk guard tripped: free space would drop under {args.min_free_gb} GB; "
                  f"remaining entries recorded in failedSlugs as disk_low.", file=sys.stderr)

    usable = []
    for ext in extractions:
        if ext.get("unusable"):
            unusable_failures[ext["slug"]] = f"extract_unusable: {ext['unusable']}"[:160]
            q.add("file:extract_unusable_needs_redownload", {"slug": ext["slug"], "why": ext["unusable"]})
        else:
            usable.append(ext)
    if unusable_failures:
        print(f"WARNING: {len(unusable_failures)} extract(s) unusable; recorded in failedSlugs for "
              f"re-download.", file=sys.stderr)
    extractions = usable
    print(f"Assembling {len(extractions)} extraction(s) [{mode}]…", flush=True)
    rows, reference_date, stats = assemble(extractions, matcher, codes, hospitals_by_id, q)

    if mode == "oria" and args.append:
        rows = merge_rows([r for r in previous if r.get("scope")], rows, q)
        rows.sort(key=lambda r: (r["hospitalId"], r["procedureId"]))

    new_keys = {(r["cmsProviderId"], r["procedureId"]) for r in rows}
    for p in previous:
        key = (p.get("cmsProviderId"), p.get("procedureId"))
        if key not in new_keys:
            q.add("row:previous_row_not_reproduced", {
                "hospitalId": p.get("hospitalId"), "procedureId": p.get("procedureId"),
                "previousCashMedian": p.get("cashMedian"), "previousVintage": p.get("priceVintage"),
                "previousSource": p.get("mrfUrl"),
                "why": "not re-derivable from the local source files under the current rules",
            })

    atomic_write_text(OUT_PRICES, dump_json(rows))
    by_proc: dict[str, int] = defaultdict(int)
    for r in rows:
        by_proc[r["procedureId"]] += 1
    meta = {
        "source": "Trilliant Health ORIA parsed hospital MRF DuckDB files",
        "attribution": "https://oria-data.trillianthealth.com/",
        "mode": mode,
        "referenceDate": reference_date,
        "referenceDateRule": "latest data_downloaded date among the source files read (not the build date)",
        "staleRule": "stale = priceVintage more than 18 months before referenceDate",
        "priceCount": len(rows),
        "cmsHospitalsWithPrices": len({r["cmsProviderId"] for r in rows}),
        "rowsByProcedure": dict(sorted(by_proc.items())),
        "staleRows": sum(1 for r in rows if r["stale"]),
        "runStats": stats,
        "contract": {
            "codeMatching": "explicit MS-DRG:/CPT:/HCPCS: token in all_codes; typed columns alone are not trusted; codes with modifiers/suffixes rejected",
            "scope": "one canonical scope per procedure (procedures.json 'scope'); MS-DRG lines must be inpatient/both (or unspecified) and not professional; CPT/HCPCS lines must be billing_class facility and setting outpatient or both",
            "cash": "discounted_cash only; cashLow/High = min/max across accepted lines, cashMedian = median",
            "negotiated": "standard_charge_dollar per payer+plan (median per plan when a plan has several lines), then median/min/max across plans; per diem and percent-of-total-billed-charges methodologies excluded; percentages, algorithms and estimated_amount never used; payerCount = distinct payer+plan pairs",
            "grossCharge": "median gross charge across accepted lines; never used as cash",
            "bounds": "values <= 0, >= 500000 or sentinels (e.g. 999999999) dropped per value; cash and payer rates below the procedure floor dropped",
            "procedureFloorsUsd": {p["id"]: codes.floor(p["id"]) for p in codes.procedures},
            "hospitalMatching": "exact CCN if the source has one (Trilliant files have none); else identical distinctive name tokens + same state + same city or ZIP; else one name's tokens containing the other's (>= 2 shared, one non-generic, no unmatched facility-kind word such as rehab/behavioral/LTAC) + same state + same city or ZIP; else identical name tokens + state when the file states no city/ZIP and the name is unique in the state; the file's hospital_name is used only when its location name differs by at most one abbreviation token; files whose locations resolve to more than one CMS hospital are not attached; ambiguous or failed matches are quarantined",
            "hospitalTypeBlocks": "Psychiatric and Long-term hospitals: imaging only; Rural Emergency Hospitals: no inpatient_stay procedures",
            "dedupe": DEDUPE_RULE,
            "mrfUrl": "the hospital's own MRF URL from source_metadata.mrf_url when https, else null; sourceDataset = the Trilliant DuckDB package URL",
            "vintage": "hospitals.last_updated_on from the MRF, else source_metadata.mrf_last_updated_on; rows without a source date are quarantined",
        },
        "note": "Prices are exactly as published in hospital MRFs, parsed by Trilliant Health. Nothing is estimated.",
    }
    atomic_write_text(OUT_META, dump_json(meta))
    write_quarantine_section(QUARANTINE_SECTION, q, {"referenceDate": reference_date})
    if progress is not None:
        progress["priceCount"] = len(rows)
        progress["cmsHospitalsWithPrices"] = meta["cmsHospitalsWithPrices"]
        if unusable_failures:
            progress["failedSlugs"] = dict(sorted({**progress["failedSlugs"], **unusable_failures}.items()))
        atomic_write_text(PROGRESS_JSON, dump_json(progress))
    elif mode == "rescan-cache":
        prog = dict(read_json(PROGRESS_JSON, {}) or {})
        prog.setdefault("nextOffset", 0)
        prog["failedSlugs"] = dict(sorted({**(prog.get("failedSlugs") or {}), **unusable_failures}.items()))
        prog["lastRescan"] = {"sources": stats.get("files", 0), "priceCount": len(rows),
                              "cmsHospitalsWithPrices": meta["cmsHospitalsWithPrices"],
                              "referenceDate": reference_date}
        atomic_write_text(PROGRESS_JSON, dump_json(prog))

    print(f"\nWrote {len(rows)} Trilliant prices ({meta['cmsHospitalsWithPrices']} hospitals) → {OUT_PRICES}")
    print("Quarantine:", json.dumps(dict(sorted(q.counts.items())), indent=1))

    if args.merge:
        existing = read_json(MRF_PRICES_JSON, []) or []
        direct = [p for p in existing if p.get("priceSource") == "hospital_mrf"]
        merged = merge_price_lists(direct=direct, trilliant=rows)
        atomic_write_text(MRF_PRICES_JSON, dump_json(merged))
        print(f"Merged {len(merged)} total prices → {MRF_PRICES_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
