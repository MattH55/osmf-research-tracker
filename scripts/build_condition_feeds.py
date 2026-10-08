#!/usr/bin/env python3
"""
Build per-condition RSS / JSON feeds of new and updated clinical trials.

    python scripts/build_condition_feeds.py          # idempotent, no network, safe to run daily

Outputs (all under feeds/):
    <condition-key>.xml    RSS 2.0  (validated with xml.etree before writing)
    <condition-key>.json   JSON Feed 1.1
    all.xml / all.json     union of every tracked trial
    index.html             listing of every condition feed (standard tracker chrome)

Source: clinical_trials/data/clinical_trials_current.json
(falls back to data/clinical_trials/clinical_trials_current.json).

A trial belongs to a condition when osmf_site.trial_matches() says so: either
its mapped_conditions[] carries the condition's label (e.g. "Long COVID / PASC"
-> long-covid) or, for conditions ClinicalTrials.gov does not label, a keyword
match on the title / raw conditions (pacvs, lyme, gulf-war-illness, pots, mcas).
Any mapped_conditions label not claimed by a condition in osmf_site.CONDITIONS
still gets a feed under a slug of the label, so nothing is silently dropped.

Each feed holds the MAX_ITEMS most recently updated trials, newest first.
trials_state.json does not record a first-seen date, so pubDate = last_updated.
"""
from __future__ import annotations

import datetime as dt
import email.utils
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from typing import Any, Dict, List

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from osmf_site import (  # noqa: E402
    CONDITIONS, ORG_LOGO, ORG_NAME, ORG_URL, SITE, as_list, breadcrumb_html, breadcrumb_jsonld,
    clean, esc, load_json, page, parse_date, phase_label, status_label, trial_matches,
    write_json, write_text,
)

FEEDS_DIR = os.path.join(ROOT, "feeds")
FEEDS_URL = f"{SITE}/feeds/"
MAX_ITEMS = 30
SUMMARY_CHARS = 300
ALL_KEY = "all"
ALL_META = {"name": "All tracked conditions", "short": "All conditions", "tracker": "/clinical_trials.html"}

SOURCES = [
    os.path.join(ROOT, "clinical_trials", "data", "clinical_trials_current.json"),
    os.path.join(ROOT, "data", "clinical_trials", "clinical_trials_current.json"),
]


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def load_trials() -> Dict[str, Any]:
    for path in SOURCES:
        d = load_json(path)
        if isinstance(d, dict) and isinstance(d.get("trials"), list):
            return d
    return {"last_run": "", "count": 0, "trials": []}


def slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return s or "unmapped"


def normalise(t: Dict[str, Any]) -> Dict[str, Any]:
    nct = clean(t.get("nct_id"))
    d = parse_date(t.get("last_updated"))
    return {
        "nct_id": nct,
        "title": clean(t.get("title")) or nct or "Untitled trial",
        "status": clean(t.get("status")) or "UNKNOWN",
        "phase": clean(t.get("phase")),
        "last_updated": d.isoformat() if d else "",
        "start_date": clean(t.get("start_date")),
        "agents": as_list(t.get("agents")),
        "summary": re.sub(r"\s+", " ", clean(t.get("brief_summary"))).strip(),
        "link": clean(t.get("link")) or f"https://clinicaltrials.gov/study/{nct}",
        "mapped_conditions": as_list(t.get("mapped_conditions")),
    }


def group_by_condition(trials: List[Dict[str, Any]]) -> "OrderedDict[str, Dict[str, Any]]":
    """Return {key: {"meta": {...}, "trials": [...]}} in CONDITIONS order, then unclaimed labels, then 'all'."""
    pairs = [(t, normalise(t)) for t in trials if isinstance(t, dict) and clean(t.get("nct_id"))]
    rows = [r for _, r in pairs]
    claimed = {lbl for m in CONDITIONS.values() for lbl in m["trial_labels"]}
    groups: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for key, meta in CONDITIONS.items():
        hits = [r for t, r in pairs if trial_matches(t, key)]
        if hits:
            groups[key] = {"meta": meta, "trials": hits}
    # Labels in mapped_conditions that no CONDITIONS entry claims.
    extra: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for r in rows:
        for lbl in r["mapped_conditions"]:
            if lbl and lbl not in claimed:
                extra.setdefault(lbl, []).append(r)
    for lbl, hits in extra.items():
        key = slug(lbl)
        if key not in groups:
            groups[key] = {"meta": {"name": lbl, "short": lbl, "tracker": "/clinical_trials.html"}, "trials": hits}
    groups[ALL_KEY] = {"meta": ALL_META, "trials": rows}
    for g in groups.values():
        g["trials"] = sorted(g["trials"], key=lambda r: (r["last_updated"], r["nct_id"]), reverse=True)[:MAX_ITEMS]
    return groups


# --------------------------------------------------------------------------
# Feeds
# --------------------------------------------------------------------------

def rfc822(d: dt.date) -> str:
    return email.utils.format_datetime(dt.datetime(d.year, d.month, d.day, 8, 0, tzinfo=dt.timezone.utc))


def iso_pub(d: dt.date) -> str:
    return dt.datetime.combine(d, dt.time(8, 0), dt.timezone.utc).isoformat()


def item_description(r: Dict[str, Any]) -> str:
    parts = [status_label(r["status"]), phase_label(r["phase"])]
    if r["agents"]:
        parts.append(", ".join(r["agents"][:5]))
    text = " · ".join(parts)
    if r["summary"]:
        s = r["summary"][:SUMMARY_CHARS]
        text += " — " + s + ("…" if len(r["summary"]) > SUMMARY_CHARS else "")
    return text


def feed_title(meta: Dict[str, Any]) -> str:
    return f"{meta['short']} clinical trials: new and updated - {ORG_NAME}"


def feed_desc(meta: Dict[str, Any]) -> str:
    return (f"ClinicalTrials.gov records for {meta['name']} that were newly registered or updated, as tracked by the "
            f"Open Source Medicine Foundation research tracker. The {MAX_ITEMS} most recently updated trials, newest first.")


def build_rss(key: str, meta: Dict[str, Any], rows: List[Dict[str, Any]], now: dt.datetime) -> str:
    ATOM = "http://www.w3.org/2005/Atom"
    ET.register_namespace("atom", ATOM)
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = feed_title(meta)
    ET.SubElement(ch, "link").text = SITE + meta["tracker"]
    ET.SubElement(ch, "description").text = feed_desc(meta)
    ET.SubElement(ch, "language").text = "en"
    ET.SubElement(ch, "lastBuildDate").text = email.utils.format_datetime(now)
    ET.SubElement(ch, "generator").text = "OSMF build_condition_feeds.py"
    ET.SubElement(ch, "ttl").text = "1440"
    ET.SubElement(ch, f"{{{ATOM}}}link", {"href": f"{FEEDS_URL}{key}.xml", "rel": "self", "type": "application/rss+xml"})
    img = ET.SubElement(ch, "image")
    ET.SubElement(img, "url").text = ORG_LOGO
    ET.SubElement(img, "title").text = feed_title(meta)
    ET.SubElement(img, "link").text = SITE + meta["tracker"]
    for r in rows:
        it = ET.SubElement(ch, "item")
        ET.SubElement(it, "title").text = r["title"]
        ET.SubElement(it, "link").text = r["link"]
        # guid changes when the registry record changes, so readers see updates as new entries.
        ET.SubElement(it, "guid", {"isPermaLink": "false"}).text = f"{r['nct_id']}:{r['last_updated']}"
        d = parse_date(r["last_updated"])
        if d:
            ET.SubElement(it, "pubDate").text = rfc822(d)
        ET.SubElement(it, "category").text = meta["short"]
        if r["status"]:
            ET.SubElement(it, "category").text = status_label(r["status"])
        ET.SubElement(it, "description").text = item_description(r)
    xml_bytes = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    ET.fromstring(xml_bytes)  # validate well-formedness before writing
    return xml_bytes.decode("utf-8")


def build_jsonfeed(key: str, meta: Dict[str, Any], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    items = []
    for r in rows:
        d = parse_date(r["last_updated"])
        item = {
            "id": f"{r['nct_id']}:{r['last_updated']}",
            "url": r["link"],
            "title": r["title"],
            "content_text": item_description(r),
            "summary": item_description(r)[:SUMMARY_CHARS],
            "tags": [meta["short"], status_label(r["status"])] + r["agents"][:5],
            "_osmf": {"nct_id": r["nct_id"], "status": r["status"], "phase": r["phase"],
                      "start_date": r["start_date"], "last_updated": r["last_updated"], "agents": r["agents"]},
        }
        if d:
            item["date_published"] = iso_pub(d)
            item["date_modified"] = iso_pub(d)
        items.append(item)
    return {
        "version": "https://jsonfeed.org/version/1.1",
        "title": feed_title(meta), "home_page_url": SITE + meta["tracker"], "feed_url": f"{FEEDS_URL}{key}.json",
        "description": feed_desc(meta), "language": "en", "icon": ORG_LOGO, "favicon": ORG_LOGO,
        "authors": [{"name": ORG_NAME, "url": ORG_URL}],
        "items": items,
    }


# --------------------------------------------------------------------------
# Index page
# --------------------------------------------------------------------------

def render_index(groups: "OrderedDict[str, Dict[str, Any]]", last_run: str, generated: str) -> str:
    title = "Clinical trial feeds by condition"
    desc = ("Follow one condition: per-condition RSS and JSON feeds of newly registered and updated ClinicalTrials.gov "
            "records for long COVID, ME/CFS, PACVS, Lyme/PTLDS, Gulf War Illness, POTS, MCAS and other post-viral syndromes.")
    crumbs = [("Research Tracker", SITE + "/"), ("Trial feeds", FEEDS_URL)]
    items = []
    for key, g in groups.items():
        meta, rows = g["meta"], g["trials"]
        latest = rows[0]["last_updated"] if rows else ""
        items.append(
            f'<li><a href="{SITE}{esc(meta["tracker"])}">{esc(meta["name"])}</a>'
            f'<div class="meta">{len(rows)} trials in feed{(" &middot; latest update " + esc(latest)) if latest else ""}</div>'
            f'<div><a class="btn ghost" href="{FEEDS_URL}{esc(key)}.xml">RSS</a>'
            f'<a class="btn ghost" href="{FEEDS_URL}{esc(key)}.json">JSON Feed</a></div></li>')
    ld = {
        "@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": FEEDS_URL,
        "isPartOf": {"@type": "WebSite", "name": "OSMF Research Tracker", "url": SITE + "/"},
        "publisher": {"@type": "Organization", "name": ORG_NAME, "url": ORG_URL},
        "hasPart": [{"@type": "DataFeed", "name": feed_title(g["meta"]), "url": f"{FEEDS_URL}{k}.xml"} for k, g in groups.items()],
    }
    hero = (f'<header class="hero"><div class="wrap"><div class="badge">Daily &middot; automated &middot; open data</div>'
            f'<h1>Clinical trial feeds by condition</h1><p>Subscribe to a single condition and get every ClinicalTrials.gov '
            f'record that is newly registered or updated, as the OSMF tracker picks it up. Each feed carries the '
            f'{MAX_ITEMS} most recently updated trials, newest first, in RSS 2.0 and JSON Feed 1.1.</p></div></header>')
    body = (f'{hero}<main id="main">{breadcrumb_html(crumbs)}'
            f'<h2 id="feeds">Feeds <span class="tag">{len(groups)} feeds</span></h2>'
            '<ol class="issue-list">' + "".join(items) + '</ol>'
            '<h2 id="how">How these feeds are built</h2>'
            '<p>A script (<code>scripts/build_condition_feeds.py</code>) runs after the daily ClinicalTrials.gov refresh. '
            'It groups the tracker\'s trial snapshot by condition (registry condition labels first, then keyword matches on '
            'the title for conditions the registry does not label) and writes the most recently updated records to each '
            'feed. An entry\'s date is the registry\'s last-update date; a registry update can be anything from a status '
            'change to an edited contact field. Entries are keyed by NCT number plus update date, so a trial reappears in '
            'your reader when its record changes.</p>'
            f'<p>Browse all tracked trials: <a href="{SITE}/clinical_trials.html">clinical trials tracker</a>. '
            f'Weekly literature summary: <a href="{SITE}/digest/">post-viral research digest</a>.</p>'
            '<div class="disclaimer"><strong>Disclaimer.</strong> These feeds are automated, unreviewed listings of '
            'ClinicalTrials.gov registry records compiled by the Open Source Medicine Foundation. Inclusion is not '
            'endorsement and is not medical advice. Discuss any treatment decision with a qualified clinician.</div>'
            '</main>')
    extra_head = "".join(
        f'\n<link rel="alternate" type="application/rss+xml" title="{esc(feed_title(g["meta"]))}" href="{FEEDS_URL}{esc(k)}.xml">'
        for k, g in groups.items())
    return page(title=title, description=desc, canonical=FEEDS_URL, body=body, jsonld=[ld, breadcrumb_jsonld(crumbs)],
                og_type="website", nav_active="/clinical_trials.html", extra_head=extra_head,
                footer_note=f"Feeds regenerated {generated[:10]} from trial snapshot {last_run[:10] or 'unknown'}.")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    doc = load_trials()
    trials = doc.get("trials", [])
    if not trials:
        print("No trials found in clinical_trials_current.json; nothing to do.", file=sys.stderr)
        return 1
    groups = group_by_condition(trials)
    os.makedirs(FEEDS_DIR, exist_ok=True)
    for key, g in groups.items():
        write_text(os.path.join(FEEDS_DIR, f"{key}.xml"), build_rss(key, g["meta"], g["trials"], now))
        write_json(os.path.join(FEEDS_DIR, f"{key}.json"), build_jsonfeed(key, g["meta"], g["trials"]))
        print(f"feeds/{key}.xml, feeds/{key}.json: {len(g['trials'])} trials")
    write_text(os.path.join(FEEDS_DIR, "index.html"), render_index(groups, clean(doc.get("last_run")), now.isoformat()))
    print(f"feeds: {len(groups)} condition feed(s) from {len(trials)} trials; wrote feeds/index.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
