#!/usr/bin/env python3
"""
Smarter bulk population that directly modifies seed.py line-by-line,
inserting schema fields before each last_verified line that doesn't already have them.
"""
import sys
import json
from pathlib import Path
from populate_schema_fields import build_schema_fields


def process_seed_file(seed_path: Path) -> int:
    """
    Process seed.py line by line, inserting schema fields before last_verified.
    """
    with open(seed_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    injected_count = 0
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check if this is a last_verified line
        if 'last_verified": date(' in line and i > 0:
            # Look back to find the start of this AccessRecord dict
            # Go back until we find the opening { with "procedure_id"

            # Collect the full record dict text from opening { to current position
            record_start = i - 1
            brace_count = 0

            # Go backwards to find the opening brace
            while record_start >= 0:
                for char in reversed(lines[record_start]):
                    if char == '}':
                        brace_count += 1
                    elif char == '{':
                        brace_count -= 1
                        if brace_count < 0:
                            break
                if brace_count < 0:
                    break
                record_start -= 1

            # Extract record text
            record_lines = lines[record_start:i+1]
            record_text = ''.join(record_lines)

            # Check if already has access_pathway
            if '"access_pathway"' not in record_text:
                # Extract key fields using simple string search
                proc_id = None
                jur_id = None
                legal_status = None
                oversight = None
                cost_range = None

                # Simple extraction
                for part in record_text.split(','):
                    if '"procedure_id"' in part:
                        proc_id = part.split('"')[-2]
                    elif '"jurisdiction_id"' in part:
                        jur_id = part.split('"')[-2]
                    elif '"legal_status"' in part:
                        # Extract enum value
                        parts = part.split('LegalStatus.') if 'LegalStatus.' in part else part.split(':')
                        if 'LegalStatus.' in part:
                            legal_status = 'LegalStatus.' + parts[1].strip().rstrip(',')
                    elif '"oversight_quality"' in part:
                        parts = part.split('OversightQuality.') if 'OversightQuality.' in part else part.split(':')
                        if 'OversightQuality.' in part:
                            oversight = 'OversightQuality.' + parts[1].strip().rstrip(',')
                    elif '"estimated_cost_range_usd"' in part:
                        cost_range = part.split('"')[3] if len(part.split('"')) > 3 else ""

                if proc_id and jur_id:
                    # Build schema fields
                    record_dict = {
                        'procedure_id': proc_id,
                        'jurisdiction_id': jur_id,
                        'legal_status': legal_status or "",
                        'oversight_quality': oversight or "",
                        'estimated_cost_range_usd': cost_range or "",
                    }

                    new_fields = build_schema_fields(record_dict)

                    # Format the injection
                    indent = '     '
                    injection_lines = [
                        f'{indent}"price_usd": {new_fields["price_usd"] if new_fields["price_usd"] else "None"},',
                        f'{indent}"price_basis": "{new_fields["price_basis"]}",',
                        f'{indent}"price_confidence": "{new_fields["price_confidence"]}",',
                        f'{indent}"total_access_cost_usd": {new_fields["total_access_cost_usd"] if new_fields["total_access_cost_usd"] else "None"},',
                        f'{indent}"travel_friction_json": \'{new_fields["travel_friction_json"]}\',',
                        f'{indent}"confidence": "{new_fields["confidence"]}",',
                        f'{indent}"volatility": "{new_fields["volatility"]}",',
                        f'{indent}"verified_by": "{new_fields["verified_by"]}",',
                    ]

                    # Add injection before last_verified
                    for inj_line in injection_lines:
                        new_lines.append(inj_line + '\n')

                    injected_count += 1
                    print(f"[OK] Injected: {proc_id} @ {jur_id}")

        new_lines.append(line)
        i += 1

    # Write back
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    return injected_count


def main():
    print("="*80)
    print("SMART BULK POPULATION - LINE BY LINE")
    print("="*80 + "\n")

    seed_path = Path(__file__).parent / "seed.py"

    if not seed_path.exists():
        print(f"[ERROR] seed.py not found at {seed_path}")
        return 1

    print(f"Processing {seed_path}...\n")
    injected_count = process_seed_file(seed_path)

    print(f"\n[SUCCESS] Injected schema fields into {injected_count} AccessRecords")
    print("\nNext steps:")
    print("  1. Review the updated seed.py file")
    print("  2. Run: python -m app.seed")
    print("  3. Verify database seeding completed successfully")

    return 0


if __name__ == "__main__":
    sys.exit(main())
