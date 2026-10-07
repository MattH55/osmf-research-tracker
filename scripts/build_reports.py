#!/usr/bin/env python3
"""
Build per-condition "state of the evidence" annual reports.

    python scripts/build_reports.py              # current year, all five conditions
    python scripts/build_reports.py --year 2026  # explicit year
    python scripts/build_reports.py --keys long-covid me-cfs

Outputs:
    reports/<key>-state-of-the-evidence-<YYYY>.html
    reports/data/<key>-<YYYY>.json      the computed numbers behind each report
    reports/reports.json                manifest
    reports/index.html

Every number is computed from the JSON files under data/ (see the Methods section
rendered into each page). Nothing is hand-written. The script is idempotent and
safe to run daily: re-running overwrites the current year's pages in place.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import os
import re
import sys
from collections import Counter, OrderedDict
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from osmf_site import (  # noqa: E402
    CONDITIONS, ORG_LOGO, ORG_NAME, ORG_URL, SITE, SUBSTACK, as_list, breadcrumb_html,
    breadcrumb_jsonld, clean, cohort_matches, esc, fmt_date, fmt_int, load_json, page,
    parse_date, phase_label, sponsor_label, status_label, trial_matches, write_json, write_text,
)

REPORT_KEYS = ["long-covid", "me-cfs", "pacvs", "lyme", "gulf-war-illness"]
REPORTS_DIR = os.path.join(ROOT, "reports")
REPORTS_URL = f"{SITE}/reports/"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
ACTIVE_STATUSES = {"RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING", "ENROLLING_BY_INVITATION"}
BLUE = "#0068f8"
DIR_COLORS = {"up": "#dc2626", "down": "#2563eb", "mixed": "#d97706", "other": "#9ca3af"}


# --------------------------------------------------------------------------
# Computation
# --------------------------------------------------------------------------

def file_mtime(path: str) -> str:
    try:
        return dt.datetime.fromtimestamp(os.path.getmtime(path), dt.timezone.utc).date().isoformat()
    except OSError:
        return ""


def compute(key: str, year: int, trials_doc: Dict[str, Any], agents_doc: Dict[str, Any],
            cohorts_doc: Dict[str, Any], now: dt.datetime) -> Dict[str, Any]:
    meta = CONDITIONS[key]
    feed_path = os.path.join(ROOT, "data", f"{key}.json")
    feed = load_json(feed_path, {}) or {}
    studies = feed.get("studies", []) if isinstance(feed, dict) else []

    # ---- literature ----
    dated: List[Tuple[dt.date, Dict[str, Any]]] = []
    undated = 0
    for s in studies:
        d = parse_date(s.get("pub_date"))
        if d:
            dated.append((d, s))
        else:
            undated += 1
    in_year = [(d, s) for d, s in dated if d.year == year]
    by_month = [0] * 12
    for d, _ in in_year:
        by_month[d.month - 1] += 1
    journals = Counter(clean(s.get("journal")) or "Unknown journal" for _, s in in_year)
    month_precision_only = sum(1 for _, s in in_year if len(clean(s.get("pub_date"))) <= 7)
    feed_range = (min(d for d, _ in dated).isoformat(), max(d for d, _ in dated).isoformat()) if dated else (None, None)
    uniq_pmids = len({clean(s.get("pmid")) for _, s in in_year if clean(s.get("pmid"))})

    # ---- trials ----
    T = trials_doc.get("trials", [])
    matched = []
    for t in T:
        how = trial_matches(t, key)
        if how:
            matched.append((how, t))
    n_mapped = sum(1 for h, _ in matched if h == "mapped")
    n_keyword = sum(1 for h, _ in matched if h == "keyword")
    trials = [t for _, t in matched]
    by_status = Counter(clean(t.get("status")) or "UNKNOWN" for t in trials)
    by_phase = Counter(clean(t.get("phase")) or "NA" for t in trials)
    by_sponsor = Counter(clean(t.get("sponsor_type")) or "" for t in trials)
    started_year = [t for t in trials if (parse_date(t.get("start_date")) or dt.date(1, 1, 1)).year == year]
    updated_year = [t for t in trials if (parse_date(t.get("last_updated")) or dt.date(1, 1, 1)).year == year]
    active = [t for t in trials if clean(t.get("status")) in ACTIVE_STATUSES]
    agent_counter: Counter = Counter()
    agent_active: Counter = Counter()
    for t in trials:
        for a in set(as_list(t.get("agents"))):
            agent_counter[a] += 1
            if clean(t.get("status")) in ACTIVE_STATUSES:
                agent_active[a] += 1
    top_agents = [{"agent": a, "trials": n, "active": agent_active.get(a, 0)} for a, n in agent_counter.most_common(10)]
    enrol = []
    for t in trials:
        try:
            enrol.append(int(float(clean(t.get("enrollment")))))
        except ValueError:
            pass
    enrol.sort()
    median_enrol = enrol[len(enrol) // 2] if enrol else None
    recent_trials = sorted(started_year, key=lambda t: clean(t.get("start_date")), reverse=True)[:8]
    recent_trials = [{
        "nct_id": clean(t.get("nct_id")), "title": clean(t.get("title")), "status": clean(t.get("status")) or "UNKNOWN",
        "phase": clean(t.get("phase")), "start_date": clean(t.get("start_date")), "sponsor": clean(t.get("sponsor")),
        "agents": as_list(t.get("agents"))[:3],
        "link": clean(t.get("link")) or f"https://clinicaltrials.gov/study/{clean(t.get('nct_id'))}",
    } for t in recent_trials]

    # ---- therapeutic agents catalogue ----
    A = agents_doc.get("agents", []) if isinstance(agents_doc, dict) else []
    cat_agents = [a for a in A if any(lbl in as_list(a.get("Primary Conditions")) for lbl in meta["agent_labels"])]
    evidence = Counter(clean(a.get("Evidence Level")) or "Unstated" for a in cat_agents)

    # ---- biomarkers ----
    bm_slug = meta.get("biomarkers")
    bm_path = os.path.join(ROOT, "data", "biomarkers", f"{bm_slug}.json") if bm_slug else None
    bm = load_json(bm_path, {}) if bm_path else {}
    markers = bm.get("markers", []) if isinstance(bm, dict) else []
    cat_labels = bm.get("categories", {}) if isinstance(bm, dict) and isinstance(bm.get("categories"), dict) else {}
    bm_by_cat: "OrderedDict[str, Counter]" = OrderedDict()
    for m in markers:
        c = clean(m.get("category")) or "uncategorised"
        d = clean(m.get("direction")).lower() or "other"
        if d not in ("up", "down", "mixed"):
            d = "other"
        bm_by_cat.setdefault(c, Counter())[d] += 1
    bm_rows = sorted(bm_by_cat.items(), key=lambda kv: -sum(kv[1].values()))
    bm_dir = Counter()
    for c in bm_by_cat.values():
        bm_dir.update(c)
    bm_refs = len({clean(m.get("reference", {}).get("doi") if isinstance(m.get("reference"), dict) else "") for m in markers} - {""})

    # ---- cohorts ----
    cohorts = cohorts_doc.get("cohorts", []) if isinstance(cohorts_doc, dict) else []
    my_cohorts = [c for c in cohorts if cohort_matches(c, key)]
    cohort_rows = []
    for c in my_cohorts:
        try:
            n = int(float(clean(c.get("n_enrolled"))))
        except ValueError:
            n = None
        cohort_rows.append({"id": clean(c.get("id")), "name": clean(c.get("name")), "design": clean(c.get("design")),
                            "n_enrolled": n, "pathogen": clean(c.get("pathogen_id")), "biobank": clean(c.get("biobank_status")),
                            "registration": clean(c.get("registration_id"))})
    cohort_rows.sort(key=lambda r: -(r["n_enrolled"] or 0))

    return {
        "key": key, "year": year, "condition": meta["name"], "short": meta["short"],
        "generated_at": now.isoformat(timespec="seconds"),
        "snapshot": {
            "feed_last_updated": clean(feed.get("last_updated"))[:10] if isinstance(feed, dict) else "",
            "feed_file_mtime": file_mtime(feed_path),
            "trials_last_run": clean(trials_doc.get("last_run"))[:10],
            "agents_last_updated": clean(agents_doc.get("last_updated"))[:10] if isinstance(agents_doc, dict) else "",
            "biomarkers_date_modified": clean((bm.get("page") or {}).get("dateModified")) if isinstance(bm, dict) else "",
            "cohorts_version": clean(cohorts_doc.get("generated")) if isinstance(cohorts_doc, dict) else "",
        },
        "literature": {
            "feed_total": len(studies), "feed_range": feed_range, "undated": undated,
            "in_year": len(in_year), "unique_pmids": uniq_pmids, "month_precision_only": month_precision_only,
            "by_month": by_month, "top_journals": journals.most_common(10), "journal_count": len(journals),
            "feed_source": clean(feed.get("source")) if isinstance(feed, dict) else "",
        },
        "trials": {
            "total": len(trials), "mapped": n_mapped, "keyword": n_keyword, "all_tracked": len(T),
            "match_labels": meta["trial_labels"], "match_keywords": meta["trial_keywords"],
            "by_status": by_status.most_common(), "by_phase": by_phase.most_common(), "by_sponsor": by_sponsor.most_common(),
            "started_in_year": len(started_year), "updated_in_year": len(updated_year), "active": len(active),
            "median_enrollment": median_enrol, "enrollment_known": len(enrol),
            "top_agents": top_agents, "distinct_agents": len(agent_counter), "recent": recent_trials,
        },
        "agents": {"catalogued": len(cat_agents), "by_evidence": evidence.most_common(), "labels": meta["agent_labels"],
                   "all_catalogued": len(A)},
        "biomarkers": {"slug": bm_slug, "total": len(markers), "by_category": [(c, dict(v)) for c, v in bm_rows],
                       "by_direction": dict(bm_dir), "category_labels": cat_labels, "distinct_dois": bm_refs},
        "cohorts": {"count": len(cohort_rows), "rows": cohort_rows, "all_tracked": len(cohorts),
                    "match_pathogens": meta["cohort_pathogens"], "match_case_defs": meta["cohort_case_defs"]},
    }


# --------------------------------------------------------------------------
# SVG charts (inline, no library)
# --------------------------------------------------------------------------

def svg_hbar(rows: List[Tuple[str, int]], title: str, color: str = BLUE, label_w: int = 190, W: int = 720, max_label: int = 30) -> str:
    """Horizontal bars: thin marks, rounded ends, direct value labels, native <title> tooltips."""
    if not rows:
        return '<p class="small">No data to chart.</p>'
    bar_h, gap, top = 18, 8, 6
    mx = max(v for _, v in rows) or 1
    plot_w = W - label_w - 50
    H = top + len(rows) * (bar_h + gap)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" xmlns="http://www.w3.org/2000/svg">'
             f'<title>{esc(title)}</title>']
    for i, (label, v) in enumerate(rows):
        y = top + i * (bar_h + gap)
        w = max(2, round(plot_w * v / mx))
        lab = label if len(label) <= max_label else label[:max_label - 1] + "…"
        parts.append(f'<text x="{label_w - 8}" y="{y + bar_h * 0.72:.0f}" text-anchor="end" font-size="12" fill="#374151">{esc(lab)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{w}" height="{bar_h}" rx="4" fill="{color}"><title>{esc(label)}: {v}</title></rect>')
        parts.append(f'<text x="{label_w + w + 6}" y="{y + bar_h * 0.72:.0f}" font-size="12" fill="#374151">{v}</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_months(by_month: List[int], year: int, now: dt.date) -> str:
    W, H, left, bottom, top = 720, 220, 36, 28, 12
    mx = max(by_month) or 1
    plot_h = H - top - bottom
    plot_w = W - left - 10
    col = plot_w / 12
    bar_w = col - 8
    title = f"Studies indexed per month, {year}"
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" xmlns="http://www.w3.org/2000/svg"><title>{esc(title)}</title>']
    # gridlines (recessive)
    for frac in (0.5, 1.0):
        y = top + plot_h - plot_h * frac
        parts.append(f'<line x1="{left}" x2="{W - 10}" y1="{y:.1f}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{left - 6}" y="{y + 4:.1f}" text-anchor="end" font-size="11" fill="#6b7280">{round(mx * frac)}</text>')
    parts.append(f'<line x1="{left}" x2="{W - 10}" y1="{top + plot_h}" y2="{top + plot_h}" stroke="#9ca3af" stroke-width="1"/>')
    for i, v in enumerate(by_month):
        x = left + i * col + 4
        h = round(plot_h * v / mx)
        future = (year > now.year) or (year == now.year and i + 1 > now.month)
        fill = "#cbd5e1" if future else BLUE
        if v > 0:
            parts.append(f'<rect x="{x:.1f}" y="{top + plot_h - h}" width="{bar_w:.1f}" height="{h}" rx="4" fill="{fill}"><title>{MONTHS[i]} {year}: {v}</title></rect>')
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h - h - 4}" text-anchor="middle" font-size="11" fill="#374151">{v}</text>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{H - 10}" text-anchor="middle" font-size="11" fill="{"#9ca3af" if future else "#374151"}">{MONTHS[i]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def svg_stacked(rows: List[Tuple[str, Dict[str, int]]], labels: Dict[str, str], title: str) -> str:
    if not rows:
        return '<p class="small">No data to chart.</p>'
    W, bar_h, gap, top, label_w = 720, 18, 8, 6, 190
    mx = max(sum(v.values()) for _, v in rows) or 1
    plot_w = W - label_w - 60
    H = top + len(rows) * (bar_h + gap)
    parts = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(title)}" xmlns="http://www.w3.org/2000/svg"><title>{esc(title)}</title>']
    for i, (cat, v) in enumerate(rows):
        y = top + i * (bar_h + gap)
        total = sum(v.values())
        lab = labels.get(cat, cat.replace("_", " ").title())
        parts.append(f'<text x="{label_w - 8}" y="{y + bar_h * 0.72:.0f}" text-anchor="end" font-size="12" fill="#374151">{esc(lab)}</text>')
        x = label_w
        for d in ("up", "down", "mixed", "other"):
            n = v.get(d, 0)
            if not n:
                continue
            w = max(2, round(plot_w * n / mx))
            parts.append(f'<rect x="{x}" y="{y}" width="{max(0, w - 2)}" height="{bar_h}" rx="3" fill="{DIR_COLORS[d]}"><title>{esc(lab)} - {d}: {n}</title></rect>')
            x += w
        parts.append(f'<text x="{x + 6}" y="{y + bar_h * 0.72:.0f}" font-size="12" fill="#374151">{total}</text>')
    parts.append("</svg>")
    legend = ('<div class="small" style="margin-top:.3rem">'
              + " &nbsp; ".join(f'<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:{DIR_COLORS[d]};margin-right:4px"></span>{lbl}'
                                for d, lbl in (("up", "Elevated"), ("down", "Reduced"), ("mixed", "Mixed / inconsistent"), ("other", "Not stated")))
              + "</div>")
    return "".join(parts) + legend


def figure(svg: str, caption: str) -> str:
    return f'<figure class="chart">{svg}<figcaption>{caption}</figcaption></figure>'


def table(headers: List[str], rows: List[List[str]]) -> str:
    if not rows:
        return '<p class="small">No rows.</p>'
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="tbl-wrap"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def report_url(key: str, year: int) -> str:
    return f"{REPORTS_URL}{key}-state-of-the-evidence-{year}.html"


def report_title(r: Dict[str, Any]) -> str:
    return f"{r['short']}: state of the evidence {r['year']}"


def size_word(n: int, small: int, moderate: int) -> str:
    return "small" if n < small else ("moderate" if n < moderate else "substantial")


def render_report(r: Dict[str, Any], now: dt.date) -> str:
    key, year = r["key"], r["year"]
    meta = CONDITIONS[key]
    lit, tr, ag, bm, co, snap = r["literature"], r["trials"], r["agents"], r["biomarkers"], r["cohorts"], r["snapshot"]
    url = report_url(key, year)
    title = report_title(r)
    desc = (f"Computed annual summary of {meta['name']} research in {year}: {lit['in_year']} studies indexed, "
            f"{tr['total']} registered trials ({tr['active']} active), {bm['total']} catalogued biomarkers and "
            f"{co['count']} research cohorts, with methods, limitations and downloadable data from the OSMF research tracker.")[:300]
    crumbs = [("Research Tracker", SITE + "/"), ("Annual Reports", REPORTS_URL), (title, url)]
    partial = year == now.year
    period = f"1 January to {fmt_date(now)}" if partial else f"calendar year {year}"
    out: List[str] = []

    # ---- hero / summary ----
    out.append(f'<header class="hero"><div class="wrap"><div class="badge">Annual report &middot; {year}{" (year to date)" if partial else ""}</div>'
               f'<h1>{esc(title)}</h1><p>What the Open Source Medicine Foundation research tracker holds on {esc(meta["name"])} '
               f'for {esc(period)}: literature flow, registered trials, agents under study, catalogued biomarkers and cohorts. '
               f'Every figure is computed from the public JSON files linked at the end of this page.</p></div></header>')
    out.append(f'<main id="main">{breadcrumb_html(crumbs)}')
    out.append('<div class="toc"><strong>Contents:</strong><ul>'
               '<li><a href="#summary">Summary</a></li><li><a href="#literature">Literature</a></li>'
               '<li><a href="#trials">Clinical trials</a></li><li><a href="#agents">Agents</a></li>'
               '<li><a href="#biomarkers">Biomarkers</a></li><li><a href="#cohorts">Cohorts</a></li>'
               '<li><a href="#methods">Methods</a></li><li><a href="#limitations">Limitations</a></li>'
               '<li><a href="#data">Download the data</a></li><li><a href="#cite">Cite</a></li></ul></div>')
    out.append(f'<h2 id="summary">Summary</h2><div class="numbers">'
               f'<div class="num"><b>{fmt_int(lit["in_year"])}</b><span>studies dated {year} in the feed</span></div>'
               f'<div class="num"><b>{fmt_int(tr["total"])}</b><span>registered trials matched</span></div>'
               f'<div class="num"><b>{fmt_int(tr["active"])}</b><span>trials recruiting or active</span></div>'
               f'<div class="num"><b>{fmt_int(tr["started_in_year"])}</b><span>trials started in {year}</span></div>'
               f'<div class="num"><b>{fmt_int(bm["total"])}</b><span>biomarkers catalogued</span></div>'
               f'<div class="num"><b>{fmt_int(co["count"])}</b><span>research cohorts indexed</span></div></div>')
    # honest framing
    flags = []
    if lit["feed_total"] and lit["feed_total"] <= 100:
        flags.append(f"The literature feed is a rolling window of the {lit['feed_total']} most recent PubMed results for this "
                     f"condition (currently spanning {esc(fmt_date(parse_date(lit['feed_range'][0])))} to "
                     f"{esc(fmt_date(parse_date(lit['feed_range'][1])))}), not a complete census of {year} publications. "
                     f"Monthly counts before the window opens are zero for that reason, not because nothing was published.")
    if tr["total"] == 0:
        flags.append("No ClinicalTrials.gov records in the tracker map to this condition, so the trial sections below are empty "
                     "rather than estimated.")
    elif tr["total"] < 15:
        flags.append(f"Only {tr['total']} trials match this condition; percentages would be misleading at this size, so counts are shown.")
    if tr["keyword"] and not tr["mapped"]:
        flags.append("Trials for this condition are identified by keyword match on the registry title and condition field, "
                     "because the tracker's curated condition mapping does not yet cover it. Expect both misses and false positives.")
    if co["count"] == 0:
        flags.append("No cohorts in the PAIS cohort database are tagged with this condition yet.")
    if bm["total"] == 0:
        flags.append("No biomarker atlas exists for this condition yet.")
    if snap["feed_last_updated"] and (now - (parse_date(snap["feed_last_updated"]) or now)).days > 14:
        flags.append(f"The literature feed was last refreshed on {esc(fmt_date(parse_date(snap['feed_last_updated'])))}; "
                     f"figures are as of that snapshot.")
    if flags:
        out.append('<div class="note"><strong>Read this first.</strong> ' + " ".join(flags) + "</div>")

    # ---- literature ----
    out.append(f'<h2 id="literature">Literature indexed in {year}</h2>')
    if lit["in_year"]:
        out.append(f'<p>The {esc(meta["short"])} feed holds <strong>{lit["in_year"]}</strong> PubMed records with a {year} publication '
                   f'date ({lit["unique_pmids"]} unique PMIDs) out of {lit["feed_total"]} records in the feed, drawn from '
                   f'{lit["journal_count"]} distinct journals. This is a {size_word(lit["in_year"], 20, 60)} sample.'
                   + (f' {lit["month_precision_only"]} record(s) carry only a year or year-month date and are assigned to the first day of that period.' if lit["month_precision_only"] else "")
                   + '</p>')
        out.append(figure(svg_months(lit["by_month"], year, now),
                          f"Records by publication month, {year}. Grey month labels are in the future. Months before the feed window opened are zero by construction."))
        out.append("<h3>Top journals</h3>")
        out.append(figure(svg_hbar([(j, n) for j, n in lit["top_journals"]], f"Top journals, {year}"),
                          f"Journals with the most {year} records in the feed (top {len(lit['top_journals'])}; ties broken by first appearance)."))
    else:
        out.append(f'<p class="small">No records with a {year} publication date are present in the feed.</p>')
    out.append(f'<p class="small">Browse the live feed: <a href="{SITE}{meta["tracker"]}">{esc(meta["short"])} research tracker</a>. '
               f'Weekly changes are in the <a href="{SITE}/digest/">research digest</a>.</p>')

    # ---- trials ----
    out.append('<h2 id="trials">Clinical trials</h2>')
    if tr["total"]:
        how = (f'{tr["mapped"]} via the tracker\'s curated condition mapping' if tr["mapped"] else "")
        how += (f'{" and " if how else ""}{tr["keyword"]} via keyword match' if tr["keyword"] else "")
        out.append(f'<p><strong>{tr["total"]}</strong> of the {fmt_int(tr["all_tracked"])} ClinicalTrials.gov records in the tracker snapshot '
                   f'(taken {esc(snap["trials_last_run"]) or "date unknown"}) match {esc(meta["short"])} ({how}). '
                   f'{tr["active"]} are recruiting, not yet recruiting, enrolling by invitation or active; {tr["started_in_year"]} list a '
                   f'{year} start date and {tr["updated_in_year"]} had their registry record updated in {year}.'
                   + (f' Median planned or actual enrollment is {fmt_int(tr["median_enrollment"])} participants ({tr["enrollment_known"]} trials report a figure).' if tr["median_enrollment"] is not None else "")
                   + '</p>')
        out.append('<div class="grid2">')
        out.append('<div><h3>By status</h3>' + figure(svg_hbar([(status_label(s), n) for s, n in tr["by_status"]], "Trials by status", label_w=150, W=380, max_label=22), "Overall status as recorded on ClinicalTrials.gov at snapshot.") + '</div>')
        out.append('<div><h3>By phase</h3>' + figure(svg_hbar([(phase_label(p), n) for p, n in tr["by_phase"]], "Trials by phase", label_w=150, W=380, max_label=22), "\"Not applicable\" covers behavioural, device, rehabilitation and observational designs.") + '</div>')
        out.append('<div><h3>By sponsor type</h3>' + figure(svg_hbar([(sponsor_label(s), n) for s, n in tr["by_sponsor"]], "Trials by sponsor type", label_w=150, W=380, max_label=22), "Lead-sponsor class from the registry; \"Academic / other\" is the registry's OTHER category.") + '</div>')
        if tr["top_agents"]:
            out.append('<div><h3>Agents under investigation</h3>' + figure(svg_hbar([(a["agent"], a["trials"]) for a in tr["top_agents"]], "Top agents by trial count", label_w=150, W=380, max_label=22),
                       f"Interventions named in the most matched trials (top {len(tr['top_agents'])} of {tr['distinct_agents']} distinct agents). A trial testing several agents counts once per agent.") + '</div>')
        out.append('</div>')
        if tr["top_agents"]:
            out.append(table(["Agent", "Trials", "Of which active"], [[esc(a["agent"]), str(a["trials"]), str(a["active"])] for a in tr["top_agents"]]))
        if tr["recent"]:
            out.append(f'<h3>Trials starting in {year}</h3>')
            out.append(table(["NCT", "Trial", "Status", "Phase", "Start", "Sponsor"], [[
                f'<a href="{esc(t["link"])}" rel="noopener" target="_blank">{esc(t["nct_id"])}</a>',
                esc(t["title"]) + (f'<div class="small">{esc(", ".join(t["agents"]))}</div>' if t["agents"] else ""),
                f'<span class="st {esc(t["status"])}">{esc(status_label(t["status"]))}</span>',
                esc(phase_label(t["phase"])), esc(t["start_date"]), esc(t["sponsor"])] for t in tr["recent"]]))
            if tr["started_in_year"] > len(tr["recent"]):
                out.append(f'<p class="small">Showing the {len(tr["recent"])} most recent of {tr["started_in_year"]} trials with a {year} start date.</p>')
    else:
        out.append(f'<p class="small">No trials in the tracker snapshot ({fmt_int(tr["all_tracked"])} records) match this condition by '
                   f'curated mapping or keyword. This reflects the tracker\'s coverage, not necessarily the absence of trials.</p>')
    out.append(f'<p class="small">All tracked trials: <a href="{SITE}/clinical_trials.html">clinical trials tracker</a>.</p>')

    # ---- agents catalogue ----
    out.append('<h2 id="agents">Therapeutic agents catalogue</h2>')
    if ag["catalogued"]:
        out.append(f'<p>The OSMF therapeutic-agents catalogue lists <strong>{fmt_int(ag["catalogued"])}</strong> agents with '
                   f'{esc(" or ".join(ag["labels"]))} as a primary condition (of {fmt_int(ag["all_catalogued"])} agents overall). '
                   f'Evidence level is the catalogue\'s own coarse grading, assigned automatically from the number and type of linked '
                   f'studies and trials; it is not a GRADE assessment.</p>')
        out.append(figure(svg_hbar([(e, n) for e, n in ag["by_evidence"]], "Agents by evidence level"), "Catalogue evidence grading: anecdotal, preliminary or moderate. No agent for any condition is graded higher than moderate."))
    else:
        out.append('<p class="small">No agents in the catalogue list this condition as primary.</p>')
    out.append(f'<p class="small">Browse: <a href="{SITE}/therapeutics-atlas.html">therapeutics atlas</a> and <a href="{SITE}/agents.html">agents</a>.</p>')

    # ---- biomarkers ----
    out.append('<h2 id="biomarkers">Biomarkers catalogued</h2>')
    if bm["total"]:
        d = bm["by_direction"]
        out.append(f'<p>The {esc(meta["short"])} biomarker atlas (last edited {esc(snap["biomarkers_date_modified"]) or "date unknown"}) holds '
                   f'<strong>{bm["total"]}</strong> marker entries across {len(bm["by_category"])} categories, citing {bm["distinct_dois"]} distinct DOIs: '
                   f'{d.get("up", 0)} reported elevated, {d.get("down", 0)} reduced and {d.get("mixed", 0)} with mixed or inconsistent findings'
                   + (f', {d.get("other", 0)} with no direction stated' if d.get("other") else "") + '. '
                   f'Direction is relative to the comparison group in the cited source (usually healthy controls) and a single entry can rest on one study.</p>')
        out.append(figure(svg_stacked(bm["by_category"], bm["category_labels"], "Biomarkers by category and direction"), "Marker entries by atlas category, split by reported direction of change."))
        out.append(table(["Category", "Elevated", "Reduced", "Mixed", "Total"], [[
            esc(bm["category_labels"].get(c, c.title())), str(v.get("up", 0)), str(v.get("down", 0)), str(v.get("mixed", 0)), str(sum(v.values()))] for c, v in bm["by_category"]]))
        out.append(f'<p class="small">Full atlas: <a href="{SITE}/{esc(bm["slug"])}-biomarkers.html">{esc(meta["short"])} biomarker atlas</a>.</p>')
    else:
        out.append(f'<p class="small">No biomarker atlas is published for this condition. See the <a href="{SITE}/biomarker-atlas.html">biomarker atlas index</a>.</p>')

    # ---- cohorts ----
    out.append('<h2 id="cohorts">Research cohorts</h2>')
    if co["count"]:
        total_n = sum(c["n_enrolled"] or 0 for c in co["rows"])
        out.append(f'<p><strong>{co["count"]}</strong> of the {co["all_tracked"]} cohorts in the OSMF post-acute infection syndrome (PAIS) cohort database '
                   f'relate to {esc(meta["short"])}, together enrolling about {fmt_int(total_n)} participants where a figure is recorded. '
                   f'This is a curated database, not a systematic census of cohorts.</p>')
        out.append(table(["Cohort", "Design", "Enrolled", "Biobank", "Registration"], [[
            f'<a href="{SITE}/pais-cohorts.html#{esc(c["id"])}">{esc(c["name"])}</a>', esc(c["design"].replace("_", " ")),
            fmt_int(c["n_enrolled"]) if c["n_enrolled"] is not None else "not recorded", esc(c["biobank"].replace("_", " ")) or "unknown",
            esc(c["registration"]) or "&mdash;"] for c in co["rows"]]))
    else:
        out.append(f'<p class="small">No cohorts in the <a href="{SITE}/pais-cohorts.html">PAIS cohort database</a> ({co["all_tracked"]} cohorts) are tagged with this condition.</p>')

    # ---- methods ----
    out.append('<h2 id="methods">Methods</h2>')
    out.append(f'<p>This page was generated by <code>scripts/build_reports.py</code> on {esc(fmt_date(now))} from the data snapshot described below. '
               f'No number is entered by hand.</p><ul class="plain">'
               f'<li><strong>Studies.</strong> Records in <code>data/{esc(key)}.json</code> (source: {esc(lit["feed_source"]) or "PubMed"}; feed last updated '
               f'{esc(snap["feed_last_updated"]) or "unknown"}) whose <code>pub_date</code> parses to a date in {year}. Year-only or year-month dates are mapped to '
               f'the first day of the period. {lit["undated"]} record(s) had no parseable date and were excluded. Monthly counts bin by publication month; '
               f'journal counts use the record\'s journal string verbatim (no normalisation of abbreviations).</li>'
               f'<li><strong>Trials.</strong> Records in <code>data/clinical_trials/clinical_trials_current.json</code> (snapshot {esc(snap["trials_last_run"]) or "unknown"}). '
               f'A trial matches when its <code>mapped_conditions</code> contains {esc(", ".join(repr(x) for x in tr["match_labels"])) or "no curated label (none defined)"}'
               + (f', or when its title or raw condition list matches the pattern(s) {esc(", ".join("/" + p + "/i" for p in tr["match_keywords"]))}' if tr["match_keywords"] else "")
               + f'. Status, phase and sponsor type are the registry\'s own fields, counted once per trial. "Started in {year}" uses <code>start_date</code>; '
               f'"updated in {year}" uses <code>last_updated</code>. Agents are the tracker\'s normalised intervention names; a trial with several agents '
               f'counts once for each. Median enrollment uses the registry <code>enrollment</code> field (actual or estimated) where numeric.</li>'
               f'<li><strong>Agents catalogue.</strong> Entries in <code>data/therapeutic_agents.json</code> (updated {esc(snap["agents_last_updated"]) or "unknown"}) '
               f'whose "Primary Conditions" includes {esc(", ".join(repr(x) for x in ag["labels"])) or "no label"}, grouped by the catalogue\'s "Evidence Level" string.</li>'
               f'<li><strong>Biomarkers.</strong> Entries in <code>data/biomarkers/{esc(bm["slug"] or "(none)")}.json</code>, grouped by <code>category</code> and '
               f'<code>direction</code> (up, down, mixed). Distinct DOIs count unique <code>reference.doi</code> values.</li>'
               f'<li><strong>Cohorts.</strong> Entries in <code>data/pais-cohorts-index.json</code> (version {esc(snap["cohorts_version"]) or "unknown"}) whose '
               f'<code>pathogen_id</code> is in {esc(str(co["match_pathogens"]))}'
               + (f' or whose <code>case_definition</code> is in {esc(str(co["match_case_defs"]))}' if co["match_case_defs"] else "") + '.</li></ul>')

    # ---- limitations ----
    out.append('<h2 id="limitations">Limitations</h2><ul class="plain">'
               '<li>The literature feed is a bounded, rolling PubMed query result. It captures recent indexing activity, not the full year, '
               'and PubMed indexing dates lag print publication. Counts here will not match a systematic search.</li>'
               '<li>Study counts measure volume, not quality. No screening for study design, sample size, peer-review status or relevance beyond the search query was applied.</li>'
               '<li>Trial matching depends on the tracker\'s condition mapping and keyword patterns; trials registered under umbrella terms '
               '(for example "post-viral fatigue") may be missed, and registry status fields are frequently stale.</li>'
               '<li>Biomarker direction reflects what each cited source reported, often from a single cohort; "elevated" in one study does not imply replication.</li>'
               '<li>The cohort database and agents catalogue are curated and incomplete, and the evidence-level grading is automatic and coarse.</li>'
               f'<li>Different sections rest on different snapshot dates (feed {esc(snap["feed_last_updated"]) or "?"}, trials {esc(snap["trials_last_run"]) or "?"}, '
               f'biomarkers {esc(snap["biomarkers_date_modified"]) or "?"}, agents {esc(snap["agents_last_updated"]) or "?"}).</li>'
               + (f'<li>This is a year-to-date report; it is regenerated daily and will change until 31 December {year}.</li>' if partial else "") + '</ul>')

    # ---- data ----
    data_links = [
        (f"/data/{key}.json", f"{meta['short']} literature feed"),
        ("/data/clinical_trials/clinical_trials_current.json", "Clinical trials snapshot (all conditions)"),
        ("/data/therapeutic_agents.json", "Therapeutic agents catalogue"),
        ("/data/pais-cohorts-index.json", "PAIS cohort database index"),
        (f"/reports/data/{key}-{year}.json", "The computed numbers behind this report"),
    ]
    if bm["slug"]:
        data_links.insert(2, (f"/data/biomarkers/{bm['slug']}.json", f"{meta['short']} biomarker atlas"))
    out.append('<h2 id="data">Download the data</h2><p>All inputs are public JSON files in the research-tracker repository, licensed for reuse with attribution.</p><ul class="plain">'
               + "".join(f'<li><a href="{SITE}{esc(p)}">{esc(lbl)}</a> <span class="small">({esc(p)})</span></li>' for p, lbl in data_links) + '</ul>')

    # ---- cite ----
    out.append(f'<div class="box" id="cite"><h3>Suggested citation</h3><div class="cite">{ORG_NAME}. {esc(title)}'
               f'{" (year-to-date, generated " + esc(fmt_date(now)) + ")" if partial else ""}. {ORG_NAME}; {year}. {esc(url)}</div>'
               f'<p class="small" style="margin-top:.6rem">For a stable reference, cite the generation date shown; the page is regenerated as data arrive. '
               f'Weekly updates: <a href="{SUBSTACK}" rel="noopener">subscribe on Substack</a> or follow the <a href="{SITE}/digest/feed.xml">digest RSS feed</a>.</p></div>')
    out.append('<div class="disclaimer"><strong>Disclaimer.</strong> This report is an automated description of a research database maintained by the '
               'Open Source Medicine Foundation. It is not a systematic review and not medical advice. Discuss any treatment decision with a qualified clinician.</div>')
    out.append('</main>')

    report_ld = {
        "@context": "https://schema.org",
        "@type": ["Report", "ScholarlyArticle"],
        "headline": title, "name": title, "description": desc, "url": url, "mainEntityOfPage": url,
        "datePublished": f"{year}-01-01" if not partial else r["generated_at"][:10],
        "dateModified": r["generated_at"][:10],
        "inLanguage": "en", "isAccessibleForFree": True,
        "author": {"@type": "Organization", "name": ORG_NAME, "url": ORG_URL},
        "publisher": {"@type": "Organization", "name": ORG_NAME, "url": ORG_URL, "logo": {"@type": "ImageObject", "url": ORG_LOGO}},
        "about": {"@type": "MedicalCondition", "name": meta["name"]},
        "temporalCoverage": f"{year}-01-01/{now.isoformat() if partial else str(year) + '-12-31'}",
        "keywords": [meta["short"], "state of the evidence", "research report", "clinical trials", "biomarkers"],
        "citation": url,
    }
    dataset_ld = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": f"{meta['short']} research tracker data, {year}",
        "description": f"Source JSON files behind the {title} report: literature feed, clinical trials snapshot, therapeutic agents, biomarker atlas and cohort index.",
        "url": url + "#data", "license": "https://creativecommons.org/licenses/by/4.0/", "isAccessibleForFree": True,
        "creator": {"@type": "Organization", "name": ORG_NAME, "url": ORG_URL},
        "dateModified": r["generated_at"][:10], "temporalCoverage": str(year),
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + p, "name": lbl} for p, lbl in data_links],
    }
    return page(title=title, description=desc, canonical=url, body="".join(out),
                jsonld=[report_ld, dataset_ld, breadcrumb_jsonld(crumbs)], nav_active="/reports/",
                footer_note=f"Report generated {r['generated_at'][:10]}.", published=report_ld["datePublished"],
                modified=r["generated_at"][:10])


def render_index(manifest: List[Dict[str, Any]], now: dt.datetime) -> str:
    title = "State of the evidence: annual reports"
    desc = ("Annual, fully computed reports on long COVID, ME/CFS, PACVS, Lyme/PTLDS and Gulf War Illness research: "
            "studies indexed, trials by status and phase, agents under investigation, biomarkers and cohorts, with methods and open data.")
    crumbs = [("Research Tracker", SITE + "/"), ("Annual Reports", REPORTS_URL)]
    years = sorted({m["year"] for m in manifest}, reverse=True)
    sections = []
    for y in years:
        items = []
        for m in [x for x in manifest if x["year"] == y]:
            items.append(f'<li><a href="{esc(m["url"])}">{esc(m["title"])}</a><div class="meta">'
                         f'{m["studies"]} studies &middot; {m["trials"]} trials ({m["active_trials"]} active) &middot; '
                         f'{m["biomarkers"]} biomarkers &middot; {m["cohorts"]} cohorts &middot; generated {esc(m["generated_at"][:10])}</div></li>')
        sections.append(f'<h2 id="y{y}">{y}{" (year to date)" if y == now.year else ""}</h2><ol class="issue-list">{"".join(items)}</ol>')
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": REPORTS_URL,
          "publisher": {"@type": "Organization", "name": ORG_NAME, "url": ORG_URL},
          "hasPart": [{"@type": "Report", "name": m["title"], "url": m["url"]} for m in manifest]}
    hero = ('<header class="hero"><div class="wrap"><div class="badge">Annual &middot; computed &middot; open data</div>'
            '<h1>State of the evidence</h1><p>One report per condition per year, generated entirely from the OSMF research-tracker data: '
            'how much was published, which trials are running and in what phase, which agents are being tested, what the biomarker atlas '
            'contains and which cohorts exist. Each report explains exactly how every number was derived and links the raw files.</p></div></header>')
    body = (f'{hero}<main id="main">{breadcrumb_html(crumbs)}' + "".join(sections)
            + '<h2 id="about">About these reports</h2><p>Reports are regenerated daily by <code>scripts/build_reports.py</code> and change as '
            'data arrive during the year. They are descriptive summaries of a database, not systematic reviews: see the methods and '
            f'limitations sections on each page before quoting a figure. Weekly changes are in the <a href="{SITE}/digest/">research digest</a>.</p>'
            '<div class="disclaimer">Not medical advice. Open Source Medicine Foundation.</div></main>')
    return page(title=title, description=desc, canonical=REPORTS_URL, body=body, jsonld=[ld, breadcrumb_jsonld(crumbs)],
                og_type="website", nav_active="/reports/", footer_note=f"Index regenerated {now.date().isoformat()}.")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=None)
    ap.add_argument("--keys", nargs="*", default=REPORT_KEYS, choices=REPORT_KEYS)
    ap.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD) for testing")
    args = ap.parse_args(argv)
    now_dt = dt.datetime.now(dt.timezone.utc)
    today = parse_date(args.today) if args.today else now_dt.date()
    year = args.year or today.year

    trials_doc = load_json(os.path.join(ROOT, "data", "clinical_trials", "clinical_trials_current.json"), {}) or {}
    agents_doc = load_json(os.path.join(ROOT, "data", "therapeutic_agents.json"), {}) or {}
    cohorts_doc = load_json(os.path.join(ROOT, "data", "pais-cohorts-index.json"), {}) or {}

    os.makedirs(os.path.join(REPORTS_DIR, "data"), exist_ok=True)
    for key in args.keys:
        r = compute(key, year, trials_doc, agents_doc, cohorts_doc, now_dt)
        write_json(os.path.join(REPORTS_DIR, "data", f"{key}-{year}.json"), r)
        write_text(os.path.join(REPORTS_DIR, f"{key}-state-of-the-evidence-{year}.html"), render_report(r, today))
        print(f"{key} {year}: {r['literature']['in_year']} studies, {r['trials']['total']} trials "
              f"({r['trials']['active']} active), {r['biomarkers']['total']} biomarkers, {r['cohorts']['count']} cohorts")

    # Manifest + index from every computed report present on disk (all years).
    manifest = []
    for path in glob.glob(os.path.join(REPORTS_DIR, "data", "*.json")):
        d = load_json(path)
        if not isinstance(d, dict) or "key" not in d:
            continue
        if not os.path.exists(os.path.join(REPORTS_DIR, f"{d['key']}-state-of-the-evidence-{d['year']}.html")):
            continue
        manifest.append({
            "key": d["key"], "year": d["year"], "title": report_title(d), "url": report_url(d["key"], d["year"]),
            "path": f"reports/{d['key']}-state-of-the-evidence-{d['year']}.html", "generated_at": d["generated_at"],
            "studies": d["literature"]["in_year"], "trials": d["trials"]["total"], "active_trials": d["trials"]["active"],
            "biomarkers": d["biomarkers"]["total"], "cohorts": d["cohorts"]["count"],
        })
    order = {k: i for i, k in enumerate(REPORT_KEYS)}
    manifest.sort(key=lambda m: (-m["year"], order.get(m["key"], 99)))
    write_json(os.path.join(REPORTS_DIR, "reports.json"), {"generated": now_dt.isoformat(timespec="seconds"), "count": len(manifest), "reports": manifest})
    write_text(os.path.join(REPORTS_DIR, "index.html"), render_index(manifest, now_dt))
    print(f"reports: {len(manifest)} report(s); wrote reports/index.html, reports/reports.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
