#!/usr/bin/env python3
"""
render_html.py — NTD Intelligence section for research.opensourcemed.info.
Matches RepurpOS / disease-intelligence page styling (dark theme, embedded CSS).
"""

from __future__ import annotations

import html
import json
import os

import ntd_registry as reg
import persistence as pers

SITE_CSS_HREF = ""
FAVICON_URL = "https://opensourcemed.info/favicon.png"
GOOGLE_ANALYTICS_ID = "G-XRCGK1QTB5"
GOOGLE_ANALYTICS_SNIPPET = f"""  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GOOGLE_ANALYTICS_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GOOGLE_ANALYTICS_ID}');
  </script>"""
UPDATED = "2026-07-09"
OUT_DIR = "ntd"

NAV = [
    ("../index.html", "Research Tracker"),
    ("../disease-intelligence/index.html", "RepurpOS"),
    ("index.html", "NTD Intelligence"),
    ("../biomarker-atlas.html", "Biomarkers"),
    ("../clinical_trials.html", "Clinical Trials"),
    ("../agents.html", "Agents"),
]

KIND_BADGE = {
    "PAIS": ("Post-infectious syndrome", "#b23a2e"),
    "chronic": ("Chronic disease", "#b7791f"),
    "sequela": ("Lasting sequela", "#3a6ea5"),
    "none": ("No post-acute phase", "#8892a4"),
}

CSS = """
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0a0e1a;--surface:#141828;--card:#1a1f35;--border:#2a3050;
  --text:#e1e4e8;--muted:#8892a4;--accent:#4a9eff;--green:#22c55e;--amber:#f59e0b;--red:#ef4444}}
body{{background:var(--bg);color:var(--text);font-family:Inter,sans-serif;line-height:1.6}}
a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
code{{background:#2a3050;padding:2px 6px;border-radius:4px;font-size:.85em}}
nav{{background:rgba(10,14,26,.97);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}}
.nav-container{{max-width:1200px;margin:0 auto;padding:0 1.5rem;display:flex;align-items:center;justify-content:space-between;height:60px}}
.nav-brand{{font-weight:700;font-size:.95rem;color:var(--text)}} .nav-brand span{{color:var(--accent)}}
.nav-links{{list-style:none;display:flex;gap:.5rem;flex-wrap:wrap}} .nav-links a{{color:var(--muted);font-size:.85rem;padding:.35rem .75rem;border-radius:6px}}
.nav-links a:hover,.nav-links a.active{{color:var(--text);background:var(--card);text-decoration:none}}
.page-hero{{background:linear-gradient(135deg,#0d1230,#1a1f45);border-bottom:1px solid var(--border);padding:3rem 1.5rem 2.5rem;text-align:center}}
.hero-eyebrow{{color:var(--accent);font-size:.8rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase}}
.page-hero h1{{font-size:clamp(1.75rem,4vw,2.5rem);margin:.75rem 0}}
.page-hero p{{color:var(--muted);max-width:760px;margin:0 auto;font-size:.95rem}}
main{{max-width:1200px;margin:0 auto;padding:2rem 1.5rem 4rem}}
.breadcrumb{{display:flex;gap:.5rem;font-size:.85rem;color:var(--muted);margin-bottom:2rem;flex-wrap:wrap}}
.stat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:2rem}}
.stat-cell{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:1rem}}
.stat-cell .label{{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
.stat-cell .value{{font-size:1.4rem;font-weight:700;margin-top:.25rem}}
.stat-cell .sub{{font-size:.75rem;color:var(--muted);margin-top:.2rem}}
.section-title{{font-size:1.25rem;font-weight:700;margin-bottom:.25rem}}
.section-sub{{color:var(--muted);font-size:.88rem;margin-bottom:1.25rem}}
.badge{{display:inline-block;color:#fff;border-radius:4px;padding:2px 8px;font-size:.72rem;font-weight:700}}
.pi-block{{background:var(--card);border:1px solid var(--border);border-left:4px solid var(--red);border-radius:12px;padding:1.5rem 1.75rem;margin-bottom:2rem}}
.pi-block .big{{font-size:2rem;font-weight:800;color:var(--amber);margin:.35rem 0}}
.pi-kv{{display:grid;grid-template-columns:160px 1fr;gap:.4rem 1rem;font-size:.88rem;margin-top:1rem}}
.pi-kv .k{{color:var(--muted)}}
.pi-src{{font-size:.8rem;color:var(--muted);margin-top:1rem}}
.table-wrap{{overflow-x:auto;margin-bottom:2rem}}
.data-table{{width:100%;border-collapse:collapse;font-size:.86rem}}
.data-table th{{text-align:left;padding:.6rem 1rem;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);border-bottom:1px solid var(--border)}}
.data-table td{{padding:.55rem 1rem;border-bottom:1px solid rgba(42,48,80,.5);vertical-align:top}}
.data-table tr:hover{{background:rgba(74,158,255,.04)}}
.disclaimer{{background:rgba(74,158,255,.06);border:1px solid rgba(74,158,255,.2);border-radius:8px;padding:1rem 1.25rem;font-size:.85rem;color:var(--muted);margin-top:2rem}}
.caveat{{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);border-radius:8px;padding:.85rem 1.1rem;font-size:.84rem;color:var(--amber);margin-bottom:1.5rem}}
footer{{text-align:center;padding:2rem;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border)}}
.muted{{color:var(--muted)}}
"""


def esc(x):
    return html.escape(str(x)) if x is not None else ""


def head(title: str) -> str:
    css_link = f'  <link rel="stylesheet" href="{SITE_CSS_HREF}">\n' if SITE_CSS_HREF else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{GOOGLE_ANALYTICS_SNIPPET}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} — NTD Intelligence | Open Source Medicine Foundation</title>
  <link rel="icon" href="{FAVICON_URL}" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
{css_link}  <style>{CSS}</style>
</head>
<body>"""


def nav_html() -> str:
    items = []
    for href, label in NAV:
        cls = ' class="active"' if label == "NTD Intelligence" else ""
        items.append(f'<li><a href="{href}"{cls}>{esc(label)}</a></li>')
    return f"""
  <nav>
    <div class="nav-container">
      <a href="../index.html" class="nav-brand">Open Source <span>Medicine</span></a>
      <ul class="nav-links">{''.join(items)}</ul>
    </div>
  </nav>"""


def fmt(n):
    if n in (None, ""):
        return "—"
    try:
        return f"{int(float(n)):,}"
    except (ValueError, TypeError):
        return esc(n)


def load_rows():
    if os.path.exists("ntd_intelligence.json"):
        with open("ntd_intelligence.json", encoding="utf-8") as f:
            return json.load(f)
    import types
    import pipeline

    args = types.SimpleNamespace(
        mock=True, burden_csv=None, drugs=6, targets=6,
        trials=False, top=25, sleep=0, out="ntd_intelligence",
    )
    rows, _ = pipeline.build_rows(args)
    return rows


def slug(row):
    return row["key"].replace("_", "-")


def indicative_banner(rows) -> str:
    if any("indicative" in str(r.get("burden_confidence", "")).lower()
           or "indicative" in str(r.get("note", "")).lower()
           for r in rows):
        pass
    sources = {str(r.get("post_acute_source", "")) for r in rows}
    if rows and all(r.get("burden_confidence") in ("med", "low", "") for r in rows):
        return (
            '<p class="caveat"><strong>Indicative burden:</strong> Deaths and DALYs use the '
            "shipped GBD seed until replaced with an authoritative GBD export. "
            "Cross-check WHO and IHME before citing.</p>"
        )
    return (
        '<p class="caveat"><strong>Indicative burden:</strong> Deaths and DALYs use the '
        "shipped GBD seed until replaced with an authoritative GBD export. "
        "Cross-check WHO and IHME before citing.</p>"
    )


def post_infectious_block(row):
    pa = reg.get_post_acute(row["key"])
    pr = pers.get(row["key"])
    kind_label, kind_color = KIND_BADGE.get(pa.kind, KIND_BADGE["none"])
    border_color = kind_color if pa.kind == "PAIS" else "#2a3050"

    if pr:
        pct_display = esc(pr.pct) if pr.pct else "not quantified"
        return f"""<div class="pi-block" style="border-left-color:{border_color}">
      <div class="muted" style="font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;font-weight:600">Documented post-infectious syndrome</div>
      <div style="font-size:1.15rem;font-weight:700;margin:.5rem 0">{esc(pr.syndrome)}</div>
      <div class="big">{pct_display}</div>
      <div class="muted" style="font-size:.82rem">persistent symptoms — of {esc(pr.denominator)}</div>
      <div class="pi-kv">
        <div class="k">Summary</div><div>{esc(pr.detail)}</div>
        <div class="k">Timeframe</div><div>{esc(pr.timeframe)}</div>
        <div class="k">Evidence strength</div><div>{esc(pr.strength)}</div>
        <div class="k">Classification</div><div><span class="badge" style="background:{kind_color}">{esc(kind_label)}</span></div>
      </div>
      <div class="pi-src">Sources: {esc('; '.join(pr.sources))}</div>
    </div>"""

    return f"""<div class="pi-block" style="border-left-color:{border_color}">
      <div class="muted" style="font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;font-weight:600">Post-acute status</div>
      <div style="font-size:1.15rem;font-weight:700;margin:.5rem 0">{esc(pa.syndrome)}</div>
      <div class="pi-kv">
        <div class="k">Classification</div><div><span class="badge" style="background:{kind_color}">{esc(kind_label)}</span></div>
        <div class="k">Onset</div><div>{esc(pa.onset)}</div>
        <div class="k">Persistent-symptom %</div><div>not quantified as a single figure (see notes)</div>
      </div>
      <div class="pi-src">Source: {esc(pa.source)}</div>
    </div>"""


def disease_page(row):
    pa = reg.get_post_acute(row["key"])
    pr = pers.get(row["key"])
    kind_label, kind_color = KIND_BADGE.get(pa.kind, KIND_BADGE["none"])
    pct = pr.pct if pr and pr.pct else ("n/a" if pa.kind in ("chronic", "sequela") else "—")

    stats = f"""
    <div class="stat-grid">
      <div class="stat-cell"><div class="label">Deaths / year</div><div class="value">{fmt(row['deaths_per_year'])}</div><div class="sub">GBD (indicative unless refreshed)</div></div>
      <div class="stat-cell"><div class="label">DALYs / year</div><div class="value">{fmt(row['dalys_per_year'])}</div><div class="sub">GBD</div></div>
      <div class="stat-cell"><div class="label">Pathogen</div><div class="value" style="font-size:1rem">{esc(row['pathogen']).title()}</div></div>
      <div class="stat-cell"><div class="label">Post-infectious</div><div class="value" style="font-size:.95rem"><span class="badge" style="background:{kind_color}">{esc(kind_label)}</span></div></div>
      <div class="stat-cell"><div class="label">Persistent symptoms</div><div class="value" style="font-size:1rem">{esc(pct)}</div><div class="sub">{esc(pr.denominator if pr else '')}</div></div>
    </div>"""

    drugs = row.get("top_drug_detail") or [{"drug": d} for d in row.get("top_drugs", [])]
    drug_rows = "".join(
        f"<tr><td><strong>{esc(d.get('drug'))}</strong></td>"
        f"<td class='muted'>{esc(d.get('type') or '—')}</td>"
        f"<td>{esc(d.get('max_phase') if d.get('max_phase') is not None else '—')}</td>"
        f"<td class='muted'>{esc(d.get('moa') or '—')}</td>"
        f"<td>{'yes' if d.get('approved') else '—'}</td></tr>"
        for d in drugs
    ) or '<tr><td colspan="5" class="muted">No drugs resolved (run live pipeline / cross-check WHO EML &amp; DNDi).</td></tr>'

    targets = row.get("top_target_detail") or []
    tgt = ", ".join(esc(t.get("symbol")) for t in targets if t.get("symbol")) or "—"

    note = f'<p class="section-sub">{esc(row["note"])}</p>' if row.get("note") else ""

    return f"""{head(row['disease'])}{nav_html()}
  <header class="page-hero">
    <div class="hero-eyebrow">NTD Intelligence</div>
    <h1>{esc(row['disease'])}</h1>
    <p>Neglected tropical disease intelligence: burden, top therapeutic hits, and documented post-infectious syndrome with literature persistence rates.</p>
  </header>
  <main>
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="../index.html">Home</a><span>/</span>
      <a href="index.html">NTD Intelligence</a><span>/</span>
      <span>{esc(row['disease'])}</span>
    </nav>
    {stats}
    {note}
    <section>
      <h2 class="section-title">Post-infectious syndrome &amp; persistent symptoms</h2>
      <p class="section-sub">Whether a post-acute infection syndrome is documented and the literature proportion with persistent symptoms.</p>
      {post_infectious_block(row)}
    </section>
    <section>
      <h2 class="section-title">Top therapeutic hits</h2>
      <p class="section-sub">From Open Targets known drugs (ChEMBL indications). Standard-of-care antiparasitics may be underrepresented.</p>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Drug / agent</th><th>Type</th><th>Max phase</th><th>Mechanism</th><th>Approved</th></tr></thead>
          <tbody>{drug_rows}</tbody>
        </table>
      </div>
      <p class="muted" style="font-size:.84rem">Top associated targets: {tgt}</p>
    </section>
    <p class="disclaimer">Burden: IHME GBD (indicative seed unless refreshed) · Therapeutics: Open Targets / ChEMBL · Post-infectious data: curated peer-reviewed literature · Ontology: {esc(row.get('efo_id') or '—')} · Updated {UPDATED}. Associations, not a diagnostic test.</p>
  </main>
  <footer>Generated by OSMF NTD Intelligence Pipeline · Open Source Medicine Foundation</footer>
</body></html>"""


def index_page(rows):
    body = []
    for r in rows:
        pa = reg.get_post_acute(r["key"])
        pr = pers.get(r["key"])
        label, color = KIND_BADGE.get(pa.kind, KIND_BADGE["none"])
        pct = pr.pct if pr and pr.pct else ("n/a" if pa.kind in ("chronic", "sequela") else "—")
        body.append(
            f'<tr><td><a href="{slug(r)}.html"><strong>{esc(r["disease"])}</strong></a></td>'
            f'<td class="muted">{esc(r["pathogen"]).title()}</td>'
            f'<td>{fmt(r["deaths_per_year"])}</td>'
            f'<td>{fmt(r["dalys_per_year"])}</td>'
            f'<td><span class="badge" style="background:{color}">{esc(label)}</span></td>'
            f'<td>{esc(pct)}</td>'
            f'<td class="muted">{esc(pr.syndrome if pr else pa.syndrome)}</td></tr>'
        )
    pais = sum(1 for r in rows if reg.get_post_acute(r["key"]).kind == "PAIS")

    return f"""{head("NTD Intelligence")}{nav_html()}
  <header class="page-hero">
    <div class="hero-eyebrow">WHO Neglected Tropical Diseases</div>
    <h1>NTD Intelligence</h1>
    <p>The 21 WHO neglected tropical disease groups ({len(rows)} rows — dengue and chikungunya are split because burden, therapeutics, and post-acute syndromes differ), ranked by disease burden, with top therapeutic hits and documented post-infectious persistence rates. {pais} carry a distinct post-infectious infection syndrome (PAIS).</p>
  </header>
  <main>
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="../index.html">Home</a><span>/</span>
      <span>NTD Intelligence</span>
    </nav>
    {indicative_banner(rows)}
    <div class="stat-grid">
      <div class="stat-cell"><div class="label">NTD groups</div><div class="value">21</div><div class="sub">WHO · noma added Dec 2023</div></div>
      <div class="stat-cell"><div class="label">Table rows</div><div class="value">{len(rows)}</div><div class="sub">dengue &amp; chikungunya split</div></div>
      <div class="stat-cell"><div class="label">Post-infectious syndromes</div><div class="value">{pais}</div><div class="sub">PAIS-type</div></div>
      <div class="stat-cell"><div class="label">Updated</div><div class="value" style="font-size:1rem">{UPDATED}</div></div>
    </div>
    <section>
      <h2 class="section-title">Ranked diseases</h2>
      <p class="section-sub">Sorted by DALYs (then deaths). Persistence % is curated from peer-reviewed literature — see each disease page for citations.</p>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Disease</th><th>Pathogen</th><th>Deaths/yr</th><th>DALYs/yr</th><th>Post-infectious</th><th>Persist %</th><th>Syndrome</th></tr></thead>
          <tbody>{''.join(body)}</tbody>
        </table>
      </div>
    </section>
    <p class="disclaimer">Burden: IHME GBD · Therapeutics: Open Targets / ChEMBL · Post-infectious persistence: curated literature. Associations, not a diagnostic test.</p>
  </main>
  <footer>Generated by OSMF NTD Intelligence Pipeline · Open Source Medicine Foundation</footer>
</body></html>"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = load_rows()
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_page(rows))
    for r in rows:
        with open(os.path.join(OUT_DIR, f"{slug(r)}.html"), "w", encoding="utf-8") as f:
            f.write(disease_page(r))
    print(f"Rendered {len(rows) + 1} pages into ./{OUT_DIR}/ (index + {len(rows)} diseases)")


if __name__ == "__main__":
    main()