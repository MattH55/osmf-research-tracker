#!/usr/bin/env python3
"""
Bulk populate all remaining AccessRecords with schema fields.
Loads actual seed data, applies transformations, writes updated seed.py.
"""
import sys
import json
import re
from pathlib import Path
from typing import Dict, List, Any
from datetime import date

# Import the actual enums and seed data
sys.path.insert(0, str(Path(__file__).parent))

from models import (
    LegalStatus, OversightQuality, AccessPathway, PriceConfidence,
    Confidence, Volatility
)
from populate_schema_fields import (
    build_schema_fields, parse_cost_range, get_confidence_and_volatility,
    TRAVEL_COSTS, MIN_STAY_DAYS
)


def extract_records_via_regex(seed_path: Path) -> List[Dict[str, Any]]:
    """
    Extract AccessRecords from seed.py using regex pattern matching.
    Returns list of dicts with key fields extracted.
    """
    with open(seed_path, 'r', encoding='utf-8') as f:
        content = f.read()

    records = []

    # Find all AccessRecord dict blocks
    # Pattern: {"procedure_id": ... } followed by comma (not closing bracket)
    pattern = r'\{[^}]*"procedure_id"[^}]*"sources":[^}]*\}(?=\s*,?\s*(?:{\s*"procedure_id"|def\s+seed_database))'

    matches = re.finditer(pattern, content, re.DOTALL)

    for match in matches:
        record_str = match.group(0)

        # Extract key fields using specific regex patterns
        record_dict = {}

        # procedure_id
        proc_match = re.search(r'"procedure_id":\s*"([^"]+)"', record_str)
        if proc_match:
            record_dict['procedure_id'] = proc_match.group(1)

        # jurisdiction_id
        jur_match = re.search(r'"jurisdiction_id":\s*"([^"]+)"', record_str)
        if jur_match:
            record_dict['jurisdiction_id'] = jur_match.group(1)

        # legal_status (enum reference)
        status_match = re.search(r'"legal_status":\s*(LegalStatus\.\w+)', record_str)
        if status_match:
            record_dict['legal_status'] = status_match.group(1)

        # oversight_quality (enum reference)
        oversight_match = re.search(r'"oversight_quality":\s*(OversightQuality\.\w+)', record_str)
        if oversight_match:
            record_dict['oversight_quality'] = oversight_match.group(1)

        # estimated_cost_range_usd
        cost_match = re.search(r'"estimated_cost_range_usd":\s*"([^"]*)"', record_str)
        if cost_match:
            record_dict['estimated_cost_range_usd'] = cost_match.group(1)

        # Check if already has new fields
        if 'price_usd' not in record_str:
            records.append((record_str, record_dict))

    return records


def generate_field_injection(record_dict: Dict[str, Any]) -> str:
    """
    Generate the schema fields to inject before last_verified.
    Returns multi-line string with properly formatted fields.
    """
    # Build schema fields
    new_fields = build_schema_fields(record_dict)

    # Format for insertion
    lines = []
    indent = '     '

    if new_fields['price_usd']:
        lines.append(f'{indent}"price_usd": {new_fields["price_usd"]},')
    else:
        lines.append(f'{indent}"price_usd": None,')

    lines.append(f'{indent}"price_basis": "{new_fields["price_basis"]}",')
    lines.append(f'{indent}"price_confidence": "{new_fields["price_confidence"]}",')

    if new_fields['total_access_cost_usd']:
        lines.append(f'{indent}"total_access_cost_usd": {new_fields["total_access_cost_usd"]},')
    else:
        lines.append(f'{indent}"total_access_cost_usd": None,')

    travel_friction = new_fields['travel_friction_json']
    lines.append(f'{indent}"travel_friction_json": \'{travel_friction}\',')

    lines.append(f'{indent}"confidence": "{new_fields["confidence"]}",')
    lines.append(f'{indent}"volatility": "{new_fields["volatility"]}",')
    lines.append(f'{indent}"verified_by": "{new_fields["verified_by"]}",')

    return '\n'.join(lines)


def inject_fields_into_seed(seed_path: Path, records_to_update: List[tuple]) -> int:
    """
    Inject schema fields into AccessRecords in seed.py.
    Returns count of records updated.
    """
    with open(seed_path, 'r', encoding='utf-8') as f:
        content = f.read()

    injected_count = 0

    for original_record_str, record_dict in records_to_update:
        # Generate injection text
        injection = generate_field_injection(record_dict)

        # Find the insertion point: before "last_verified" in this record
        # Insert after "arbitrage_summary" line, before "last_verified" line

        # Create the updated record with injected fields
        # Find "last_verified" in the original record string
        updated_record = original_record_str.replace(
            '     "last_verified":',
            f'{injection},\n     "last_verified":'
        )

        # Replace in main content
        if updated_record != original_record_str:
            content = content.replace(original_record_str, updated_record)
            injected_count += 1

    # Write back
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return injected_count


def analyze_records(records_to_update: List[tuple]) -> Dict[str, Any]:
    """
    Analyze the records to be updated.
    Returns statistics about the update.
    """
    stats = {
        'total': len(records_to_update),
        'by_procedure': {},
        'by_jurisdiction': {},
        'price_distribution': {
            'under_1k': 0,
            '1k_to_10k': 0,
            '10k_to_100k': 0,
            'over_100k': 0,
            'none': 0,
        },
        'volatility_distribution': {},
    }

    for original_record_str, record_dict in records_to_update:
        proc = record_dict.get('procedure_id', 'unknown')
        jur = record_dict.get('jurisdiction_id', 'unknown')

        stats['by_procedure'][proc] = stats['by_procedure'].get(proc, 0) + 1
        stats['by_jurisdiction'][jur] = stats['by_jurisdiction'].get(jur, 0) + 1

        # Analyze pricing
        new_fields = build_schema_fields(record_dict)
        price = new_fields['total_access_cost_usd']

        if price is None:
            stats['price_distribution']['none'] += 1
        elif price < 1000:
            stats['price_distribution']['under_1k'] += 1
        elif price < 10000:
            stats['price_distribution']['1k_to_10k'] += 1
        elif price < 100000:
            stats['price_distribution']['10k_to_100k'] += 1
        else:
            stats['price_distribution']['over_100k'] += 1

        # Analyze volatility
        volatility = new_fields['volatility']
        stats['volatility_distribution'][volatility] = stats['volatility_distribution'].get(volatility, 0) + 1

    return stats


def print_analysis(stats: Dict[str, Any]) -> None:
    """Pretty-print analysis results."""
    print("\n" + "="*80)
    print("BULK POPULATION ANALYSIS")
    print("="*80)

    print(f"\nTotal records to update: {stats['total']}")

    print(f"\nBy procedure (top 10):")
    sorted_procs = sorted(stats['by_procedure'].items(), key=lambda x: x[1], reverse=True)[:10]
    for proc, count in sorted_procs:
        print(f"  {proc}: {count}")

    print(f"\nBy jurisdiction (top 10):")
    sorted_jurs = sorted(stats['by_jurisdiction'].items(), key=lambda x: x[1], reverse=True)[:10]
    for jur, count in sorted_jurs:
        print(f"  {jur}: {count}")

    print(f"\nPrice distribution (total_access_cost_usd):")
    for bucket, count in stats['price_distribution'].items():
        pct = 100 * count / stats['total'] if stats['total'] > 0 else 0
        print(f"  {bucket}: {count} ({pct:.1f}%)")

    print(f"\nVolatility distribution:")
    for volatility, count in stats['volatility_distribution'].items():
        pct = 100 * count / stats['total'] if stats['total'] > 0 else 0
        print(f"  {volatility}: {count} ({pct:.1f}%)")

    print("\n" + "="*80)


def main():
    """Main entry point."""
    print("="*80)
    print("BULK POPULATING ACCESSRECORDS WITH SCHEMA FIELDS")
    print("="*80 + "\n")

    seed_path = Path(__file__).parent / "seed.py"

    if not seed_path.exists():
        print(f"[ERROR] seed.py not found at {seed_path}")
        return 1

    print(f"Loading AccessRecords from {seed_path}...")
    records_to_update = extract_records_via_regex(seed_path)
    print(f"[OK] Found {len(records_to_update)} AccessRecords needing schema field injection\n")

    if len(records_to_update) == 0:
        print("No records to update. All AccessRecords already have schema fields.")
        return 0

    # Analyze before updating
    print("Analyzing records...")
    stats = analyze_records(records_to_update)
    print_analysis(stats)

    # Inject fields
    print("\nInjecting schema fields...")
    injected_count = inject_fields_into_seed(seed_path, records_to_update)
    print(f"[OK] Injected schema fields into {injected_count} records\n")

    # Verification sample
    print("Sample of updated fields:")
    print("-" * 80)
    for original_record_str, record_dict in records_to_update[:3]:
        new_fields = build_schema_fields(record_dict)
        print(f"\n{record_dict['procedure_id']} @ {record_dict['jurisdiction_id']}:")
        print(f"  price_usd: {new_fields['price_usd']}")
        print(f"  total_access_cost_usd: {new_fields['total_access_cost_usd']}")
        print(f"  confidence: {new_fields['confidence']}")
        print(f"  volatility: {new_fields['volatility']}")

    print("\n" + "="*80)
    print("[SUCCESS] BULK POPULATION COMPLETE")
    print("="*80)
    print("\nNext steps:")
    print("  1. Review the updated seed.py file")
    print("  2. Run: python -m app.seed")
    print("  3. Verify database seeding completed successfully")
    print("  4. Test arbitrage queries via API")

    return 0


if __name__ == "__main__":
    sys.exit(main())
