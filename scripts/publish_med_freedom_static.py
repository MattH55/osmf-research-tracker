#!/usr/bin/env python3
"""Publish Medical Freedom Map + Gene Therapy Mapper as static GitHub Pages assets.

Outputs:
  data/med-freedom/access-public.json
  data/med-freedom/gene-therapies.json
  medical-freedom-map.html  (already maintained separately; not overwritten)
  disease-intelligence/gene-therapy-mapper.html
  maps/, states/, compare/, corrections/  (copied from med-freedom-map/frontend)

Usage (from repo root):
  python scripts/publish_med_freedom_static.py
"""
from __future__ import annotations

import html
import json
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "med-freedom-map" / "backend" / "medfreedom.db"
FRONTEND = ROOT / "med-freedom-map" / "frontend"
OUT_DATA = ROOT / "data" / "med-freedom"


def parse_json_field(x):
    if not x:
        return None
    if isinstance(x, (list, dict)):
        return x
    try:
        return json.loads(x)
    except Exception:
        return x


def export_access_json() -> dict:
    if not DB.exists():
        raise SystemExit(f"Database not found: {DB}")
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row

    jurisdictions = []
    for r in c.execute("SELECT * FROM jurisdictions"):
        d = dict(r)
        jurisdictions.append(
            {
                "id": d["id"],
                "name": d["name"],
                "type": d.get("type"),
                "country_code": d.get("country_code"),
                "latitude": d.get("latitude"),
                "longitude": d.get("longitude"),
                "general_notes": d.get("general_notes"),
                "level": d.get("level"),
                "parent_id": d.get("parent_id"),
            }
        )

    procedures = []
    for r in c.execute("SELECT * FROM procedures"):
        d = dict(r)
        procedures.append(
            {
                "id": d["id"],
                "name": d["name"],
                "modality": d.get("modality"),
                "regulatory_modality": d.get("regulatory_modality"),
                "restriction_driver": d.get("restriction_driver"),
                "therapeutic_areas": parse_json_field(d.get("therapeutic_areas")) or [],
                "diseases": parse_json_field(d.get("diseases")) or [],
                "description": d.get("description"),
                "typical_us_cost_range": d.get("typical_us_cost_range"),
            }
        )

    access = []
    q = """
    SELECT a.*, p.name as procedure_name, p.modality, p.therapeutic_areas as p_therapeutic_areas,
           p.diseases as p_diseases,
           j.name as jurisdiction_name, j.latitude as jurisdiction_latitude,
           j.longitude as jurisdiction_longitude, j.type as jurisdiction_type,
           j.country_code
    FROM access_records a
    JOIN procedures p ON a.procedure_id = p.id
    JOIN jurisdictions j ON a.jurisdiction_id = j.id
    """
    for r in c.execute(q):
        d = dict(r)
        status = str(d.get("status") or "active").lower()
        if status in ("inactive", "deprecated", "deleted"):
            continue
        access.append(
            {
                "id": d["id"],
                "procedure_id": d["procedure_id"],
                "jurisdiction_id": d["jurisdiction_id"],
                "procedure_name": d["procedure_name"],
                "jurisdiction_name": d["jurisdiction_name"],
                "jurisdiction_latitude": d["jurisdiction_latitude"],
                "jurisdiction_longitude": d["jurisdiction_longitude"],
                "jurisdiction_type": d["jurisdiction_type"],
                "country_code": d["country_code"],
                "legal_status": d.get("legal_status"),
                "access_pathway": d.get("access_pathway"),
                "oversight_quality": d.get("oversight_quality"),
                "modality": d.get("modality"),
                "estimated_cost_range_usd": d.get("estimated_cost_range_usd")
                or (str(d["price_usd"]) if d.get("price_usd") is not None else None),
                "price_usd": d.get("price_usd"),
                "access_pathway_details": d.get("access_pathway_details"),
                "eligibility_requirements": d.get("eligibility_requirements"),
                "provider_requirements": d.get("provider_requirements"),
                "residency_travel_notes": d.get("residency_travel_notes"),
                "risk_notes": d.get("risk_notes"),
                "arbitrage_summary": d.get("arbitrage_summary"),
                "oversight_notes": d.get("oversight_notes"),
                "cost_notes": d.get("cost_notes"),
                "legal_basis": d.get("legal_basis"),
                "regulatory_authority": d.get("regulatory_authority"),
                "last_verified": d.get("last_verified"),
                "sources": parse_json_field(d.get("sources")),
                "therapeutic_areas": parse_json_field(d.get("p_therapeutic_areas")) or [],
                "diseases": parse_json_field(d.get("p_diseases")) or [],
                "status": d.get("status") or "active",
            }
        )

    payload = {
        "generated": "2026-08-08",
        "source": "med-freedom-map SQLite export for static GitHub Pages",
        "counts": {
            "jurisdictions": len(jurisdictions),
            "procedures": len(procedures),
            "access_records": len(access),
        },
        "jurisdictions": jurisdictions,
        "procedures": procedures,
        "access_records": access,
        "filter_options": {
            "modalities": sorted({a["modality"] for a in access if a.get("modality")}),
            "legal_statuses": sorted(
                {a["legal_status"] for a in access if a.get("legal_status")}
            ),
            "oversight_qualities": sorted(
                {a["oversight_quality"] for a in access if a.get("oversight_quality")}
            ),
            "therapeutic_areas": sorted(
                {
                    ta
                    for a in access
                    for ta in (a.get("therapeutic_areas") or [])
                    if isinstance(ta, str)
                }
            ),
        },
    }
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    out = OUT_DATA / "access-public.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.2f} MB, {len(access)} records)")
    return payload


def export_gene_therapies() -> dict:
    sys.path.insert(0, str(ROOT / "med-freedom-map" / "backend"))
    from app.gene_therapy_data import get_gene_therapies  # type: ignore

    data = get_gene_therapies()
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    out = OUT_DATA / "gene-therapies.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    n = data.get("count", len(data.get("items", [])))
    print(f"Wrote {out} ({n} items)")
    return data


def build_gene_therapy_html(gt: dict) -> None:
    items = gt.get("items") or []
    as_of = gt.get("as_of") or "2026-07"

    def esc(s):
        return html.escape("" if s is None else str(s))

    cards = []
    for i in items:
        therapies = i.get("approved_therapies") or []
        sources = i.get("sources") or []
        burden = i.get("burden") or {}
        th_parts = []
        for t in therapies:
            th_parts.append(
                f'<div class="therapy-item approved"><strong>{esc(t.get("name"))}</strong>'
                f'<div class="detail">{esc(t.get("construct") or "")}</div>'
                f'<div class="detail">Sponsor: {esc(t.get("sponsor") or "—")} · '
                f'Approved: {esc(t.get("approved") or "—")}</div>'
                f'<div class="detail">List price: {esc(t.get("list_price_usd") or "—")}</div>'
                f'<div class="detail">Eligibility: {esc(t.get("eligibility") or "—")}</div></div>'
            )
        th_html = (
            "".join(th_parts)
            if th_parts
            else f'<div class="empty-note">{esc(i.get("pipeline_note") or "No approved gene therapy yet.")}</div>'
        )

        src_parts = []
        for s in sources:
            if isinstance(s, dict) and s.get("url"):
                src_parts.append(
                    f'<li><a href="{esc(s.get("url"))}" target="_blank" rel="noopener">'
                    f'{esc(s.get("title") or s.get("url"))}</a></li>'
                )
        src_html = "".join(src_parts)

        trials = i.get("trials_url") or (
            "https://clinicaltrials.gov/search?cond=" + esc(i.get("disease") or "")
        )
        burden_rows = []
        for k, label in [
            ("incidence", "Incidence"),
            ("carrier_frequency", "Carrier frequency"),
            ("us_patients", "US patients"),
            ("global_patients", "Global patients"),
            ("notes", "Notes"),
        ]:
            if burden.get(k):
                burden_rows.append(
                    f'<div class="info-row"><span class="info-label">{label}</span>'
                    f'<span class="info-value">{esc(burden[k])}</span></div>'
                )

        rep = i.get("repurpos")
        rep_html = ""
        profile_link = ""
        if isinstance(rep, dict):
            slug = rep.get("slug") or ""
            if slug:
                profile_link = (
                    f'<a href="{esc(slug)}.html" class="cta-button">View Disease Profile</a>'
                )
            cands = rep.get("candidates") or rep.get("items") or rep.get("top") or []
            if isinstance(cands, list) and cands:
                bits = [
                    '<div class="section-box"><div class="section-box-title">'
                    "Management / repurposing candidates</div>"
                ]
                for r in cands[:8]:
                    if isinstance(r, dict):
                        bits.append(
                            f'<div class="section-box-item"><strong>'
                            f'{esc(r.get("name") or r.get("agent") or "")}</strong> — '
                            f'{esc(r.get("rationale") or r.get("note") or "")}</div>'
                        )
                    else:
                        bits.append(f'<div class="section-box-item">{esc(r)}</div>')
                bits.append("</div>")
                rep_html = "".join(bits)

        other = (
            f'<p class="muted-note"><strong>Other treatments:</strong> '
            f'{esc(i.get("other_treatments"))}</p>'
            if i.get("other_treatments")
            else ""
        )

        cards.append(
            f'<article class="disease-card" id="{esc(i.get("id",""))}" '
            f'data-gene="{esc(i.get("gene",""))}" data-approved="{"1" if therapies else "0"}">'
            f'<h2 class="disease-title">{esc(i.get("disease"))}</h2>'
            f'<div class="info-row"><span class="info-label">Gene</span>'
            f'<span class="info-value highlight">{esc(i.get("gene"))}</span></div>'
            f'<div class="info-row"><span class="info-label">Inheritance</span>'
            f'<span class="info-value">{esc(i.get("inheritance") or "—")}</span></div>'
            f'<div class="info-row"><span class="info-label">OMIM</span>'
            f'<span class="info-value">{esc(i.get("omim") or "—")}</span></div>'
            + "".join(burden_rows)
            + f'<div class="section-box"><div class="section-box-title">Mechanism</div>'
            f'<div class="section-box-item">{esc(i.get("mechanism") or "—")}</div></div>'
            f'<div class="section-box"><div class="section-box-title">Biomarker / genetic test</div>'
            f'<div class="section-box-item">{esc(i.get("biomarker") or "—")}</div>'
            f'<div class="section-box-item">{esc(i.get("genetic_test") or "")}</div></div>'
            f'<div class="therapy-section"><div class="therapy-title">'
            f"Approved gene / cell-gene therapies</div>{th_html}</div>"
            f"{other}{rep_html}"
            f'<div style="display:flex;flex-wrap:wrap;gap:.5rem;margin-top:1rem">'
            f"{profile_link}"
            f'<a class="cta-button secondary" href="{esc(trials)}" target="_blank" '
            f'rel="noopener">ClinicalTrials.gov →</a></div>'
            + (f'<ul class="src-list">{src_html}</ul>' if src_html else "")
            + "</article>"
        )

    n = len(items)
    approved_n = sum(1 for i in items if i.get("approved_therapies"))
    cards_html = "\n".join(cards)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gene Therapy Mapper — Monogenic Diseases &amp; Approved Therapies | Open Source Medicine</title>
  <meta name="description" content="Static gene therapy mapper: {n} monogenic diseases with causal genes, genetic tests, disease burden estimates, approved products (Zolgensma, Luxturna, Casgevy, and more), and live ClinicalTrials.gov links.">
  <meta name="keywords" content="gene therapy, monogenic disease, Zolgensma, Luxturna, Casgevy, CRISPR, AAV, right to try, expanded access">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="https://research.opensourcemed.info/disease-intelligence/gene-therapy-mapper.html">
  <link rel="icon" href="https://opensourcemed.info/favicon.png" type="image/png">
  <meta property="og:type" content="website">
  <meta property="og:title" content="Gene Therapy Mapper — Monogenic Diseases">
  <meta property="og:description" content="{n} monogenic diseases with approved or advanced gene therapies, burden estimates, and trial links.">
  <meta property="og:url" content="https://research.opensourcemed.info/disease-intelligence/gene-therapy-mapper.html">
  <meta property="og:image" content="https://opensourcemed.info/favicon.png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    :root{{--bg:#0a0e1a;--surface:#141828;--card:#1a1f35;--border:#2a3050;--text:#e1e4e8;--muted:#8892a4;--accent:#4a9eff;--green:#22c55e;--amber:#f59e0b}}
    body{{background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif;line-height:1.6}}
    a{{color:var(--accent);text-decoration:none}} a:hover{{text-decoration:underline}}
    nav{{background:rgba(10,14,26,.97);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}}
    .nav-container{{max-width:1200px;margin:0 auto;padding:0 1.5rem;display:flex;align-items:center;justify-content:space-between;height:60px;flex-wrap:wrap}}
    .nav-brand{{font-weight:700;font-size:.95rem;color:var(--text)}} .nav-brand span{{color:var(--accent)}}
    .nav-links{{list-style:none;display:flex;gap:.5rem;flex-wrap:wrap}} .nav-links a{{color:var(--muted);font-size:.85rem;padding:.35rem .75rem;border-radius:6px}}
    .nav-links a:hover{{color:var(--text);background:var(--card);text-decoration:none}}
    .page-hero{{background:linear-gradient(135deg,#0d1230,#1a1f45);border-bottom:1px solid var(--border);padding:3rem 1.5rem 2.5rem;text-align:center}}
    .hero-eyebrow{{color:var(--accent);font-size:.8rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase}}
    .page-hero h1{{font-size:clamp(1.75rem,4vw,2.5rem);margin:.75rem 0}}
    .page-hero p{{color:var(--muted);max-width:720px;margin:0 auto;font-size:.95rem}}
    main{{max-width:1200px;margin:0 auto;padding:2rem 1.5rem 4rem}}
    .breadcrumb{{display:flex;gap:.5rem;font-size:.85rem;color:var(--muted);margin-bottom:1.5rem;flex-wrap:wrap}}
    .explanation-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}}
    .explanation-card h2{{font-size:1.05rem;color:var(--accent);margin-bottom:.75rem}}
    .explanation-card p,.explanation-card li{{font-size:.9rem;color:var(--muted)}}
    .explanation-card ul{{margin:.5rem 0 0 1.25rem}}
    .filter-bar{{display:flex;flex-wrap:wrap;gap:.75rem;margin:1rem 0 1.25rem;align-items:center}}
    .filter-bar input{{flex:1;min-width:220px;padding:.55rem .85rem;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text)}}
    .filter-bar label{{font-size:.85rem;color:var(--muted);display:flex;align-items:center;gap:.35rem}}
    .results-count{{font-size:.9rem;color:var(--muted);margin-bottom:1rem}}
    .disease-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:1.25rem}}
    .disease-card{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.35rem}}
    .disease-card.hidden{{display:none}}
    .disease-title{{font-size:1.05rem;font-weight:700;margin-bottom:.75rem}}
    .info-row{{display:flex;justify-content:space-between;gap:1rem;padding:.4rem 0;border-bottom:1px solid rgba(42,48,80,.35);font-size:.85rem}}
    .info-label{{color:var(--muted)}} .info-value{{font-weight:600;text-align:right}} .info-value.highlight{{color:var(--green)}}
    .section-box{{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:.85rem;margin:.85rem 0;font-size:.85rem}}
    .section-box-title{{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem;font-weight:600}}
    .section-box-item{{margin-bottom:.35rem;color:var(--muted)}} .section-box-item strong{{color:var(--text)}}
    .therapy-title{{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-weight:600;margin-bottom:.5rem}}
    .therapy-item{{background:rgba(34,197,94,.12);border:1px solid rgba(34,197,94,.25);color:var(--green);padding:.55rem .7rem;border-radius:6px;font-size:.82rem;margin-bottom:.4rem}}
    .therapy-item .detail{{color:var(--muted);font-size:.78rem;margin-top:.15rem}}
    .empty-note{{color:var(--amber);font-size:.85rem}}
    .muted-note{{color:var(--muted);font-size:.82rem;margin-top:.6rem}}
    .cta-button{{display:inline-block;padding:.55rem 1rem;background:var(--accent);color:#0a0e1a;border-radius:6px;font-size:.82rem;font-weight:600;text-decoration:none}}
    .cta-button.secondary{{background:transparent;color:var(--accent);border:1px solid rgba(74,158,255,.4)}}
    .src-list{{margin-top:.85rem;padding-left:1.1rem;font-size:.8rem;color:var(--muted)}}
    footer{{text-align:center;padding:2rem;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border)}}
    .related{{margin-top:2rem;padding:1.25rem;background:var(--card);border-radius:12px;border:1px solid var(--border)}}
    .related a{{margin-right:1rem}}
  </style>
  <script type="application/ld+json">
  {{"@context":"https://schema.org","@type":"Dataset","name":"Gene Therapy Mapper","description":"Monogenic diseases with approved or clinically advanced gene therapies.","url":"https://research.opensourcemed.info/disease-intelligence/gene-therapy-mapper.html","creator":{{"@type":"Organization","name":"Open Source Medicine Foundation"}},"dateModified":"{as_of}","isAccessibleForFree":true}}
  </script>
</head>
<body>
  <nav>
    <div class="nav-container">
      <a href="../index.html" class="nav-brand">Open Source Medicine <span>Foundation</span></a>
      <ul class="nav-links">
        <li><a href="../index.html">Research Tracker</a></li>
        <li><a href="index.html">RepurpOS</a></li>
        <li><a href="right-to-try.html">Right to Try</a></li>
        <li><a href="../medical-freedom-map.html">Freedom Map</a></li>
        <li><a href="../maps/">State Law Maps</a></li>
      </ul>
    </div>
  </nav>
  <header class="page-hero">
    <div class="hero-eyebrow">RepurpOS · Gene Therapy</div>
    <h1>Gene Therapy Mapper</h1>
    <p>{n} monogenic (or single-gene-addressable) diseases with approved or clinically advanced gene/cell-gene therapies. Burden figures are rough planning estimates — not epidemiology of record. Data as of {as_of}.</p>
  </header>
  <main>
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="../index.html">Home</a><span>/</span>
      <a href="index.html">RepurpOS</a><span>/</span>
      <span>Gene Therapy Mapper</span>
    </nav>
    <div class="explanation-card">
      <h2>What this page is</h2>
      <p>A fully static, search-engine-indexable reference (no backend API). Each card lists causal gene, inheritance, genetic test/biomarker, rough disease burden, approved products with sponsors and list prices, other treatments, and a live ClinicalTrials.gov search.</p>
      <ul>
        <li><strong>{approved_n}</strong> diseases with at least one approved therapy in this snapshot</li>
        <li>Prices are US list (WAC) where known and change over time</li>
        <li>For jurisdictional access pathways, see the <a href="../medical-freedom-map.html">Medical Freedom Arbitrage Map</a> and <a href="../maps/right-to-try/">state Right-to-Try maps</a></li>
      </ul>
    </div>
    <div class="filter-bar">
      <input type="search" id="gt-q" placeholder="Filter by disease or gene (e.g. SMN1, sickle, DMD)…" oninput="filterGT()">
      <label><input type="checkbox" id="gt-approved" onchange="filterGT()"> Approved only</label>
    </div>
    <div class="results-count" id="gt-count">Showing {n} diseases</div>
    <div class="disease-grid" id="gt-grid">
{cards_html}
    </div>
    <div class="related">
      <strong>Related:</strong>
      <a href="right-to-try.html">Right-to-Try Compendium</a>
      <a href="../medical-freedom-map.html">Medical Freedom Arbitrage Map</a>
      <a href="../maps/">State Healthcare Law Maps</a>
      <a href="../data/med-freedom/gene-therapies.json">JSON data</a>
    </div>
  </main>
  <footer>
    <p><strong>Not medical advice.</strong> Verify product labels, eligibility, and regulatory status with official sources.</p>
    <p>Open Source Medicine Foundation · research.opensourcemed.info · Data as of {as_of}</p>
  </footer>
  <script>
  function filterGT(){{
    const q = (document.getElementById('gt-q').value||'').toLowerCase().trim();
    const ao = document.getElementById('gt-approved').checked;
    let n = 0;
    document.querySelectorAll('#gt-grid .disease-card').forEach(card => {{
      const text = card.textContent.toLowerCase();
      const okQ = !q || text.includes(q) || (card.dataset.gene||'').toLowerCase().includes(q);
      const okA = !ao || card.dataset.approved === '1';
      const show = okQ && okA;
      card.classList.toggle('hidden', !show);
      if (show) n++;
    }});
    document.getElementById('gt-count').textContent = 'Showing ' + n + ' disease' + (n===1?'':'s');
  }}
  </script>
</body>
</html>
"""
    out = ROOT / "disease-intelligence" / "gene-therapy-mapper.html"
    out.write_text(page, encoding="utf-8")
    print(f"Wrote {out} ({out.stat().st_size // 1024} KB, {n} diseases)")


def copy_maps_to_site_root() -> None:
    """Copy static maps so absolute paths /maps/ /states/ /compare/ /corrections/ work."""
    maps_src = FRONTEND / "maps"
    if not maps_src.exists():
        raise SystemExit(f"Maps not found: {maps_src}")

    for name, src in [
        ("maps", maps_src),
        ("states", maps_src / "states"),
        ("compare", maps_src / "compare"),
        ("corrections", FRONTEND / "corrections"),
    ]:
        dest = ROOT / name
        if dest.exists():
            shutil.rmtree(dest)
        if src.exists():
            shutil.copytree(src, dest)
            n = len(list(dest.rglob("*.html")))
            print(f"Published /{name}/ ({n} HTML files)")
        else:
            print(f"Skip missing {src}")


def patch_map_canonicals() -> None:
    """Add research.opensourcemed.info brand link on maps hub if missing."""
    hub = ROOT / "maps" / "index.html"
    if not hub.exists():
        return
    text = hub.read_text(encoding="utf-8")
    if 'rel="canonical"' not in text:
        text = text.replace(
            '<meta name="robots" content="index,follow">',
            '<meta name="robots" content="index,follow">\n'
            '<link rel="canonical" href="https://research.opensourcemed.info/maps/">\n'
            '<meta property="og:url" content="https://research.opensourcemed.info/maps/">\n'
            '<meta property="og:title" content="Medical Freedom Maps — Healthcare Access Laws by State">',
            1,
        )
    # Point home breadcrumb to research tracker
    text = text.replace(
        '<div class="bc"><a href="/">Home</a> &raquo; Maps</div>',
        '<div class="bc"><a href="/">Research Tracker</a> &raquo; '
        '<a href="/maps/">Medical Freedom Maps</a> &raquo; Layers</div>',
    )
    # Related tools strip
    if "medical-freedom-map.html" not in text:
        text = text.replace(
            '<section class="hero"><h2>Healthcare Access Laws by State</h2>',
            '<section class="hero"><h2>Healthcare Access Laws by State</h2>'
            '<p style="margin-top:.75rem;font-size:.9rem">'
            '<a href="/medical-freedom-map.html">Procedure Access Map</a> · '
            '<a href="/disease-intelligence/right-to-try.html">Right-to-Try Disease Compendium</a> · '
            '<a href="/disease-intelligence/gene-therapy-mapper.html">Gene Therapy Mapper</a></p>',
            1,
        )
    hub.write_text(text, encoding="utf-8")
    print(f"Patched {hub}")


def main():
    print("Publishing Medical Freedom static site assets…")
    export_access_json()
    gt = export_gene_therapies()
    build_gene_therapy_html(gt)
    copy_maps_to_site_root()
    patch_map_canonicals()
    print("Done.")


if __name__ == "__main__":
    main()
