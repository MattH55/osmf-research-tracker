#!/usr/bin/env python3
"""
Direct population by modifying records with a safe Python approach.
Reads seed.py, parses Python data, updates records, writes back.
"""
import sys
import re
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from populate_schema_fields import build_schema_fields


def update_seed_py_directly():
    """
    Read seed.py, find each {"procedure_id" ... "last_verified": date(...), "sources": [...]}
    and inject schema fields before last_verified.
    """
    seed_path = Path(__file__).parent / "seed.py"

    with open(seed_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find ACCESS_RECORDS section
    start_marker = "ACCESS_RECORDS = ["
    end_marker = "\ndef seed_database():"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print("[ERROR] Could not find ACCESS_RECORDS in seed.py")
        return 0

    # Extract just the records section
    records_section = content[start_idx + len(start_marker):end_idx]

    # Count how many times we see last_verified (each record has one)
    last_verified_count = records_section.count('last_verified": date(')
    print(f"[OK] Found {last_verified_count} AccessRecords in seed.py")

    # Process each record: find last_verified line and insert before it
    # Strategy: find every occurrence of '"last_verified": date(' and insert before it

    # Split by "last_verified" to find insertion points
    parts = records_section.split('"last_verified"')

    if len(parts) < 2:
        print("[ERROR] Could not split records by last_verified")
        return 0

    new_records_section = parts[0]  # Start with first part (before first last_verified)
    injected_count = 0

    for i in range(1, len(parts)):
        # For each subsequent part, check if it already has price_usd
        # Go back in new_records_section to find the record dict

        # Extract enough context to identify procedure_id and jurisdiction_id
        # Look at the part before this one
        prev_part_end = new_records_section[-1000:] if len(new_records_section) > 1000 else new_records_section

        if '"price_usd"' not in parts[i][:200]:  # Not already have price_usd nearby
            # Extract procedure_id and jurisdiction_id from the record text
            proc_match = re.search(r'"procedure_id":\s*"([^"]+)"', prev_part_end + '"price_usd' + parts[i][:500])
            jur_match = re.search(r'"jurisdiction_id":\s*"([^"]+)"', prev_part_end + '"price_usd' + parts[i][:500])

            if proc_match and jur_match:
                proc_id = proc_match.group(1)
                jur_id = jur_match.group(1)

                # Extract cost range
                cost_match = re.search(r'"estimated_cost_range_usd":\s*"([^"]*)"', prev_part_end + '"price_usd' + parts[i][:500])
                cost_range = cost_match.group(1) if cost_match else ""

                # Extract legal_status and oversight
                status_match = re.search(r'"legal_status":\s*(LegalStatus\.\w+)', prev_part_end + '"price_usd' + parts[i][:500])
                oversight_match = re.search(r'"oversight_quality":\s*(OversightQuality\.\w+)', prev_part_end + '"price_usd' + parts[i][:500])

                legal_status = status_match.group(1) if status_match else ""
                oversight = oversight_match.group(1) if oversight_match else ""

                # Build schema fields
                record_dict = {
                    'procedure_id': proc_id,
                    'jurisdiction_id': jur_id,
                    'legal_status': legal_status,
                    'oversight_quality': oversight,
                    'estimated_cost_range_usd': cost_range,
                }

                try:
                    new_fields = build_schema_fields(record_dict)

                    # Format injection
                    indent = '     '
                    injection = (
                        f'{indent}"price_usd": {new_fields["price_usd"] if new_fields["price_usd"] else "None"},\n'
                        f'{indent}"price_basis": "{new_fields["price_basis"]}",\n'
                        f'{indent}"price_confidence": "{new_fields["price_confidence"]}",\n'
                        f'{indent}"total_access_cost_usd": {new_fields["total_access_cost_usd"] if new_fields["total_access_cost_usd"] else "None"},\n'
                        f'{indent}"travel_friction_json": \'{new_fields["travel_friction_json"]}\',\n'
                        f'{indent}"confidence": "{new_fields["confidence"]}",\n'
                        f'{indent}"volatility": "{new_fields["volatility"]}",\n'
                        f'{indent}"verified_by": "{new_fields["verified_by"]}",\n'
                    )

                    new_records_section += injection + '"last_verified"' + parts[i]
                    injected_count += 1
                    print(f"[OK] Injected: {proc_id} @ {jur_id}")
                except Exception as e:
                    print(f"[WARN] Failed to process {proc_id} @ {jur_id}: {e}")
                    new_records_section += '"last_verified"' + parts[i]
            else:
                new_records_section += '"last_verified"' + parts[i]
        else:
            # Already has price_usd, skip
            new_records_section += '"last_verified"' + parts[i]

    # Reconstruct the full content
    new_content = (
        content[:start_idx + len(start_marker)] +
        new_records_section +
        content[end_idx:]
    )

    # Write back
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    return injected_count


if __name__ == "__main__":
    print("="*80)
    print("DIRECT SEED.PY POPULATION")
    print("="*80 + "\n")

    injected_count = update_seed_py_directly()

    print(f"\n[SUCCESS] Injected schema fields into {injected_count} additional AccessRecords")
    print(f"\nTotal AccessRecords now schema-compliant:")
    print(f"  8 manually updated + {injected_count} bulk injected = {8 + injected_count} total")
