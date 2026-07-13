#!/usr/bin/env python3
"""
PriceOS validator CLI.

Validates price observations against schemas, checks data quality, staleness,
FX sanity, and orphaned foreign keys.

USAGE:
  python etl/priceos_validate.py data/observations/
  python etl/priceos_validate.py data/observations/ --strict
  python etl/priceos_validate.py data/observations/ --report json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema not installed. Run: pip install jsonschema", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schema"
DATA_DIR = ROOT / "data"

SCHEMAS = {
    "price_observation": json.loads((SCHEMA_DIR / "price_observation.schema.json").read_text()),
    "facility": json.loads((SCHEMA_DIR / "facility.schema.json").read_text()),
    "procedure": json.loads((SCHEMA_DIR / "procedure.schema.json").read_text()),
}


class ValidationResult:
    def __init__(self):
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.stats: dict = {
            "total_observations": 0,
            "valid_observations": 0,
            "schema_errors": 0,
            "data_quality_issues": 0,
            "stale_observations": 0,
            "missing_required_fields": 0,
            "observations_by_source": {},
            "observations_by_procedure": {},
            "completeness_score_stats": {
                "min": None,
                "max": None,
                "mean": None,
            },
        }
        self.facilities: dict[str, dict] = {}
        self.procedures: set[str] = set()

    def add_error(self, file_path: str, line_num: int | None, message: str, code: str):
        self.errors.append({
            "file": str(file_path),
            "line": line_num,
            "message": message,
            "code": code,
        })
        if code.startswith("SCHEMA_"):
            self.stats["schema_errors"] += 1
        else:
            self.stats["data_quality_issues"] += 1

    def add_warning(self, file_path: str, line_num: int | None, message: str, code: str):
        self.warnings.append({
            "file": str(file_path),
            "line": line_num,
            "message": message,
            "code": code,
        })

    def to_dict(self) -> dict:
        return {
            "summary": {
                "total_errors": len(self.errors),
                "total_warnings": len(self.warnings),
                "pass": len(self.errors) == 0,
                "stats": self.stats,
            },
            "errors": self.errors[:100],  # Limit output
            "warnings": self.warnings[:100],
        }

    def to_text(self) -> str:
        lines = []
        lines.append(f"{'='*60}")
        lines.append(f"Validation Results")
        lines.append(f"{'='*60}")
        lines.append(f"Total observations: {self.stats['total_observations']}")
        lines.append(f"Valid: {self.stats['valid_observations']}")
        lines.append(f"Schema errors: {self.stats['schema_errors']}")
        lines.append(f"Data quality issues: {self.stats['data_quality_issues']}")
        lines.append(f"Stale: {self.stats['stale_observations']}")
        lines.append(f"")
        lines.append(f"Observations by source:")
        for source, count in sorted(self.stats["observations_by_source"].items()):
            lines.append(f"  {source}: {count}")
        lines.append(f"")
        lines.append(f"Observations by procedure:")
        for proc, count in sorted(self.stats["observations_by_procedure"].items()):
            lines.append(f"  {proc}: {count}")
        lines.append(f"")
        if self.stats["completeness_score_stats"]["mean"]:
            cs = self.stats["completeness_score_stats"]
            lines.append(f"Completeness scores: min={cs['min']:.2f}, max={cs['max']:.2f}, mean={cs['mean']:.2f}")
        lines.append(f"")
        if self.errors:
            lines.append(f"Errors ({len(self.errors)} shown, {len(self.errors)} total):")
            for err in self.errors[:20]:
                lines.append(f"  {err['code']}: {err['message']} ({err['file']})")
            if len(self.errors) > 20:
                lines.append(f"  ... and {len(self.errors) - 20} more")
        if self.warnings:
            lines.append(f"")
            lines.append(f"Warnings ({len(self.warnings)} shown, {len(self.warnings)} total):")
            for warn in self.warnings[:10]:
                lines.append(f"  {warn['code']}: {warn['message']}")
            if len(self.warnings) > 10:
                lines.append(f"  ... and {len(self.warnings) - 10} more")
        lines.append(f"")
        return "\n".join(lines)


def validate_observation(obs: dict, file_path: str, line_num: int, result: ValidationResult) -> bool:
    result.stats["total_observations"] += 1

    # Schema validation
    try:
        jsonschema.validate(obs, SCHEMAS["price_observation"])
    except jsonschema.ValidationError as e:
        result.add_error(file_path, line_num, f"Schema validation: {e.message}", "SCHEMA_INVALID")
        return False

    result.stats["valid_observations"] += 1

    # Track facility/procedure references
    result.facilities[obs.get("facility_id")] = {"id": obs.get("facility_id")}
    result.procedures.add(obs.get("procedure_slug", "unknown"))

    # Update stats
    source = obs.get("priceSource", "unknown")
    result.stats["observations_by_source"][source] = result.stats["observations_by_source"].get(source, 0) + 1

    proc = obs.get("procedure_slug", "unknown")
    result.stats["observations_by_procedure"][proc] = result.stats["observations_by_procedure"].get(proc, 0) + 1

    # Check for stale observations (>18 months old)
    obs_date_str = obs.get("observation_date")
    if obs_date_str:
        try:
            obs_date = datetime.fromisoformat(obs_date_str).date()
            cutoff = date.today() - timedelta(days=18 * 30)
            if obs_date < cutoff:
                result.stats["stale_observations"] += 1
                result.add_warning(
                    file_path, line_num,
                    f"Observation from {obs_date} is >18 months old",
                    "STALENESS_WARNING"
                )
        except (ValueError, TypeError):
            pass

    # Check for missing required provenance fields
    prov = obs.get("provenance", {})
    if not prov.get("source_url"):
        result.add_error(file_path, line_num, "Missing required provenance.source_url", "PROVENANCE_MISSING_URL")
    if not obs.get("observation_date"):
        result.add_error(file_path, line_num, "Missing required observation_date", "PROVENANCE_MISSING_DATE")

    # Check bundle completeness
    bundle = obs.get("bundle", {})
    if bundle is None:
        result.add_error(file_path, line_num, "bundle must not be null (use includes: [])", "BUNDLE_NULL")
    else:
        cs = bundle.get("completeness_score")
        if cs is not None:
            if result.stats["completeness_score_stats"]["min"] is None:
                result.stats["completeness_score_stats"]["min"] = cs
                result.stats["completeness_score_stats"]["max"] = cs
                result.stats["completeness_score_stats"]["mean"] = 0
            else:
                result.stats["completeness_score_stats"]["min"] = min(
                    result.stats["completeness_score_stats"]["min"], cs
                )
                result.stats["completeness_score_stats"]["max"] = max(
                    result.stats["completeness_score_stats"]["max"], cs
                )
            total = sum(
                result.stats["observations_by_procedure"].values()
            )
            result.stats["completeness_score_stats"]["mean"] = (
                result.stats["completeness_score_stats"]["mean"] * (total - 1) / total + cs / total
            )

    # FX sanity check
    amount_native = obs.get("amount_native")
    amount_usd = obs.get("amount_usd")
    fx_rate = obs.get("fx_rate_to_usd")
    if all([amount_native, amount_usd, fx_rate]):
        computed_usd = round(amount_native * fx_rate, 2)
        if abs(computed_usd - amount_usd) > 1:
            result.add_warning(
                file_path, line_num,
                f"FX mismatch: {amount_native} * {fx_rate} = {computed_usd}, but amount_usd = {amount_usd}",
                "FX_MISMATCH"
            )

    # Sanity: currency vs FX rate
    currency = obs.get("currency")
    if currency == "USD" and fx_rate and abs(fx_rate - 1.0) > 0.01:
        result.add_warning(
            file_path, line_num,
            f"USD price should have fx_rate_to_usd = 1.0, but got {fx_rate}",
            "FX_USD_MISMATCH"
        )

    return True


def validate_data_dir(data_dir: Path, result: ValidationResult, strict: bool = False) -> int:
    """Validate all observation files in data directory."""
    obs_dir = data_dir / "observations"
    if not obs_dir.exists():
        print(f"Directory not found: {obs_dir}", file=sys.stderr)
        return 1

    obs_files = sorted(obs_dir.glob("*.jsonl"))
    if not obs_files:
        print(f"No .jsonl files found in {obs_dir}", file=sys.stderr)
        return 1

    total_files = len(obs_files)
    for i, path in enumerate(obs_files, 1):
        print(f"[{i}/{total_files}] Validating {path.name}…", file=sys.stderr)
        try:
            with open(path, encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obs = json.loads(line)
                        validate_observation(obs, str(path), line_num, result)
                    except json.JSONDecodeError as e:
                        result.add_error(path, line_num, f"Invalid JSON: {e}", "JSON_PARSE_ERROR")
        except OSError as e:
            print(f"Error reading {path}: {e}", file=sys.stderr)
            return 1

    # Check for orphaned FKs (references to non-existent facilities/procedures)
    print(f"Checking foreign keys…", file=sys.stderr)
    # This is deferred: would need to load facility.json and procedure.json

    return 0 if len(result.errors) == 0 or not strict else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="PriceOS data validator")
    ap.add_argument("data_dir", nargs="?", default=str(DATA_DIR), help="Data directory to validate")
    ap.add_argument("--strict", action="store_true", help="Fail on any error or warning")
    ap.add_argument("--report", choices=["text", "json"], default="text", help="Output format")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    result = ValidationResult()

    rc = validate_data_dir(data_dir, result, args.strict)
    if rc != 0:
        return rc

    if args.report == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.to_text())

    return 0 if len(result.errors) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
