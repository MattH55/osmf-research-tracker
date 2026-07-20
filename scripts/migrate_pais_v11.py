#!/usr/bin/env python3
"""One-time, idempotent migration adding v1.1 fields to existing cohort records.

Adds symptom_inventory_scope, n_symptoms_queried, symptom_instrument_note,
related_cohorts, last_verified, verified_by, and an empty symptom_findings array
where missing. Safe to re-run: only fills fields that are absent.
"""
import json, glob, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFIED_DATE = "2026-07-20"
VERIFIED_BY = "OSMF research-tracker (web-verified against source)"

SCOPE = {
    "davis-2021-longcovid": "comprehensive_inventory",
    "dubbo-infection-outcomes": "targeted_panel",
    "colombo-dengue": "single_domain",
    "bergen-giardiasis-2004": "targeted_panel",
    "prevail-iii-ebola": "targeted_panel",
    "sejvar-wnv-neuroinvasive": "targeted_panel",
    "mylonas-rrv-polyarthritis": "targeted_panel",
    "moldofsky-post-sars": "single_domain",
    "cao-lormeau-zika-gbs": "single_domain",
    "telechik-reunion": "targeted_panel",
    "katz-2009-mononucleosis": "single_domain",
    "white-1998-glandular-fever": "single_domain",
    "huang-2021-wuhan": "targeted_panel",
    "phosp-covid": "targeted_panel",
    "blomberg-2021-bergen-covid": "targeted_panel",
    "lam-2009-sars-survivors": "targeted_panel",
    "schilte-2013-chikungunya-reunion": "targeted_panel",
    "aucott-slice-ptlds": "targeted_panel",
    "morroy-netherlands-qfever": "targeted_panel",
    "nohynek-2012-pandemrix-narcolepsy": "none",
    "walkerton-health-study": "single_domain",
}
N_SYMPTOMS = {"davis-2021-longcovid": 203}
RELATED = {
    "telechik-reunion": [
        {"id": "schilte-2013-chikungunya-reunion", "relation": "sibling_analysis"},
        {"id": "marimoutou-2012-gendarmes", "relation": "sibling_analysis"},
    ],
    "schilte-2013-chikungunya-reunion": [
        {"id": "telechik-reunion", "relation": "sibling_analysis"},
        {"id": "marimoutou-2012-gendarmes", "relation": "sibling_analysis"},
    ],
}


def main():
    changed = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "cohorts", "*.json"))):
        with open(f, encoding="utf-8") as fh:
            d = json.load(fh)
        cid = d["id"]
        before = json.dumps(d, sort_keys=True)
        d.setdefault("symptom_inventory_scope", SCOPE.get(cid, "targeted_panel"))
        d.setdefault("n_symptoms_queried", N_SYMPTOMS.get(cid))
        d.setdefault("symptom_instrument_note", None)
        d.setdefault("related_cohorts", RELATED.get(cid, []))
        d.setdefault("last_verified", VERIFIED_DATE)
        d.setdefault("verified_by", VERIFIED_BY)
        d.setdefault("symptom_findings", [])
        if json.dumps(d, sort_keys=True) != before:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(d, fh, ensure_ascii=False, indent=2)
                fh.write("\n")
            changed += 1
            print("migrated", cid)
    print(f"Done. {changed} file(s) updated.")


if __name__ == "__main__":
    main()
