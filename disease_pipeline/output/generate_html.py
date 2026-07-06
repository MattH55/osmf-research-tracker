"""Generate static HTML pages from DiseaseIntelligencePage JSON."""
from __future__ import annotations

import html
import json
from pathlib import Path

from ..published_conditions import (
    biomarker_count,
    clinical_biomarker_count,
    db100_index_slugs,
    is_publishable,
    on_db100_index,
)
from ..site_nav import (
    FAVICON_URL,
    GOOGLE_ANALYTICS_SNIPPET,
    REPURPOS_BRAND,
    REPURPOS_FULL,
    REPURPOS_TAGLINE,
    related_links,
    render_nav,
)

TIER_COLOUR = {"A": "#22c55e", "B": "#4a9eff", "C": "#f59e0b"}
TYPE_COLOUR = {"A": "#7c6af7", "B": "#4a9eff", "C": "#f59e0b", "D": "#ef4444", "E": "#22c55e"}


def _esc(text: str | None) -> str:
    return html.escape(str(text or ""))


def _page_title(page: dict, short: str) -> str:
    title = str(page.get("title") or "")
    if "Disease Intelligence" in title:
        return title.replace(
            " — Disease Intelligence | OSMF",
            f" — {REPURPOS_BRAND} | OpenSourceMedicine",
        )
    if title:
        return title
    return f"{short} — {REPURPOS_BRAND} | OpenSourceMedicine"


def _tier_badge(tier: str, label: str) -> str:
    colour = TIER_COLOUR.get(tier, "#8892a4")
    return f'<span class="tier-badge" style="background:{colour}">{_esc(label)}</span>'


def _type_badge(t: str, label: str) -> str:
    colour = TYPE_COLOUR.get(t, "#8892a4")
    return f'<span class="type-badge" style="background:{colour}">{_esc(label)}</span>'


def _links_html(links: list[dict]) -> str:
    if not links:
        return '<span class="muted">—</span>'
    return " ".join(
        f'<a href="{_esc(l["url"])}" target="_blank" rel="noopener" class="ext-link">{_esc(l["label"])}</a>'
        for l in links[:4]
    )


def _alterations_table(alts: list[dict]) -> str:
    if not alts:
        return '<p class="no-data">No alterations in this category.</p>'
    rows = []
    for a in alts:
        dir_txt = a.get("direction_label") or "—"
        freq = a.get("frequency_label") or "—"
        defn = (a.get("definition") or "")[:120]
        rows.append(f"""
        <tr data-type="{_esc(a['type'])}">
          <td class="name-cell"><strong>{_esc(a['name'])}</strong>
            {f'<div class="sub">{_esc(defn)}</div>' if defn else ''}</td>
          <td>{_type_badge(a['type'], a['type_label'])}</td>
          <td class="muted">{_esc(a['subtype_label'])}</td>
          <td>{_esc(dir_txt)}</td>
          <td class="muted">{_esc(freq)}</td>
          <td>{_tier_badge(a['evidence_tier'], a['evidence_tier_label'])}</td>
          <td class="muted">{', '.join(_esc(s) for s in a.get('sources', [])[:3])}</td>
          <td class="links-cell">{_links_html(a.get('external_links', []))}</td>
        </tr>""")
    return f"""
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Name</th><th>Type</th><th>Subtype</th><th>Direction</th>
          <th>Frequency</th><th>Evidence</th><th>Sources</th><th>Links</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>"""


def _evidence_cell(ev: dict | None) -> str:
    if not ev:
        return '<span class="muted">—</span>'
    counts = ev.get("counts", {})
    badges = []
    trial_n = counts.get("trials_registry", 0)
    if trial_n:
        badges.append(f'<span class="ev-badge trial">{trial_n} trials</span>')
    for key, label in (
        ("cochrane_review", "Cochrane"),
        ("meta_analysis", "Meta-analysis"),
        ("clinical_trial", "Trial pubs"),
        ("rct", "RCT"),
    ):
        n = counts.get(key, 0)
        if n:
            badges.append(f'<span class="ev-badge lit">{n} {label}</span>')
    assoc = counts.get("association_total", 0)
    if assoc and not badges:
        badges.append(f'<span class="ev-badge assoc">{assoc} pubs</span>')
    badge_html = " ".join(badges) if badges else '<span class="muted">No indexed hits</span>'

    trial_rows = []
    for t in ev.get("clinical_trials", [])[:8]:
        nct = t.get("nct_id") or ""
        link = t.get("url") or ""
        status = t.get("status") or ""
        phase = t.get("phase") or ""
        trial_rows.append(
            f'<li><a href="{_esc(link)}" target="_blank" rel="noopener">{_esc(nct or t.get("title", ""))}</a>'
            f' — {_esc(t.get("title", ""))}'
            f'{f" <span class=muted>({ _esc(status)})</span>" if status else ""}'
            f'{f" <span class=muted>{_esc(phase)}</span>" if phase else ""}</li>'
        )

    lit_rows = []
    for lit in ev.get("literature", [])[:12]:
        lit_rows.append(
            f'<li><span class="ev-lit-type">{_esc(lit.get("publication_type_label", ""))}</span> '
            f'<a href="{_esc(lit.get("url", ""))}" target="_blank" rel="noopener">{_esc(lit.get("title", ""))}</a>'
            f'{f" <span class=muted>({_esc(lit.get("journal", ""))}, {lit.get("year", "")})</span>" if lit.get("journal") else ""}</li>'
        )

    links = ev.get("search_links", {})
    link_bits = []
    if links.get("clinicaltrials_gov"):
        link_bits.append(f'<a href="{_esc(links["clinicaltrials_gov"])}" target="_blank" rel="noopener">CT.gov search</a>')
    if links.get("cochrane"):
        link_bits.append(f'<a href="{_esc(links["cochrane"])}" target="_blank" rel="noopener">Cochrane</a>')
    if links.get("pubmed"):
        link_bits.append(f'<a href="{_esc(links["pubmed"])}" target="_blank" rel="noopener">PubMed</a>')

    detail = ""
    if trial_rows or lit_rows or link_bits:
        detail = f"""<details class="ev-details"><summary>View evidence</summary>
          {"<p><strong>Registry trials</strong><ul>" + "".join(trial_rows) + "</ul></p>" if trial_rows else ""}
          {"<p><strong>Published literature</strong><ul>" + "".join(lit_rows) + "</ul></p>" if lit_rows else ""}
          {"<p class=ev-search>" + " · ".join(link_bits) + "</p>" if link_bits else ""}
        </details>"""

    return f'<div class="ev-cell">{badge_html}{detail}</div>'


def _therapeutics_table(drugs: list[dict], show_via: bool = False) -> str:
    if not drugs:
        return '<p class="no-data">No therapeutics in this section.</p>'
    has_evidence = any(d.get("clinical_evidence") for d in drugs)
    rows = []
    for d in drugs:
        rep = '<span class="repurposing">Repurposing</span>' if d.get("repurposing_signal") else ""
        nat = ""
        if d.get("source_type") == "natural_agent":
            nat = '<span class="natural-agent">OSMF review</span>'
        elif d.get("source_type") == "natural_product":
            nat = '<span class="natural-agent">Natural product</span>'
        via = f'<span class="muted">via {_esc(d["via_alteration"])}</span>' if show_via and d.get("via_alteration") else ""
        ev_cell = _evidence_cell(d.get("clinical_evidence")) if has_evidence else ""
        rows.append(f"""
        <tr>
          <td class="name-cell"><strong>{_esc(d['name'])}</strong> {rep} {nat} {via}</td>
          <td class="muted">{_esc(d['drug_type_label'])}</td>
          <td>{_esc(d['phase_label'])}</td>
          <td>{_tier_badge(d['evidence_tier'], d['evidence_tier_label'])}</td>
          <td><span class="score">{d.get('score', 0)}</span></td>
          {f"<td>{ev_cell}</td>" if has_evidence else ""}
          <td class="muted">{', '.join(_esc(s) for s in d.get('sources', [])[:3])}</td>
          <td class="links-cell">{_links_html(d.get('external_links', []))}</td>
        </tr>""")
    ev_th = "<th>Trials &amp; literature</th>" if has_evidence else ""
    return f"""
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Drug</th><th>Type</th><th>Phase</th><th>Evidence</th>
          <th>Score</th>{ev_th}<th>Sources</th><th>Links</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>"""


def _np_source_links(np: dict) -> str:
    links = np.get("source_links") or {}
    bits = []
    for src in np.get("sources", []):
        url = links.get(src)
        if url:
            bits.append(f'<a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(src)}</a>')
        else:
            bits.append(_esc(src))
    return " · ".join(bits) if bits else "—"


def _np_lookup_links(summary: dict) -> str:
    lookup = summary.get("np_lookup_links") or {}
    if not lookup:
        return ""
    bits = [
        f'<a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(label)}</a>'
        for label, url in lookup.items()
    ]
    return f'<p class="section-sub">Reference lookups: {" · ".join(bits)}</p>'


def _natural_products_table(nps: list[dict]) -> str:
    if not nps:
        return '<p class="no-data">No natural products indexed for this condition yet.</p>'
    if nps[0].get("drug_type") is not None or nps[0].get("source_type") == "natural_product":
        return _therapeutics_table(nps[:80])
    rows = []
    for np in nps[:80]:
        tier = np.get("np_evidence_tier", "D")
        safety = np.get("safety_tier", "unknown")
        findings = (np.get("key_findings") or "")[:140]
        targets = ", ".join(np.get("target_names", [])[:3])
        rows.append(f"""
        <tr>
          <td class="name-cell"><strong>{_esc(np.get('name', ''))}</strong>
            {f'<div class="sub">{_esc(findings)}</div>' if findings else ''}</td>
          <td class="muted">{_esc(np.get('np_type', '').replace('_', ' '))}</td>
          <td>{_tier_badge(tier, tier)}</td>
          <td class="muted">{_esc(safety.replace('_', ' '))}</td>
          <td><span class="score">{np.get('score', 0):.0f}</span></td>
          <td class="muted">{np.get('ct_trial_count', 0)} CT · {np.get('rct_count', 0)} RCT</td>
          <td class="muted">{_np_source_links(np)}</td>
          <td class="muted">{_esc(targets) or '—'}</td>
        </tr>""")
    return f"""
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Natural product</th><th>Type</th><th>Evidence</th><th>Safety</th>
          <th>Score</th><th>Trials</th><th>Sources</th><th>Targets</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>"""


def _remission_section(data: dict) -> str:
    rem = data.get("remission") or {}
    if not rem:
        return ""

    def cell(label: str, value: str | None) -> str:
        return f"""
        <div class="rem-cell">
          <div class="label">{_esc(label)}</div>
          <div class="value">{_esc(value) or "—"}</div>
        </div>"""

    grid = "".join([
        cell("Spontaneous remission", rem.get("spontaneous_remission_rate")),
        cell("Best-intervention remission", rem.get("best_intervention_remission_rate")),
        cell("Drug-free remission", rem.get("drug_free_remission_rate")),
        cell("Relapse after remission", rem.get("relapse_rate_after_remission")),
        cell("Chronicity", rem.get("chronicity_rate")),
        cell("Gap size", rem.get("gap_size")),
        cell("Primary barrier", rem.get("barrier_type")),
    ])

    definition = rem.get("remission_definition")
    def_block = (
        f'<p class="meta-line"><strong>Remission definition:</strong> {_esc(definition)}</p>'
        if definition else ""
    )

    gbd_note = ""
    if rem.get("gbd_epi_remission_rate_per_100k") is not None:
        gbd_note = (
            f'<p class="meta-line">GBD epidemiological remission rate (USA): '
            f'{rem["gbd_epi_remission_rate_per_100k"]:.2f} per 100k person-years '
            f'(≈{100 * rem.get("gbd_epi_annual_probability", 0):.2f}% annual transition). '
            f'Population-level DisMod estimate — not clinical remission criteria.</p>'
        )

    barrier = rem.get("barrier_detail") or rem.get("notes")
    barrier_block = (
        f'<div class="barrier-note"><strong>Barrier detail:</strong> {_esc(barrier)}</div>'
        if barrier else ""
    )

    layers = ", ".join(rem.get("layers", []))
    locked = " · source-locked manual data" if rem.get("source_locked") else ""
    meta = f'<p class="meta-line">Remission data layers: {_esc(layers)}{_esc(locked)} · confidence: {_esc(rem.get("confidence", "unknown"))}</p>'

    pubmed = rem.get("pubmed_extractions") or []
    pubmed_block = ""
    if pubmed:
        links = " ".join(
            f'<a href="{_esc(p.get("pubmed_url", ""))}" target="_blank" rel="noopener" class="ext-link">'
            f'PMID {_esc(p.get("pmid", ""))}</a>'
            for p in pubmed[:5]
            if p.get("pmid")
        )
        if links:
            pubmed_block = f'<p class="meta-line">PubMed systematic reviews: {links}</p>'

    soc = rem.get("last_soc_change")
    soc_block = f'<p class="meta-line"><strong>Last SoC change:</strong> {_esc(soc)}</p>' if soc else ""

    return f"""
    <section id="remission" class="overview-card">
      <h2>Remission &amp; chronicity</h2>
      <div class="remission-grid">{grid}</div>
      {def_block}{gbd_note}{barrier_block}{soc_block}{meta}{pubmed_block}
    </section>"""


def _summary_cards(data: dict) -> str:
    s = data["summary"]
    counts = s["alteration_counts_by_type"]
    tc = s["therapeutic_counts"]
    ev_drugs = s.get("evidence_drugs", 0)
    np_count = s.get("natural_product_count", len(data.get("natural_products", [])))
    cells = [
        ("Alterations", str(s["alteration_count"])),
        ("Molecular (A)", str(counts.get("A", 0))),
        ("Clinical (B–E)", str(sum(counts.get(k, 0) for k in "BCDE"))),
        ("Direct drugs", str(tc.get("direct", 0))),
        ("Via biomarker", str(tc.get("via_biomarker", 0))),
        ("Natural agents", str(tc.get("natural", 0))),
        ("Natural products", str(np_count)),
        ("Merged ranked", str(tc.get("merged", 0))),
    ]
    if ev_drugs:
        cells.append(("With trial/literature evidence", str(ev_drugs)))
    inner = "".join(
        f'<div class="stat-cell"><div class="label">{_esc(lbl)}</div><div class="value">{_esc(val)}</div></div>'
        for lbl, val in cells
    )
    sources = ", ".join(s.get("sources_queried", [])[:8]) or "Open Targets"
    return f"""
    <div class="overview-card">
      <h2>Disease overview</h2>
      <div class="stat-grid">{inner}</div>
      <p class="meta-line">Sources: {_esc(sources)} · Pipeline phase {s.get('pipeline_phase', 1)} · Updated {_esc(data['page']['dateModified'])}</p>
    </div>"""


def build_html(data: dict) -> str:
    page = data["page"]
    slug = data["slug"]
    short = data["condition"]["shortName"]
    summary = data["summary"]
    alts = data["alterations"]
    ther = data["therapeutics"]

    type_chips = []
    for t, label in data.get("categories", {}).items():
        n = summary["alteration_counts_by_type"].get(t, 0)
        if n:
            type_chips.append(
                f'<button class="filter-chip" data-filter="{t}" type="button">{_esc(label)} ({n})</button>'
            )

    ids = data.get("identifiers", {})
    id_rows = " · ".join(
        f"{k.replace('_id','').upper()}: <code>{_esc(v)}</code>"
        for k, v in ids.items()
        if v
    )

    shown_alts = summary.get("displayed_alterations", len(alts))
    total_alts = summary["alteration_count"]
    alt_note = f"Showing {shown_alts} of {total_alts}" if shown_alts < total_alts else f"{total_alts} total"

    natural = ther.get("natural", [])
    natural_review = data.get("natural_review") or {}
    natural_note = ""
    if natural:
        review = natural_review.get("review") or {}
        cite = review.get("title") or "OSMF chronic disease narrative review"
        natural_note = (
            f'<p class="section-sub">From <a href="{_esc(natural_review.get("source_page", "https://opensourcemed.info/chronic-disease.html"))}" '
            f'target="_blank" rel="noopener">opensourcemed.info/chronic-disease</a> — {_esc(cite)}. '
            f'Candidates for further study, not approved treatments.</p>'
        )
    natural_tab = ""
    natural_panel = ""
    if natural:
        natural_tab = f'<button class="tab-btn" data-tab="natural" type="button">OSMF review ({len(natural)})</button>'
        natural_panel = f'<div class="tab-panel" id="tab-natural">{_therapeutics_table(natural)}</div>'

    nps = data.get("natural_products", [])
    np_count = summary.get("natural_product_count", len(nps))
    np_section = ""
    if np_count:
        np_section = f"""
    <section id="natural-products">
      <h2 class="section-title">Natural Products</h2>
      <p class="section-sub">{np_count} natural products with the same evidence schema as repurposed drugs — registry trials, PubMed literature, and reference links (pipeline-ranked)</p>
      {_np_lookup_links(summary)}
      {_natural_products_table(nps)}
    </section>"""

    rel = related_links(slug)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{GOOGLE_ANALYTICS_SNIPPET}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(_page_title(page, short))}</title>
  <meta name="description" content="{_esc(page['description'])}">
  <link rel="canonical" href="{_esc(page['canonical'])}">
  <link rel="icon" href="{FAVICON_URL}" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{--bg:#0a0e1a;--surface:#141828;--card:#1a1f35;--border:#2a3050;
      --text:#e1e4e8;--muted:#8892a4;--accent:#4a9eff;--green:#22c55e;--amber:#f59e0b}}
    body{{background:var(--bg);color:var(--text);font-family:Inter,sans-serif;line-height:1.6}}
    a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
    code{{background:#2a3050;padding:2px 6px;border-radius:4px;font-size:.85em}}
    nav{{background:rgba(10,14,26,.97);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}}
    .nav-container{{max-width:1200px;margin:0 auto;padding:0 1.5rem;display:flex;align-items:center;justify-content:space-between;height:60px}}
    .nav-brand{{font-weight:700;font-size:.95rem;color:var(--text)}} .nav-brand span{{color:var(--accent)}}
    .nav-links{{list-style:none;display:flex;gap:.5rem}} .nav-links a{{color:var(--muted);font-size:.85rem;padding:.35rem .75rem;border-radius:6px}}
    .nav-links a:hover,.nav-links a.active{{color:var(--text);background:var(--card);text-decoration:none}}
    .page-hero{{background:linear-gradient(135deg,#0d1230,#1a1f45);border-bottom:1px solid var(--border);padding:3rem 1.5rem 2.5rem;text-align:center}}
    .hero-eyebrow{{color:var(--accent);font-size:.8rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase}}
    .page-hero h1{{font-size:clamp(1.75rem,4vw,2.5rem);margin:.75rem 0}}
    .page-hero p{{color:var(--muted);max-width:720px;margin:0 auto}}
    main{{max-width:1200px;margin:0 auto;padding:2rem 1.5rem 4rem}}
    .breadcrumb{{display:flex;gap:.5rem;font-size:.85rem;color:var(--muted);margin-bottom:2rem;flex-wrap:wrap}}
    .overview-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.75rem;margin-bottom:2rem}}
    .overview-card h2{{font-size:1.1rem;color:var(--accent);margin-bottom:1rem}}
    .stat-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:1rem}}
    .stat-cell{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem}}
    .stat-cell .label{{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
    .stat-cell .value{{font-size:1.4rem;font-weight:700;margin-top:.25rem}}
    .remission-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:1rem}}
    .rem-cell{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem}}
    .rem-cell .label{{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
    .rem-cell .value{{font-size:.88rem;margin-top:.35rem;line-height:1.4}}
    .barrier-note{{background:rgba(74,158,255,.06);border:1px solid rgba(74,158,255,.2);border-radius:8px;padding:1rem 1.25rem;font-size:.88rem;color:var(--muted);margin-top:.75rem}}
    .meta-line,.section-sub{{color:var(--muted);font-size:.88rem;margin-bottom:1.25rem}}
    .section-title{{font-size:1.25rem;font-weight:700;margin-bottom:.25rem}}
    .filter-row{{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:1rem}}
    .filter-chip{{background:var(--card);border:1px solid var(--border);color:var(--text);border-radius:20px;padding:.35rem .9rem;font-size:.8rem;cursor:pointer}}
    .filter-chip.active,.filter-chip:hover{{border-color:var(--accent);background:rgba(74,158,255,.1)}}
    .table-wrap{{overflow-x:auto;margin-bottom:2rem}}
    .data-table{{width:100%;border-collapse:collapse;font-size:.86rem}}
    .data-table th{{text-align:left;padding:.6rem 1rem;font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);border-bottom:1px solid var(--border)}}
    .data-table td{{padding:.55rem 1rem;border-bottom:1px solid rgba(42,48,80,.5);vertical-align:top}}
    .data-table tr:hover{{background:rgba(74,158,255,.04)}}
    .name-cell strong{{color:var(--text)}} .sub{{font-size:.78rem;color:var(--muted);margin-top:.2rem}}
    .tier-badge{{display:inline-block;color:#fff;border-radius:4px;padding:2px 8px;font-size:.72rem;font-weight:700}}
    .type-badge{{display:inline-block;color:#fff;border-radius:4px;padding:2px 7px;font-size:.7rem;font-weight:600}}
    .ext-link{{font-size:.75rem;background:var(--surface);border:1px solid var(--border);border-radius:4px;padding:2px 7px;color:var(--muted)!important;margin-right:.25rem;display:inline-block}}
    .ext-link:hover{{color:var(--accent)!important;border-color:var(--accent);text-decoration:none!important}}
    .repurposing{{background:rgba(245,158,11,.15);color:var(--amber);font-size:.7rem;padding:2px 6px;border-radius:4px;margin-left:.35rem}}
    .natural-agent{{background:rgba(34,197,94,.12);color:var(--green);font-size:.7rem;padding:2px 6px;border-radius:4px;margin-left:.35rem}}
    .score{{font-weight:700;color:var(--green)}}
    .muted{{color:var(--muted)}}
    .no-data{{color:var(--muted);font-style:italic;padding:1rem 0}}
    .disclaimer{{background:rgba(74,158,255,.06);border:1px solid rgba(74,158,255,.2);border-radius:8px;padding:1rem 1.25rem;font-size:.85rem;color:var(--muted);margin-top:2rem}}
    .tab-bar{{display:flex;gap:.5rem;margin-bottom:1rem;flex-wrap:wrap}}
    .tab-btn{{background:var(--surface);border:1px solid var(--border);color:var(--muted);padding:.45rem 1rem;border-radius:8px;cursor:pointer;font-size:.85rem}}
    .tab-btn.active{{color:var(--text);border-color:var(--accent);background:rgba(74,158,255,.08)}}
    .tab-panel{{display:none}} .tab-panel.active{{display:block}}
    .ev-badge{{display:inline-block;font-size:.68rem;padding:2px 6px;border-radius:4px;margin:0 .2rem .2rem 0}}
    .ev-badge.trial{{background:rgba(74,158,255,.15);color:var(--accent)}}
    .ev-badge.lit{{background:rgba(34,197,94,.12);color:var(--green)}}
    .ev-badge.assoc{{background:rgba(245,158,11,.12);color:var(--amber)}}
    .ev-details{{margin-top:.35rem;font-size:.78rem}}
    .ev-details summary{{cursor:pointer;color:var(--accent)}}
    .ev-details ul{{margin:.35rem 0 .5rem 1rem;color:var(--muted)}}
    .ev-lit-type{{color:var(--green);font-size:.7rem;font-weight:600;margin-right:.25rem}}
    .ev-search a{{font-size:.75rem;margin-right:.5rem}}
    footer{{text-align:center;padding:2rem;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border)}}
    .related-links{{font-size:.88rem;margin-bottom:1.5rem}}
  </style>
</head>
<body>
{render_nav(depth="di", active="di")}

  <header class="page-hero">
    <div class="hero-eyebrow">{_esc(REPURPOS_BRAND)}</div>
    <h1>{_esc(short)}</h1>
    <p>{_esc(page['hero'])}</p>
  </header>

  <main>
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="../index.html">Home</a><span>/</span>
      <a href="index.html">{_esc(REPURPOS_BRAND)}</a><span>/</span>
      <span>{_esc(short)}</span>
    </nav>

    {_summary_cards(data)}

    {_remission_section(data)}

    {rel}
    <p class="meta-line">Identifiers: {id_rows or '—'}</p>

    <section id="alterations">
      <h2 class="section-title">Alterations</h2>
      <p class="section-sub">{alt_note} · Types A (molecular) through E (functional)</p>
      <div class="filter-row" id="type-filters">
        <button class="filter-chip active" data-filter="all" type="button">All</button>
        {''.join(type_chips)}
      </div>
      {_alterations_table(alts)}
    </section>

    <section id="therapeutics">
      <h2 class="section-title">Therapeutics</h2>
      <p class="section-sub">Direct disease associations, biomarker-linked drugs, OSMF narrative-review natural agents, merged ranking, and clinical trial / literature evidence (top agents)</p>
      {natural_note}
      <div class="tab-bar">
        <button class="tab-btn active" data-tab="merged" type="button">Merged ({len(ther['merged_ranked'])})</button>
        <button class="tab-btn" data-tab="direct" type="button">Direct ({len(ther['direct'])})</button>
        <button class="tab-btn" data-tab="via" type="button">Via biomarker ({len(ther['via_biomarker'])})</button>
        {natural_tab}
      </div>
      <div class="tab-panel active" id="tab-merged">{_therapeutics_table(ther['merged_ranked'])}</div>
      <div class="tab-panel" id="tab-direct">{_therapeutics_table(ther['direct'])}</div>
      <div class="tab-panel" id="tab-via">{_therapeutics_table(ther['via_biomarker'], show_via=True)}</div>
      {natural_panel}
    </section>

    {np_section}

    <p class="disclaimer">{_esc(data.get('disclaimer', ''))}</p>
  </main>

  <footer>
    Generated by OSMF Disease Intelligence Pipeline · Schema {_esc(data.get('schema_version', ''))}
  </footer>

  <script>
    document.querySelectorAll('.filter-chip').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const f = btn.dataset.filter;
        document.querySelectorAll('#alterations tbody tr').forEach(row => {{
          row.style.display = (f === 'all' || row.dataset.type === f) ? '' : 'none';
        }});
      }});
    }});
    document.querySelectorAll('.tab-btn').forEach(btn => {{
      btn.addEventListener('click', () => {{
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
      }});
    }});
  </script>
</body>
</html>"""


def build_index_html(pages: list[dict]) -> str:
    rows = []
    published = [p for p in pages if is_publishable(p) and on_db100_index(p)]
    db100 = db100_index_slugs()
    count_label = (
        f"{len(published)} conditions (100-disease database)"
        if db100 is not None
        else f"{len(published)} conditions"
    )
    for p in sorted(published, key=lambda x: x["condition"]["shortName"]):
        slug = p["slug"]
        short = p["condition"]["shortName"]
        s = p["summary"]
        tc = s["therapeutic_counts"]
        np_n = s.get("natural_product_count", len(p.get("natural_products", [])))
        nat_n = tc.get("natural", 0)
        markers = biomarker_count(p)
        clinical = clinical_biomarker_count(p)
        marker_bits = [f"{markers} biomarkers"]
        if clinical:
            marker_bits.append(f"{clinical} clinical")
        extra = []
        if np_n:
            extra.append(f"{np_n} natural products")
        if nat_n:
            extra.append(f"{nat_n} OSMF review agents")
        extra_txt = f" · {' · '.join(extra)}" if extra else ""
        rows.append(f"""
        <a class="disease-card" href="{_esc(slug)}.html">
          <h3>{_esc(short)}</h3>
          <p class="muted">{' · '.join(marker_bits)} · {tc['merged']} therapeutics{extra_txt}</p>
          <p class="date">Updated {_esc(p['page']['dateModified'])}</p>
        </a>""")
    nav = render_nav(
        depth="di",
        active="di",
        brand=REPURPOS_BRAND,
        brand_span=REPURPOS_TAGLINE,
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
{GOOGLE_ANALYTICS_SNIPPET}
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_esc(REPURPOS_FULL)}</title>
  <meta name="description" content="RepurpOS: structured biomarkers, ranked therapeutics, natural products, and clinical evidence for {count_label} — from Open Targets, HPO, ChEMBL, DGIdb, ClinicalTrials.gov, and OSMF narrative reviews.">
  <link rel="canonical" href="https://research.opensourcemed.info/disease-intelligence/index.html">
  <link rel="icon" href="{FAVICON_URL}" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{--bg:#0a0e1a;--surface:#141828;--card:#1a1f35;--border:#2a3050;--text:#e1e4e8;--muted:#8892a4;--accent:#4a9eff}}
    body{{background:var(--bg);color:var(--text);font-family:Inter,sans-serif;line-height:1.6}}
    a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
    nav{{background:rgba(10,14,26,.97);border-bottom:1px solid var(--border)}}
    .nav-container{{max-width:1200px;margin:0 auto;padding:0 1.5rem;display:flex;align-items:center;justify-content:space-between;height:60px}}
    .nav-brand{{font-weight:700;font-size:.95rem;color:var(--text)}} .nav-brand span{{color:var(--accent)}}
    .nav-links{{list-style:none;display:flex;gap:.5rem;flex-wrap:wrap}} .nav-links a{{color:var(--muted);font-size:.85rem;padding:.35rem .75rem;border-radius:6px}}
    .nav-links a:hover,.nav-links a.active{{color:var(--text);background:var(--card);text-decoration:none}}
    main{{max-width:1200px;margin:0 auto;padding:2rem 1.5rem 4rem}}
    h1{{margin-bottom:.5rem}} .sub{{color:var(--muted);margin-bottom:2rem;max-width:720px}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1rem}}
    .disease-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.25rem;text-decoration:none;color:inherit;display:block}}
    .disease-card:hover{{border-color:var(--accent)}}
    .disease-card h3{{color:var(--accent);margin-bottom:.5rem}}
    .muted{{color:var(--muted);font-size:.9rem}} .date{{font-size:.8rem;color:var(--muted);margin-top:.5rem}}
  </style>
</head>
<body>
{nav}
<main>
  <h1>{_esc(REPURPOS_BRAND)}</h1>
  <p class="sub">{_esc(REPURPOS_TAGLINE)} — structured biomarkers, ranked therapeutics, natural products, and clinical evidence for {count_label} from Open Targets, HPO, ChEMBL, DGIdb, ClinicalTrials.gov, and OSMF narrative reviews.</p>
  <div class="grid">{''.join(rows)}</div>
</main>
</body>
</html>"""


def write_page(data: dict, html_dir: Path) -> Path:
    html_dir.mkdir(parents=True, exist_ok=True)
    out = html_dir / f"{data['slug']}.html"
    out.write_text(build_html(data), encoding="utf-8")
    return out