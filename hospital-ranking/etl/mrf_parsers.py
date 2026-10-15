#!/usr/bin/env python3
"""
Streaming parsers for hospital price transparency files (45 CFR Part 180).

  * parse_cms_hpt(text)       -> cms-hpt.txt entries (location-name, source-page-url,
                                 mrf-url, contact-name, contact-email)
  * open_mrf(path)            -> a binary stream of the MRF, transparently
                                 un-gzipping / un-zipping, plus the detected format
  * iter_mrf(path, keep)      -> (meta, lines) for CMS template v2.x / v3.x
                                 CSV (tall or wide) and JSON

Everything streams: CSV row by row, JSON item by item with ijson, so a multi-GB
file never sits in memory. Only lines for which keep(all_codes) is true are
returned, so the caller can restrict to the procedures it prices.

No price rules live here (see price_contract.py). A "line" is the raw input of
those rules:

  {"lineNo", "description", "all_codes", "setting", "billing_class", "modifiers",
   "cash", "gross", "rates": [{"payer", "plan", "dollar", "methodology"}]}
"""

from __future__ import annotations

import csv
import gzip
import io
import re
import sys
import zipfile
from pathlib import Path
from typing import Callable, Iterable

csv.field_size_limit(2**31 - 1)

GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK\x03\x04"
DESC_MAX = 100


class UnsupportedFormat(ValueError):
    pass


# ============================================================ cms-hpt.txt

HPT_KEYS = ("location_name", "source_page_url", "mrf_url", "contact_name", "contact_email")


def parse_cms_hpt(text: str) -> list[dict[str, str]]:
    """Parse cms-hpt.txt. Entries are blocks of 'key: value' lines separated by blank
    lines; a repeated key also starts a new entry (some files omit the blank line).
    Keys are lower-cased with '-' -> '_'. Only entries with an mrf_url are returned."""
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    text = text.lstrip("﻿")
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            if current:
                entries.append(current)
                current = {}
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = re.sub(r"[\s-]+", "_", key.strip().lower())
        if key not in HPT_KEYS:
            continue
        if key in current:
            entries.append(current)
            current = {}
        current[key] = val.strip()
    if current:
        entries.append(current)
    return [e for e in entries if e.get("mrf_url")]


def looks_like_cms_hpt(text: str) -> bool:
    return bool(re.search(r"(?im)^\s*mrf-url\s*:", text or "")) and "<html" not in (text or "")[:2000].lower()


# ============================================================ helpers

def parse_money(val) -> float | None:
    if val is None or isinstance(val, bool):
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


def codes_from_pairs(pairs: Iterable[tuple]) -> str:
    """Render (code, type) pairs as an all_codes string: 'CPT:45378 | RC:0750'."""
    out = []
    for c, t in pairs:
        c = "" if c is None else str(c).strip()
        if c:
            out.append(f"{('' if t is None else str(t)).strip().upper()}:{c}")
    return " | ".join(out)


def _s(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def norm_col(c: str) -> str:
    """CSV header normaliser: v3 examples write 'code | 1 | type'."""
    return re.sub(r"\s*\|\s*", "|", (c or "").strip().lstrip("﻿")).lower()


def _keep_col(c: str) -> str:
    """Normalise pipes/whitespace but keep the payer/plan names' case."""
    return re.sub(r"\s*\|\s*", "|", (c or "").strip().lstrip("﻿"))


# ============================================================ container / format

def sniff_container(path: Path) -> str:
    with open(path, "rb") as f:
        head = f.read(4)
    if head.startswith(GZIP_MAGIC):
        return "gzip"
    if head.startswith(ZIP_MAGIC):
        return "zip"
    return "plain"


def _zip_member(zf: zipfile.ZipFile) -> zipfile.ZipInfo:
    names = [i for i in zf.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")]
    if any(i.filename.startswith("xl/") for i in names):
        raise UnsupportedFormat("xlsx workbook (not a CMS CSV/JSON template)")
    data = [i for i in names if i.filename.lower().endswith((".csv", ".json", ".txt"))]
    if not data:
        raise UnsupportedFormat("zip without a .csv/.json member")
    # The largest data member is the MRF (others are readme/notes).
    return sorted(data, key=lambda i: (-i.file_size, i.filename))[0]


def open_mrf(path: Path):
    """Return (binary stream, closer list). Caller closes every item in closers."""
    kind = sniff_container(path)
    if kind == "gzip":
        f = gzip.open(path, "rb")
        return f, [f]
    if kind == "zip":
        zf = zipfile.ZipFile(path)
        m = zf.open(_zip_member(zf))
        return m, [m, zf]
    f = open(path, "rb")
    return f, [f]


def sniff_format(path: Path) -> str:
    """'json' or 'csv' (after decompression)."""
    stream, closers = open_mrf(path)
    try:
        head = stream.read(4096)
    finally:
        for c in closers:
            c.close()
    h = head.lstrip(b"\xef\xbb\xbf").lstrip()
    if h.startswith(b"{"):
        return "json"
    if h[:1] == b"<" or h[:20].lower().startswith(b"<!doctype"):
        raise UnsupportedFormat("file is HTML, not an MRF")
    if h.startswith(b"PK") or h.startswith(b"\xd0\xcf\x11\xe0"):
        raise UnsupportedFormat("binary spreadsheet, not a CMS CSV/JSON template")
    return "csv"


# ============================================================ CSV (tall or wide)

META_ALIASES = {"hospital_location": "location_name"}


def _csv_lines(text_stream, keep: Callable[[str], bool]) -> tuple[dict, list[dict], str]:
    reader = csv.reader(text_stream)
    first = next(reader, None)
    if first is None:
        raise UnsupportedFormat("empty CSV")
    meta: dict = {}
    cols_raw = first
    if "description" not in {norm_col(c) for c in first}:
        head_keys = [norm_col(h) for h in first]
        head_vals = next(reader, []) or []
        for k, v in zip(head_keys, head_vals):
            if not k or len(k) > 80:  # the long attestation header carries no metadata we use
                continue
            k = META_ALIASES.get(k, k)
            if k.startswith("license_number|"):
                meta["license_state"] = k.split("|", 1)[1].upper()
                k = "license_number"
            meta[k] = (v or "").strip()
        cols_raw = next(reader, None)
        if cols_raw is None:
            raise UnsupportedFormat("CSV has no column header row")
    cols = [norm_col(c) for c in cols_raw]
    if "description" not in cols:
        raise UnsupportedFormat("CSV column header row has no 'description' (not a CMS template)")
    ix: dict[str, int] = {}
    for i, c in enumerate(cols):
        ix.setdefault(c, i)
    code_idx: list[tuple[int, int]] = []
    for i, c in enumerate(cols):
        m = re.fullmatch(r"code\|(\d+)", c)
        if m and f"code|{m.group(1)}|type" in ix:
            code_idx.append((i, ix[f"code|{m.group(1)}|type"]))
    if not code_idx:
        raise UnsupportedFormat("CSV has no code|N / code|N|type columns")
    tall = "payer_name" in ix
    wide: list[tuple[int, str, str, int | None]] = []
    meth_cols = {c.rsplit("|", 1)[0]: i for i, c in enumerate(cols) if c.endswith("|methodology") and c.count("|") == 3}
    for i, c in enumerate(cols):
        if c.startswith("standard_charge|") and c.endswith("|negotiated_dollar") and c.count("|") == 3:
            _, payer, plan, _ = _keep_col(cols_raw[i]).split("|")
            wide.append((i, payer.strip(), plan.strip(), meth_cols.get(c.rsplit("|", 1)[0])))
    layout = "csv-tall" if tall else "csv-wide"

    def get(row, name):
        i = ix.get(name)
        return row[i] if i is not None and i < len(row) else None

    lines: list[dict] = []
    grouped: dict[tuple, dict] = {}
    for n, row in enumerate(reader, start=4 if meta else 2):
        if not row:
            continue
        pairs = [(row[a] if a < len(row) else "", row[b] if b < len(row) else "") for a, b in code_idx]
        all_codes = codes_from_pairs(pairs)
        if not all_codes or not keep(all_codes):
            continue
        base = {
            "lineNo": n,
            "description": (get(row, "description") or "").strip()[:DESC_MAX],
            "all_codes": all_codes,
            "setting": _s(get(row, "setting")),
            "billing_class": _s(get(row, "billing_class")),
            "modifiers": _s(get(row, "modifiers")),
            "cash": parse_money(get(row, "standard_charge|discounted_cash")),
            "gross": parse_money(get(row, "standard_charge|gross")),
        }
        rates = []
        if tall:
            d = parse_money(get(row, "standard_charge|negotiated_dollar"))
            if d is not None:
                rates.append({"payer": _s(get(row, "payer_name")), "plan": _s(get(row, "plan_name")),
                              "dollar": d, "methodology": _s(get(row, "standard_charge|methodology"))})
            # Tall files repeat the item once per payer/plan: one line per item.
            key = tuple(base[k] for k in ("description", "all_codes", "setting", "billing_class",
                                          "modifiers", "cash", "gross"))
            line = grouped.get(key)
            if line is None:
                line = {**base, "rates": []}
                grouped[key] = line
                lines.append(line)
            line["rates"].extend(rates)
            continue
        for i, payer, plan, mi in wide:
            d = parse_money(row[i] if i < len(row) else None)
            if d is not None:
                rates.append({"payer": payer, "plan": plan, "dollar": d,
                              "methodology": _s(row[mi]) if mi is not None and mi < len(row) else None})
        lines.append({**base, "rates": rates})
    return meta, lines, layout


def parse_csv_stream(binary_stream, keep: Callable[[str], bool]) -> tuple[dict, list[dict], str]:
    text = io.TextIOWrapper(binary_stream, encoding="utf-8-sig", errors="replace", newline="")
    try:
        return _csv_lines(text, keep)
    finally:
        text.detach()


# ============================================================ JSON (v2 / v3)

META_SCALARS = ("hospital_name", "last_updated_on", "version")
META_LISTS = {"location_name.item": "location_name", "hospital_location.item": "location_name",
              "hospital_address.item": "hospital_address"}


def _json_meta(binary_stream) -> dict:
    """Top-level metadata, streaming. Stops at standard_charge_information once the
    date and version are known (they precede it in the CMS templates); otherwise
    keeps scanning (slow path, still constant memory)."""
    import ijson

    meta: dict = {}
    lists: dict[str, list] = {}
    for prefix, event, value in ijson.parse(binary_stream, use_float=True):
        if prefix in META_SCALARS and event in ("string", "number"):
            meta[prefix] = str(value)
        elif prefix in META_LISTS and event == "string":
            lists.setdefault(META_LISTS[prefix], []).append(value)
        elif prefix in ("hospital_location", "location_name", "hospital_address") and event == "string":
            lists.setdefault(META_ALIASES.get(prefix, prefix), []).append(value)
        elif prefix == "license_information.license_number" and event in ("string", "number"):
            meta["license_number"] = str(value)
        elif prefix == "license_information.state" and event == "string":
            meta["license_state"] = value
        elif prefix == "standard_charge_information" and event == "start_array":
            if "last_updated_on" in meta and "version" in meta:
                break
    for k, v in lists.items():
        meta[k] = "|".join(str(x) for x in v)
    return meta


def _json_lines(binary_stream, keep: Callable[[str], bool]) -> list[dict]:
    import ijson

    lines: list[dict] = []
    for n, item in enumerate(ijson.items(binary_stream, "standard_charge_information.item", use_float=True)):
        if not isinstance(item, dict):
            continue
        all_codes = codes_from_pairs((ci.get("code"), ci.get("type"))
                                     for ci in item.get("code_information") or [] if isinstance(ci, dict))
        if not all_codes or not keep(all_codes):
            continue
        for sc in item.get("standard_charges") or []:
            if not isinstance(sc, dict):
                continue
            mods = sc.get("modifier_code")
            if isinstance(mods, list):
                mods = ",".join(str(m) for m in mods if m is not None)
            rates = []
            for p in sc.get("payers_information") or []:
                if not isinstance(p, dict):
                    continue
                d = parse_money(p.get("standard_charge_dollar"))
                if d is not None:
                    rates.append({"payer": _s(p.get("payer_name")), "plan": _s(p.get("plan_name")),
                                  "dollar": d, "methodology": _s(p.get("methodology"))})
            lines.append({
                "lineNo": n,
                "description": str(item.get("description") or "").strip()[:DESC_MAX],
                "all_codes": all_codes,
                "setting": _s(sc.get("setting")),
                "billing_class": _s(sc.get("billing_class") or item.get("billing_class")),
                "modifiers": _s(mods),
                "cash": parse_money(sc.get("discounted_cash")),
                "gross": parse_money(sc.get("gross_charge")),
                "rates": rates,
            })
    return lines


# ============================================================ entry point

def iter_mrf(path: Path, keep: Callable[[str], bool]) -> tuple[dict, list[dict], str]:
    """Stream-parse an MRF on disk. Returns (meta, candidate lines, layout)."""
    fmt = sniff_format(path)
    if fmt == "json":
        stream, closers = open_mrf(path)
        try:
            meta = _json_meta(stream)
        finally:
            for c in closers:
                c.close()
        stream, closers = open_mrf(path)
        try:
            lines = _json_lines(stream, keep)
        finally:
            for c in closers:
                c.close()
        return meta, lines, "json"
    stream, closers = open_mrf(path)
    try:
        return parse_csv_stream(stream, keep)
    finally:
        for c in closers:
            c.close()


if __name__ == "__main__":  # debugging aid: python etl/mrf_parsers.py FILE
    m, ls, lay = iter_mrf(Path(sys.argv[1]), lambda _c: True)
    print(lay, m)
    print(len(ls), "lines")
    for ln in ls[:5]:
        print(ln)
