#!/usr/bin/env python3
"""
Medical Freedom Maps -- CI Validation Script
Validates all cell data files against schemas, source registry, and layer registry.
Fails the build on any of the conditions in S8 of jurisdictional-access-maps-spec.

Usage:
    python scripts/validate_cells.py          # validate all cells
    python scripts/validate_cells.py --strict # also fail on stale thresholds
"""

import argparse
import json
import os
import sys
import yaml
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_source_registry() -> Tuple[Dict[str, dict], List[str]]:
    """Load sources.yaml and return (lookup_by_id, errors)."""
    errors: List[str] = []
    try:
        data = load_yaml(ROOT / "data" / "sources.yaml")
    except Exception as e:
        return {}, [f"Failed to parse data/sources.yaml: {e}"]

    sources = data.get("sources", [])
    lookup = {}
    for s in sources:
        sid = s.get("id")
        if not sid:
            errors.append("Source entry missing 'id'")
            continue
        if sid in lookup:
            errors.append(f"Duplicate source id: {sid}")
        lookup[sid] = s

        # CI fails on PENDING terms_reviewed or redistribution_permitted
        terms = s.get("terms_reviewed")
        redist = s.get("redistribution_permitted")
        if terms == "PENDING":
            errors.append(f"Source '{sid}': terms_reviewed is PENDING -- must be resolved before ingest.")
        if redist == "PENDING":
            errors.append(f"Source '{sid}': redistribution_permitted is PENDING -- must be resolved before ingest.")

    return lookup, errors


def load_layer_registry() -> Tuple[Dict[str, dict], List[str]]:
    """Load layer-registry.yaml and return (lookup_by_id, errors)."""
    errors: List[str] = []
    try:
        data = load_yaml(ROOT / "schemas" / "layer-registry.yaml")
    except Exception as e:
        return {}, [f"Failed to parse schemas/layer-registry.yaml: {e}"]

    layers = data.get("layers", [])
    lookup = {}
    for layer in layers:
        lid = layer.get("id")
        if not lid:
            errors.append("Layer entry missing 'id'")
            continue
        dims = {}
        for dim in layer.get("dimensions", []):
            did = dim.get("id")
            if did:
                dims[did] = dim
        layer["_dim_lookup"] = dims
        lookup[lid] = layer

    return lookup, errors


def validate_cell_file(filepath: Path, source_lookup: Dict[str, dict], layer_lookup: Dict[str, dict]) -> List[str]:
    """Validate a single cell YAML file. Returns list of error strings."""
    errors: List[str] = []
    relpath = filepath.relative_to(ROOT)

    try:
        cell = load_yaml(filepath)
    except Exception as e:
        errors.append(f"{relpath}: Failed to parse YAML: {e}")
        return errors

    if not isinstance(cell, dict):
        errors.append(f"{relpath}: Root must be a mapping, got {type(cell).__name__}")
        return errors

    # Required top-level fields
    for field in ["jurisdiction", "layer", "dimensions"]:
        if field not in cell:
            errors.append(f"{relpath}: Missing required field '{field}'")
    if errors:
        return errors

    # Validate jurisdiction code format
    jurisdiction = cell["jurisdiction"]
    if not isinstance(jurisdiction, str) or not jurisdiction:
        errors.append(f"{relpath}: 'jurisdiction' must be a non-empty string, got {repr(jurisdiction)}")
    else:
        parts = jurisdiction.split("-")
        if len(parts) > 2:
            errors.append(f"{relpath}: Invalid jurisdiction format '{jurisdiction}'. Expected ISO 3166-2 (e.g. US-MT) or ISO 3166-1 (e.g. HN).")
        if len(parts[0]) != 2 or not parts[0].isalpha():
            errors.append(f"{relpath}: Invalid country code in '{jurisdiction}'.")
        # International tier: 2-letter codes only
        if len(parts) == 1 and len(jurisdiction) == 2:
            pass  # ISO 3166-1 alpha-2, e.g. HN, MX -- valid

    # Validate layer exists in registry
    layer_id = cell["layer"]
    if layer_id not in layer_lookup:
        errors.append(f"{relpath}: Unknown layer '{layer_id}'. Must be one of: {sorted(layer_lookup.keys())}")

    # Validate dimensions
    dimensions = cell.get("dimensions", [])
    if not isinstance(dimensions, list) or len(dimensions) == 0:
        errors.append(f"{relpath}: 'dimensions' must be a non-empty list")
        return errors

    layer_def = layer_lookup.get(layer_id)
    dim_lookup = layer_def.get("_dim_lookup", {}) if layer_def else {}
    dim_seen: Set[str] = set()

    for i, dim in enumerate(dimensions):
        prefix = f"{relpath} dim[{i}]"
        if not isinstance(dim, dict):
            errors.append(f"{prefix}: Must be a mapping")
            continue

        # Required fields per spec S8
        for required_field in ["id", "value", "citation", "source_id", "source_url", "source_type", "verified_on", "verified_by"]:
            if required_field not in dim:
                errors.append(f"{prefix}: Missing required field '{required_field}'")
            elif required_field in ("citation", "source_id", "source_url", "verified_by") and not dim.get(required_field):
                errors.append(f"{prefix}: Field '{required_field}' must not be empty")

        dim_id = dim.get("id")
        if dim_id:
            if dim_id in dim_seen:
                errors.append(f"{prefix}: Duplicate dimension id '{dim_id}' in this cell")
            dim_seen.add(dim_id)

            if layer_def and dim_id not in dim_lookup:
                errors.append(f"{prefix}: Dimension '{dim_id}' is not defined in layer '{layer_id}' in layer-registry.yaml")

            dim_def = dim_lookup.get(dim_id, {})
            if dim_def:
                dim_type = dim_def.get("type")
                value = dim.get("value")
                if dim_type == "bool" and not isinstance(value, bool):
                    errors.append(f"{prefix}: Value must be boolean for dimension '{dim_id}', got {type(value).__name__} ({repr(value)})")
                elif dim_type == "int" and not isinstance(value, int):
                    errors.append(f"{prefix}: Value must be integer for dimension '{dim_id}', got {type(value).__name__} ({repr(value)})")
                elif dim_type == "enum" and value not in dim_def.get("values", []):
                    errors.append(f"{prefix}: Value '{value}' not in allowed values {dim_def.get('values')} for dimension '{dim_id}'")

        # Validate source_id resolves
        source_id = dim.get("source_id")
        if source_id and source_id not in source_lookup:
            errors.append(f"{prefix}: source_id '{source_id}' does not resolve to an entry in data/sources.yaml")

        # Validate source_type
        source_type = dim.get("source_type")
        if source_type and source_type not in ("primary_statute", "secondary_tracker", "agency_guidance"):
            errors.append(f"{prefix}: source_type '{source_type}' must be one of: primary_statute, secondary_tracker, agency_guidance")

        # Validate confidence
        confidence = dim.get("confidence")
        if confidence and confidence not in ("high", "medium", "derived"):
            errors.append(f"{prefix}: confidence '{confidence}' must be one of: high, medium, derived")

        # Validate verified_on is a valid date
        verified_on = dim.get("verified_on")
        if verified_on:
            try:
                date.fromisoformat(str(verified_on))
            except (ValueError, TypeError):
                errors.append(f"{prefix}: verified_on '{verified_on}' is not a valid date (YYYY-MM-DD)")

    return errors


def check_staleness(cell: dict, layer_lookup: Dict[str, dict]) -> List[str]:
    """Check if the cell data is stale based on review cadence. Returns warnings (not errors for CI)."""
    warnings: List[str] = []
    layer_id = cell.get("layer")
    layer_def = layer_lookup.get(layer_id, {})
    cadence_days = layer_def.get("review_cadence_days", 365)
    today = date.today()

    for dim in cell.get("dimensions", []):
        verified_on = dim.get("verified_on")
        if not verified_on:
            continue
        try:
            verified_date = date.fromisoformat(str(verified_on))
        except ValueError:
            continue

        age_days = (today - verified_date).days
        ratio = age_days / cadence_days if cadence_days > 0 else 0

        if ratio > 1.5:
            warnings.append(
                f"  STALE (>150% cadence): dim '{dim['id']}' age={age_days}d cadence={cadence_days}d "
                f"(verified {verified_on})"
            )
        elif ratio > 1.0:
            warnings.append(
                f"  AGING (100-150% cadence): dim '{dim['id']}' age={age_days}d cadence={cadence_days}d "
                f"(verified {verified_on})"
            )

    return warnings


def collect_cell_files() -> List[Path]:
    """Find all YAML files under data/cells/."""
    cells_dir = ROOT / "data" / "cells"
    if not cells_dir.exists():
        return []
    return sorted(cells_dir.rglob("*.yaml")) + sorted(cells_dir.rglob("*.yml"))


def compute_stale_ratio(cell: dict, layer_lookup: dict) -> Tuple[int, int]:
    """Return (stale_count, total_count) for a cell."""
    layer_id = cell.get("layer")
    layer_def = layer_lookup.get(layer_id, {})
    cadence_days = layer_def.get("review_cadence_days", 365)
    today = date.today()
    stale = 0
    total = len(cell.get("dimensions", []))
    for dim in cell.get("dimensions", []):
        verified_on = dim.get("verified_on")
        if not verified_on:
            continue
        try:
            verified_date = date.fromisoformat(str(verified_on))
        except ValueError:
            continue
        age_days = (today - verified_date).days
        ratio = age_days / cadence_days if cadence_days > 0 else 0
        if ratio > 1.5:
            stale += 1
    return stale, total


def main():
    parser = argparse.ArgumentParser(description="Validate Medical Freedom Maps cell data")
    parser.add_argument("--strict", action="store_true", help="Also fail on stale thresholds (>20%% stale per layer)")
    parser.add_argument("--warnings", action="store_true", help="Show staleness warnings even when not failing")
    args = parser.parse_args()

    all_errors: List[str] = []
    all_warnings: List[str] = []

    # Load registries
    source_lookup, source_errors = load_source_registry()
    all_errors.extend(source_errors)

    layer_lookup, layer_errors = load_layer_registry()
    all_errors.extend(layer_errors)

    if source_errors or layer_errors:
        print("ERROR: Source or layer registry has issues:\n")
        for e in source_errors + layer_errors:
            print(f"  - {e}")
        print(f"\n{len(source_errors) + len(layer_errors)} registry error(s). Fix before proceeding.")
        sys.exit(1)

    # Collect and validate all cells
    cell_files = collect_cell_files()
    if not cell_files:
        print("WARNING: No cell files found under data/cells/")
        print("Phase 0 schema validation passed (no data to validate).")
        sys.exit(0)

    print(f"Validating {len(cell_files)} cell file(s)...\n")

    layer_stale: Dict[str, Tuple[int, int]] = {}

    for cf in cell_files:
        file_errors = validate_cell_file(cf, source_lookup, layer_lookup)
        all_errors.extend(file_errors)

        if not file_errors and args.warnings:
            try:
                cell = load_yaml(cf)
                warnings = check_staleness(cell, layer_lookup)
                for w in warnings:
                    all_warnings.append(f"{cf.relative_to(ROOT)}: {w}")

                layer_id = cell.get("layer")
                stale, total = compute_stale_ratio(cell, layer_lookup)
                if layer_id not in layer_stale:
                    layer_stale[layer_id] = (0, 0)
                s, t = layer_stale[layer_id]
                layer_stale[layer_id] = (s + stale, t + total)
            except Exception:
                pass

    # Staleness check
    stale_layer_errors: List[str] = []
    for layer_id, (stale, total) in sorted(layer_stale.items()):
        if total > 0:
            pct = (stale / total) * 100
            if pct > 20:
                msg = f"Layer '{layer_id}': {pct:.1f}% stale cells ({stale}/{total}) -- exceeds 20% threshold (S8)"
                stale_layer_errors.append(msg)

    if stale_layer_errors:
        if args.strict:
            all_errors.extend(stale_layer_errors)
        else:
            all_warnings.extend([f"WARNING: {e}" for e in stale_layer_errors])

    # Print warnings
    if all_warnings:
        for w in all_warnings:
            print(f"WARN: {w}")

    # Print errors and exit
    if all_errors:
        print(f"\nFAIL: {len(all_errors)} validation error(s):\n")
        for e in all_errors:
            print(f"  - {e}")
        print(f"\nBuild failed. Fix {len(all_errors)} error(s) before proceeding.")
        sys.exit(1)

    print(f"[OK] All {len(cell_files)} cell file(s) validated successfully.")
    if all_warnings:
        print(f"   ({len(all_warnings)} warning(s) -- re-run with --strict to fail on stale thresholds)")
    sys.exit(0)


if __name__ == "__main__":
    main()