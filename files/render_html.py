#!/usr/bin/env python3
"""
render_html.py
--------------
Generates the hosted "NTD Intelligence" section for research.opensourcemed.info,
mirroring the RepurpOS disease-page format:

  ntd/index.html          -> section landing (ranked table of all NTDs)
  ntd/<slug>.html         -> one page per NTD

Each disease page carries the same anatomy as an existing RepurpOS page
(stat cards -> overview -> a chronicity block -> therapeutics), with the
chronicity block replaced by the requested **Post-infectious syndrome &
persistent-symptom** section (documented syndrome + literature % persisting).

DATA SOURCES (merged at render time):
  ntd_intelligence.json   burden + top drugs/targets   (from pipeline.py)
  ntd_registry.POST_ACUTE has / kind / syndrome / onset
  persistence.PERSISTENCE literature persistence percentages + citations

If ntd_intelligence.json is absent, this runs pipeline.build_rows(--mock) so the
section renders out-of-the-box; re-run the live pipeline for real burden/drugs.

--- Matching the live site exactly ---
The embedded CSS approximates the RepurpOS navy theme so pages are usable
immediately. If the osmf-research-tracker repo (or the deployed site) exposes a
shared stylesheet, set SITE_CSS_HREF below to that URL/path and the pages will
link it instead of (or in addition to) the embedded styles. See AGENT_INSTRUCTIONS.md.
"""

from __future__ import annotations
import html
import json
import os

import ntd_registry as reg
import persistence as pers

# If the site has a shared stylesheet, put its href here to match pixel-for-pixel.
SITE_CSS_HREF = ""   # e.g. "/assets/repurpos.css"
UPDATED = "2026-07-09"
OUT_DIR = "ntd"

NAV = [
    ("Research Tracker", "https://research.opensourcemed.info/index.html"),
    ("RepurpOS", "https://research.opensourcemed.info/disease-intelligence/index.html"),
    ("NTD Intelligence", "index.html"),
    ("Biomarkers", "https://research.opensourcemed.info/biomarker-atlas.html"),
    ("Interventions", "https://research.opensourcemed.info/chronic-disease-interventions/index.html"),
    ("Clinical Trials", "https://research.opensourcemed.info/clinical_trials.html"),
]

KIND_BADGE = {
    "PAIS":    ("Post-infectious syndrome", "badge-pais"),
    "chronic": ("Chronic disease", "badge-chronic"),
    "sequela": ("Lasting sequela", "badge-seq"),
    "none":    ("No post-acute phase", "badge-none"),
}

CSS = """
:root{--navy:#0e1444;--navy2:#1b2566;--ink:#152238;--muted:#5a6577;--line:#e2e6ee;
--bg:#f6f7fb;--card:#fff;--teal:#0e7c7b;--pais:#b23a2e;--chronic:#b7791f;--seq:#3a6ea5;--none:#8a93a3;}
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
color:var(--ink);background:var(--bg);line-height:1.5}
a{color:var(--teal);text-decoration:none}a:hover{text-decoration:underline}
header.top{background:var(--navy);color:#fff;padding:14px 26px;display:flex;gap:22px;flex-wrap:wrap;align-items:center}
header.top .brand{font-weight:700;letter-spacing:.2px}
header.top nav a{color:#c9d2f0;font-size:14px}header.top nav a:hover{color:#fff}
.wrap{max-width:1120px;margin:0 auto;padding:0 26px 60px}
.crumb{font-size:13px;color:var(--muted);margin:18px 0}
h1{font-size:30px;margin:8px 0 6px}
.lede{color:var(--muted);max-width:760px;margin:0 0 22px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:22px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card .k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.card .v{font-size:22px;font-weight:700;margin-top:4px}
.card .s{font-size:12px;color:var(--muted);margin-top:2px}
h2{font-size:20px;border-bottom:2px solid var(--line);padding-bottom:8px;margin:38px 0 16px}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:600;color:#fff}
.badge-pais{background:var(--pais)}.badge-chronic{background:var(--chronic)}
.badge-seq{background:var(--seq)}.badge-none{background:var(--none)}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
th,td{text-align:left;padding:10px 12px;font-size:14px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f0f2f8;font-size:12px;text-transform:uppercase;letter-spacing:.4px;color:var(--muted)}
tr:last-child td{border-bottom:none}
.pi{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--pais);border-radius:12px;padding:18px 20px;margin:8px 0}
.pi .big{font-size:34px;font-weight:800;color:var(--pais)}
.pi .lbl{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.4px}
.kv{display:grid;grid-template-columns:170px 1fr;gap:6px 18px;margin-top:12px;font-size:14px}
.kv .k{color:var(--muted)}
.src{font-size:12px;color:var(--muted);margin-top:10px}
.foot{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}
.pill{font-size:12px;color:var(--muted)}
"""

def esc(x): return html.escape(str(x)) if x is not None else ""

def head(title, depth=1):
    css_link = f'<link rel="stylesheet" href="{SITE_CSS_HREF}">' if SITE_CSS_HREF else ""
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#0e1444">
<title>{esc(title)} — NTD Intelligence | OpenSourceMedicine</title>
{css_link}<style>{CSS}</style></head><body>"""

def nav():
    links = "".join(f'<a href="{h}">{esc(n)}</a>' for n, h in NAV)
    return (f'<header class="top"><span class="brand">Open Source Medicine Foundation</span>'
            f'<nav style="display:flex;gap:16px;flex-wrap:wrap">{links}</nav></header>')

def fmt(n):
    if n in (None, ""): return "—"
    try: return f"{int(float(n)):,}"
    except (ValueError, TypeError): return esc(n)

def load_rows():
    if os.path.exists("ntd_intelligence.json"):
        with open("ntd_intelligence.json") as f:
            return json.load(f)
    # fallback: generate mock rows so the section still renders
    import types, pipeline
    args = types.SimpleNamespace(mock=True, burden_csv=None, drugs=6, targets=6,
                                 trials=False, top=25, sleep=0, out="ntd_intelligence")
    rows, _ = pipeline.build_rows(args)
    return rows

def slug(row): return row["key"].replace("_", "-")

# ---------------- per-disease page ----------------
def disease_page(row):
    pa = reg.get_post_acute(row["key"])
    pr = pers.get(row["key"])
    kind_label, kind_cls = KIND_BADGE.get(pa.kind, KIND_BADGE["none"])
    pct = (pr.pct if pr and pr.pct else ("n/a" if pa.kind in ("chronic", "sequela") else "—"))

    cards = [
        ("Deaths / year", fmt(row["deaths_per_year"]), "GBD (indicative unless refreshed)"),
        ("DALYs / year", fmt(row["dalys_per_year"]), "GBD"),
        ("Pathogen", esc(row["pathogen"]).title(), ""),
        ("Post-infectious", kind_label, ""),
        ("Persistent symptoms", esc(pct), (pr.denominator if pr else "")),
    ]
    card_html = "".join(
        f'<div class="card"><div class="k">{esc(k)}</div><div class="v">{v}</div>'
        f'<div class="s">{esc(s)}</div></div>'
        for k, v, s in cards)

    # post-infectious section
    if pr:
        pi = f"""<div class="pi">
          <div class="lbl">Documented post-infectious syndrome</div>
          <div style="font-size:18px;font-weight:700;margin:4px 0 10px">{esc(pr.syndrome)}</div>
          <div class="big">{esc(pr.pct) if pr.pct else 'not quantified'}</div>
          <div class="pill">persistent symptoms — of {esc(pr.denominator)}</div>
          <div class="kv">
            <div class="k">Summary</div><div>{esc(pr.detail)}</div>
            <div class="k">Timeframe</div><div>{esc(pr.timeframe)}</div>
            <div class="k">Evidence strength</div><div>{esc(pr.strength)}</div>
            <div class="k">Classification</div><div><span class="badge {kind_cls}">{esc(kind_label)}</span></div>
          </div>
          <div class="src">Sources: {esc('; '.join(pr.sources))}</div>
        </div>"""
    else:
        pi = f"""<div class="pi" style="border-left-color:var(--{('chronic' if pa.kind=='chronic' else 'seq' if pa.kind=='sequela' else 'none')})">
          <div class="lbl">Post-acute status</div>
          <div style="font-size:18px;font-weight:700;margin:4px 0 8px">{esc(pa.syndrome)}</div>
          <div class="kv">
            <div class="k">Classification</div><div><span class="badge {kind_cls}">{esc(kind_label)}</span></div>
            <div class="k">Onset</div><div>{esc(pa.onset)}</div>
            <div class="k">Persistent-symptom %</div><div>not quantified as a single figure (see notes)</div>
          </div>
          <div class="src">Source: {esc(pa.source)}</div>
        </div>"""

    # therapeutics table
    drugs = row.get("top_drug_detail") or [{"drug": d} for d in row.get("top_drugs", [])]
    drug_rows = "".join(
        f"<tr><td><strong>{esc(d.get('drug'))}</strong></td>"
        f"<td>{esc(d.get('type') or '—')}</td>"
        f"<td>{esc(d.get('max_phase') if d.get('max_phase') is not None else '—')}</td>"
        f"<td>{esc(d.get('moa') or '—')}</td>"
        f"<td>{'approved' if d.get('approved') else '—'}</td></tr>"
        for d in drugs) or '<tr><td colspan="5" class="pill">No drugs resolved (run live pipeline / cross-check WHO EML & DNDi).</td></tr>'

    targets = row.get("top_target_detail") or []
    tgt = ", ".join(esc(t.get("symbol")) for t in targets if t.get("symbol")) or "—"

    return f"""{head(row['disease'])}{nav()}
<div class="wrap">
  <div class="crumb"><a href="../index.html">Home</a> / <a href="index.html">NTD Intelligence</a> / {esc(row['disease'])}</div>
  <h1>{esc(row['disease'])}</h1>
  <p class="lede">Neglected tropical disease intelligence: burden, top therapeutic hits, and documented
  post-infectious syndrome with literature persistence rates. Pathogen: {esc(row['pathogen'])}.</p>
  <div class="cards">{card_html}</div>

  <h2>Post-infectious syndrome &amp; persistent symptoms</h2>
  {pi}

  <h2>Top therapeutic hits</h2>
  <table><thead><tr><th>Drug / agent</th><th>Type</th><th>Max phase</th><th>Mechanism</th><th>Approved</th></tr></thead>
  <tbody>{drug_rows}</tbody></table>
  <p class="pill" style="margin-top:8px">Top associated targets: {tgt}</p>

  <div class="foot">
    Burden: GBD (indicative seed unless refreshed) · Therapeutics: Open Targets / ChEMBL ·
    Post-infectious data: curated from peer-reviewed literature (see sources above) ·
    Ontology: {esc(row.get('efo_id') or '—')} · Updated {UPDATED}<br>
    Open Source Medicine Foundation · research.opensourcemed.info · Associations, not a diagnostic test.
  </div>
</div></body></html>"""

# ---------------- section index ----------------
def index_page(rows):
    body = []
    for r in rows:
        pa = reg.get_post_acute(r["key"])
        pr = pers.get(r["key"])
        label, cls = KIND_BADGE.get(pa.kind, KIND_BADGE["none"])
        pct = (pr.pct if pr and pr.pct else ("n/a" if pa.kind in ("chronic", "sequela") else "—"))
        body.append(
            f'<tr><td><a href="{slug(r)}.html"><strong>{esc(r["disease"])}</strong></a></td>'
            f'<td>{esc(r["pathogen"]).title()}</td>'
            f'<td>{fmt(r["deaths_per_year"])}</td>'
            f'<td>{fmt(r["dalys_per_year"])}</td>'
            f'<td><span class="badge {cls}">{esc(label)}</span></td>'
            f'<td>{esc(pct)}</td>'
            f'<td class="pill">{esc((pr.syndrome if pr else pa.syndrome))}</td></tr>')
    pais = sum(1 for r in rows if reg.get_post_acute(r["key"]).kind == "PAIS")
    return f"""{head("NTD Intelligence")}{nav()}
<div class="wrap">
  <div class="crumb"><a href="../index.html">Home</a> / NTD Intelligence</div>
  <h1>Neglected Tropical Disease Intelligence</h1>
  <p class="lede">The 21 WHO neglected tropical diseases, ranked by disease burden, with top therapeutic
  hits and — for each — whether a post-infectious syndrome is documented and what proportion of patients
  have persistent symptoms in the literature. {pais} carry a distinct post-infectious infection syndrome
  (the post-acute / Long-COVID analog).</p>
  <div class="cards">
    <div class="card"><div class="k">NTD groups</div><div class="v">21</div><div class="s">WHO · noma added Dec 2023</div></div>
    <div class="card"><div class="k">Post-infectious syndromes</div><div class="v">{pais}</div><div class="s">PAIS-type</div></div>
    <div class="card"><div class="k">Sources</div><div class="v">4</div><div class="s">GBD · Open Targets · ChEMBL · literature</div></div>
    <div class="card"><div class="k">Updated</div><div class="v">{UPDATED}</div><div class="s"></div></div>
  </div>
  <h2>Ranked diseases</h2>
  <table><thead><tr><th>Disease</th><th>Pathogen</th><th>Deaths/yr</th><th>DALYs/yr</th>
  <th>Post-infectious</th><th>Persist %</th><th>Syndrome</th></tr></thead>
  <tbody>{''.join(body)}</tbody></table>
  <div class="foot">
    Ranked by DALYs (burden = GBD; indicative seed unless refreshed). Persistence percentages are curated
    from peer-reviewed meta-analyses and cohorts; see each disease page for citations.<br>
    Open Source Medicine Foundation · research.opensourcemed.info
  </div>
</div></body></html>"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = load_rows()
    with open(os.path.join(OUT_DIR, "index.html"), "w") as f:
        f.write(index_page(rows))
    for r in rows:
        with open(os.path.join(OUT_DIR, f"{slug(r)}.html"), "w") as f:
            f.write(disease_page(r))
    print(f"Rendered {len(rows)+1} pages into ./{OUT_DIR}/ (index + {len(rows)} diseases)")


if __name__ == "__main__":
    main()
