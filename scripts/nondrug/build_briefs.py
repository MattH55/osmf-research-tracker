#!/usr/bin/env python3
"""Feature 2: printable one-page evidence briefs, one per RepurpOS condition.

Every section is computed from data already on the tracker and names its own scale; a section with
no data is omitted rather than padded:

  * Medicines with registered trials in this condition, parsed from the tracker condition page
    (the same list the research-note digests publish; non-drug arms removed). Scale: trial count.
    RepurpOS's gene-target ranking is NOT used here: a target link is a mechanistic signal, and on a
    printed brief it would read as a recommendation.
  * Non-drug approaches with completed trials and posted results (non-drug evidence map). Scale: trial status.
  * Natural products in the RepurpOS "Moderate" tier. Scale: RepurpOS tier label.
  * Biomarkers with a reported direction (biomarker atlas, where one exists). Scale: direction as reported.
  * Trials recruiting now (drug arms from the condition page, non-drug from the evidence map).
  * Evidence gaps (shared computation with the gap maps).
  * QR code and URL of the live page, sources, date, and the not-medical-advice line.

Writes briefs/index.html and briefs/<slug>.html.  Needs `segno` (requirements.txt).

    python scripts/nondrug/build_briefs.py
"""
from __future__ import annotations

import html as htmllib
import json
import re
import sys
from datetime import date
from pathlib import Path

import segno

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gaps import compute  # noqa: E402
from ndsite import ROOT, SITE, esc, load_dataset, shell, write  # noqa: E402
from taxonomy import ALL_CLASSES, classify  # noqa: E402

BIOMARKER_ALIASES = {
    "chronic-obstructive-pulmonary-disease": "copd", "myalgic-encephalomyelitis-chronic-fatigue-syndrome": "me-cfs",
    "post-acute-covidvaccination-syndrome": "pacvs", "inflammatory-bowel-disease": "inflammatory-bowel-disease-crohn-s-uc",
    "lyme-ptlds": "lyme", "nafld-mash": "nafld-mash-metabolic-associated-steatohepatitis",
}
PRINT_CSS = """
.brief{max-width:900px}
.brief-head{display:flex;gap:18px;align-items:flex-start;justify-content:space-between;border-bottom:2px solid #0e1444;padding-bottom:10px;margin-bottom:12px}
.brief-head h2{font-size:1.35rem;margin:0 0 4px}
.brief-head p{margin:0;font-size:.85rem;color:#525a73}
.brief-qr{flex:0 0 auto;text-align:center;font-size:.7rem;color:#525a73}
.brief-qr svg{display:block;width:96px;height:96px;margin:0 auto 2px}
.brief-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 22px}
.brief-sec h3{font-size:.82rem;letter-spacing:.06em;text-transform:uppercase;color:#0e1444;margin:8px 0 4px;border-bottom:1px solid rgba(14,20,68,.15);padding-bottom:2px}
.brief-sec .scale{font-size:.72rem;color:#525a73;margin:0 0 4px}
.brief-sec ul{margin:0;padding-left:16px}
.brief-sec li{font-size:.84rem;line-height:1.4;margin:0 0 2px}
.brief-sec li .m{color:#525a73;font-size:.76rem}
.brief-foot{margin-top:10px;border-top:1px solid rgba(14,20,68,.15);padding-top:6px;font-size:.74rem;color:#525a73;line-height:1.45}
.brief-foot strong{color:#0e1444}
.brief-print{margin:0 0 14px}
@media (max-width:700px){.brief-grid{grid-template-columns:1fr}.brief-head{flex-direction:column}}
@media print{
  @page{margin:11mm 12mm}  /* no forced size: fits the paper the reader selects (checked on A4 and US Letter) */
  body{background:#fff!important}
  header,nav,footer,.osmf-header,.osmf-footer,.skip,.crumbs,.page-hero,.brief-print,.no-print,#osmf-ui-header,#osmf-ui-footer{display:none!important}
  .main-section,.section-inner{padding:0!important;margin:0!important;max-width:none!important}
  .brief{max-width:none;font-size:9.4pt}
  .brief-sec li{font-size:8.6pt;line-height:1.3}
  .brief-sec h3{font-size:8pt;margin-top:5px}
  .brief-head h2{font-size:14pt}
  a{color:#0e1444!important;text-decoration:none!important}
  .brief p,.brief li,.brief .brief-foot{font-size:8.4pt!important;line-height:1.3!important}
  .brief .brief-sec .scale{font-size:7.4pt!important;line-height:1.25!important;margin:0 0 2px!important}
  .brief .brief-head p{font-size:8.2pt!important;margin:0!important}
  .brief .brief-head{padding-bottom:6px!important;margin-bottom:6px!important}
  .brief .brief-grid{gap:2px 18px!important}
  .brief .brief-sec ul{margin:0!important;padding-left:13px!important}
  .brief .brief-sec li{margin:0 0 1px!important}
  .brief .brief-qr svg{width:78px!important;height:78px!important}
  .brief .brief-foot{font-size:7.4pt!important;margin-top:6px!important}
}
"""


def text(s: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def medicines_from_condition_page(slug: str) -> list[dict]:
    """Agents with registered trials, as listed on /chronic-disease-interventions/<slug>.html (non-drug arms removed)."""
    p = ROOT / "chronic-disease-interventions" / f"{slug}.html"
    if not p.exists():
        return []
    markup = p.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'<p class="agent-name"[^>]*>(.*?)</p>\s*</div>\s*<p[^>]*>(.*?)</p>', markup, re.S):
        label = text(re.sub(r"<span.*?</span>", "", m.group(1), flags=re.S))
        meta = m.group(2)
        n = re.search(r"(\d+) trials?", meta)
        trials = int(n.group(1)) if n else 0
        if not label or len(label) > 60 or trials == 0 or classify(label, "OTHER") is not None:
            continue  # unnamed, overlong, no trial, or a non-drug arm
        out.append({"name": label, "approved": "Approved</span>" in meta, "trials": trials,
                     "ncts": list(dict.fromkeys(re.findall(r"study/(NCT\d+)", meta)))[:2]})
    out.sort(key=lambda a: (-a["trials"], not a["approved"], a["name"].lower()))
    seen, uniq = set(), []
    for a in out:  # "pregabalin" and "Pregabalin capsule" are one medicine
        key = re.sub(r"[^a-z0-9]", "", a["name"].lower().split()[0]) if a["name"].split() else a["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a)
    return uniq


def recruiting_from_condition_page(slug: str) -> list[dict]:
    p = ROOT / "chronic-disease-interventions" / f"{slug}.html"
    if not p.exists():
        return []
    markup = p.read_text(encoding="utf-8")
    out = []
    for m in re.finditer(r'<div class="trial-card">(.*?)</div>\s*(?=<div class="trial-card">|</div>\s*<)', markup, re.S):
        card = m.group(1)
        t = re.search(r'class="trial-title">(.*?)</a>', card, re.S)
        nct = re.search(r'class="trial-nct">(NCT\d+)<', card)
        status = re.search(r'<span style="background:[^"]*">([^<]+)</span>', card)
        if t and nct and status and text(status.group(1)).lower() in ("recruiting", "enrolling by invitation"):
            out.append({"nct": nct.group(1), "title": text(t.group(1))})
    return out


def biomarkers(slug: str) -> tuple[list[dict], str | None]:
    bslug = BIOMARKER_ALIASES.get(slug, slug)
    p = ROOT / "data" / "biomarkers" / f"{bslug}.json"
    if not p.exists():
        return [], None
    d = json.loads(p.read_text(encoding="utf-8"))
    marks = [m for m in d.get("markers") or [] if m.get("direction") in ("increased", "decreased", "up", "down", "higher", "lower")]
    page = f"/biomarkers/{bslug}/" if (ROOT / "biomarkers" / bslug).exists() else None
    return marks, page


def qr_svg(url: str) -> str:
    svg = segno.make(url, error="m").svg_inline(scale=3, dark="#0e1444", border=1)
    return re.sub(r'(<svg[^>]*?)>', r'\1 role="img" aria-label="QR code linking to this brief online">', svg, count=1)


def li(name: str, meta: str = "") -> str:
    return f"<li>{name}{(' <span class=m>' + meta + '</span>') if meta else ''}</li>"


def build() -> None:
    d = load_dataset()
    trials, conds, built = d["trials"], d["conditions"], d["built"]
    today = date.today()
    stamp = today.strftime("%d %B %Y").lstrip("0")
    idx_rows = []
    for slug, cm in sorted(conds.items(), key=lambda kv: kv[1]["name"].lower()):
        di = ROOT / "data" / "disease-intelligence" / f"{slug}.json"
        if not di.exists():
            continue
        dj = json.loads(di.read_text(encoding="utf-8"))
        name = cm["name"]
        path = f"briefs/{slug}.html"
        url = f"{SITE}/{path}"
        mine = {n: t for n, t in trials.items() if slug in t["c"]}
        g = compute(mine)
        secs = []

        meds = medicines_from_condition_page(slug)
        if meds:
            secs.append(("Medicines with registered trials", "Scale: trials listed for each medicine on the tracker's condition page, a snapshot of ClinicalTrials.gov. A trial means it is being studied, not that it works.",
                         [li(esc(a["name"]), f"{a['trials']} trial{'s' if a['trials'] != 1 else ''}{' · approved medicine' if a['approved'] else ''}") for a in meds[:6]]))

        catch_all = {"behavioural-other", "supplement-other"}  # vague buckets go last
        nd = sorted(((c, v) for c, v in g["class_tot"].items() if v["c"] or v["r"]),
                    key=lambda kv: (kv[0] in catch_all, -kv[1]["r"], -kv[1]["c"], -kv[1]["n"]))
        if nd:
            secs.append(("Non-drug approaches tested", "Scale: trial status on ClinicalTrials.gov (completed, results posted). Status is not a result.",
                         [li(esc(ALL_CLASSES[c].label), f"{v['n']} trials · {v['c']} completed · {v['r']} with results") for c, v in nd[:6]]))

        nps = [x for x in dj.get("natural_products") or [] if isinstance(x, dict) and x.get("evidence_tier") == "B"]
        names = list(dict.fromkeys((x.get("name") or "").strip() for x in nps if x.get("name")))
        if names:
            secs.append(("Natural products (RepurpOS Moderate tier)", "Scale: RepurpOS evidence tier, from linked trials and literature. Product quality and dose vary.",
                         [li(esc(n)) for n in names[:6]]))

        marks, bpage = biomarkers(slug)
        if marks:
            arrow = lambda dirn: "higher" if dirn in ("increased", "up", "higher") else "lower"
            secs.append(("Biomarkers reported", "Direction in patients compared with the stated comparison group, as reported in the cited study.",
                         [li(esc(m.get("name") or ""), f"{arrow(m['direction'])} · {esc((m.get('reference') or {}).get('citation') or '')}") for m in marks[:6]]))

        rec_drug = recruiting_from_condition_page(slug)[:3]
        rec_nd = sorted((n for n, t in mine.items() if t["g"] == "recruiting"), key=lambda n: -(mine[n]["n"] or 0) if isinstance(mine[n]["n"], int) else 0)[:3]
        short = lambda x: x if len(x) <= 85 else x[:84].rsplit(" ", 1)[0] + "…"
        rec = [li(esc(short(t["title"])), t["nct"]) for t in rec_drug] + [li(esc(short(mine[n]["t"])), n) for n in rec_nd]
        if rec:
            secs.append(("Trials recruiting", f"Status as recorded on ClinicalTrials.gov when searched ({cm.get('fetched_at') or built}); check the registry for current status and eligibility.", rec))

        capped = (cm.get("total") or 0) > (cm.get("fetched") or 0)
        gaps = [] if capped else [li(f"Among {gn} {esc(gl.lower())} trials found, none measured {esc(dl.lower())}", f"{n} trials of other approaches did")
                                  for n, gl, dl, gn in g["unmeasured"][:3]]
        gaps += [li(f"{esc(gl)}: {esc(dl.lower())}", f"{n} trials, no results posted yet") for n, gl, dl, _ in g["unreported"][:2]]
        if gaps:
            secs.append(("What we don't know yet", "Gaps in registered trials, from the evidence-gap map. A gap is not a recommendation.", gaps))

        if not secs:
            continue
        sections_html = "".join(f'<section class="brief-sec"><h3>{esc(t)}</h3><p class="scale">{esc(sc)}</p><ul>{"".join(items)}</ul></section>' for t, sc, items in secs)
        live = [f'<a href="/evidence-gaps/{slug}.html">evidence-gap map</a>']
        if cm.get("repurpos"):
            live.append(f'<a href="{esc(cm["repurpos"])}">RepurpOS</a>')
        if cm.get("page"):
            live.append(f'<a href="{esc(cm["page"])}">condition page</a>')
        if bpage:
            live.append(f'<a href="{bpage}">biomarker atlas</a>')
        body = f"""
<p class="brief-print no-print"><a class="btn" href="#" onclick="window.print();return false;">Print or save as PDF</a> <span class="nd-method">Fits on one A4 or Letter page.</span></p>
<article class="brief" aria-label="Evidence brief: {esc(name)}">
  <div class="brief-head">
    <div><h2>{esc(name)}: evidence brief</h2>
    <p>Open Source Medicine Foundation · page built {esc(stamp)} · trial data searched {esc(cm.get('fetched_at') or built)}{(' (capped at 1,000 of ' + format(cm['total'], ',') + ' matching trials)') if capped else ''} · {esc(url)}</p>
    <p><strong>Research information, not medical advice.</strong> Prepared to support a conversation with a clinician, not to choose a treatment.</p></div>
    <div class="brief-qr">{qr_svg(url)}Live version</div>
  </div>
  <div class="brief-grid">{sections_html}</div>
  <div class="brief-foot"><strong>Sources:</strong> ClinicalTrials.gov (trials, status, posted results); RepurpOS natural-product tiers (registry trials, PubMed, reference databases); OSMF biomarker atlas where available; OSMF non-drug evidence map ({len(mine):,} non-drug trials for this condition). Lists are shortened; the live pages carry every entry with its source: {' · '.join(live)}.
  Counts change daily. Nothing here is a recommendation to start, stop or change any treatment.</div>
</article>
"""
        desc = f"One-page printable evidence brief for {name}: medicines and non-drug approaches in registered trials, natural products, biomarkers, recruiting trials and evidence gaps."
        write(path, shell(path=path, title=f"{name}: one-page evidence brief"[:70], description=desc, eyebrow="Evidence brief · printable",
                          h1=name, h1_span="evidence brief", lede="One page, every section sourced. Print it or bring it on your phone.",
                          body=body, crumbs=[("Evidence briefs", f"{SITE}/briefs/index.html"), (name, url)], modified=today.isoformat())
              .replace("</style>", PRINT_CSS + "</style>", 1))
        idx_rows.append(f'<tr><th scope="row"><a href="/briefs/{slug}.html">{esc(name)}</a></th><td>{esc(", ".join(t for t, _, _ in secs))}</td></tr>')
    body = f"""<p class="lede">A printable one-page brief per condition: medicines and non-drug approaches in registered trials, natural products, biomarkers, recruiting trials and the evidence gaps. Each section names its scale and links to its source.</p>
<div class="disclaimer"><span>⚠️</span><div><strong>Research information, not medical advice.</strong> A brief summarises what is being studied. It does not recommend any treatment.</div></div>
<div class="tbl-wrap"><table class="nd-tbl"><thead><tr><th scope="col">Condition</th><th scope="col">Sections with data</th></tr></thead><tbody>{''.join(idx_rows)}</tbody></table></div>"""
    write("briefs/index.html", shell(path="briefs/index.html", title="Printable evidence briefs by condition",
                                     description="One-page printable evidence briefs for chronic and post-viral conditions, built from public trial and research data.",
                                     eyebrow="Research Tracker · evidence briefs", h1="Evidence", h1_span="briefs",
                                     lede=f"{len(idx_rows)} conditions, updated {esc(stamp)}.", body=body,
                                     crumbs=[("Evidence briefs", f"{SITE}/briefs/index.html")]))
    written = {r.split('href="/briefs/')[1].split('.html')[0] for r in idx_rows}
    for f in (ROOT / "briefs").glob("*.html"):  # remove briefs for conditions that no longer have data
        if f.stem != "index" and f.stem not in written:
            f.unlink()
            print(f"  removed stale brief {f.name}")
    print(f"briefs: {len(idx_rows)} briefs + index")


if __name__ == "__main__":
    build()
