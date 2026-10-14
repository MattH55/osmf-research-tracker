#!/usr/bin/env python3
"""
Ingest hospital prices directly from CMS-required machine-readable files (MRFs).

Pipeline per seed hospital (data/seed/hospitals.json):
  1. Fetch cms-hpt.txt from the hospital's domain (45 CFR 180.50(d)(6)).
  2. Keep ONLY the cms-hpt entries whose location-name strictly matches this
     hospital (etl/price_contract.StrictHospitalMatcher must resolve the
     location to this hospital's CCN). A system-wide file is never attached to
     every member hospital; an entry for another campus (e.g. NYU Langone
     Suffolk for NYU Langone 330214) is skipped and recorded.
  3. Download the MRF into data/mrf/cache/<CCN>/ (so the extract can be
     re-derived offline with --offline) and parse CMS template v2 CSV (tall or
     wide) or JSON.
  4. Apply the shared contract (etl/price_contract.py): explicit code types,
     canonical scope, cash = discounted cash only, negotiated = dollar payer
     rates, bounds, vintage = the file's last_updated_on.

Output: data/cms/mrf-prices.json (hospital_mrf rows only), data/cms/mrf-meta.json,
and the "hospital_mrf" section of data/cms/quarantine.json.

USAGE:
  python etl/ingest_mrf_prices.py --hospital 330214   # one CMS provider id (network)
  python etl/ingest_mrf_prices.py --limit 3           # smoke test (network)
  python etl/ingest_mrf_prices.py --offline           # rebuild from data/mrf/cache only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
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
    write_quarantine_section,
)

SEED_HOSPITALS = ROOT / "data" / "seed" / "hospitals.json"
MRF_CACHE = ROOT / "data" / "mrf" / "cache"
OUT_PRICES = CMS_DIR / "mrf-prices.json"
OUT_META = CMS_DIR / "mrf-meta.json"
QUARANTINE_SECTION = "hospital_mrf"
MAX_BYTES = 1024 * 1_048_576
CHUNK = 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (compatible; OpenSourceMed-HospitalCompare/1.0; "
    "+https://opensourcemed.info; hospital-price-transparency-ingest)"
)


# ============================================================ network

def fetch_text(url: str, timeout: int = 60) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def cms_hpt_candidates(website: str | None, shoppable_url: str | None) -> list[str]:
    hosts: list[str] = []
    for u in (website, shoppable_url):
        host = urlparse(u).netloc if u else ""
        if host and host not in hosts:
            hosts.append(host)
    return [f"https://{h}/cms-hpt.txt" for h in hosts]


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
        key = key.strip().lower().replace("-", "_")
        if key in current:  # entries not separated by a blank line
            entries.append(current)
            current = {}
        current[key] = val.strip()
    if current:
        entries.append(current)
    return entries


def download(url: str, dest: Path) -> str:
    """Download to dest; returns sha256 of the bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    total = 0
    part = dest.with_suffix(dest.suffix + ".part")
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=600) as resp, open(part, "wb") as out:
        while True:
            chunk = resp.read(CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                raise ValueError("MRF exceeds size cap")
            h.update(chunk)
            out.write(chunk)
    part.replace(dest)
    return h.hexdigest()


# ============================================================ parsing (CMS template v2)

def parse_money(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    v = str(val).strip().replace("$", "").replace(",", "")
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def codes_from_pairs(pairs: list[tuple[str, str]]) -> str:
    """Render (code, type) pairs as an all_codes string: 'CPT:45378 | RC:0750'."""
    return " | ".join(f"{(t or '').strip().upper()}:{(c or '').strip()}" for c, t in pairs if c)


def parse_csv(path: Path) -> tuple[dict, list[dict]]:
    """CMS v2 CSV (tall or wide). Returns (header_meta, lines)."""
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.reader(f)
        head_keys = [h.strip().lower() for h in next(reader)]
        head_vals = next(reader)
        meta = dict(zip(head_keys, head_vals))
        cols = [c.strip().lower() for c in next(reader)]
        code_idx = []
        for i, c in enumerate(cols):
            m = re.fullmatch(r"code\|(\d+)", c)
            if m and f"code|{m.group(1)}|type" in cols:
                code_idx.append((i, cols.index(f"code|{m.group(1)}|type")))
        ix = {c: i for i, c in enumerate(cols)}
        wide = [
            (i, c) for i, c in enumerate(cols)
            if c.startswith("standard_charge|") and c.endswith("|negotiated_dollar") and c.count("|") == 3
        ]
        meth_cols = {c.rsplit("|", 1)[0]: i for i, c in enumerate(cols) if c.endswith("|methodology") and c.count("|") == 3}

        def get(row, name):
            i = ix.get(name)
            return row[i] if i is not None and i < len(row) else None

        lines: list[dict] = []
        for n, row in enumerate(reader, start=4):
            if not row:
                continue
            all_codes = codes_from_pairs([(row[a] if a < len(row) else "", row[b] if b < len(row) else "")
                                          for a, b in code_idx])
            rates = []
            if "payer_name" in ix:
                rates.append({
                    "payer": get(row, "payer_name"), "plan": get(row, "plan_name"),
                    "dollar": parse_money(get(row, "standard_charge|negotiated_dollar")),
                    "methodology": get(row, "standard_charge|methodology"),
                })
            for i, c in wide:
                _, payer, plan, _ = c.split("|")
                meth_i = meth_cols.get(f"standard_charge|{payer}|{plan}")
                rates.append({
                    "payer": payer, "plan": plan,
                    "dollar": parse_money(row[i] if i < len(row) else None),
                    "methodology": row[meth_i] if meth_i is not None and meth_i < len(row) else None,
                })
            lines.append({
                "lineNo": n,
                "description": (get(row, "description") or "")[:100],
                "all_codes": all_codes,
                "setting": get(row, "setting"),
                "billing_class": get(row, "billing_class"),
                "modifiers": get(row, "modifiers"),
                "cash": parse_money(get(row, "standard_charge|discounted_cash")),
                "gross": parse_money(get(row, "standard_charge|gross")),
                "rates": rates,
            })
    return meta, lines


def parse_json(path: Path) -> tuple[dict, list[dict]]:
    doc = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    meta = {k: doc.get(k) for k in ("hospital_name", "last_updated_on", "version")}
    loc = doc.get("hospital_location")
    meta["hospital_location"] = "|".join(loc) if isinstance(loc, list) else loc
    lines: list[dict] = []
    for n, item in enumerate(doc.get("standard_charge_information") or []):
        all_codes = codes_from_pairs([(ci.get("code"), ci.get("type")) for ci in item.get("code_information") or []])
        for sc in item.get("standard_charges") or []:
            rates = [
                {"payer": p.get("payer_name"), "plan": p.get("plan_name"),
                 "dollar": parse_money(p.get("standard_charge_dollar")), "methodology": p.get("methodology")}
                for p in sc.get("payers_information") or []
            ]
            lines.append({
                "lineNo": n,
                "description": (item.get("description") or "")[:100],
                "all_codes": all_codes,
                "setting": sc.get("setting"),
                "billing_class": sc.get("billing_class"),
                "modifiers": ",".join(sc.get("modifier_code") or []) if isinstance(sc.get("modifier_code"), list) else sc.get("modifier_code"),
                "cash": parse_money(sc.get("discounted_cash")),
                "gross": parse_money(sc.get("gross_charge")),
                "rates": rates,
            })
    return meta, lines


def parse_mrf(path: Path) -> tuple[dict, list[dict]]:
    with open(path, "rb") as f:
        first = f.read(64).lstrip(b"\xef\xbb\xbf").lstrip()
    return parse_json(path) if first.startswith(b"{") else parse_csv(path)


# ============================================================ extraction

def extract(path: Path, source: dict, hospital: dict, codes: CodeIndex, q: Quarantine) -> list[dict]:
    meta, lines = parse_mrf(path)
    vintage = parse_iso_date(meta.get("last_updated_on"))
    base = {"hospitalId": hospital["id"], "mrfUrl": source["mrfUrl"], "file": path.name}
    accepted: dict[str, list[dict]] = defaultdict(list)
    for ln in lines:
        matches, problems = codes.match_all_codes(ln["all_codes"])
        sample = {**base, "line": ln["lineNo"], "description": ln["description"], "allCodes": ln["all_codes"][:160]}
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
        prob = line_scope_problem(codes.scope(pid), ln["setting"], ln["billing_class"], ln["modifiers"])
        if prob:
            q.add(prob, sample)
            continue
        accepted[pid].append({**ln, "sample": sample, "labels": sorted({m[2] for m in matches}),
                              "types": sorted({m[1] for m in matches})})
    rows: list[dict] = []
    for pid, lns in sorted(accepted.items()):
        if not vintage:
            q.add("row:missing_source_vintage", {**base, "procedureId": pid})
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
            "stale": False,  # set once the reference date is known
            "mrfUrl": source["mrfUrl"],
            "sourceDataset": source.get("cmsHptUrl"),
            "sourceDocumentHash": source.get("sha256") and f"sha256:{source['sha256']}",
            "sourceRetrievedAt": source.get("retrievedAt"),
            "sourceFacilityName": source.get("locationName"),
            "hospitalMatch": source.get("hospitalMatch"),
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


def source_record_path(ccn: str) -> Path:
    return MRF_CACHE / ccn / "sources.json"


def fetch_sources(seed: dict, hospital: dict, matcher: StrictHospitalMatcher, q: Quarantine) -> None:
    """Network step: resolve cms-hpt.txt entries for this hospital and cache its MRF(s)."""
    ccn = hospital["cmsProviderId"]
    hpt_text = hpt_url = None
    for cand in cms_hpt_candidates(seed.get("website"), seed.get("shoppableUrl")):
        try:
            hpt_text, hpt_url = fetch_text(cand), cand
            break
        except Exception:  # noqa: BLE001
            continue
    if not hpt_text:
        q.add("file:no_cms_hpt_txt", {"hospitalId": hospital["id"]})
        return
    records = []
    for entry in parse_cms_hpt(hpt_text):
        url = entry.get("mrf_url") or ""
        loc = entry.get("location_name") or ""
        if not url.startswith("https://"):
            q.add("file:mrf_url_not_https", {"hospitalId": hospital["id"], "mrfUrl": url})
            continue
        h, how = matcher.match([loc], hospital.get("state") or "", {hospital.get("city") or ""},
                               {(hospital.get("zip") or "")[:5]})
        if not h or h["cmsProviderId"] != ccn:
            q.add("file:cms_hpt_location_is_another_facility",
                  {"hospitalId": hospital["id"], "locationName": loc, "mrfUrl": url,
                   "resolvedTo": h and h["cmsProviderId"], "why": how})
            continue
        name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(urlparse(url).path).name)[-120:] or "mrf"
        dest = MRF_CACHE / ccn / name
        try:
            sha = download(url, dest)
        except Exception as exc:  # noqa: BLE001
            q.add("file:mrf_download_failed", {"hospitalId": hospital["id"], "mrfUrl": url, "error": str(exc)[:160]})
            continue
        records.append({"file": name, "mrfUrl": url, "cmsHptUrl": hpt_url, "locationName": loc,
                        "hospitalMatch": how, "sha256": sha,
                        "retrievedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    if records:
        atomic_write_text(source_record_path(ccn), dump_json(records))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Max seed hospitals (network mode)")
    ap.add_argument("--hospital", help="CMS provider id")
    ap.add_argument("--offline", action="store_true", help="Only re-derive from data/mrf/cache")
    args = ap.parse_args()

    codes = CodeIndex()
    hospitals = load_hospitals()
    by_ccn = {h["cmsProviderId"]: h for h in hospitals}
    hospitals_by_id = {h["id"]: h for h in hospitals}
    matcher = StrictHospitalMatcher(hospitals)
    q = Quarantine()

    if not args.offline:
        seeds = read_json(SEED_HOSPITALS, []) or []
        if args.hospital:
            seeds = [s for s in seeds if s.get("cmsProviderId") == args.hospital]
        if args.limit:
            seeds = seeds[: args.limit]
        for seed in seeds:
            h = by_ccn.get(seed.get("cmsProviderId") or "")
            if h:
                print(f"Fetching {h['name']} ({h['cmsProviderId']})…")
                fetch_sources(seed, h, matcher, q)

    # Extraction always runs from the local cache, so the output is reproducible offline.
    sources: list[tuple[dict, dict, Path]] = []
    for rec_path in sorted(MRF_CACHE.glob("*/sources.json")) if MRF_CACHE.exists() else []:
        ccn = rec_path.parent.name
        h = by_ccn.get(ccn)
        for rec in read_json(rec_path, []) or []:
            p = rec_path.parent / rec["file"]
            if not h or not p.exists():
                q.add("file:cached_source_missing", {"ccn": ccn, "file": rec.get("file")})
                continue
            sources.append((rec, h, p))
    rows: list[dict] = []
    for rec, h, p in sources:
        try:
            got = extract(p, rec, h, codes, q)
        except Exception as exc:  # noqa: BLE001
            q.add("file:mrf_parse_error", {"file": str(p.name), "error": str(exc)[:200]})
            continue
        rows.extend(got)
    # reference date = latest source vintage seen (never the build date)
    reference_date = max((r["priceVintage"] for r in rows), default=None)
    checked: list[dict] = []
    for r in rows:
        r["stale"] = is_stale(r["priceVintage"], reference_date)
        probs = contract_problems(r, codes, hospitals_by_id)
        if probs:
            q.add(f"row:contract_violation:{probs[0]}", {"hospitalId": r["hospitalId"], "procedureId": r["procedureId"]})
        else:
            checked.append(r)
    rows = checked

    # one row per hospital + procedure: most recent vintage, then more lines, then URL order
    best: dict[tuple[str, str], dict] = {}
    for r in sorted(rows, key=lambda r: r["mrfUrl"]):
        k = (r["cmsProviderId"], r["procedureId"])
        cur = best.get(k)
        if not cur or (r["priceVintage"], r["lineCount"]) > (cur["priceVintage"], cur["lineCount"]):
            if cur:
                q.add("row:duplicate_superseded", {"hospitalId": cur["hospitalId"], "procedureId": cur["procedureId"], "mrfUrl": cur["mrfUrl"]})
            best[k] = r
        else:
            q.add("row:duplicate_superseded", {"hospitalId": r["hospitalId"], "procedureId": r["procedureId"], "mrfUrl": r["mrfUrl"]})
    rows = [best[k] for k in sorted(best)]

    previous = read_json(OUT_PRICES, []) or []
    keys = set(best)
    for p in previous:
        if (p.get("cmsProviderId"), p.get("procedureId")) not in keys:
            q.add("row:source_not_reprocessable_offline", {
                "hospitalId": p.get("hospitalId"), "procedureId": p.get("procedureId"),
                "previousMrfUrl": p.get("mrfUrl"), "previousVintage": p.get("priceVintage"),
                "why": "no cached copy of the source MRF in data/mrf/cache; cannot be re-derived under the current rules",
            })

    atomic_write_text(OUT_PRICES, dump_json(rows))
    atomic_write_text(OUT_META, dump_json({
        "source": "CMS Hospital Price Transparency MRF files (cms-hpt.txt -> mrf-url), cached in data/mrf/cache",
        "method": "Strict cms-hpt location match to the hospital's CCN; explicit code types; shared contract in etl/price_contract.py",
        "priceCount": len(rows),
        "cmsHospitalsWithPrices": len({r["cmsProviderId"] for r in rows}),
        "cachedSourceFiles": len(sources),
        "referenceDate": reference_date,
        "referenceDateRule": "latest last_updated_on among the cached source files",
        "note": "Prices exactly as published by hospitals. Nothing is estimated.",
    }))
    write_quarantine_section(QUARANTINE_SECTION, q, {"referenceDate": reference_date})
    print(f"Wrote {len(rows)} prices → {OUT_PRICES}")
    print("Quarantine:", json.dumps(dict(sorted(q.counts.items())), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
