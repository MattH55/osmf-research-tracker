"""Generate static HTML pages from DiseaseIntelligencePage JSON."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from ..published_conditions import (
    biomarker_count,
    clinical_biomarker_count,
    db100_index_slugs,
    is_publishable,
    on_db100_index,
)
from ..adapters.burden.loader import get_burden_for_slug
from ..adapters.remission.hero import hero_burden_html, hero_remission_html
from ..light_theme import LIGHT_CSS, restyle_html
from ..adapters.remission.slug_map import display_names_for_slug
from ..display_np_names import resolve_np_display_name
from ..np_publications import resolve_np_publications
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

# PubMed / registry counts that indicate direct clinical evidence (not association-only hits).
_CLINICAL_EVIDENCE_KEYS = (
    "trials_registry",
    "cochrane_review",
    "meta_analysis",
    "systematic_review",
    "clinical_trial",
    "rct",
)


def _is_gmi_label(label: str | None) -> bool:
    text = str(label or "")
    return text == "GreenMedInfo" or text.startswith("GreenMedInfo (")


def _is_gmi_url(url: str | None) -> bool:
    return "greenmedinfo" in str(url or "").lower()


def _filter_gmi_sources(sources: list[str]) -> list[str]:
    return [s for s in sources if not _is_gmi_label(s)]


def _filter_gmi_lookup(lookup: dict[str, str]) -> dict[str, str]:
    return {label: url for label, url in lookup.items() if not _is_gmi_label(label)}


def _filter_gmi_links(links: list[dict]) -> list[dict]:
    return [
        link for link in links
        if not _is_gmi_label(link.get("label")) and not _is_gmi_url(link.get("url"))
    ]


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
    filtered = _filter_gmi_links(links)
    if not filtered:
        return '<span class="muted">—</span>'
    return " ".join(
        f'<a href="{_esc(l["url"])}" target="_blank" rel="noopener" class="ext-link">{_esc(l["label"])}</a>'
        for l in filtered[:4]
    )


def _price_cell(d: dict) -> str:
    prices = d.get("prices") or {}
    uk = prices.get("uk") or d.get("price_uk")
    us = prices.get("us") or d.get("price_us")
    note = d.get("price_note")
    if uk or us:
        parts = []
        if uk:
            parts.append(f'<span title="NHS / openprescribing.net">UK {_esc(uk)}</span>')
        if us:
            parts.append(f'<span title="Cost Plus Drugs / GoodRx">US {_esc(us)}</span>')
        return " · ".join(parts)
    if note:
        return f'<span class="muted" style="font-size:0.72rem">{_esc(note)}</span>'
    # Fallback for everything else
    return '<span class="muted" style="font-size:0.72rem">Varies — <a href="https://openprescribing.net/" target="_blank" rel="noopener">openprescribing.net</a> (UK) / <a href="https://www.costplusdrugs.com/" target="_blank" rel="noopener">costplusdrugs.com</a> or GoodRx (US)</span>'


def _short_pub_title(title: str, *, max_len: int = 72) -> str:
    text = re.sub(r"\s+", " ", (title or "").strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _np_publications_html(
    np: dict,
    *,
    gmi_articles: list[dict] | None = None,
    extra_evidence: dict[str, dict] | None = None,
    disease_name: str | None = None,
    limit: int = 3,
) -> str:
    pubs = resolve_np_publications(
        np,
        gmi_articles=gmi_articles,
        extra_evidence=extra_evidence,
        disease_name=disease_name,
        limit=limit,
    )
    if not pubs:
        return ""
    items = []
    for pub in pubs:
        url = pub.get("url") or ""
        if not url:
            continue
        label = _short_pub_title(pub.get("title") or url)
        study = pub.get("study_type")
        prefix = (
            f'<span class="np-pub-type">{_esc(study)}</span> '
            if study else ""
        )
        items.append(
            f'<li>{prefix}<a href="{_esc(url)}" target="_blank" rel="noopener" '
            f'title="{_esc(pub.get("title") or label)}">{_esc(label)}</a></li>'
        )
    if not items:
        return ""
    return f'<ul class="np-pubs">{"".join(items)}</ul>'


def _alteration_has_value(a: dict) -> bool:
    """True when the alteration carries a measured value (direction and/or frequency)."""
    return bool(
        a.get("direction")
        or a.get("direction_label")
        or a.get("frequency_label")
        or a.get("frequency_pct")
    )


def _alterations_value_toggle_html(alts: list[dict]) -> str:
    """Checkbox that hides alteration rows missing a direction/frequency value."""
    no_value = sum(1 for a in alts if not _alteration_has_value(a))
    if no_value == 0:
        return ""
    return f"""
      <label class="evidence-toggle" for="hide-alterations-without-value">
        <input type="checkbox" id="hide-alterations-without-value" aria-controls="alterations-table">
        <span>Hide alterations without a value (no direction or frequency)</span>
        <span class="hidden-count" data-hidden-for="hide-alterations-without-value" style="display:none"></span>
      </label>"""


def _alterations_table(alts: list[dict]) -> str:
    if not alts:
        return '<p class="no-data">No alterations in this category.</p>'
    rows = []
    for a in alts:
        dir_txt = a.get("direction_label") or "—"
        freq = a.get("frequency_label") or "—"
        defn = (a.get("definition") or "")[:120]
        row_cls = "" if _alteration_has_value(a) else ' class="alt-no-value"'
        rows.append(f"""
        <tr data-type="{_esc(a['type'])}"{row_cls}>
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
      <table class="data-table" id="alterations-table">
        <thead><tr>
          <th>Name</th><th>Type</th><th>Subtype</th><th>Direction</th>
          <th>Frequency</th><th>Evidence</th><th>Sources</th><th>Links</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>"""


def _has_direct_clinical_evidence(item: dict) -> bool:
    """True when indexed registry trials or published trial/RCT literature exist."""
    ev = item.get("clinical_evidence")
    if ev:
        counts = ev.get("counts") or {}
        if any(int(counts.get(k) or 0) > 0 for k in _CLINICAL_EVIDENCE_KEYS):
            return True
        if ev.get("clinical_trials"):
            return True
        if ev.get("literature"):
            return True
        return False
    if int(item.get("ct_trial_count") or 0) > 0 or int(item.get("rct_count") or 0) > 0:
        return True
    return False


def _therapeutic_row_class(item: dict) -> str:
    base = "therapeutic-row"
    return f"{base} has-clinical-evidence" if _has_direct_clinical_evidence(item) else f"{base} no-clinical-evidence"


def _evidence_toggle_html(checkbox_id: str, *, hidden_hint: str = "") -> str:
    return f"""
      <label class="evidence-toggle" for="{checkbox_id}">
        <input type="checkbox" id="{checkbox_id}" aria-controls="therapeutics-panels">
        <span>Show agents without direct trial evidence</span>
        <span class="hidden-count" data-hidden-for="{checkbox_id}">{hidden_hint}</span>
      </label>"""


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


def _therapeutics_table(
    drugs: list[dict],
    show_via: bool = False,
    *,
    gmi_articles: list[dict] | None = None,
    extra_evidence: dict[str, dict] | None = None,
    disease_name: str | None = None,
) -> str:
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
        drug_name = d["name"]
        np_pubs = ""
        if d.get("source_type") == "natural_product":
            drug_name = resolve_np_display_name(
                d["name"],
                common_names=d.get("common_names"),
                canonical_id=d.get("canonical_id"),
            )
            np_pubs = _np_publications_html(
                d,
                gmi_articles=gmi_articles,
                extra_evidence=extra_evidence,
                disease_name=disease_name,
            )
        rows.append(f"""
        <tr class="{_therapeutic_row_class(d)}">
          <td class="name-cell"><strong>{_esc(drug_name)}</strong> {rep} {nat} {via}
            {np_pubs}</td>
          <td class="muted">{_esc(d['drug_type_label'])}</td>
          <td>{_esc(d['phase_label'])}</td>
          <td>{_tier_badge(d['evidence_tier'], d['evidence_tier_label'])}</td>
          <td><span class="score">{d.get('score', 0)}</span></td>
          <td class="price-cell">{_price_cell(d)}</td>
          {f"<td>{ev_cell}</td>" if has_evidence else ""}
          <td class="muted">{', '.join(_esc(s) for s in _filter_gmi_sources(d.get('sources', []))[:3])}</td>
          <td class="links-cell">{_links_html(d.get('external_links', []))}</td>
        </tr>""")
    ev_th = "<th>Trials &amp; literature</th>" if has_evidence else ""
    price_th = "<th>Price (UK / US)</th>"
    return f"""
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr>
          <th>Drug</th><th>Type</th><th>Phase</th><th>Evidence</th>
          <th>Score</th>{price_th}{ev_th}<th>Sources</th><th>Links</th>
        </tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>"""


def _np_source_links(np: dict) -> str:
    links = np.get("source_links") or {}
    bits = []
    for src in _filter_gmi_sources(np.get("sources", [])):
        url = links.get(src)
        if url and not _is_gmi_url(url):
            bits.append(f'<a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(src)}</a>')
        else:
            bits.append(_esc(src))
    return " · ".join(bits) if bits else "—"


def _np_lookup_links(summary: dict) -> str:
    lookup = _filter_gmi_lookup(summary.get("np_lookup_links") or {})
    if not lookup:
        return ""
    bits = [
        f'<a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(label)}</a>'
        for label, url in lookup.items()
    ]
    return f'<p class="section-sub">Reference lookups: {" · ".join(bits)}</p>'


def _natural_products_table(
    nps: list[dict],
    *,
    gmi_articles: list[dict] | None = None,
    extra_evidence: dict[str, dict] | None = None,
    disease_name: str | None = None,
) -> str:
    if not nps:
        return '<p class="no-data">No natural products indexed for this condition yet.</p>'
    if nps[0].get("drug_type") is not None or nps[0].get("source_type") == "natural_product":
        return _therapeutics_table(
            nps[:80],
            gmi_articles=gmi_articles,
            extra_evidence=extra_evidence,
            disease_name=disease_name,
        )
    rows = []
    for np in nps[:80]:
        tier = np.get("np_evidence_tier", "D")
        safety = np.get("safety_tier", "unknown")
        findings = (np.get("key_findings") or "")[:140]
        targets = ", ".join(np.get("target_names", [])[:3])
        np_name = resolve_np_display_name(
            np.get("name", ""),
            common_names=np.get("common_names"),
            canonical_id=np.get("canonical_id"),
        )
        np_pubs = _np_publications_html(
            np,
            gmi_articles=gmi_articles,
            extra_evidence=extra_evidence,
            disease_name=disease_name,
        )
        rows.append(f"""
        <tr class="{_therapeutic_row_class(np)}">
          <td class="name-cell"><strong>{_esc(np_name)}</strong>
            {np_pubs}
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
    sources = ", ".join(_filter_gmi_sources(s.get("sources_queried", []))[:8]) or "Open Targets"
    return f"""
    <div class="overview-card">
      <h2>Disease overview</h2>
      <div class="stat-grid">{inner}</div>
      <p class="meta-line">Sources: {_esc(sources)} · Pipeline phase {s.get('pipeline_phase', 1)} · Updated {_esc(data['page']['dateModified'])}</p>
    </div>"""


def build_html(data: dict) -> str:
    page = data["page"]
    slug = data["slug"]
    short, full = display_names_for_slug(
        slug,
        fallback_short=data["condition"].get("shortName"),
        fallback_full=data["condition"].get("name"),
    )
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
    gmi_articles: list[dict] = []
    np_extra_evidence = data.get("natural_product_evidence") or {}
    disease_name = (data.get("condition") or {}).get("name") or short
    np_count = summary.get("natural_product_count", len(nps))
    np_section = ""
    if np_count:
        np_section = f"""
    <section id="natural-products">
      <h2 class="section-title">Natural Products</h2>
      <p class="section-sub">{np_count} natural products with the same evidence schema as repurposed drugs — registry trials, PubMed literature, and reference links (pipeline-ranked). Only agents with direct clinical evidence are shown by default.</p>
      {_np_lookup_links(summary)}
      {_evidence_toggle_html("show-no-evidence-natural")}
      {_natural_products_table(nps, gmi_articles=gmi_articles, extra_evidence=np_extra_evidence, disease_name=disease_name)}
    </section>"""

    rel = related_links(slug)
    burden = data.get("burden") or get_burden_for_slug(slug, data["condition"]["name"])

    return restyle_html(f"""<!DOCTYPE html>
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
{LIGHT_CSS}  </style>
</head>
<body>
{render_nav(depth="di", active="di")}

  <header class="page-hero">
    <div class="hero-eyebrow">{_esc(REPURPOS_BRAND)}</div>
    <h1>{_esc(short)}</h1>
    <p>{_esc(page['hero'])}</p>
    {hero_burden_html(burden)}
    {hero_remission_html(data.get("remission"), detail_anchor="#remission")}
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
      {_alterations_value_toggle_html(alts)}
      {_alterations_table(alts)}
      <p class="no-data" id="alterations-no-value-msg" hidden>Every alteration recorded for this condition is missing a direction or frequency value.</p>
    </section>

    <section id="therapeutics">
      <h2 class="section-title">Therapeutics</h2>
      <p class="section-sub">Direct disease associations, biomarker-linked drugs, OSMF narrative-review natural agents, and merged ranking. Only agents with registry trials or published clinical literature are shown by default.</p>
      {natural_note}
      {_evidence_toggle_html("show-no-evidence-therapeutics")}
      <div class="tab-bar" id="therapeutics-panels">
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
    function bindEvidenceToggle(checkboxId) {{
      var cb = document.getElementById(checkboxId);
      if (!cb) return;
      var scope = cb.closest('section');
      if (!scope) return;
      var hidden = scope.querySelectorAll('.therapeutic-row.no-clinical-evidence').length;
      var hint = scope.querySelector('[data-hidden-for="' + checkboxId + '"]');
      if (hint && hidden) hint.textContent = '(' + hidden + ' hidden)';
      cb.addEventListener('change', function() {{
        scope.classList.toggle('show-no-clinical-evidence', cb.checked);
      }});
    }}
    bindEvidenceToggle('show-no-evidence-therapeutics');
    bindEvidenceToggle('show-no-evidence-natural');
    (function () {{
      var cb = document.getElementById('hide-alterations-without-value');
      if (!cb) return;
      var section = document.getElementById('alterations');
      if (!section) return;
      var body = section.querySelector('tbody');
      var noValueRows = body ? body.querySelectorAll('tr.alt-no-value').length : 0;
      var totalRows = body ? body.querySelectorAll('tr').length : 0;
      var hint = section.querySelector('[data-hidden-for="hide-alterations-without-value"]');
      var emptyMsg = document.getElementById('alterations-no-value-msg');
      function apply() {{
        section.classList.toggle('hide-alterations-without-value', cb.checked);
        if (hint) {{
          hint.textContent = '(' + noValueRows + ' hidden)';
          hint.style.display = (cb.checked && noValueRows) ? '' : 'none';
        }}
        if (emptyMsg) {{
          emptyMsg.hidden = !(cb.checked && noValueRows >= totalRows);
        }}
      }}
      cb.addEventListener('change', apply);
      apply();
    }})();
  </script>
</body>
</html>""")


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
        <a class="disease-card" href="{_esc(slug)}.html" data-slug="{_esc(slug)}">
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
    return restyle_html(f"""<!DOCTYPE html>
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
{LIGHT_CSS}  </style>
</head>
<body>
{nav}
<main>
  <h1>{_esc(REPURPOS_BRAND)}</h1>
  <p class="sub">{_esc(REPURPOS_TAGLINE)} — structured biomarkers, ranked therapeutics, natural products, and clinical evidence for {count_label} from Open Targets, HPO, ChEMBL, DGIdb, ClinicalTrials.gov, and OSMF narrative reviews.</p>
  <div class="search-bar">
    <div class="search-wrap">
      <span class="search-icon" aria-hidden="true">&#8981;</span>
      <input id="condition-search" type="search" placeholder="Search conditions by name, abbreviation, or keyword…" autocomplete="off" spellcheck="false" aria-label="Search conditions">
    </div>
    <button type="button" class="search-clear" id="search-clear" hidden>Clear</button>
    <p class="search-meta" id="search-meta" aria-live="polite"></p>
  </div>
  <div class="grid" id="condition-grid">{''.join(rows)}
    <div class="search-empty" id="search-empty">No conditions match your search. Try a different name or abbreviation.</div>
  </div>
</main>
<script>
(function() {{
  const input = document.getElementById('condition-search');
  const grid = document.getElementById('condition-grid');
  const meta = document.getElementById('search-meta');
  const clearBtn = document.getElementById('search-clear');
  const emptyEl = document.getElementById('search-empty');
  const cards = Array.from(grid.querySelectorAll('.disease-card'));

  function normalize(value) {{
    return value.toLowerCase().normalize('NFD').replace(/[\\u0300-\\u036f]/g, '');
  }}

  function cardText(card) {{
    const slug = card.getAttribute('data-slug') || (card.getAttribute('href') || '').replace(/\\.html$/, '');
    return normalize(card.textContent + ' ' + slug.replace(/-/g, ' '));
  }}

  function filterCards() {{
    const query = normalize(input.value.trim());
    let visible = 0;
    cards.forEach(function(card) {{
      const show = !query || cardText(card).includes(query);
      card.classList.toggle('hidden', !show);
      if (show) visible += 1;
    }});
    emptyEl.classList.toggle('visible', !!query && visible === 0);
    meta.textContent = query
      ? 'Showing ' + visible + ' of ' + cards.length
      : cards.length + ' conditions';
    clearBtn.hidden = !query;
  }}

  input.addEventListener('input', filterCards);
  clearBtn.addEventListener('click', function() {{
    input.value = '';
    input.focus();
    filterCards();
  }});
  document.addEventListener('keydown', function(event) {{
    if (event.key === '/' && document.activeElement !== input) {{
      event.preventDefault();
      input.focus();
    }}
    if (event.key === 'Escape' && document.activeElement === input) {{
      input.value = '';
      input.blur();
      filterCards();
    }}
  }});
  filterCards();
}})();
</script>
</body>
</html>""")


def write_page(data: dict, html_dir: Path) -> Path:
    html_dir.mkdir(parents=True, exist_ok=True)
    out = html_dir / f"{data['slug']}.html"
    out.write_text(build_html(data), encoding="utf-8")
    return out