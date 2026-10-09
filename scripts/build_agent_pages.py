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
Then:  python scripts/apply_osmf_ui.py --only agents/...   (shared header/footer)
"""
import json, re, sys, os
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


CSS = """<style>
/* Agent hub pages (Template C). Built on css/osmf-ui.css, which every page
   loads last via scripts/apply_osmf_ui.py; the fallbacks keep the page
   readable if that stylesheet is missing. */
:root{--ag-wrap:1200px;--ag-gutter:clamp(16px,3.2vw,32px)}
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 var(--ui-font,'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif);background:#fff;color:var(--ui-text,#3d4466)}
.ag-wrap{max-width:var(--ag-wrap);margin:0 auto;padding:0 var(--ag-gutter)}
.ag-crumbs{padding:14px 0;border-bottom:1px solid var(--ui-line,#e6e8f2);background:#fff}
.ag-crumbs .ag-wrap{display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px}
.ag-crumbs span[aria-hidden]{color:var(--ui-faint,#9aa0bd)}
.ag-crumbs [aria-current]{color:var(--ui-ink-2,#2a3160);font-weight:500}
.ag-hero{padding:56px 0 52px}
.ag-hero h1{font-size:clamp(32px,4.8vw,54px);margin:18px 0 10px;max-width:22ch;overflow-wrap:anywhere}
.ag-hero .ag-aka{margin:0 0 4px;font-size:15px}
.ag-hero .ag-lede{margin:0;font-size:clamp(15.5px,1.6vw,18px);line-height:1.65;max-width:62ch}
.ag-stats{display:flex;flex-wrap:wrap;gap:18px 48px;margin-top:30px;padding-top:24px;border-top:1px solid rgba(255,255,255,.12)}
.ag-stat{display:grid;gap:6px}
.ag-stat b{font-family:var(--ui-display,Georgia,serif);font-weight:500;font-size:clamp(26px,3vw,36px);letter-spacing:-.02em;line-height:1;color:#fff}
.ag-stat span{font-size:11.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:rgba(214,219,245,.75)}
.ag-hero-links{display:flex;flex-wrap:wrap;gap:10px;margin-top:28px}
.ag-hero .ag-btn{display:inline-flex;align-items:center;gap:8px;padding:9px 16px;border-radius:999px;border:1px solid rgba(255,255,255,.24);color:#fff;font-size:14px;font-weight:600;text-decoration:none}
.ag-hero .ag-btn:hover{background:rgba(255,255,255,.08)}
.ag-main{padding:48px 0 8px}
.ag-layout{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:40px;align-items:start}
@media(max-width:960px){.ag-layout{grid-template-columns:minmax(0,1fr)}}
.ag-section{margin:0 0 48px}
.ag-section:last-child{margin-bottom:0}
.ag-section h2{font-size:22px;font-weight:700;letter-spacing:-.015em;color:var(--ui-ink,#0e1444);margin:0 0 6px}
.ag-section .ag-sub{margin:0 0 18px;font-size:14px;color:var(--ui-muted,#6b7194)}
.ag-facts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:18px 0 0}
@media(max-width:640px){.ag-facts{grid-template-columns:minmax(0,1fr)}}
.ag-fact{background:#fff;border:1px solid var(--ui-line,#e6e8f2);border-radius:var(--ui-radius,14px);box-shadow:var(--ui-shadow-1);padding:18px 20px;margin:0}
.ag-fact--wide{grid-column:1/-1}
.ag-fact dt{font-size:11.5px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--ui-muted,#6b7194);margin:0 0 8px}
.ag-fact dd{margin:0;font-size:15px;line-height:1.65;color:var(--ui-ink-2,#2a3160);overflow-wrap:anywhere}
.ag-level{display:inline-flex;align-items:center;gap:8px;font-weight:650}
.ag-level::before{content:"";width:8px;height:8px;border-radius:50%;background:currentColor}
.ag-level--moderate{color:var(--ui-ok,#047857)}
.ag-level--preliminary{color:var(--ui-warn,#a16207)}
.ag-level--anecdotal{color:var(--ui-up,#c2410c)}
.ag-note{margin-top:14px}
.ag-table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--ui-line,#e6e8f2);border-radius:var(--ui-radius,14px);box-shadow:var(--ui-shadow-1);background:#fff}
.ag-table{width:100%;min-width:560px;border-collapse:collapse;font-size:14px}
.ag-table th{text-align:left;font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;color:var(--ui-muted,#6b7194);background:var(--ui-bg-soft,#f7f8fc);padding:11px 14px;border-bottom:1px solid var(--ui-line,#e6e8f2);white-space:nowrap}
.ag-table td{padding:13px 14px;border-bottom:1px solid var(--ui-line,#e6e8f2);vertical-align:top;color:var(--ui-ink-2,#2a3160);line-height:1.5}
.ag-table tr:last-child td{border-bottom:0}
.ag-table td:first-child{white-space:nowrap;font-weight:600}
.ag-table td:first-child a{font-family:var(--ui-mono,ui-monospace,monospace);font-size:13px}
.ag-table td.ag-nowrap{white-space:nowrap}
.ag-refs{list-style:none;margin:0;padding:0;background:#fff;border:1px solid var(--ui-line,#e6e8f2);border-radius:var(--ui-radius,14px);box-shadow:var(--ui-shadow-1)}
.ag-refs li{padding:12px 18px;border-top:1px solid var(--ui-line,#e6e8f2);font-size:14.5px;color:var(--ui-ink-2,#2a3160)}
.ag-refs li:first-child{border-top:0}
.ag-refs a{font-family:var(--ui-mono,ui-monospace,monospace);font-size:13.5px}
.ag-aside{display:grid;gap:18px;position:sticky;top:calc(var(--ui-header-h,68px) + 20px)}
@media(max-width:960px){.ag-aside{position:static}}
.ag-aside .osmf-card h2{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--ui-muted,#6b7194);margin:0 0 12px}
.ag-aside .osmf-card p{margin:0 0 10px;font-size:14px;line-height:1.6}
.ag-aside .osmf-card p:last-child{margin-bottom:0}
.ag-conds{display:flex;flex-wrap:wrap;gap:8px}
.ag-conds a.osmf-pill{text-decoration:none;color:var(--ui-link,#2f45c4);background:#fff;border-color:var(--ui-line-2,#d5d9ea)}
.ag-conds a.osmf-pill:hover{border-color:var(--ui-link,#2f45c4)}
.ag-conds .osmf-pill{display:inline-block;white-space:normal;line-height:1.45;padding:5px 11px;border-radius:10px}
.ag-muted{color:var(--ui-muted,#6b7194);font-size:13px}
.ag-note-foot{margin:0}
/* index */
.ag-tools{position:sticky;top:var(--ui-header-h,68px);z-index:20;background:rgba(255,255,255,.94);-webkit-backdrop-filter:saturate(180%) blur(12px);backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--ui-line,#e6e8f2);padding:14px 0}
.ag-tools .ag-wrap{display:flex;align-items:center;gap:14px}
.ag-tools .ag-search{flex:1;max-width:520px;width:100%;font:inherit;font-size:15px;color:var(--ui-ink,#0e1444);border:1px solid var(--ui-line-2,#d5d9ea);border-radius:12px;padding:11px 14px 11px 40px;min-height:46px;background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7194' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='M20 20l-3.5-3.5'/%3E%3C/svg%3E") no-repeat 14px center}
.ag-tools .ag-search:focus{outline:none;border-color:#8090ea;box-shadow:0 0 0 4px rgba(47,69,196,.12)}
.ag-count{margin-left:auto;font-size:13px;font-weight:600;color:var(--ui-muted,#6b7194);white-space:nowrap}
@media(max-width:640px){.ag-tools{position:static}.ag-count{display:none}}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;padding:36px 0 8px}
.card{display:flex;flex-direction:column;gap:8px;background:#fff;border:1px solid var(--ui-line,#e6e8f2);border-radius:var(--ui-radius,14px);box-shadow:var(--ui-shadow-1);padding:18px 20px;text-decoration:none;color:inherit;transition:transform .2s,box-shadow .2s,border-color .2s;min-width:0}
.card:hover{transform:translateY(-2px);box-shadow:var(--ui-shadow-2);border-color:var(--ui-line-2,#d5d9ea)}
.card h3{margin:0;font-size:16px;font-weight:650;line-height:1.35;letter-spacing:-.01em;color:var(--ui-ink,#0e1444);overflow-wrap:anywhere}
.card .meta{margin:0;font-size:13px;line-height:1.5;color:var(--ui-muted,#6b7194)}
.card .ag-card-pills{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto;padding-top:4px}
.ag-foot{margin:40px 0 0;padding-top:20px;border-top:1px solid var(--ui-line,#e6e8f2);font-size:13px;color:var(--ui-muted,#6b7194);text-align:center}
</style>"""

STATUS_LABEL = {
    "RECRUITING": ("Recruiting", "ok"), "ENROLLING_BY_INVITATION": ("Enrolling by invitation", "ok"),
    "ACTIVE_NOT_RECRUITING": ("Active, not recruiting", "down"), "NOT_YET_RECRUITING": ("Not yet recruiting", "down"),
    "COMPLETED": ("Completed", ""), "UNKNOWN": ("Unknown status", "warn"),
    "TERMINATED": ("Terminated", "up"), "WITHDRAWN": ("Withdrawn", "up"), "SUSPENDED": ("Suspended", "up"),
}
PHASE_LABEL = {"PHASE4": "Phase 4", "PHASE3": "Phase 3", "PHASE2": "Phase 2", "PHASE1": "Phase 1",
               "EARLY_PHASE1": "Early phase 1", "NA": "Not applicable"}


def pill(text: str, kind: str = "") -> str:
    mod = f" osmf-pill--{kind}" if kind else ""
    return f'<span class="osmf-pill{mod}">{text}</span>'


def level_html(level: str) -> str:
    key = (level or "").strip().lower().split(" ")[0]
    return f'<span class="ag-level ag-level--{key}">{level}</span>'


def ref_html(ref: str) -> str:
    """Link bare PMID references to PubMed; leave anything else as text."""
    r = (ref or "").strip()
    if r.upper().startswith("PMID:") and r[5:].strip().isdigit():
        return f'<a href="https://pubmed.ncbi.nlm.nih.gov/{r[5:].strip()}/" target="_blank" rel="noopener">{r}</a>'
    return r


HEAD_DROP = [
    re.compile(r"<style\b[^>]*>.*?</style>", re.S | re.I),
    re.compile(r"<!-- OSMF_UI_HEAD_START -->.*?<!-- OSMF_UI_HEAD_END -->", re.S),
    re.compile(r'<link href="https://fonts\.googleapis\.com/css2\?family=Inter[^"]*" rel="stylesheet">', re.I),
]


def carried_head(page_path: Path) -> str:
    """SEO metadata already on the published page (canonical, Open Graph,
    Twitter, JSON-LD, robots, title, description), written after generation
    by scripts/fix_site_audit_issues.py. Regenerating must not drop it, so we
    lift the existing <head> verbatim minus styles and the shared-UI block
    (apply_osmf_ui.py re-adds that). Returns "" for a page that does not exist."""
    if not page_path.exists():
        return ""
    src = page_path.read_text(encoding="utf-8")
    m = re.search(r"<head>(.*?)</head>", src, re.S | re.I)
    if not m:
        return ""
    head = m.group(1)
    for rx in HEAD_DROP:
        head = rx.sub("", head)
    # a stray ">" after the robots tag closed <head> early in browsers
    head = head.replace('max-image-preview:large">>', 'max-image-preview:large">')
    head = re.sub(r"\n{3,}", "\n\n", head).strip("\n")
    return head


def page_head(fresh_meta: str, carried: str) -> str:
    meta = carried if carried else fresh_meta
    return f"""<head>
{meta}
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
{CSS}
</head>"""


def build_agent_page(agent: dict, slug: str, disease_map: dict, carried: str = "") -> str:
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
            disease_links.append(f'<a class="osmf-pill" href="{url}">{cond}</a>')
        else:
            disease_links.append(f'<span class="osmf-pill">{cond} <span class="ag-muted">(no page yet)</span></span>')

    # --- Trials section ---
    trials_html = ""
    if trials:
        rows = []
        for t in trials[:10]:
            nct = t.get("nct_id", "")
            title = t.get("title", "")
            status = t.get("status", "")
            phase = t.get("phase", "")
            s_label, s_kind = STATUS_LABEL.get(status, (status.replace("_", " ").capitalize(), ""))
            nct_html = f'<a href="https://clinicaltrials.gov/study/{nct}" target="_blank" rel="noopener">{nct}</a>' if nct.startswith("NCT") else nct
            rows.append(
                f'<tr><td>{nct_html}</td><td>{title}</td>'
                f'<td class="ag-nowrap">{pill(PHASE_LABEL.get(phase, phase)) if phase else ""}</td>'
                f'<td class="ag-nowrap">{pill(s_label, s_kind) if status else ""}</td></tr>')
        trials_html = f"""
<section class="ag-section" id="trials">
<h2>Clinical Trials</h2>
<p class="ag-sub">{len(trials)} trial(s) registered</p>
<div class="ag-table-wrap"><table class="ag-table">
<thead><tr><th scope="col">NCT ID</th><th scope="col">Title</th><th scope="col">Phase</th><th scope="col">Status</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
</section>"""

    # --- Studies section ---
    studies_html = ""
    if studies:
        study_items = [f'<li>{ref_html(s)}</li>' for s in studies[:15]]
        studies_html = f"""
<section class="ag-section" id="references">
<h2>Key Studies / References</h2>
<ul class="ag-refs">{''.join(study_items)}</ul>
</section>"""

    # --- Aliases ---
    aliases_html = ""
    if aliases:
        aliases_html = f'<p class="ag-aka">Also known as: {", ".join(aliases)}</p>'

    # --- PubChem link ---
    pubchem_html = ""
    if pubchem and "pubchem" in pubchem.lower():
        pubchem_html = f'<div class="ag-hero-links"><a class="ag-btn" href="{pubchem}" target="_blank" rel="noopener">PubChem entry ↗</a></div>'

    n_refs = len([s for s in studies if s and s != "See linked studies"])
    body = f"""<nav class="osmf-crumbs ag-crumbs" aria-label="Breadcrumb"><div class="ag-wrap">
<a href="/index.html">Research tracker</a><span aria-hidden="true">›</span><a href="/agents/">All agents</a><span aria-hidden="true">›</span><span aria-current="page">{name}</span>
</div></nav>
<header class="hero ag-hero"><div class="ag-wrap">
<span class="osmf-eyebrow">Therapeutic agent</span>
<h1>{name}</h1>
{aliases_html}
<div class="ag-stats">
<div class="ag-stat"><b>{evidence_level}</b><span>Evidence level</span></div>
<div class="ag-stat"><b>{len(trials)}</b><span>Registered trials</span></div>
<div class="ag-stat"><b>{len(conditions)}</b><span>Conditions</span></div>
<div class="ag-stat"><b>{n_refs}</b><span>Study references</span></div>
</div>
{pubchem_html}
</div></header>

<main class="ag-main"><div class="ag-wrap ag-layout">
<div class="ag-content">
<section class="ag-section" id="evidence">
<h2>Evidence Summary</h2>
<dl class="ag-facts">
<div class="ag-fact"><dt>Evidence Level</dt><dd>{level_html(evidence_level)}</dd></div>
<div class="ag-fact"><dt>Mechanism</dt><dd>{mechanism}</dd></div>
<div class="ag-fact ag-fact--wide"><dt>Safety</dt><dd>{safety}</dd></div>
{('<div class="ag-fact ag-fact--wide"><dt>Dosing</dt><dd>' + dosing + '</dd></div>') if dosing else ''}
</dl>
{('<div class="osmf-callout ag-note">' + clinical_notes + '</div>') if clinical_notes else ''}
</section>
{trials_html}
{studies_html}
</div>

<aside class="ag-aside">
<div class="osmf-card">
<h2>Related Conditions</h2>
<div class="ag-conds">{''.join(disease_links) if disease_links else '<span class="ag-muted">No mapped conditions</span>'}</div>
</div>
<div class="osmf-card">
<h2>About this page</h2>
<p class="ag-note-foot">This page was generated from structured therapeutic agent data. Not medical advice. Always consult a qualified healthcare provider.</p>
<p><a href="/therapeutic-agents.html">Therapeutics Atlas</a> · <a href="/agents/">All agents</a></p>
</div>
</aside>
</div></main>"""

    fresh_meta = f"""<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name} — Mechanism, Trials & Evidence | OSMF</title>
<meta name="description" content="Evidence review for {name}: mechanism, clinical trials, safety and dosing information from the Open Source Medicine Foundation therapeutic agent database.">
<link rel="canonical" href="https://research.opensourcemed.info/agents/{slug}/">"""
    return f"""<!DOCTYPE html>
<html lang="en">
{page_head(fresh_meta, carried)}
<body>
{body}
</body>
</html>"""


def build_index_page(agents: list[dict], slug_map: dict, carried: str = "") -> str:
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
        kind = {"moderate": "ok", "preliminary": "warn", "anecdotal": "up"}.get(evidence.lower(), "")
        cards.append(f"""<a class="card" href="/agents/{slug}/">
<h3>{name}</h3>
<p class="meta">Conditions: {conditions}</p>
<div class="ag-card-pills">{pill("Evidence: " + evidence, kind)}{pill("Trials: " + str(trials_count))}</div>
</a>""")

    fresh_meta = f"""<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Therapeutic Agents — Evidence Database | OSMF</title>
<meta name="description" content="Browse {len(cards)} therapeutic agents with mechanism, safety, dosing, and clinical trial evidence. Repurposed drugs, natural products, and investigational agents from the Open Source Medicine Foundation database.">
<link rel="canonical" href="https://research.opensourcemed.info/agents/">"""
    n_trials = sum(len(a.get("trials", [])) for a in agents if slug_map.get(a.get("Therapeutic Agent", "")))
    n_moderate = sum(1 for a in agents if slug_map.get(a.get("Therapeutic Agent", "")) and a.get("Evidence Level") == "Moderate")
    return f"""<!DOCTYPE html>
<html lang="en">
{page_head(fresh_meta, carried)}
<body>
<nav class="osmf-crumbs ag-crumbs" aria-label="Breadcrumb"><div class="ag-wrap">
<a href="/index.html">Research tracker</a><span aria-hidden="true">›</span><span aria-current="page">Therapeutic agents</span>
</div></nav>
<header class="hero ag-hero"><div class="ag-wrap">
<span class="osmf-eyebrow">Evidence database</span>
<h1>Therapeutic Agent Database</h1>
<p class="lede ag-lede">{len(cards)} agents with mechanism, safety, dosing, and clinical trial evidence. Includes repurposed drugs, natural products, and investigational agents from the OSMF database. Not medical advice.</p>
<div class="ag-stats">
<div class="ag-stat"><b>{len(cards)}</b><span>Agents</span></div>
<div class="ag-stat"><b>{n_trials}</b><span>Linked trials</span></div>
<div class="ag-stat"><b>{n_moderate}</b><span>Moderate evidence</span></div>
</div>
</div></header>
<div class="ag-tools"><div class="ag-wrap">
<input id="search" class="ag-search" type="search" placeholder="Search by agent name or condition..." aria-label="Search agents" oninput="filterCards()">
<span class="ag-count" id="ag-count" aria-live="polite">{len(cards)} agents</span>
</div></div>
<main class="ag-wrap">
<div class="grid" id="grid">{''.join(cards)}</div>
<p class="ag-foot">Generated from structured therapeutic agent data. CC BY 4.0. Not medical advice.</p>
</main>
<script>
function filterCards() {{
  const q = document.getElementById('search').value.toLowerCase();
  let n = 0;
  document.querySelectorAll('.card').forEach(c => {{
    const show = c.textContent.toLowerCase().includes(q);
    c.style.display = show ? '' : 'none';
    if (show) n++;
  }});
  const el = document.getElementById('ag-count');
  if (el) el.textContent = n + (n === 1 ? ' agent' : ' agents');
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

        page_dir = AGENTS_DIR / slug
        carried = carried_head(page_dir / "index.html")
        page_html = build_agent_page(agent, slug, disease_map, carried)

        # Run thin-content gate (new pages only: a published page keeps the
        # robots directive already in its carried-over head)
        result = thin_gate(page_html, min_words=MIN_WORDS_AGENT, corpus_dir=None)
        if not result.indexable and not carried:
            robots_meta = '<meta name="robots" content="noindex,follow">'
            page_html = page_html.replace("<head>\n", f"<head>\n  {robots_meta}\n")
            noindexed += 1

        if dry_run:
            print(f"  [dry-run] {slug}: words={result.word_count} indexable={result.indexable}")
        else:
            page_dir.mkdir(parents=True, exist_ok=True)
            (page_dir / "index.html").write_text(page_html, encoding="utf-8")

        generated += 1

    # Build index
    index_html = build_index_page(valid, slug_map, carried_head(INDEX_FILE))
    if dry_run:
        print(f"  [dry-run] would write agents/index.html ({len(valid)} agents)")
    else:
        INDEX_FILE.write_text(index_html, encoding="utf-8")

    print(f"\nGenerated: {generated} agent pages, {noindexed} noindexed, 1 index page")
    print("Done.")


if __name__ == "__main__":
    main()