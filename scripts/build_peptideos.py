#!/usr/bin/env python3
"""Build PeptideOS (research.opensourcemed.info/peptideos/) from verified YAML records.

    python scripts/build_peptideos.py                    # validate + lint + render
    python scripts/build_peptideos.py --refresh-trials   # also refresh ClinicalTrials.gov denominators
    python scripts/build_peptideos.py --check            # validate + lint only

Records: peptideos/data/compounds/<slug>.yaml (protocol: peptideos/data/RESEARCH_PROTOCOL.md).
Any schema or editorial-lint violation, or a failed source check recorded in
peptideos/data/source-check.json (scripts/verify_peptideos_sources.py), exits 1 and writes nothing.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date
from html import escape as esc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from peptideos_lib import (CLASSES, DATA, JURIS, PEP, REG_STATUS, SAFETY, TIER_LABEL, TIER_SHORT, TIERS, TRIALS,  # noqa: E402
                           WADA, best_tier, load_all, main_class)

SITE = "https://research.opensourcemed.info/peptideos/"
REPO = "https://github.com/MattH55/osmf-research-tracker"
SRC = REPO + "/blob/main/peptideos/"
TODAY = date.today().isoformat()
CHECK = PEP / "data" / "source-check.json"
GA = "G-202S9N21TE"

STANDING = {
    "B": ("This compound is an investigational drug. It is not approved in any jurisdiction. There is no lawful "
          "supply. Any material sold under this name is of unverified origin, and is neither manufactured nor "
          "tested to pharmaceutical standards."),
    "C": ("This compound is not approved as a medicine in any jurisdiction tracked here and has no active sponsor "
          "seeking approval. Material sold under this name, typically labelled “research chemical, not for human "
          "consumption”, is of unverified identity and purity and is not manufactured to pharmaceutical standards."),
}


# ── page chrome ──────────────────────────────────────────────────────────
def page(*, title: str, desc: str, path: str, body: str, active: str = "", reviewed: str = TODAY,
         source: str = "", jsonld: list | None = None, extra_head: str = "") -> str:
    depth = path.count("/")
    up = "../" * depth
    canon = SITE + (path[:-10] if path.endswith("index.html") else path)
    nav = [("index.html", "Compounds", "idx"), ("methods.html", "Method", "methods"),
           ("what-we-wont-tell-you.html", "What we won’t tell you", "wont"), ("purity.html", "Purity", "purity"),
           ("data.html", "Open data", "data")]
    navh = "".join(f'<a href="{up}{h}"{" aria-current=\"page\"" if k == active else ""}>{t}</a>' for h, t, k in nav)
    src_link = f'<a href="{esc(source)}">source file</a>' if source else f'<a href="{REPO}/tree/main/peptideos">source</a>'
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{canon}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canon}">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}assets/peptideos.css">
<script async src="https://www.googletagmanager.com/gtag/js?id={GA}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{GA}');</script>
{ld}{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="mast"><div class="wrap">
<a class="brand" href="{up}index.html"><b>P/OS</b>PeptideOS <span>evidence &amp; status map</span></a>
<nav aria-label="PeptideOS">{navh}</nav>
</div></header>
<div class="docstrip"><div class="wrap"><span>OPEN SOURCE MEDICINE FOUNDATION</span><span>Last reviewed <b>{esc(str(reviewed))}</b></span><span>No dosing &middot; no vendors &middot; no advice</span><span>{src_link}</span></div></div>
<main id="main"><div class="wrap">
{body}
</div></main>
<footer class="foot"><div class="wrap cols">
<div class="coi"><p><strong>Conflict of interest.</strong> PeptideOS is published by the Open Source Medicine Foundation. No peptide vendor, manufacturer, compounding pharmacy or supplement company funds any part of it, and it carries no advertising or affiliate links. <a href="{up}coi-disclosure.html">Full disclosure</a>.</p>
<p>Information only. Nothing here is medical advice, and nothing here describes how to obtain or use any compound.</p></div>
<div><ul><li><a href="{up}corrections.html">Corrections log</a></li><li><a href="{up}coi-disclosure.html">COI disclosure</a></li><li><a href="{up}what-we-wont-tell-you.html">What we won’t tell you</a></li><li><a href="{up}methods.html">Evidence tier rubric</a></li></ul></div>
<div><ul><li><a href="{up}data.html">Open data (CC BY 4.0)</a></li><li><a href="{REPO}/tree/main/peptideos">GitHub</a></li><li><a href="https://research.opensourcemed.info/">OSMF Research</a></li><li><a href="mailto:contact@opensourcemed.info">contact@opensourcemed.info</a></li></ul></div>
</div></footer>
</body>
</html>
"""


# ── components ───────────────────────────────────────────────────────────
def tnum(t: str) -> int:
    return TIERS.index(t) + 1


def mini(tiers: set[str]) -> str:
    return '<div class="mini" aria-hidden="true">' + "".join(
        f'<i class="t{i + 1}{" on" if t in tiers else ""}"></i>' for i, t in enumerate(TIERS)) + "</div>"


def display_name(rec: dict) -> str:
    n = rec["names"]
    name = n.get("inn") or (n.get("common") or [rec["slug"]])[0]
    return name[:1].upper() + name[1:]


def matrix(evs: list[dict]) -> str:
    """Several claimed uses: one ladder per row, sharing the E1-E8 axis."""
    head = "".join(f'<th scope="col">{t}</th>' for t in TIERS)
    rows = "".join(
        f'<tr><th scope="row"><span class="chip t{tnum(e["tier"])}">{e["tier"]}</span> {esc(e["indication"])}</th>'
        + "".join(f'<td class="t{i + 1}{" on" if t == e["tier"] else ""}">{"<span>" + t + "</span>" if t == e["tier"] else ""}</td>'
                  for i, t in enumerate(TIERS)) + "</tr>"
        for e in evs)
    return (f'<div class="tablewrap"><table class="matrix"><caption class="kicker">Evidence tier for each claimed use &middot; '
            f'&larr; established &middot; unknown &rarr;</caption><thead><tr><th scope="col">Use</th>{head}</tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def cite_href(c: dict) -> str:
    if c.get("doi"):
        return "https://doi.org/" + c["doi"]
    if c.get("pmid"):
        return f"https://pubmed.ncbi.nlm.nih.gov/{c['pmid']}/"
    return c.get("url", "")


def trial_counts(rec: dict, refresh: bool) -> dict:
    TRIALS.mkdir(parents=True, exist_ok=True)
    f = TRIALS / f"{rec['slug']}.json"
    cache = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    queries = sorted({ev.get("trials_query") for ev in rec["evidence"] if ev.get("trials_query")})
    if refresh:
        for q in queries:
            try:
                base = "https://clinicaltrials.gov/api/v2/studies?" + urllib.parse.urlencode(
                    {"query.intr": q, "countTotal": "true", "pageSize": 1})
                tot = _ctgov_total(base)
                res = _ctgov_total(base + "&" + urllib.parse.urlencode({"aggFilters": "results:with"}))
                cache[q] = {"registered": tot, "with_results": res, "fetched": TODAY}
            except Exception as ex:  # keep the old count; never invent one
                print(f"  trials: {q}: {ex}", file=sys.stderr)
        f.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    return cache


def _ctgov_total(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "OSMF-PeptideOS/1.0 (contact@opensourcemed.info)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return int(json.load(r).get("totalCount", 0))


# ── compound page ────────────────────────────────────────────────────────
def compound_page(rec: dict, counts: dict) -> str:
    name = display_name(rec)
    n = rec["names"]
    cls = main_class(rec)
    cites: list[dict] = []
    idx: dict[str, int] = {}

    def ref(c: dict) -> str:
        key = str(c.get("doi") or c.get("pmid") or c.get("url") or c["title"]).lower()
        if key not in idx:
            cites.append(c)
            idx[key] = len(cites)
        k = idx[key]
        return f'<a class="ref" href="#c{k}">[{k}]</a>'

    evs = sorted(rec["evidence"], key=lambda e: TIERS.index(e["tier"]))
    # 1. tier ladders: one row per claimed use on a shared E1-E8 axis
    top = matrix(evs)
    # 2-3. sequence, names, class
    seq = rec.get("sequence")
    if seq:
        seqh = f'<p class="seq{" long" if len(seq) > 30 else ""}" aria-label="Amino acid sequence">{esc(seq)}</p>'
        seqnote = (f'<p class="seqnote">{esc(rec["sequence_note"])}</p>' if rec.get("sequence_note")
                   else f'<p class="seqnote">{len(seq)} residues &middot; one-letter code</p>')
    else:
        seqh = (f'<p class="seq struct" aria-label="Structure">{esc(rec["sequence_note"])}</p>' if rec.get("sequence_note") else "")
        seqnote = '<p class="seqnote">Non-standard residues or modifications: no plain one-letter sequence</p>' if seqh else ""
    bits = []
    alts = [x for x in n.get("common") or [] if x.lower() != name.lower() and x not in (n.get("codes") or [])]
    if alts: bits.append("Also: " + ", ".join(esc(x) for x in alts))
    if n.get("codes"): bits.append("Codes: " + ", ".join(esc(x) for x in n["codes"]))
    if n.get("brands"): bits.append("Brands: " + ", ".join(esc(x) for x in n["brands"]))
    if n.get("cas"): bits.append("CAS " + esc(n["cas"]))
    classrow = "".join(
        (f'<li class="cls-{c}" title="{JURIS[j]}: {CLASSES[c]}">{j} <b>{c}</b> {CLASSES[c].lower()}</li>' if c else
         f'<li class="unver" title="{JURIS[j]}: not verified">{j} <b>?</b> not verified</li>')
        for j, c in ((j, rec["class_by_jurisdiction"].get(j)) for j in JURIS))
    hero = (f'<div class="hero"><div class="kicker">Class {cls} &middot; {CLASSES[cls]}</div><h1>{esc(name)}</h1>'
            f'{seqh}{seqnote}<p class="names">{" &middot; ".join(bits)}</p>'
            f'<p class="lede">{esc(rec["what_it_is"])}</p><ul class="classrow" aria-label="Class by jurisdiction">{classrow}</ul></div>')

    secs = []
    # 4. regulatory
    notice = f'<div class="notice" role="note"><strong>Standing notice.</strong> {STANDING[cls]}</div>' if cls in STANDING else ""
    elsewhere = [j for j, c in rec["class_by_jurisdiction"].items() if c in ("B", "C")]
    if cls == "A" and elsewhere:
        approved = [j for j, c in rec["class_by_jurisdiction"].items() if c == "A"]
        notice = (f'<div class="notice" role="note"><strong>Standing notice.</strong> Approved in {", ".join(JURIS[j] for j in approved)} only. '
                  f'In {", ".join(JURIS[j] for j in elsewhere)} it is not an approved medicine: material sold there under this name '
                  'is of unverified origin and is not manufactured or tested to pharmaceutical standards there.</div>')
    by_j = {}
    for r in rec["regulatory"]:
        by_j.setdefault(r["jurisdiction"], []).append(r)
    rows = []
    missing = [j for j in JURIS if j not in by_j]
    for j in [j for j in JURIS if j in by_j]:
        for r in by_j[j]:
            rows.append(
                f'<tr><td class="j">{j}</td><td><span class="st">{REG_STATUS[r["status"]]}</span></td>'
                f'<td>{esc(r["detail"])}<blockquote>“{esc(r["quote"])}”</blockquote>'
                f'<span class="src"><a class="citeurl" href="{esc(r["source_url"])}">{esc(r.get("source_title") or urllib.parse.urlparse(r["source_url"]).hostname)}</a>'
                f' &middot; retrieved {esc(str(r["retrieved"]))}</span></td></tr>')
    if missing:
        rows.append(f'<tr><td class="j">{" ".join(missing)}</td><td colspan="2" class="unver">Not yet verified from a primary source. '
                    f'No status is shown rather than an unsourced one.</td></tr>')
    sport = rec.get("sport")
    sporth = ""
    if sport:
        why = esc(sport.get("detail") or "")
        if not why and sport["wada_status"] == "not_prohibited" and cls == "A":
            why = ("Not named on the Prohibited List. As an approved medicine it also falls outside class S0, "
                   "which covers only substances without current regulatory approval:")
        sporth = (f'<p class="notice" style="margin-top:14px"><strong>Sport (WADA):</strong> {WADA[sport["wada_status"]]}'
                  f'{" &middot; class " + esc(sport["wada_class"]) if sport.get("wada_class") else ""}. {why} '
                  f'“{esc(sport.get("quote", ""))}” <a class="citeurl" href="{esc(sport["source_url"])}">WADA source</a></p>')
    secs.append(("Regulatory status, by jurisdiction",
                 notice + f'<div class="tablewrap"><table class="reg"><thead><tr><th>Jurisdiction</th><th>Status</th><th>Detail and primary source</th></tr></thead>'
                 f'<tbody>{"".join(rows)}</tbody></table></div>{sporth}'))
    # 5. human evidence
    evh = []
    for e in evs:
        rcts, anyh = e.get("human_rcts"), e.get("human_trials_any")
        fmt = lambda v: "n/c" if v is None else v  # noqa: E731
        c = counts.get(e.get("trials_query") or "", {})
        reg = (f'<div><b>{c["registered"]}</b><span>registered studies</span></div>'
               f'<div><b>{c["with_results"]}</b><span>with posted results</span></div>') if c else ""
        absent = ""
        if rcts == 0:
            absent = ('<p class="absent">No randomised controlled trial in humans has been published for this use.</p>'
                      if anyh else '<p class="absent">No human trial of any design has been published for this use.</p>')
        crefs = "".join(f'<li>{ref(ci)} {esc(ci.get("finding") or "")}</li>' for ci in e.get("citations") or [])
        query = (f'<p class="muted" style="font-size:.82rem">Registered-study counts: ClinicalTrials.gov intervention search '
                 f'“{esc(e["trials_query"])}”, fetched {esc(c["fetched"])}. Registered studies include trials of other '
                 f'uses; the gap between registered and reported is itself a finding.</p>') if c else ""
        evh.append(f'<div class="indic"><div class="indic-head"><span class="chip t{tnum(e["tier"])}">{e["tier"]}</span>'
                   f'<h3>{esc(e["indication"])}</h3></div>{absent}<div class="counts"><div><b>{fmt(rcts)}</b><span>published human RCTs</span></div>'
                   f'<div><b>{fmt(anyh)}</b><span>published human trials</span></div>{reg}</div>'
                   f'{"<p class=muted style=font-size:.82rem>n/c: not counted here; see the cited review.</p>" if rcts is None or anyh is None else ""}<p>{esc(e["summary"])}</p>'
                   f'{"<ul class=cites>" + crefs + "</ul>" if crefs else ""}{query}</div>')
    tr = rec.get("trials") or []
    if tr:
        evh.append('<h3>Key registered trials</h3><div class="tablewrap"><table class="trials"><thead><tr><th>NCT</th><th>Title (as registered)</th><th>Phase</th><th>Status</th></tr></thead><tbody>'
                   + "".join(f'<tr><td><a href="https://clinicaltrials.gov/study/{t["nct"]}">{t["nct"]}</a></td><td>{esc(t["title"])}</td>'
                             f'<td>{esc(str(t.get("phase") or ""))}</td><td>{esc(str(t.get("status") or ""))}</td></tr>' for t in tr)
                   + "</tbody></table></div>")
    secs.append(("What the human evidence shows", "".join(evh)))
    # 6. safety
    sf = rec["safety"]
    sig = sf.get("known_signals") or []
    sh = f'<div class="grade"><b>{sf["grade"]}</b><span>{esc(SAFETY[sf["grade"]])}</span></div>'
    if sf.get("no_data_statement"):
        sh += '<p class="absent">There are no adequate human safety data. The absence of reported harm is not evidence of safety.</p>'
    if sig:
        sh += '<ul class="signals">' + "".join(
            f'<li class="signal"><span class="signal-title">{esc(s["signal"])}</span> {ref(s["citation"])}<br>{esc(s.get("evidence") or "")}</li>'
            for s in sig) + "</ul>"
    elif not sf.get("no_data_statement"):
        sh += "<p>No specific safety signal is recorded here; see the cited trials and label.</p>"
    secs.append(("Safety signals", sh))
    # 7. unknowns
    secs.append(("What is unknown", '<ul class="unknowns">' + "".join(f"<li>{esc(u)}</li>" for u in rec["unknowns"]) + "</ul>"))
    # 8. purity
    secs.append(("Product quality", '<p>No independent purity results have been published for this compound yet. '
                 'The <a href="../purity.html">purity programme</a> will publish full methods and vendor-named results, passes and failures, '
                 'once its protocol has had legal review.</p>'))
    # 9. citations
    cl = "".join(
        f'<li id="c{i}">{esc(c["title"])}{(" (" + str(c["year"]) + ")") if c.get("year") else ""}. '
        f'<a class="citeurl" href="{esc(cite_href(c))}">{esc("doi:" + c["doi"] if c.get("doi") else ("PMID " + str(c["pmid"]) if c.get("pmid") else cite_href(c)))}</a></li>'
        for i, c in enumerate(cites, 1))
    secs.append(("Citations", (f'<ol class="cites">{cl}</ol>' if cl else '<p class="muted">No efficacy literature exists to cite.</p>')
                 + '<p class="muted" style="font-size:.85rem">Every DOI is resolved against Crossref and every NCT number against '
                   'ClinicalTrials.gov, title for title, before publication. Regulatory sources are cited inline above with a verbatim quote and retrieval date.</p>'))
    # 10. mechanism last
    if rec.get("mechanism"):
        secs.append(("Mechanism", f'<p class="mech">{esc(rec["mechanism"])}</p><p class="muted" style="font-size:.85rem">'
                     'Mechanism is placed last on purpose: a plausible mechanism is not evidence that a compound works in people.</p>'))
    body_secs = "".join(f'<section class="sec"><h2><span class="n">{i:02d}</span>{t}</h2>{b}</section>' for i, (t, b) in enumerate(secs, 1))
    rv = f'<p class="muted" style="font-size:.85rem;margin-top:30px">Reviewed by {esc(rec["reviewer"])} on {esc(str(rec["last_reviewed"]))}. ' \
         f'Found an error? It goes in the <a href="../corrections.html">corrections log</a>: <a href="mailto:contact@opensourcemed.info?subject=PeptideOS%20correction:%20{esc(rec["slug"])}">report it</a>.</p>'
    best = best_tier(rec)
    desc = (f"{name}: evidence tier {best} ({TIER_SHORT[best]}), regulatory status in {len(JURIS)} jurisdictions with primary sources, "
            f"safety grade {sf['grade']}, and what is unknown. No dosing, no vendors.")[:300]
    ld = [{"@context": "https://schema.org", "@type": "MedicalWebPage", "name": f"{name} — PeptideOS",
           "url": SITE + f"compounds/{rec['slug']}.html", "lastReviewed": str(rec["last_reviewed"]),
           "reviewedBy": {"@type": "Organization", "name": "Open Source Medicine Foundation"},
           "about": {"@type": "Drug", "name": name, "alternateName": [x for x in (n.get("common") or []) + (n.get("codes") or []) if x != name] or None,
                     "nonProprietaryName": n.get("inn") or None},
           "isAccessibleForFree": True},
          {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "PeptideOS", "item": SITE},
              {"@type": "ListItem", "position": 2, "name": name, "item": SITE + f"compounds/{rec['slug']}.html"}]}]
    first = ('<p class="kicker"><a href="../index.html">&larr; All compounds</a> &middot; evidence tier first, by design</p>'
             f'<section aria-label="Evidence tier by indication">{top}</section>')
    return page(title=f"{name}: evidence tier, regulatory status and safety | PeptideOS", desc=desc,
                path=f"compounds/{rec['slug']}.html", body=first + hero + body_secs + rv, active="idx",
                reviewed=rec["last_reviewed"], source=SRC + f"data/compounds/{rec['slug']}.yaml", jsonld=ld)


# ── index (the thesis) ───────────────────────────────────────────────────
def index_page(recs: list[dict]) -> str:
    N = len(recs)
    no_rct = [r for r in recs if all(e.get("human_rcts") == 0 for e in r["evidence"])]
    claimed_gap = [r for r in recs if any(e.get("human_rcts") == 0 for e in r["evidence"])]
    dist = {t: 0 for t in TIERS}
    for r in recs:
        for e in r["evidence"]:
            dist[e["tier"]] += 1
    mx = max(dist.values() or [1]) or 1
    ramp = "".join(
        f'<div title="{t}: {dist[t]} indication{"s" if dist[t] != 1 else ""}"><span class="bar" style="height:{max(2, round(40 * dist[t] / mx))}px;background:var(--e{i + 1})"></span>'
        f'<span class="lab">{t}&middot;{dist[t]}</span></div>' for i, t in enumerate(TIERS))
    bands = []
    for t in TIERS:
        rs = [r for r in recs if best_tier(r) == t]
        if not rs:
            continue
        cards = []
        for r in sorted(rs, key=lambda r: display_name(r).lower()):
            tiers = {e["tier"] for e in r["evidence"]}
            cls = main_class(r)
            alt = [x for x in (r["names"].get("common") or []) + (r["names"].get("brands") or []) if x != display_name(r)][:3]
            jattr = " ".join(f'data-{j.lower()}="{c or ""}"' for j, c in r["class_by_jurisdiction"].items())
            wada = (r.get("sport") or {}).get("wada_status", "unknown")
            ind = "; ".join(f'{e["indication"]} ({e["tier"]})' for e in sorted(r["evidence"], key=lambda e: TIERS.index(e["tier"])))
            cards.append(
                f'<a class="card b{tnum(t)}" href="compounds/{r["slug"]}.html" data-class="{cls}" data-tiers="{" ".join(sorted(tiers))}" '
                f'data-wada="{wada}" {jattr}><div style="display:flex;justify-content:space-between;gap:8px;align-items:start">'
                f'<h3>{esc(display_name(r))}</h3><span class="clsbadge" title="Class {cls}: {CLASSES[cls]}">{cls} &middot; {CLASSES[cls].replace("Investigational", "Investig.")}</span></div>'
                f'<div class="alt">{esc(", ".join(alt))}</div>{mini(tiers)}<div class="ind">{esc(ind)}</div>'
                f'<div class="meta"><span>safety {r["safety"]["grade"]}</span><span>reviewed {esc(str(r["last_reviewed"]))}</span></div></a>')
        bands.append(f'<section class="band" data-band="{t}"><h2><span class="chip t{tnum(t)}">{t}</span>{esc(TIER_LABEL[t])}</h2>'
                     f'<div class="grid">{"".join(cards)}</div></section>')
    opts = lambda d: "".join(f'<option value="{k}">{esc(v)}</option>' for k, v in d.items())  # noqa: E731
    filters = (
        '<form class="filters noprint" id="flt" aria-label="Filter compounds" onsubmit="return false">'
        f'<label>Class<select name="class"><option value="">All classes</option>{opts({k: k + " · " + v for k, v in CLASSES.items()})}</select></label>'
        f'<label>Class in<select name="jur"><option value="">Best class anywhere</option>{opts(JURIS)}</select></label>'
        f'<label>Has an indication at<select name="tier"><option value="">Any tier</option>{opts({t: t + " · " + TIER_SHORT[t] for t in TIERS})}</select></label>'
        f'<label>WADA<select name="wada"><option value="">Any</option>{opts(WADA)}</select></label>'
        f'<span class="count" id="cnt" aria-live="polite">{N} compound{"s" if N != 1 else ""}</span></form>')
    js = """<script>
(function(){var f=document.getElementById('flt');if(!f)return;var cards=[].slice.call(document.querySelectorAll('.card'));
function run(){var c=f['class'].value,j=f.jur.value,t=f.tier.value,w=f.wada.value,n=0;
cards.forEach(function(el){var cls=j?el.getAttribute('data-'+j.toLowerCase()):el.dataset['class'];
var ok=(!c||cls===c)&&(!t||(' '+el.dataset.tiers+' ').indexOf(' '+t+' ')>-1)&&(!w||el.dataset.wada===w);el.hidden=!ok;if(ok)n++;});
[].forEach.call(document.querySelectorAll('.band'),function(b){b.hidden=!b.querySelector('.card:not([hidden])');});
document.getElementById('cnt').textContent=n+' of '+cards.length+' compounds';}
f.addEventListener('change',run);})();
</script>"""
    pct = round(100 * len(no_rct) / N) if N else 0
    thesis = (
        '<div class="thesis"><div><div class="kicker">PeptideOS &middot; therapeutic peptides, approved to gray market</div>'
        '<h1>What is the evidence that it works in people? Is it legal where you are?</h1>'
        '<p class="lede">An evidence and regulatory map with no dosing, no vendors and no advice. Every compound gets the same '
        'treatment: evidence tier first, regulatory status from primary sources, then what nobody knows. Mechanism comes last.</p></div>'
        f'<div><div class="stat">{len(no_rct)} of {N}<small>{'compound here has' if N == 1 else 'compounds here have'} no published randomised human trial for <em>any</em> use. '
        f'{len(claimed_gap)} {"has" if len(claimed_gap) == 1 else "have"} at least one claimed use with none.</small></div>'
        f'<div class="ramp" role="img" aria-label="Indications by evidence tier: {", ".join(f"{t} {dist[t]}" for t in TIERS)}">{ramp}</div></div></div>')
    if not N:
        thesis += '<p class="absent">No compound has completed source verification yet.</p>'
    legend = ('<p class="muted" style="font-size:.88rem">Sorted by the best-supported use, strongest first. Tiers run from '
              '<span class="chip t1">E1</span> multiple adequate RCTs to <span class="chip t8">E8</span> no published efficacy evidence in any model; '
              'colour encodes knowledge, not danger (<a href="methods.html">rubric</a>). Each small bar marks one claimed use.</p>')
    ld = [{"@context": "https://schema.org", "@type": "Dataset", "name": "PeptideOS evidence and regulatory map",
           "description": "Evidence tiers, regulatory status by jurisdiction with primary-source quotes, safety grades and documented unknowns for therapeutic peptides.",
           "url": SITE, "license": "https://creativecommons.org/licenses/by/4.0/", "dateModified": TODAY,
           "creator": {"@type": "Organization", "name": "Open Source Medicine Foundation", "url": "https://opensourcemed.info"},
           "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": SITE + "data/peptideos.json"},
                            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": SITE + "data/peptideos.csv"}]}]
    return page(title="PeptideOS: evidence tiers and regulatory status for therapeutic peptides",
                desc=f"{N} peptides from semaglutide to BPC-157, each graded E1–E8 for human evidence, with regulatory status in 7 jurisdictions from primary sources. No dosing, no vendors.",
                path="index.html", body=thesis + filters + legend + "".join(bands) + js, active="idx", jsonld=ld)


# ── static pages ─────────────────────────────────────────────────────────
def methods_page(recs) -> str:
    rows = "".join(f'<tr><td><span class="chip t{tnum(t)}">{t}</span></td><td>{esc(TIER_LABEL[t])}</td></tr>' for t in TIERS)
    srows = "".join(f'<tr><td class="mono">{k}</td><td>{esc(v)}</td></tr>' for k, v in SAFETY.items())
    body = f"""<div class="prose"><div class="kicker">Method</div><h1>How a compound is graded</h1>
<p class="lede">Every record answers three questions: what the human evidence shows, what the regulatory status is, and what is actually in the vial. The rules below are applied the same way to an approved drug and to a research chemical.</p>
<h2>Evidence tier (per claimed use)</h2>
<p>Each use the compound is <em>marketed or claimed</em> for is tiered separately, not only its approved use. A compound with three claimed uses shows three ladders.</p>
<table><thead><tr><th>Tier</th><th>Definition</th></tr></thead><tbody>{rows}</tbody></table>
<p>&ldquo;Adequately powered&rdquo; means the trial was designed and sized for the outcome reported. Tiers are checked by the build: an E1 claim with fewer than two human RCTs, or an E6 claim with any human trial, fails and is not published.</p>
<h2>Safety grade</h2>
<table><thead><tr><th>Grade</th><th>Definition</th></tr></thead><tbody>{srows}</tbody></table>
<p>A documented harm is listed with its citation, in the only red on the site. Absence of data is stated and never presented as safety.</p>
<h2>Class</h2>
<p><strong>A, Approved:</strong> marketing authorisation in the jurisdiction. <strong>B, Investigational:</strong> in active, sponsored clinical development and not approved there. <strong>C, Gray market:</strong> neither. Class is assigned per jurisdiction: one compound can be A in one country and C in another.</p>
<h2>Verification</h2>
<ul>
<li>Every journal citation carries a DOI or PMID; a script resolves it against Crossref or PubMed and compares the title. A mismatch blocks publication.</li>
<li>Every NCT number is checked against the ClinicalTrials.gov API, title for title.</li>
<li>Every regulatory status cites a primary regulator source (FDA, EMA, MHRA, Health Canada, TGA, PMDA, NMPA, WADA), a verbatim quote and the date it was read. Where no source has been verified the table says so.</li>
<li>Registered-study counts come from the ClinicalTrials.gov API and are dated.</li>
<li>Editorial rules are enforced by a linter: no dose amounts, no administration language, no vendors or purchase language, no advice, no testimonials, no benefit verbs without a named model.</li>
</ul>
<p>Records are researched with AI assistance under a written <a href="{SRC}data/RESEARCH_PROTOCOL.md">protocol</a> and then machine-checked; every record names its reviewer and review date. The previous version of PeptideOS failed this standard, and was withdrawn (see the <a href="corrections.html">corrections log</a>).</p>
<h2>What this resource will not say</h2>
<p>No doses, no administration, no vendors, no advice: <a href="what-we-wont-tell-you.html">what we won&rsquo;t tell you, and why</a>.</p></div>"""
    return page(title="Evidence tier rubric and verification method | PeptideOS",
                desc="How PeptideOS grades human evidence (E1–E8), safety (S1–S5) and regulatory class, and how every citation and regulatory status is machine-checked.",
                path="methods.html", body=body, active="methods")


def wont_page() -> str:
    items = [
        ("Doses", "No dose amounts appear anywhere on this site, including the doses printed on approved labels. Approved drugs have a label and a prescriber; for everything else, a number on this page would be the first line of a usage guide.",
         "A dose table is the single line that turns an information resource into an instruction manual for unapproved drugs."),
        ("How to use it", "Nothing about reconstitution, injection, cycling, stacking, timing or storage.",
         "Usage guidance is the rest of the instruction manual."),
        ("Where to get it", "No vendor names, links, rankings or “reputable source” lists. Vendors will appear only as the subjects of published purity testing, with passes and failures.",
         "The existing peptide content ecosystem is paid for by sales. A resource that earns nothing when someone buys is the only kind that can be believed about whether the product works."),
        ("Whether you should take it", "No recommendations, no second-person advice, no testimonials or before-and-after stories.",
         "That decision belongs to a person and their clinician, with the evidence in front of them. Anecdote is not evidence, and it is the main form of marketing in this market."),
        ("That a mechanism means it works", "Mechanisms are described last on every page, in neutral language, with the model named (“in rats”, “in cultured cells”).",
         "A plausible mechanism reads like evidence to a non-specialist and costs nothing to assert."),
    ]
    rows = "".join(f'<h2>{esc(h)}</h2><p>{esc(a)}</p><p class="muted"><strong>Why:</strong> {esc(b)}</p>' for h, a, b in items)
    body = f"""<div class="prose"><div class="kicker">Editorial policy</div><h1>What we won&rsquo;t tell you</h1>
<p class="lede">PeptideOS answers three questions about each compound: what the human evidence shows, what its legal status is, and what is actually in the vial. It does not answer the questions below, on any page, in any format.</p>
{rows}
<h2>How this is enforced</h2>
<p>These rules are code, not intentions. The build runs a linter over every record and refuses to publish one that contains a dose amount, administration language, a vendor or purchase phrase, second-person advice, a testimonial, or a benefit claim without a named model. The rules and the linter are <a href="{REPO}/blob/main/scripts/peptideos_lib.py">public</a>.</p>
<p>If you need dosing information for an approved medicine, it is on the official label and comes from your prescriber or pharmacist.</p></div>"""
    return page(title="What we won’t tell you: no doses, no vendors, no advice | PeptideOS",
                desc="PeptideOS publishes no doses, no administration guidance, no vendors and no advice about any peptide. Why, and how the rule is enforced in code.",
                path="what-we-wont-tell-you.html", body=body, active="wont")


def purity_page() -> str:
    body = """<div class="prose"><div class="kicker">Purity programme &middot; not started</div><h1>What is actually in the vial?</h1>
<p class="lede">For a gray-market compound, the live question is often not what it does in a rat but what was sold. No published results exist here yet, and none will appear until the protocol below has had legal review.</p>
<h2>Planned design</h2>
<table><thead><tr><th>Element</th><th>Plan</th></tr></thead><tbody>
<tr><td>Procurement</td><td>Blinded retail purchase, documented chain of custody from purchase to laboratory.</td></tr>
<tr><td>Assay panel</td><td>Identity (LC-MS/MS), purity (HPLC), quantity against label claim, endotoxin (LAL), sterility; for lyophilised injectables, visible particulates and residual solvents.</td></tr>
<tr><td>Laboratory</td><td>Independent analytical laboratory with no commercial relationship to any vendor.</td></tr>
<tr><td>Publication</td><td>Full methods and full results, vendor-named, passes and failures alike, in a form a critic could replicate.</td></tr>
</tbody></table>
<h2>Status</h2>
<p>Not started. Purchasing unapproved drugs, even for analysis, raises legal questions that differ by jurisdiction, so counsel reviews the protocol before any procurement. This page will say when that has happened.</p>
<p>Purity results do not imply that a product is safe or effective to use. A pure compound with no human evidence is still a compound with no human evidence.</p></div>"""
    return page(title="Purity programme: independent testing of gray-market peptides | PeptideOS",
                desc="The PeptideOS purity programme plan: blinded procurement, LC-MS/MS identity, HPLC purity, endotoxin and sterility testing, vendor-named results. Not yet started.",
                path="purity.html", body=body, active="purity")


def coi_page() -> str:
    body = """<div class="prose"><div class="kicker">Governance</div><h1>Conflict of interest disclosure</h1>
<p class="lede">PeptideOS is published by the Open Source Medicine Foundation (OSMF). This page states who is responsible for it, how it is paid for and what it refuses.</p>
<h2>What PeptideOS refuses</h2>
<ul><li>Funding of any kind from peptide vendors, manufacturers, compounding pharmacies or supplement companies, including &ldquo;educational grants&rdquo;.</li>
<li>Advertising, sponsored content, affiliate links and referral fees.</li>
<li>Any arrangement that lets a funder see or change a record before publication.</li></ul>
<p>If any of this ever changes, this page changes first.</p>
<h2>Funding</h2>
<p>PeptideOS has no dedicated external funding. It is maintained as part of OSMF&rsquo;s open research work. Specific funding sources, if any are received, will be listed here with amounts and terms before the money is used.</p>
<p class="muted">An earlier version of this page listed grants and amounts that could not be substantiated. It was withdrawn on 2026-10-10; see the <a href="corrections.html">corrections log</a>.</p>
<h2>Responsibility</h2>
<p>Editorial responsibility rests with OSMF. Each compound record names its reviewer and review date. Records are researched with AI assistance under a written protocol and machine-checked against Crossref, ClinicalTrials.gov and primary regulator sources before publication.</p>
<h2>Related work</h2>
<p>OSMF also runs clinical research of its own. If OSMF ever studies a compound listed here, the compound page will say so at the top.</p>
<h2>Contact</h2>
<p><a href="mailto:contact@opensourcemed.info">contact@opensourcemed.info</a></p></div>"""
    return page(title="Conflict of interest disclosure | PeptideOS",
                desc="Who publishes PeptideOS, how it is funded, and what it refuses: no vendor, manufacturer or supplement money, no ads, no affiliate links.",
                path="coi-disclosure.html", body=body)


CORRECTIONS = [
    ("2026-10-10", "Previous compound content and funding disclosure withdrawn",
     "An audit found that the first version of PeptideOS cited DOIs and ClinicalTrials.gov numbers that did not correspond to the claimed papers or trials: of 26 DOIs checked, 18 did not resolve and 7 of the 8 that did pointed to unrelated papers; all 5 NCT numbers checked were wrong. The conflict-of-interest page listed grants and amounts that could not be substantiated. All of that content has been withdrawn. Every record now published was rebuilt from scratch under a written protocol and passes automated checks: titles matched against Crossref and ClinicalTrials.gov, and regulatory statuses quoted from primary regulator pages with retrieval dates. Dose amounts, including label doses, are no longer shown anywhere."),
    ("2026-07-13", "Initial launch", "First build of PeptideOS governance pages, schema and lint rules."),
]


def corrections_page() -> str:
    items = "".join(f'<li><time datetime="{d}">{d}</time><h3>{esc(h)}</h3><p>{esc(t)}</p></li>' for d, h, t in CORRECTIONS)
    body = f"""<div class="prose"><div class="kicker">Governance</div><h1>Corrections log</h1>
<p class="lede">Every substantive correction is recorded here, newest first. Earlier versions of every page remain in the <a href="{REPO}/commits/main/peptideos">public history</a>.</p>
<ul class="log">{items}</ul>
<h2>Report an error</h2>
<p>Email <a href="mailto:contact@opensourcemed.info?subject=PeptideOS%20correction">contact@opensourcemed.info</a> or <a href="{REPO}/issues">open an issue</a>. Factual errors (a wrong source, a wrong tier, a wrong status) are fixed first.</p></div>"""
    return page(title="Corrections log | PeptideOS",
                desc="Public log of corrections to PeptideOS, including the October 2026 withdrawal of unverifiable citations and funding claims.",
                path="corrections.html", body=body)


# ── open data ────────────────────────────────────────────────────────────
def export(recs: list[dict]) -> None:
    out = PEP / "data"
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in recs]
    payload = {"name": "PeptideOS", "license": "CC-BY-4.0", "generated": TODAY, "publisher": "Open Source Medicine Foundation",
               "tiers": TIER_LABEL, "safety_grades": SAFETY, "classes": CLASSES, "compounds": clean}
    (out / "peptideos.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["slug", "name", "indication", "tier", "human_rcts", "human_trials_any", "safety_grade", *[f"class_{j}" for j in JURIS],
                "wada_status", "last_reviewed"])
    for r in recs:
        for e in r["evidence"]:
            w.writerow([r["slug"], display_name(r), e["indication"], e["tier"], e.get("human_rcts", 0), e.get("human_trials_any", 0),
                        r["safety"]["grade"], *[r["class_by_jurisdiction"].get(j) or "" for j in JURIS],
                        (r.get("sport") or {}).get("wada_status", ""), r["last_reviewed"]])
    (out / "peptideos.csv").write_text(buf.getvalue(), encoding="utf-8")


def data_page(recs) -> str:
    body = f"""<div class="prose"><div class="kicker">Open data</div><h1>Download the dataset</h1>
<p class="lede">Every record behind these pages, under <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Cite as: Open Source Medicine Foundation, <em>PeptideOS evidence and regulatory map</em>, {TODAY[:7]}.</p>
<div class="dl"><a href="data/peptideos.json">peptideos.json</a><a href="data/peptideos.csv">peptideos.csv (one row per use)</a><a href="{REPO}/tree/main/peptideos/data/compounds">YAML sources on GitHub</a></div>
<p>The JSON holds the complete records: names, sequence, class by jurisdiction, evidence by indication with citations, safety signals, regulatory statuses with source URLs, verbatim quotes and retrieval dates, and documented unknowns. {len(recs)} compounds as of {TODAY}.</p>
<p>Institutions that want a maintained feed or a licence on other terms can write to <a href="mailto:contact@opensourcemed.info">contact@opensourcemed.info</a>.</p></div>"""
    return page(title="Open data: PeptideOS dataset (JSON, CSV, CC BY) | PeptideOS",
                desc="Download PeptideOS as JSON or CSV under CC BY 4.0: evidence tiers, regulatory status with primary-source quotes and safety grades for therapeutic peptides.",
                path="data.html", body=body, active="data")


# ── checks on output ─────────────────────────────────────────────────────
def source_check_errors(recs) -> list[str]:
    if not CHECK.exists():
        return []
    chk = json.loads(CHECK.read_text(encoding="utf-8"))
    live = {r["slug"] for r in recs}
    return [f"source-check: {f['slug']}: {f['what']}" for f in chk.get("failures", []) if f.get("slug") in live]


def css_signal_lint() -> list[str]:
    errs = []
    css = (PEP / "assets" / "peptideos.css").read_text(encoding="utf-8")
    for m in re.finditer(r"([^{}]+)\{([^}]*var\(--signal\)[^}]*)\}", css):
        sel = m.group(1).strip()
        if not all(re.match(r"\.signal", s.strip()) for s in sel.split(",")):
            errs.append(f"peptideos.css: --signal used outside .signal rules: {sel}")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh-trials", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    recs, errs = load_all()
    errs += css_signal_lint() + source_check_errors(recs)
    if errs:
        print(f"PeptideOS: {len(errs)} problem(s); nothing written.", file=sys.stderr)
        for e in errs:
            print("  " + e, file=sys.stderr)
        return 1
    print(f"PeptideOS: {len(recs)} records valid and lint-clean.")
    if a.check:
        return 0
    (PEP / "compounds").mkdir(exist_ok=True)
    keep = set()
    for r in recs:
        out = PEP / "compounds" / f"{r['slug']}.html"
        out.write_text(compound_page(r, trial_counts(r, a.refresh_trials)), encoding="utf-8")
        keep.add(out.name)
    for old in (PEP / "compounds").glob("*.html"):
        if old.name not in keep:
            old.unlink()
    pages = {"index.html": index_page(recs), "methods.html": methods_page(recs), "what-we-wont-tell-you.html": wont_page(),
             "purity.html": purity_page(), "coi-disclosure.html": coi_page(), "corrections.html": corrections_page(),
             "data.html": data_page(recs)}
    for name, html_ in pages.items():
        (PEP / name).write_text(html_, encoding="utf-8")
    export(recs)
    print(f"Wrote {len(recs)} compound pages and {len(pages)} site pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
