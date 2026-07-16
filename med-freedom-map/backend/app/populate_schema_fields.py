#!/usr/bin/env python3
"""
Bulk-populate AccessRecord entries with schema-compliant fields.
Parses estimated_cost_range_usd, computes total_access_cost_usd, assigns confidence/volatility.
"""
import re
import json
from typing import Dict, Tuple, Optional


# Travel cost by jurisdiction region (estimated USD)
TRAVEL_COSTS = {
    # US
    "jur-us-federal": 0,
    "jur-us-or": 0,
    "jur-us-co": 0,
    "jur-us-ca": 0,
    "jur-us-tx": 0,
    "jur-us-fl": 0,

    # Near US (easy travel)
    "jur-mx": 1500,
    "jur-ca": 1000,

    # Europe
    "jur-ch": 2500,
    "jur-nl": 2500,
    "jur-de": 2500,
    "jur-uk": 2500,
    "jur-be": 2500,
    "jur-fr": 2500,
    "jur-se": 2500,
    "jur-pt": 2500,
    "jur-es": 2500,
    "jur-gr": 2500,
    "jur-po": 2500,

    # Central/South America
    "jur-cr": 1200,
    "jur-br": 2000,
    "jur-ar": 2000,
    "jur-cl": 2000,
    "jur-hn": 1500,
    "jur-hn-prospera": 1500,

    # Asia
    "jur-th": 3000,
    "jur-jp": 3500,
    "jur-kr": 3500,
    "jur-sg": 3500,
    "jur-in": 2500,
    "jur-ph": 2500,

    # Middle East
    "jur-uae": 3000,
    "jur-il": 2500,

    # Africa
    "jur-za": 3500,

    # Caribbean
    "jur-jm": 1500,

    # Australia
    "jur-au": 4500,
}

# Min stay days by procedure type
MIN_STAY_DAYS = {
    "proc-psilocybin-trd": 1,
    "proc-psilocybin-eol": 1,
    "proc-mdma-ptsd": 2,
    "proc-ketamine-depression": 1,
    "proc-ibogaine-addiction": 5,
    "proc-gene-crispr": 30,
    "proc-gene-aa9": 30,
    "proc-stem-msc": 3,
    "proc-stem-car-t": 30,
    "proc-maid": 3,
    "proc-peptide-bpc": 1,
    "proc-peptide-thymosin": 1,
    "proc-repro-ivf": 7,
    "proc-repro-surrogacy": 180,
    "proc-repurposed-ldn": 0,
    "proc-repurposed-methylene": 0,
    "proc-repurposed-semaglutide": 0,
    "proc-repurposed-rapamycin": 0,
    "proc-nad-iv": 1,
    "proc-hbot": 14,
    "proc-fmt": 1,
    "proc-mescaline-therapy": 5,
}

# Access pathway mapping by legal status
ACCESS_PATHWAY_MAP = {
    "Approved_On_Label": "STANDARD_PRESCRIPTION",
    "Approved_Off_Label": "OFF_LABEL_PRESCRIPTION",
    "Permitted_Expanded_Access": "EXPANDED_ACCESS",
    "Permitted_RTT": "RIGHT_TO_TRY",
    "Clinical_Trial_Only": "CLINICAL_TRIAL_ENROLLMENT",
    "Physician_Discretion_Gray": "LICENSED_PROVIDER_REGIME",
    "Unregulated_Permitted": "LICENSED_PROVIDER_REGIME",
    "Decriminalized_No_Supply": "PERSONAL_IMPORT",
    "Prohibited": "NONE",
    "Unknown": "NONE",
    "Fully_Approved": "STANDARD_PRESCRIPTION",
    "Regulated_Therapy_Program": "LICENSED_PROVIDER_REGIME",
    "Decriminalized_Possession": "PERSONAL_IMPORT",
    "Right_To_Try": "RIGHT_TO_TRY",
    "Off_Label": "OFF_LABEL_PRESCRIPTION",
    "REGULATED_THERAPY": "LICENSED_PROVIDER_REGIME",
    "FULLY_APPROVED": "STANDARD_PRESCRIPTION",
    "OFF_LABEL": "OFF_LABEL_PRESCRIPTION",
    "FULLY_APPROVED": "STANDARD_PRESCRIPTION",
    "PHYSICIAN_DISCRETION": "LICENSED_PROVIDER_REGIME",
    "LEGAL": "LICENSED_PROVIDER_REGIME",
    "VARIABLE": "LICENSED_PROVIDER_REGIME",
}


def parse_cost_range(cost_range_text: str) -> Optional[float]:
    """Extract median price from estimated_cost_range_usd text.

    Examples:
        "$1,500-3,500 per session" -> 2500.0
        "$2,200,000+ (Casgevy list price)" -> 2200000.0
        "CHF 5,000-15,000 (USD $5,600-17,000) per treatment course" -> 11300.0
    """
    if not cost_range_text:
        return None

    # Try to find USD amounts first
    usd_matches = re.findall(r'\$[\d,]+', cost_range_text)
    if usd_matches:
        amounts = []
        for match in usd_matches:
            amount = float(match.replace('$', '').replace(',', ''))
            amounts.append(amount)
        if len(amounts) >= 2:
            return (amounts[0] + amounts[-1]) / 2  # median of low and high
        elif len(amounts) == 1:
            return amounts[0]

    # Try to find standalone numbers
    numbers = re.findall(r'[\d,]+', cost_range_text)
    if numbers:
        amounts = [float(n.replace(',', '')) for n in numbers if float(n.replace(',', '')) > 100]
        if len(amounts) >= 2:
            return (amounts[0] + amounts[-1]) / 2
        elif len(amounts) == 1:
            return amounts[0]

    return None


def get_confidence_and_volatility(legal_status: str, oversight_quality: str, jurisdiction_id: str) -> Tuple[str, str]:
    """Determine confidence and volatility based on legal/oversight state.

    Returns: (confidence, volatility)
    """
    # Volatility is primarily driven by legal status
    if "PENDING" in legal_status or "pending" in legal_status.lower():
        volatility = "PENDING_LEGISLATION"
    elif legal_status in ["REGULATED_THERAPY", "FULLY_APPROVED", "Approved_On_Label"]:
        volatility = "STABLE"
    elif "DECRIMINALIZED" in legal_status or "decriminalized" in legal_status.lower():
        volatility = "ACTIVE_FLUX"  # could be rescinded
    elif legal_status in ["Prohibited", "PROHIBITED"]:
        volatility = "STABLE"
    else:
        volatility = "ACTIVE_FLUX"  # uncertain/gray area

    # Confidence driven by oversight quality + source clarity
    if oversight_quality in ["HIGH", "Regulated_High"]:
        confidence = "HIGH"
    elif oversight_quality in ["MEDIUM", "VARIABLE", "Regulated_Moderate"]:
        confidence = "MODERATE"
    else:
        confidence = "LOW"

    return (confidence, volatility)


def get_price_confidence(cost_range_text: str) -> str:
    """Determine price_confidence based on text quality.

    QUOTED: explicit price data with sources
    ESTIMATED: range-based or inference
    UNKNOWN: no data
    """
    if not cost_range_text:
        return "UNKNOWN"

    # Explicit sourcing or quoted language
    if any(keyword in cost_range_text.lower() for keyword in
           ["quoted", "fda", "cms", "insurance", "covered", "list price", "median"]):
        return "QUOTED"

    # Range-based (estimated)
    if "-" in cost_range_text or "typical" in cost_range_text.lower():
        return "ESTIMATED"

    return "UNKNOWN"


def get_access_pathway(legal_status: str) -> str:
    """Map legal_status to AccessPathway enum."""
    # Normalize legal_status to match map keys
    normalized = legal_status.replace("_", "").lower()

    for key, value in ACCESS_PATHWAY_MAP.items():
        if key.replace("_", "").lower() == normalized:
            return value

    # Default mapping
    if "approved" in normalized:
        return "STANDARD_PRESCRIPTION"
    elif "off_label" in normalized or "offlabel" in normalized:
        return "OFF_LABEL_PRESCRIPTION"
    elif "rtt" in normalized or "right" in normalized:
        return "RIGHT_TO_TRY"
    elif "expanded" in normalized:
        return "EXPANDED_ACCESS"
    elif "trial" in normalized:
        return "CLINICAL_TRIAL_ENROLLMENT"
    elif "physician" in normalized or "discretion" in normalized:
        return "LICENSED_PROVIDER_REGIME"
    elif "legal" in normalized or "permitted" in normalized or "unregulated" in normalized:
        return "LICENSED_PROVIDER_REGIME"
    elif "import" in normalized or "decriminalized" in normalized:
        return "PERSONAL_IMPORT"
    elif "prohibited" in normalized or "banned" in normalized:
        return "NONE"

    return "LICENSED_PROVIDER_REGIME"  # default


def build_schema_fields(record: Dict) -> Dict:
    """Build new schema fields for an AccessRecord.

    Returns dict with keys to add/update:
    - access_pathway
    - price_usd
    - price_basis
    - price_confidence
    - total_access_cost_usd
    - travel_friction_json
    - confidence
    - volatility
    - verified_by
    """
    jurisdiction_id = record.get("jurisdiction_id")
    legal_status = record.get("legal_status", "")
    oversight = record.get("oversight_quality", "")
    cost_range = record.get("estimated_cost_range_usd", "")
    procedure_id = record.get("procedure_id", "")

    # Parse price
    price_usd = parse_cost_range(cost_range)

    # Add travel cost
    travel_cost = TRAVEL_COSTS.get(jurisdiction_id, 2000)  # default $2000
    min_stay = MIN_STAY_DAYS.get(procedure_id, 1)
    accommodation_cost = min_stay * 150  # assume $150/night
    total_access_cost = (price_usd or 0) + travel_cost + accommodation_cost

    # Get confidence/volatility
    confidence, volatility = get_confidence_and_volatility(legal_status, oversight, jurisdiction_id)

    # Get access pathway
    access_pathway = get_access_pathway(legal_status)

    # Get price confidence
    price_confidence = get_price_confidence(cost_range)

    # Travel friction
    travel_friction = {
        "visa": "none" if jurisdiction_id.startswith("jur-us") else "tourist_visa",
        "min_stay_days": min_stay,
        "language": "English"  # simplified; would need per-jurisdiction mapping
    }

    return {
        "access_pathway": access_pathway,
        "price_usd": price_usd if price_usd else None,
        "price_basis": "cash_pay",
        "price_confidence": price_confidence,
        "total_access_cost_usd": total_access_cost if price_usd else None,
        "travel_friction_json": json.dumps(travel_friction),
        "confidence": confidence,
        "volatility": volatility,
        "verified_by": "seed_data",  # would track real source per record
    }


def generate_schema_update_statements(records: list) -> list:
    """Generate update statements for all records.

    Returns list of dicts with original record + new fields.
    """
    updated = []

    for record in records:
        # Skip if already has access_pathway (already updated)
        if "access_pathway" in record:
            updated.append(record)
            continue

        new_fields = build_schema_fields(record)
        updated_record = {**record, **new_fields}
        updated.append(updated_record)

    return updated


def print_sample_updates(records: list, limit: int = 5) -> None:
    """Print sample of schema updates for review."""
    print(f"\n{'='*80}")
    print(f"SAMPLE SCHEMA UPDATES (first {limit} records)")
    print(f"{'='*80}\n")

    for i, record in enumerate(records[:limit]):
        if "access_pathway" in record:  # Skip already-updated
            continue

        new_fields = build_schema_fields(record)

        print(f"Procedure: {record.get('procedure_id')} | Jurisdiction: {record.get('jurisdiction_id')}")
        print(f"  Legal Status: {record.get('legal_status')}")
        print(f"  Oversight: {record.get('oversight_quality')}")
        print(f"  Cost Range: {record.get('estimated_cost_range_usd')}")
        print(f"\n  NEW FIELDS:")
        print(f"    access_pathway: {new_fields['access_pathway']}")
        print(f"    price_usd: {new_fields['price_usd']}")
        print(f"    price_confidence: {new_fields['price_confidence']}")
        print(f"    total_access_cost_usd: {new_fields['total_access_cost_usd']}")
        print(f"    confidence: {new_fields['confidence']}")
        print(f"    volatility: {new_fields['volatility']}")
        print(f"    travel_friction: {new_fields['travel_friction_json']}")
        print()


def export_python_code(records: list, filename: str = "seed_updates.py") -> None:
    """Export updated records as Python code (to copy into seed.py).

    This generates the exact syntax needed for seed.py.
    """
    updated = generate_schema_update_statements(records)

    with open(filename, 'w') as f:
        f.write("# AUTO-GENERATED: Schema-compliant AccessRecord updates\n")
        f.write("# Copy the ACCESS_RECORDS list below into seed.py\n\n")
        f.write("ACCESS_RECORDS = [\n")

        for i, record in enumerate(updated):
            f.write("    {\n")
            for key, value in record.items():
                if value is None:
                    f.write(f'        "{key}": None,\n')
                elif isinstance(value, str):
                    # Escape quotes
                    escaped_value = value.replace('"', '\\"')
                    f.write(f'        "{key}": "{escaped_value}",\n')
                elif isinstance(value, (int, float)):
                    f.write(f'        "{key}": {value},\n')
                elif isinstance(value, dict):
                    f.write(f'        "{key}": {value},\n')
                else:
                    f.write(f'        "{key}": {repr(value)},\n')
            f.write("    },\n")

        f.write("]\n")

    print(f"\n✅ Exported {len(updated)} records to {filename}")


if __name__ == "__main__":
    print("Schema Field Population Script")
    print("================================\n")

    # Example records from seed.py (would be loaded from actual seed data in real use)
    sample_records = [
        {
            "procedure_id": "proc-psilocybin-trd",
            "jurisdiction_id": "jur-us-co",
            "legal_status": "REGULATED_THERAPY",
            "oversight_quality": "HIGH",
            "estimated_cost_range_usd": "$1,500-3,500 per session",
        },
        {
            "procedure_id": "proc-mdma-ptsd",
            "jurisdiction_id": "jur-au",
            "legal_status": "Permitted_Expanded_Access",
            "oversight_quality": "HIGH",
            "estimated_cost_range_usd": "$AUD 8,000-15,000 (USD $5,400-10,100) per treatment course",
        },
        {
            "procedure_id": "proc-stem-car-t",
            "jurisdiction_id": "jur-us-federal",
            "legal_status": "FULLY_APPROVED",
            "oversight_quality": "HIGH",
            "estimated_cost_range_usd": "$373,000-475,000 (drug cost only). Total episode of care: $500,000-1,000,000+",
        },
        {
            "procedure_id": "proc-repro-ivf",
            "jurisdiction_id": "jur-mx",
            "legal_status": "FULLY_APPROVED",
            "oversight_quality": "VARIABLE",
            "estimated_cost_range_usd": "IVF cycle: $4,000-8,000 (50-70% less than US). PGT-A: $1,500-3,000.",
        },
        {
            "procedure_id": "proc-maid",
            "jurisdiction_id": "jur-ch",
            "legal_status": "FULLY_APPROVED",
            "oversight_quality": "HIGH",
            "estimated_cost_range_usd": "$8,500-13,600 (Dignitas/Pegasos cost)",
        },
        {
            "procedure_id": "proc-ibogaine-addiction",
            "jurisdiction_id": "jur-mx",
            "legal_status": "PHYSICIAN_DISCRETION",
            "oversight_quality": "VARIABLE",
            "estimated_cost_range_usd": "$3,000-8,000 for 5-7 day treatment program. Medical-supervised clinics: $6,000-12,000.",
        },
    ]

    # Show samples
    print_sample_updates(sample_records, limit=6)

    print("\n" + "="*80)
    print("TO USE THIS SCRIPT WITH ACTUAL SEED DATA:")
    print("="*80)
    print("""
1. Import ACCESS_RECORDS from seed.py
2. Call: updated = generate_schema_update_statements(ACCESS_RECORDS)
3. Export with: export_python_code(ACCESS_RECORDS)
4. Copy output into seed.py

Example usage:
    from seed import ACCESS_RECORDS
    updated_records = generate_schema_update_statements(ACCESS_RECORDS)
    export_python_code(ACCESS_RECORDS, "updated_access_records.py")
""")
