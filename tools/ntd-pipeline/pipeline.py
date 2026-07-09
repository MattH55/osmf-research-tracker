#!/usr/bin/env python3
"""
pipeline.py
-----------
Orchestrates the NTD intelligence workflow and emits a ranked table.

STAGES
  1. Seed        : 21 WHO NTDs from ntd_registry.NTD_LIST
  2. Burden      : deaths + DALYs (GBD export or indicative seed)  -> ranking key
  3. Resolve     : NTD name -> EFO/MONDO id (Open Targets search)
  4. Therapeutics: knownDrugs (top drugs) + associatedTargets (top targets)
  5. Post-acute  : curated POST_ACUTE table + live ClinicalTrials.gov signal
  6. Rank/Output : sort by DALYs (then deaths); write CSV + JSON

USAGE
  python pipeline.py                      # live APIs, indicative burden
  python pipeline.py --burden-csv gbd.csv # live APIs, authoritative burden
  python pipeline.py --mock               # no network - canned demo data
  python pipeline.py --top 10 --drugs 8 --targets 8

Live mode needs network access to api.platform.opentargets.org and clinicaltrials.gov.
"""

from __future__ import annotations
import argparse
import csv
import json
import sys
import time

import ntd_registry as reg
import burden as burden_mod
import therapeutics as ther

# ---- optional live connectors (only imported when not --mock) ----------------
def _live():
    import opentargets as ot
    import clinicaltrials as ct
    return ot, ct


# ---- mock providers so the pipeline runs with zero network -------------------
_MOCK_DRUGS = {
    "chagas": [
        {"drug": "BENZNIDAZOLE", "approved": True, "max_phase": 4, "moa": "Nitroreductase-activated trypanocide", "target": "TcNTR"},
        {"drug": "NIFURTIMOX", "approved": True, "max_phase": 4, "moa": "Nitrofuran trypanocide", "target": "TcNTR"},
        {"drug": "FEXINIDAZOLE", "approved": False, "max_phase": 2, "moa": "Nitroimidazole", "target": "-"},
    ],
    "leishmaniasis": [
        {"drug": "AMPHOTERICIN B", "approved": True, "max_phase": 4, "moa": "Ergosterol binder", "target": "-"},
        {"drug": "MILTEFOSINE", "approved": True, "max_phase": 4, "moa": "Phospholipid analog", "target": "-"},
        {"drug": "PAROMOMYCIN", "approved": True, "max_phase": 4, "moa": "Aminoglycoside", "target": "16S rRNA"},
    ],
    "dengue": [
        {"drug": "DENGUE TETRAVALENT VACCINE", "approved": True, "max_phase": 4, "moa": "Live attenuated vaccine", "target": "-"},
    ],
}
_MOCK_TARGETS = {
    "chagas": [{"symbol": "CYP51", "name": "sterol 14-alpha demethylase", "score": 0.71},
               {"symbol": "CRUZIPAIN", "name": "cysteine protease", "score": 0.64}],
    "leishmaniasis": [{"symbol": "LDH", "name": "dihydrofolate reductase", "score": 0.58}],
}


def resolve_id(ntd, ot, mock):
    if mock:
        return ntd.efo_hint or f"MOCK_{ntd.key}"
    rid = ot.resolve_disease(ntd.search_terms[0]) or ntd.efo_hint
    return rid


def merge_drugs(ntd_key: str, ot_drugs: list[dict], n_pipeline: int = 6) -> list[dict]:
    """All curated SOC agents; then up to n_pipeline Open Targets phase 2+ candidates."""
    soc = ther.get_soc(ntd_key)
    seen = {ther.normalize_name(d["drug"]) for d in soc}
    merged = list(soc)
    added = 0
    for d in ot_drugs:
        name = ther.normalize_name(d.get("drug", ""))
        if not name or name in seen:
            continue
        phase = d.get("max_phase") or 0
        if phase < 2 and not d.get("approved"):
            continue
        entry = dict(d)
        entry["source"] = "Open Targets (clinical pipeline)"
        merged.append(entry)
        seen.add(name)
        added += 1
        if added >= n_pipeline:
            break
    return merged


def get_drugs(ntd, efo, ot, mock, n):
    if mock:
        return merge_drugs(ntd.key, _MOCK_DRUGS.get(ntd.key, []), n_pipeline=n)
    ot_drugs = ot.known_drugs(efo, size=50) if efo else []
    return merge_drugs(ntd.key, ot_drugs, n_pipeline=n)


def get_targets(ntd, efo, ot, mock, n):
    if mock:
        return _MOCK_TARGETS.get(ntd.key, [])[:n]
    if not efo:
        return []
    return ot.associated_targets(efo, n=n)


def get_ct_signal(ntd, pa, ct, mock):
    if mock:
        return {"trials_total": 123, "trials_post_acute": 21, "post_acute_share": 0.171}
    terms = [pa.syndrome.split()[0]] if pa.has else []
    return ct.post_acute_signal(ntd.search_terms[0], terms)


def build_rows(args):
    mock = args.mock
    ot = ct = None
    if not mock:
        ot, ct = _live()

    burden = burden_mod.load_burden(args.burden_csv)
    seed_flag = burden.get("_meta", {}).get("is_seed", True)

    rows = []
    for ntd in reg.NTD_LIST:
        b = burden_mod.get(burden, ntd.key)
        pa = reg.get_post_acute(ntd.key)

        efo = resolve_id(ntd, ot, mock)
        drugs = get_drugs(ntd, efo, ot, mock, args.drugs)
        targets = get_targets(ntd, efo, ot, mock, args.targets)
        ct_sig = get_ct_signal(ntd, pa, ct, mock) if args.trials else {}

        rows.append({
            "key": ntd.key,
            "disease": ntd.name,
            "pathogen": ntd.pathogen,
            "efo_id": efo,
            "deaths_per_year": b["deaths"],
            "dalys_per_year": b["dalys"],
            "burden_confidence": b["confidence"],
            "top_drugs": [d.get("drug") for d in drugs],
            "top_drug_detail": drugs,
            "top_targets": [t.get("symbol") for t in targets],
            "top_target_detail": targets,
            "has_post_acute": pa.has,
            "post_acute_kind": pa.kind,          # PAIS | chronic | sequela | none
            "post_acute_syndrome": pa.syndrome,
            "post_acute_onset": pa.onset,
            "post_acute_source": pa.source,
            "ct_signal": ct_sig,
            "note": ntd.note,
        })
        if not mock:
            time.sleep(args.sleep)  # be polite to the APIs

    # ---- rank: DALYs desc, then deaths desc; None sinks to the bottom --------
    def sortkey(r):
        return (r["dalys_per_year"] or -1, r["deaths_per_year"] or -1)
    rows.sort(key=sortkey, reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows, seed_flag


def write_outputs(rows, prefix):
    # JSON (full detail)
    with open(f"{prefix}.json", "w") as f:
        json.dump(rows, f, indent=2)
    # CSV (flat, publication-friendly)
    cols = ["rank", "disease", "pathogen", "efo_id", "deaths_per_year", "dalys_per_year",
            "burden_confidence", "has_post_acute", "post_acute_kind", "post_acute_syndrome",
            "post_acute_onset", "post_acute_source"]
    with open(f"{prefix}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols + ["top_drugs", "top_targets", "ct_trials_total", "ct_trials_post_acute"])
        for r in rows:
            w.writerow([r[c] for c in cols] + [
                "; ".join([d for d in r["top_drugs"] if d]),
                "; ".join([t for t in r["top_targets"] if t]),
                (r.get("ct_signal") or {}).get("trials_total", ""),
                (r.get("ct_signal") or {}).get("trials_post_acute", ""),
            ])


def print_table(rows, top):
    print(f"\n{'#':>2}  {'Disease':38} {'Deaths/yr':>10} {'DALYs/yr':>11}  PA   Top drug")
    print("-" * 100)
    for r in rows[:top]:
        pa = {"PAIS": "PAIS", "chronic": "chrn", "sequela": "seq", "none": " - "}[r["post_acute_kind"]]
        d = r["deaths_per_year"]; da = r["dalys_per_year"]
        drug = (r["top_drugs"][0] if r["top_drugs"] else "-")
        print(f"{r['rank']:>2}  {r['disease'][:38]:38} "
              f"{('' if d is None else f'{int(d):,}'):>10} "
              f"{('' if da is None else f'{int(da):,}'):>11}  {pa:4} {str(drug)[:28]}")


def main():
    ap = argparse.ArgumentParser(description="NTD burden + therapeutics + post-acute pipeline")
    ap.add_argument("--mock", action="store_true", help="run with canned data, no network")
    ap.add_argument("--burden-csv", default=None, help="authoritative GBD export CSV")
    ap.add_argument("--drugs", type=int, default=6, help="top-N drugs per disease")
    ap.add_argument("--targets", type=int, default=6, help="top-N targets per disease")
    ap.add_argument("--no-trials", dest="trials", action="store_false", help="skip ClinicalTrials.gov calls")
    ap.add_argument("--top", type=int, default=21, help="rows to print")
    ap.add_argument("--sleep", type=float, default=0.34, help="delay between diseases (live mode)")
    ap.add_argument("--out", default="ntd_intelligence", help="output file prefix")
    args = ap.parse_args()

    mode = "MOCK (no network)" if args.mock else "LIVE"
    print(f"NTD pipeline - {mode} - 21 WHO NTD groups "
          f"({len(reg.NTD_LIST)} rows; dengue & chikungunya split)")
    rows, seed_flag = build_rows(args)
    write_outputs(rows, args.out)
    print_table(rows, args.top)
    if seed_flag:
        print("\n[!] Burden = INDICATIVE seed. Replace with a GBD export via --burden-csv "
              "before publishing (see burden.py).")
    print(f"\nWrote {args.out}.csv and {args.out}.json")


if __name__ == "__main__":
    sys.exit(main())
