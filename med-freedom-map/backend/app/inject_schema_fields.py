#!/usr/bin/env python3
"""
Simpler approach: inject schema fields by regex pattern matching.
Finds each AccessRecord entry and inserts new fields before last_verified.
"""
import re
from pathlib import Path
from populate_schema_fields import build_schema_fields, get_price_confidence, parse_cost_range


FIELD_INJECTION_TEMPLATE = '''     "price_usd": {price_usd},
     "price_basis": "cash_pay",
     "price_confidence": "{price_confidence}",
     "total_access_cost_usd": {total_access_cost},
     "travel_friction_json": '{travel_friction_json}',
     "confidence": "{confidence}",
     "volatility": "{volatility}",
     "verified_by": "{verified_by}",'''


def inject_schema_fields_into_seed() -> int:
    """Inject schema fields into seed.py by regex pattern matching."""
    seed_path = Path(__file__).parent / "seed.py"

    with open(seed_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find all AccessRecord dictionaries
    # Pattern: {"procedure_id": "...", ..., "last_verified": date(...), ...}
    # We want to insert new fields before "last_verified"

    # Since we can't easily parse Python dicts with enums, we'll do a simpler approach:
    # Find lines starting with "last_verified" within an AccessRecord and insert before them

    lines = content.split('\n')
    new_lines = []
    injected_count = 0
    in_access_record = False
    current_record_start = None

    for i, line in enumerate(lines):
        # Check if this is the start of ACCESS_RECORDS
        if "ACCESS_RECORDS = [" in line:
            in_access_record = True

        # Check if this line has "last_verified"
        if in_access_record and 'last_verified": date(' in line:
            # Extract the record dict from current position back to opening {
            # This is hacky but works for our format

            # Look back to find opening { of this record
            record_start = i - 1
            while record_start >= 0 and lines[record_start].strip() != "{":
                record_start -= 1

            # Extract procedure_id and other key fields from the record
            record_lines = lines[record_start:i+1]
            record_text = '\n'.join(record_lines)

            # Extract fields using regex
            proc_match = re.search(r'"procedure_id":\s*"([^"]+)"', record_text)
            jur_match = re.search(r'"jurisdiction_id":\s*"([^"]+)"', record_text)
            status_match = re.search(r'"legal_status":\s*([\w\.]+)', record_text)
            oversight_match = re.search(r'"oversight_quality":\s*([\w\.]+)', record_text)
            cost_match = re.search(r'"estimated_cost_range_usd":\s*"([^"]*)"', record_text)

            if proc_match and jur_match:
                procedure_id = proc_match.group(1)
                jurisdiction_id = jur_match.group(1)
                legal_status = status_match.group(1) if status_match else ""
                oversight = oversight_match.group(1) if oversight_match else ""
                cost_range = cost_match.group(1) if cost_match else ""

                # Build schema fields using our logic
                import json
                from populate_schema_fields import (
                    TRAVEL_COSTS, MIN_STAY_DAYS, parse_cost_range, get_confidence_and_volatility
                )

                price_usd = parse_cost_range(cost_range)
                travel_cost = TRAVEL_COSTS.get(jurisdiction_id, 2000)
                min_stay = MIN_STAY_DAYS.get(procedure_id, 1)
                accommodation_cost = min_stay * 150
                total_access_cost = (price_usd or 0) + travel_cost + accommodation_cost

                confidence, volatility = get_confidence_and_volatility(legal_status, oversight, jurisdiction_id)
                price_confidence = get_price_confidence(cost_range)

                travel_friction = {
                    "visa": "none" if jurisdiction_id.startswith("jur-us") else "tourist_visa",
                    "min_stay_days": min_stay,
                    "language": "English"
                }

                # Check if already has these fields
                if '"price_usd"' not in record_text:
                    # Insert before last_verified
                    indent = "     "  # Match existing indentation
                    new_fields = f'''{indent}"price_usd": {price_usd if price_usd else "None"},
{indent}"price_basis": "cash_pay",
{indent}"price_confidence": "{price_confidence}",
{indent}"total_access_cost_usd": {total_access_cost if price_usd else "None"},
{indent}"travel_friction_json": '{json.dumps(travel_friction)}',
{indent}"confidence": "{confidence}",
{indent}"volatility": "{volatility}",
{indent}"verified_by": "seed_data",
'''
                    # Insert before this line
                    new_lines.append(new_fields)
                    injected_count += 1

        new_lines.append(line)

    # Write updated content
    with open(seed_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    return injected_count


if __name__ == "__main__":
    print("Injecting schema fields into seed.py...")
    count = inject_schema_fields_into_seed()
    print(f"✅ Injected schema fields into {count} AccessRecord entries")
