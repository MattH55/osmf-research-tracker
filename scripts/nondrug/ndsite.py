"""Shared page helpers for the non-drug evidence map, evidence-gap maps, supplement safety
pages and condition briefs. Built on scripts/osmf_site.page(); apply_osmf_ui.py adds the shared
header, footer and css/osmf-ui.css afterwards (these folders are in its PUBLIC_DIRS)."""
from __future__ import annotations

import csv
import io
import json
import sys
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import osmf_site as o  # noqa: E402

ROOT = SCRIPTS.parent
SITE = o.SITE
esc = o.esc

STATUS_TEXT = {
    "RECRUITING": "Recruiting", "ENROLLING_BY_INVITATION": "Enrolling by invitation", "NOT_YET_RECRUITING": "Not yet recruiting",
    "ACTIVE_NOT_RECRUITING": "Active, not recruiting", "COMPLETED": "Completed", "TERMINATED": "Terminated",
    "WITHDRAWN": "Withdrawn", "SUSPENDED": "Suspended", "UNKNOWN": "Status unknown",
}

EXTRA_CSS = """
.nd-numbers{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:8px 0 26px}
.nd-numbers div{background:#f6f7fb;border:1px solid rgba(14,20,68,.09);border-radius:14px;padding:14px 16px}
.nd-numbers b{display:block;font-size:1.6rem;font-weight:800;color:#0e1444;letter-spacing:-.02em;line-height:1.1}
.nd-numbers span{font-size:.84rem;color:#525a73}
.nd-groups{display:grid;gap:22px;margin:10px 0 30px}
.nd-group h2{font-size:1.15rem;margin:0 0 10px}
.nd-cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px}
@media (max-width:600px){.nd-cards{grid-template-columns:1fr 1fr;gap:8px}.nd-card{padding:10px}.nd-card strong{font-size:.86rem}.nd-card span{font-size:.74rem}}
.nd-jump{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px}
.nd-jump a{font-size:.8rem;padding:5px 10px;border-radius:999px;background:#f1f3f9;color:#0e1444;text-decoration:none;border:1px solid rgba(14,20,68,.1)}
.nd-jump a:hover,.nd-jump a:focus-visible{background:#ffe7c7}
.nd-group{scroll-margin-top:80px}
.nd-filter{display:flex;flex-direction:column;gap:4px;max-width:360px;margin:10px 0 4px;font-size:.85rem;font-weight:600;color:#0e1444}
.nd-filter input{font:inherit;font-weight:400;padding:9px 12px;border:1px solid #8a90a6;border-radius:10px}
.nd-filter-count{font-size:.8rem;color:#4a5170;min-height:1.2em;margin:0 0 6px}
@media (max-width:600px){
.nd-jump{flex-wrap:nowrap;overflow-x:auto;padding-bottom:6px;-webkit-overflow-scrolling:touch}
.nd-jump a{white-space:nowrap;flex:0 0 auto}
#nd-cond-table thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
#nd-cond-table,#nd-cond-table tbody{display:block}
#nd-cond-table tr{display:grid;grid-template-columns:1fr auto;gap:2px 10px;padding:9px 2px;border-bottom:1px solid rgba(14,20,68,.08)}
#nd-cond-table tr[hidden]{display:none}
#nd-cond-table th,#nd-cond-table td{border:0;padding:0}
#nd-cond-table td:nth-child(2)::after{content:" trials";color:#4a5170;font-size:.8rem}
#nd-cond-table td:nth-child(3){display:none}
#nd-cond-table td:last-child{grid-column:1/-1;font-size:.82rem}
.nd-tbl th{white-space:normal}
}
.nd-card{display:block;border:1px solid rgba(14,20,68,.1);border-radius:12px;padding:12px 14px;text-decoration:none!important;color:#0e1444;background:#fff}
.nd-card:hover{border-color:#bf360c;box-shadow:0 4px 14px rgba(14,20,68,.08)}
.nd-card strong{display:block;font-size:.95rem;margin-bottom:4px}
.nd-card span{font-size:.8rem;color:#525a73}
.nd-tbl{width:100%;border-collapse:separate;border-spacing:0;font-size:14px}
.nd-tbl th,.nd-tbl td{padding:9px 10px;border-bottom:1px solid rgba(14,20,68,.08);text-align:left;vertical-align:top}
.nd-tbl thead th{font-size:11.5px;letter-spacing:.06em;text-transform:uppercase;color:#525a73;background:#f6f7fb;position:sticky;top:0}
.nd-tbl td.n,.nd-tbl th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.nd-tbl tbody th{font-weight:650}
.nd-tbl a{color:#bf360c}
details.nd-trials{margin:4px 0 0}
details.nd-trials summary{cursor:pointer;color:#bf360c;font-weight:600;font-size:.85rem}
.nd-tlist{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:6px}
.nd-tlist li{font-size:.86rem;line-height:1.45}
.nd-tlist .meta{color:#525a73;font-size:.78rem}
.nd-st{display:inline-block;font-size:.72rem;font-weight:700;border-radius:999px;padding:1px 7px;background:#eef0f6;color:#2b3050;white-space:nowrap}
.nd-st.recruiting{background:#e7f7f0;color:#065f46}.nd-st.completed{background:#eaf0ff;color:#1e40af}.nd-st.stopped{background:#fdecea;color:#8a1c1c}
.nd-res{display:inline-block;font-size:.72rem;font-weight:700;border-radius:999px;padding:1px 7px;background:#fff3e0;color:#8a3a00}
.nd-matrix{border-collapse:separate;border-spacing:3px;font-size:12.5px;min-width:900px}
.nd-matrix th{font-weight:650;text-align:left;padding:6px 8px;color:#0e1444}
.nd-matrix thead th{font-size:11px;line-height:1.3;vertical-align:bottom;width:68px}
.nd-matrix td{text-align:center;padding:6px 4px;border-radius:6px;min-width:56px;font-variant-numeric:tabular-nums}
.nd-matrix td.z{background:#f6f7fb;color:#8a90a6}
.nd-matrix td.l1{background:#fff3e0;color:#7a3300}.nd-matrix td.l2{background:#ffd9a8;color:#6b2c00}.nd-matrix td.l3{background:#f8a95c;color:#3d1800}.nd-matrix td.l4{background:#9a3412;color:#fff}
.nd-matrix td small{display:block;font-size:10.5px;opacity:.85}
.nd-legend{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:.82rem;color:#525a73;margin:10px 0 18px}
.nd-legend i{display:inline-block;width:14px;height:14px;border-radius:4px;vertical-align:-2px;margin-right:5px}
.nd-gaps{columns:2 280px;column-gap:28px;margin:8px 0 0;padding-left:18px}
.nd-gaps li{break-inside:avoid;margin:0 0 6px;font-size:.92rem}
.nd-quote{border-left:3px solid #2440c9;background:#eef3ff;padding:12px 14px;border-radius:0 10px 10px 0;margin:10px 0;font-size:.93rem;line-height:1.6}
.nd-quote cite{display:block;font-style:normal;font-size:.8rem;color:#525a73;margin-top:6px}
.nd-callout{border:1px solid #f5dcb0;background:#fffaf2;color:#5a3a06;border-radius:12px;padding:14px 16px;margin:12px 0 22px;line-height:1.6;font-size:.93rem}
.nd-callout strong{color:#3d2600}
.nd-actions{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0 6px}
.nd-actions a{font-weight:650}
.nd-method{font-size:.88rem;color:#525a73;line-height:1.65}
.nd-method li{margin-bottom:4px}
@media (max-width:600px){.nd-tbl{font-size:13px}.nd-tbl th,.nd-tbl td{padding:8px 6px}}
.page-hero{padding:clamp(30px,5vw,56px) max(20px,calc((100% - 1152px)/2)) clamp(28px,4vw,46px)}
.page-hero .hero-eyebrow{display:inline-block;font-size:.72rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:#ffcf8a;background:rgba(255,152,0,.14);border:1px solid rgba(255,152,0,.35);border-radius:999px;padding:.3rem .8rem;margin:0 0 .9rem}
.page-hero h1{font-size:clamp(1.7rem,3.6vw,2.6rem);line-height:1.15;margin:0 0 .6rem;color:#fff}
.page-hero p{margin:0;max-width:62ch;color:rgba(255,255,255,.82);font-size:1.02rem}
.nd-tbl tbody th{text-transform:none;letter-spacing:normal;font-size:14px;font-weight:650;color:#0e1444;background:#fff}
.nd-tbl tbody th a{color:#bf360c}
.nd-matrix tbody th{text-transform:none;letter-spacing:normal;font-size:12.5px;color:#0e1444;background:#fff;white-space:normal;min-width:170px}
.nd-matrix tbody th .meta,.nd-tlist .meta{color:#4a5170}
.tbl-wrap[tabindex]:focus-visible{outline:3px solid #bf360c;outline-offset:2px}
.nd-matrix tbody th,.nd-matrix thead th:first-child{position:sticky;left:0;z-index:2;background:#fff;box-shadow:4px 0 6px -4px rgba(14,20,68,.25)}
.nd-scroll-hint{font-size:12.5px;color:#4a5170;margin:6px 0 0}
.nd-scroll-hint::after{content:" →"}
.brief-head p{overflow-wrap:anywhere}
.sr-only{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
"""


def status_badge(status: str, group: str) -> str:
    cls = {"recruiting": "recruiting", "planned": "recruiting", "completed": "completed", "stopped": "stopped"}.get(group, "")
    return f'<span class="nd-st {cls}">{esc(STATUS_TEXT.get(status, status.replace("_", " ").title()))}</span>'


def trial_li(nct: str, t: dict, extra: str = "") -> str:
    bits = [status_badge(t["s"], t["g"])]
    if t.get("r"):
        bits.append('<span class="nd-res">Results posted</span>')
    meta = []
    if t.get("y"):
        meta.append(f"started {t['y']}")
    if t.get("n"):
        meta.append(f"{t['n']:,} participants" if isinstance(t["n"], int) else f"{t['n']} participants")
    if t.get("rnd"):
        meta.append("randomised")
    if t.get("p") and t["p"] != "NA":
        meta.append(t["p"].replace("PHASE", "Phase ").replace(",", "/"))
    return (f'<li><a href="https://clinicaltrials.gov/study/{nct}" target="_blank" rel="noopener">{esc(t["t"])}</a> '
            f'{" ".join(bits)} <span class="meta">{nct} · {esc(" · ".join(meta))}{extra}</span></li>')


def shell(*, path: str, title: str, description: str, eyebrow: str, h1: str, h1_span: str = "", lede: str,
          body: str, crumbs: list[tuple], jsonld: list[dict] | None = None, modified: str = "") -> str:
    url = f"{SITE}/{path}"
    crumbs_full = [("Research Tracker", f"{SITE}/")] + crumbs
    html_body = f"""
<section class="page-hero">
  <div class="hero-eyebrow">{esc(eyebrow)}</div>
  <h1>{esc(h1)}{(' <span>' + esc(h1_span) + '</span>') if h1_span else ''}</h1>
  <p>{lede}</p>
</section>
<main class="main-section" id="main">
  <div class="section-inner">
    {o.breadcrumb_html(crumbs_full)}
    {body}
  </div>
</main>
"""
    ld = [o.breadcrumb_jsonld(crumbs_full)] + list(jsonld or [])
    return o.page(title=title, description=description, canonical=url, body=html_body, jsonld=ld,
                  extra_head=f"<style>{EXTRA_CSS}</style>", modified=modified or date.today().isoformat(),
                  footer_note="Compiled by the Open Source Medicine Foundation.")


def write(path: str, html: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(html, encoding="utf-8")


def write_csv(path: str, header: list[str], rows: list[list]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(buf.getvalue(), encoding="utf-8")


def dataset_ld(name: str, description: str, url: str, csv_url: str, modified: str) -> dict:
    return {
        "@context": "https://schema.org", "@type": "Dataset", "name": name, "description": description,
        "url": url, "isAccessibleForFree": True, "dateModified": modified,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "creator": {"@type": "Organization", "name": o.ORG_NAME, "url": o.ORG_URL},
        "isBasedOn": "https://clinicaltrials.gov/",
        "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": csv_url}],
    }


def load_dataset() -> dict:
    return json.loads((ROOT / "data" / "nondrug" / "nondrug_trials.json").read_text(encoding="utf-8"))


DISCLAIMER = ('<div class="disclaimer"><span>⚠️</span><div><strong>Research information, not medical advice.</strong> '
              'These pages index what has been <em>studied</em> in registered trials. A trial existing, completing or posting '
              'results says nothing on its own about whether an approach works or is safe for you. Supplements and devices can '
              'interact with medicines. Discuss any change with your own clinician.</div></div>')
