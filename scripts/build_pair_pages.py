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
/* Template B. Built on css/osmf-ui.css (loaded last by scripts/apply_osmf_ui.py);
   fallbacks keep the page readable without it. */
:root{--pp-wrap:1200px;--pp-gutter:clamp(16px,3.2vw,32px);--text-dark:var(--ui-ink,#0e1444);--text-mid:var(--ui-text,#3d4466);--text-light:var(--ui-muted,#6b7194);--border:var(--ui-line,#e6e8f2);--bg-light:var(--ui-bg-soft,#f7f8fc)}
*{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:var(--ui-font,'Inter',-apple-system,BlinkMacSystemFont,sans-serif);line-height:1.6;color:var(--text-mid);background:#fff}
a{color:var(--ui-link,#2f45c4)}
.hero-inner,.crumbs-inner{max-width:var(--pp-wrap);margin:0 auto;padding:0 var(--pp-gutter)}
.hero{padding:56px 0 52px}
.hero-badge{margin-bottom:18px}
.hero h1{font-size:clamp(30px,4.6vw,52px);margin:0 0 14px;max-width:24ch;overflow-wrap:anywhere}
.hero p{font-size:clamp(15.5px,1.6vw,18px);line-height:1.65;max-width:68ch}
.hero-meta{display:flex;flex-wrap:wrap;gap:18px 44px;margin-top:30px;padding-top:24px;border-top:1px solid rgba(255,255,255,.12)}
.hero-meta .pp-stat{display:grid;gap:6px}
.hero-meta .pp-stat b{font-family:var(--ui-display,Georgia,serif);font-weight:500;font-size:clamp(26px,3vw,36px);letter-spacing:-.02em;line-height:1;color:#fff}
.hero-meta .pp-stat span{font-size:11.5px;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:rgba(214,219,245,.75)}
.crumbs{padding:14px 0;border-bottom:1px solid var(--border);background:#fff}
.crumbs-inner{display:flex;flex-wrap:wrap;gap:4px 8px;align-items:center}
.crumbs .sep{color:var(--ui-faint,#9aa0bd)}
.crumbs .here{color:var(--ui-ink-2,#2a3160);font-weight:500}
main{max-width:var(--pp-wrap);margin:0 auto;padding:44px var(--pp-gutter) 8px}
section.block{margin:0 0 56px}
section.block > p{max-width:76ch}
h2{font-size:22px;font-weight:700;color:var(--text-dark);letter-spacing:-.015em;margin-bottom:14px}
h3{font-size:16px;color:var(--text-dark);margin:14px 0 6px}
p{margin:0 0 12px}
.lede{font-size:17px;line-height:1.7;color:var(--ui-ink-2,#2a3160)}
main > .warn{margin:0 0 40px}
main > .warn:last-child{margin:8px 0 0}
.callout{background:var(--bg-light);border:1px solid var(--border);border-radius:var(--ui-radius,14px);padding:16px 18px;margin:16px 0}
.table-wrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--border);border-radius:var(--ui-radius,14px);box-shadow:var(--ui-shadow-1);background:#fff;margin:0 0 12px}
.table-wrap table{width:100%;border-collapse:collapse;font-size:14px}
.table-wrap thead th{background:var(--bg-light);font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text-light);padding:11px 14px;text-align:left;border-bottom:1px solid var(--border);white-space:nowrap}
.table-wrap td,.table-wrap tbody th{padding:12px 14px;text-align:left;vertical-align:top;border-bottom:1px solid var(--border);color:var(--ui-ink-2,#2a3160);line-height:1.55}
.table-wrap tbody th[scope=row]{width:30%;min-width:150px;font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--text-light);background:var(--bg-light);border-right:1px solid var(--border)}
.table-wrap tr:last-child td,.table-wrap tr:last-child th{border-bottom:0}
.table-wrap table.pp-trials{min-width:720px}
.pp-trials td:first-child{white-space:nowrap;font-family:var(--ui-mono,ui-monospace,monospace);font-size:13px;font-weight:600}
.pp-trials td:nth-child(3),.pp-trials td:nth-child(4){white-space:nowrap}
.pp-trials td:nth-child(5),.pp-trials th:nth-child(5){text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.tag{display:inline-flex;align-items:center;font-size:12px;font-weight:650;padding:3px 10px;border-radius:999px;border:1px solid var(--border);background:var(--bg-light);color:var(--ui-ink-2,#2a3160);white-space:nowrap;line-height:1.4}
.tag.rec{background:var(--ui-ok-bg,#e7f7f0);color:var(--ui-ok,#047857);border-color:#bfe9d6}
.tag.act{background:var(--ui-down-bg,#eaf0ff);color:var(--ui-down,#1d4ed8);border-color:#cfdcff}
.tag.done{background:var(--bg-light);color:var(--ui-ink-2,#2a3160)}
.tag.off{background:var(--ui-up-bg,#fff1e8);color:var(--ui-up,#c2410c);border-color:#ffd9c2}
.tag.tier-A{background:var(--ui-ok-bg,#e7f7f0);color:var(--ui-ok,#047857);border-color:#bfe9d6}
.tag.tier-B{background:var(--ui-down-bg,#eaf0ff);color:var(--ui-down,#1d4ed8);border-color:#cfdcff}
.tag.tier-C{background:var(--ui-warn-bg,#fff7df);color:var(--ui-warn,#a16207);border-color:#f5e0a3}
.tag.tier-D{background:var(--bg-light);color:var(--text-light)}
ul.refs{list-style:none;padding:0;margin:0 0 12px;background:#fff;border:1px solid var(--border);border-radius:var(--ui-radius,14px);box-shadow:var(--ui-shadow-1)}
ul.refs li{padding:14px 18px;border-top:1px solid var(--border);font-size:14.5px;line-height:1.55;color:var(--ui-ink-2,#2a3160);overflow-wrap:anywhere}
ul.refs li:first-child{border-top:0}
ul.refs li .tag{margin-right:6px;font-size:11px;padding:2px 8px;vertical-align:1px}
ul.refs li .muted{margin-top:4px}
.muted{color:var(--text-light);font-size:13px}
details.faq{border:1px solid var(--border);border-radius:12px;background:#fff;margin:10px 0;padding:0 18px;box-shadow:var(--ui-shadow-1);max-width:880px}
details.faq summary{cursor:pointer;padding:15px 0;font-weight:600;color:var(--text-dark);list-style:none;display:flex;align-items:center;gap:12px}
details.faq summary::-webkit-details-marker{display:none}
details.faq summary::before{content:"";width:8px;height:8px;flex:none;border-right:2px solid var(--ui-accent-2,#f2711c);border-bottom:2px solid var(--ui-accent-2,#f2711c);transform:rotate(-45deg);transition:transform .2s}
details.faq[open] summary::before{transform:rotate(45deg)}
details.faq p{margin:0 0 16px;color:var(--text-mid);line-height:1.7}
details.faq .score-parts{margin:0 0 16px;padding-left:20px}
.cite{font-family:var(--ui-mono,ui-monospace,monospace);font-size:13px;line-height:1.65;background:var(--bg-light);border:1px solid var(--border);border-radius:12px;padding:14px 16px;overflow-wrap:anywhere;color:var(--ui-ink-2,#2a3160);margin:0 0 12px;max-width:880px}
.btn{display:inline-flex;align-items:center;background:linear-gradient(180deg,#ffa31a,var(--ui-accent-2,#f2711c));color:#fff;text-decoration:none;font-weight:650;padding:9px 16px;border-radius:999px;font-size:14px;box-shadow:0 6px 16px rgba(242,113,28,.25);border:0}
.btn:hover{box-shadow:0 10px 22px rgba(242,113,28,.32)}
.btn.ghost{background:#fff;color:var(--ui-ink,#0e1444);border:1px solid var(--ui-line-2,#d5d9ea);box-shadow:none;font-weight:600}
.btn.ghost:hover{background:var(--bg-light);border-color:#c4c9e0}
.links{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0 0}
main > .links{margin:0 0 8px}
main > .links + section.block{margin-top:44px}
.score-parts{font-size:14px;color:var(--text-mid)}
.score-parts li{margin:6px 0;line-height:1.6}
.card-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px;margin:0 0 14px}
.card{border:1px solid var(--border);border-radius:var(--ui-radius,14px);padding:18px 20px;background:#fff;text-decoration:none;color:inherit;display:block;box-shadow:var(--ui-shadow-1);transition:transform .2s,box-shadow .2s,border-color .2s;min-width:0}
.card:hover{transform:translateY(-2px);box-shadow:var(--ui-shadow-2);border-color:var(--ui-line-2,#d5d9ea)}
.card h3{margin:0 0 6px;font-size:16px;font-weight:650;color:var(--text-dark);letter-spacing:-.01em;overflow-wrap:anywhere}
.card .muted{line-height:1.55}
.search{width:100%;max-width:520px;font:inherit;font-size:15px;color:var(--text-dark);border:1px solid var(--ui-line-2,#d5d9ea);border-radius:12px;padding:11px 14px 11px 40px;min-height:46px;margin:28px 0 22px;background:#fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%236b7194' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='M20 20l-3.5-3.5'/%3E%3C/svg%3E") no-repeat 14px center;display:block}
.search:focus{outline:none;border-color:#8090ea;box-shadow:0 0 0 4px rgba(47,69,196,.12)}
@media (max-width:640px){.hero{padding:40px 0 38px}.hero-meta{gap:16px 28px}section.block{margin-bottom:44px}.table-wrap tbody th[scope=row]{min-width:120px}}
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
        trials_html = f"""<div class="table-wrap"><table class="pp-trials">
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
<nav class="crumbs osmf-crumbs" aria-label="Breadcrumb"><div class="crumbs-inner"><a href="/index.html">Research Tracker</a><span class="sep" aria-hidden="true">›</span><a href="/pairs/">Pairs</a><span class="sep" aria-hidden="true">›</span><a href="/pairs/{esc(rec['disease_slug'])}/">{esc(disease)}</a><span class="sep" aria-hidden="true">›</span><span class="here" aria-current="page">{esc(agent)}</span></div></nav>
<header class="hero">
<div class="hero-inner">
<div class="hero-badge">Disease × agent evidence record</div>
<h1>{esc(agent)} for {esc(disease)}: evidence, trials and status</h1>
<p>{esc(what_evidence_shows(rec))}</p>
<div class="hero-meta">
<div class="pp-stat"><b>{tb['total']}</b><span>registered trials</span></div>
<div class="pp-stat"><b>{tb['recruiting']}</b><span>recruiting</span></div>
<div class="pp-stat"><b>{n_lit}</b><span>publications</span></div>
<div class="pp-stat"><b>{esc(rec['tier'])}</b><span>Evidence tier · {esc(rec['tier_label'])}</span></div>
<div class="pp-stat"><b>{rec['score']}</b><span>Score</span></div>
</div>
</div>
</header>
<main>
<div class="warn osmf-callout"><strong>Research map, not treatment advice.</strong> This page aggregates registry and literature records. It does not evaluate efficacy, dosing or safety for any individual. Discuss any treatment decision with a qualified clinician.</div>

<section class="block" id="summary">
<h2>Summary</h2>
<p class="lede">{esc(intro)}</p>
<p>{esc(disease_context(rec, cond))}</p>
<div class="links">{explorer_link}{agent_link}{cond_link}{interv_link}{ext}</div>
</section>

<section class="block" id="evidence">
<h2>Evidence table</h2>
<div class="table-wrap"><table><tbody>{ev_table}</tbody></table></div>
<details class="faq" style="margin-top:14px"><summary>How the evidence score is calculated</summary><ul class="score-parts">{score_doc}</ul></details>
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

<div class="warn osmf-callout">This is a research map, not treatment advice. Evidence tiers and scores summarise what has been studied, not whether a treatment works or is safe for you.</div>
</main>
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
<nav class="crumbs osmf-crumbs" aria-label="Breadcrumb"><div class="crumbs-inner"><a href="/index.html">Research Tracker</a><span class="sep" aria-hidden="true">›</span><a href="/pairs/">Pairs</a><span class="sep" aria-hidden="true">›</span><span class="here" aria-current="page">{esc(disease)}</span></div></nav>
<header class="hero"><div class="hero-inner"><div class="hero-badge">Disease × agent pairs</div>
<h1>{esc(disease)}: candidate agents with evidence</h1>
<p>{len(recs)} agents linked to {esc(cond['name'])} by at least one registered trial or two publications, ranked by the OSMF evidence score. Not treatment advice.</p></div></header>
<main>
<div class="links"><a class="btn" href="/tools/repurposing-explorer.html#c={esc(cond['slug'])}">Open {esc(disease)} in the Repurposing Explorer</a><a class="btn ghost" href="{esc(cond['url'])}">{esc(disease)} hub</a></div>
<input class="search" type="search" placeholder="Filter agents…" oninput="var q=this.value.toLowerCase();document.querySelectorAll('.card').forEach(function(c){{c.style.display=c.textContent.toLowerCase().indexOf(q)>-1?'':'none'}})">
<div class="card-list">{cards}</div>
<p class="muted" style="margin-top:28px">Research map, not treatment advice. Built {TODAY}.</p>
</main>
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
<nav class="crumbs osmf-crumbs" aria-label="Breadcrumb"><div class="crumbs-inner"><a href="/index.html">Research Tracker</a><span class="sep" aria-hidden="true">›</span><span class="here" aria-current="page">Pairs</span></div></nav>
<header class="hero"><div class="hero-inner"><div class="hero-badge">Drug repurposing research map</div>
<h1>Disease × agent evidence pages</h1>
<p>{n_pages} pages, one per condition-agent pair with at least one registered trial or two publications, across {len(by_cond)} conditions. Each page lists trials with NCT links, literature with PubMed links, an evidence tier and a transparent score.</p></div></header>
<main>
<div class="warn osmf-callout"><strong>Research map, not treatment advice.</strong> These pages summarise what has been studied, not what works.</div>
<div class="links"><a class="btn" href="/tools/repurposing-explorer.html">Open the interactive Repurposing Explorer</a><a class="btn ghost" href="/agents/">Agent hub pages</a></div>
{''.join(sections)}
<p class="muted">Built {TODAY}. Data from ClinicalTrials.gov, PubMed, Open Targets, ChEMBL, DGIdb and the OSMF therapeutic agent database.</p>
</main>
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
