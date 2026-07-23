#!/usr/bin/env python3
"""
Ticket 5 — Build per-agent hub pages (Template C).

Reads:
  data/therapeutic_agents.json   — 596 agents with mechanism/safety/trials data
  data/vocab/agent-slugs.json    — slug map (built by Ticket 0)
  data/vocab/agent-slugs-flagged.json — dosing artifacts to skip
  data/vocab/disease-slugs.yaml  — disease slug lookup for internal links

Writes:
  agents/<slug>/index.html       — one page per non-flagged agent
  agents/index.html              — hub listing all agents

Usage: python scripts/build_agent_pages.py [--dry-run]
"""
import json, sys, os
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
AGENTS_FILE = ROOT / "data" / "therapeutic_agents.json"
SLUGS_FILE = ROOT / "data" / "vocab" / "agent-slugs.json"
FLAGGED_FILE = ROOT / "data" / "vocab" / "agent-slugs-flagged.json"
DISEASE_SLUGS = ROOT / "data" / "vocab" / "disease-slugs.yaml"
AGENTS_DIR = ROOT / "agents"
INDEX_FILE = AGENTS_DIR / "index.html"

sys.path.insert(0, str(ROOT))
import yaml
from scripts.lib.thin_content_gate import gate as thin_gate

MIN_WORDS_AGENT = 200

CSS = """<style>
:root{--bg:#fff;--fg:#1a1f26;--muted:#6b7480;--line:#e3e7ec;--card:#f7f9fb;--accent:#0b6bcb}
@media(prefers-color-scheme:dark){:root{--bg:#0f1216;--fg:#e6e9ee;--muted:#9aa4b0;--line:#252b33;--card:#161b21;--accent:#5aa2ea}}
body{margin:0;font:16px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--fg)}
.wrap{max-width:960px;margin:0 auto;padding:24px 18px 80px}
a{color:var(--accent)}h1{font-size:1.7rem;margin:.2em 0}h2{font-size:1.2rem;margin:1.5em 0 .5em;border-bottom:1px solid var(--line);padding-bottom:.3em}
.lede{color:var(--muted)}.meta{font-size:.82rem;color:var(--muted);margin:.4em 0}
.back{font-size:.85rem}.section{margin:1rem 0}.tag{display:inline-block;font-size:.72rem;padding:2px 8px;border-radius:4px;border:1px solid var(--line);margin:2px 4px 2px 0}
.evidence{background:var(--card);border:1px solid var(--line);border-radius:6px;padding:8px 12px;margin:6px 0;font-size:.9rem}
.trial{font-size:.85rem;padding:4px 8px;border-left:2px solid var(--accent);margin:4px 0}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1rem;margin:1rem 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1rem;text-decoration:none;color:inherit;display:block}
.card:hover{border-color:var(--accent)}.card h3{margin:0 0 .4rem;color:var(--accent)}
footer{margin-top:40px;border-top:1px solid var(--line);padding-top:14px;font-size:.8rem;color:var(--muted)}
.search-wrap{margin-bottom:1rem}
.search-wrap input{width:100%;padding:.55rem .75rem;border:1px solid var(--line);border-radius:8px;font:inherit;background:var(--bg);color:var(--fg)}
.warn{background:#fef2f2;border:1px solid #fca5a5;border-radius:6px;padding:8px 12px;font-size:.85rem;margin:12px 0}
.noindex-badge{color:var(--muted);font-size:.75rem}
</style>"""


def load_agent_slugs() -> dict:
    with open(SLUGS_FILE, "r", encoding="utf-8") as f:
        slugs = json.load(f)
    return {s["display_name"]: s["slug"] for s in slugs}


def load_flagged_names() -> set:
    if not FLAGGED_FILE.exists():
        return set()
    with open(FLAGGED_FILE, "r", encoding="utf-8") as f:
        return {a["display_name"] for a in json.load(f)}


def load_disease_slug_map() -> dict:
    """Return {disease_name: slug} for Template A pages that exist."""
    with open(DISEASE_SLUGS, "r", encoding="utf-8") as f:
        entries = yaml.safe_load(f)
    # Build two maps: name -> slug (loose match) and slug -> exists
    name_to_slug = {}
    for e in entries:
        if e.get("alias_of"):
            continue
        slug = e["slug"]
        label = e.get("canonical_label", "").lower().strip()
        name_to_slug[slug.replace("-", " ")] = slug
        name_to_slug[label] = slug
        # Also store slug itself
        name_to_slug[slug] = slug
    return name_to_slug


def resolve_disease_link(condition_name: str, disease_map: dict) -> tuple[str, str]:
    """Try to resolve a Primary Condition name to a disease-intelligence slug + URL."""
    key = condition_name.strip().lower()
    slug = disease_map.get(key)
    if not slug:
        # Try hyphenated form
        slug = disease_map.get(key.replace(" ", "-"))
    if not slug:
        return "", ""
    return slug, f"/disease-intelligence/{slug}.html"


def build_agent_page(agent: dict, slug: str, disease_map: dict) -> str:
    name = agent.get("Therapeutic Agent", "Unknown Agent")
    mechanism = agent.get("Proposed Mechanism", "Not available")
    evidence_level = agent.get("Evidence Level", "Not rated")
    safety = agent.get("Safety", "Not available")
    dosing = agent.get("Dosing", "Not available")
    clinical_notes = agent.get("Clinical Notes", "")
    studies = agent.get("Key Studies / References", [])
    trials = agent.get("trials", [])
    conditions = agent.get("Primary Conditions", [])
    pubchem = agent.get("PubChem", "")
    aliases = agent.get("aliases", [])

    # --- Internal links to disease pages ---
    disease_links = []
    for cond in conditions:
        ds_slug, url = resolve_disease_link(cond, disease_map)
        if ds_slug:
            disease_links.append(f'<a href="{url}">{cond}</a>')
        else:
            disease_links.append(f'<span class="meta">{cond} (no page yet)</span>')

    # --- Trials section ---
    trials_html = ""
    if trials:
        trial_items = []
        for t in trials[:10]:
            nct = t.get("nct_id", "")
            title = t.get("title", "")
            status = t.get("status", "")
            phase = t.get("phase", "")
            trial_items.append(
                f'<div class="trial"><strong>{nct}</strong>: {title} '
                f'<span class="tag">{phase}</span> <span class="tag">{status}</span></div>'
            )
        trials_html = f"""
    <h2>Clinical Trials</h2>
    <p class="meta">{len(trials)} trial(s) registered</p>
    {''.join(trial_items)}"""

    # --- Studies section ---
    studies_html = ""
    if studies:
        study_items = [f'<li>{s}</li>' for s in studies[:15]]
        studies_html = f"""
    <h2>Key Studies / References</h2>
    <ul>{''.join(study_items)}</ul>"""

    # --- Aliases ---
    aliases_html = ""
    if aliases:
        aliases_html = f'<p class="meta">Also known as: {", ".join(aliases)}</p>'

    # --- PubChem link ---
    pubchem_html = ""
    if pubchem and "pubchem" in pubchem.lower():
        pubchem_html = f'<p class="meta"><a href="{pubchem}" target="_blank" rel="noopener">PubChem entry</a></p>'

    body = f"""<div class="wrap">
<p class="back"><a href="/agents/">← All agents</a> | <a href="/index.html">← Research tracker</a></p>
<h1>{name}</h1>
{aliases_html}
{pubchem_html}

<div class="section">
<h2>Evidence Summary</h2>
<div class="evidence"><strong>Evidence Level:</strong> {evidence_level}</div>
<div class="evidence"><strong>Mechanism:</strong> {mechanism}</div>
<div class="evidence"><strong>Safety:</strong> {safety}</div>
{('<div class="evidence"><strong>Dosing:</strong> ' + dosing + '</div>') if dosing else ''}
{('<div class="warn">' + clinical_notes + '</div>') if clinical_notes else ''}
</div>

<div class="section">
<h2>Related Conditions</h2>
<p>{' · '.join(disease_links) if disease_links else '<span class="meta">No mapped conditions</span>'}</p>
</div>

{trials_html}
{studies_html}

<footer>
<p>This page was generated from structured therapeutic agent data. Not medical advice. Always consult a qualified healthcare provider. | <a href="/therapeutic-agents.html">Therapeutics Atlas</a></p>
</footer>
</div>"""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name} — Mechanism, Trials & Evidence | OSMF</title>
<meta name="description" content="Evidence review for {name}: mechanism, clinical trials, safety and dosing information from the Open Source Medicine Foundation therapeutic agent database.">
<link rel="canonical" href="https://research.opensourcemed.info/agents/{slug}/">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
{CSS[7:-8]}  /* strip <style> wrapper for inline use */
</style>
</head>
<body>
<nav><div class="nav-container">
<a href="https://opensourcemed.info" class="nav-brand">Open Source <span>Medicine</span><span class="nav-brand-sub">Research Tracker</span></a>
<ul class="nav-links">
<li><a href="/index.html">All Conditions</a></li>
<li><a href="/pais-cohorts.html">PAIS Cohorts</a></li>
<li><a href="/agents/" class="nav-active">Therapeutic Agents</a></li>
<li><a href="/biomarker-atlas.html">Biomarkers</a></li>
<li><a href="/clinical_trials.html">Trials</a></li>
</ul></div></nav>
{body}
<footer class="osmf-network-footer"><div class="osmf-network-inner">
<div class="footer-brand">Open Source Medicine Foundation</div>
<div class="footer-links">
<a href="https://opensourcemed.info">OSMF</a>
<a href="https://research.opensourcemed.info/">Research Platform</a>
</div><div class="footer-note">Not medical advice. CC BY 4.0.</div></div></footer>
</body>
</html>"""


def build_index_page(agents: list[dict], slug_map: dict) -> str:
    """Build agents/index.html — hub listing all agents."""
    cards = []
    for agent in agents:
        name = agent.get("Therapeutic Agent", "")
        slug = slug_map.get(name, "")
        if not slug:
            continue
        conditions = ", ".join(agent.get("Primary Conditions", [])[:3]) or "No mapped conditions"
        evidence = agent.get("Evidence Level", "Not rated")
        trials_count = len(agent.get("trials", []))
        cards.append(f"""<a class="card" href="/agents/{slug}/">
<h3>{name}</h3>
<p class="meta">Conditions: {conditions}</p>
<p class="meta">Evidence: {evidence} | Trials: {trials_count}</p>
</a>""")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Therapeutic Agents — Evidence Database | OSMF</title>
<meta name="description" content="Browse {len(cards)} therapeutic agents with mechanism, safety, dosing, and clinical trial evidence. Repurposed drugs, natural products, and investigational agents from the Open Source Medicine Foundation database.">
<link rel="canonical" href="https://research.opensourcemed.info/agents/">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
{CSS[7:-8]}
.nav-container{{max-width:960px;margin:0 auto;padding:0 1rem;display:flex;align-items:center;justify-content:space-between;height:54px}}
.nav-brand{{font-weight:700;font-size:.9rem;color:var(--fg);text-decoration:none}} .nav-brand span{{color:var(--accent)}}
.nav-links{{list-style:none;display:flex;gap:.4rem}} .nav-links a{{color:var(--muted);font-size:.8rem;padding:.3rem .6rem;border-radius:6px;text-decoration:none}}
.nav-links a:hover,.nav-active{{color:var(--fg);background:var(--card)}}
</style>
</head>
<body>
<nav><div class="nav-container">
<a href="https://opensourcemed.info" class="nav-brand">Open Source <span>Medicine</span><span class="nav-brand-sub">Research Tracker</span></a>
<ul class="nav-links">
<li><a href="/index.html">All Conditions</a></li>
<li><a href="/pais-cohorts.html">PAIS Cohorts</a></li>
<li><a href="/agents/" class="nav-active">Therapeutic Agents</a></li>
<li><a href="/biomarker-atlas.html">Biomarkers</a></li>
<li><a href="/clinical_trials.html">Trials</a></li>
</ul></div></nav>
<div class="wrap">
<p class="back"><a href="/index.html">← Research tracker</a></p>
<h1>Therapeutic Agent Database</h1>
<p class="lede">{len(cards)} agents with mechanism, safety, dosing, and clinical trial evidence. Includes repurposed drugs, natural products, and investigational agents from the OSMF database. Not medical advice.</p>
<div class="search-wrap">
<input id="search" type="search" placeholder="Search by agent name or condition..." oninput="filterCards()">
</div>
<div class="grid" id="grid">{''.join(cards)}</div>
<footer>Generated from structured therapeutic agent data. CC BY 4.0. Not medical advice.</footer>
</div>
<script>
function filterCards() {{
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('.card').forEach(c => {{
    c.style.display = c.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


def main():
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv

    slug_map = load_agent_slugs()
    flagged = load_flagged_names()
    disease_map = load_disease_slug_map()

    agents_data = json.loads(AGENTS_FILE.read_text(encoding="utf-8"))
    all_agents = agents_data.get("agents", [])

    # Filter: skip flagged (dosing artifacts) and agents without slugs
    valid = [a for a in all_agents if a.get("Therapeutic Agent") not in flagged and a.get("Therapeutic Agent") in slug_map]

    print(f"Total agents: {len(all_agents)}, Flagged: {len(flagged)}, Valid: {len(valid)}")

    AGENTS_DIR.mkdir(parents=True, exist_ok=True)

    generated = 0
    noindexed = 0
    for agent in valid:
        name = agent.get("Therapeutic Agent", "")
        slug = slug_map[name]

        page_html = build_agent_page(agent, slug, disease_map)

        # Run thin-content gate
        result = thin_gate(page_html, min_words=MIN_WORDS_AGENT, corpus_dir=None)
        if not result.indexable:
            robots_meta = '<meta name="robots" content="noindex,follow">'
            page_html = page_html.replace("<head>\n", f"<head>\n  {robots_meta}\n")
            noindexed += 1

        page_dir = AGENTS_DIR / slug
        if dry_run:
            print(f"  [dry-run] {slug}: words={result.word_count} indexable={result.indexable}")
        else:
            page_dir.mkdir(parents=True, exist_ok=True)
            (page_dir / "index.html").write_text(page_html, encoding="utf-8")

        generated += 1

    # Build index
    index_html = build_index_page(valid, slug_map)
    if dry_run:
        print(f"  [dry-run] would write agents/index.html ({len(valid)} agents)")
    else:
        INDEX_FILE.write_text(index_html, encoding="utf-8")

    print(f"\nGenerated: {generated} agent pages, {noindexed} noindexed, 1 index page")
    print("Done.")


if __name__ == "__main__":
    main()