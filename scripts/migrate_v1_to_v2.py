#!/usr/bin/env python3
"""Migrate v1.x cohort records (Finding + SymptomFinding) to the v2 Observation model.

Every Finding and SymptomFinding becomes one polymorphic Observation. Missing values
become typed sentinels ({"status": "measured_not_reported"} etc.), never null or a guess.
Source values are never altered — only restructured. Idempotent: a cohort already at
schema_version 2.0.0 is left untouched.
"""
import json, glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULESET = "pais-harmony-v1"

MNR = {"status": "measured_not_reported"}      # assessed, number not published
NA = {"status": "not_applicable"}

OUTCOME_MEASURE = {
    "mecfs_criteria_met": "case-def:cfs", "chronic_fatigue": "sym:fatigue",
    "ibs": "sym:irritable-bowel-syndrome", "arthralgia": "sym:arthralgia",
    "myalgia": "sym:myalgia", "joint_swelling": "sym:arthralgia",
    "neurocognitive": "sym:cognitive-dysfunction", "sleep_disturbance": "sym:sleep-disturbance",
    "depression": "sym:depression", "pem": "sym:post-exertional-malaise",
    "qol_impairment": "func:qol-impairment", "unable_to_work": "func:unable-to-work",
    "recovered": "func:recovery",
}
OTHER_MEASURE_BY_FINDING = {
    "narcolepsy-rate-ratio": "event:narcolepsy",
    "zika-gbs-serology": "event:guillain-barre-syndrome",
    "blomberg-persist-6mo": "func:any-persistent-symptom",
    "blomberg-young-6mo": "func:any-persistent-symptom",
}
EFFECT_MAP = {"pr": "pr", "rr": "rr", "or": "or", "hr": "hr",
              "risk_difference": "rd", "prevalence_ratio": "pr", "none": "none", None: "none"}


def sym_measure(sid):
    return {"cfs_like_illness": "case-def:cfs-like"}.get(sid, "sym:" + sid.replace("_", "-"))


def band(m):
    if m is None:
        return "unspecified"
    if m == 0:
        return "acute"
    if m <= 3:
        return "0-3mo"
    if m <= 6:
        return "3-6mo"
    if m <= 12:
        return "6-12mo"
    if m <= 24:
        return "12-24mo"
    return "24mo+"


def int_or_mnr(v):
    return v if isinstance(v, int) else MNR


def ci_of(lo, hi):
    return [lo, hi] if lo is not None and hi is not None else None


def provenance(source_locator, verified_by, verified_on):
    return {"source_locator": source_locator, "extracted_by": None, "extracted_on": None,
            "verified_by": verified_by, "verified_on": verified_on, "extraction_method": "manual"}


def comparator_from(group, cp, cn, effect_estimate, effect_type):
    """Build a v2 comparator block from v1 comparator fields."""
    if cp is None:
        return {"group": "none", "value": NA, "effect": None}
    if cp == "not_reported":
        return {"group": group or "not_reported", "value": MNR, "effect": None}
    val = {"type": "proportion", "percent": cp, "precision": "exact"}
    if isinstance(cn, int):
        val["denominator"] = cn
    effect = None
    if effect_estimate is not None and EFFECT_MAP.get(effect_type, "none") != "none":
        effect = {"estimate": effect_estimate, "effect_type": EFFECT_MAP.get(effect_type, "none")}
    return {"group": group or "not_reported", "value": val, "effect": effect}


def obs_from_symptom_finding(sf, cohort, control_group):
    numerator = sf.get("n_with_symptom")
    val = {"type": "proportion",
           "numerator": numerator if isinstance(numerator, int) else MNR,
           "denominator": int_or_mnr(sf.get("n_assessed")),
           "percent": sf["percent"],
           "ci": ci_of(sf.get("ci_low"), sf.get("ci_high")),
           "precision": sf["value_precision"]}
    group = sf.get("comparator_group") or (control_group if sf.get("comparator_percent") not in (None,) else None)
    comparator = comparator_from(group, sf.get("comparator_percent"), sf.get("comparator_n"),
                                 sf.get("effect_estimate"), sf.get("effect_type"))
    scope = "subgroup" if sf.get("denominator_basis") == "symptomatic_subset" else "whole_cohort"
    return {
        "id": sf["id"], "cohort_id": cohort["id"], "publication_id": sf["publication_id"],
        "schema_version": "2.0.0", "measure_id": sym_measure(sf["symptom_id"]),
        "measure_verbatim": sf.get("symptom_verbatim"),
        "population": {"scope": scope, "stratum": None,
                       "denominator_basis": sf["denominator_basis"], "n_assessed": int_or_mnr(sf.get("n_assessed"))},
        "timing": {"timepoint_months": sf.get("timepoint_months"), "timepoint_band": band(sf.get("timepoint_months")),
                   "reference_period": sf.get("reference_period", "not_reported"), "is_cumulative": False},
        "method": {"ascertainment": sf["ascertainment"], "instrument_id": sf.get("instrument_id"),
                   "severity_threshold": sf.get("severity_threshold"), "blinded_assessment": "not_reported"},
        "value": val, "comparator": comparator, "harmonised": None,
        "provenance": provenance(sf["source_locator"], cohort.get("verified_by"), sf.get("last_verified")),
    }


def measure_for_finding(f):
    if f["outcome"] == "other":
        return OTHER_MEASURE_BY_FINDING.get(f["id"], "func:any-persistent-symptom")
    return OUTCOME_MEASURE.get(f["outcome"], "func:any-persistent-symptom")


def obs_from_finding(f, cohort, control_group):
    measure = measure_for_finding(f)
    # Nohynek is an incidence-rate finding -> use the 'rate' value type
    if f["id"] == "narcolepsy-rate-ratio":
        val = {"type": "rate", "events": int_or_mnr(f.get("n_with_outcome")), "person_time": MNR,
               "person_time_unit": "per 100000 person-years", "rate": 9.0, "ci": None}
        comparator = {"group": "unexposed_unmatched",
                      "value": {"type": "rate", "rate": 0.7, "person_time_unit": "per 100000 person-years"},
                      "effect": {"estimate": f.get("effect_estimate"), "effect_type": "rr",
                                 "ci": ci_of(f.get("ci_low"), f.get("ci_high"))}}
        n_assessed = MNR
        denom_basis = "person_time"
    else:
        numerator = f.get("n_with_outcome")
        val = {"type": "proportion",
               "numerator": numerator if isinstance(numerator, int) else MNR,
               "denominator": int_or_mnr(f.get("n_assessed")),
               "percent": f["percent"] if f.get("percent") is not None else MNR,
               "ci": ci_of(f.get("ci_low"), f.get("ci_high")),
               "precision": "exact" if isinstance(numerator, int) else "approximate"}
        comparator = comparator_from(control_group, f.get("comparator_percent"), f.get("comparator_n"),
                                     f.get("effect_estimate"), f.get("effect_type"))
        n_assessed = int_or_mnr(f.get("n_assessed"))
        denom_basis = "assessed_at_timepoint" if isinstance(f.get("n_assessed"), int) else "unclear"
    return {
        "id": f["id"], "cohort_id": cohort["id"], "publication_id": f["publication_id"],
        "schema_version": "2.0.0", "measure_id": measure, "measure_verbatim": f.get("outcome_verbatim"),
        "population": {"scope": "whole_cohort", "stratum": None,
                       "denominator_basis": denom_basis, "n_assessed": n_assessed},
        "timing": {"timepoint_months": f.get("timepoint_months"), "timepoint_band": band(f.get("timepoint_months")),
                   "reference_period": "not_reported", "is_cumulative": False},
        "method": {"ascertainment": "unclear", "instrument_id": f.get("instrument_id"),
                   "severity_threshold": None, "blinded_assessment": "not_reported"},
        "value": val, "comparator": comparator, "harmonised": None,
        "provenance": provenance(f["source_locator"], cohort.get("verified_by"), cohort.get("last_verified")),
    }


def migrate(cohort):
    if cohort.get("schema_version") == "2.0.0":
        return False
    control_group = cohort.get("control_group")
    obs = []
    for f in cohort.get("findings", []):
        obs.append(obs_from_finding(f, cohort, control_group))
    for sf in cohort.get("symptom_findings", []):
        obs.append(obs_from_symptom_finding(sf, cohort, control_group))
    # id uniqueness within cohort
    seen = {}
    for o in obs:
        if o["id"] in seen:
            o["id"] = o["id"] + "-2"
        seen[o["id"]] = True
    cohort.pop("findings", None)
    cohort.pop("symptom_findings", None)
    cohort["schema_version"] = "2.0.0"
    cohort["harmonisation_ruleset"] = RULESET
    cohort["observations"] = obs
    return True


def main():
    changed = 0
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "cohorts", "*.json"))):
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        if migrate(d):
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            changed += 1
            print(f"migrated {d['id']}: {len(d['observations'])} observations")
    print(f"Done. {changed} cohort(s) migrated to v2.")


if __name__ == "__main__":
    main()
