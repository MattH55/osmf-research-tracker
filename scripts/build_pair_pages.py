#!/usr/bin/env python3
"""
Build Template B pages: "<Agent> for <Disease>: evidence, trials and status".

Reads (via scripts/lib/repurposing_data.py) the disease-intelligence files,
therapeutic_agents.json, the current trials registry, the literature caches
and the disease-agent join table.

Writes:
  pairs/<disease-slug>/<agent-slug>.html   one page per pair with >=1 trial or >=2 literature items
  pairs/<disease-slug>/index.html          per-disease list
  pairs/index.html                         hub

Thin pairs (no trial and fewer than 2 literature items) are skipped and counted.
Pages that still fall under 200 words of prose, or carry no PMID/DOI/NCT
citation, get <meta name="robots" content="noindex,follow"> (spec section 4).

Usage: python scripts/build_pair_pages.py [--dry-run] [--limit N]
"""
import html
import json
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.lib.repurposing_data import build_records, SCORE_DOC, SITE, TIER_LABEL  # noqa: E402
from scripts.lib.thin_content_gate import gate as thin_gate  # noqa: E402

OUT_DIR = ROOT / "pairs"
MIN_WORDS = 200
GA_ID = "G-202S9N21TE"
SUBSTACK = "https://opensourcemed.substack.com/subscribe?utm_source=tracker"
TODAY = date.today().isoformat()


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def plural(n: int, one: str, many: str = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def join_list(items) -> str:
    items = [i for i in items if i]
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


STATUS_HUMAN = {
    "RECRUITING": "recruiting",
    "ENROLLING_BY_INVITATION": "enrolling by invitation",
    "ACTIVE_NOT_RECRUITING": "active, not recruiting",
    "NOT_YET_RECRUITING": "not yet recruiting",
    "COMPLETED": "completed",
    "UNKNOWN": "status unknown",
    "TERMINATED": "terminated",
    "WITHDRAWN": "withdrawn",
    "SUSPENDED": "suspended",
}
PHASE_HUMAN = {
    "PHASE4": "Phase 4", "PHASE3": "Phase 3", "PHASE2": "Phase 2", "PHASE1": "Phase 1",
    "EARLY_PHASE1": "Early Phase 1", "NA": "Not applicable",
}
PHASE_RANK = {"PHASE4": 4, "PHASE3": 3, "PHASE2": 2, "PHASE1": 1, "EARLY_PHASE1": 0.5, "NA": 0}
LIT_HUMAN = {
    "cochrane_review": ("Cochrane review", "Cochrane reviews"),
    "meta_analysis": ("meta-analysis", "meta-analyses"),
    "systematic_review": ("systematic review", "systematic reviews"),
    "rct": ("randomised controlled trial publication", "randomised controlled trial publications"),
    "clinical_trial": ("clinical trial publication", "clinical trial publications"),
    "curated_reference": ("curated reference", "curated references"),
    "pubmed_search": ("PubMed search record", "PubMed search records"),
    "other": ("other publication", "other publications"),
}

# ---------------------------------------------------------------------------
# Shared chrome
# ---------------------------------------------------------------------------
CSS = """
:root{--primary:#0068f8;--primary-dark:#0052c7;--secondary:#ff9800;--text-dark:#1f2937;--text-mid:#4b5563;--text-light:#6b7280;--bg-light:#f8fafc;--bg-white:#fff;--border:#e5e7eb;--success:#10b981;--warning:#f59e0b;--danger:#ef4444}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif;line-height:1.6;color:var(--text-dark);background:var(--bg-white)}
a{color:var(--primary)}
.nav-minimal{background:var(--primary);padding:.75rem 0;position:sticky;top:0;z-index:100}
.nav-container{max-width:1100px;margin:0 auto;padding:0 1rem;display:flex;justify-content:space-between;align-items:center;gap:1rem;flex-wrap:wrap}
.nav-brand{color:#fff;text-decoration:none;font-weight:700;font-size:.95rem;white-space:nowrap}
.nav-brand span{opacity:.8;font-weight:400;font-size:.8rem;margin-left:.4rem}
.nav-links{display:flex;align-items:center;gap:1rem;flex-wrap:wrap}
.nav-links a{color:rgba(255,255,255,.85);text-decoration:none;font-size:.85rem;font-weight:500}
.nav-links a:hover,.nav-links a.active{color:#fff}
.hero{background:linear-gradient(135deg,#0068f8 0%,#0052c7 100%);color:#fff;padding:2.5rem 1rem 2.75rem}
.hero-inner{max-width:1100px;margin:0 auto}
.hero-badge{display:inline-block;background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);font-size:.72rem;font-weight:600;padding:.25rem .8rem;border-radius:20px;letter-spacing:.04em;text-transform:uppercase;margin-bottom:.9rem}
.hero h1{font-size:clamp(1.5rem,3.5vw,2.25rem);font-weight:700;line-height:1.25;letter-spacing:-.01em;margin-bottom:.6rem}
.hero p{font-size:1rem;color:rgba(255,255,255,.88);max-width:760px}
.hero-meta{display:flex;flex-wrap:wrap;gap:.6rem 1.2rem;margin-top:1rem;font-size:.85rem;color:rgba(255,255,255,.8)}
.hero-meta strong{color:#fff}
.crumbs{max-width:1100px;margin:0 auto;padding:.6rem 1rem;font-size:.8rem;color:var(--text-light)}
.crumbs a{color:var(--text-mid);text-decoration:none}.crumbs a:hover{text-decoration:underline}
main{max-width:1100px;margin:0 auto;padding:1.5rem 1rem 3rem}
section.block{margin:1.75rem 0}
h2{font-size:1.3rem;margin-bottom:.6rem;letter-spacing:-.01em}
h3{font-size:1.05rem;margin:.9rem 0 .35rem}
p{margin:.5rem 0}
.lede{font-size:1.02rem;color:var(--text-mid)}
.warn{background:#fffbeb;border:1px solid #fde68a;border-left:4px solid var(--warning);border-radius:8px;padding:.8rem 1rem;font-size:.9rem;margin:1rem 0}
.callout{background:var(--bg-light);border:1px solid var(--border);border-radius:10px;padding:1rem 1.1rem;margin:1rem 0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.75rem;margin:.75rem 0}
.stat{background:var(--bg-light);border:1px solid var(--border);border-radius:10px;padding:.75rem .9rem}
.stat .v{font-size:1.45rem;font-weight:700;color:var(--primary-dark);line-height:1.2}
.stat .l{font-size:.75rem;color:var(--text-light);text-transform:uppercase;letter-spacing:.04em}
.table-wrap{overflow-x:auto;border:1px solid var(--border);border-radius:10px}
table{width:100%;border-collapse:collapse;font-size:.88rem}
th,td{padding:.55rem .7rem;text-align:left;vertical-align:top;border-bottom:1px solid var(--border)}
th{background:var(--bg-light);font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;color:var(--text-mid)}
tr:last-child td{border-bottom:none}
.tag{display:inline-block;font-size:.7rem;font-weight:600;padding:.12rem .5rem;border-radius:999px;border:1px solid var(--border);background:#fff;color:var(--text-mid);white-space:nowrap}
.tag.rec{background:#ecfdf5;color:#047857;border-color:#a7f3d0}
.tag.act{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}
.tag.done{background:#f8fafc;color:#334155}
.tag.off{background:#fef2f2;color:#b91c1c;border-color:#fecaca}
.tag.tier-A{background:#dcfce7;color:#166534;border-color:#86efac}
.tag.tier-B{background:#dbeafe;color:#1e40af;border-color:#93c5fd}
.tag.tier-C{background:#fef3c7;color:#92400e;border-color:#fcd34d}
.tag.tier-D{background:#f3f4f6;color:#4b5563}
ul.refs{list-style:none;padding:0}
ul.refs li{padding:.5rem 0;border-bottom:1px solid var(--border);font-size:.9rem}
ul.refs li:last-child{border-bottom:none}
.muted{color:var(--text-light);font-size:.82rem}
details.faq{border:1px solid var(--border);border-radius:8px;padding:.6rem .9rem;margin:.5rem 0;background:#fff}
details.faq summary{font-weight:600;cursor:pointer}
details.faq p{margin:.5rem 0 .2rem;color:var(--text-mid)}
.cite{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.8rem;background:#f1f5f9;border:1px solid var(--border);border-radius:8px;padding:.75rem .9rem;word-break:break-word}
.btn{display:inline-block;background:var(--secondary);color:#fff;text-decoration:none;font-weight:600;padding:.5rem .95rem;border-radius:6px;font-size:.88rem}
.btn.ghost{background:#fff;color:var(--primary);border:1px solid var(--primary)}
.links{display:flex;flex-wrap:wrap;gap:.5rem;margin:.6rem 0}
.score-parts{font-size:.85rem;color:var(--text-mid)}
.score-parts li{margin:.2rem 0 .2rem 1.1rem}
footer.site{background:#111827;color:#9ca3af;padding:2rem 1rem;font-size:.85rem;margin-top:2rem}
footer.site .inner{max-width:1100px;margin:0 auto;display:flex;flex-wrap:wrap;gap:1rem 2rem;justify-content:space-between}
footer.site a{color:#d1d5db;text-decoration:none;margin-right:1rem}
footer.site a:hover{color:#fff}
.card-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.75rem}
.card{border:1px solid var(--border);border-radius:10px;padding:.85rem 1rem;background:#fff;text-decoration:none;color:inherit;display:block}
.card:hover{border-color:var(--primary)}
.card h3{margin:0 0 .3rem;font-size:1rem;color:var(--primary-dark)}
.search{width:100%;padding:.6rem .8rem;border:1px solid var(--border);border-radius:8px;font:inherit;margin:.75rem 0}
@media (max-width:640px){.hero{padding:1.8rem 1rem 2rem}.nav-links{gap:.7rem}.nav-links a{font-size:.8rem}}
"""


def head(title: str, description: str, canonical: str, jsonld: list, noindex: bool = False, og_type: str = "article") -> str:
    robots = '<meta name="robots" content="noindex,follow">' if noindex else '<meta name="robots" content="index,follow,max-image-preview:large">'
    ld = "\n".join(f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False)}</script>' for x in jsonld)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA_ID}');
</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{robots}
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="{og_type}">
<meta property="og:site_name" content="Open Source Medicine Foundation">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="https://opensourcemed.info/favicon.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(description)}">
<link rel="icon" href="https://opensourcemed.info/favicon.png" type="image/png">
<link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
{ld}
</head>"""


def nav(active: str = "") -> str:
    def a(href, label, key):
        cls = ' class="active"' if key == active else ""
        return f'<a href="{href}"{cls}>{label}</a>'
    return f"""<nav class="nav-minimal" aria-label="Main navigation">
<div class="nav-container">
<a href="/index.html" class="nav-brand">Open Source Medicine <span>Research Tracker</span></a>
<div class="nav-links">
{a('/index.html', 'Conditions', 'index')}
{a('/biomarker-atlas.html', 'Biomarkers', 'biomarkers')}
{a('/clinical_trials.html', 'Trials', 'trials')}
{a('/agents.html', 'Agents', 'agents')}
{a('/tools/repurposing-explorer.html', 'Repurposing Explorer', 'explorer')}
<a href="https://opensourcemed.info" rel="noopener">opensourcemed.info</a>
</div>
</div>
</nav>"""


def footer() -> str:
    return f"""<footer class="site">
<div class="inner">
<div><strong style="color:#fff">Open Source Medicine Foundation</strong><br>Research map, not treatment advice. Content CC BY 4.0. Data from ClinicalTrials.gov, PubMed, Open Targets, ChEMBL and DGIdb.</div>
<div><a href="/index.html">Research Tracker</a><a href="/tools/repurposing-explorer.html">Repurposing Explorer</a><a href="/pairs/">All pairs</a><a href="/agents/">Agent pages</a><a href="https://opensourcemed.info" rel="noopener">opensourcemed.info</a><a href="{SUBSTACK}" rel="noopener">Substack</a></div>
</div>
</footer>"""


# ---------------------------------------------------------------------------
# Prose helpers (built from the record; varies with the evidence profile)
# ---------------------------------------------------------------------------
def trial_sentences(rec: dict) -> str:
    trials = rec["trials"]
    disease = rec["disease_short"]
    agent = rec["agent_name"]
    if not trials:
        return (f"No registered clinical trial in this database tests {agent} specifically in {disease}. "
                f"The evidence below comes from published literature only, so any clinical signal has not yet been "
                f"tested prospectively against this condition in a registered study.")
    tb = rec["trial_breakdown"]
    parts = []
    if tb["recruiting"]:
        parts.append(plural(tb["recruiting"], "is currently recruiting", "are currently recruiting"))
    if tb["active"]:
        parts.append(plural(tb["active"], "is active or not yet recruiting", "are active or not yet recruiting"))
    if tb["completed"]:
        parts.append(plural(tb["completed"], "has completed", "have completed"))
    if tb["other"]:
        parts.append(plural(tb["other"], "is terminated, withdrawn, suspended or of unknown status",
                            "are terminated, withdrawn, suspended or of unknown status"))
    status_txt = "; ".join(parts)
    best = max(trials, key=lambda t: (PHASE_RANK.get(t["phase"], 0), t.get("enrollment") or 0))
    largest = max(trials, key=lambda t: t.get("enrollment") or 0)
    s = (f"ClinicalTrials.gov lists {plural(len(trials), 'registered trial')} linking {agent} to {disease}: {status_txt}. ")
    if best["phase"] != "NA":
        s += f"The most advanced is {PHASE_HUMAN.get(best['phase'], best['phase'])} ({best['nct_id']}"
        if best.get("sponsor"):
            s += f", sponsored by {best['sponsor']}"
        s += "). "
    else:
        s += "None of the registered studies carries a drug-development phase label, which is typical for behavioural, device and supplement protocols. "
    if largest.get("enrollment") and largest is not best:
        s += f"The largest enrolment is {largest['enrollment']} participants ({largest['nct_id']}). "
    elif largest.get("enrollment"):
        s += f"It plans or enrolled {largest['enrollment']} participants. "
    years = [t["year"] for t in trials if t.get("year")]
    if years:
        if min(years) == max(years):
            s += f"Registered activity dates to {min(years)}."
        else:
            s += f"Registration activity spans {min(years)} to {max(years)}."
    return s.strip()


def lit_sentences(rec: dict) -> str:
    lit = rec["literature"]
    agent = rec["agent_name"]
    disease = rec["disease_short"]
    if not lit:
        return (f"No published literature item is linked to {agent} and {disease} in the OSMF database yet, so the record "
                f"rests on registry entries alone. Registry entries describe intent to study, not outcomes.")
    counts = rec["lit_breakdown"]
    order = ["cochrane_review", "meta_analysis", "systematic_review", "rct", "clinical_trial", "curated_reference", "pubmed_search", "other"]
    bits = []
    for k in order:
        if counts.get(k):
            one, many = LIT_HUMAN.get(k, (k, k))
            bits.append(plural(counts[k], one, many))
    years = [l["year"] for l in lit if l.get("year")]
    s = f"The literature layer holds {plural(len(lit), 'publication')} for this pair: {join_list(bits)}. "
    if years:
        s += f"Publication years run from {min(years)} to {max(years)}. " if min(years) != max(years) else f"The dated items are from {min(years)}. "
    hi = (counts.get("cochrane_review", 0) + counts.get("meta_analysis", 0) + counts.get("systematic_review", 0))
    if hi:
        s += ("Because at least one synthesis-level source exists (systematic review, meta-analysis or Cochrane review), "
              "this pair has been assessed beyond single studies, although the synthesis may concern a different indication. ")
    elif counts.get("rct") or counts.get("clinical_trial"):
        s += ("These are primary trial reports rather than syntheses, so results have not yet been pooled or graded "
              "independently. ")
    else:
        s += ("Items here are search-derived or curated references rather than classified trial reports; treat them as "
              "leads to read, not as graded evidence. ")
    return s.strip()


def approval_sentence(rec: dict) -> str:
    agent = rec["agent_name"]
    disease = rec["disease_short"]
    if rec["source_track"] == "ta":
        return (f"{agent} is tracked by OSMF as an investigational option for {disease}; no regulator has approved it "
                f"for this indication, and most post-viral conditions have no approved disease-modifying therapy at all.")
    if rec["approved_any"]:
        ind = rec["approved_indications"]
        if ind:
            return (f"{agent} has reached approval for other indications ({join_list(ind[:4])}), so its use in {disease} "
                    f"would be repurposing of an established medicine rather than a new chemical entity.")
        return (f"{agent} has reached the approved stage (maximum clinical phase 4) for at least one indication, so its use "
                f"in {disease} would be drug repurposing rather than first-in-human development. This does not mean it is "
                f"approved for {disease}.")
    ph = rec["phase_label"] or "an unspecified"
    return (f"{agent} has reached {ph} as its most advanced recorded development stage across any indication, and the "
            f"database holds no approval for {disease}.")


def tier_sentence(rec: dict) -> str:
    t = rec["tier"]
    label = TIER_LABEL.get(t, t)
    base = f"OSMF's existing evidence tier for this pair is {t} ({label})"
    if rec["source_track"] == "di":
        src = join_list(rec["sources"]) or "public databases"
        how = f", derived from the strength of the disease association recorded in {src}"
        if rec["via_alteration"]:
            how += f", in this case via the biomarker or target {rec['via_alteration']}"
        return base + how + ". The tier describes how well the drug-disease link is documented, not how well the drug works."
    return base + (", taken from the OSMF therapeutic agent database, which grades agents by the volume and design of "
                   "condition-specific evidence rather than by effect size.")


def mechanism_sentence(rec: dict) -> str:
    if rec["mechanism"]:
        return f"Recorded mechanism or class: {rec['mechanism']}."
    if rec["agent_type"] == "Behavioural":
        return "This is a behavioural, rehabilitation or protocol-based intervention rather than a molecule, so no pharmacological mechanism is recorded."
    if rec["agent_type"] == "Device":
        return "This is a device or procedure-based intervention; no pharmacological mechanism is recorded."
    return "No mechanism of action is recorded for this pair in the source databases."


def disease_context(rec: dict, cond: dict) -> str:
    disease = rec["disease_short"]
    if cond["track"] == "post-viral":
        return (f"{cond['name']} is tracked on the OSMF post-viral programme alongside ME/CFS, Long COVID, POTS and MCAS. "
                f"Across the programme, {cond['n_candidates']} candidate agents are logged for {disease}, most of them "
                f"preliminary; this page isolates the record for one of them.")
    s = (f"The RepurpOS disease-intelligence file for {cond['name']} ranks {cond['n_candidates']} candidate therapeutics from "
         f"Open Targets, ChEMBL, DGIdb and PubMed; only a minority carry direct clinical evidence, and this page covers one of those. ")
    if cond.get("remission_note"):
        s += f"Spontaneous remission context recorded for the condition: {cond['remission_note'].rstrip('.')}. "
    return s.strip()


def what_evidence_shows(rec: dict) -> str:
    tb = rec["trial_breakdown"]
    lit = rec["lit_breakdown"]
    hi = lit.get("cochrane_review", 0) + lit.get("meta_analysis", 0) + lit.get("systematic_review", 0)
    agent, disease = rec["agent_name"], rec["disease_short"]
    if hi and tb["completed"]:
        core = (f"{agent} has both completed registered trials and synthesis-level publications linked to {disease}. "
                f"That is the strongest profile in this database, but the summaries here do not extract effect sizes, "
                f"so read the linked reviews for direction and magnitude of benefit.")
    elif tb["completed"] and lit:
        core = (f"{agent} has {plural(tb['completed'], 'completed trial')} and {plural(len(rec['literature']), 'linked publication')} "
                f"for {disease}. Completed trials may or may not have posted results; follow the NCT links to check.")
    elif tb["completed"]:
        core = (f"{agent} has {plural(tb['completed'], 'completed registered trial')} for {disease} but no linked publication, "
                f"which usually means results are unpublished, pending, or not yet matched to this record.")
    elif tb["total"]:
        core = (f"Trials of {agent} in {disease} are registered but none has completed, so there is no outcome evidence from "
                f"those studies yet; the record is a signal of research interest.")
    elif hi:
        core = (f"Synthesis-level literature links {agent} to {disease}, but no registered trial in this database tests the pair, "
                f"so the evidence is observational, pooled from other indications, or pre-dates registry practice.")
    else:
        core = (f"The record for {agent} in {disease} rests on {plural(len(rec['literature']), 'publication')} without a registered trial. "
                f"This is a lead for hypothesis generation, not evidence of efficacy.")
    return core


def build_pair_page(rec: dict, cond: dict, siblings: list) -> str:
    agent = rec["agent_name"]
    disease = rec["disease_short"]
    url = SITE + rec["pair_url"]
    tb = rec["trial_breakdown"]
    n_lit = len(rec["literature"])
    title = f"{agent} for {disease}: evidence, trials and status"
    desc_bits = [f"{plural(tb['total'], 'registered trial')}"]
    if tb["recruiting"]:
        desc_bits.append(f"{tb['recruiting']} recruiting")
    desc_bits.append(f"{plural(n_lit, 'publication')}")
    description = (f"{agent} for {disease}: {', '.join(desc_bits)}, evidence tier {rec['tier']} ({rec['tier_label']}). "
                   f"Trial status, PubMed links and repurposing context from the Open Source Medicine Foundation research map.")[:300]

    intro = " ".join([approval_sentence(rec), trial_sentences(rec), lit_sentences(rec)])
    faq = [
        (f"Is {agent} approved for {disease}?", approval_sentence(rec) + " Approval status for the specific indication should always be confirmed with the relevant regulator and prescribing information."),
        (f"Is {agent} in clinical trials for {disease}?", trial_sentences(rec)),
        (f"What does the evidence show for {agent} in {disease}?", what_evidence_shows(rec) + " " + tier_sentence(rec)),
    ]

    # evidence table
    ev_rows = [
        ("Evidence tier", f'<span class="tag tier-{esc(rec["tier"])}">{esc(rec["tier"])} · {esc(rec["tier_label"])}</span>'),
        ("Evidence score", f"{rec['score']} (trials {rec['score_parts']['trials']}, literature {rec['score_parts']['literature']}, tier {rec['score_parts']['tier']}, approved bonus {rec['score_parts']['approved']})"),
        ("Registered trials", f"{tb['total']} total: {tb['recruiting']} recruiting, {tb['active']} active / not yet recruiting, {tb['completed']} completed, {tb['other']} other"),
        ("Linked publications", str(n_lit) + (" (" + ", ".join(f"{v} {LIT_HUMAN.get(k, (k, k))[1 if v != 1 else 0]}" for k, v in sorted(rec['lit_breakdown'].items(), key=lambda kv: -kv[1])) + ")" if n_lit else "")),
        ("Agent type", esc(rec["agent_type"]) + (f' <span class="muted">({esc(rec["agent_type_raw"])})</span>' if rec["agent_type_raw"] and rec["agent_type_raw"] != rec["agent_type"] else "")),
        ("Development stage (any indication)", esc(rec["phase_label"] or "Not recorded")),
        ("Mechanism / class", esc(rec["mechanism"]) if rec["mechanism"] else '<span class="muted">Not recorded</span>'),
        ("Data sources", esc(", ".join(rec["sources"])) if rec["sources"] else '<span class="muted">OSMF database</span>'),
    ]
    if rec["via_alteration"]:
        ev_rows.append(("Linked via biomarker / target", esc(rec["via_alteration"])))
    if rec["aliases"]:
        ev_rows.append(("Also known as", esc(", ".join(rec["aliases"][:8]))))
    ev_table = "".join(f"<tr><th scope=\"row\">{esc(k)}</th><td>{v}</td></tr>" for k, v in ev_rows)

    # trials
    if rec["trials"]:
        trows = []
        for t in sorted(rec["trials"], key=lambda t: (-(PHASE_RANK.get(t["phase"], 0)), t["status"])):
            grp = {"RECRUITING": "rec", "ENROLLING_BY_INVITATION": "rec", "ACTIVE_NOT_RECRUITING": "act",
                   "NOT_YET_RECRUITING": "act", "COMPLETED": "done"}.get(t["status"], "off")
            enrol = f"{t['enrollment']:,}" if t.get("enrollment") else "—"
            meta = " · ".join(x for x in [esc(t.get("sponsor")), str(t["year"]) if t.get("year") else ""] if x)
            trows.append(
                f'<tr><td><a href="{esc(t["url"])}" target="_blank" rel="noopener">{esc(t["nct_id"] or "Registry entry")}</a></td>'
                f'<td>{esc(t["title"]) or "<span class=muted>Untitled</span>"}' + (f'<div class="muted">{meta}</div>' if meta else "") + "</td>"
                f'<td><span class="tag {grp}">{esc(STATUS_HUMAN.get(t["status"], t["status"].lower()))}</span></td>'
                f'<td>{esc(PHASE_HUMAN.get(t["phase"], t["phase"]))}</td><td>{enrol}</td></tr>')
        trials_html = f"""<div class="table-wrap"><table>
<thead><tr><th>NCT ID</th><th>Title</th><th>Status</th><th>Phase</th><th>Enrolment</th></tr></thead>
<tbody>{''.join(trows)}</tbody></table></div>"""
    else:
        trials_html = f'<p class="muted">No registered trial links {esc(agent)} to {esc(disease)} in the current OSMF trial extract.</p>'
    ct_search = rec["search_links"].get("clinicaltrials_gov", "")
    pm_search = rec["search_links"].get("pubmed", "")

    # literature
    if rec["literature"]:
        lrows = []
        for l in sorted(rec["literature"], key=lambda l: (-(l.get("year") or 0), l["type"])):
            label = esc(l["title"]) if l["title"] else (f"PubMed record PMID {esc(l['pmid'])}" if l["pmid"] else "Reference")
            link = l["url"] or (f"https://doi.org/{l['doi']}" if l["doi"] else "")
            main_txt = f'<a href="{esc(link)}" target="_blank" rel="noopener">{label}</a>' if link else label
            meta = " · ".join(x for x in [esc(l.get("authors")), esc(l.get("journal")), str(l["year"]) if l.get("year") else "",
                                           f"PMID {esc(l['pmid'])}" if l["pmid"] and l["title"] else "",
                                           f"DOI {esc(l['doi'])}" if l["doi"] else ""] if x)
            lrows.append(f'<li><span class="tag">{esc(l["type_label"])}</span> {main_txt}' + (f'<div class="muted">{meta}</div>' if meta else "") + "</li>")
        lit_html = f'<ul class="refs">{"".join(lrows)}</ul>'
    else:
        lit_html = f'<p class="muted">No publication is linked to this pair yet.</p>'

    # notes (post-viral track)
    notes_html = ""
    if rec["source_track"] == "ta":
        bits = []
        if rec["notes"]:
            bits.append(f"<p><strong>Clinical notes:</strong> {esc(rec['notes'])}</p>")
        if rec["safety"]:
            bits.append(f"<p><strong>Safety:</strong> {esc(rec['safety'])}</p>")
        if rec["dosing"]:
            bits.append(f"<p><strong>Dosing in studies:</strong> {esc(rec['dosing'])}</p>")
        if bits:
            notes_html = f'<section class="block" id="notes"><h2>Mechanism and notes</h2><p>{esc(mechanism_sentence(rec))}</p>{"".join(bits)}</section>'
    else:
        notes_html = f'<section class="block" id="notes"><h2>Mechanism and notes</h2><p>{esc(mechanism_sentence(rec))}</p><p>{esc(tier_sentence(rec))}</p></section>'

    ext = "".join(f'<a class="btn ghost" href="{esc(l["url"])}" target="_blank" rel="noopener">{esc(l.get("label", "Link"))}</a>' for l in rec["external_links"][:4])
    agent_link = f'<a class="btn ghost" href="{esc(rec["agent_url"])}">Agent page: {esc(agent)}</a>' if rec["agent_url"] else ""
    cond_link = f'<a class="btn ghost" href="{esc(cond["url"])}">{esc(cond["short"])} hub</a>'
    interv_link = f'<a class="btn ghost" href="{esc(cond["interventions_url"])}">{esc(cond["short"])} biomarkers &amp; interventions</a>' if cond.get("interventions_url") else ""
    explorer_link = f'<a class="btn" href="/tools/repurposing-explorer.html#c={esc(rec["disease_slug"])}&amp;q={esc(agent)}">Open in Repurposing Explorer</a>'

    sib_html = ""
    others = [s for s in siblings if s["agent_slug"] != rec["agent_slug"]][:8]
    if others:
        sib_html = '<section class="block" id="related"><h2>Other candidates for ' + esc(disease) + '</h2><div class="card-list">' + "".join(
            f'<a class="card" href="{esc(s["pair_url"])}"><h3>{esc(s["agent_name"])}</h3><div class="muted">Tier {esc(s["tier"])} · {s["trial_breakdown"]["total"]} trials · {len(s["literature"])} publications · score {s["score"]}</div></a>'
            for s in others) + f'</div><p><a href="/pairs/{esc(rec["disease_slug"])}/">All {esc(disease)} pairs</a></p></section>'

    faq_html = "".join(f'<details class="faq"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in faq)
    score_doc = "".join(f"<li>{esc(s)}</li>" for s in SCORE_DOC)
    updated = rec["last_updated"] or TODAY

    # JSON-LD
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Research Tracker", "item": SITE + "/index.html"},
        {"@type": "ListItem", "position": 2, "name": "Disease × agent pairs", "item": SITE + "/pairs/"},
        {"@type": "ListItem", "position": 3, "name": cond["short"], "item": SITE + f"/pairs/{rec['disease_slug']}/"},
        {"@type": "ListItem", "position": 4, "name": agent, "item": url},
    ]}
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}
    cond_ld = {"@context": "https://schema.org", "@type": "MedicalCondition", "name": cond["name"], "url": SITE + cond["url"]}
    if cond.get("aliases"):
        cond_ld["alternateName"] = cond["aliases"][:6]
    if cond.get("mondo_id"):
        cond_ld["code"] = {"@type": "MedicalCode", "codeValue": cond["mondo_id"], "codingSystem": "MONDO"}
    agent_type_ld = {"Drug": "Drug", "Biologic": "Drug", "Supplement": "Substance", "Advanced therapy": "MedicalTherapy",
                     "Behavioural": "MedicalTherapy", "Device": "MedicalDevice", "Other": "MedicalTherapy"}[rec["agent_type"]]
    agent_ld = {"@context": "https://schema.org", "@type": agent_type_ld, "name": agent, "url": url}
    if rec["aliases"]:
        agent_ld["alternateName"] = rec["aliases"][:6]
    if rec["mechanism"] and agent_type_ld == "Drug":
        agent_ld["mechanismOfAction"] = rec["mechanism"][:200]
    if rec["chembl_id"]:
        agent_ld["code"] = {"@type": "MedicalCode", "codeValue": rec["chembl_id"], "codingSystem": "ChEMBL"}
    cites = [{"@type": "ScholarlyArticle", "identifier": f"PMID:{l['pmid']}", "url": l["url"]} for l in rec["literature"] if l["pmid"]][:10]
    if cites:
        agent_ld["citation"] = cites
    cond_ld["possibleTreatment"] = {"@type": agent_type_ld, "name": agent, "url": url}
    page_ld = {"@context": "https://schema.org", "@type": "MedicalWebPage", "name": title, "url": url,
               "description": description, "dateModified": updated,
               "about": [{"@type": "MedicalCondition", "name": cond["name"]}, {"@type": agent_type_ld, "name": agent}],
               "publisher": {"@type": "Organization", "name": "Open Source Medicine Foundation", "url": "https://opensourcemed.info"}}

    body = f"""
<body>
{nav('explorer')}
<header class="hero">
<div class="hero-inner">
<div class="hero-badge">Disease × agent evidence record</div>
<h1>{esc(agent)} for {esc(disease)}: evidence, trials and status</h1>
<p>{esc(what_evidence_shows(rec))}</p>
<div class="hero-meta">
<span><strong>{tb['total']}</strong> registered trials</span>
<span><strong>{tb['recruiting']}</strong> recruiting</span>
<span><strong>{n_lit}</strong> publications</span>
<span>Evidence tier <strong>{esc(rec['tier'])} · {esc(rec['tier_label'])}</strong></span>
<span>Score <strong>{rec['score']}</strong></span>
</div>
</div>
</header>
<div class="crumbs"><a href="/index.html">Research Tracker</a> › <a href="/pairs/">Pairs</a> › <a href="/pairs/{esc(rec['disease_slug'])}/">{esc(disease)}</a> › {esc(agent)}</div>
<main>
<div class="warn"><strong>Research map, not treatment advice.</strong> This page aggregates registry and literature records. It does not evaluate efficacy, dosing or safety for any individual. Discuss any treatment decision with a qualified clinician.</div>

<section class="block" id="summary">
<h2>Summary</h2>
<p class="lede">{esc(intro)}</p>
<p>{esc(disease_context(rec, cond))}</p>
<div class="links">{explorer_link}{agent_link}{cond_link}{interv_link}{ext}</div>
</section>

<section class="block" id="evidence">
<h2>Evidence table</h2>
<div class="table-wrap"><table><tbody>{ev_table}</tbody></table></div>
<details class="faq" style="margin-top:.75rem"><summary>How the evidence score is calculated</summary><ul class="score-parts">{score_doc}</ul></details>
</section>

<section class="block" id="trials">
<h2>Registered clinical trials</h2>
{trials_html}
<p class="muted">{('<a href="' + esc(ct_search) + '" target="_blank" rel="noopener">Search ClinicalTrials.gov for newer studies</a>') if ct_search else ''}</p>
</section>

<section class="block" id="literature">
<h2>Published literature</h2>
{lit_html}
<p class="muted">{('<a href="' + esc(pm_search) + '" target="_blank" rel="noopener">Run the live PubMed search</a>') if pm_search else ''}</p>
</section>

{notes_html}

<section class="block" id="faq">
<h2>Frequently asked questions</h2>
{faq_html}
</section>

{sib_html}

<section class="block" id="cite">
<h2>Cite this page</h2>
<div class="cite">Open Source Medicine Foundation. {esc(agent)} for {esc(disease)}: evidence, trials and status. OSMF Research Tracker. Updated {esc(updated)}. {esc(url)}</div>
<p class="muted">Data: ClinicalTrials.gov, PubMed, Open Targets, ChEMBL, DGIdb and the OSMF therapeutic agent database. Last updated {esc(updated)}. Page built {TODAY}.</p>
<p><a class="btn" href="{SUBSTACK}" rel="noopener">Get OSMF research updates on Substack</a></p>
</section>

<div class="warn">This is a research map, not treatment advice. Evidence tiers and scores summarise what has been studied, not whether a treatment works or is safe for you.</div>
</main>
{footer()}
</body>
</html>"""
    return head(title, description, url, [crumbs, faq_ld, cond_ld, agent_ld, page_ld]), body


def build_disease_index(cond: dict, recs: list) -> str:
    disease = cond["short"]
    url = SITE + f"/pairs/{cond['slug']}/"
    title = f"{disease}: candidate agents with trial or literature evidence"
    description = f"{len(recs)} disease-agent evidence pages for {disease}, each with registered trials, PubMed links and an evidence tier. OSMF drug repurposing research map."
    cards = "".join(
        f'<a class="card" href="{esc(r["pair_url"])}"><h3>{esc(r["agent_name"])}</h3><div class="muted">{esc(r["agent_type"])} · tier {esc(r["tier"])} · {r["trial_breakdown"]["total"]} trials ({r["trial_breakdown"]["recruiting"]} recruiting) · {len(r["literature"])} publications · score {r["score"]}</div></a>'
        for r in recs)
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Research Tracker", "item": SITE + "/index.html"},
        {"@type": "ListItem", "position": 2, "name": "Disease × agent pairs", "item": SITE + "/pairs/"},
        {"@type": "ListItem", "position": 3, "name": disease, "item": url}]}
    coll = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": url, "description": description,
            "about": {"@type": "MedicalCondition", "name": cond["name"]}}
    return head(title, description, url, [crumbs, coll], og_type="website") + f"""
<body>
{nav('explorer')}
<header class="hero"><div class="hero-inner"><div class="hero-badge">Disease × agent pairs</div>
<h1>{esc(disease)}: candidate agents with evidence</h1>
<p>{len(recs)} agents linked to {esc(cond['name'])} by at least one registered trial or two publications, ranked by the OSMF evidence score. Not treatment advice.</p></div></header>
<div class="crumbs"><a href="/index.html">Research Tracker</a> › <a href="/pairs/">Pairs</a> › {esc(disease)}</div>
<main>
<div class="links"><a class="btn" href="/tools/repurposing-explorer.html#c={esc(cond['slug'])}">Open {esc(disease)} in the Repurposing Explorer</a><a class="btn ghost" href="{esc(cond['url'])}">{esc(disease)} hub</a></div>
<input class="search" type="search" placeholder="Filter agents…" oninput="var q=this.value.toLowerCase();document.querySelectorAll('.card').forEach(function(c){{c.style.display=c.textContent.toLowerCase().indexOf(q)>-1?'':'none'}})">
<div class="card-list">{cards}</div>
<p class="muted" style="margin-top:1.5rem">Research map, not treatment advice. Built {TODAY}.</p>
</main>
{footer()}
</body></html>"""


def build_hub(conditions: dict, by_cond: dict, n_pages: int) -> str:
    url = SITE + "/pairs/"
    title = "Disease × agent evidence pages"
    description = f"{n_pages} pages pairing a candidate agent with a condition: registered trials, publications, evidence tier and repurposing status. Open Source Medicine Foundation."
    groups = defaultdict(list)
    for slug, recs in by_cond.items():
        c = conditions[slug]
        groups[c["category_label"]].append((c, recs))
    sections = []
    for cat in sorted(groups, key=lambda k: (k != "Post-Viral & Complex Chronic Illness", k)):
        items = sorted(groups[cat], key=lambda x: x[0]["short"].lower())
        cards = "".join(
            f'<a class="card" href="/pairs/{esc(c["slug"])}/"><h3>{esc(c["short"])}</h3><div class="muted">{len(recs)} agent pages · {sum(r["trial_breakdown"]["total"] for r in recs)} trials · {sum(len(r["literature"]) for r in recs)} publications</div></a>'
            for c, recs in items)
        sections.append(f'<section class="block"><h2>{esc(cat)}</h2><div class="card-list">{cards}</div></section>')
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Research Tracker", "item": SITE + "/index.html"},
        {"@type": "ListItem", "position": 2, "name": "Disease × agent pairs", "item": url}]}
    coll = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": url, "description": description}
    return head(title, description, url, [crumbs, coll], og_type="website") + f"""
<body>
{nav('explorer')}
<header class="hero"><div class="hero-inner"><div class="hero-badge">Drug repurposing research map</div>
<h1>Disease × agent evidence pages</h1>
<p>{n_pages} pages, one per condition-agent pair with at least one registered trial or two publications, across {len(by_cond)} conditions. Each page lists trials with NCT links, literature with PubMed links, an evidence tier and a transparent score.</p></div></header>
<div class="crumbs"><a href="/index.html">Research Tracker</a> › Pairs</div>
<main>
<div class="warn"><strong>Research map, not treatment advice.</strong> These pages summarise what has been studied, not what works.</div>
<div class="links"><a class="btn" href="/tools/repurposing-explorer.html">Open the interactive Repurposing Explorer</a><a class="btn ghost" href="/agents/">Agent hub pages</a></div>
{''.join(sections)}
<p class="muted">Built {TODAY}. Data from ClinicalTrials.gov, PubMed, Open Targets, ChEMBL, DGIdb and the OSMF therapeutic agent database.</p>
</main>
{footer()}
</body></html>"""


def main():
    dry = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    conditions, records = build_records(verbose=True)
    eligible = [r for r in records if r["pair_eligible"]]
    skipped_thin = [r for r in records if not r["pair_eligible"]]
    by_cond = defaultdict(list)
    for r in eligible:
        by_cond[r["disease_slug"]].append(r)

    written = 0
    noindexed = 0
    low_words = []
    for slug, recs in by_cond.items():
        cond = conditions[slug]
        recs.sort(key=lambda r: (-r["score"], r["agent_name"].lower()))
        d = OUT_DIR / slug
        if not dry:
            d.mkdir(parents=True, exist_ok=True)
        for r in recs:
            if limit and written >= limit:
                break
            head_html, body_html = build_pair_page(r, cond, recs)
            page = head_html + body_html
            res = thin_gate(page, min_words=MIN_WORDS, corpus_dir=None)
            has_registry = bool(re.search(r"NCT\d{8}", body_html))
            indexable = res.word_count >= MIN_WORDS and (res.has_citation or has_registry)
            if not indexable:
                page = head_html.replace('<meta name="robots" content="index,follow,max-image-preview:large">',
                                         '<meta name="robots" content="noindex,follow">') + body_html
                noindexed += 1
                if res.word_count < MIN_WORDS:
                    low_words.append((r["pair_url"], res.word_count))
            if not dry:
                (d / f"{r['agent_slug']}.html").write_text(page, encoding="utf-8")
            written += 1
        if not dry:
            (d / "index.html").write_text(build_disease_index(cond, recs), encoding="utf-8")

    if not dry:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "index.html").write_text(build_hub(conditions, by_cond, written), encoding="utf-8")

    print(f"Pair pages written: {written} across {len(by_cond)} conditions ({len(by_cond)} disease indexes + 1 hub)")
    print(f"Skipped as thin (no trial and <2 literature items): {len(skipped_thin)}")
    print(f"Noindexed (under {MIN_WORDS} prose words or no PMID/DOI/NCT citation): {noindexed}")
    if low_words:
        print("  lowest word counts:", sorted(low_words, key=lambda x: x[1])[:5])


if __name__ == "__main__":
    main()
