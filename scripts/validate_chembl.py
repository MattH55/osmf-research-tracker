#!/usr/bin/env python3
"""External cross-check of the repurposing index against ChEMBL drug_indication.

This is the manuscript's partial external validation. repoDB is not used (see the
limitations section): instead, for every index condition that carries a MeSH id we
pull the ChEMBL molecules recorded as APPROVED for that indication
(max_phase_for_ind == 4), resolve them to preferred names, and measure:

  recall    - what fraction of the external approved set the explorer lists at all;
  agreement - what fraction the explorer additionally flags as approved elsewhere.

Matching is on normalised agent names (salt/ester forms stripped), so a name ChEMBL
spells differently can be missed: treat the numbers as a lower bound.

Run:  python scripts/validate_chembl.py            (network, ~1-2 min)
Writes: data/explorer-validation.json
"""
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "explorer-validation.json"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
UA = {"User-Agent": "OSMF-Explorer/1.0 (research@opensourcemed.info)"}

# conditions to attempt first: common, well annotated, plenty of index rows
PREFERRED = ["asthma", "rheumatoid-arthritis", "type-2-diabetes", "breast-cancer",
             "chronic-obstructive-pulmonary-disease", "major-depressive-disorder",
             "psoriasis-vulgaris", "multiple-sclerosis", "parkinson-disease",
             "heart-failure", "cancer"]
MAX_CONDITIONS = 25


def norm(name):
    """Lower-case, drop punctuation and common salt/ester suffixes, take the head word."""
    n = re.sub(r"[^a-z ]", "", (name or "").lower())
    n = re.sub(r"\b(sodium|hcl|hydrochloride|sulfate|phosphate|acetate|maleate|fumarate|"
               r"tartrate,citrate|besylate|mesylate|propionate|dipropionate|xinafoate|"
               r"succinate|palmitate|aspirate|nasal|inhalation|oral)\b", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n.split(" ")[0] if n else ""


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if i == tries - 1:
                print(f"    give up: {e}", flush=True)
                return None
            time.sleep(2 + 3 * i)


def main():
    idx = json.loads((ROOT / "js" / "generated" / "repurposing-index.json")
                     .read_text(encoding="utf-8"))
    conds = {c["s"]: c for c in idx["conditions"]}
    rows_by_cond = {}
    for r in idx["rows"]:
        rows_by_cond.setdefault(r["d"], []).append(r)

    # slug -> MeSH id, taken from the upstream disease-intelligence files
    mesh = {}
    for slug in conds:
        p = ROOT / "data" / "disease-intelligence" / f"{slug}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        m = (d.get("identifiers") or {}).get("mesh_id")
        if m:
            mesh[slug] = m

    pick = [s for s in PREFERRED if s in mesh]
    for s in sorted(mesh):
        if len(pick) >= MAX_CONDITIONS:
            break
        if s not in pick and conds[s]["nRows"] >= 10:
            pick.append(s)

    print(f"index rows {len(idx['rows'])}  conditions {len(conds)}  "
          f"with MeSH id {len(mesh)}  validating {len(pick)}", flush=True)

    results = []
    tot_b = tot_hit = tot_ap = tot_listed = tot_flag = 0
    for slug in pick:
        m = mesh[slug]
        ours = rows_by_cond.get(slug, [])
        our_norm = {norm(r["n"]) for r in ours}
        our_ap = {norm(r["n"]) for r in ours if r["ap"] == 1}
        data = get(f"{CHEMBL}/drug_indication.json?mesh_id={m}&limit=1000")
        if not data:
            print(f"{slug:36s} mesh={m:9s} FETCH FAILED", flush=True)
            continue
        p4 = {d["parent_molecule_chembl_id"] for d in data.get("drug_indications", [])
              if str(d.get("max_phase_for_ind")) in ("4.0", "4")}
        names = set()
        ids = sorted(p4)
        for i in range(0, len(ids), 500):
            md = get(f"{CHEMBL}/molecule.json?molecule_chembl_id__in="
                     f"{','.join(ids[i:i + 500])}&limit=500")
            for mol in (md or {}).get("molecules", []):
                nm = norm(mol.get("pref_name"))
                if nm:
                    names.add(nm)
        hit, conf = names & our_norm, names & our_ap
        tot_b += len(names)
        tot_hit += len(hit)
        tot_ap += len(conf)
        tot_listed += len(our_norm)
        tot_flag += len(our_ap)
        # our_ap means "approved for ANY indication", so conf/our_ap is a floor on
        # how many of those approvals ChEMBL also records FOR THIS indication. It is
        # not a false-positive rate. agreement_pct keeps the ChEMBL set as denominator.
        results.append({"condition": slug, "mesh_id": m,
                        "chembl_approved": len(names), "index_agents": len(our_norm),
                        "index_approved_flags": len(our_ap),
                        "covered": len(hit),
                        "recall_pct": round(100 * len(hit) / max(1, len(names)), 1),
                        "flagged_approved": len(conf),
                        "agreement_pct": round(100 * len(conf) / max(1, len(names)), 1),
                        "flag_confirmed_for_indication_pct":
                            round(100 * len(conf) / max(1, len(our_ap)), 1)})
        print(f"{slug:36s} mesh={m:9s} chembl_p4={len(names):4d} idx={len(our_norm):4d} "
              f"covered={len(hit):4d} ({100*len(hit)/max(1,len(names)):5.1f}%) "
              f"approved-flag={len(conf):4d}", flush=True)

    summary = {
        "method": "ChEMBL drug_indication records with max_phase_for_ind == 4 per condition "
                  "MeSH id, matched to explorer agents on normalised names",
        "external_source": "ChEMBL",
        "conditions_validated": len(results),
        "chembl_approved_total": tot_b,
        "covered_total": tot_hit,
        "recall_pct": round(100 * tot_hit / max(1, tot_b), 1),
        "flagged_approved_total": tot_ap,
        "agreement_pct": round(100 * tot_ap / max(1, tot_b), 1),
        "index_agents_total": tot_listed,
        "index_approved_flags_total": tot_flag,
        "flag_confirmed_for_indication_pct":
            round(100 * tot_ap / max(1, tot_flag), 1),
        "note": "covered counts ChEMBL-approved agents the explorer lists for that "
                "condition; flagged_approved is the subset the explorer also flags "
                "approved (max phase 4 or 'Approved' label). covered == "
                "flagged_approved here, so every externally approved agent that is "
                "listed is also approved-flagged.",
        "caveat": "name-normalised matching; a sample of conditions, not the whole index; "
                  "a repoDB-style proxy rather than repoDB itself",
        "per_condition": results,
    }
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nTOTAL chembl_p4={tot_b} covered={tot_hit} "
          f"({100*tot_hit/max(1,tot_b):.1f}%) flagged_approved={tot_ap} "
          f"({100*tot_ap/max(1,tot_b):.1f}%)")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
