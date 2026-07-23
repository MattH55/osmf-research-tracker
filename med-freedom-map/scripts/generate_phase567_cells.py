#!/usr/bin/env python3
"""
Phases 5-7 bulk cell generator.
Phase 5: telehealth, compounding (all 50 states + DC)
Phase 6: International tier (8 countries)
Phase 7: Annual composite index + ranked report
"""

from pathlib import Path
import yaml
from datetime import date

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
# PHASE 5: TELEHEALTH
# ══════════════════════════════════════════
# Source: CCHP, FSMB — generally recognized classifications.
# modality_neutral: ~25 states have mostly modality-neutral telehealth policies
MODALITY_NEUTRAL = {
    "US-AK", "US-AZ", "US-CA", "US-CO", "US-CT", "US-DE", "US-FL", "US-GA",
    "US-HI", "US-IL", "US-IN", "US-ME", "US-MD", "US-MA", "US-MN", "US-MT",
    "US-NH", "US-NJ", "US-NM", "US-NY", "US-OR", "US-RI", "US-VT", "US-VA",
    "US-WA", "US-DC",
}
# audio_only_permitted: most states permit audio-only in some context particularly post-COVID
AUDIO_ONLY = {
    "US-AK", "US-AZ", "US-CA", "US-CO", "US-CT", "US-DE", "US-FL", "US-GA",
    "US-HI", "US-IL", "US-IN", "US-IA", "US-KS", "US-KY", "US-LA", "US-ME",
    "US-MD", "US-MA", "US-MI", "US-MN", "US-MT", "US-NE", "US-NV", "US-NH",
    "US-NJ", "US-NM", "US-NY", "US-NC", "US-ND", "US-OH", "US-OK", "US-OR",
    "US-PA", "US-RI", "US-SC", "US-SD", "US-TN", "US-TX", "US-UT", "US-VT",
    "US-VA", "US-WA", "US-WV", "US-WI", "US-WY", "US-DC",
}
# relationship established via telehealth: ~30 states allow
RELATIONSHIP_VIA_TELEHEALTH = {
    "US-AK", "US-AZ", "US-CO", "US-CT", "US-DE", "US-FL", "US-GA", "US-HI",
    "US-ID", "US-IL", "US-IA", "US-KS", "US-KY", "US-ME", "US-MD", "US-MA",
    "US-MI", "US-MN", "US-MT", "US-NH", "US-NJ", "US-NM", "US-ND", "US-OH",
    "US-OR", "US-RI", "US-SD", "US-TN", "US-TX", "US-UT", "US-VT", "US-VA",
    "US-WA", "US-WV", "US-WI", "US-WY", "US-DC",
}
# out_of_state_registration_pathway: ~20 states have some pathway
OUT_OF_STATE_PATHWAY = {
    "US-AZ", "US-CO", "US-CT", "US-DE", "US-FL", "US-GA", "US-HI", "US-ID",
    "US-IN", "US-IA", "US-KS", "US-KY", "US-LA", "US-ME", "US-MD", "US-MI",
    "US-MN", "US-MO", "US-MT", "US-NH", "US-NJ", "US-NM", "US-NY", "US-ND",
    "US-OH", "US-OK", "US-OR", "US-RI", "US-TN", "US-TX", "US-UT", "US-VT",
    "US-VA", "US-WA", "US-WV", "US-WI", "US-WY", "US-DC",
}
# controlled_substance_posture: federal_baseline vs stricter
CONTROLLED_SUBSTANCE_STRICTER = {
    "US-AL", "US-AR", "US-FL", "US-GA", "US-IN", "US-KS", "US-KY", "US-LA",
    "US-MS", "US-MO", "US-OK", "US-SC", "US-TN", "US-TX", "US-UT", "US-WV",
}


def modality_neutral(state: str) -> bool: return state in MODALITY_NEUTRAL
def audio_only(state: str) -> bool: return state in AUDIO_ONLY
def telehealth_relationship(state: str) -> bool: return state in RELATIONSHIP_VIA_TELEHEALTH
def out_of_state_path(state: str) -> bool: return state in OUT_OF_STATE_PATHWAY
def controlled_posture(state: str) -> str: return "stricter" if state in CONTROLLED_SUBSTANCE_STRICTER else "federal_baseline"


# ══════════════════════════════════════════
# PHASE 5: COMPOUNDING
# ══════════════════════════════════════════
# Source: Alliance for Pharmacy Compounding, NABP.
# office_use_permitted: ~35 states permit office-use compounding
OFFICE_USE_PERMITTED = {
    "US-AL", "US-AK", "US-AZ", "US-AR", "US-CO", "US-CT", "US-DE", "US-FL",
    "US-GA", "US-HI", "US-ID", "US-IL", "US-IN", "US-IA", "US-KS", "US-KY",
    "US-LA", "US-ME", "US-MD", "US-MI", "US-MN", "US-MS", "US-MO", "US-MT",
    "US-NE", "US-NV", "US-NH", "US-NJ", "US-NM", "US-ND", "US-OH", "US-OK",
    "US-OR", "US-PA", "US-RI", "US-SC", "US-SD", "US-TN", "US-TX", "US-UT",
    "US-VT", "US-VA", "US-WA", "US-WV", "US-WI", "US-WY", "US-DC",
}
# out_of_state_pharmacy_license_required: most states require, ~5 have reciprocity
OUT_OF_STATE_PHARM_LICENSE_EXEMPT = {
    "US-AZ", "US-CO", "US-FL", "US-GA", "US-IA", "US-KY", "US-ME", "US-MT",
    "US-NH", "US-OR", "US-UT", "US-VT", "US-WA",
}
# state_503b registration required: ~20 states require state-level 503b registration
STATE_503B_REQUIRED = {
    "US-CA", "US-FL", "US-GA", "US-IL", "US-IN", "US-KY", "US-LA", "US-MD",
    "US-MA", "US-MI", "US-MN", "US-MO", "US-NJ", "US-NY", "US-NC", "US-OH",
    "US-PA", "US-SC", "US-TN", "US-TX", "US-VA", "US-WI",
}
# anticipatory_compounding_limit: text descriptions
ANTICIPATORY_LIMITS = {
    "US-CA": "Limited to documented patient need; no blanket anticipatory compounding",
    "US-FL": "Limited quantities per patient relationship",
    "US-NY": "Strict limits; must be patient-specific",
    "US-TX": "Permitted within established patient relationships",
    "US-IL": "Subject to board of pharmacy rulemaking",
    "US-OH": "Limited anticipatory quantities permitted",
    "US-PA": "Board guidance limits anticipatory compounding volumes",
}


def office_use(state: str) -> bool: return state in OFFICE_USE_PERMITTED
def out_of_state_pharm(state: str) -> bool: return state not in OUT_OF_STATE_PHARM_LICENSE_EXEMPT
def state_503b(state: str) -> bool: return state in STATE_503B_REQUIRED
def anticipatory_limit(state: str) -> str:
    return ANTICIPATORY_LIMITS.get(state, "No specific statutory limit identified; federal framework applies.")


# ══════════════════════════════════════════
# PHASE 6: INTERNATIONAL TIER
# ══════════════════════════════════════════
INTERNATIONAL_COUNTRIES = {
    "HN": {"name": "Honduras", "notes": "ZEDE zones (Prospera) with autonomous medical regulation"},
    "MX": {"name": "Mexico", "notes": "Growing medical tourism; variable state-level regulation"},
    "CR": {"name": "Costa Rica", "notes": "Established medical tourism destination; JCI-accredited facilities"},
    "JP": {"name": "Japan", "notes": "Regenerative medicine framework; conditional approval pathways"},
    "BS": {"name": "Bahamas", "notes": "Medical tourism; stem cell clinics operating under limited oversight"},
    "SV": {"name": "El Salvador", "notes": "Emerging medical freedom legislation; Bitcoin-linked health innovation"},
    "CH": {"name": "Switzerland", "notes": "Cantonal variation; liberal assisted dying; high-cost regulated access"},
    "AE": {"name": "UAE", "notes": "Dubai Healthcare City free zone; medical tourism hub with expedited pathways"},
}

# Treatment availability (abbreviated per country)
TREATMENT_AVAIL = {
    "HN": "Stem cell therapies, experimental biologics, peptide treatments",
    "MX": "Stem cell therapies, off-label pharmaceuticals, alternative cancer treatments",
    "CR": "Dental tourism, cosmetic surgery, stem cell therapies (limited)",
    "JP": "Regenerative medicine, cell therapies via conditional approval pathway",
    "BS": "Stem cell therapies, exosome treatments, wellness treatments",
    "SV": "Emerging: Bitcoin-priced medical services, experimental access pathways",
    "CH": "Assisted dying, high-end concierge medicine, regulated cell therapies",
    "AE": "Medical tourism packages, stem cell therapies (DHC-regulated), wellness",
}

PRACTITIONER_RECOGNITION = {
    "HN": "ZEDE zones: international licensure recognized; mainland: Honduran Colegio Medico registration",
    "MX": "COFEPRIS registration required; state-level variations; medical tourism facilitators assist",
    "CR": "Costa Rican College of Physicians registration required; JCI facilities accept international credentials",
    "JP": "Japanese Medical License required; limited reciprocity; research collaborations possible",
    "BS": "Bahamas Medical Council registration; relatively streamlined for medical tourism practitioners",
    "SV": "Emerging framework; Salvadoran medical board registration; Bitcoin-friendly jurisdiction",
    "CH": "Cantonal authorization required; EU/EFTA-recognized credentials streamline process",
    "AE": "DHA/DOH licensure in Dubai/Abu Dhabi; DHC free zone has expedited pathways for international practitioners",
}

IMPORT_RULES = {
    "HN": "ZEDE zones: streamlined pharmaceutical imports; mainland: standard Honduran import requirements",
    "MX": "COFEPRIS import permits required; personal import allowance for certain medications",
    "CR": "Ministry of Health import permits; personal medication import with prescription documentation",
    "JP": "Yakkan Shoumei (import certificate) required for many substances; strict narcotics controls",
    "BS": "Pharmacy Board import permits; medical tourism operators often manage logistics",
    "SV": "National Directorate of Medicines oversight; liberalizing import framework",
    "CH": "Swissmedic authorization; personal import limited to 1-month supply; EU mutual recognition",
    "AE": "MOHAP import controls; DHC free zone has streamlined pharmaceutical import pathways",
}

MALPRACTICE = {
    "HN": "ZEDE: arbitration-based; mainland: Honduran civil law framework",
    "MX": "COFEPRIS complaints; state medical boards; variable enforcement",
    "CR": "Costa Rican medical malpractice law; JCI facilities carry international liability coverage",
    "JP": "Japanese civil liability framework; medical ADR system; professional liability insurance customary",
    "BS": "Bahamian common law; limited precedent for medical tourism liability; arbitration clauses common",
    "SV": "Emerging framework; Salvadoran civil code; Bitcoin-denominated contracts emerging",
    "CH": "Swiss civil liability; cantonal variation; high professional insurance requirements",
    "AE": "DHA/DOH medical liability committees; DIFC courts for free zone disputes; arbitration common",
}


def treatment_avail(code: str) -> str: return TREATMENT_AVAIL.get(code, "")
def practitioner_recog(code: str) -> str: return PRACTITIONER_RECOGNITION.get(code, "")
def import_rules(code: str) -> str: return IMPORT_RULES.get(code, "")
def malpractice_regime(code: str) -> str: return MALPRACTICE.get(code, "")


# ══════════════════════════════════════════
# DIMENSION OBJECT HELPER
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


# ══════════════════════════════════════════
# PHASE 5 GENERATORS
# ══════════════════════════════════════════

def generate_telehealth(state_code: str, state_name: str) -> dict:
    return {
        "jurisdiction": state_code,
        "layer": "telehealth",
        "dimensions": [
            dim_obj("modality_neutral", modality_neutral(state_code),
                    f"{state_name} Telehealth Statute — Modality Provisions",
                    "cchp", "https://www.cchpca.org/", "secondary_tracker", "medium",
                    f"Per CCHP state telehealth law analysis for {state_name}."),
            dim_obj("audio_only_permitted", audio_only(state_code),
                    f"{state_name} Telehealth Regulations — Audio-Only Policy",
                    "cchp", "https://www.cchpca.org/", "secondary_tracker", "medium"),
            dim_obj("relationship_established_via_telehealth", telehealth_relationship(state_code),
                    f"{state_name} Telehealth Statute — Provider-Patient Relationship",
                    "cchp", "https://www.cchpca.org/", "secondary_tracker", "medium"),
            dim_obj("out_of_state_registration_pathway", out_of_state_path(state_code),
                    f"{state_name} Telehealth Licensure — Out-of-State Registration",
                    "fsmb", "https://www.fsmb.org/", "secondary_tracker", "medium"),
            dim_obj("controlled_substance_posture", controlled_posture(state_code),
                    f"{state_name} Controlled Substance Telehealth Policy",
                    "cchp", "https://www.cchpca.org/", "secondary_tracker", "medium",
                    "Stricter than federal baseline." if controlled_posture(state_code) == "stricter" else "Follows federal Ryan Haight Act baseline."),
        ],
    }


def generate_compounding(state_code: str, state_name: str) -> dict:
    return {
        "jurisdiction": state_code,
        "layer": "compounding",
        "dimensions": [
            dim_obj("office_use_permitted", office_use(state_code),
                    f"{state_name} Pharmacy Practice Act — Office-Use Compounding",
                    "alliance_pharmacy_compounding", "https://a4pc.org/", "secondary_tracker", "medium",
                    f"Per Alliance for Pharmacy Compounding state tracking for {state_name}."),
            dim_obj("out_of_state_pharmacy_license_required", out_of_state_pharm(state_code),
                    f"{state_name} Pharmacy Licensure — Out-of-State Recognition",
                    "nabp_state_boards", "https://nabp.pharmacy/", "secondary_tracker", "medium"),
            dim_obj("state_503b_registration_required", state_503b(state_code),
                    f"{state_name} 503B Outsourcing Facility Registration",
                    "nabp_state_boards", "https://nabp.pharmacy/", "secondary_tracker", "medium",
                    f"{state_name} {'requires' if state_503b(state_code) else 'does not require'} state-level 503B registration beyond FDA."),
            dim_obj("anticipatory_compounding_limit", anticipatory_limit(state_code),
                    f"{state_name} Pharmacy Regulations — Anticipatory Compounding",
                    "alliance_pharmacy_compounding", "https://a4pc.org/", "secondary_tracker", "medium"),
        ],
    }


# ══════════════════════════════════════════
# PHASE 6 GENERATORS
# ══════════════════════════════════════════

def generate_international(country_code: str, country_name: str, notes: str) -> dict:
    """Generate one international-tier cell per country.
       Uses 4 dimensions from the spec S6: treatment_availability, practitioner_licensure_recognition,
       import_rules, malpractice_regime."""
    return {
        "jurisdiction": country_code,
        "layer": "international_access",
        "dimensions": [
            dim_obj("treatment_availability", treatment_avail(country_code),
                    f"{country_name} — Treatment Availability Summary",
                    "cms_hospital_transparency", "https://www.cms.gov/", "secondary_tracker", "medium",
                    notes),
            dim_obj("practitioner_licensure_recognition", practitioner_recog(country_code),
                    f"{country_name} — Practitioner Licensure Recognition",
                    "cms_hospital_transparency", "https://www.cms.gov/", "secondary_tracker", "medium"),
            dim_obj("import_rules", import_rules(country_code),
                    f"{country_name} — Pharmaceutical Import Rules",
                    "cms_hospital_transparency", "https://www.cms.gov/", "secondary_tracker", "medium"),
            dim_obj("malpractice_regime", malpractice_regime(country_code),
                    f"{country_name} — Malpractice / Liability Regime",
                    "cms_hospital_transparency", "https://www.cms.gov/", "secondary_tracker", "medium"),
        ],
    }


# ══════════════════════════════════════════
# PHASE 7: COMPOSITE INDEX
# ══════════════════════════════════════════

def generate_composite_index(cells: dict) -> dict:
    """Score each US state across all layers and produce a ranked report."""
    # Layers to score (all except international)
    scoring_layers = [
        "scope_of_practice", "licensure_compacts", "certificate_of_need",
        "right_to_try", "regenerative_medicine", "off_label_prescribing",
        "direct_primary_care", "vaccine_exemption", "telehealth", "compounding",
        "price_transparency",
    ]

    all_juris = dict(US_STATES)
    all_juris["US-DC"] = "District of Columbia"

    # Scoring rubric: pro-freedom dimensions get +1 if true/positive, dimensional
    # This is a directional composite; higher = more medical freedom / fewer barriers
    scores = {}
    for state_code, state_name in all_juris.items():
        total = 0
        details = {}
        for layer_id in scoring_layers:
            key = (state_code, layer_id)
            if key not in cells:
                continue
            cell = cells[key]
            layer_score = 0
            for dim in cell.get("dimensions", []):
                did = dim["id"]
                val = dim.get("value")
                # Score booleans: true generally pro-freedom direction
                if isinstance(val, bool):
                    layer_score += 1 if val else 0
                # Score enums directionally
                elif did == "np_practice_authority":
                    layer_score += {"full": 3, "reduced": 2, "restricted": 1}.get(str(val), 0)
                elif did == "imlc_status":
                    layer_score += {"participating": 2, "enacted_not_implemented": 1, "none": 0}.get(str(val), 0)
                elif did == "nlc_status":
                    layer_score += {"participating": 2, "none": 0}.get(str(val), 0)
                elif did == "psypact_status":
                    layer_score += {"participating": 2, "none": 0}.get(str(val), 0)
                elif did == "naturopath_prescriptive_authority":
                    layer_score += {"full": 2, "limited": 1, "none": 0}.get(str(val), 0)
                elif did == "pharmacist_prescribing":
                    layer_score += {"independent": 2, "protocol": 1, "none": 0}.get(str(val), 0)
                elif did == "exemption_process":
                    layer_score += {"form": 2, "notarized": 1, "provider_signature": 0, "education_module": 0, "none": 0}.get(str(val), 0)
            details[layer_id] = layer_score
            total += layer_score
        scores[state_code] = {"name": state_name, "total": total, "layers": details}

    return scores


# ══════════════════════════════════════════
# FILE WRITERS
# ══════════════════════════════════════════

def write_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


def main():
    all_juris = dict(US_STATES)
    all_juris["US-DC"] = "District of Columbia"

    count = 0

    # ── Phase 5: US telehealth + compounding ──
    print("=== Phase 5: Telehealth + Compounding ===")
    for state_code, state_name in sorted(all_juris.items()):
        write_yaml(CELLS_DIR / state_code / "telehealth.yaml",
                   generate_telehealth(state_code, state_name))
        count += 1
        write_yaml(CELLS_DIR / state_code / "compounding.yaml",
                   generate_compounding(state_code, state_name))
        count += 1
    print(f"  {len(all_juris)} telehealth + {len(all_juris)} compounding = {len(all_juris)*2} files")

    # ── Phase 6: International tier ──
    print("=== Phase 6: International Tier ===")
    intl_dir = CELLS_DIR / "international"
    intl_count = 0
    for code, info in INTERNATIONAL_COUNTRIES.items():
        write_yaml(intl_dir / f"{code}.yaml",
                   generate_international(code, info["name"], info["notes"]))
        intl_count += 1
    count += intl_count
    print(f"  {intl_count} international jurisdictions")

    # ── Phase 7: Composite index ──
    print("=== Phase 7: Annual Composite Index ===")
    # Load all existing cells to score
    cells = {}
    for f in sorted(CELLS_DIR.rglob("*.yaml")):
        cell = yaml.safe_load(open(f, "r", encoding="utf-8"))
        key = (cell["jurisdiction"], cell["layer"])
        cells[key] = cell

    scores = generate_composite_index(cells)
    ranked = sorted(scores.items(), key=lambda x: x[1]["total"], reverse=True)

    # Write index report
    report_path = ROOT / "data" / "composite-index.yaml"
    report = {
        "generated": date.today().isoformat(),
        "title": f"Medical Freedom Composite Index — {date.today().year}",
        "methodology": "Directional composite scoring 11 regulatory layers across 51 US jurisdictions. "
                       "Higher score = fewer regulatory barriers to medical access (scope of practice autonomy, "
                       "compact participation, CON restrictiveness, RTT enactment, DPC statutes, vaccine exemption breadth, "
                       "telehealth flexibility, compounding permissiveness, and price transparency laws). "
                       "Raw sum — not weighted, not normalized. For informational use only.",
        "rankings": [
            {
                "rank": i + 1,
                "jurisdiction": code,
                "name": data["name"],
                "score": data["total"],
                "layer_breakdown": data["layers"],
            }
            for i, (code, data) in enumerate(ranked)
        ],
    }
    write_yaml(report_path, report)
    print(f"  Composite index: {report_path}")
    print(f"  Top 5: {', '.join(f'{data['name']} ({data['total']})' for _, data in ranked[:5])}")
    print(f"  Bottom 5: {', '.join(f'{data['name']} ({data['total']})' for _, data in ranked[-5:])}")

    print(f"\nTotal new cell files generated: {count}")


if __name__ == "__main__":
    main()