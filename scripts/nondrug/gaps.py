"""Gap computation shared by the evidence-gap maps and the condition briefs, so both report the same gaps."""
from __future__ import annotations

from collections import defaultdict

from outcomes import DOMAINS
from taxonomy import ALL_CLASSES, GROUPS

DOMAIN_COLS = [(d, label) for d, label, _ in DOMAINS] + [("unclassified", "Not classified")]


def compute(mine: dict) -> dict:
    """mine: {nct: trial} for one condition. Returns cell counts, totals and the two gap lists."""
    cell = defaultdict(lambda: {"n": 0, "r": 0, "c": 0, "rec": 0})
    group_tot, dom_tot = defaultdict(int), defaultdict(int)
    class_tot = defaultdict(lambda: {"n": 0, "r": 0, "rec": 0, "c": 0})
    for t in mine.values():
        groups = {ALL_CLASSES[c].group for c, _ in t["iv"]}
        for c in dict.fromkeys(c for c, _ in t["iv"]):
            x = class_tot[c]
            x["n"] += 1
            x["r"] += t["r"]
            x["rec"] += t["g"] == "recruiting"
            x["c"] += t["g"] == "completed"
        for g in groups:
            group_tot[g] += 1
            for dom in t["d"]:
                x = cell[(g, dom)]
                x["n"] += 1
                x["r"] += t["r"]
                x["c"] += t["g"] == "completed"
                x["rec"] += t["g"] == "recruiting"
        for dom in t["d"]:
            dom_tot[dom] += 1
    measured = {dom for dom, n in dom_tot.items() if n >= 3 and dom not in ("unclassified", "feasibility")}
    unmeasured = []  # (other trials measuring it, group label, domain label, trials found in this group)
    for gid, glabel in GROUPS:
        if group_tot.get(gid, 0) < 3:
            continue
        for dom, dlabel in DOMAIN_COLS:
            if dom in measured and cell[(gid, dom)]["n"] == 0:
                unmeasured.append((dom_tot[dom], glabel, dlabel, group_tot[gid]))
    unmeasured.sort(key=lambda x: -x[0])
    unreported = sorted(
        [(cell[(gid, dom)]["n"], gl, dl, cell[(gid, dom)]["rec"]) for gid, gl in GROUPS for dom, dl in DOMAIN_COLS
         if dom != "unclassified" and cell[(gid, dom)]["n"] >= 3 and cell[(gid, dom)]["r"] == 0],
        key=lambda x: -x[0])
    return {"cell": cell, "group_tot": group_tot, "dom_tot": dom_tot, "class_tot": class_tot,
            "unmeasured": unmeasured, "unreported": unreported}
