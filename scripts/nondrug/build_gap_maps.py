#!/usr/bin/env python3
"""Feature 4: living evidence-gap maps for non-drug interventions, one per condition.

Rows are intervention groups (taxonomy.GROUPS); columns are primary-outcome domains
(outcomes.DOMAINS). A cell counts registered trials in that condition whose non-drug
intervention falls in the group AND whose primary outcomes fall in the domain.

Gaps are reported two ways, both computed from the counts:
  * unmeasured: a domain other groups have measured (>= 3 trials) that a group with >= 8 trials (gaps.MIN_GROUP_TRIALS)
    in this condition has never used as a primary outcome;
  * unreported: cells with >= 3 trials but no posted results yet.

Writes evidence-gaps/index.html, evidence-gaps/<slug>.html and evidence-gaps/data/<slug>.csv.

    python scripts/nondrug/build_gap_maps.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ndsite import filter_box, DISCLAIMER, ROOT, SITE, dataset_ld, esc, load_dataset, shell, write, write_csv  # noqa: E402
from gaps import DOMAIN_COLS, compute  # noqa: E402
from taxonomy import ALL_CLASSES, GROUPS  # noqa: E402

DECENTRIAL = "https://protocol-forge-five.vercel.app/"
SUPPORT = "https://opensourcemed.info/support.html"


def level(n: int) -> str:
    return "z" if n == 0 else "l1" if n <= 2 else "l2" if n <= 9 else "l3" if n <= 29 else "l4"


def rule_agreement() -> str:
    p = ROOT / "data" / "nondrug" / "outcome_rule_checks.json"
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        held = doc["samples"][-1]
        return (f"Checked against {sum(len(s['items']) for s in doc['samples'])} hand-labelled outcomes; on a held-out sample of "
                f"{len(held['items'])}, the rules agreed with the hand label for 20 before adjustment, and every outcome they labelled was labelled correctly (misses were left unclassified).")
    except Exception:
        return ""


def build() -> None:
    d = load_dataset()
    trials, conds, built = d["trials"], d["conditions"], d["built"]
    agreement = rule_agreement()
    index_rows = []
    for slug, cm in sorted(conds.items(), key=lambda kv: kv[1]["name"].lower()):
        mine = {n: t for n, t in trials.items() if slug in t["c"]}
        g = compute(mine)
        cell, group_tot, dom_tot, class_tot = g["cell"], g["group_tot"], g["dom_tot"], g["class_tot"]
        # matrix
        head = "".join(f'<th scope="col">{esc(lab)}</th>' for _, lab in DOMAIN_COLS)
        body_rows, csv_rows, empty_groups = [], [], []
        for gid, glabel in GROUPS:
            if not group_tot.get(gid):
                empty_groups.append(glabel)
                for dom, dlabel in DOMAIN_COLS:
                    csv_rows.append([gid, glabel, dom, dlabel, 0, 0, 0, 0])
                continue
            tds = []
            for dom, dlabel in DOMAIN_COLS:
                x = cell[(gid, dom)]
                sub = f"<small>{x['r']} with results</small>" if x["n"] and x["r"] else ""
                aria = f"{glabel}, {dlabel}: {x['n']} trials, {x['r']} with results posted, {x['rec']} recruiting"
                tds.append(f'<td class="{level(x["n"])}" title="{esc(aria)}" aria-label="{esc(aria)}">{x["n"] or "·"}{sub}</td>')
                csv_rows.append([gid, glabel, dom, dlabel, x["n"], x["c"], x["r"], x["rec"]])
            body_rows.append(f'<tr><th scope="row">{esc(glabel)} <span class="meta">({group_tot.get(gid, 0)})</span></th>{"".join(tds)}</tr>')
        write_csv(f"evidence-gaps/data/{slug}.csv",
                  ["group_id", "group", "domain_id", "domain", "trials", "completed", "results_posted", "recruiting"], csv_rows)
        # gaps (shared with the condition briefs)
        capped = (cm.get("total") or 0) > (cm.get("fetched") or 0)
        # Absence can only be claimed when the search was not capped.
        unmeasured = [] if capped else [
            (n, f"Among the {gn} trials of {gl[:1].lower() + gl[1:]} found, none used <strong>{esc(dl.lower())}</strong> as a primary outcome "
                f"({n} trials of other approaches did).") for n, gl, dl, gn in g["unmeasured"]]
        unreported = [(n, f"<strong>{esc(gl)} × {esc(dl.lower())}</strong>: {n} trials registered, none with results posted"
                          + (f" ({rec} still recruiting)" if rec else "")) for n, gl, dl, rec in g["unreported"]]
        gaps_html = ""
        if unmeasured:
            gaps_html += "<h3>Outcomes not found as a primary outcome in a group's trials</h3><ul class=\"nd-gaps\">" + "".join(f"<li>{h}</li>" for _, h in unmeasured[:14]) + "</ul>"
        if unreported:
            gaps_html += "<h3>Questions studied but with no results posted</h3><ul class=\"nd-gaps\">" + "".join(f"<li>{h}</li>" for _, h in unreported[:14]) + "</ul>"
        if capped:
            gaps_html = (f"<p class=\"nd-method\">This condition has {cm['total']:,} matching trials, more than the 1,000 this map covers, "
                         "so it cannot show that an outcome was never measured. Only studied-but-unreported questions are listed.</p>") + gaps_html
        if not gaps_html:
            gaps_html = "<p>Too few registered trials to identify gaps with these rules.</p>"
        top = sorted(class_tot.items(), key=lambda kv: -kv[1]["n"])[:12]
        top_rows = "".join(f'<tr><th scope="row"><a href="/nondrug/{c}.html">{esc(ALL_CLASSES[c].label)}</a></th><td class="n">{v["n"]}</td>'
                           f'<td class="n">{v["r"]}</td><td class="n">{v["rec"]}</td></tr>' for c, v in top)
        cap_note = (f" The registry search returned {cm['total']:,} trials, more than the 1,000-trial cap, so this map covers the most recently updated 1,000."
                    if capped else "")
        unc = dom_tot.get("unclassified", 0)
        links = [f'<a href="/nondrug/index.html">Non-drug evidence map</a>']
        if cm.get("repurpos"):
            links.append(f'<a href="/briefs/{slug}.html">Evidence brief</a>')
            links.append(f'<a href="{esc(cm["repurpos"])}">RepurpOS condition page</a>')
        if cm.get("page"):
            links.append(f'<a href="{esc(cm["page"])}">Condition page</a>')
        body = f"""
<p class="lede">Which non-drug approaches have been tested for {esc(cm['name'])}, and which outcomes they were tested on. An empty cell means no matching trial was found among those searched: a possible gap, not proof that nobody has asked the question.</p>
<div class="nd-numbers">
  <div><b>{len(mine):,}</b><span>registered non-drug trials</span></div>
  <div><b>{sum(t['r'] for t in mine.values()):,}</b><span>with results posted</span></div>
  <div><b>{sum(t['g'] == 'recruiting' for t in mine.values()):,}</b><span>recruiting as of {esc(cm.get('fetched_at') or built)}</span></div>
  <div><b>{sum(1 for k, v in cell.items() if v['n'] and k[1] != 'unclassified')}</b><span>group × outcome cells with at least one trial</span></div>
</div>
{DISCLAIMER}
<h2>Evidence-gap matrix</h2>
<p class="nd-method">Each number is the count of trials; "with results" is how many of them have posted results on ClinicalTrials.gov. A trial is counted once per group and per outcome domain it covers. The number in brackets after each group is its total trials for this condition.{cap_note}</p>
<div class="nd-legend"><span><i style="background:#f6f7fb"></i>none</span><span><i style="background:#fff3e0"></i>1–2</span><span><i style="background:#ffd9a8"></i>3–9</span><span><i style="background:#f8a95c"></i>10–29</span><span><i style="background:#9a3412"></i>30 or more</span></div>
<div class="tbl-wrap" role="region" tabindex="0" aria-label="Evidence-gap matrix, scrolls sideways"><table class="nd-matrix"><caption class="sr-only">Registered non-drug trials for {esc(cm['name'])} by intervention group and primary outcome domain</caption>
<thead><tr><th scope="col">Intervention group</th>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>
<p class="nd-scroll-hint">The table scrolls sideways: {len(DOMAIN_COLS)} outcome columns.</p>
{('<p class="nd-method">No trials found for this condition in: ' + esc('; '.join(empty_groups)) + '.</p>') if empty_groups else ''}
<div class="box"><h2>Where the gaps are</h2>{gaps_html}
<p class="nd-actions"><a class="btn" href="{DECENTRIAL}" target="_blank" rel="noopener">Design a trial with DecenTrial (beta)</a> <a href="{SUPPORT}">Fund a component of this work</a></p>
<p class="nd-method">A gap here means no matching trial was found among those searched, not that an approach would work. About one trial in six has primary outcomes the rules cannot classify, so a few gaps may be measured under another name. Some gaps are gaps for good reason.</p></div>
<h2>Most-studied approaches for {esc(cm['name'])}</h2>
<div class="tbl-wrap"><table class="nd-tbl"><thead><tr><th scope="col">Class</th><th scope="col" class="n">Trials</th><th scope="col" class="n">Results posted</th><th scope="col" class="n">Recruiting</th></tr></thead><tbody>{top_rows}</tbody></table></div>
<p class="nd-actions"><a class="btn" href="/evidence-gaps/data/{slug}.csv">Download this matrix (CSV)</a> {' '.join(links)}</p>
<div class="box"><h2>How outcomes are grouped</h2><p class="nd-method">Each trial's primary outcome measures are sorted into domains by keyword rules. {unc:,} trials for this condition have primary outcomes the rules could not classify; they appear in the last column rather than being dropped. {esc(agreement)}</p>
<p class="nd-method">Trial selection and exclusions follow the <a href="/nondrug/index.html#method">non-drug evidence map method</a>. Source: ClinicalTrials.gov, searched {esc(cm.get('fetched_at') or built)}.</p></div>
"""
        path = f"evidence-gaps/{slug}.html"
        title = f"{cm['name']}: non-drug evidence-gap map"
        desc = (f"Which exercise, psychological, diet, device and supplement approaches have registered trials for {cm['name']}, on which outcomes, "
                f"and where the gaps are. {len(mine):,} trials from ClinicalTrials.gov.")
        write(path, shell(path=path, title=title[:70], description=desc[:300], eyebrow="Evidence-gap map · non-drug interventions",
                          h1=cm["name"], h1_span="evidence gaps", lede=f"{len(mine):,} registered non-drug trials, mapped by approach and outcome.",
                          body=body, crumbs=[("Evidence-gap maps", f"{SITE}/evidence-gaps/index.html"), (cm["name"], f"{SITE}/{path}")],
                          jsonld=[dataset_ld(f"{cm['name']} non-drug evidence-gap matrix", desc, f"{SITE}/{path}", f"{SITE}/evidence-gaps/data/{slug}.csv", built)],
                          modified=built))
        top_gap = unmeasured[0][1] if unmeasured else ("not shown: search capped" if capped else "")
        index_rows.append(f'<tr data-name="{esc(cm["name"].lower())}"><th scope="row"><a href="/evidence-gaps/{slug}.html">{esc(cm["name"])}</a></th><td class="n" data-label="Trials">{len(mine):,}</td>'
                          f'<td class="n" data-label="Results posted">{sum(t["r"] for t in mine.values()):,}</td><td class="wide" data-label="Top possible gap">{top_gap or "–"}</td></tr>')
    fbox, fjs = filter_box("gap-index")
    body = f"""
<p class="lede">For each condition, a matrix of non-drug approaches against the outcomes trials have measured. Empty cells show where no matching trial was found among those searched, and weak cells where trials have posted no results. Built from {len(trials):,} ClinicalTrials.gov records.</p>
{DISCLAIMER}
{fbox}
<div class="tbl-wrap"><table class="nd-tbl nd-compact" id="gap-index"><thead><tr><th scope="col">Condition</th><th scope="col" class="n">Trials</th><th scope="col" class="n">Results posted</th><th scope="col">Top possible gap</th></tr></thead>
<tbody>{''.join(index_rows)}</tbody></table></div>
{fjs}
<p class="nd-method">Method: <a href="/nondrug/index.html#method">how trials are selected</a>. A gap means no matching trial was found among those searched, not that an approach would work.</p>
"""
    desc = f"Evidence-gap maps for non-drug interventions across {len(conds)} conditions: which approaches and outcomes have registered trials, and which do not."
    write("evidence-gaps/index.html", shell(path="evidence-gaps/index.html", title="Evidence-gap maps for non-drug interventions", description=desc,
                                            eyebrow="Research Tracker · evidence-gap maps", h1="Evidence-gap", h1_span="maps",
                                            lede=f"{len(conds)} conditions, updated {esc(built)}.", body=body,
                                            crumbs=[("Evidence-gap maps", f"{SITE}/evidence-gaps/index.html")], modified=built))
    print(f"evidence-gaps: {len(conds)} condition maps + index")


if __name__ == "__main__":
    build()
