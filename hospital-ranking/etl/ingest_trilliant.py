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
  --rescan-cache        Rebuild from data/trilliant/cache/*.duckdb (no downloads)
  --duckdb-dir PATH     Folder of per-hospital *.duckdb files
  --consolidated PATH   A single DuckDB with the same tables
  --oria                Download per-hospital files into the cache, then extract

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
import json
import os
import re
import sys
import time
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
    line_scope_problem,
    load_hospitals,
    name_tokens,
    order_row,
    parse_iso_date,
    read_json,
    write_quarantine_section,
)

TRILLIANT_DIR = ROOT / "data" / "trilliant"
CACHE_DIR = TRILLIANT_DIR / "cache"
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

def fetch_text(url: str, timeout: int = 120, retries: int = 5) -> str:
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise last_err  # type: ignore[misc]


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


def download_file(url: str, dest: Path, timeout: int = 600) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + f".part.{os.getpid()}")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        part.replace(dest)
    finally:
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass


def ensure_cached(entry: dict, use_cache: bool) -> tuple[str, str | None]:
    """Download one ORIA hospital DuckDB into the cache. Returns (slug, error)."""
    slug = entry["id"]
    if entry.get("status") != "completed":
        return slug, "not_completed"
    cache_path = CACHE_DIR / f"{slug}.duckdb"
    if use_cache and cache_path.exists() and cache_path.stat().st_size > 1000 and validate_duckdb(cache_path):
        return slug, None
    try:
        html = fetch_text(ORIA_HOSPITAL_URL.format(slug=slug), timeout=60)
    except Exception as exc:  # noqa: BLE001
        return slug, f"index_page_error: {exc}"[:160]
    m = DUCKDB_PATH_RE.search(html)
    if not m:
        return slug, "no_duckdb_url"
    try:
        download_file(ORIA_BASE + m.group(1), cache_path)
    except Exception as exc:  # noqa: BLE001
        return slug, f"download_error: {exc}"[:160]
    if not validate_duckdb(cache_path):
        cache_path.unlink(missing_ok=True)
        return slug, "corrupt_duckdb"
    return slug, None


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


def extract_file(path_str: str, code_cfg: dict, index_entry: dict | None) -> dict:
    """Extract per-procedure aggregates from one DuckDB file. Runs in a worker process."""
    codes = CodeIndex(code_cfg["procedures"])
    q = Quarantine()
    slug = Path(path_str).stem
    out: dict = {"slug": slug, "file": Path(path_str).name, "procs": {}, "quarantine": None}
    try:
        con = duckdb.connect(path_str, read_only=True)
    except duckdb.Error as exc:
        q.add("file:source_file_unreadable", {"file": Path(path_str).name, "error": str(exc)[:200]})
        out["quarantine"] = q.to_dict()
        out["error"] = "unreadable"
        return out
    try:
        src = read_source(con)
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

        sc_cols = table_columns(con, "standard_charges")
        if "all_codes" not in sc_cols:
            q.add("file:no_all_codes_column", {"file": out["file"]})
            out["quarantine"] = q.to_dict()
            return out
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
        sel = ", ".join([
            "sc.charge_id AS charge_id",
            _col(sc_cols, "sc", "description"),
            _col(sc_cols, "sc", "all_codes"),
            _col(sc_cols, "sc", "ms_drg"),
            _col(sc_cols, "sc", "cpt"),
            _col(sc_cols, "sc", "hcpcs"),
            _col(sc_cols, "sc", "setting"),
            _col(sc_cols, "sc", "billing_class"),
            _col(sc_cols, "sc", "modifiers"),
            _col(sc_cols, "sc", "discounted_cash"),
            _col(sc_cols, "sc", "gross_charge"),
        ])
        lines = con.execute(
            f"SELECT {sel} FROM standard_charges sc WHERE {where} ORDER BY sc.charge_id"
        ).fetchall()
        cols = [d[0] for d in con.description]

        accepted: dict[str, list[dict]] = defaultdict(list)
        for raw in lines:
            line = dict(zip(cols, raw))
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

        # payer-level dollar rates for accepted lines
        d_cols = table_columns(con, "standard_charge_details")
        charge_ids = sorted({ln["chargeId"] for lns in accepted.values() for ln in lns})
        rates_by_charge: dict = defaultdict(list)
        if charge_ids and {"charge_id", "standard_charge_dollar"} <= d_cols:
            id_list = ", ".join(str(int(c)) for c in charge_ids)
            dsel = ", ".join([
                "d.charge_id AS charge_id",
                _col(d_cols, "d", "payer_name"),
                _col(d_cols, "d", "plan_name"),
                _col(d_cols, "d", "standard_charge_dollar"),
                _col(d_cols, "d", "methodology"),
            ])
            drows = con.execute(
                f"SELECT {dsel} FROM standard_charge_details d "
                f"WHERE d.charge_id IN ({id_list}) AND d.standard_charge_dollar IS NOT NULL "
                f"ORDER BY d.charge_id, d.payer_name, d.plan_name, d.standard_charge_dollar"
            ).fetchall()
            dcols = [x[0] for x in con.description]
            for r in drows:
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
    except duckdb.Error as exc:
        q.add("file:duckdb_query_error", {"file": out["file"], "error": str(exc)[:200]})
        out["error"] = "query_error"
    finally:
        con.close()
    out["quarantine"] = q.to_dict()
    return out


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


def run_extractions(paths: list[Path], codes: CodeIndex, workers: int) -> list[dict]:
    index = load_index_by_slug()
    cfg = {"procedures": codes.procedures}
    results: list[dict] = []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(extract_file, str(p), cfg, index.get(p.stem)) for p in paths]
        for i, f in enumerate(futs, 1):
            results.append(f.result())
            if i % 50 == 0 or i == len(futs):
                print(f"  extracted {i}/{len(futs)} files")
    return results


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
    args = ap.parse_args()

    if args.force and RUN_LOCK.exists():
        RUN_LOCK.unlink(missing_ok=True)
    if not acquire_run_lock(args.force):
        return 1
    atexit.register(release_run_lock)

    hospitals = load_hospitals()
    hospitals_by_id = {h["id"]: h for h in hospitals}
    matcher = StrictHospitalMatcher(hospitals)
    codes = CodeIndex()
    previous = read_json(OUT_PRICES, []) or []
    q = Quarantine()
    progress = None

    if args.consolidated:
        paths = [Path(args.consolidated)]
        mode = "consolidated"
    elif args.duckdb_dir:
        paths = list_duckdb(Path(args.duckdb_dir))
        mode = "duckdb-dir"
    elif args.rescan_cache:
        paths = list_duckdb(CACHE_DIR)
        mode = "rescan-cache"
    else:
        mode = "oria"
        index = load_oria_index(refresh=args.refresh_index)
        start = max(0, args.offset)
        end = len(index) if not args.limit else min(len(index), start + args.limit)
        batch = index[start:end]
        print(f"Downloading ORIA entries {start}..{end - 1} of {len(index)} into cache…")
        failures: dict[str, str] = {}
        ok_slugs: list[str] = []
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for slug, err in pool.map(lambda e: ensure_cached(e, not args.no_cache), batch):
                if err:
                    failures[slug] = err
                else:
                    ok_slugs.append(slug)
        paths = [CACHE_DIR / f"{s}.duckdb" for s in sorted(ok_slugs)]
        prev_prog = read_json(PROGRESS_JSON, {}) or {}
        retry = dict(prev_prog.get("failedSlugs") or {})
        for s in ok_slugs:
            retry.pop(s, None)
        retry.update({s: e for s, e in failures.items() if e != "not_completed"})
        progress = {
            "lastBatch": {"offset": start, "end": end, "attempted": len(batch),
                          "cached": len(ok_slugs), "failed": len(failures)},
            # Every index entry in [start, end) was attempted exactly once; entries that
            # failed are carried in failedSlugs for retry rather than silently skipped.
            "nextOffset": end,
            "oriaIndexTotal": len(index),
            "failedSlugs": dict(sorted(retry.items())),
        }
        for s, e in sorted(failures.items()):
            q.add("file:oria_download_failed", {"slug": s, "error": e})

    print(f"Extracting {len(paths)} DuckDB file(s) [{mode}]…")
    extractions = run_extractions(paths, codes, args.workers)
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
        atomic_write_text(PROGRESS_JSON, dump_json(progress))
    elif mode == "rescan-cache":
        prev_prog = read_json(PROGRESS_JSON, {}) or {}
        atomic_write_text(PROGRESS_JSON, dump_json({
            "nextOffset": prev_prog.get("nextOffset", 0),
            "oriaIndexTotal": prev_prog.get("oriaIndexTotal"),
            "failedSlugs": prev_prog.get("failedSlugs", {}),
            "lastRescan": {"files": len(paths), "priceCount": len(rows), "referenceDate": reference_date},
        }))

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
