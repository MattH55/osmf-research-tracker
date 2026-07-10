#!/usr/bin/env python3
"""
Ingest hospital prices from Trilliant Health ORIA parsed DuckDB files.

Trilliant parses each hospital's CMS-required MRF into DuckDB (standard_charges
table). This script extracts our 24 shoppable CPT/DRG codes and maps facilities
to CMS Provider IDs in data/cms/hospitals.json.

Sources (pick one):
  --consolidated PATH   Oria "Full Data Download" DuckDB archive
  --duckdb-dir PATH     Folder of per-hospital *_parsed.duckdb files
  --oria                Download from oria-data.trillianthealth.com (public)

Output:
  data/cms/trilliant-prices.json
  data/cms/trilliant-meta.json

With --merge, also writes data/cms/mrf-prices.json combining direct MRF scrape
(hospital_mrf) and Trilliant (trilliant_mrf); direct scrape wins on conflicts.

USAGE:
  python etl/ingest_trilliant.py --consolidated data/trilliant/consolidated.duckdb
  python etl/ingest_trilliant.py --duckdb-dir data/trilliant/duckdb
  python etl/ingest_trilliant.py --oria --limit 50
  python etl/ingest_trilliant.py --oria --merge
"""

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import statistics
import sys
import tempfile
import time
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
CMS_DIR = ROOT / "data" / "cms"
TRILLIANT_DIR = ROOT / "data" / "trilliant"
CACHE_DIR = TRILLIANT_DIR / "cache"
HOSPITALS_JSON = CMS_DIR / "hospitals.json"
PROCEDURES_JSON = ROOT / "data" / "seed" / "procedures.json"
MRF_PRICES_JSON = CMS_DIR / "mrf-prices.json"
OUT_PRICES = CMS_DIR / "trilliant-prices.json"
OUT_META = CMS_DIR / "trilliant-meta.json"

ORIA_INDEX_URL = "https://oria-data.trillianthealth.com/search-index.json"
ORIA_HOSPITAL_URL = "https://oria-data.trillianthealth.com/hospital/{slug}"
USER_AGENT = (
    "Mozilla/5.0 (compatible; OpenSourceMed-HospitalCompare/1.0; "
    "+https://opensourcemed.info; trilliant-orias-ingest)"
)
DUCKDB_PATH_RE = re.compile(r'(/data/store/[^"\']+_parsed\.duckdb)')
ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")
NAME_STOPWORDS = {
    "hospital", "medical", "center", "centre", "health", "regional",
    "community", "memorial", "general", "the", "of", "and", "inc", "llc",
    "dba", "at", "campus", "system", "st", "saint", "san",
}


def fetch_text(url: str, timeout: int = 120) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def atomic_write_text(path: Path, content: str, retries: int = 8) -> None:
    """Write via temp file + replace to avoid Windows/OneDrive lock errors."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    for attempt in range(retries):
        try:
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(path)
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))
        finally:
            if tmp.exists() and not path.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass


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


RUN_LOCK = CMS_DIR / ".trilliant-ingest.lock"


def acquire_run_lock(force: bool) -> bool:
    if RUN_LOCK.exists() and not force:
        try:
            holder = RUN_LOCK.read_text(encoding="utf-8").strip()
        except OSError:
            holder = "unknown"
        print(
            f"\nAnother Trilliant ingest may be running (lock: {RUN_LOCK}, pid {holder}).\n"
            "Stop other python ingest processes, then retry.\n"
            "If nothing is running, pass --force to clear the lock.\n",
            file=sys.stderr,
        )
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


def normalize_name(name: str) -> set[str]:
    tokens = re.sub(r"[^a-z0-9\s]", " ", name.lower()).split()
    return {t for t in tokens if t and t not in NAME_STOPWORDS and len(t) > 1}


def normalize_address(addr: str) -> set[str]:
    tokens = re.sub(r"[^a-z0-9\s]", " ", addr.lower()).split()
    return {t for t in tokens if t and not t.isdigit() and len(t) > 2}


def extract_zip(text: str) -> str | None:
    m = ZIP_RE.search(text or "")
    return m.group(1) if m else None


def extract_street_number(text: str) -> str | None:
    m = re.search(r"\b(\d{1,6})\b", text or "")
    return m.group(1) if m else None


def parse_city_from_address(address: str) -> str:
    """Parse '420 Thomson Circle, Abbeville, SC 29620' → Abbeville."""
    if not address:
        return ""
    parts = [p.strip() for p in address.split(",") if p.strip()]
    if len(parts) >= 2:
        city_part = parts[-2] if ZIP_RE.search(parts[-1]) else parts[-1]
        city_part = re.sub(r"\b[A-Z]{2}\b", "", city_part).strip()
        return city_part
    return ""


def flatten_address(addr) -> str:
    if addr is None:
        return ""
    if isinstance(addr, (list, tuple)):
        return " | ".join(str(a) for a in addr if a)
    return str(addr)


def load_procedure_index() -> tuple[dict[str, dict], set[str], set[str], dict[str, str]]:
    procs = json.loads(PROCEDURES_JSON.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in procs}
    cpts: set[str] = set()
    drgs: set[str] = set()
    code_to_proc: dict[str, str] = {}
    for p in procs:
        for c in p.get("cptCodes") or []:
            cpts.add(c)
            code_to_proc[f"cpt:{c}"] = p["id"]
        for d in p.get("drgCodes") or []:
            drgs.add(d)
            code_to_proc[f"drg:{d}"] = p["id"]
    return by_id, cpts, drgs, code_to_proc


def aggregate_rows(rows: list[dict]) -> dict | None:
    sane = [
        r for r in rows
        if (r.get("cash") or 0) >= 75 or (r.get("gross") or 0) >= 75
    ]
    if not sane:
        return None
    cash_vals = [r["cash"] for r in sane if r.get("cash") and r["cash"] >= 75]
    gross_vals = [r["gross"] for r in sane if r.get("gross") and r["gross"] >= 75]
    neg_vals = [r["negotiated"] for r in rows if r.get("negotiated")]
    if not cash_vals and not gross_vals:
        return None
    base = cash_vals or gross_vals
    cash_median = statistics.median(cash_vals) if cash_vals else statistics.median(gross_vals)
    neg_med = statistics.median(neg_vals) if neg_vals else None
    return {
        "cashLow": round(min(base)),
        "cashMedian": round(cash_median),
        "cashHigh": round(max(base)),
        "negotiatedMedian": round(neg_med) if neg_med else None,
    }


class CmsMatcher:
    def __init__(self, hospitals: list[dict]):
        self.hospitals = hospitals
        self.by_zip: dict[tuple[str, str], list[dict]] = defaultdict(list)
        self.by_state: dict[str, list[dict]] = defaultdict(list)
        for h in hospitals:
            state = (h.get("state") or "").upper()
            zip5 = (h.get("zip") or "")[:5]
            if state:
                self.by_state[state].append(h)
            if state and zip5:
                self.by_zip[(state, zip5)].append(h)

    def match(
        self,
        name: str,
        address: str,
        state: str,
        city: str = "",
    ) -> dict | None:
        state = (state or "").upper()
        if not state:
            return None
        parsed_city = city or parse_city_from_address(address)
        zip5 = extract_zip(address) or extract_zip(parsed_city) or extract_zip(name)
        name_tokens = normalize_name(name)
        addr_tokens = normalize_address(address)
        street_num = extract_street_number(address)

        candidates: list[dict] = []
        if zip5 and (state, zip5) in self.by_zip:
            candidates = self.by_zip[(state, zip5)]
        else:
            candidates = self.by_state.get(state, [])

        if not candidates:
            return None

        best: dict | None = None
        best_score = 0.0
        for h in candidates:
            h_name = normalize_name(h.get("name", ""))
            h_addr = normalize_address(h.get("address", ""))
            if not name_tokens:
                continue
            name_overlap = len(name_tokens & h_name) / max(len(name_tokens | h_name), 1)
            addr_overlap = (
                len(addr_tokens & h_addr) / max(len(addr_tokens | h_addr), 1)
                if addr_tokens and h_addr
                else 0.0
            )
            h_zip = (h.get("zip") or "")[:5]
            zip_match = zip5 and h_zip == zip5
            zip_bonus = 0.3 if zip_match else 0.0
            city_bonus = (
                0.12
                if parsed_city
                and parsed_city.lower() in (h.get("city") or "").lower()
                else 0.0
            )
            street_bonus = (
                0.15
                if street_num and street_num == extract_street_number(h.get("address", ""))
                else 0.0
            )
            score = (
                name_overlap * 0.55
                + addr_overlap * 0.2
                + zip_bonus
                + city_bonus
                + street_bonus
            )
            if score > best_score:
                best_score = score
                best = h

        threshold = 0.18 if zip5 and best and (best.get("zip") or "")[:5] == zip5 else 0.26
        if best_score < threshold:
            return None
        return best


def match_oria_entry(entry: dict, matcher: CmsMatcher) -> dict | None:
    name = entry.get("locationName") or entry.get("hospitalName") or ""
    address = entry.get("address") or ""
    state = entry.get("state") or ""
    city = entry.get("city") or parse_city_from_address(address)
    return matcher.match(name, address, state, city)


def remap_prices_to_cms(prices: list[dict], cms: dict) -> list[dict]:
    cms_id = cms["cmsProviderId"]
    remapped: list[dict] = []
    seen: set[str] = set()
    for p in prices:
        proc = p["procedureId"]
        if proc in seen:
            continue
        seen.add(proc)
        remapped.append({
            **p,
            "hospitalId": f"hosp-cms-{cms_id}",
            "cmsProviderId": cms_id,
        })
    return remapped


def hospital_columns(con: duckdb.DuckDBPyConnection) -> set[str]:
    try:
        rows = con.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'hospitals'"
        ).fetchall()
        return {r[0] for r in rows}
    except duckdb.Error:
        return set()


def charge_query(cpts: set[str], drgs: set[str], h_cols: set[str]) -> str:
    cpt_list = ", ".join(f"'{c}'" for c in sorted(cpts))
    drg_list = ", ".join(f"'{d}'" for d in sorted(drgs))
    city_sel = "h.hospital_city" if "hospital_city" in h_cols else "NULL AS hospital_city"
    return f"""
        SELECT
            h.hospital_name,
            h.hospital_address,
            h.hospital_state,
            {city_sel},
            sc.cpt,
            sc.ms_drg,
            sc.discounted_cash,
            sc.gross_charge,
            sc.avg_negotiated_rate,
            sc.minimum,
            sc.maximum
        FROM standard_charges sc
        JOIN hospitals h ON h.hospital_id = sc.hospital_id
        WHERE sc.cpt IN ({cpt_list}) OR sc.ms_drg IN ({drg_list})
    """


def extract_from_connection(
    con: duckdb.DuckDBPyConnection,
    matcher: CmsMatcher,
    code_to_proc: dict[str, str],
    cpts: set[str],
    drgs: set[str],
    source_url: str = "",
    vintage: str | None = None,
) -> tuple[list[dict], dict]:
    vintage = vintage or date.today().isoformat()
    h_cols = hospital_columns(con)
    try:
        rows = con.execute(charge_query(cpts, drgs, h_cols)).fetchall()
        cols = [d[0] for d in con.description]
    except duckdb.Error:
        return [], {"matched": 0, "unmatched": 0, "skipped": True}

    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    facility_meta: dict[str, dict] = {}

    for raw in rows:
        row = dict(zip(cols, raw))
        name = row.get("hospital_name") or ""
        address = flatten_address(row.get("hospital_address"))
        state = row.get("hospital_state") or ""
        city = row.get("hospital_city") or ""
        fac_key = f"{name}|{address}|{state}"

        if fac_key not in facility_meta:
            facility_meta[fac_key] = {
                "name": name,
                "address": address,
                "state": state,
                "city": city,
            }

        cpt = (row.get("cpt") or "").strip()
        drg = (row.get("ms_drg") or "").strip()
        proc_id = None
        if cpt and f"cpt:{cpt}" in code_to_proc:
            proc_id = code_to_proc[f"cpt:{cpt}"]
        elif drg and f"drg:{drg}" in code_to_proc:
            proc_id = code_to_proc[f"drg:{drg}"]
        if not proc_id:
            continue

        cash = row.get("discounted_cash")
        gross = row.get("gross_charge")
        neg = row.get("avg_negotiated_rate")
        grouped[(fac_key, proc_id)].append({
            "cash": float(cash) if cash is not None else None,
            "gross": float(gross) if gross is not None else None,
            "negotiated": float(neg) if neg is not None else None,
        })

    prices: list[dict] = []
    matched = 0
    unmatched = 0
    seen_cms: set[str] = set()

    for (fac_key, proc_id), charge_rows in grouped.items():
        meta = facility_meta[fac_key]
        cms = matcher.match(meta["name"], meta["address"], meta["state"], meta["city"])
        if not cms:
            unmatched += 1
            continue
        matched += 1
        cms_id = cms["cmsProviderId"]
        seen_cms.add(cms_id)
        agg = aggregate_rows(charge_rows)
        if not agg:
            continue
        prices.append({
            "hospitalId": f"hosp-cms-{cms_id}",
            "cmsProviderId": cms_id,
            "procedureId": proc_id,
            "cashLow": agg["cashLow"],
            "cashMedian": agg["cashMedian"],
            "cashHigh": agg["cashHigh"],
            "negotiatedMedian": agg["negotiatedMedian"],
            "negotiatedLow": None,
            "negotiatedHigh": None,
            "oopUninsured": agg["cashMedian"],
            "oopPpo": round(agg["cashMedian"] * 0.15) if agg["cashMedian"] else None,
            "oopHdhp": round(agg["cashMedian"] * 0.22) if agg["cashMedian"] else None,
            "priceSource": "trilliant_mrf",
            "priceVintage": vintage,
            "mrfUrl": source_url or None,
            "trilliantFacility": meta["name"],
        })

    return prices, {
        "matched": matched,
        "unmatched": unmatched,
        "hospitals": len(seen_cms),
        "prices": len(prices),
    }


def read_vintage(con: duckdb.DuckDBPyConnection) -> str:
    try:
        row = con.execute(
            "SELECT last_updated_on FROM hospitals WHERE last_updated_on IS NOT NULL LIMIT 1"
        ).fetchone()
        if row and row[0]:
            return str(row[0])[:10]
    except duckdb.Error:
        pass
    try:
        row = con.execute(
            "SELECT last_updated_on FROM mrf_metadata WHERE last_updated_on IS NOT NULL LIMIT 1"
        ).fetchone()
        if row and row[0]:
            return str(row[0])[:10]
    except duckdb.Error:
        pass
    return date.today().isoformat()


def ingest_duckdb_file(
    path: Path,
    matcher: CmsMatcher,
    code_to_proc: dict[str, str],
    cpts: set[str],
    drgs: set[str],
    source_url: str = "",
) -> tuple[list[dict], dict]:
    con = duckdb.connect(str(path), read_only=True)
    try:
        vintage = read_vintage(con)
        return extract_from_connection(
            con, matcher, code_to_proc, cpts, drgs, source_url, vintage
        )
    finally:
        con.close()


def ingest_consolidated(
    path: Path,
    matcher: CmsMatcher,
    code_to_proc: dict[str, str],
    cpts: set[str],
    drgs: set[str],
) -> tuple[list[dict], dict]:
    print(f"Querying consolidated DuckDB: {path}")
    con = duckdb.connect(str(path), read_only=True)
    try:
        vintage = read_vintage(con)
        return extract_from_connection(
            con, matcher, code_to_proc, cpts, drgs, str(path), vintage
        )
    finally:
        con.close()


def discover_duckdb_paths(slug: str) -> str | None:
    try:
        html = fetch_text(ORIA_HOSPITAL_URL.format(slug=slug), timeout=60)
    except Exception:
        return None
    m = DUCKDB_PATH_RE.search(html)
    if not m:
        return None
    return "https://oria-data.trillianthealth.com" + m.group(1)


def process_oria_hospital(
    entry: dict,
    matcher: CmsMatcher,
    code_to_proc: dict[str, str],
    cpts: set[str],
    drgs: set[str],
    use_cache: bool,
) -> tuple[list[dict], dict, str]:
    slug = entry["id"]
    name = entry.get("locationName") or entry.get("hospitalName") or slug
    if entry.get("status") != "completed":
        return [], {"skipped": True, "reason": "not_completed"}, slug

    cache_path = CACHE_DIR / f"{slug}.duckdb"
    duckdb_url = discover_duckdb_paths(slug)
    if not duckdb_url:
        return [], {"skipped": True, "reason": "no_duckdb_url"}, slug

    if not (use_cache and cache_path.exists() and cache_path.stat().st_size > 1000):
        try:
            download_file(duckdb_url, cache_path)
        except Exception as exc:
            return [], {"skipped": True, "reason": str(exc)[:120]}, slug

    if not cache_path.exists() or cache_path.stat().st_size < 1000:
        return [], {"skipped": True, "reason": "incomplete_download"}, slug

    index_cms = match_oria_entry(entry, matcher)

    prices, stats = ingest_duckdb_file(
        cache_path,
        matcher,
        code_to_proc,
        cpts,
        drgs,
        duckdb_url,
    )

    if not prices and index_cms:
        stats["indexMatchOnly"] = True

    if index_cms and prices:
        duckdb_cms_ids = {p.get("cmsProviderId") for p in prices if p.get("cmsProviderId")}
        if not duckdb_cms_ids or index_cms["cmsProviderId"] not in duckdb_cms_ids:
            prices = remap_prices_to_cms(prices, index_cms)
            stats["remappedViaIndex"] = True

    stats["name"] = name
    if index_cms:
        stats["indexCmsId"] = index_cms["cmsProviderId"]
    return prices, stats, slug


def ingest_oria(
    matcher: CmsMatcher,
    code_to_proc: dict[str, str],
    cpts: set[str],
    drgs: set[str],
    limit: int = 0,
    offset: int = 0,
    workers: int = 4,
    use_cache: bool = True,
) -> tuple[list[dict], dict]:
    print("Fetching ORIA search index…")
    index = json.loads(fetch_text(ORIA_INDEX_URL))
    total_index = len(index)
    if offset:
        index = index[offset:]
    if limit:
        index = index[:limit]
    print(
        f"Processing {len(index)} ORIA hospitals "
        f"(offset {offset}, index total {total_index}, {workers} workers)…"
    )

    all_prices: list[dict] = []
    stats_agg = {
        "oriaIndexTotal": total_index,
        "oriaHospitals": len(index),
        "offset": offset,
        "processed": 0,
        "skipped": 0,
        "matchedFacilities": 0,
        "unmatchedFacilities": 0,
        "indexRemapped": 0,
        "cmsHospitals": set(),
        "errors": 0,
    }

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                process_oria_hospital,
                entry,
                matcher,
                code_to_proc,
                cpts,
                drgs,
                use_cache,
            ): entry
            for entry in index
        }
        for i, fut in enumerate(as_completed(futures), 1):
            entry = futures[fut]
            slug = entry.get("id", "?")
            try:
                prices, stats, slug = fut.result()
            except Exception as exc:
                stats_agg["errors"] += 1
                print(f"  [{i}/{len(index)}] {slug}: ERROR {exc}")
                continue

            if stats.get("skipped"):
                stats_agg["skipped"] += 1
                if i % 25 == 0 or limit and limit <= 20:
                    print(f"  [{i}/{len(index)}] {slug}: skip ({stats.get('reason', '?')})")
                continue

            stats_agg["processed"] += 1
            stats_agg["matchedFacilities"] += stats.get("matched", 0)
            stats_agg["unmatchedFacilities"] += stats.get("unmatched", 0)
            if stats.get("remappedViaIndex"):
                stats_agg["indexRemapped"] += 1
            stats_agg["cmsHospitals"].update(
                p["cmsProviderId"] for p in prices if p.get("cmsProviderId")
            )
            all_prices.extend(prices)

            if prices:
                print(
                    f"  [{i}/{len(index)}] {stats.get('name', slug)}: "
                    f"{len(prices)} price(s), CMS hospitals={stats.get('hospitals', 0)}"
                )
            elif i % 50 == 0:
                print(f"  [{i}/{len(index)}] … {len(all_prices)} total prices so far")

    stats_agg["cmsHospitals"] = len(stats_agg["cmsHospitals"])
    return all_prices, stats_agg


def ingest_duckdb_dir(
    directory: Path,
    matcher: CmsMatcher,
    code_to_proc: dict[str, str],
    cpts: set[str],
    drgs: set[str],
) -> tuple[list[dict], dict]:
    files = sorted(directory.rglob("*_parsed.duckdb")) + sorted(directory.rglob("*.duckdb"))
    files = [f for f in files if f.is_file()]
    # dedupe
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in files:
        if f.resolve() not in seen:
            seen.add(f.resolve())
            unique.append(f)

    print(f"Scanning {len(unique)} DuckDB file(s) in {directory}")
    all_prices: list[dict] = []
    cms_ids: set[str] = set()
    for i, path in enumerate(unique, 1):
        prices, stats = ingest_duckdb_file(path, matcher, code_to_proc, cpts, drgs, str(path))
        all_prices.extend(prices)
        cms_ids.update(p["cmsProviderId"] for p in prices if p.get("cmsProviderId"))
        if prices:
            print(f"  [{i}/{len(unique)}] {path.name}: {len(prices)} price(s)")
    return all_prices, {"duckdbFiles": len(unique), "cmsHospitals": len(cms_ids)}


def dedupe_prices(prices: list[dict]) -> list[dict]:
    """Keep best price per (cmsProviderId, procedureId) — lowest cash median."""
    best: dict[tuple[str, str], dict] = {}
    for p in prices:
        key = (p.get("cmsProviderId") or p["hospitalId"], p["procedureId"])
        prev = best.get(key)
        if not prev or (p.get("cashMedian") or 0) < (prev.get("cashMedian") or 9e18):
            best[key] = p
    return list(best.values())


def merge_price_lists(
    direct: list[dict],
    trilliant: list[dict],
) -> list[dict]:
    """Direct hospital_mrf scrape wins over trilliant_mrf."""
    by_key: dict[tuple[str, str], dict] = {}
    for p in trilliant:
        key = (p.get("cmsProviderId") or p["hospitalId"], p["procedureId"])
        by_key[key] = p
    for p in direct:
        key = (p.get("cmsProviderId") or p["hospitalId"], p["procedureId"])
        by_key[key] = p
    return list(by_key.values())


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest Trilliant ORIA MRF prices")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--consolidated", metavar="PATH", help="Consolidated Oria DuckDB file")
    src.add_argument("--duckdb-dir", metavar="PATH", help="Directory of per-hospital DuckDB files")
    src.add_argument("--oria", action="store_true", help="Download from ORIA public directory")
    ap.add_argument("--limit", type=int, default=0, help="Max ORIA hospitals per batch")
    ap.add_argument("--offset", type=int, default=0, help="Skip first N ORIA index entries")
    ap.add_argument("--workers", type=int, default=4, help="Parallel ORIA downloads")
    ap.add_argument("--no-cache", action="store_true", help="Re-download ORIA DuckDB files")
    ap.add_argument(
        "--append",
        action="store_true",
        help="Merge with existing trilliant-prices.json instead of replacing",
    )
    ap.add_argument("--merge", action="store_true", help="Merge into data/cms/mrf-prices.json")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Ignore stale lock file if no other ingest is running",
    )
    args = ap.parse_args()

    if args.force and RUN_LOCK.exists():
        try:
            RUN_LOCK.unlink()
        except OSError:
            pass

    if not acquire_run_lock(args.force):
        return 1
    atexit.register(release_run_lock)

    if not HOSPITALS_JSON.exists():
        print(f"Missing {HOSPITALS_JSON} — run: npm run build:data", file=sys.stderr)
        return 1

    hospitals = json.loads(HOSPITALS_JSON.read_text(encoding="utf-8"))
    matcher = CmsMatcher(hospitals)
    _, cpts, drgs, code_to_proc = load_procedure_index()

    if args.consolidated:
        path = Path(args.consolidated)
        if not path.exists():
            print(f"File not found: {path}", file=sys.stderr)
            return 1
        all_prices, run_stats = ingest_consolidated(path, matcher, code_to_proc, cpts, drgs)
    elif args.duckdb_dir:
        path = Path(args.duckdb_dir)
        if not path.is_dir():
            print(f"Directory not found: {path}", file=sys.stderr)
            return 1
        all_prices, run_stats = ingest_duckdb_dir(path, matcher, code_to_proc, cpts, drgs)
    else:
        all_prices, run_stats = ingest_oria(
            matcher,
            code_to_proc,
            cpts,
            drgs,
            limit=args.limit,
            offset=args.offset,
            workers=args.workers,
            use_cache=not args.no_cache,
        )

    if args.append and OUT_PRICES.exists():
        for attempt in range(8):
            try:
                existing = json.loads(OUT_PRICES.read_text(encoding="utf-8"))
                break
            except OSError:
                if attempt == 7:
                    raise
                time.sleep(1.5 * (attempt + 1))
        all_prices = dedupe_prices(existing + all_prices)
    else:
        all_prices = dedupe_prices(all_prices)
    CMS_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_text(OUT_PRICES, json.dumps(all_prices, indent=2))

    meta = {
        "priceCount": len(all_prices),
        "cmsHospitalsWithPrices": len({p.get("cmsProviderId") for p in all_prices}),
        "source": "Trilliant Health ORIA parsed hospital MRF DuckDB files",
        "attribution": "https://oria-data.trillianthealth.com/",
        "method": "DuckDB standard_charges query + CMS hospital fuzzy match (name/state/zip)",
        "builtAt": date.today().isoformat(),
        "runStats": run_stats,
        "note": (
            "Prices are as published in hospital MRFs, parsed by Trilliant Health. "
            "For full nationwide coverage, download the consolidated archive from "
            "https://oria.trillianthealth.com/full-data-download"
        ),
    }
    atomic_write_text(OUT_META, json.dumps(meta, indent=2))
    print(f"\nWrote {len(all_prices)} Trilliant prices → {OUT_PRICES}")

    if args.merge:
        existing = []
        if MRF_PRICES_JSON.exists():
            existing = json.loads(MRF_PRICES_JSON.read_text(encoding="utf-8"))
        direct = [p for p in existing if p.get("priceSource") == "hospital_mrf"]
        merged = merge_price_lists(all_prices, direct)
        MRF_PRICES_JSON.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        print(f"Merged {len(merged)} total prices → {MRF_PRICES_JSON}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())