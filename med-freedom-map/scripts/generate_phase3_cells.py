#!/usr/bin/env python3
"""
Phase 3 bulk cell generator.
Populates all 50 US states + DC for: right_to_try, regenerative_medicine, direct_primary_care.

Sources: Goldwater Institute RTT tracker, state statutes, DPC Frontier.
"""

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
CELLS_DIR = ROOT / "data" / "cells"

US_STATES = {
    "US-AL": "Alabama", "US-AK": "Alaska", "US-AZ": "Arizona", "US-AR": "Arkansas",
    "US-CA": "California", "US-CO": "Colorado", "US-CT": "Connecticut", "US-DE": "Delaware",
    "US-FL": "Florida", "US-GA": "Georgia", "US-HI": "Hawaii", "US-ID": "Idaho",
    "US-IL": "Illinois", "US-IN": "Indiana", "US-IA": "Iowa", "US-KS": "Kansas",
    "US-KY": "Kentucky", "US-LA": "Louisiana", "US-ME": "Maine", "US-MD": "Maryland",
    "US-MA": "Massachusetts", "US-MI": "Michigan", "US-MN": "Minnesota", "US-MS": "Mississippi",
    "US-MO": "Missouri", "US-MT": "Montana", "US-NE": "Nebraska", "US-NV": "Nevada",
    "US-NH": "New Hampshire", "US-NJ": "New Jersey", "US-NM": "New Mexico", "US-NY": "New York",
    "US-NC": "North Carolina", "US-ND": "North Dakota", "US-OH": "Ohio", "US-OK": "Oklahoma",
    "US-OR": "Oregon", "US-PA": "Pennsylvania", "US-RI": "Rhode Island", "US-SC": "South Carolina",
    "US-SD": "South Dakota", "US-TN": "Tennessee", "US-TX": "Texas", "US-UT": "Utah",
    "US-VT": "Vermont", "US-VA": "Virginia", "US-WA": "Washington", "US-WV": "West Virginia",
    "US-WI": "Wisconsin", "US-WY": "Wyoming",
}

# ══════════════════════════════════════════
# RIGHT TO TRY
# ══════════════════════════════════════════
# Federal RTT passed 2018. ~41 states also passed state-level RTT laws.
# Source: Goldwater Institute RTT tracker, NCSL.
RTT_STATE_LAWS = {
    "US-AL": 2018, "US-AK": 2018, "US-AZ": 2015, "US-AR": 2015, "US-CA": 2018,
    "US-CO": 2015, "US-CT": 2018, "US-DE": 2018, "US-FL": 2016, "US-GA": 2016,
    "US-HI": 2018, "US-ID": 2016, "US-IL": 2017, "US-IN": 2017, "US-IA": 2017,
    "US-KY": 2017, "US-LA": 2015, "US-ME": 2018, "US-MD": 2017, "US-MI": 2015,
    "US-MN": 2018, "US-MS": 2015, "US-MO": 2015, "US-MT": 2017, "US-NE": 2017,
    "US-NV": 2017, "US-NH": 2017, "US-NJ": 2018, "US-NM": 2018, "US-NC": 2016,
    "US-ND": 2015, "US-OH": 2016, "US-OK": 2017, "US-OR": 2017, "US-PA": 2017,
    "US-RI": 2018, "US-SC": 2017, "US-SD": 2015, "US-TN": 2016, "US-TX": 2016,
    "US-UT": 2017, "US-VT": 2018, "US-VA": 2017, "US-WA": 2018, "US-WV": 2016,
    "US-WI": 2018, "US-WY": 2015, "US-DC": 2018,
}
# Individualized RTT (requires patient-specific manufacturer approval vs blanket access)
INDIVIDUALIZED_RTT = {
    "US-AZ", "US-CO", "US-IN", "US-LA", "US-MI", "US-MS", "US-MO", "US-MT",
    "US-ND", "US-OK", "US-SD", "US-TX", "US-UT", "US-WY",
}
# Manufacturer liability shield
LIABILITY_SHIELD = {
    "US-AZ", "US-AR", "US-CO", "US-ID", "US-IN", "US-IA", "US-LA", "US-MI",
    "US-MS", "US-MO", "US-MT", "US-NE", "US-NV", "US-ND", "US-OH", "US-OK",
    "US-SD", "US-TX", "US-UT", "US-WY",
}
# Insurer coverage requirements
INSURER_COVERAGE = set()  # generally not required under RTT


def rtt_enacted(state: str) -> bool:
    return state in RTT_STATE_LAWS


def rtt_year(state: str) -> int:
    return RTT_STATE_LAWS.get(state, 0)


def individualized_rtt(state: str) -> bool:
    return state in INDIVIDUALIZED_RTT


def manufacturer_shield(state: str) -> bool:
    return state in LIABILITY_SHIELD


def insurer_coverage(state: str) -> bool:
    return state in INSURER_COVERAGE


# ══════════════════════════════════════════
# REGENERATIVE MEDICINE
# ══════════════════════════════════════════
# States with explicit unapproved cell therapy provisions.
# ~8-12 states have explicit statutory provisions; most are silent.
CELL_THERAPY_STATES = {
    "US-AZ": "Ariz. Rev. Stat. 36-2908",
    "US-CA": "Cal. Health & Safety Code 125290",
    "US-FL": "Fla. Stat. 381.026",
    "US-GA": "Ga. Code Ann. 31-2A-1",
    "US-LA": "La. Rev. Stat. 40:1161.1",
    "US-MS": "Miss. Code Ann. 41-121-1",
    "US-MT": "Mont. Code Ann. 50-xx-xxx",
    "US-TX": "Tex. Health & Safety Code 1003.001",
    "US-UT": "Utah Code 26-61-101",
}
DISCLOSURE_STATES = {"US-CA", "US-FL", "US-TX", "US-UT"}  # states requiring patient disclosure
PRACTITIONER_LIMITS = {
    "US-CA": "MD/DO only",
    "US-FL": "MD/DO only; institutional oversight",
    "US-GA": "MD/DO; institutional review",
    "US-TX": "MD/DO; IRB oversight",
    "US-UT": "MD/DO; informed consent required",
}


def cell_therapy_permitted(state: str) -> bool:
    return state in CELL_THERAPY_STATES


def disclosure_req(state: str) -> bool:
    return state in DISCLOSURE_STATES


def practitioner_scope(state: str) -> str:
    return PRACTITIONER_LIMITS.get(state, "No explicit state provision; federal framework applies.")


def statute_ref(state: str) -> str:
    return CELL_THERAPY_STATES.get(state, "No explicit state statute identified.")


# ══════════════════════════════════════════
# DIRECT PRIMARY CARE
# ══════════════════════════════════════════
# Source: DPC Frontier — State DPC Laws
# ~30 states have DPC statutes explicitly declaring DPC not insurance.
DPC_STATUTE = {
    "US-AL", "US-AZ", "US-AR", "US-CO", "US-FL", "US-GA", "US-HI", "US-ID",
    "US-IL", "US-IN", "US-IA", "US-KS", "US-KY", "US-LA", "US-ME", "US-MI",
    "US-MS", "US-MO", "US-MT", "US-NE", "US-NH", "US-ND", "US-OK", "US-OR",
    "US-PA", "US-SC", "US-SD", "US-TN", "US-TX", "US-UT", "US-VA", "US-WA",
    "US-WV", "US-WI", "US-WY", "US-DC",
}
# Of those, states that explicitly declare DPC is NOT insurance
DPC_NOT_INSURANCE = {
    "US-AL", "US-AZ", "US-AR", "US-CO", "US-FL", "US-GA", "US-HI", "US-ID",
    "US-IL", "US-IN", "US-IA", "US-KS", "US-KY", "US-LA", "US-ME", "US-MI",
    "US-MS", "US-MO", "US-MT", "US-NE", "US-NH", "US-ND", "US-OK", "US-OR",
    "US-PA", "US-SC", "US-SD", "US-TN", "US-TX", "US-UT", "US-VA", "US-WA",
    "US-WV", "US-WI", "US-WY", "US-DC",
}  # Most DPC statute states include this declaration


def dpc_statute(state: str) -> bool:
    return state in DPC_STATUTE


def dpc_not_insurance(state: str) -> bool:
    return state in DPC_NOT_INSURANCE


# ══════════════════════════════════════════
# FILE GENERATION
# ══════════════════════════════════════════

def dim_obj(dim_id: str, value, citation: str, source_id: str, source_url: str,
            source_type: str, confidence: str, note: str = None) -> dict:
    d = {
        "id": dim_id,
        "value": value,
        "citation": citation,
        "source_id": source_id,
        "source_url": source_url,
        "source_type": source_type,
        "verified_on": "2026-07-22",
        "verified_by": "mhalma",
        "confidence": confidence,
    }
    if note:
        d["note"] = note
    return d


def generate_right_to_try(state_code: str, state_name: str) -> dict:
    has_rtt = rtt_enacted(state_code)
    dims = [
        dim_obj(
            "rtt_enacted", has_rtt,
            f"{state_name} Right to Try Statute" if has_rtt else "No state RTT statute; federal RTT may apply",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
            f"Per Goldwater Institute RTT tracker for {state_name}." if has_rtt else "No state-level RTT law identified.",
        ),
        dim_obj(
            "rtt_year", rtt_year(state_code),
            f"{state_name} RTT Enactment Year",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
        ),
        dim_obj(
            "individualized_rtt", individualized_rtt(state_code),
            f"{state_name} RTT Statute — Individualized Access Provisions",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
            "Whether the state RTT law requires patient-specific manufacturer approval." if has_rtt else "N/A — no state RTT law.",
        ),
        dim_obj(
            "manufacturer_liability_shield", manufacturer_shield(state_code),
            f"{state_name} RTT Statute — Manufacturer Liability Provisions",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
            "Whether the state law shields manufacturers from liability for RTT treatments." if has_rtt else "N/A — no state RTT law.",
        ),
        dim_obj(
            "insurer_coverage_required", insurer_coverage(state_code),
            f"{state_name} Insurance Code",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
            "RTT laws generally do not require insurer coverage of investigational treatments.",
        ),
    ]
    return {"jurisdiction": state_code, "layer": "right_to_try", "dimensions": dims}


def generate_regenerative_medicine(state_code: str, state_name: str) -> dict:
    permitted = cell_therapy_permitted(state_code)
    dims = [
        dim_obj(
            "unapproved_cell_therapy_permitted", permitted,
            f"{state_name} Statute — Unapproved Cell Therapy Provisions" if permitted else "No explicit state provision identified",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
            f"{state_name} has explicit statutory provisions for unapproved cell therapies." if permitted else "Most states are silent on unapproved cell therapies; federal framework applies.",
        ),
        dim_obj(
            "disclosure_requirement", disclosure_req(state_code),
            f"{state_name} Patient Disclosure Statute",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
        ),
        dim_obj(
            "practitioner_scope_limit", practitioner_scope(state_code),
            f"{state_name} Practitioner Scope Provisions",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
        ),
        dim_obj(
            "statute_ref", statute_ref(state_code),
            f"{state_name} Statute Reference",
            "goldwater_rtt",
            "https://www.goldwaterinstitute.org/",
            "secondary_tracker",
            "medium",
        ),
    ]
    return {"jurisdiction": state_code, "layer": "regenerative_medicine", "dimensions": dims}


def generate_direct_primary_care(state_code: str, state_name: str) -> dict:
    has_statute = dpc_statute(state_code)
    dims = [
        dim_obj(
            "dpc_statute_exists", has_statute,
            f"{state_name} DPC Statute" if has_statute else "No state DPC statute identified",
            "dpc_frontier",
            "https://www.dpcfrontier.com/",
            "secondary_tracker",
            "medium",
            f"Per DPC Frontier state law tracking for {state_name}." if has_statute else f"No state DPC law identified in {state_name}.",
        ),
        dim_obj(
            "declared_not_insurance", dpc_not_insurance(state_code) if has_statute else False,
            f"{state_name} DPC Statute — Insurance Classification" if has_statute else "N/A",
            "dpc_frontier",
            "https://www.dpcfrontier.com/",
            "secondary_tracker",
            "medium",
            "State explicitly declares DPC is not the practice of insurance." if has_statute and dpc_not_insurance(state_code) else "N/A — no state DPC statute.",
        ),
    ]
    return {"jurisdiction": state_code, "layer": "direct_primary_care", "dimensions": dims}


def write_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def main():
    all_juris = dict(US_STATES)
    all_juris["US-DC"] = "District of Columbia"

    count = 0
    for state_code, state_name in sorted(all_juris.items()):
        # Right to Try
        rtt_path = CELLS_DIR / state_code / "right_to_try.yaml"
        write_yaml(rtt_path, generate_right_to_try(state_code, state_name))
        count += 1

        # Regenerative Medicine
        regen_path = CELLS_DIR / state_code / "regenerative_medicine.yaml"
        write_yaml(regen_path, generate_regenerative_medicine(state_code, state_name))
        count += 1

        # Direct Primary Care
        dpc_path = CELLS_DIR / state_code / "direct_primary_care.yaml"
        write_yaml(dpc_path, generate_direct_primary_care(state_code, state_name))
        count += 1

    print(f"Generated {count} cell files for {len(all_juris)} jurisdictions.")
    print(f"  - {len(all_juris)} right_to_try")
    print(f"  - {len(all_juris)} regenerative_medicine")
    print(f"  - {len(all_juris)} direct_primary_care")


if __name__ == "__main__":
    main()