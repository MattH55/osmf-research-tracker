#!/usr/bin/env python3
"""
Build the weekly post-viral research digest.

    python scripts/build_digest.py                 # current ISO week (idempotent, safe daily)
    python scripts/build_digest.py --backfill 8    # also ensure the 8 most recent weeks with data exist
    python scripts/build_digest.py --allow-empty   # publish the current week even if nothing was indexed
    python scripts/build_digest.py --force         # recompute backfilled weeks from current feed data
    python scripts/build_digest.py --today 2026-07-10   # pretend today is another date (testing)

Outputs (all under digest/):
    <YYYY>-W<WW>.html      one page per issue
    data/<YYYY>-W<WW>.json frozen per-issue snapshot (so an issue does not change when feeds roll over)
    archive.json           manifest of issues (newest first)
    index.html             archive page with subscribe block
    feed.xml               RSS 2.0  (validated with xml.etree before writing)
    feed.json              JSON Feed 1.1

Also inserts <link rel="alternate" type="application/rss+xml"> into the root index.html
head if it is not already there (idempotent, nothing else in that file is touched).

How an issue is computed
------------------------
* Window: the 7 days ending on the issue's as-of date (today for the current
  week, the Sunday of the week for backfilled weeks).  If fewer than
  MIN_STUDIES new studies fall in the window across all conditions, the window
  is widened to 14 days and the page says so.  Backfill skips weeks whose
  strict 7-day window holds nothing at all (so stale feeds do not produce
  duplicate issues); the current week is skipped when empty unless --allow-empty.
* Studies: entries in data/<key>.json whose pub_date falls in the window.  A
  PMID that appears in several feeds is listed once, under the first condition
  in FEED_KEYS order, tagged with the other conditions.
* Trial activity: trials in data/clinical_trials/clinical_trials_current.json
  whose last_updated falls in the window.
* "By the numbers": sum of studies across all feeds, trial count, number of
  marker entries across data/biomarkers/*.json files that have a markers[] list.
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import glob
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from typing import Any, Dict, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from osmf_site import (  # noqa: E402
    CONDITIONS, FEED_KEYS, ORG_LOGO, ORG_NAME, ORG_URL, SITE, SUBSTACK, SUBSTACK_HOME,
    as_list, breadcrumb_html, breadcrumb_jsonld, clean, esc, excerpt_sentences, fmt_date,
    fmt_int, iso_week_id, load_json, page, parse_date, phase_label, status_label,
    trial_matches, trim_authors, week_bounds, write_json, write_text,
)

DIGEST_DIR = os.path.join(ROOT, "digest")
ISSUE_DATA_DIR = os.path.join(DIGEST_DIR, "data")
MANIFEST = os.path.join(DIGEST_DIR, "archive.json")
MIN_STUDIES = 3
DIGEST_URL = f"{SITE}/digest/"
FEED_TITLE = "Post-viral research digest - Open Source Medicine Foundation"
FEED_DESC = ("Weekly digest of newly indexed peer-reviewed studies and clinical-trial activity in "
             "long COVID, ME/CFS, PACVS, Lyme/PTLDS, Gulf War Illness, POTS, MCAS and other "
             "post-infectious syndromes, compiled from the OSMF research tracker.")


# --------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------

def load_feeds() -> "OrderedDict[str, Dict[str, Any]]":
    feeds: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for key in FEED_KEYS:
        d = load_json(os.path.join(ROOT, "data", f"{key}.json"))
        if not isinstance(d, dict) or not isinstance(d.get("studies"), list):
            continue  # post-viral-illness.json is a treatment overview, not a feed
        feeds[key] = d
    return feeds


def load_trials() -> Dict[str, Any]:
    d = load_json(os.path.join(ROOT, "data", "clinical_trials", "clinical_trials_current.json"), {})
    if not isinstance(d, dict):
        d = {}
    d.setdefault("trials", [])
    return d


def count_biomarkers() -> int:
    n = 0
    for path in glob.glob(os.path.join(ROOT, "data", "biomarkers", "*.json")):
        d = load_json(path)
        if isinstance(d, dict) and isinstance(d.get("markers"), list):
            n += len(d["markers"])
    return n


# --------------------------------------------------------------------------
# Issue computation
# --------------------------------------------------------------------------

def collect_studies(feeds, start: dt.date, end: dt.date):
    """Return (per_condition_lists, total_unique) for pub_date in [start, end]."""
    seen: Dict[str, str] = {}
    per: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for key, feed in feeds.items():
        rows = []
        for s in feed.get("studies", []):
            d = parse_date(s.get("pub_date"))
            if not d or d < start or d > end:
                continue
            pmid = clean(s.get("pmid"))
            if pmid and pmid in seen:
                if seen[pmid] != key:  # tag the earlier entry with this condition
                    for r in per[seen[pmid]]:
                        if r["pmid"] == pmid and key not in r["also"]:
                            r["also"].append(key)
                continue
            if pmid:
                seen[pmid] = key
            rows.append({
                "pmid": pmid,
                "title": clean(s.get("title")),
                "journal": clean(s.get("journal")),
                "pub_date": d.isoformat(),
                "authors": trim_authors(s.get("authors")),
                "excerpt": excerpt_sentences(s.get("abstract")),
                "url": clean(s.get("url")) or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""),
                "also": [],
            })
        rows.sort(key=lambda r: (r["pub_date"], r["title"]), reverse=True)
        per[key] = rows
    total = sum(len(v) for v in per.values())
    return per, total


def collect_trials(trials: List[Dict[str, Any]], start: dt.date, end: dt.date) -> List[Dict[str, Any]]:
    out = []
    for t in trials:
        d = parse_date(t.get("last_updated"))
        if not d or d < start or d > end:
            continue
        conds = [k for k in CONDITIONS if trial_matches(t, k)]
        out.append({
            "nct_id": clean(t.get("nct_id")),
            "title": clean(t.get("title")),
            "status": clean(t.get("status")) or "UNKNOWN",
            "phase": clean(t.get("phase")),
            "last_updated": d.isoformat(),
            "start_date": clean(t.get("start_date")),
            "sponsor": clean(t.get("sponsor")),
            "sponsor_type": clean(t.get("sponsor_type")),
            "agents": as_list(t.get("agents")),
            "conditions": conds or ["other-post-viral"],
            "mapped_conditions": as_list(t.get("mapped_conditions")),
            "link": clean(t.get("link")) or f"https://clinicaltrials.gov/study/{clean(t.get('nct_id'))}",
        })
    out.sort(key=lambda r: (r["last_updated"], r["nct_id"]), reverse=True)
    return out


def compute_issue(issue_id: str, asof: dt.date, feeds, trials_doc, generated_at: dt.datetime) -> Dict[str, Any]:
    end = asof
    start = end - dt.timedelta(days=6)
    per, total = collect_studies(feeds, start, end)
    strict_total = total
    strict_trials = len(collect_trials(trials_doc.get("trials", []), start, end))
    widened = False
    if total < MIN_STUDIES:
        widened = True
        start = end - dt.timedelta(days=13)
        per, total = collect_studies(feeds, start, end)
    trial_rows = collect_trials(trials_doc.get("trials", []), start, end)
    year, week = int(issue_id[:4]), int(issue_id[-2:])
    monday, sunday = week_bounds(year, week)
    latest_pub = max((parse_date(s.get("pub_date")) for f in feeds.values() for s in f.get("studies", [])
                      if parse_date(s.get("pub_date"))), default=None)
    return {
        "id": issue_id,
        "year": year,
        "week": week,
        "week_monday": monday.isoformat(),
        "week_sunday": sunday.isoformat(),
        "asof": asof.isoformat(),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "window_days": (end - start).days + 1,
        "widened": widened,
        "strict_study_count": strict_total,
        "strict_trial_count": strict_trials,
        "study_count": total,
        "trial_count": len(trial_rows),
        "studies": per,
        "trials": trial_rows,
        "feed_latest_pub_date": latest_pub.isoformat() if latest_pub else None,
        "numbers": {
            "studies_tracked": sum(len(f.get("studies", [])) for f in feeds.values()),
            "trials_tracked": len(trials_doc.get("trials", [])),
            "biomarkers_catalogued": count_biomarkers(),
            "feeds": len(feeds),
        },
        "feed_updates": {k: clean(f.get("last_updated"))[:10] for k, f in feeds.items()},
        "trials_last_run": clean(trials_doc.get("last_run"))[:10],
        "generated_at": generated_at.isoformat(timespec="seconds"),
    }


def issue_title(issue: Dict[str, Any]) -> str:
    n = issue["study_count"]
    return f"Post-viral research digest, week {issue['week']:02d} {issue['year']}: {n} new {'study' if n == 1 else 'studies'}"


def issue_url(issue_id: str) -> str:
    return f"{DIGEST_URL}{issue_id}.html"


def issue_description(issue: Dict[str, Any]) -> str:
    parts = []
    for key, rows in issue["studies"].items():
        if rows:
            parts.append(f"{CONDITIONS[key]['short']} {len(rows)}")
    cond = ", ".join(parts) if parts else "no new studies indexed"
    s = (f"{issue['study_count']} newly indexed peer-reviewed studies ({cond}) and "
         f"{issue['trial_count']} clinical-trial updates, {fmt_date(parse_date(issue['window_start']))} to "
         f"{fmt_date(parse_date(issue['window_end']))}. From the Open Source Medicine Foundation research tracker.")
    return s[:300]


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_study(r: Dict[str, Any]) -> str:
    also = "".join(f'<span class="tag alt">also {esc(CONDITIONS[k]["short"])}</span>' for k in r.get("also", []))
    meta = []
    if r["journal"]:
        meta.append(f"<b>{esc(r['journal'])}</b>")
    meta.append(esc(fmt_date(parse_date(r["pub_date"]))))
    if r["authors"]:
        meta.append(esc(r["authors"]))
    link_open = f'<a href="{esc(r["url"])}" rel="noopener" target="_blank">' if r["url"] else ""
    link_close = "</a>" if r["url"] else ""
    pm = f' <a class="small" href="{esc(r["url"])}" rel="noopener" target="_blank">PubMed {esc(r["pmid"])}</a>' if r["pmid"] else ""
    body = f"<p>{esc(r['excerpt'])}</p>" if r["excerpt"] else '<p class="small">No abstract available.</p>'
    return (f'<article class="study"><h4>{link_open}{esc(r["title"]) or "Untitled"}{link_close}{also}</h4>'
            f'<div class="meta">{" &middot; ".join(meta)}{pm}</div>{body}</article>')


def render_issue_body(issue: Dict[str, Any], prev_i: Optional[Dict[str, Any]], next_i: Optional[Dict[str, Any]],
                      for_feed: bool = False) -> str:
    """Issue content (without hero).  for_feed=True returns a standalone HTML fragment for RSS."""
    ws, we = parse_date(issue["window_start"]), parse_date(issue["window_end"])
    out = []
    # Intro
    if issue["study_count"] == 0 and issue["trial_count"] == 0:
        out.append(f'<p class="lede">No new studies or trial updates were indexed by the tracker between '
                   f'{esc(fmt_date(ws))} and {esc(fmt_date(we))}.</p>')
    else:
        out.append(f'<p class="lede">Between {esc(fmt_date(ws))} and {esc(fmt_date(we))} the tracker indexed '
                   f'<strong>{issue["study_count"]} new peer-reviewed {"study" if issue["study_count"] == 1 else "studies"}</strong> '
                   f'and <strong>{issue["trial_count"]} clinical-trial {"update" if issue["trial_count"] == 1 else "updates"}</strong> '
                   f'across {issue["numbers"]["feeds"]} post-viral and post-infectious conditions.</p>')
    if issue["widened"]:
        out.append(f'<div class="note"><strong>Note:</strong> fewer than {MIN_STUDIES} new studies were indexed in the '
                   f'7 days to {esc(fmt_date(we))}, so this issue covers the 14 days from {esc(fmt_date(ws))}. '
                   f'Some items may therefore also appear in the previous issue.</div>')
    latest = parse_date(issue.get("feed_latest_pub_date"))
    if latest and latest < ws:
        out.append(f'<div class="note">The most recent study in the literature feeds is dated {esc(fmt_date(latest))}; '
                   f'the feeds may not have been refreshed for this window.</div>')

    # By the numbers
    n = issue["numbers"]
    out.append('<section aria-label="By the numbers"><h2 id="numbers">By the numbers</h2><div class="numbers">'
               f'<div class="num"><b>{fmt_int(issue["study_count"])}</b><span>new studies this issue</span></div>'
               f'<div class="num"><b>{fmt_int(issue["trial_count"])}</b><span>trial updates this issue</span></div>'
               f'<div class="num"><b>{fmt_int(n["studies_tracked"])}</b><span>studies currently in the feeds</span></div>'
               f'<div class="num"><b>{fmt_int(n["trials_tracked"])}</b><span>clinical trials tracked</span></div>'
               f'<div class="num"><b>{fmt_int(n["biomarkers_catalogued"])}</b><span>biomarkers catalogued</span></div>'
               '</div>'
               f'<p class="small">Studies tracked = entries across the {n["feeds"]} condition feeds (each feed keeps a rolling '
               f'window of recent PubMed results); trials tracked = ClinicalTrials.gov records in the current trial snapshot '
               f'(last run {esc(issue["trials_last_run"]) or "unknown"}); biomarkers catalogued = marker entries across all '
               f'OSMF biomarker atlases.</p></section>')

    # Contents
    conds_with = [k for k, rows in issue["studies"].items() if rows]
    if conds_with and not for_feed:
        out.append('<div class="toc"><strong>In this issue:</strong><ul>' + "".join(
            f'<li><a href="#{esc(k)}">{esc(CONDITIONS[k]["short"])} ({len(issue["studies"][k])})</a></li>' for k in conds_with)
            + (f'<li><a href="#trials">Trial activity ({issue["trial_count"]})</a></li>' if issue["trial_count"] else "")
            + '</ul></div>')

    # Studies per condition
    out.append('<h2 id="studies">New studies by condition</h2>')
    if not conds_with:
        out.append('<p class="small">No studies with a publication date inside this window were present in the feeds.</p>')
    for key in conds_with:
        rows = issue["studies"][key]
        meta = CONDITIONS[key]
        out.append(f'<section id="{esc(key)}"><h3>{esc(meta["name"])} '
                   f'<span class="tag">{len(rows)} new</span></h3>'
                   f'<p class="small">Full feed: <a href="{SITE}{meta["tracker"]}">{esc(meta["short"])} research tracker</a></p>')
        out.extend(render_study(r) for r in rows)
        out.append('</section>')
    empty = [k for k in issue["studies"] if not issue["studies"][k]]
    if empty and conds_with:
        out.append('<p class="small">No new studies this window for: ' + ", ".join(
            f'<a href="{SITE}{CONDITIONS[k]["tracker"]}">{esc(CONDITIONS[k]["short"])}</a>' for k in empty) + '.</p>')

    # Trial activity
    out.append('<h2 id="trials">Trial activity</h2>')
    if issue["trials"]:
        out.append(f'<p class="small">ClinicalTrials.gov records whose registry entry was last updated between '
                   f'{esc(fmt_date(ws))} and {esc(fmt_date(we))}. A registry update can be anything from a status change '
                   f'to an edited contact field; status shown is as of the tracker snapshot.</p>')
        rows = []
        for t in issue["trials"]:
            conds = ", ".join(esc(CONDITIONS[c]["short"]) for c in t["conditions"])
            agents = ", ".join(esc(a) for a in t["agents"][:3]) or "&mdash;"
            rows.append(f'<tr><td><a href="{esc(t["link"])}" rel="noopener" target="_blank">{esc(t["nct_id"])}</a></td>'
                        f'<td>{esc(t["title"])}<div class="small">{conds}</div></td>'
                        f'<td><span class="st {esc(t["status"])}">{esc(status_label(t["status"]))}</span></td>'
                        f'<td>{esc(phase_label(t["phase"]))}</td><td>{agents}</td>'
                        f'<td>{esc(t["last_updated"])}</td></tr>')
        out.append('<div class="tbl-wrap"><table><thead><tr><th>NCT</th><th>Trial</th><th>Status</th><th>Phase</th>'
                   '<th>Agents</th><th>Updated</th></tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')
    else:
        out.append('<p class="small">No ClinicalTrials.gov records in the tracker were updated during this window.</p>')
    out.append(f'<p class="small">Browse all tracked trials: <a href="{SITE}/clinical_trials.html">clinical trials tracker</a>.</p>')
    return "\n".join(out)


def cite_box(issue: Dict[str, Any]) -> str:
    url = issue_url(issue["id"])
    asof = parse_date(issue["asof"])
    return (f'<div class="box" id="cite"><h3>Cite this issue</h3><div class="cite">{ORG_NAME}. '
            f'{esc(issue_title(issue))}. Published {esc(fmt_date(asof))}. {esc(url)}</div>'
            f'<p class="small" style="margin-top:.6rem">Issues are regenerated from the live tracker data within their week '
            f'and frozen afterwards; the snapshot behind this page is at '
            f'<a href="{DIGEST_URL}data/{esc(issue["id"])}.json">data/{esc(issue["id"])}.json</a>.</p></div>')


DISCLAIMER = ('<div class="disclaimer"><strong>Disclaimer.</strong> This digest is an automated, unreviewed listing of '
              'newly indexed PubMed records and ClinicalTrials.gov registry updates compiled by the Open Source Medicine '
              'Foundation. Inclusion is not endorsement; abstracts are excerpted verbatim from PubMed and may contain errors. '
              'It is not medical advice. Discuss any treatment decision with a qualified clinician.</div>')


def subscribe_block() -> str:
    return (f'<div class="subscribe"><h3>Get the digest every week</h3>'
            f'<p>The same issue goes out by email on Substack. RSS and JSON Feed are available for readers and aggregators.</p>'
            f'<a class="btn" href="{SUBSTACK}" rel="noopener">Subscribe on Substack</a>'
            f'<a class="btn ghost" href="{DIGEST_URL}feed.xml">RSS feed</a>'
            f'<a class="btn ghost" href="{DIGEST_URL}feed.json">JSON Feed</a></div>')


def render_issue_page(issue: Dict[str, Any], prev_i, next_i) -> str:
    title = issue_title(issue)
    desc = issue_description(issue)
    url = issue_url(issue["id"])
    asof = issue["asof"]
    crumbs = [("Research Tracker", SITE + "/"), ("Weekly Digest", DIGEST_URL), (f"Week {issue['week']:02d} {issue['year']}", url)]
    article_ld = {
        "@context": "https://schema.org",
        "@type": ["Article", "NewsArticle"],
        "headline": title,
        "description": desc,
        "url": url,
        "mainEntityOfPage": url,
        "datePublished": asof,
        "dateModified": issue["generated_at"][:10],
        "inLanguage": "en",
        "isAccessibleForFree": True,
        "author": {"@type": "Organization", "name": ORG_NAME, "url": ORG_URL},
        "publisher": {"@type": "Organization", "name": ORG_NAME, "url": ORG_URL,
                      "logo": {"@type": "ImageObject", "url": ORG_LOGO}},
        "isPartOf": {"@type": "Periodical", "name": "Post-viral research digest", "url": DIGEST_URL},
        "about": [{"@type": "MedicalCondition", "name": CONDITIONS[k]["name"]} for k, rows in issue["studies"].items() if rows],
        "keywords": ["long COVID", "ME/CFS", "PACVS", "post-viral syndrome", "research digest"],
    }
    pager = '<nav class="pager" aria-label="Issue navigation">'
    pager += (f'<a href="{issue_url(prev_i["id"])}">&larr; Previous: week {prev_i["week"]:02d} {prev_i["year"]}</a>' if prev_i else "<span></span>")
    pager += (f'<a href="{issue_url(next_i["id"])}">Next: week {next_i["week"]:02d} {next_i["year"]} &rarr;</a>' if next_i else f'<a href="{DIGEST_URL}">All issues &rarr;</a>')
    pager += "</nav>"
    hero = (f'<header class="hero"><div class="wrap"><div class="badge">Weekly digest &middot; ISO week {issue["week"]:02d}</div>'
            f'<h1>{esc(title)}</h1><p>{esc(fmt_date(parse_date(issue["window_start"])))} &ndash; {esc(fmt_date(parse_date(issue["window_end"])))}'
            f' &middot; published {esc(fmt_date(parse_date(asof)))} &middot; <a href="{SUBSTACK}" rel="noopener">Subscribe</a></p></div></header>')
    body = (f'{hero}<main id="main">{breadcrumb_html(crumbs)}'
            + render_issue_body(issue, prev_i, next_i)
            + subscribe_block() + cite_box(issue) + DISCLAIMER + pager + "</main>")
    return page(title=title, description=desc, canonical=url, body=body,
                jsonld=[article_ld, breadcrumb_jsonld(crumbs)], nav_active="/digest/",
                footer_note=f"Digest generated {issue['generated_at'][:10]}.", published=asof,
                modified=issue["generated_at"][:10])


def render_index(manifest: List[Dict[str, Any]], generated: str) -> str:
    title = "Post-viral research digest: weekly archive"
    desc = ("Weekly archive of newly indexed studies and clinical-trial activity in long COVID, ME/CFS, PACVS, "
            "Lyme/PTLDS, Gulf War Illness, POTS and MCAS. Subscribe by email or RSS.")
    crumbs = [("Research Tracker", SITE + "/"), ("Weekly Digest", DIGEST_URL)]
    items = []
    for m in manifest:
        conds = ", ".join(f'{esc(CONDITIONS[k]["short"])} {v}' for k, v in m.get("conditions", {}).items() if v)
        items.append(f'<li><a href="{esc(m["url"])}">{esc(m["title"])}</a>'
                     f'<div class="meta">{esc(fmt_date(parse_date(m["window_start"])))} &ndash; {esc(fmt_date(parse_date(m["window_end"])))}'
                     f' &middot; {m["trial_count"]} trial updates{(" &middot; " + conds) if conds else ""}'
                     f'{" &middot; 14-day window" if m.get("widened") else ""}</div></li>')
    listing = '<ol class="issue-list">' + "".join(items) + "</ol>" if items else '<p class="small">No issues have been published yet.</p>'
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": DIGEST_URL,
        "isPartOf": {"@type": "WebSite", "name": "OSMF Research Tracker", "url": SITE + "/"},
        "publisher": {"@type": "Organization", "name": ORG_NAME, "url": ORG_URL},
        "hasPart": [{"@type": "Article", "headline": m["title"], "url": m["url"], "datePublished": m["date_published"]} for m in manifest[:50]],
    }
    hero = (f'<header class="hero"><div class="wrap"><div class="badge">Weekly &middot; automated &middot; open data</div>'
            f'<h1>Post-viral research digest</h1><p>Every week: the peer-reviewed studies newly indexed in the OSMF research '
            f'tracker and the ClinicalTrials.gov records that changed, across long COVID, ME/CFS, PACVS, Lyme/PTLDS, Gulf War '
            f'Illness, POTS, MCAS and other post-infectious syndromes.</p></div></header>')
    body = (f'{hero}<main id="main">{breadcrumb_html(crumbs)}' + subscribe_block()
            + f'<h2 id="archive">Archive <span class="tag">{len(manifest)} issues</span></h2>' + listing
            + '<h2 id="how">How the digest is built</h2>'
            '<p>A script (<code>scripts/build_digest.py</code>) runs after the daily PubMed and ClinicalTrials.gov refresh. '
            'It takes every study whose publication date falls in the last seven days from each condition feed, de-duplicates '
            'by PMID, and lists trials whose registry record changed in the same window. When fewer than three new studies are '
            'found the window is widened to fourteen days and the issue says so. Each issue is frozen as a JSON snapshot once '
            'its week has passed. Nothing is written by hand; errors in titles or abstracts come from the source records.</p>'
            f'<p>Annual, per-condition summaries live in the <a href="{SITE}/reports/">state-of-the-evidence reports</a>.</p>'
            + DISCLAIMER + "</main>")
    return page(title=title, description=desc, canonical=DIGEST_URL, body=body, jsonld=[ld, breadcrumb_jsonld(crumbs)],
                og_type="website", nav_active="/digest/", footer_note=f"Archive regenerated {generated[:10]}.")


# --------------------------------------------------------------------------
# Feeds
# --------------------------------------------------------------------------

def rfc822(d: dt.date) -> str:
    return email.utils.format_datetime(dt.datetime(d.year, d.month, d.day, 8, 0, tzinfo=dt.timezone.utc))


def build_rss(manifest: List[Dict[str, Any]], issues: Dict[str, Dict[str, Any]], now: dt.datetime) -> str:
    ATOM = "http://www.w3.org/2005/Atom"
    ET.register_namespace("atom", ATOM)
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = FEED_TITLE
    ET.SubElement(ch, "link").text = DIGEST_URL
    ET.SubElement(ch, "description").text = FEED_DESC
    ET.SubElement(ch, "language").text = "en"
    ET.SubElement(ch, "lastBuildDate").text = email.utils.format_datetime(now)
    ET.SubElement(ch, "generator").text = "OSMF build_digest.py"
    ET.SubElement(ch, "ttl").text = "1440"
    ET.SubElement(ch, f"{{{ATOM}}}link", {"href": DIGEST_URL + "feed.xml", "rel": "self", "type": "application/rss+xml"})
    img = ET.SubElement(ch, "image")
    ET.SubElement(img, "url").text = ORG_LOGO
    ET.SubElement(img, "title").text = FEED_TITLE
    ET.SubElement(img, "link").text = DIGEST_URL
    for m in manifest[:52]:
        issue = issues.get(m["id"])
        if not issue:
            continue
        it = ET.SubElement(ch, "item")
        ET.SubElement(it, "title").text = m["title"]
        ET.SubElement(it, "link").text = m["url"]
        ET.SubElement(it, "guid", {"isPermaLink": "true"}).text = m["url"]
        ET.SubElement(it, "pubDate").text = rfc822(parse_date(m["date_published"]))
        for k, v in m.get("conditions", {}).items():
            if v:
                ET.SubElement(it, "category").text = CONDITIONS[k]["short"]
        ET.SubElement(it, "description").text = render_issue_body(issue, None, None, for_feed=True)
    xml_bytes = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    ET.fromstring(xml_bytes)  # validate well-formedness before writing
    return xml_bytes.decode("utf-8")


def build_jsonfeed(manifest: List[Dict[str, Any]], issues: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for m in manifest[:52]:
        issue = issues.get(m["id"])
        if not issue:
            continue
        items.append({
            "id": m["url"], "url": m["url"], "title": m["title"],
            "content_html": render_issue_body(issue, None, None, for_feed=True),
            "summary": issue_description(issue),
            "date_published": dt.datetime.combine(parse_date(m["date_published"]), dt.time(8, 0), dt.timezone.utc).isoformat(),
            "tags": [CONDITIONS[k]["short"] for k, v in m.get("conditions", {}).items() if v],
        })
    return {
        "version": "https://jsonfeed.org/version/1.1",
        "title": FEED_TITLE, "home_page_url": DIGEST_URL, "feed_url": DIGEST_URL + "feed.json",
        "description": FEED_DESC, "language": "en", "icon": ORG_LOGO, "favicon": ORG_LOGO,
        "authors": [{"name": ORG_NAME, "url": ORG_URL}],
        "items": items,
    }


# --------------------------------------------------------------------------
# Root index.html: add RSS discovery link (idempotent)
# --------------------------------------------------------------------------

def patch_root_index() -> bool:
    path = os.path.join(ROOT, "index.html")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            html_text = fh.read()
    except OSError:
        return False
    if 'type="application/rss+xml"' in html_text:
        return False
    tag = ('  <link rel="alternate" type="application/rss+xml" title="Post-viral research digest (RSS)" '
           f'href="{SITE}/digest/feed.xml">\n')
    if "</head>" not in html_text:
        return False
    html_text = html_text.replace("</head>", tag + "</head>", 1)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(html_text)
    return True


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def manifest_entry(issue: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": issue["id"], "year": issue["year"], "week": issue["week"],
        "title": issue_title(issue), "url": issue_url(issue["id"]),
        "path": f"digest/{issue['id']}.html", "data_path": f"digest/data/{issue['id']}.json",
        "date_published": issue["asof"], "window_start": issue["window_start"], "window_end": issue["window_end"],
        "widened": issue["widened"], "study_count": issue["study_count"], "trial_count": issue["trial_count"],
        "conditions": {k: len(v) for k, v in issue["studies"].items()},
        "generated_at": issue["generated_at"],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backfill", type=int, default=0, metavar="N", help="ensure the N most recent weeks that have data exist (walks back up to --max-weeks)")
    ap.add_argument("--max-weeks", type=int, default=104, help="how far back --backfill may look (default 104)")
    ap.add_argument("--allow-empty", action="store_true", help="publish the current week even with 0 studies and 0 trial updates")
    ap.add_argument("--force", action="store_true", help="recompute already-frozen backfilled weeks from current data")
    ap.add_argument("--today", default=None, help="override today's date (YYYY-MM-DD) for testing")
    args = ap.parse_args(argv)

    now = dt.datetime.now(dt.timezone.utc)
    today = parse_date(args.today) if args.today else now.date()
    if not today:
        print("Bad --today value", file=sys.stderr)
        return 2

    feeds = load_feeds()
    trials_doc = load_trials()
    if not feeds:
        print("No literature feeds found under data/; nothing to do.", file=sys.stderr)
        return 1

    os.makedirs(ISSUE_DATA_DIR, exist_ok=True)
    manifest_doc = load_json(MANIFEST, {}) or {}
    existing = {m["id"]: m for m in manifest_doc.get("issues", []) if isinstance(m, dict) and m.get("id")}
    issues: Dict[str, Dict[str, Any]] = {}
    for iid in list(existing):
        d = load_json(os.path.join(ISSUE_DATA_DIR, f"{iid}.json"))
        if isinstance(d, dict):
            issues[iid] = d
        else:
            del existing[iid]  # snapshot lost: drop from manifest

    current_id = iso_week_id(today)
    log = []

    # Current week (always recomputed from live data).
    cur = compute_issue(current_id, today, feeds, trials_doc, now)
    if cur["study_count"] == 0 and cur["trial_count"] == 0 and not args.allow_empty:
        log.append(f"{current_id}: no studies or trial updates in the window ending {today} - not published "
                   f"(feeds' latest pub_date {cur['feed_latest_pub_date']}); use --allow-empty to force")
        # If an earlier run this week published something, keep it.
    else:
        issues[current_id] = cur
        log.append(f"{current_id}: {cur['study_count']} studies, {cur['trial_count']} trial updates"
                   + (" (14-day window)" if cur["widened"] else ""))

    # Backfill: walk backwards from last week, keep weeks with content.
    if args.backfill > 0:
        found = 0
        monday_cur = dt.date.fromisocalendar(today.isocalendar()[0], today.isocalendar()[1], 1)
        for i in range(1, args.max_weeks + 1):
            if found >= args.backfill:
                break
            sunday = monday_cur - dt.timedelta(days=7 * (i - 1) + 1)
            iid = iso_week_id(sunday)
            if iid in issues and not args.force:
                found += 1
                continue
            bf = compute_issue(iid, sunday, feeds, trials_doc, now)
            if bf["strict_study_count"] == 0 and bf["strict_trial_count"] == 0:
                continue  # nothing in the week itself: do not widen into a duplicate of the previous issue
            issues[iid] = bf
            found += 1
            log.append(f"{iid}: backfilled {bf['study_count']} studies, {bf['trial_count']} trial updates"
                       + (" (14-day window)" if bf["widened"] else ""))
        if found < args.backfill:
            log.append(f"backfill: only {found} week(s) with data found in the last {args.max_weeks} weeks")

    # Persist snapshots + manifest.
    for iid, issue in issues.items():
        write_json(os.path.join(ISSUE_DATA_DIR, f"{iid}.json"), issue)
    manifest = sorted((manifest_entry(i) for i in issues.values()), key=lambda m: m["id"], reverse=True)
    write_json(MANIFEST, {"generated": now.isoformat(timespec="seconds"), "site": DIGEST_URL,
                          "feed": DIGEST_URL + "feed.xml", "count": len(manifest), "issues": manifest})

    # Render every issue page (so prev/next links stay correct).
    for idx, m in enumerate(manifest):
        prev_i = manifest[idx + 1] if idx + 1 < len(manifest) else None
        next_i = manifest[idx - 1] if idx > 0 else None
        write_text(os.path.join(DIGEST_DIR, f"{m['id']}.html"), render_issue_page(issues[m["id"]], prev_i, next_i))
    write_text(os.path.join(DIGEST_DIR, "index.html"), render_index(manifest, now.isoformat()))
    write_text(os.path.join(DIGEST_DIR, "feed.xml"), build_rss(manifest, issues, now))
    write_json(os.path.join(DIGEST_DIR, "feed.json"), build_jsonfeed(manifest, issues))
    if patch_root_index():
        log.append("index.html: added RSS <link rel=alternate> to <head>")

    print("\n".join(log) if log else "Nothing changed.")
    print(f"digest: {len(manifest)} issue(s) in archive; wrote digest/index.html, feed.xml, feed.json, archive.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
