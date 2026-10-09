#!/usr/bin/env python3
"""
render_html.py — NTD Intelligence section for research.opensourcemed.info.
Matches RepurpOS / disease-intelligence page styling (shared light theme from
disease_pipeline/light_theme.py, embedded CSS).
"""

from __future__ import annotations

import html
import json
import os

import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from disease_pipeline.light_theme import LIGHT_CSS, restyle_html  # noqa: E402

import ntd_registry as reg  # noqa: E402
import persistence as pers  # noqa: E402
import therapeutics as ther  # noqa: E402

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
UPDATED = "2026-07-10"
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

CSS = LIGHT_CSS


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


def phase_label(d: dict) -> str:
    p = d.get("max_phase") or 0
    if d.get("approved") or p >= 4:
        return "Approved"
    if p == 3:
        return "Phase 3"
    if p == 2:
        return "Phase 2"
    if p == 1:
        return "Phase 1"
    if p == 0 and d.get("source", "").startswith("WHO"):
        return "Standard of care"
    return "—"


def evidence_badge(ev: str) -> str:
    labels = {"published": "Published evidence", "pipeline": "Pipeline", "preliminary": "Preliminary"}
    return f'<span class="evidence-badge evidence-{ev}">{esc(labels.get(ev, ev))}</span>'


def drug_rows_html(drugs: list[dict]) -> str:
    if not drugs:
        return '<tr><td colspan="5" class="muted">No agents in this stage.</td></tr>'
    rows = []
    for d in drugs:
        src = d.get("source") or "Open Targets"
        src_cls = "source-soc" if (
            "WHO" in src or "standard" in src.lower() or "MSF" in src or "DNDi" in src
            or "FDA" in src or "Published" in src
        ) else "source-ot"
        ev = ther.infer_evidence(d)
        rows.append(
            f"<tr class='agent-row evidence-{ev}'>"
            f"<td><strong>{esc(d.get('drug'))}</strong>{evidence_badge(ev) if ev != 'published' else ''}</td>"
            f"<td class='muted'>{esc(d.get('type') or '—')}</td>"
            f"<td>{esc(phase_label(d))}</td>"
            f"<td class='muted'>{esc(d.get('moa') or '—')}</td>"
            f"<td><span class='{src_cls}'>{esc(src)}</span></td>"
            f"</tr>"
        )
    return "".join(rows)


def staged_therapeutics_html(drugs: list[dict]) -> tuple[str, int]:
    """Group agents by clinical stage; return HTML and count of hidden (non-published) rows."""
    by_stage: dict[str, list[dict]] = {s: [] for s in ther.STAGES}
    hidden = 0
    for d in drugs:
        stage = d.get("stage") or "acute"
        if stage not in by_stage:
            stage = "acute"
        by_stage[stage].append(d)
        if ther.infer_evidence(d) != "published":
            hidden += 1

    parts = []
    for stage in ther.STAGES:
        items = by_stage.get(stage, [])
        if not items:
            continue
        label = ther.STAGE_LABELS.get(stage, stage)
        parts.append(
            f'<h3 class="stage-heading">{esc(label)}</h3>'
            f'<div class="table-wrap"><table class="data-table">'
            f'<thead><tr><th>Agent</th><th>Type</th><th>Status</th>'
            f'<th>Mechanism / role</th><th>Source</th></tr></thead>'
            f"<tbody>{drug_rows_html(items)}</tbody></table></div>"
        )
    if not parts:
        parts.append('<p class="muted">No therapeutic agents curated for this condition.</p>')
    return "".join(parts), hidden


EVIDENCE_TOGGLE = """
      <label class="evidence-toggle">
        <input type="checkbox" id="show-unpublished" aria-controls="therapeutics-stages">
        <span>Show pipeline &amp; preliminary agents</span>
        <span class="hidden-count" id="hidden-agent-count"></span>
      </label>
      <script>
        (function(){
          var cb = document.getElementById('show-unpublished');
          var cnt = document.getElementById('hidden-agent-count');
          var hidden = document.querySelectorAll('.agent-row.evidence-pipeline,.agent-row.evidence-preliminary').length;
          if (cnt && hidden) cnt.textContent = '(' + hidden + ' hidden)';
          if (cb) cb.addEventListener('change', function(){
            document.body.classList.toggle('show-unpublished', cb.checked);
          });
        })();
      </script>"""


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
    staged_html, hidden_n = staged_therapeutics_html(drugs)

    targets = row.get("top_target_detail") or []
    tgt = ", ".join(esc(t.get("symbol")) for t in targets[:6] if t.get("symbol")) or "—"

    note = f'<p class="caveat">{esc(row["note"])}</p>' if row.get("note") else ""
    supp = reg.is_supplemental(row["key"])
    hero_sub = (
        "Supplemental viral disease intelligence: burden, staged therapeutics with published-evidence filter, "
        "and documented post-infectious syndrome."
        if supp else
        "Neglected tropical disease intelligence: burden, staged therapeutics with published-evidence filter, "
        "and documented post-infectious syndrome with literature persistence rates."
    )

    return f"""{head(row['disease'])}{nav_html()}
  <header class="page-hero">
    <div class="hero-eyebrow">NTD Intelligence</div>
    <h1>{esc(row['disease'])}</h1>
    <p>{hero_sub}</p>
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
    <section id="therapeutics">
      <h2 class="section-title">Therapeutic agents by stage</h2>
      <p class="section-sub">Vector control, prevention, acute treatment, and post-infectious care. Only agents with published evidence are shown by default.</p>
      {EVIDENCE_TOGGLE}
      <div id="therapeutics-stages">{staged_html}</div>
      <p class="muted" style="font-size:.84rem;margin-top:1rem">Associated drug targets (Open Targets): {tgt}</p>
    </section>
    <p class="disclaimer">Burden: IHME GBD (indicative seed unless refreshed) · Therapeutics: curated WHO EML / SOC + Open Targets pipeline · Post-infectious data: curated peer-reviewed literature · Ontology: {esc(row.get('efo_id') or '—')} · Updated {UPDATED}. Associations, not a diagnostic test.</p>
  </main>
  <footer>Generated by OSMF NTD Intelligence Pipeline · Open Source Medicine Foundation</footer>
</body></html>"""


def _index_rows(rows):
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
    return "".join(body)


def index_page(rows):
    who_rows = [r for r in rows if not reg.is_supplemental(r["key"])]
    viral_rows = [r for r in rows if reg.is_supplemental(r["key"])]
    pais = sum(1 for r in who_rows if reg.get_post_acute(r["key"]).kind == "PAIS")
    viral_section = ""
    if viral_rows:
        viral_section = f"""
    <section>
      <h2 class="section-title">Supplemental viral diseases</h2>
      <p class="section-sub">High-burden viral diseases not on the WHO NTD list — same intelligence template (measles, yellow fever, Zika).</p>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Disease</th><th>Pathogen</th><th>Deaths/yr</th><th>DALYs/yr</th><th>Post-infectious</th><th>Persist %</th><th>Syndrome</th></tr></thead>
          <tbody>{_index_rows(viral_rows)}</tbody>
        </table>
      </div>
    </section>"""

    return f"""{head("NTD Intelligence")}{nav_html()}
  <header class="page-hero">
    <div class="hero-eyebrow">WHO Neglected Tropical Diseases</div>
    <h1>NTD Intelligence</h1>
    <p>The 21 WHO neglected tropical disease groups ({len(who_rows)} rows — dengue and chikungunya are split because burden, therapeutics, and post-acute syndromes differ), ranked by disease burden, with staged therapeutics and documented post-infectious persistence rates. {pais} carry a distinct post-infectious infection syndrome (PAIS). {len(viral_rows)} supplemental viral diseases are listed below.</p>
  </header>
  <main>
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="../index.html">Home</a><span>/</span>
      <span>NTD Intelligence</span>
    </nav>
    {indicative_banner(rows)}
    <div class="stat-grid">
      <div class="stat-cell"><div class="label">NTD groups</div><div class="value">21</div><div class="sub">WHO · noma added Dec 2023</div></div>
      <div class="stat-cell"><div class="label">WHO table rows</div><div class="value">{len(who_rows)}</div><div class="sub">dengue &amp; chikungunya split</div></div>
      <div class="stat-cell"><div class="label">Supplemental viral</div><div class="value">{len(viral_rows)}</div><div class="sub">measles, yellow fever, Zika</div></div>
      <div class="stat-cell"><div class="label">Post-infectious syndromes</div><div class="value">{pais}</div><div class="sub">PAIS-type</div></div>
      <div class="stat-cell"><div class="label">Updated</div><div class="value" style="font-size:1rem">{UPDATED}</div></div>
    </div>
    <section>
      <h2 class="section-title">WHO NTD diseases (ranked)</h2>
      <p class="section-sub">Sorted by DALYs (then deaths). Persistence % is curated from peer-reviewed literature — see each disease page for citations.</p>
      <div class="table-wrap">
        <table class="data-table">
          <thead><tr><th>Disease</th><th>Pathogen</th><th>Deaths/yr</th><th>DALYs/yr</th><th>Post-infectious</th><th>Persist %</th><th>Syndrome</th></tr></thead>
          <tbody>{_index_rows(who_rows)}</tbody>
        </table>
      </div>
    </section>
    {viral_section}
    <p class="disclaimer">Burden: IHME GBD · Therapeutics: Open Targets / ChEMBL · Post-infectious persistence: curated literature. Associations, not a diagnostic test.</p>
  </main>
  <footer>Generated by OSMF NTD Intelligence Pipeline · Open Source Medicine Foundation</footer>
</body></html>"""


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = load_rows()
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(restyle_html(index_page(rows)))
    for r in rows:
        with open(os.path.join(OUT_DIR, f"{slug(r)}.html"), "w", encoding="utf-8") as f:
            f.write(restyle_html(disease_page(r)))
    print(f"Rendered {len(rows) + 1} pages into ./{OUT_DIR}/ (index + {len(rows)} diseases)")


if __name__ == "__main__":
    main()