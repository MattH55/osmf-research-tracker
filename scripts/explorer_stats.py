#!/usr/bin/env python3
"""
Reproducible coverage / distribution statistics for the Drug Repurposing Explorer
manuscript. Recomputes every number quoted in the manuscript from the live
generated index and the shared data layer, so the manuscript can be re-fact-checked
against the code at any time.

Run from the research-tracker directory:
    python scripts/explorer_stats.py
Writes data/explorer-stats.json and prints manuscript-ready tables.
"""
import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.lib.repurposing_data import build_records  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "js" / "generated" / "repurposing-index.json"
OUT = ROOT / "data" / "explorer-stats.json"


def pct(n, d):
    return round(100 * n / d, 1) if d else 0.0


def main():
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    rows, conds = idx["rows"], idx["conditions"]
    cond_by_slug = {c["s"]: c for c in conds}
    _, recs = build_records()

    s = {"generated_index_date": idx["generated"], "computed_on": date.today().isoformat(),
         "index_file_kb": round(INDEX.stat().st_size / 1024, 1)}

    # ---- coverage -----------------------------------------------------------
    s["n_conditions"] = len(conds)
    s["n_pairs"] = len(rows)
    s["n_unique_agents"] = len({r["a"] for r in rows})
    s["n_conditions_zero_rows"] = sum(1 for c in conds if c["nRows"] == 0)
    s["track_counts"] = dict(Counter(c["track"] for c in conds))
    s["category_counts"] = dict(Counter(c["cat"] for c in conds))
    s["rows_per_cond"] = {"min": min(c["nRows"] for c in conds),
                          "median": statistics.median([c["nRows"] for c in conds]),
                          "max": max(c["nRows"] for c in conds)}

    # ---- evidence presence --------------------------------------------------
    with_trial = sum(1 for r in rows if r["tb"][0] > 0)
    with_lit = sum(1 for r in rows if r["lit"] > 0)
    both = sum(1 for r in rows if r["tb"][0] > 0 and r["lit"] > 0)
    s["pairs"] = {
        "with_trial": with_trial, "with_trial_pct": pct(with_trial, len(rows)),
        "with_literature": with_lit, "with_literature_pct": pct(with_lit, len(rows)),
        "with_both": both, "with_both_pct": pct(both, len(rows)),
        "trial_only": sum(1 for r in rows if r["tb"][0] and not r["lit"]),
        "literature_only": sum(1 for r in rows if r["lit"] and not r["tb"][0]),
        "with_phase3_4": sum(1 for r in rows if r["ph3"] > 0),
        "with_recruiting": sum(1 for r in rows if r["tb"][1] > 0),
    }

    # ---- distributions (pairs) ---------------------------------------------
    s["tier_distribution"] = dict(Counter(r["tier"] for r in rows))
    s["agent_type_distribution"] = dict(Counter(r["ty"] for r in rows))
    uniq = {r["a"]: r for r in rows}
    s["unique_agent_type_distribution"] = dict(Counter(r["ty"] for r in uniq.values()))
    s["source_track_distribution"] = dict(Counter(r["src"] for r in rows))
    s["approved_pairs"] = sum(r["ap"] for r in rows)
    s["approved_pct"] = pct(s["approved_pairs"], len(rows))
    s["phase_label_distribution"] = dict(Counter(r["ph"] for r in rows))
    s["agent_pages"] = sum(1 for r in rows if r["au"])
    s["pair_pages"] = sum(1 for r in rows if r["pu"])
    # ---- unique linked trials ----------------------------------------------
    trials = {}
    trial_slots = 0
    for r in recs:
        for t in r["trials"]:
            trial_slots += 1
            if t["nct_id"]:
                trials.setdefault(t["nct_id"], t)
    neg = sum(1 for t in trials.values()
              if t["status"] in ("TERMINATED", "WITHDRAWN", "SUSPENDED"))
    s["trials"] = {
        "unique_nct": len(trials), "pair_trial_slots": trial_slots,
        "mean_pairs_per_trial": round(trial_slots / len(trials), 2),
        "status": dict(Counter(t["status"] for t in trials.values())),
        "phase": dict(Counter(t["phase"] for t in trials.values())),
        "negative_outcome": neg, "negative_outcome_pct": pct(neg, len(trials)),
        "no_enrollment": sum(1 for t in trials.values() if not t["enrollment"]),
        "no_phase": sum(1 for t in trials.values() if not t["phase"] or t["phase"] == "NA"),
        "year_min": min((t["year"] for t in trials.values() if t["year"]), default=None),
        "year_max": max((t["year"] for t in trials.values() if t["year"]), default=None),
    }

    # ---- unique linked publications ----------------------------------------
    lit = {}
    lit_slots = 0
    for r in recs:
        for l in r["literature"]:
            lit_slots += 1
            if l["pmid"]:
                lit.setdefault(l["pmid"], l)
    no_year = sum(1 for l in lit.values() if not l["year"])
    s["literature"] = {
        "unique_pmid": len(lit), "pair_literature_slots": lit_slots,
        "type": dict(Counter(l["type"] for l in lit.values())),
        "year_min": min((l["year"] for l in lit.values() if l["year"]), default=None),
        "year_max": max((l["year"] for l in lit.values() if l["year"]), default=None),
        "no_year": no_year, "no_year_pct": pct(no_year, len(lit)),
        "with_doi": sum(1 for l in lit.values() if l["doi"]),
        "with_title": sum(1 for l in lit.values() if l["title"]),
        "no_title": sum(1 for l in lit.values() if not l["title"]),
    }

    # ---- score model --------------------------------------------------------
    sc = sorted(r["sc"] for r in rows)
    n = len(sc)
    s["score"] = {"min": sc[0], "max": sc[-1], "median": statistics.median(sc),
                  "mean": round(statistics.mean(sc), 1), "q1": sc[n // 4],
                  "q3": sc[3 * n // 4], "p90": sc[int(0.9 * n)],
                  "zero": sum(1 for x in sc if x == 0),
                  "ge40": sum(1 for x in sc if x >= 40),
                  "ge60": sum(1 for x in sc if x >= 60),
                  "max_at_cap": sum(1 for x in sc if x == 80), "bins": {}}
    for lo in range(0, 80, 10):
        hi = lo + 10
        s["score"]["bins"][f"{lo}-{hi}"] = sum(
            1 for x in sc if (lo <= x < hi) or (hi == 80 and x == 80))
    s["score"]["component_means"] = {
        k: round(statistics.mean(r["score_parts"][k] for r in recs), 2)
        for k in ("trials", "literature", "tier", "approved")}
    s["score"]["trial_cap_reached"] = sum(1 for r in recs if r["score_parts"]["trials"] >= 30)
    s["score"]["lit_cap_reached"] = sum(1 for r in recs if r["score_parts"]["literature"] >= 30)
    s["score"]["both_caps_reached"] = sum(
        1 for r in recs if r["score_parts"]["trials"] >= 30
        and r["score_parts"]["literature"] >= 30)
    # ---- category breakdown (Table 3) --------------------------------------
    cat = defaultdict(lambda: {"conditions": 0, "pairs": 0, "agents": set(),
                               "trial_slots": 0, "lit_slots": 0})
    for c in conds:
        cat[c["cat"]]["conditions"] += 1
    for r in rows:
        b = cat[cond_by_slug[r["d"]]["cat"]]
        b["pairs"] += 1
        b["agents"].add(r["a"])
        b["trial_slots"] += r["tb"][0]
        b["lit_slots"] += r["lit"]
    s["by_category"] = {k: {"conditions": v["conditions"], "pairs": v["pairs"],
                            "agents": len(v["agents"]), "trial_slots": v["trial_slots"],
                            "lit_slots": v["lit_slots"]}
                        for k, v in sorted(cat.items(), key=lambda kv: -kv[1]["pairs"])}

    # ---- per-agent reuse ----------------------------------------------------
    reuse = Counter(r["a"] for r in rows)
    s["agent_reuse"] = {"in_2plus": sum(1 for a, c in reuse.items() if c >= 2),
                        "in_5plus": sum(1 for a, c in reuse.items() if c >= 5),
                        "top": [{"agent": uniq[a]["n"], "conditions": c}
                                for a, c in reuse.most_common(10)]}

    # ---- top pairs ----------------------------------------------------------
    top = sorted(rows, key=lambda r: -r["sc"])
    s["top_pairs"] = [{"condition": cond_by_slug[r["d"]]["short"], "agent": r["n"],
                       "score": r["sc"], "tier": r["tier"], "parts": r["sp"]}
                      for r in top[:15]]

    # ---- index shape, funnel, per-row completeness --------------------------
    n_mech = sum(1 for r in rows if r["m"])
    n_ext = sum(1 for r in rows if r["ext"])
    n_either = sum(1 for r in rows if not r["pu"] and not r["au"])
    s["ui"] = {"index_keys": sorted(idx.keys()), "row_keys": sorted(rows[0].keys()),
               "score_max_in_ui": 80, "all_view_row_limit": 300,
               "tier_labels": idx["tier_labels"],
               "score_doc_lines": len(idx["score_doc"]),
               "csv_columns": 16,
               "filters": ["condition", "free-text", "tier", "agent type",
                           "recruiting-only", "approved-only"],
               "sortable_columns": 6, "url_hash_state": True}
    s["funnel"] = {"candidates_logged": sum(c.get("nCand", 0) for c in conds),
                   "pairs_in_index": len(rows),
                   "pct_of_candidates": pct(len(rows), sum(c.get("nCand", 0) for c in conds)),
                   "conditions_with_url": sum(1 for c in conds if c.get("url"))}
    s["completeness"] = {
        "mechanism": n_mech, "mechanism_pct": pct(n_mech, len(rows)),
        "external_links": n_ext, "external_links_pct": pct(n_ext, len(rows)),
        "external_link_labels": dict(Counter(e["l"] for r in rows for e in r["ext"])),
        "pair_page": s["pair_pages"], "agent_page": s["agent_pages"],
        "no_page_at_all": n_either,
        "literature_slots": lit_slots,
        "lit_no_doi": sum(1 for l in lit.values() if not l["doi"]),
        "lit_no_title": sum(1 for l in lit.values() if not l["title"]),
        "lit_no_year": s["literature"]["no_year"],
        "trials_no_enrollment": s["trials"]["no_enrollment"],
        "trials_no_phase": s["trials"]["no_phase"],
    }

    # ---- integrity checks ---------------------------------------------------
    s["integrity"] = {
        "pairs_with_zero_trial_and_zero_lit":
            sum(1 for r in rows if r["tb"][0] == 0 and r["lit"] == 0),
        "score_out_of_range": sum(1 for r in rows if not 0 <= r["sc"] <= 80),
        "duplicate_pairs": len(rows) - len({(r["d"], r["a"]) for r in rows}),
        "approved_not_tierA": sum(1 for r in rows if r["ap"] == 1 and r["tier"] != "A"),
        "tiers_present": sorted({r["tier"] for r in rows}),
        "max_rows_chronic": max((c["nRows"] for c in conds
                                 if c["s"] not in ("long-covid", "me-cfs")), default=None),
    }

    # ---- upstream source files (methods provenance) ------------------------
    di_dir = ROOT / "data" / "disease-intelligence"
    di_files = sorted(di_dir.glob("*.json"))
    ids_cov, merged_total, chembl_total = Counter(), 0, 0
    for p in di_files:
        d = json.loads(p.read_text(encoding="utf-8"))
        if "schema_version" not in d:
            continue
        for k, v in (d.get("identifiers") or {}).items():
            if v:
                ids_cov[k] += 1
        me = (d.get("therapeutics") or {}).get("merged_ranked") or []
        merged_total += len(me)
        chembl_total += sum(1 for e in me if e.get("chembl_id"))
    s["upstream"] = {
        "di_files": len(di_files),
        "merged_therapeutic_records": merged_total,
        "merged_with_chembl_id": chembl_total,
        "identifier_coverage": dict(ids_cov),
        "pair_pages_cond_dirs": len([p for p in (ROOT / "pairs").iterdir() if p.is_dir()])
            if (ROOT / "pairs").exists() else 0,
    }

    OUT.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    report(s)
    print(f"\nWrote {OUT}")


def report(s):
    print(f"=== EXPLORER STATS (index generated {s['generated_index_date']}, "
          f"computed {s['computed_on']}) ===")
    print(f"conditions {s['n_conditions']}  pairs {s['n_pairs']}  "
          f"unique agents {s['n_unique_agents']}  index {s['index_file_kb']} KB")
    print(f"tracks {s['track_counts']}  zero-row conditions {s['n_conditions_zero_rows']}")
    print("per-condition rows", s["rows_per_cond"])
    print("presence:", s["pairs"])
    print("tiers:", s["tier_distribution"], "| approved",
          f"{s['approved_pairs']} ({s['approved_pct']}%)")
    print("agent types (pairs):", s["agent_type_distribution"])
    print("agent types (unique):", s["unique_agent_type_distribution"])
    print("phase labels:", s["phase_label_distribution"])
    t = s["trials"]
    print(f"trials: {t['unique_nct']} unique NCT; {t['negative_outcome']} "
          f"({t['negative_outcome_pct']}%) terminated/withdrawn/suspended; "
          f"years {t['year_min']}-{t['year_max']}")
    print("trial status:", t["status"])
    l = s["literature"]
    print(f"literature: {l['unique_pmid']} unique PMID; years {l['year_min']}-"
          f"{l['year_max']}; with DOI {l['with_doi']}; no title {l['no_title']}")
    print("lit types:", l["type"])
    sc = s["score"]
    print(f"score: {sc['min']}-{sc['max']} median {sc['median']} mean {sc['mean']} "
          f"q1 {sc['q1']} q3 {sc['q3']} p90 {sc['p90']} | >=40 {sc['ge40']} "
          f">=60 {sc['ge60']} | at 80 {sc['max_at_cap']}")
    print("score bins:", sc["bins"])
    print("component means:", sc["component_means"], "| caps reached trials",
          sc["trial_cap_reached"], "lit", sc["lit_cap_reached"],
          "both", sc["both_caps_reached"])
    print("integrity:", s["integrity"])
    print("funnel:", s["funnel"])
    print("ui:", s["ui"])
    print("completeness:", s["completeness"])
    print("upstream:", s["upstream"])
    print("reuse:", s["agent_reuse"]["in_2plus"], "agents in 2+ conditions;",
          s["agent_reuse"]["in_5plus"], "in 5+")
    print("top reused:", [(a["agent"], a["conditions"]) for a in s["agent_reuse"]["top"][:6]])
    print("\n--- Table 3: coverage by category ---")
    print(f"{'category':42s} {'cond':>5s} {'pairs':>6s} {'agents':>7s} {'trials':>7s} {'lit':>6s}")
    for k, v in s["by_category"].items():
        print(f"{k:42s} {v['conditions']:5d} {v['pairs']:6d} {v['agents']:7d} "
              f"{v['trial_slots']:7d} {v['lit_slots']:6d}")
    print("\n--- Top 15 pairs ---")
    for p in s["top_pairs"]:
        print(f"{p['score']:5.1f}  {p['condition'][:34]:34s} {p['agent'][:26]:26s} "
              f"tier {p['tier']}  {p['parts']}")


if __name__ == "__main__":
    main()

