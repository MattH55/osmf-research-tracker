#!/usr/bin/env python3
"""
Generate one HTML page per disease showing:
  - Disease overview card (remission rates, primary barrier, from CSV)
  - Biomarker → therapeutic agent table (from pipeline JSON results)
  - Clinical trials section (from ClinicalTrials.gov v2 API, live fetch)

Output: research-tracker/chronic-disease-interventions/{slug}.html

Usage:
    # From research-tracker/ directory:
    python -m biomarker_pipeline.generate_disease_pages
    python -m biomarker_pipeline.generate_disease_pages --skip-trials
"""
import argparse
import csv
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CSV_PATH     = Path(__file__).parent.parent / "cure_vs_chronic_50.csv"
RESULTS_DIR  = Path(__file__).parent / "results" / "biomarkers"
DISEASE_AGENTS_DIR = Path(__file__).parent / "results" / "disease_agents"
ATLAS_DATA_DIR = Path(__file__).parent.parent / "data" / "biomarkers"
OUTPUT_DIR   = Path(__file__).parent.parent / "chronic-disease-interventions"

CT_API       = "https://clinicaltrials.gov/api/v2/studies"
NOW_ISO      = datetime.now(timezone.utc).strftime("%Y-%m-%d")

# Evidence tier badge colours
TIER_COLOUR = {
    "clinical":     "#22c55e",   # green
    "mechanistic":  "#4a9eff",   # blue
    "correlative":  "#f59e0b",   # amber
}

TIER_LABEL = {
    "clinical":     "Clinical",
    "mechanistic":  "Mechanistic",
    "correlative":  "Correlative",
}

DIRECTION_SYMBOL = {
    "inhibits":   "↓",
    "decreases":  "↓",
    "activates":  "↑",
    "increases":  "↑",
    "modulates":  "~",
    "unclear":    "?",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _esc(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _fetch_trials(disease_name: str, max_results: int = 15) -> list[dict]:
    params = {
        "query.cond": disease_name,
        "filter.overallStatus": "RECRUITING,ACTIVE_NOT_RECRUITING,COMPLETED",
        "format": "json",
        "pageSize": str(max_results),
        "sort": "LastUpdatePostDate:desc",
    }
    url = CT_API + "?" + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "OSMF-BiomarkerPipeline/0.1 (research@opensourcemed.info)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        studies = []
        for s in data.get("studies", []):
            proto = s.get("protocolSection", {})
            ident = proto.get("identificationModule", {})
            status = proto.get("statusModule", {})
            design = proto.get("designModule", {})
            desc   = proto.get("descriptionModule", {})
            studies.append({
                "nct_id":    ident.get("nctId", ""),
                "title":     ident.get("briefTitle", ""),
                "status":    status.get("overallStatus", ""),
                "phase":     ", ".join(design.get("phases", [])) or "N/A",
                "start":     (status.get("startDateStruct") or {}).get("date", ""),
                "summary":   (desc.get("briefSummary", "") or "")[:300].replace("\n", " "),
            })
        return studies
    except Exception as e:
        log.warning("ClinicalTrials.gov fetch failed for '%s': %s", disease_name, e)
        return []


def _load_pipeline_results(disease: str) -> dict[str, dict]:
    """Return {gene: pipeline_output_dict} for a disease. Empty dict if not yet run."""
    slug = _slug(disease)
    disease_dir = RESULTS_DIR / slug
    results: dict[str, dict] = {}
    if not disease_dir.exists():
        return results
    for json_file in sorted(disease_dir.glob("*.json")):
        gene = json_file.stem
        try:
            results[gene] = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("Could not load %s: %s", json_file, e)
    return results


def _status_badge(status: str) -> str:
    colour = {
        "RECRUITING":             "#22c55e",
        "ACTIVE_NOT_RECRUITING":  "#4a9eff",
        "COMPLETED":              "#94a3b8",
        "TERMINATED":             "#ef4444",
        "WITHDRAWN":              "#ef4444",
    }.get(status.upper(), "#94a3b8")
    label = status.replace("_", " ").title()
    return f'<span style="background:{colour};color:#fff;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600">{_esc(label)}</span>'


# ── HTML builder ─────────────────────────────────────────────────────────────

def _biomarker_section(gene: str, data: dict) -> str:
    agents = data.get("agents", [])
    bm     = data.get("biomarker", {})
    uniprot = bm.get("uniprot_id", "")
    ensembl = bm.get("ensembl_id", "")

    ext_links = ""
    if uniprot:
        ext_links += f'<a href="https://www.uniprot.org/uniprot/{_esc(uniprot)}" target="_blank" rel="noopener" class="ext-link">UniProt</a> '
    if ensembl:
        ext_links += f'<a href="https://www.ensembl.org/id/{_esc(ensembl)}" target="_blank" rel="noopener" class="ext-link">Ensembl</a> '
    ext_links += f'<a href="https://dgidb.org/genes/{_esc(gene)}" target="_blank" rel="noopener" class="ext-link">DGIdb</a> '
    ext_links += f'<a href="https://platform.opentargets.org/target/{_esc(ensembl or gene)}" target="_blank" rel="noopener" class="ext-link">Open Targets</a>'

    if not agents:
        return f"""
        <div class="gene-card" id="gene-{_esc(gene)}">
          <div class="gene-header">
            <h3>{_esc(gene)}</h3>
            <div class="ext-links">{ext_links}</div>
          </div>
          <p class="no-data">Pipeline results not yet available for this target. Run the pipeline to populate.</p>
        </div>"""

    rows_html = ""
    for a in agents[:40]:
        tier   = a.get("evidence_tier", "correlative")
        colour = TIER_COLOUR.get(tier, "#94a3b8")
        label  = TIER_LABEL.get(tier, tier)
        direc  = a.get("direction_of_effect", "unclear")
        sym    = DIRECTION_SYMBOL.get(direc, "?")
        name   = _esc(a.get("agent_name", ""))
        potency = ""
        pdata  = a.get("potency") or {}
        if pdata.get("value") and pdata.get("measure"):
            potency = f'{pdata["value"]} {pdata.get("unit","") or ""} ({_esc(pdata["measure"])})'

        # Source link (first DGIdb or ChEMBL source with a URL)
        src_link = ""
        for src in (a.get("sources") or []):
            if src.get("url"):
                src_db = _esc(src.get("database") or "Source")
                src_link = f'<a href="{_esc(src["url"])}" target="_blank" rel="noopener">{src_db}</a>'
                break
            if src.get("pubmed_id"):
                pmid = _esc(src["pubmed_id"])
                src_link = f'<a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/" target="_blank" rel="noopener">PubMed&nbsp;{pmid}</a>'
                break

        rows_html += f"""
          <tr>
            <td class="agent-name">{name}</td>
            <td class="direction">{sym} <span class="dir-text">{_esc(direc)}</span></td>
            <td><span class="tier-badge" style="background:{colour}">{label}</span></td>
            <td class="potency">{potency}</td>
            <td class="source-link">{src_link}</td>
          </tr>"""

    total = len(agents)
    shown = min(40, total)
    more_note = f'<p class="more-note">Showing top {shown} of {total} agents ranked by evidence tier.</p>' if total > 40 else ""

    return f"""
    <div class="gene-card" id="gene-{_esc(gene)}">
      <div class="gene-header">
        <h3>{_esc(gene)}</h3>
        <div class="ext-links">{ext_links}</div>
      </div>
      <div class="table-wrap">
        <table class="agents-table">
          <thead>
            <tr>
              <th>Therapeutic Agent</th>
              <th>Effect Direction</th>
              <th>Evidence Tier</th>
              <th>Potency</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
      {more_note}
    </div>"""


def _trials_section(trials: list[dict]) -> str:
    if not trials:
        return '<p class="no-data">No recent clinical trials found on ClinicalTrials.gov for this condition.</p>'
    cards = ""
    for t in trials:
        nct   = _esc(t["nct_id"])
        title = _esc(t["title"])
        phase = _esc(t["phase"])
        start = _esc(t.get("start", ""))
        summ  = _esc(t.get("summary", ""))
        badge = _status_badge(t.get("status", ""))
        url   = f"https://clinicaltrials.gov/study/{nct}"
        cards += f"""
        <div class="trial-card">
          <div class="trial-header">
            <a href="{url}" target="_blank" rel="noopener" class="trial-title">{title}</a>
            {badge}
          </div>
          <div class="trial-meta">
            <span class="trial-nct">{nct}</span>
            <span class="trial-phase">Phase: {phase}</span>
            {f'<span class="trial-start">Started: {start}</span>' if start else ""}
          </div>
          {f'<p class="trial-summary">{summ}{"..." if len(t.get("summary","")) >= 300 else ""}</p>' if summ else ""}
        </div>"""
    return cards


def _load_disease_agents(disease: str) -> list[dict]:
    """Load disease-level agent discovery results (search FROM the disease
    directly via ClinicalTrials.gov interventions + Open Targets disease
    knownDrugs), produced by run_disease_agent_discovery.py. Distinct from
    _load_pipeline_results(), which is gene-first and only finds agents
    interacting with the disease's ~10-15 curated genes."""
    path = DISEASE_AGENTS_DIR / f"{_slug(disease)}.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("candidates", [])
    except Exception as e:
        log.warning("Could not load disease agents for %s: %s", disease, e)
        return []


_PHASE_LABELS = {
    "PRECLINICAL": "Preclinical", "IND": "IND", "EARLY_PHASE_1": "Early Phase 1",
    "PHASE_1": "Phase 1", "PHASE_1_2": "Phase 1/2", "PHASE_2": "Phase 2",
    "PHASE_2_3": "Phase 2/3", "PHASE_3": "Phase 3", "PREAPPROVAL": "Pre-approval",
    "APPROVAL": "Approved", "UNKNOWN": "Unknown",
}


def _disease_agents_section(candidates: list[dict], gene_first_names: set[str]) -> str:
    if not candidates:
        return (
            '<p class="no-data pending">Not yet run. '
            '<code>python -m biomarker_pipeline.run_disease_agent_discovery --disease "...''"</code></p>'
        )

    # Highlight agents this disease's curated gene panel wouldn't have found —
    # the whole point of searching from the disease instead of a gene list.
    def _norm(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", name.lower())

    rows_html = ""
    shown = [c for c in candidates if c.get("approval_status") == "Approved" or c.get("trial_evidence")][:60]
    for c in shown:
        name = _esc(c["agent_name"])
        is_new = _norm(c["agent_name"]) not in gene_first_names
        new_badge = '<span style="background:#f59e0b;color:#1a1200;padding:2px 8px;border-radius:4px;font-size:0.72rem;font-weight:700;margin-left:0.4rem">NOT in gene-target list</span>' if is_new else ""
        phase = _PHASE_LABELS.get(c.get("max_phase") or "", c.get("max_phase") or "")
        approved = '<span style="color:#22c55e;font-weight:600">Approved</span>' if c.get("approval_status") == "Approved" else _esc(phase)
        n_trials = len(c.get("trial_evidence") or [])
        sources = ", ".join(_esc(s) for s in c.get("sources", []))
        trial_links = " ".join(
            f'<a href="https://clinicaltrials.gov/study/{_esc(e["nct_id"])}" target="_blank" rel="noopener" class="ext-link">{_esc(e["nct_id"])}</a>'
            for e in (c.get("trial_evidence") or [])[:3]
        )
        rows_html += f"""
        <div class="gene-card" style="padding:0.9rem 1.2rem">
          <div class="gene-header" style="margin-bottom:0.3rem">
            <h3 style="font-size:1rem">{name}{new_badge}</h3>
          </div>
          <p style="font-size:0.82rem;color:#8892a4;margin:0">
            {approved} &middot; {n_trials} trial{"s" if n_trials != 1 else ""} &middot; source: {sources}
            {f'<br>{trial_links}' if trial_links else ""}
          </p>
        </div>"""

    n_new = sum(1 for c in shown if _norm(c["agent_name"]) not in gene_first_names)
    summary = f'<p class="section-sub">{len(shown)} agents shown (approved or with trial evidence) &mdash; {n_new} not found by the gene-target search above.</p>'
    return summary + rows_html


def build_page(
    disease: str,
    csv_row: dict,
    pipeline_data: dict[str, dict],
    trials: list[dict],
    disease_agents: list[dict] | None = None,
) -> str:
    slug     = _slug(disease)
    title    = _esc(disease)
    page_url = f"https://research.opensourcemed.info/chronic-disease-interventions/{slug}.html"

    spont  = _esc(csv_row.get("spontaneous_remission_rate", ""))
    best   = _esc(csv_row.get("best_intervention_remission_rate", ""))
    gap    = _esc(csv_row.get("gap_size", ""))
    barrier= _esc(csv_row.get("primary_barrier", ""))
    notes  = _esc(csv_row.get("notes", ""))

    gene_sections = ""
    if pipeline_data:
        gene_sections = "\n".join(_biomarker_section(gene, data) for gene, data in sorted(pipeline_data.items()))
    else:
        gene_sections = '<p class="no-data pending">Pipeline results not yet available. Run: <code>python -m biomarker_pipeline.run_for_diseases --skip-llm</code></p>'

    trials_html = _trials_section(trials)

    # Build gene index chips
    gene_chips = ""
    if pipeline_data:
        for gene in sorted(pipeline_data.keys()):
            n = len(pipeline_data[gene].get("agents", []))
            gene_chips += f'<a href="#gene-{_esc(gene)}" class="gene-chip">{_esc(gene)} <span class="chip-count">{n}</span></a>'

    gene_first_names = {
        re.sub(r"[^a-z0-9]+", "", (a.get("agent_name", "")).lower())
        for data in pipeline_data.values()
        for a in data.get("agents", [])
    }
    disease_agents_html = _disease_agents_section(disease_agents or [], gene_first_names)

    atlas_crosslink = ""
    if (ATLAS_DATA_DIR / f"{slug}.json").exists():
        atlas_crosslink = f"""
    <span>/</span>
    <a href="../{slug}-biomarkers.html">Biomarker Atlas &rarr;</a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Biomarkers &amp; Therapeutic Agents | OSMF</title>
  <meta name="description" content="Pharmacologically actionable biomarkers and therapeutic agents for {title}, with evidence tiers from DGIdb, Open Targets, ChEMBL, and peer-reviewed literature. Clinical trials from ClinicalTrials.gov.">
  <link rel="canonical" href="{page_url}">
  <meta property="og:type" content="article">
  <meta property="og:title" content="{title} — Biomarkers &amp; Therapeutic Agents | OSMF">
  <meta property="og:url" content="{page_url}">
  <meta property="og:site_name" content="Open Source Medicine Foundation">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="../favicon.png" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    :root {{
      --bg: #0a0e1a; --surface: #141828; --card: #1a1f35;
      --border: #2a3050; --text: #e1e4e8; --muted: #8892a4;
      --accent: #4a9eff; --accent2: #7c6af7;
      --green: #22c55e; --amber: #f59e0b; --red: #ef4444;
    }}
    body {{ background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; line-height: 1.6; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    code {{ background: #2a3050; padding: 2px 6px; border-radius: 4px; font-size: 0.875em; }}

    /* Nav */
    nav {{ background: rgba(10,14,26,0.97); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 100; }}
    .nav-container {{ max-width: 1200px; margin: 0 auto; padding: 0 1.5rem; display: flex; align-items: center; justify-content: space-between; height: 60px; }}
    .nav-brand {{ color: var(--text); font-weight: 700; font-size: 0.95rem; line-height: 1.2; display: flex; flex-direction: column; }}
    .nav-brand span {{ color: var(--accent); }}
    .nav-brand-sub {{ color: var(--muted); font-size: 0.7rem; font-weight: 400; }}
    .nav-links {{ list-style: none; display: flex; gap: 0.25rem; align-items: center; flex-wrap: wrap; }}
    .nav-links a {{ color: var(--muted); padding: 0.35rem 0.75rem; border-radius: 6px; font-size: 0.85rem; transition: all 0.2s; }}
    .nav-links a:hover, .nav-links a.active {{ color: var(--text); background: var(--card); text-decoration: none; }}
    .nav-support {{ background: var(--accent) !important; color: #fff !important; font-weight: 600; }}

    /* Hero */
    .page-hero {{ background: linear-gradient(135deg, #0d1230 0%, #1a1f45 100%); border-bottom: 1px solid var(--border); padding: 3rem 1.5rem 2.5rem; text-align: center; }}
    .hero-eyebrow {{ color: var(--accent); font-size: 0.8rem; font-weight: 600; letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 0.75rem; }}
    .page-hero h1 {{ font-size: clamp(1.75rem, 4vw, 2.75rem); font-weight: 700; margin-bottom: 0.75rem; }}
    .page-hero p {{ color: var(--muted); max-width: 700px; margin: 0 auto; font-size: 1rem; }}

    /* Main layout */
    main {{ max-width: 1200px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}

    /* Breadcrumb */
    .breadcrumb {{ display: flex; gap: 0.5rem; font-size: 0.85rem; color: var(--muted); margin-bottom: 2rem; }}
    .breadcrumb a {{ color: var(--muted); }}
    .breadcrumb a:hover {{ color: var(--accent); }}
    .breadcrumb span {{ color: var(--border); }}

    /* Disease overview card */
    .overview-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; padding: 1.75rem; margin-bottom: 2.5rem; }}
    .overview-card h2 {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 1.25rem; color: var(--accent); }}
    .remission-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 1.25rem; }}
    .rem-cell {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1rem; }}
    .rem-cell .label {{ font-size: 0.75rem; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.4rem; }}
    .rem-cell .value {{ font-size: 0.9rem; color: var(--text); line-height: 1.4; }}
    .barrier-note {{ background: rgba(74,158,255,0.06); border: 1px solid rgba(74,158,255,0.2); border-radius: 8px; padding: 1rem 1.25rem; font-size: 0.9rem; color: var(--muted); }}
    .barrier-note strong {{ color: var(--text); }}

    /* Section headings */
    .section-title {{ font-size: 1.3rem; font-weight: 700; margin-bottom: 0.35rem; }}
    .section-sub {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 1.5rem; }}

    /* Gene index */
    .gene-index {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 2rem; }}
    .gene-chip {{ background: var(--card); border: 1px solid var(--border); border-radius: 20px; padding: 0.3rem 0.9rem; font-size: 0.82rem; font-weight: 600; color: var(--text); transition: all 0.2s; display: inline-flex; align-items: center; gap: 0.4rem; }}
    .gene-chip:hover {{ border-color: var(--accent); text-decoration: none; background: rgba(74,158,255,0.08); }}
    .chip-count {{ background: var(--accent); color: #fff; border-radius: 10px; padding: 0 6px; font-size: 0.72rem; }}

    /* Gene cards */
    .gene-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 12px; margin-bottom: 1.5rem; overflow: hidden; scroll-margin-top: 80px; }}
    .gene-header {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.75rem; padding: 1.1rem 1.5rem; border-bottom: 1px solid var(--border); background: rgba(74,158,255,0.04); }}
    .gene-header h3 {{ font-size: 1.05rem; font-weight: 700; color: var(--accent); }}
    .ext-links {{ display: flex; gap: 0.4rem; flex-wrap: wrap; }}
    .ext-link {{ font-size: 0.75rem; background: var(--surface); border: 1px solid var(--border); border-radius: 4px; padding: 2px 8px; color: var(--muted) !important; }}
    .ext-link:hover {{ color: var(--accent) !important; border-color: var(--accent); text-decoration: none !important; }}

    /* Agents table */
    .table-wrap {{ overflow-x: auto; padding: 0.5rem 0; }}
    table.agents-table {{ width: 100%; border-collapse: collapse; font-size: 0.87rem; }}
    .agents-table th {{ padding: 0.6rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); border-bottom: 1px solid var(--border); white-space: nowrap; }}
    .agents-table td {{ padding: 0.55rem 1rem; border-bottom: 1px solid rgba(42,48,80,0.5); vertical-align: middle; }}
    .agents-table tbody tr:last-child td {{ border-bottom: none; }}
    .agents-table tbody tr:hover {{ background: rgba(74,158,255,0.04); }}
    .agent-name {{ font-weight: 600; }}
    .direction {{ font-size: 0.9rem; }}
    .dir-text {{ color: var(--muted); font-size: 0.8rem; }}
    .tier-badge {{ display: inline-block; color: #fff; border-radius: 4px; padding: 2px 8px; font-size: 0.74rem; font-weight: 700; letter-spacing: 0.04em; }}
    .potency {{ color: var(--muted); font-size: 0.82rem; font-family: monospace; }}
    .source-link a {{ font-size: 0.8rem; color: var(--muted); }}
    .source-link a:hover {{ color: var(--accent); }}
    .more-note {{ font-size: 0.8rem; color: var(--muted); padding: 0.6rem 1.5rem; border-top: 1px solid var(--border); }}
    .no-data {{ color: var(--muted); font-size: 0.9rem; padding: 1.5rem; }}
    .no-data.pending {{ font-style: italic; }}

    /* Clinical trials */
    .trial-card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.1rem 1.25rem; margin-bottom: 0.85rem; }}
    .trial-header {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: 0.5rem; }}
    .trial-title {{ font-size: 0.92rem; font-weight: 600; color: var(--text); line-height: 1.4; flex: 1; }}
    .trial-title:hover {{ color: var(--accent); }}
    .trial-meta {{ display: flex; flex-wrap: wrap; gap: 0.75rem; font-size: 0.78rem; color: var(--muted); margin-bottom: 0.5rem; }}
    .trial-nct {{ font-family: monospace; color: var(--accent); }}
    .trial-summary {{ font-size: 0.85rem; color: var(--muted); line-height: 1.5; }}

    /* Divider between sections */
    .section-divider {{ border: none; border-top: 1px solid var(--border); margin: 2.5rem 0; }}

    /* Footer */
    footer {{ background: var(--surface); border-top: 1px solid var(--border); padding: 2rem 1.5rem; text-align: center; color: var(--muted); font-size: 0.82rem; }}
    footer a {{ color: var(--muted); }}
    footer a:hover {{ color: var(--accent); }}

    @media (max-width: 640px) {{
      .nav-links {{ display: none; }}
      .remission-grid {{ grid-template-columns: 1fr; }}
      .trial-header {{ flex-direction: column; }}
    }}
  </style>
</head>
<body>

<nav>
  <div class="nav-container">
    <a href="https://opensourcemed.info" class="nav-brand">
      Open Source <span>Medicine</span>
      <span class="nav-brand-sub">Research Tracker</span>
    </a>
    <ul class="nav-links">
      <li><a href="../index.html">All Conditions</a></li>
      <li><a href="../biomarker-atlas.html">Biomarker Atlas</a></li>
      <li><a href="../clinical_trials.html">Clinical Trials</a></li>
      <li><a href="../agents.html">Agents</a></li>
      <li><a href="https://opensourcemed.info/campaign.html" class="nav-support">Support Us</a></li>
    </ul>
  </div>
</nav>

<section class="page-hero">
  <div class="hero-eyebrow">Biomarker &amp; Intervention Discovery</div>
  <h1>{title}</h1>
  <p>Pharmacologically actionable gene targets, therapeutic agents ranked by evidence tier, and active clinical trials.</p>
</section>

<main>
  <div class="breadcrumb">
    <a href="../index.html">Research Tracker</a>
    <span>/</span>
    <a href="index.html">Chronic Disease Interventions</a>
    <span>/</span>
    <span>{title}</span>{atlas_crosslink}
  </div>

  <!-- Disease overview -->
  <div class="overview-card">
    <h2>Disease Overview</h2>
    <div class="remission-grid">
      <div class="rem-cell">
        <div class="label">Spontaneous remission</div>
        <div class="value">{spont or "Not established"}</div>
      </div>
      <div class="rem-cell">
        <div class="label">Best-intervention remission</div>
        <div class="value">{best or "—"}</div>
      </div>
      <div class="rem-cell">
        <div class="label">Gap size</div>
        <div class="value">{gap or "—"}</div>
      </div>
      <div class="rem-cell">
        <div class="label">Primary barrier</div>
        <div class="value">{barrier or "—"}</div>
      </div>
    </div>
    {f'<div class="barrier-note">{notes}</div>' if notes else ""}
  </div>

  <!-- Biomarker targets -->
  <div class="section-title">Biomarker Targets &amp; Therapeutic Agents</div>
  <p class="section-sub">
    Gene targets queried against DGIdb, Open Targets, ChEMBL, PubMed, and Europe PMC.
    Agents ranked: <span style="color:#22c55e">&#9679; Clinical</span> &gt;
    <span style="color:#4a9eff">&#9679; Mechanistic</span> &gt;
    <span style="color:#f59e0b">&#9679; Correlative</span>.
  </p>

  {f'<div class="gene-index">{gene_chips}</div>' if gene_chips else ""}

  {gene_sections}

  <hr class="section-divider">

  <!-- Clinical trials -->
  <div class="section-title">Clinical Trials</div>
  <p class="section-sub">
    Recruiting and recently completed trials from <a href="https://clinicaltrials.gov" target="_blank" rel="noopener">ClinicalTrials.gov</a>.
    Data retrieved {NOW_ISO}.
  </p>
  {trials_html}

  <hr class="section-divider">

  <!-- Disease-level agent search (not gene-first) -->
  <div class="section-title">Agents Found By Disease-Level Search</div>
  <p class="section-sub">
    Searched directly from &ldquo;{title}&rdquo; via ClinicalTrials.gov interventions and Open Targets'
    disease&rarr;drug data &mdash; independent of the {len(pipeline_data)}-gene target panel above.
    This surfaces agents whose mechanism doesn't route through a curated gene (combination
    therapies, standard-of-care drugs, targets outside the panel).
  </p>
  {disease_agents_html}

</main>

<footer>
  <p>
    Generated by the <a href="https://opensourcemed.info">Open Source Medicine Foundation</a>
    Biomarker Pipeline &mdash; {NOW_ISO}.
    Data sources: DGIdb, Open Targets, ChEMBL, PubMed, ClinicalTrials.gov.
    Not medical advice.
  </p>
</footer>

</body>
</html>"""


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate per-disease HTML pages")
    parser.add_argument("--skip-trials", action="store_true", help="Skip ClinicalTrials.gov fetch")
    parser.add_argument("--disease", default=None, help="Generate only this disease (exact CSV name)")
    args = parser.parse_args()

    if not CSV_PATH.exists():
        log.error("CSV not found: %s", CSV_PATH)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load CSV
    rows: list[dict] = []
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("disease", "").strip():
                rows.append(row)

    log.info("Loaded %d diseases from CSV", len(rows))

    for row in rows:
        disease = row["disease"].strip()
        if args.disease and disease.lower() != args.disease.lower():
            continue

        log.info("Generating page for: %s", disease)
        slug = _slug(disease)

        pipeline_data = _load_pipeline_results(disease)
        log.info("  Pipeline results: %d genes loaded", len(pipeline_data))

        disease_agents = _load_disease_agents(disease)
        log.info("  Disease-level agents: %d candidates loaded", len(disease_agents))

        if args.skip_trials:
            trials = []
        else:
            log.info("  Fetching clinical trials...")
            trials = _fetch_trials(disease)
            log.info("  Found %d trials", len(trials))
            time.sleep(0.5)  # courteous delay

        html = build_page(disease, row, pipeline_data, trials, disease_agents)
        out_path = OUTPUT_DIR / f"{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        log.info("  Written: %s", out_path)

    # chronic-disease-interventions/index.html is now hand-maintained
    # (category-grouped, shared tracker.css chrome — see research-tracker
    # nav/IA workstream) and no longer generated by this script.
    # _build_index() still exists below for reference but is never called
    # automatically; regenerating it would silently replace that hand-built
    # index with the old flat, uncategorized grid.
    log.info("Done. Pages in: %s", OUTPUT_DIR)


def _build_index(rows: list[dict]) -> None:
    cards = ""
    for row in rows:
        disease = row["disease"].strip()
        slug    = _slug(disease)
        best    = _esc(row.get("best_intervention_remission_rate", "") or "")[:80]
        barrier = _esc(row.get("primary_barrier", "") or "")
        gene_dir = RESULTS_DIR / slug
        n_genes = len(list(gene_dir.glob("*.json"))) if gene_dir.exists() else 0
        n_agents = 0
        if gene_dir.exists():
            for jf in gene_dir.glob("*.json"):
                try:
                    n_agents += len(json.loads(jf.read_text(encoding="utf-8")).get("agents", []))
                except Exception:
                    pass
        status_badge = f'<span style="background:#22c55e;color:#fff;padding:2px 8px;border-radius:4px;font-size:0.75rem">{n_genes} genes · {n_agents} agents</span>' if n_genes else '<span style="color:#8892a4;font-size:0.8rem">Pipeline not yet run</span>'
        cards += f"""
      <a href="{_esc(slug)}.html" class="disease-card">
        <div class="disease-name">{_esc(disease)}</div>
        <div class="disease-meta">{status_badge}</div>
        <div class="disease-best">{best}</div>
        <div class="disease-barrier" style="color:#8892a4;font-size:0.8rem;margin-top:0.4rem">{barrier}</div>
      </a>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Chronic Disease Interventions | OSMF Biomarker Pipeline</title>
  <link rel="icon" href="../favicon.png" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: #0a0e1a; color: #e1e4e8; font-family: 'Inter', sans-serif; }}
    nav {{ background: rgba(10,14,26,0.97); border-bottom: 1px solid #2a3050; padding: 0 1.5rem; height: 60px; display: flex; align-items: center; justify-content: space-between; }}
    .brand {{ font-weight: 700; color: #e1e4e8; font-size: 0.95rem; }}
    .brand span {{ color: #4a9eff; }}
    main {{ max-width: 1100px; margin: 0 auto; padding: 3rem 1.5rem; }}
    h1 {{ font-size: 2rem; margin-bottom: 0.5rem; }}
    .sub {{ color: #8892a4; margin-bottom: 2.5rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; }}
    .disease-card {{ background: #1a1f35; border: 1px solid #2a3050; border-radius: 12px; padding: 1.5rem; text-decoration: none; color: #e1e4e8; display: block; transition: border-color 0.2s; }}
    .disease-card:hover {{ border-color: #4a9eff; text-decoration: none; }}
    .disease-name {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 0.5rem; color: #e1e4e8; }}
    .disease-meta {{ margin-bottom: 0.5rem; }}
    .disease-best {{ font-size: 0.82rem; color: #22c55e; line-height: 1.4; }}
  </style>
</head>
<body>
<nav>
  <span class="brand">Open Source <span>Medicine</span> — Chronic Disease Interventions</span>
  <a href="../index.html" style="color:#8892a4;font-size:0.85rem">← Research Tracker</a>
</nav>
<main>
  <h1>Chronic Disease Interventions</h1>
  <p class="sub">Biomarker targets and therapeutic agents for 8 chronic diseases, generated by the OSMF pipeline. Data: DGIdb · Open Targets · ChEMBL · PubMed · ClinicalTrials.gov</p>
  <div class="grid">{cards}</div>
</main>
</body>
</html>"""
    out = OUTPUT_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    log.info("Index written: %s", out)


if __name__ == "__main__":
    main()
