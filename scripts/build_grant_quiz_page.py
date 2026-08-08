#!/usr/bin/env python3
"""Build grant-eligibility-quiz.html for research.opensourcemed.info.

Takes the Expanding Edge quiz (scripts/grant-eligibility-quiz.html), keeps
GRANTS + matching logic, and wraps it in OSMF research-tracker chrome/style.
Also writes data/grants.json for reuse.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "grant-eligibility-quiz.html"
OUT = ROOT / "grant-eligibility-quiz.html"
DATA_OUT = ROOT / "data" / "grants.json"


def extract_grants_js(src: str) -> str:
    m = re.search(r"const GRANTS = (\[.*?\]);\s*\n\s*const state", src, re.S)
    if not m:
        raise SystemExit("Could not find GRANTS array")
    return m.group(1)


def grants_js_to_json(grants_js: str) -> list:
    """Best-effort convert JS object array to JSON (null, unquoted keys)."""
    s = grants_js
    # Remove HTML entities that are fine in JS strings but keep as-is in JSON text later
    # Quote keys
    s = re.sub(r"(\n\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', s)
    s = s.replace("null", "null")
    # Trailing commas
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        print(f"Warning: could not parse grants as JSON ({e}); writing JS-only")
        return []


def build_page(src: str, grants_js: str) -> str:
    # Script from const state through end of renderResults (exclusive of closing script tag)
    sm = re.search(r"(const state = \{.*?)(</script>\s*</body>)", src, re.S)
    if not sm:
        raise SystemExit("Could not find quiz logic script")
    logic = sm.group(1).rstrip()

    # Soften Expanding Edge-specific CTA to OSMF framing while keeping utility
    logic = logic.replace(
        "Turn this into a quote",
        "Next steps",
    )
    logic = logic.replace(
        "Most of these cost-share programs pay against invoiced work &mdash; the design, earthworks, and planting Expanding Edge already delivers are eligible costs under nearly all of them. Pair this result with a site visit to fold the matching programs into the proposal.",
        "Most of these cost-share programs pay against invoiced, eligible project work (design, earthworks, planting, infrastructure). Confirm current intake windows with the delivery agency, then fold matching programs into a project plan or contractor quote.",
    )

    # Enhance results cards to always show eligibility chips (province/types)
    # Inject after card-desc in renderResults if not already enhanced
    if "card-elig" not in logic:
        logic = logic.replace(
            "html += '<p class=\"card-desc\">'+g.desc+'</p>';",
            "html += '<p class=\"card-desc\">'+g.desc+'</p>';\n"
            "      html += '<div class=\"card-elig\">'\n"
            "        + '<span class=\"elig-chip\"><strong>Who:</strong> ' + eligTypes(g.types) + '</span>'\n"
            "        + '<span class=\"elig-chip\"><strong>Where:</strong> ' + g.provinces.join(', ') + '</span>'\n"
            "        + '<span class=\"elig-chip\"><strong>Min production:</strong> ' + incomeLabel(g.minIncome) + '</span>'\n"
            "        + (g.wetland === 'yes' ? '<span class=\"elig-chip\"><strong>Site:</strong> Wetland / watercourse nearby</span>' : '')\n"
            "        + '</div>';",
        )
        # Add helpers before matches()
        logic = logic.replace(
            "const INCOME_RANK = {under25:0, \"25to50\":1, over50:2};",
            "const INCOME_RANK = {under25:0, \"25to50\":1, over50:2};\n"
            "const TYPE_LABELS = {producer:'Registered producer',acreage:'Acreage / rural residential',"
            "processor:'Processor',greenhouse:'Greenhouse / CE',org:'Municipality / First Nation / NGO',unsure:'Any / unsure'};\n"
            "function eligTypes(types){ return (types||[]).map(t=>TYPE_LABELS[t]||t).join(' · '); }\n"
            "function incomeLabel(v){\n"
            "  if(v==='under25') return 'None / any';\n"
            "  if(v==='25to50') return '≥ $25,000/yr farm commodities';\n"
            "  if(v==='over50') return '≥ $50,000/yr';\n"
            "  return v;\n"
            "}\n",
        )

    # Also enhance renderResults to show browse-all when zero or add directory section after results
    if "showAllGrants" not in logic:
        logic += """

function showAllGrants(){
  const wrap = document.getElementById('results');
  let html = '<div class="results-head"><p class="eyebrow">Full directory</p>';
  html += '<h2>All '+GRANTS.length+' programs in the database</h2>';
  html += '<p>Summaries, eligibility rules, cost-share rates, and official links. Status fields drift — verify before applying.</p></div>';
  html += '<div class="stack">';
  GRANTS.forEach(g=>{
    const stampClass = g.status==='open' ? '' : g.status==='maybe' ? 'maybe' : 'closed';
    const stampText = g.status==='open' ? 'Open' : g.status==='maybe' ? 'Check intake' : 'Closed';
    html += '<div class="card" id="grant-'+slugify(g.name)+'">';
    html += '<div class="card-top"><div><p class="card-jur">'+g.jur+'</p><p class="card-name">'+g.name+'</p></div><span class="stamp '+stampClass+'">'+stampText+'</span></div>';
    html += '<p class="card-desc">'+g.desc+'</p>';
    html += '<div class="card-elig">'
      + '<span class="elig-chip"><strong>Who:</strong> ' + eligTypes(g.types) + '</span>'
      + '<span class="elig-chip"><strong>Where:</strong> ' + g.provinces.join(', ') + '</span>'
      + '<span class="elig-chip"><strong>Min production:</strong> ' + incomeLabel(g.minIncome) + '</span>'
      + (g.wetland === 'yes' ? '<span class="elig-chip"><strong>Site:</strong> Wetland / watercourse nearby</span>' : '')
      + '</div>';
    html += '<div class="card-figs"><div class="fig">Cost-share<b>'+g.costShare+'</b></div><div class="fig">Cap<b>'+g.cap+'</b></div></div>';
    html += '<p class="card-note">'+g.note+'</p>';
    if(g.link){
      html += '<p style="margin-top:10px;position:relative;"><a class="card-link" href="'+g.link+'" target="_blank" rel="noopener">Official program page &#8599;</a></p>';
    }
    html += '</div>';
  });
  html += '</div>';
  html += '<div class="navrow" style="margin-top:22px;"><button class="btn ghost" onclick="location.reload()">Back to quiz</button><span></span></div>';
  html += '<p class="fine">Informational only. Not affiliated with listed agencies. Confirm current terms before applying.</p>';
  wrap.innerHTML = html;
  goTo(5);
}

function slugify(s){
  return String(s||'').toLowerCase().replace(/&mdash;|—/g,'-').replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
}

// Wire "browse all" from intro + deep link #browse / #directory
document.addEventListener('DOMContentLoaded', ()=>{
  const b = document.getElementById('browse-all');
  if(b) b.addEventListener('click', (e)=>{ e.preventDefault(); showAllGrants(); });
  const h = (location.hash || '').toLowerCase();
  if(h === '#browse' || h === '#directory' || h === '#all') showAllGrants();
});
"""

    # Insert "Browse all" on results fine print area by patching renderResults end
    logic = logic.replace(
        "html += '<div class=\"navrow\" style=\"margin-top:22px;\"><button class=\"btn ghost\" onclick=\"location.reload()\">Start over</button><span></span></div>';",
        "html += '<div class=\"navrow\" style=\"margin-top:22px;\">"
        "<button class=\"btn ghost\" onclick=\"location.reload()\">Start over</button>"
        "<button class=\"btn ghost\" onclick=\"showAllGrants()\">Browse all programs</button>"
        "</div>';",
    )

    # Use placeholders so GRANTS/JS curly braces never break formatting
    page = """<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-EP8RK1RZ29"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-EP8RK1RZ29');
  </script>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Grant &amp; Cost-Share Eligibility Quiz — AB / BC / SK &amp; Federal | Open Source Medicine</title>
  <meta name="description" content="Interactive eligibility quiz for 29 agricultural, land stewardship, and clean-tech cost-share programs in Alberta, British Columbia, Saskatchewan, and federal Canada. Summaries, eligibility rules, and official links.">
  <meta name="keywords" content="farm grants Canada, Environmental Farm Plan, SCAP, RALP, cost-share agriculture Alberta, BC BMP, Saskatchewan FRWIP, Agricultural Clean Technology">
  <meta name="robots" content="index, follow, max-image-preview:large">
  <link rel="canonical" href="https://research.opensourcemed.info/grant-eligibility-quiz.html">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Open Source Medicine Foundation">
  <meta property="og:title" content="Grant &amp; Cost-Share Eligibility Quiz">
  <meta property="og:description" content="Match land, farm, and clean-tech projects to AB/BC/SK and federal cost-share programs. Eligibility, summaries, and official links.">
  <meta property="og:url" content="https://research.opensourcemed.info/grant-eligibility-quiz.html">
  <meta property="og:image" content="https://opensourcemed.info/favicon.png">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Grant &amp; Cost-Share Eligibility Quiz">
  <meta name="twitter:description" content="29 programs across Alberta, BC, Saskatchewan, and federal Canada.">
  <link rel="icon" href="https://opensourcemed.info/favicon.png" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="tracker.css">
  <script src="js/site-universal.js" defer></script>
  <style>
    /* Scoped quiz — OSMF research-tracker palette, field-guide layout */
    .gq {
      --gq-bg: #0a0e1a;
      --gq-surface: #141828;
      --gq-card: #1a1f35;
      --gq-border: #2a3050;
      --gq-text: #e1e4e8;
      --gq-muted: #8892a4;
      --gq-accent: #4a9eff;
      --gq-green: #22c55e;
      --gq-amber: #f59e0b;
      --gq-red: #ef4444;
      --gq-teal: #2dd4bf;
      max-width: 760px;
      margin: 0 auto;
      padding: 0 1.25rem 4rem;
      color: var(--gq-text);
      font-family: Inter, system-ui, sans-serif;
    }
    .gq .disc {
      background: rgba(245,158,11,.08);
      border: 1px solid rgba(245,158,11,.35);
      border-radius: 10px;
      padding: .85rem 1rem;
      font-size: .875rem;
      color: var(--gq-muted);
      margin: 1.25rem 0 1.5rem;
      line-height: 1.55;
    }
    .gq .disc strong { color: var(--gq-amber); }
    .gq-hero {
      padding: 1.5rem 0 1rem;
      border-bottom: 1px solid var(--gq-border);
      margin-bottom: 1.5rem;
    }
    .gq-hero .eyebrow {
      font-family: 'IBM Plex Mono', monospace;
      font-size: .72rem;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: var(--gq-accent);
      margin: 0 0 .5rem;
    }
    .gq-hero h1 {
      font-size: clamp(1.55rem, 3.5vw, 2.1rem);
      font-weight: 700;
      margin: 0 0 .65rem;
      letter-spacing: -.02em;
      line-height: 1.15;
    }
    .gq-hero p { color: var(--gq-muted); font-size: .95rem; line-height: 1.6; max-width: 36rem; margin: 0 0 1rem; }
    .gq-hero .meta {
      font-family: 'IBM Plex Mono', monospace;
      font-size: .72rem;
      color: var(--gq-muted);
      letter-spacing: .04em;
    }
    .gq-tools { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1rem; }
    .gq-tools a, .gq-tools button {
      display: inline-block;
      padding: .4rem .85rem;
      border-radius: 8px;
      border: 1px solid var(--gq-border);
      background: var(--gq-surface);
      color: var(--gq-accent);
      font-size: .82rem;
      font-weight: 600;
      text-decoration: none;
      cursor: pointer;
      font-family: inherit;
    }
    .gq-tools a:hover, .gq-tools button:hover { border-color: var(--gq-accent); }

    .gq .progress { display: flex; gap: 4px; margin-bottom: 1.5rem; }
    .gq .progress span { height: 3px; flex: 1; background: var(--gq-border); border-radius: 2px; }
    .gq .progress span.done { background: var(--gq-accent); }

    .gq .step { display: none; }
    .gq .step.active { display: block; animation: gqfade .22s ease; }
    @keyframes gqfade { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: none; } }

    .gq .q-index {
      font-family: 'IBM Plex Mono', monospace;
      font-size: .75rem;
      color: var(--gq-teal);
      margin-bottom: .5rem;
      letter-spacing: .06em;
    }
    .gq .q-text {
      font-size: 1.25rem;
      font-weight: 600;
      line-height: 1.35;
      margin: 0 0 1.15rem;
      max-width: 32rem;
    }
    .gq .opts { display: flex; flex-direction: column; gap: .5rem; margin-bottom: 1.5rem; }
    .gq .opt {
      border: 1.5px solid var(--gq-border);
      background: var(--gq-surface);
      text-align: left;
      padding: .8rem 1rem;
      border-radius: 10px;
      font-size: .95rem;
      color: var(--gq-text);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: .75rem;
      transition: border-color .12s, background .12s;
      font-family: inherit;
      width: 100%;
    }
    .gq .opt:hover { border-color: var(--gq-accent); background: rgba(74,158,255,.06); }
    .gq .opt.sel { border-color: var(--gq-accent); background: rgba(74,158,255,.12); }
    .gq .opt .mark {
      width: 16px; height: 16px;
      border: 1.5px solid var(--gq-border);
      flex: 0 0 auto;
      border-radius: 3px;
      position: relative;
    }
    .gq .opt.single .mark { border-radius: 50%; }
    .gq .opt.sel .mark { border-color: var(--gq-accent); background: var(--gq-accent); }
    .gq .opt.sel .mark::after {
      content: '';
      position: absolute; left: 4px; top: 1px; width: 4px; height: 8px;
      border: solid var(--gq-bg); border-width: 0 2px 2px 0; transform: rotate(45deg);
    }
    .gq .opt.single.sel .mark::after {
      left: 50%; top: 50%; width: 6px; height: 6px; border: none;
      background: var(--gq-bg); border-radius: 50%; transform: translate(-50%,-50%);
    }

    .gq .navrow { display: flex; justify-content: space-between; align-items: center; gap: .75rem; flex-wrap: wrap; }
    .gq .btn {
      font-family: 'IBM Plex Mono', monospace;
      font-size: .72rem;
      letter-spacing: .06em;
      text-transform: uppercase;
      padding: .7rem 1.25rem;
      border-radius: 8px;
      cursor: pointer;
      border: 1.5px solid var(--gq-accent);
      background: var(--gq-accent);
      color: #0a0e1a;
      font-weight: 600;
    }
    .gq .btn:disabled { opacity: .35; cursor: not-allowed; }
    .gq .btn.ghost {
      background: transparent;
      color: var(--gq-text);
      border-color: var(--gq-border);
    }
    .gq .btn.ghost:hover { border-color: var(--gq-accent); color: var(--gq-accent); }

    .gq .results-head { margin-bottom: 1.25rem; }
    .gq .results-head .eyebrow {
      font-family: 'IBM Plex Mono', monospace;
      font-size: .72rem;
      letter-spacing: .12em;
      text-transform: uppercase;
      color: var(--gq-teal);
      margin: 0 0 .5rem;
    }
    .gq .results-head h2 { font-size: 1.35rem; font-weight: 700; margin: 0 0 .5rem; }
    .gq .results-head p { color: var(--gq-muted); font-size: .9rem; line-height: 1.6; margin: 0; }

    .gq .stack { display: flex; flex-direction: column; gap: .9rem; margin: 1.25rem 0; }
    .gq .card {
      border: 1px solid var(--gq-border);
      background: var(--gq-card);
      border-radius: 12px;
      padding: 1.15rem 1.25rem;
      position: relative;
    }
    .gq .card-top { display: flex; justify-content: space-between; align-items: flex-start; gap: .85rem; margin-bottom: .4rem; }
    .gq .card-jur {
      font-family: 'IBM Plex Mono', monospace;
      font-size: .68rem;
      letter-spacing: .08em;
      text-transform: uppercase;
      color: var(--gq-teal);
      margin: 0 0 .25rem;
    }
    .gq .card-name { font-size: 1.05rem; font-weight: 700; margin: 0; line-height: 1.3; }
    .gq .stamp {
      font-family: 'IBM Plex Mono', monospace;
      font-size: .65rem;
      letter-spacing: .06em;
      text-transform: uppercase;
      border: 1.5px solid var(--gq-green);
      color: var(--gq-green);
      padding: .3rem .55rem;
      border-radius: 999px;
      white-space: nowrap;
      flex: 0 0 auto;
      font-weight: 600;
    }
    .gq .stamp.maybe { border-color: var(--gq-amber); color: var(--gq-amber); }
    .gq .stamp.closed { border-color: var(--gq-muted); color: var(--gq-muted); }
    .gq .card-desc { font-size: .9rem; color: var(--gq-muted); line-height: 1.6; margin: .5rem 0 .75rem; }
    .gq .card-elig { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: .75rem; }
    .gq .elig-chip {
      font-size: .72rem;
      background: var(--gq-surface);
      border: 1px solid var(--gq-border);
      border-radius: 6px;
      padding: .3rem .55rem;
      color: var(--gq-muted);
    }
    .gq .elig-chip strong { color: var(--gq-text); font-weight: 600; }
    .gq .card-figs { display: flex; flex-wrap: wrap; gap: 1.1rem; margin-bottom: .75rem; }
    .gq .fig { font-family: 'IBM Plex Mono', monospace; font-size: .75rem; color: var(--gq-muted); }
    .gq .fig b { display: block; font-size: .9rem; color: var(--gq-text); margin-top: .15rem; font-weight: 600; }
    .gq .card-note {
      font-size: .8rem;
      color: var(--gq-muted);
      border-top: 1px solid var(--gq-border);
      padding-top: .65rem;
      line-height: 1.55;
      margin: 0;
    }
    .gq .card-link {
      font-size: .85rem;
      color: var(--gq-accent);
      text-decoration: none;
      font-weight: 600;
    }
    .gq .card-link:hover { text-decoration: underline; }
    .gq .cta {
      margin-top: 1.5rem;
      border: 1px solid rgba(74,158,255,.35);
      background: rgba(74,158,255,.08);
      padding: 1.15rem 1.25rem;
      border-radius: 12px;
    }
    .gq .cta h3 { font-size: 1rem; margin: 0 0 .4rem; }
    .gq .cta p { font-size: .88rem; color: var(--gq-muted); margin: 0; line-height: 1.55; }
    .gq .fine {
      font-size: .78rem;
      color: var(--gq-muted);
      margin-top: 1.5rem;
      line-height: 1.6;
      border-top: 1px solid var(--gq-border);
      padding-top: 1rem;
    }
    .gq .empty { font-size: .95rem; color: var(--gq-muted); padding: 1rem 0; }

    /* Dark page body when quiz is main content */
    body.gq-page { background: #0a0e1a; color: #e1e4e8; }
    body.gq-page .page-hero-gq {
      background: linear-gradient(135deg, #0d1230, #1a1f45);
      border-bottom: 1px solid #2a3050;
      padding: 2.5rem 1.25rem 2rem;
      text-align: center;
    }
    body.gq-page .page-hero-gq .eyebrow {
      color: #4a9eff;
      font-size: .8rem;
      font-weight: 600;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    body.gq-page .page-hero-gq h1 {
      font-size: clamp(1.6rem, 4vw, 2.25rem);
      margin: .65rem 0;
    }
    body.gq-page .page-hero-gq p {
      color: #8892a4;
      max-width: 40rem;
      margin: 0 auto;
      font-size: .95rem;
    }
  </style>
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    "name": "Grant & Cost-Share Eligibility Quiz",
    "url": "https://research.opensourcemed.info/grant-eligibility-quiz.html",
    "description": "Interactive eligibility matching for agricultural and land-stewardship cost-share programs in Alberta, British Columbia, Saskatchewan, and federal Canada.",
    "applicationCategory": "EducationalApplication",
    "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" },
    "creator": { "@type": "Organization", "name": "Open Source Medicine Foundation", "url": "https://opensourcemed.info" }
  }
  </script>
</head>
<body class="gq-page">
<nav>
  <div class="nav-container">
    <a href="https://opensourcemed.info" class="nav-brand">
      Open Source <span>Medicine</span>
      <span class="nav-brand-sub">Research Tracker</span>
    </a>
    <button class="nav-toggle" aria-label="Toggle navigation menu"><span></span><span></span><span></span></button>
    <ul class="nav-links">
      <li><a href="index.html">Home</a></li>
      <li><a href="medical-freedom-map.html">Freedom Map</a></li>
      <li><a href="maps/">State Maps</a></li>
      <li><a href="grant-eligibility-quiz.html" class="active">Grants</a></li>
      <li><a href="https://www.paypal.com/ncp/payment/A2MK3BCVE4X7C" class="nav-support">Support</a></li>
    </ul>
  </div>
</nav>

<header class="page-hero-gq">
  <div class="eyebrow">Land · agriculture · clean tech</div>
  <h1>Grant &amp; cost-share eligibility</h1>
  <p>Match your property and project to 29 programs across Alberta, British Columbia, Saskatchewan, and federal Canada — with summaries, eligibility rules, and official links.</p>
</header>

<main class="gq">
  <div class="disc">
    <strong>Informational only.</strong> Not legal, tax, or grant-writing advice. Intake windows, rates, and caps change without notice — verify with the delivery agency before applying. Curated for research and planning; not affiliated with listed programs.
  </div>

  <div class="gq-hero">
    <p class="eyebrow">Interactive quiz + full directory</p>
    <h1 style="font-size:1.25rem;margin:0 0 .5rem;">Five questions → matched programs</h1>
    <p>Answers filter by province, operation type, production value, wetland proximity, and project tags. Or skip to the full directory of every program with eligibility chips and source links.</p>
    <p class="meta">AB · BC · SK · Federal · EFP · SCAP · water · riparian · energy · processing</p>
    <div class="gq-tools">
      <button type="button" id="browse-all">Browse all programs →</button>
      <a href="data/grants.json">Download grants JSON</a>
      <a href="index.html">Research Tracker home</a>
    </div>
  </div>

  <div id="quiz">
    <div class="progress" id="progress"></div>

    <div class="step active" data-step="0">
      <p class="q-index">01 / property</p>
      <p class="q-text">Where is the property?</p>
      <div class="opts single" data-q="province" data-multi="false">
        <button class="opt single" data-v="AB" type="button">Alberta<span class="mark"></span></button>
        <button class="opt single" data-v="BC" type="button">British Columbia<span class="mark"></span></button>
        <button class="opt single" data-v="SK" type="button">Saskatchewan<span class="mark"></span></button>
        <button class="opt single" data-v="OTHER" type="button">Somewhere else in Canada<span class="mark"></span></button>
      </div>
      <div class="navrow"><span></span><button class="btn" id="next0" type="button" disabled>Next</button></div>
    </div>

    <div class="step" data-step="1">
      <p class="q-index">02 / operation type</p>
      <p class="q-text">Which best describes you?</p>
      <div class="opts single" data-q="type" data-multi="false">
        <button class="opt single" data-v="producer" type="button">Registered agricultural producer (farm or ranch business)<span class="mark"></span></button>
        <button class="opt single" data-v="acreage" type="button">Acreage, hobby farm, or rural residential landowner<span class="mark"></span></button>
        <button class="opt single" data-v="processor" type="button">Agricultural or food processor (dairy, poultry, egg, meat, value-added)<span class="mark"></span></button>
        <button class="opt single" data-v="greenhouse" type="button">Greenhouse, vertical farm, or controlled-environment grower<span class="mark"></span></button>
        <button class="opt single" data-v="org" type="button">Municipality, First Nation, land trust, or non-profit<span class="mark"></span></button>
        <button class="opt single" data-v="unsure" type="button">Not sure yet<span class="mark"></span></button>
      </div>
      <div class="navrow"><button class="btn ghost" type="button" data-back="1">Back</button><button class="btn" id="next1" type="button" disabled>Next</button></div>
    </div>

    <div class="step" data-step="2">
      <p class="q-index">03 / production value</p>
      <p class="q-text">Roughly what's the annual value of farm products produced or sold on the property?</p>
      <div class="opts single" data-q="income" data-multi="false">
        <button class="opt single" data-v="under25" type="button">Under $25,000, or not applicable<span class="mark"></span></button>
        <button class="opt single" data-v="25to50" type="button">$25,000 – $50,000<span class="mark"></span></button>
        <button class="opt single" data-v="over50" type="button">Over $50,000<span class="mark"></span></button>
      </div>
      <div class="navrow"><button class="btn ghost" type="button" data-back="2">Back</button><button class="btn" id="next2" type="button" disabled>Next</button></div>
    </div>

    <div class="step" data-step="3">
      <p class="q-index">04 / site features</p>
      <p class="q-text">Is the property near a wetland, stream, river, or lake?</p>
      <div class="opts single" data-q="wetland" data-multi="false">
        <button class="opt single" data-v="yes" type="button">Yes, it borders or includes one<span class="mark"></span></button>
        <button class="opt single" data-v="no" type="button">No, or not that I know of<span class="mark"></span></button>
        <button class="opt single" data-v="unsure" type="button">Not sure<span class="mark"></span></button>
      </div>
      <div class="navrow"><button class="btn ghost" type="button" data-back="3">Back</button><button class="btn" id="next3" type="button" disabled>Next</button></div>
    </div>

    <div class="step" data-step="4">
      <p class="q-index">05 / project interest</p>
      <p class="q-text">Which projects are you exploring? Pick as many as apply.</p>
      <div class="opts multi" data-q="projects" data-multi="true">
        <button class="opt multi" data-v="pond" type="button">Pond or dugout — water storage<span class="mark"></span></button>
        <button class="opt multi" data-v="swale" type="button">Swales &amp; water-harvesting earthworks<span class="mark"></span></button>
        <button class="opt multi" data-v="shelterbelt" type="button">Shelterbelt or windbreak planting<span class="mark"></span></button>
        <button class="opt multi" data-v="riparian" type="button">Riparian or wetland restoration<span class="mark"></span></button>
        <button class="opt multi" data-v="waterinfra" type="button">Well, pipeline, or off-grid water system<span class="mark"></span></button>
        <button class="opt multi" data-v="design" type="button">General permaculture design &amp; site planning<span class="mark"></span></button>
        <button class="opt multi" data-v="grazing" type="button">Rotational grazing &amp; pasture improvement<span class="mark"></span></button>
        <button class="opt multi" data-v="greenhouse" type="button">Greenhouse or vertical farm build/expansion<span class="mark"></span></button>
        <button class="opt multi" data-v="energy" type="button">Solar, energy efficiency, or clean tech<span class="mark"></span></button>
        <button class="opt multi" data-v="processing" type="button">Water, wastewater, or energy at a processing facility<span class="mark"></span></button>
        <button class="opt multi" data-v="forestry" type="button">Forest, woodlot, or wildfire risk management<span class="mark"></span></button>
        <button class="opt multi" data-v="market" type="button">Developing new or export markets<span class="mark"></span></button>
      </div>
      <div class="navrow"><button class="btn ghost" type="button" data-back="4">Back</button><button class="btn" id="next4" type="button" disabled>See eligible programs</button></div>
    </div>

    <div class="step" data-step="5" id="results"></div>
  </div>
</main>

<footer class="osmf-network-footer">
  <div class="osmf-network-inner">
    <div class="footer-brand">Open Source Medicine Foundation</div>
    <div class="footer-links">
      <a href="https://opensourcemed.info">OSMF</a>
      <a href="index.html">Research Tracker</a>
      <a href="medical-freedom-map.html">Medical Freedom Map</a>
      <a href="grant-eligibility-quiz.html">Grant Quiz</a>
    </div>
    <p style="margin-top:1rem;font-size:.8rem;opacity:.7">Program data curated for planning; verify with official sources.</p>
  </div>
</footer>

<script>
const GRANTS = __GRANTS_JS__;

__LOGIC__
renderProgress();
</script>
</body>
</html>
"""
    page = page.replace("__GRANTS_JS__", grants_js).replace("__LOGIC__", logic)
    return page


def main():
    src = SRC.read_text(encoding="utf-8")
    grants_js = extract_grants_js(src)
    grants = grants_js_to_json(grants_js)
    if grants:
        DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
        # Unescape common HTML entities in string fields for cleaner JSON
        def clean(o):
            if isinstance(o, str):
                return (
                    o.replace("&mdash;", "—")
                    .replace("&ndash;", "–")
                    .replace("&amp;", "&")
                    .replace("&middot;", "·")
                )
            if isinstance(o, list):
                return [clean(x) for x in o]
            if isinstance(o, dict):
                return {k: clean(v) for k, v in o.items()}
            return o

        clean_grants = clean(grants)
        DATA_OUT.write_text(
            json.dumps(
                {
                    "source": "Expanding Edge grant eligibility quiz (adapted for OSMF Research Tracker)",
                    "count": len(clean_grants),
                    "jurisdictions": ["AB", "BC", "SK", "Federal"],
                    "items": clean_grants,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"Wrote {DATA_OUT} ({len(clean_grants)} grants)")
    else:
        print("Skipped grants.json (parse failed)")

    page = build_page(src, grants_js)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
