#!/usr/bin/env python3
"""Turn the cached ClinicalTrials.gov crawl into data/nondrug/nondrug_trials.json.

For every trial: keep only interventions that are non-drug (taxonomy.classify) AND part of what
the trial tests (taxonomy.is_studied_arm). Trials with no such intervention are dropped. Each kept
trial records its classes, primary-outcome domains, status, results flag and the conditions whose
query returned it. Exclusions are tallied by reason so pages can disclose them.

    python scripts/nondrug/build_dataset.py
"""
from __future__ import annotations

import gc
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from conditions import load_conditions, on_topic  # noqa: E402
from outcomes import domains_for_trial  # noqa: E402
from taxonomy import ALL_CLASSES, DRUG_TYPES, classify, is_studied_arm  # noqa: E402

ROOT = HERE.parents[1]
CACHE = ROOT / "data" / "nondrug" / "cache"
OUT = ROOT / "data" / "nondrug" / "nondrug_trials.json"

STATUS_GROUP = {
    "RECRUITING": "recruiting", "ENROLLING_BY_INVITATION": "recruiting", "NOT_YET_RECRUITING": "planned",
    "ACTIVE_NOT_RECRUITING": "active", "COMPLETED": "completed", "TERMINATED": "stopped", "WITHDRAWN": "stopped",
    "SUSPENDED": "stopped", "UNKNOWN": "unknown", "AVAILABLE": "other", "NO_LONGER_AVAILABLE": "other",
    "TEMPORARILY_NOT_AVAILABLE": "other", "APPROVED_FOR_MARKETING": "other", "WITHHELD": "other",
}


def year(s: str) -> int | None:
    try:
        return int((s or "")[:4])
    except ValueError:
        return None


def main() -> None:
    conds = {c["slug"]: c for c in load_conditions()}
    trials: dict[str, dict] = {}
    meta: dict[str, dict] = {}
    excluded = Counter()
    for slug, c in conds.items():
        f = CACHE / f"{slug}.json"
        if not f.exists():
            print(f"  missing crawl for {slug}; run crawl_ctgov.py")
            continue
        raw = json.loads(f.read_text(encoding="utf-8"))
        meta[slug] = {k: raw.get(k) for k in ("name", "query", "total", "fetched", "cap", "fetched_at")}
        fs = CACHE / f"{slug}.supp.json"
        if fs.exists():  # second pass: named supplements registered as drugs
            supp = json.loads(fs.read_text(encoding="utf-8"))
            meta[slug]["supp_total"], meta[slug]["supp_fetched"] = supp.get("total"), supp.get("fetched")
            raw["studies"] = raw["studies"] + supp["studies"]
            del supp
        meta[slug].update({"page": c.get("page"), "repurpos": c.get("repurpos"), "kept": 0})
        for s in raw["studies"]:
            ps = s.get("protocolSection", {})
            nct = ps.get("identificationModule", {}).get("nctId")
            if not nct:
                continue
            if not on_topic(c, ps.get("conditionsModule", {}).get("conditions", []), ps.get("identificationModule", {}).get("briefTitle", "")):
                excluded["off-topic for the searched condition (registry search expanded the term)"] += 1
                continue
            if nct in trials:
                if slug not in trials[nct]["c"]:
                    trials[nct]["c"].append(slug)
                    meta[slug]["kept"] += 1
                continue
            ai = ps.get("armsInterventionsModule", {})
            roles = {(a.get("label") or "").strip(): a.get("type") or "" for a in ai.get("armGroups", []) or []}
            ivs, seen = [], set()
            for iv in ai.get("interventions", []) or []:
                name, itype = (iv.get("name") or "").strip(), (iv.get("type") or "").upper()
                k = classify(name, itype)
                if itype in DRUG_TYPES and not k:
                    excluded["medicine or biological (registry type)"] += 1
                    continue
                if not k:
                    excluded["not a non-drug intervention (control, assessment, procedure or unmatched name)"] += 1
                    continue
                arm_roles = [roles.get((l or "").strip(), "") for l in iv.get("armGroupLabels") or []]
                if not is_studied_arm(arm_roles):
                    excluded["only in a placebo, sham, comparator or no-intervention arm"] += 1
                    continue
                key = (k.id, name.lower())
                if key not in seen:
                    seen.add(key)
                    ivs.append([k.id, name[:120]])
            if not ivs:
                continue
            st = ps.get("statusModule", {})
            design = ps.get("designModule", {})
            outs = [{"measure": o.get("measure", ""), "description": o.get("description", "")}
                    for o in ps.get("outcomesModule", {}).get("primaryOutcomes", []) or []]
            status = st.get("overallStatus") or "UNKNOWN"
            trials[nct] = {
                "t": (ps.get("identificationModule", {}).get("briefTitle") or nct)[:180],
                "s": status, "g": STATUS_GROUP.get(status, "other"),
                "p": ",".join(design.get("phases") or []) or "NA",
                "n": (design.get("enrollmentInfo") or {}).get("count"),
                "rnd": (design.get("designInfo") or {}).get("allocation") == "RANDOMIZED",
                "y": year((st.get("startDateStruct") or {}).get("date")),
                "u": (st.get("lastUpdatePostDateStruct") or {}).get("date"),
                "r": bool(s.get("hasResults")),
                "iv": ivs,
                "d": domains_for_trial(outs),
                "o": [o["measure"][:160] for o in outs[:3]],
                "c": [slug],
            }
            meta[slug]["kept"] += 1
        del raw
        gc.collect()
    payload = {
        "built": date.today().isoformat(),
        "source": "ClinicalTrials.gov API v2, interventional studies with a behavioural, device, dietary-supplement, other or procedure intervention",
        "classes": {k: {"label": v.label, "group": v.group} for k, v in ALL_CLASSES.items()},
        "conditions": meta, "excluded": dict(excluded), "trials": trials,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    cls = Counter(c for t in trials.values() for c, _ in t["iv"])
    print(f"wrote {OUT.relative_to(ROOT)}: {len(trials)} trials, {OUT.stat().st_size // 1024} KB, {len(meta)} conditions")
    print("excluded interventions:", dict(excluded))
    print("top classes:", cls.most_common(12))


if __name__ == "__main__":
    main()
