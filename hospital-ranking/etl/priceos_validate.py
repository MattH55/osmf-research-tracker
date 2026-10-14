#!/usr/bin/env python3
"""
PriceOS validator.

Checks, and exits non-zero on failure:
  * data/seed/procedures.json: every code in exactly one procedure, one
    canonical scope per procedure (CodeIndex raises otherwise);
  * data/cms/trilliant-prices.json and mrf-prices.json: the price-row contract
    (etl/price_contract.contract_problems), no estimate/OOP fields, no
    duplicate hospital+procedure, deterministic id present;
  * data/observations/*.jsonl: JSON schema (schema/price_observation.schema.json),
    foreign keys (facility_id -> data/cms/hospitals.json or the international
    facility registry; procedure_id -> procedures.json), canonical scope,
    matched codes belong to the procedure, amount within bounds, stale flag
    consistent with the dataset reference date, unique ids.

--strict also fails on warnings.

USAGE:
  python etl/priceos_validate.py [data_dir] [--strict] [--report text|json]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema not installed. Run: pip install jsonschema", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from price_contract import (  # noqa: E402
    FORBIDDEN_FIELDS,
    ROOT,
    CodeIndex,
    contract_problems,
    is_stale,
    normalize_drg,
    read_json,
    valid_amount,
)
from migrate_to_observation_store import procedure_slug  # noqa: E402

SCHEMA_DIR = ROOT / "schema"
DATA_DIR = ROOT / "data"
OBS_SCHEMA = json.loads((SCHEMA_DIR / "price_observation.schema.json").read_text(encoding="utf-8"))
PRICE_FILES = ("trilliant-prices.json", "mrf-prices.json")
REFERENCE_META = {
    "us-mrf-trilliant.jsonl": "trilliant-meta.json",
    "us-mrf-direct.jsonl": "mrf-meta.json",
}


class Result:
    def __init__(self) -> None:
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.codes: Counter = Counter()
        self.stats: dict = {
            "price_rows": {},
            "observations": 0,
            "valid_observations": 0,
            "stale_observations": 0,
            "observations_by_procedure": Counter(),
        }

    def error(self, where: str, code: str, msg: str) -> None:
        self.codes[code] += 1
        self.errors.append({"where": where, "code": code, "message": msg})

    def warn(self, where: str, code: str, msg: str) -> None:
        self.codes[code] += 1
        self.warnings.append({"where": where, "code": code, "message": msg})

    def to_dict(self) -> dict:
        return {
            "pass": not self.errors,
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "byCode": dict(sorted(self.codes.items())),
            "stats": {**self.stats, "observations_by_procedure": dict(sorted(self.stats["observations_by_procedure"].items()))},
            "firstErrors": self.errors[:50],
            "firstWarnings": self.warnings[:50],
        }

    def to_text(self) -> str:
        lines = ["=" * 60, "PriceOS validation", "=" * 60]
        for f, n in self.stats["price_rows"].items():
            lines.append(f"Price rows {f}: {n}")
        lines.append(f"Observations: {self.stats['observations']} (schema-valid {self.stats['valid_observations']}, stale {self.stats['stale_observations']})")
        lines.append(f"Errors: {len(self.errors)}   Warnings: {len(self.warnings)}")
        for code, n in sorted(self.codes.items()):
            lines.append(f"  {code}: {n}")
        for e in self.errors[:20]:
            lines.append(f"  ERROR {e['code']}: {e['message']} ({e['where']})")
        for w in self.warnings[:10]:
            lines.append(f"  WARN  {w['code']}: {w['message']} ({w['where']})")
        lines.append("PASS" if not self.errors else "FAIL")
        return "\n".join(lines)


def load_facility_ids(data_dir: Path) -> set[str]:
    ids = {h["id"] for h in read_json(data_dir / "cms" / "hospitals.json", []) or []}
    reg = read_json(data_dir / "adapters" / "facility_registry.json", None)
    if isinstance(reg, list):
        ids |= {f.get("facility_id") for f in reg if isinstance(f, dict) and f.get("facility_id")}
    elif isinstance(reg, dict):
        items = reg.get("facilities") if isinstance(reg.get("facilities"), list) else list(reg.values())
        for f in items:
            if isinstance(f, dict) and f.get("facility_id"):
                ids.add(f["facility_id"])
    return ids


def validate_price_files(data_dir: Path, codes: CodeIndex, hospitals_by_id: dict, res: Result) -> None:
    for name in PRICE_FILES:
        path = data_dir / "cms" / name
        rows = read_json(path, None)
        if rows is None:
            res.error(name, "PRICE_FILE_MISSING", f"{path} not found")
            continue
        if not isinstance(rows, list):
            res.error(name, "PRICE_FILE_NOT_ARRAY", "price file must be a JSON array")
            continue
        res.stats["price_rows"][name] = len(rows)
        seen: set[tuple[str, str]] = set()
        ids: set[str] = set()
        for i, r in enumerate(rows):
            where = f"{name}[{i}]"
            for p in contract_problems(r, codes, hospitals_by_id):
                res.error(where, "ROW_CONTRACT", f"{r.get('hospitalId')}/{r.get('procedureId')}: {p}")
            bad = FORBIDDEN_FIELDS & set(r)
            if bad:
                res.error(where, "ROW_ESTIMATE_FIELD", f"forbidden fields {sorted(bad)}")
            key = (r.get("hospitalId"), r.get("procedureId"))
            if key in seen:
                res.error(where, "ROW_DUPLICATE", f"duplicate hospital+procedure {key}")
            seen.add(key)
            if not r.get("id"):
                res.error(where, "ROW_NO_ID", "missing deterministic id")
            elif r["id"] in ids:
                res.error(where, "ROW_DUPLICATE_ID", r["id"])
            ids.add(r.get("id"))
            if r.get("priceSource") != ("trilliant_mrf" if name.startswith("trilliant") else "hospital_mrf"):
                res.error(where, "ROW_WRONG_SOURCE_FILE", f"priceSource {r.get('priceSource')} in {name}")
            for c in r.get("matchedCodes") or []:
                ctype, _, val = str(c).partition(":")
                owner = codes.drg.get(normalize_drg(val)) if ctype == "MS-DRG" else codes.cpt.get(val)
                if owner != r.get("procedureId"):
                    res.error(where, "ROW_CODE_NOT_IN_PROCEDURE", f"{c} does not belong to {r.get('procedureId')}")
            for k in ("mrfUrl", "sourceDataset"):
                v = r.get(k)
                if v and (not str(v).startswith("https://") or "\\" in str(v)):
                    res.error(where, "ROW_LOCAL_OR_INSECURE_URL", f"{k}={v}")


def validate_observations(data_dir: Path, codes: CodeIndex, facility_ids: set[str], res: Result) -> None:
    obs_dir = data_dir / "observations"
    files = sorted(obs_dir.glob("*.jsonl")) if obs_dir.exists() else []
    if not files:
        res.error(str(obs_dir), "OBS_NONE", "no observation files")
        return
    validator = jsonschema.Draft7Validator(OBS_SCHEMA, format_checker=jsonschema.FormatChecker())
    known_slugs = {procedure_slug(p["id"]) for p in codes.procedures}
    seen_ids: set[str] = set()
    seen_keys: set[tuple] = set()
    for path in files:
        meta_name = REFERENCE_META.get(path.name)
        ref = (read_json(data_dir / "cms" / meta_name, {}) or {}).get("referenceDate") if meta_name else None
        with open(path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                where = f"{path.name}:{n}"
                res.stats["observations"] += 1
                try:
                    obs = json.loads(line)
                except json.JSONDecodeError as e:
                    res.error(where, "OBS_JSON", str(e))
                    continue
                errs = sorted(validator.iter_errors(obs), key=lambda e: list(e.path))
                if errs:
                    for e in errs[:3]:
                        res.error(where, "OBS_SCHEMA", f"{'/'.join(map(str, e.path))}: {e.message}")
                    continue
                res.stats["valid_observations"] += 1
                oid = obs["observation_id"]
                if oid in seen_ids:
                    res.error(where, "OBS_DUPLICATE_ID", oid)
                seen_ids.add(oid)
                key = (obs["facility_id"], obs.get("procedure_id") or obs["procedure_slug"], obs["price_type"])
                if key in seen_keys:
                    res.error(where, "OBS_DUPLICATE", f"{key}")
                seen_keys.add(key)
                if obs["facility_id"] not in facility_ids:
                    res.error(where, "FK_FACILITY", f"facility_id {obs['facility_id']} not in hospitals.json / facility registry")
                pid = obs.get("procedure_id")
                if pid is not None and pid not in codes.by_id:
                    res.error(where, "FK_PROCEDURE", f"procedure_id {pid} not in procedures.json")
                if obs["procedure_slug"] not in known_slugs:
                    res.error(where, "FK_PROCEDURE_SLUG", f"procedure_slug {obs['procedure_slug']} unknown")
                if pid in codes.by_id:
                    res.stats["observations_by_procedure"][pid] += 1
                    if obs.get("scope") != codes.scope(pid):
                        res.error(where, "OBS_SCOPE", f"{pid} scope {obs.get('scope')} != {codes.scope(pid)}")
                    for c in obs.get("matched_codes") or []:
                        ctype, _, val = c.partition(":")
                        owner = codes.drg.get(normalize_drg(val)) if ctype == "MS-DRG" else codes.cpt.get(val)
                        if owner != pid:
                            res.error(where, "OBS_CODE_NOT_IN_PROCEDURE", f"{c} not a code of {pid}")
                    if valid_amount(obs["amount_usd"], codes.floor(pid)) is None:
                        res.error(where, "OBS_OUT_OF_BOUNDS", f"{pid} amount {obs['amount_usd']}")
                if obs.get("stale"):
                    res.stats["stale_observations"] += 1
                if ref and bool(obs.get("stale")) != is_stale(obs["observation_date"], ref):
                    res.error(where, "OBS_STALE_FLAG", f"stale={obs.get('stale')} but date {obs['observation_date']} vs reference {ref}")
                if obs["observation_date"] > (ref or "9999-12-31"):
                    res.error(where, "OBS_DATE_AFTER_REFERENCE", f"{obs['observation_date']} > {ref}")
                amount_native, amount_usd, fx = obs["amount_native"], obs["amount_usd"], obs["fx_rate_to_usd"]
                if abs(round(amount_native * fx, 2) - amount_usd) > 1:
                    res.warn(where, "FX_MISMATCH", f"{amount_native} * {fx} != {amount_usd}")
                if obs["currency"] == "USD" and abs(fx - 1.0) > 0.01:
                    res.warn(where, "FX_USD_MISMATCH", f"USD with fx {fx}")


def main() -> int:
    ap = argparse.ArgumentParser(description="PriceOS data validator")
    ap.add_argument("data_dir", nargs="?", default=str(DATA_DIR))
    ap.add_argument("--strict", action="store_true", help="Fail on warnings as well as errors")
    ap.add_argument("--report", choices=["text", "json"], default="text")
    args = ap.parse_args()
    data_dir = Path(args.data_dir)
    if data_dir.name == "observations":
        data_dir = data_dir.parent
    res = Result()
    try:
        codes = CodeIndex()
    except ValueError as e:
        res.error("data/seed/procedures.json", "PROCEDURE_CODE_MAP", str(e))
        print(res.to_text())
        return 1
    hospitals = read_json(data_dir / "cms" / "hospitals.json", []) or []
    hospitals_by_id = {h["id"]: h for h in hospitals}
    validate_price_files(data_dir, codes, hospitals_by_id, res)
    validate_observations(data_dir, codes, load_facility_ids(data_dir), res)
    print(json.dumps(res.to_dict(), indent=2) if args.report == "json" else res.to_text())
    if res.errors:
        return 1
    if args.strict and res.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
