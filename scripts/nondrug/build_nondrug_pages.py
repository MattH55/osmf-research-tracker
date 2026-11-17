#!/usr/bin/env python3
"""Feature 1: the non-drug evidence map.

Writes:
  nondrug/index.html            hub: classes by group, conditions, method and exclusions
  nondrug/<class>.html          one page per intervention class (not per class x condition)
  nondrug/data/*.csv            downloads (all trials; one file per class)

Reads data/nondrug/nondrug_trials.json (scripts/nondrug/build_dataset.py). No efficacy grading:
pages report trial STATUS only (registered, recruiting, completed, results posted).

    python scripts/nondrug/build_nondrug_pages.py
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from outcomes import DOMAIN_LABEL  # noqa: E402
from ndsite import DISCLAIMER, ROOT, SITE, dataset_ld, esc, load_dataset, shell, trial_li, write, write_csv  # noqa: E402
from taxonomy import ALL_CLASSES, GROUP_LABEL, GROUPS  # noqa: E402

SHOW_PER_CONDITION = 15


def rank(t: dict) -> tuple:
    order = {"completed": 1, "recruiting": 2, "active": 3, "planned": 4, "stopped": 6, "unknown": 7}
    return (not t["r"], order.get(t["g"], 5), -(t["n"] or 0) if isinstance(t["n"], int) else 0)


def fmt(n: int) -> str:
    return f"{n:,}"


def method_box(d: dict) -> str:
    ex = d["excluded"]
    capped = sorted((c for c in d["conditions"].values() if (c.get("total") or 0) > (c.get("fetched") or 0)), key=lambda c: c["name"])
    cap_list = ", ".join(f"{esc(c['name'])} ({fmt(c['fetched'])} of {fmt(c['total'])})" for c in capped)
    return f"""<div class="box" id="method"><h2>How this map is built</h2><ol class="nd-method">
<li><strong>Source.</strong> For each condition, ClinicalTrials.gov is searched for interventional studies with a behavioural, device, dietary-supplement, "other" or procedure intervention, plus a second search for named supplements that registries often record as drugs (vitamin D, omega-3, probiotics, melatonin and similar). Results are sorted by last update; up to 1,000 trials per search are kept.</li>
<li><strong>Which interventions count.</strong> The registry's own intervention type decides first: medicines and biologicals are excluded, except clearly named supplements. Behavioural and supplement interventions are included; devices, procedures and "other" interventions are included only when their name matches one of the classes on this page (so stents, catheters and surgery are left out).</li>
<li><strong>On-topic only.</strong> The registry's condition search expands terms loosely (a Long COVID search also returns post-stroke fatigue trials), so a trial counts for a condition only when its registered conditions or title name that condition or a listed synonym. {fmt(ex.get('off-topic for the searched condition (registry search expanded the term)', 0))} off-topic matches were removed.</li>
<li><strong>Controls are not counted.</strong> An intervention that appears only in placebo, sham, active-comparator or no-intervention arms is a control, not the thing being tested, and is excluded.</li>
<li><strong>Excluded in this build:</strong> {fmt(ex.get('medicine or biological (registry type)', 0))} medicine or biological interventions, {fmt(ex.get('only in a placebo, sham, comparator or no-intervention arm', 0))} control-only interventions and {fmt(ex.get('not a non-drug intervention (control, assessment, procedure or unmatched name)', 0))} other entries (assessments, usual care, procedures and devices that match no class).</li>
<li><strong>No efficacy grades.</strong> Status labels describe the trial record only. "Results posted" means the sponsor uploaded results to ClinicalTrials.gov; it does not mean the intervention worked.</li>
<li><strong>Capped searches.</strong> For these conditions the registry returned more trials than the cap, so only the most recently updated are included: {cap_list or 'none'}.</li>
<li><strong>Known limits.</strong> Classes come from intervention names and can misfile an individual entry; the registry record is authoritative. A trial can appear under several classes and several conditions.</li>
</ol></div>"""


def build() -> None:
    d = load_dataset()
    trials, conds, built = d["trials"], d["conditions"], d["built"]
    by_class: dict[str, list[str]] = defaultdict(list)
    for nct, t in trials.items():
        for cid in dict.fromkeys(c for c, _ in t["iv"]):
            by_class[cid].append(nct)

    # ---------- CSV: everything ----------
    write_csv("nondrug/data/nondrug-trials.csv",
              ["nct_id", "title", "status", "results_posted", "start_year", "enrollment", "randomised", "phase",
               "classes", "interventions", "conditions", "outcome_domains"],
              [[n, t["t"], t["s"], t["r"], t["y"] or "", t["n"] or "", t["rnd"], t["p"],
                "; ".join(dict.fromkeys(c for c, _ in t["iv"])), "; ".join(nm for _, nm in t["iv"]),
                "; ".join(t["c"]), "; ".join(t["d"])] for n, t in sorted(trials.items())])

    # ---------- class pages ----------
    class_stats = {}
    for cid, ncts in by_class.items():
        k = ALL_CLASSES[cid]
        ts = [trials[n] for n in ncts]
        stats = {"trials": len(ts), "conditions": len({c for t in ts for c in t["c"]}),
                 "results": sum(t["r"] for t in ts), "recruiting": sum(t["g"] == "recruiting" for t in ts),
                 "completed": sum(t["g"] == "completed" for t in ts), "rnd": sum(t["rnd"] for t in ts)}
        class_stats[cid] = stats
        per_cond: dict[str, list[str]] = defaultdict(list)
        for n in ncts:
            for c in trials[n]["c"]:
                per_cond[c].append(n)
        rows = []
        for cslug, cn in sorted(per_cond.items(), key=lambda kv: (-len(kv[1]), conds[kv[0]]["name"])):
            cts = sorted(cn, key=lambda n: rank(trials[n]))
            cm = conds[cslug]
            sizes = [trials[n]["n"] for n in cn if isinstance(trials[n]["n"], int)]
            lis = "".join(trial_li(n, trials[n]) for n in cts[:SHOW_PER_CONDITION])
            more = (f'<li class="meta">and {len(cts) - SHOW_PER_CONDITION} more in the <a href="/nondrug/data/{cid}.csv">CSV download</a></li>'
                    if len(cts) > SHOW_PER_CONDITION else "")
            name = esc(cm["name"])
            name_html = f'<a href="/evidence-gaps/{cslug}.html">{name}</a>'
            rows.append(f"""<tr><th scope="row">{name_html}
<details class="nd-trials"><summary>Show trials</summary><ul class="nd-tlist">{lis}{more}</ul></details></th>
<td class="n">{len(cn)}</td><td class="n">{sum(trials[n]['g'] == 'completed' for n in cn)}</td>
<td class="n">{sum(trials[n]['r'] for n in cn)}</td><td class="n">{sum(trials[n]['g'] == 'recruiting' for n in cn)}</td>
<td class="n">{sum(trials[n]['rnd'] for n in cn)}</td><td class="n">{fmt(max(sizes)) if sizes else '–'}</td></tr>""")
        dom = Counter(x for t in ts for x in t["d"])
        dom_html = ", ".join(f"{esc(DOMAIN_LABEL[x])} ({v})" for x, v in dom.most_common() if x != "unclassified")
        names = Counter(nm.strip().lower() for t in ts for c, nm in t["iv"] if c == cid)
        examples = ", ".join(esc(n) for n, _ in names.most_common(12))
        siblings = [c for c in ALL_CLASSES.values() if c.group == k.group and c.id != cid and c.id in by_class]
        sib_html = " · ".join(f'<a href="/nondrug/{c.id}.html">{esc(c.label)}</a>' for c in siblings)
        write_csv(f"nondrug/data/{cid}.csv",
                  ["nct_id", "title", "status", "results_posted", "start_year", "enrollment", "randomised", "conditions", "interventions_in_class", "outcome_domains"],
                  [[n, trials[n]["t"], trials[n]["s"], trials[n]["r"], trials[n]["y"] or "", trials[n]["n"] or "", trials[n]["rnd"],
                    "; ".join(trials[n]["c"]), "; ".join(nm for c, nm in trials[n]["iv"] if c == cid), "; ".join(trials[n]["d"])]
                   for n in sorted(ncts)])
        body = f"""
<p class="lede">{esc(k.blurb)} This page lists the registered trials that test it, condition by condition, with each trial's status on ClinicalTrials.gov.</p>
<div class="nd-numbers">
  <div><b>{fmt(stats['trials'])}</b><span>registered trials</span></div>
  <div><b>{stats['conditions']}</b><span>conditions</span></div>
  <div><b>{fmt(stats['completed'])}</b><span>completed</span></div>
  <div><b>{fmt(stats['results'])}</b><span>with results posted</span></div>
  <div><b>{fmt(stats['recruiting'])}</b><span>recruiting as of {esc(built)}</span></div>
</div>
{DISCLAIMER}
<h2>Trials by condition</h2>
<p class="nd-method">Sorted by number of trials. Within a condition, trials with posted results come first, then completed, recruiting and active ones. The condition name opens its evidence-gap map.</p>
<div class="tbl-wrap"><table class="nd-tbl"><thead><tr><th scope="col">Condition</th><th scope="col" class="n">Trials</th><th scope="col" class="n">Completed</th><th scope="col" class="n">Results posted</th><th scope="col" class="n">Recruiting</th><th scope="col" class="n">Randomised</th><th scope="col" class="n">Largest</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="box"><h2>What these trials measure</h2><p>Primary outcomes, grouped by keyword rules: {dom_html or 'not classified'}.</p>
<h3>Names used for this class in the registry</h3><p class="nd-method">{examples}</p></div>
<p class="nd-actions"><a class="btn" href="/nondrug/data/{cid}.csv">Download all {fmt(stats['trials'])} trials (CSV)</a> <a href="/nondrug/index.html">All non-drug classes</a></p>
{('<p class="nd-method">Related in ' + esc(GROUP_LABEL[k.group]) + ': ' + sib_html + '</p>') if sib_html else ''}
<p class="nd-method">Source: ClinicalTrials.gov, searched {esc(built)}. Classification rules and exclusions: <a href="/nondrug/index.html#method">how this map is built</a>.</p>
"""
        path = f"nondrug/{cid}.html"
        title = f"{k.label}: {fmt(stats['trials'])} registered trials across {stats['conditions']} conditions"
        desc = (f"Registered clinical trials testing {k.label.lower()} for {stats['conditions']} chronic and post-viral conditions, "
                f"with status, posted results and outcomes, from ClinicalTrials.gov. Research information, not medical advice.")
        write(path, shell(path=path, title=title[:70], description=desc[:300], eyebrow=f"Non-drug evidence map · {GROUP_LABEL[k.group]}",
                          h1=k.label, lede=f"{fmt(stats['trials'])} registered trials across {stats['conditions']} conditions, from ClinicalTrials.gov.",
                          body=body, crumbs=[("Non-drug evidence map", f"{SITE}/nondrug/index.html"), (k.label, f"{SITE}/{path}")],
                          jsonld=[dataset_ld(f"Registered trials of {k.label.lower()}", desc, f"{SITE}/{path}", f"{SITE}/nondrug/data/{cid}.csv", built)],
                          modified=built))

    # ---------- hub ----------
    groups_html = []
    for gid, glabel in GROUPS:
        cards = [c for c in ALL_CLASSES.values() if c.group == gid and c.id in class_stats]
        if not cards:
            continue
        cards.sort(key=lambda c: -class_stats[c.id]["trials"])
        items = "".join(
            f'<a class="nd-card" href="/nondrug/{c.id}.html"><strong>{esc(c.label)}</strong>'
            f'<span>{fmt(class_stats[c.id]["trials"])} trials · {class_stats[c.id]["conditions"]} conditions · '
            f'{fmt(class_stats[c.id]["results"])} with results</span></a>' for c in cards)
        groups_html.append(f'<section class="nd-group"><h2>{esc(glabel)}</h2><div class="nd-cards">{items}</div></section>')
    cond_rows = []
    for slug, c in sorted(conds.items(), key=lambda kv: kv[1]["name"].lower()):
        kept = sum(1 for t in trials.values() if slug in t["c"])
        capped = (c.get("total") or 0) > (c.get("fetched") or 0)
        links = [f'<a href="/evidence-gaps/{slug}.html">Evidence-gap map</a>']
        if c.get("repurpos"):
            links.append(f'<a href="/briefs/{slug}.html">Evidence brief</a>')
        if c.get("page"):
            links.append(f'<a href="{esc(c["page"])}">Condition page</a>')
        cond_rows.append(f'<tr><th scope="row">{esc(c["name"])}</th><td class="n">{fmt(kept)}</td>'
                         f'<td class="n">{fmt(c.get("total") or 0)}{" *" if capped else ""}</td><td>{" · ".join(links)}</td></tr>')
    total = len(trials)
    stats_all = {"results": sum(t["r"] for t in trials.values()), "recruiting": sum(t["g"] == "recruiting" for t in trials.values()),
                 "completed": sum(t["g"] == "completed" for t in trials.values())}
    body = f"""
<p class="lede">Exercise, rehabilitation, psychological, diet, sleep, device and supplement interventions tested in registered clinical trials, for {len(conds)} chronic and post-viral conditions. Every number links back to the trial records on ClinicalTrials.gov.</p>
<div class="nd-numbers">
  <div><b>{fmt(total)}</b><span>trials with a non-drug intervention</span></div>
  <div><b>{len(class_stats)}</b><span>intervention classes</span></div>
  <div><b>{fmt(stats_all['completed'])}</b><span>completed</span></div>
  <div><b>{fmt(stats_all['results'])}</b><span>with results posted</span></div>
  <div><b>{fmt(stats_all['recruiting'])}</b><span>recruiting as of {esc(built)}</span></div>
</div>
{DISCLAIMER}
<div class="nd-groups">{''.join(groups_html)}</div>
<h2 id="conditions">By condition</h2>
<p class="nd-method">Trials counts are after the exclusions described below. "Registry matches" is how many trials the ClinicalTrials.gov search returned; * marks searches that hit the 1,000-trial cap.</p>
<div class="tbl-wrap"><table class="nd-tbl"><thead><tr><th scope="col">Condition</th><th scope="col" class="n">Non-drug trials</th><th scope="col" class="n">Registry matches</th><th scope="col">Open</th></tr></thead>
<tbody>{''.join(cond_rows)}</tbody></table></div>
<p class="nd-actions"><a class="btn" href="/nondrug/data/nondrug-trials.csv">Download all {fmt(total)} trials (CSV)</a> <a href="/supplement-safety/index.html">Supplement safety pages</a> <a href="/evidence-gaps/index.html">Evidence-gap maps</a></p>
{method_box(d)}
"""
    desc = (f"{fmt(total)} registered trials of exercise, psychological, diet, device and supplement interventions across {len(conds)} conditions, "
            "classified from ClinicalTrials.gov with status and posted results. Research information, not medical advice.")
    write("nondrug/index.html", shell(path="nondrug/index.html", title="Non-drug evidence map: trials of non-drug interventions",
                                      description=desc, eyebrow="Research Tracker · non-drug evidence map", h1="Non-drug", h1_span="evidence map",
                                      lede=f"{fmt(total)} registered trials across {len(conds)} conditions, built {esc(built)}.",
                                      body=body, crumbs=[("Non-drug evidence map", f"{SITE}/nondrug/index.html")],
                                      jsonld=[dataset_ld("Non-drug interventions in registered clinical trials", desc, f"{SITE}/nondrug/index.html",
                                                         f"{SITE}/nondrug/data/nondrug-trials.csv", built)], modified=built))
    for f in (ROOT / "nondrug").glob("*.html"):  # remove pages for classes that no longer have trials
        if f.stem != "index" and f.stem not in class_stats:
            f.unlink()
            print(f"  removed stale class page {f.name}")
    print(f"nondrug: {len(class_stats)} class pages + hub, {total} trials")


if __name__ == "__main__":
    build()
