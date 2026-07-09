#!/usr/bin/env python3
"""
Ingest real hospital prices from CMS-required Machine-Readable Files (MRFs).

Pipeline per hospital system:
  1. Fetch cms-hpt.txt from hospital domain (CMS Hospital Price Transparency rule)
  2. Download each mrf-url listed in cms-hpt.txt
  3. Extract cash / negotiated charges for our procedure CPT & DRG codes
  4. Write data/cms/mrf-prices.json

Data source: each hospital's own published MRF (45 CFR § 180.50).
NOT modeled estimates.

USAGE:
  python etl/ingest_mrf_prices.py                    # seed hospitals with known domains
  python etl/ingest_mrf_prices.py --limit 3          # smoke test
  python etl/ingest_mrf_prices.py --hospital 330214  # single CMS provider id
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics
import sys
import tempfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cms"
SEED_HOSPITALS = ROOT / "data" / "seed" / "hospitals.json"
PROCEDURES = ROOT / "data" / "seed" / "procedures.json"

USER_AGENT = (
    "Mozilla/5.0 (compatible; OpenSourceMed-HospitalCompare/1.0; "
    "+https://opensourcemed.info; hospital-price-transparency-ingest)"
)
MAX_JSON_MB = 250
CHUNK = 256 * 1024


def request_headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/plain,application/json,text/csv,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def fetch_text(url: str, timeout: int = 120) -> str:
    req = Request(url, headers=request_headers())
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def domain_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or ""


def cms_hpt_candidates(website: str | None, shoppable_url: str | None) -> list[str]:
    hosts: list[str] = []
    for u in (website, shoppable_url):
        if not u:
            continue
        host = domain_from_url(u)
        if host and host not in hosts:
            hosts.append(host)
    urls: list[str] = []
    for host in hosts:
        for scheme in ("https", "http"):
            urls.append(f"{scheme}://{host}/cms-hpt.txt")
    return urls


def parse_cms_hpt(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        current[key.strip().lower().replace("-", "_")] = val.strip()
    if current:
        entries.append(current)
    return entries


def load_procedure_index() -> tuple[dict[str, dict], set[str], set[str]]:
    procs = json.loads(PROCEDURES.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in procs}
    cpts: set[str] = set()
    drgs: set[str] = set()
    for p in procs:
        cpts.update(p.get("cptCodes") or [])
        drgs.update(p.get("drgCodes") or [])
    return by_id, cpts, drgs


def match_procedure(cpt: str | None, drg: str | None, by_id: dict[str, dict]) -> str | None:
    for pid, p in by_id.items():
        if cpt and cpt in (p.get("cptCodes") or []):
            return pid
        if drg and drg in (p.get("drgCodes") or []):
            return pid
    return None


def parse_money(val: str | None) -> float | None:
    if not val:
        return None
    v = val.strip().replace("$", "").replace(",", "")
    if not v or v.lower() in ("n/a", "na", ""):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def aggregate_prices(rows: list[dict]) -> dict | None:
    sane = [
        r
        for r in rows
        if (r.get("cash") or 0) >= 75 or (r.get("gross") or 0) >= 75
    ]
    if not sane:
        return None
    cash_vals = [r["cash"] for r in sane if r.get("cash") and r["cash"] >= 75]
    gross_vals = [r["gross"] for r in sane if r.get("gross") and r["gross"] >= 75]
    neg_vals = [r["negotiated"] for r in rows if r.get("negotiated")]
    if not cash_vals and not gross_vals:
        return None
    cash_median = statistics.median(cash_vals) if cash_vals else statistics.median(gross_vals)
    cash_low = min(cash_vals or gross_vals)
    cash_high = max(cash_vals or gross_vals)
    neg_med = statistics.median(neg_vals) if neg_vals else None
    return {
        "cashLow": round(cash_low),
        "cashMedian": round(cash_median),
        "cashHigh": round(cash_high),
        "negotiatedMedian": round(neg_med) if neg_med else None,
    }


def iter_lines(url: str, timeout: int = 300):
    req = Request(url, headers=request_headers())
    with urlopen(req, timeout=timeout) as resp:
        buf = b""
        while True:
            chunk = resp.read(CHUNK)
            if not chunk:
                if buf:
                    yield buf.decode("utf-8", errors="replace")
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                yield line.decode("utf-8", errors="replace")


def extract_from_csv(url: str, cpts: set[str], drgs: set[str]) -> list[dict]:
    hits: list[dict] = []
    found_cpts: set[str] = set()
    found_drgs: set[str] = set()
    header: list[str] | None = None
    for line in iter_lines(url):
        if header is None:
            if line.startswith("code|1,") or ",code|1," in line:
                header = next(csv.reader([line]))
            continue
        if not header:
            continue
        row = next(csv.reader([line]))
        if len(row) < len(header):
            row.extend([""] * (len(header) - len(row)))
        data = dict(zip(header, row))
        cpt = (data.get("code|1") or "").strip()
        drg = (data.get("code|1") or data.get("ms_drg") or "").strip()
        ctype = (data.get("code|1|type") or "").upper()
        if ctype == "DRG" or (drg in drgs and drg):
            code, kind = drg, "drg"
        elif cpt in cpts:
            code, kind = cpt, "cpt"
        else:
            continue
        cash = parse_money(data.get("standard_charge|discounted_cash"))
        gross = parse_money(data.get("standard_charge|gross"))
        neg = parse_money(data.get("standard_charge|negotiated_dollar"))
        if neg is None:
            for k, v in data.items():
                if "negotiated" in k.lower() and "dollar" in k.lower():
                    neg = parse_money(v)
                    if neg:
                        break
        hits.append({
            "code": code,
            "kind": kind,
            "cash": cash,
            "gross": gross,
            "negotiated": neg,
            "description": (data.get("description") or "")[:120],
        })
        if kind == "cpt":
            found_cpts.add(code)
        else:
            found_drgs.add(code)
        if found_cpts >= cpts and found_drgs >= drgs:
            break
    return hits


def download_temp(url: str, max_bytes: int) -> Path:
    req = Request(url, headers=request_headers())
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mrf")
    path = Path(tmp.name)
    total = 0
    with urlopen(req, timeout=300) as resp, open(path, "wb") as out:
        while True:
            chunk = resp.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"MRF exceeds {max_bytes // 1_048_576} MB cap")
            out.write(chunk)
    return path


def extract_from_json(url: str, cpts: set[str], drgs: set[str]) -> list[dict]:
    """Scan JSON MRF for CPT/DRG blocks (CMS v2 wide format)."""
    path = download_temp(url, MAX_JSON_MB * 1_048_576)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    finally:
        path.unlink(missing_ok=True)

    hits: list[dict] = []
    all_codes = cpts | drgs
    for code in all_codes:
        for m in re.finditer(rf'"code"\s*:\s*"{re.escape(code)}"', text):
            window = text[m.start() : m.start() + 4000]
            cash_m = re.search(r'"discounted_cash_price"\s*:\s*([0-9.]+)', window)
            gross_m = re.search(r'"gross_charge"\s*:\s*([0-9.]+)', window)
            neg_m = re.search(r'"negotiated_dollar"\s*:\s*([0-9.]+)', window)
            if not cash_m and not gross_m:
                continue
            hits.append({
                "code": code,
                "kind": "drg" if code in drgs else "cpt",
                "cash": float(cash_m.group(1)) if cash_m else None,
                "gross": float(gross_m.group(1)) if gross_m else None,
                "negotiated": float(neg_m.group(1)) if neg_m else None,
                "description": "",
            })
    return hits


def extract_mrf(url: str, cpts: set[str], drgs: set[str]) -> list[dict]:
    lower = url.lower()
    if lower.endswith(".csv"):
        return extract_from_csv(url, cpts, drgs)
    if lower.endswith(".json"):
        return extract_from_json(url, cpts, drgs)
    try:
        return extract_from_json(url, cpts, drgs)
    except Exception:
        return extract_from_csv(url, cpts, drgs)


def ingest_hospital(
    seed: dict,
    by_id: dict[str, dict],
    cpts: set[str],
    drgs: set[str],
) -> list[dict]:
    cms_id = seed.get("cmsProviderId")
    if not cms_id:
        return []

    hpt_text = None
    hpt_url = None
    for candidate in cms_hpt_candidates(seed.get("website"), seed.get("shoppableUrl")):
        try:
            hpt_text = fetch_text(candidate, timeout=60)
            hpt_url = candidate
            break
        except Exception:
            continue

    if not hpt_text:
        print(f"  [{cms_id}] no cms-hpt.txt found")
        return []

    entries = parse_cms_hpt(hpt_text)
    print(f"  [{cms_id}] {seed.get('name')} — {len(entries)} MRF location(s) from {hpt_url}")

    proc_rows: dict[str, list[dict]] = {}
    vintage = date.today().isoformat()
    mrf_used = None

    for entry in entries:
        mrf_url = entry.get("mrf_url")
        if not mrf_url:
            continue
        location = entry.get("location_name", "")
        try:
            raw_hits = extract_mrf(mrf_url, cpts, drgs)
        except Exception as exc:
            print(f"    skip {location[:40]}: {exc}")
            continue
        if not raw_hits:
            continue
        mrf_used = mrf_url
        for hit in raw_hits:
            proc_id = match_procedure(
                hit["code"] if hit["kind"] == "cpt" else None,
                hit["code"] if hit["kind"] == "drg" else None,
                by_id,
            )
            if not proc_id:
                continue
            proc_rows.setdefault(proc_id, []).append(hit)

    results: list[dict] = []
    for proc_id, rows in proc_rows.items():
        agg = aggregate_prices(rows)
        if not agg:
            continue
        results.append({
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
            "priceSource": "hospital_mrf",
            "priceVintage": vintage,
            "mrfUrl": mrf_used,
            "cmsHptUrl": hpt_url,
        })
    print(f"    → {len(results)} procedure price(s) extracted")
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Max hospital systems to process")
    ap.add_argument("--hospital", help="CMS provider id (e.g. 330214)")
    args = ap.parse_args()

    by_id, cpts, drgs = load_procedure_index()
    seeds = json.loads(SEED_HOSPITALS.read_text(encoding="utf-8"))

    if args.hospital:
        seeds = [s for s in seeds if s.get("cmsProviderId") == args.hospital]
    if args.limit:
        seeds = seeds[: args.limit]

    all_prices: list[dict] = []
    seen_cms: set[str] = set()
    for seed in seeds:
        cms_id = seed.get("cmsProviderId")
        if not cms_id or cms_id in seen_cms:
            continue
        seen_cms.add(cms_id)
        print(f"Ingesting {seed.get('name')}…")
        all_prices.extend(ingest_hospital(seed, by_id, cpts, drgs))

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "mrf-prices.json"
    out_path.write_text(json.dumps(all_prices, indent=2), encoding="utf-8")
    meta_path = OUT / "mrf-meta.json"
    meta = {
        "priceCount": len(all_prices),
        "hospitalSystemsProcessed": len(seen_cms),
        "source": "CMS Hospital Price Transparency MRF files (cms-hpt.txt → mrf-url)",
        "method": "Direct download and CPT/DRG extraction from each hospital's published MRF",
        "builtAt": date.today().isoformat(),
        "note": "Prices are as published by hospitals. OOP PPO/HDHP are rough ratios until plan data is added.",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nWrote {len(all_prices)} prices → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())