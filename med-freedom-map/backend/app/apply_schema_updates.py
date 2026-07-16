#!/usr/bin/env python3
"""
Integration script to apply schema field population to actual seed.py ACCESS_RECORDS.
Loads the seed data, populates new fields, and outputs updated Python code.
"""
import sys
import re
from pathlib import Path
from populate_schema_fields import build_schema_fields


def extract_access_records_from_seed() -> list:
    """Parse ACCESS_RECORDS list from seed.py source code."""
    seed_path = Path(__file__).parent / "seed.py"

    with open(seed_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the ACCESS_RECORDS list
    start_marker = "ACCESS_RECORDS = ["
    end_marker = "def seed_database():"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print("❌ Could not find ACCESS_RECORDS in seed.py")
        return []

    records_str = content[start_idx + len(start_marker):end_idx]

    # Parse as Python (simplified - split by dict boundaries)
    # This is a hacky parser; ideally would use ast.literal_eval
    records = []
    current_dict = ""
    brace_depth = 0

    for char in records_str:
        if char == '{':
            brace_depth += 1
            current_dict += char
        elif char == '}':
            brace_depth -= 1
            current_dict += char
            if brace_depth == 0 and current_dict.strip():
                # Try to evaluate as dict
                try:
                    record = eval(current_dict)
                    records.append(record)
                except Exception as e:
                    print(f"⚠️  Failed to parse record: {e}")
                current_dict = ""
        else:
            current_dict += char

    return records


def format_record_for_output(record: dict) -> str:
    """Format a single record as Python dict code."""
    lines = ["    {"]

    for key, value in record.items():
        if value is None:
            lines.append(f'     "{key}": None,')
        elif isinstance(value, str):
            # Handle multi-line strings and escaping
            if '\n' in value:
                lines.append(f'     "{key}": """{value}""",')
            else:
                escaped = value.replace('\\', '\\\\').replace('"', '\\"')
                lines.append(f'     "{key}": "{escaped}",')
        elif isinstance(value, (int, float)):
            lines.append(f'     "{key}": {value},')
        elif isinstance(value, bool):
            lines.append(f'     "{key}": {str(value)},')
        elif isinstance(value, dict):
            lines.append(f'     "{key}": {repr(value)},')
        else:
            lines.append(f'     "{key}": {repr(value)},')

    lines.append("    },")
    return '\n'.join(lines)


def apply_schema_updates(records: list) -> list:
    """Apply schema field updates to all records that don't have them yet."""
    updated = []

    for i, record in enumerate(records):
        # Skip if already has access_pathway
        if "access_pathway" in record and record["access_pathway"] is not None:
            updated.append(record)
            continue

        # Build new fields
        new_fields = build_schema_fields(record)

        # Create updated record
        updated_record = {**record, **new_fields}
        updated.append(updated_record)

        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{len(records)} records...")

    return updated


def save_updated_seed_file(updated_records: list) -> None:
    """Save updated records back to seed.py."""
    seed_path = Path(__file__).parent / "seed.py"

    # Read original file
    with open(seed_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the ACCESS_RECORDS list boundaries
    start_marker = "ACCESS_RECORDS = ["
    end_marker = "\ndef seed_database():"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print("❌ Could not find ACCESS_RECORDS boundaries in seed.py")
        return

    # Build new ACCESS_RECORDS section
    new_access_records = "ACCESS_RECORDS = [\n"
    for record in updated_records:
        new_access_records += format_record_for_output(record) + "\n"
    new_access_records += "]\n"

    # Replace in content
    new_content = (
        content[:start_idx] +
        new_access_records +
        content[end_idx:]
    )

    # Write back
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"✅ Updated seed.py with {len(updated_records)} records")


def print_statistics(original: list, updated: list) -> None:
    """Print statistics about the update."""
    print("\n" + "="*80)
    print("SCHEMA UPDATE STATISTICS")
    print("="*80)

    # Count records with new fields
    with_access_pathway = sum(1 for r in updated if r.get("access_pathway"))
    with_price_usd = sum(1 for r in updated if r.get("price_usd"))
    with_total_cost = sum(1 for r in updated if r.get("total_access_cost_usd"))
    with_confidence = sum(1 for r in updated if r.get("confidence"))

    print(f"Total records: {len(updated)}")
    print(f"With access_pathway: {with_access_pathway}")
    print(f"With price_usd: {with_price_usd}")
    print(f"With total_access_cost_usd: {with_total_cost}")
    print(f"With confidence/volatility: {with_confidence}")

    # Sample some confidence/volatility distributions
    volatilities = [r.get("volatility") for r in updated if r.get("volatility")]
    confusions = [r.get("confidence") for r in updated if r.get("confidence")]

    if volatilities:
        print(f"\nVolatility distribution:")
        for v in set(volatilities):
            count = volatilities.count(v)
            pct = 100 * count / len(volatilities)
            print(f"  {v}: {count} ({pct:.1f}%)")

    if confusions:
        print(f"\nConfidence distribution:")
        for c in set(confusions):
            count = confusions.count(c)
            pct = 100 * count / len(confusions)
            print(f"  {c}: {count} ({pct:.1f}%)")

    print("\n" + "="*80)


if __name__ == "__main__":
    print("="*80)
    print("APPLYING SCHEMA FIELD UPDATES TO SEED.PY")
    print("="*80 + "\n")

    print("Loading ACCESS_RECORDS from seed.py...")
    records = extract_access_records_from_seed()
    print(f"✅ Loaded {len(records)} records\n")

    if not records:
        print("❌ No records loaded. Check seed.py format.")
        sys.exit(1)

    print("Applying schema field updates...")
    updated = apply_schema_updates(records)

    print_statistics(records, updated)

    print("Saving updated records back to seed.py...")
    save_updated_seed_file(updated)

    print("\n✅ Schema field population complete!")
    print("\nNext steps:")
    print("  1. Review the updated seed.py file")
    print("  2. Run: python -m app.seed")
    print("  3. Start the app and verify data is seeded correctly")
