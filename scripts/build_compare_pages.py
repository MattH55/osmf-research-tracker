#!/usr/bin/env python3
"""Build programmatic condition-comparison pages: compare/<a>-vs-<b>.html + compare/index.html.

Run from the repo root:  python scripts/build_compare_pages.py
Idempotent: regenerates every page from data/ on each run.

Inputs (read-only):
  data/biomarkers/<slug>.json            biomarker atlases (post-viral set)
  data/<key>.json                        PubMed literature feeds
  data/clinical_trials/clinical_trials_current.json
  data/cohorts/*.json                    PAIS cohort database
  data/therapeutic_agents.json, data/disease-agent-pairs.json
  data/vocab/agent-slugs.json            (optional) for /agents/<slug>.html links
Outputs:
  compare/<a>-vs-<b>.html, compare/index.html
Does NOT touch sitemap.xml, workflows or atlas pages.
"""
from __future__ import annotations

import datetime as dt
import glob
import html
import itertools
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "compare")
SITE = "https://research.opensourcemed.info"
SUBSTACK = "https://opensourcemed.substack.com/subscribe?utm_source=tracker"
GA_ID = "G-202S9N21TE"
TODAY = dt.date.today().isoformat()

# --------------------------------------------------------------------------------------
# Condition registry
# --------------------------------------------------------------------------------------
POST_VIRAL = ["long-covid", "me-cfs", "pacvs", "lyme", "gulf-war-illness"]
LIT_ONLY = ["pots", "mcas"]

CONDITIONS = {
    "long-covid": dict(
        name="Long COVID", short="Long COVID", alt=["PASC", "Post-Acute Sequelae of COVID-19", "Post-COVID-19 condition"],
        lit="long-covid", feed="long-covid.html", atlas="long-covid-biomarkers.html",
        trial_mapped="Long COVID / PASC", trial_re=None,
        cohort_pathogens={"sars-cov-2"}, cohort_name_re=r"long covid|covid-19|pasc|phosp",
        agent_cond={"Long COVID"},
        blurb=("Long COVID describes symptoms that persist or emerge more than three months after SARS-CoV-2 infection and "
               "cannot be explained by another diagnosis. The World Health Organization calls it post-COVID-19 condition; "
               "the US National Institutes of Health uses the term PASC. Common features include fatigue, post-exertional "
               "symptom exacerbation, cognitive difficulties, orthostatic intolerance, breathlessness and chest pain. "
               "Because the triggering infection is known and recent, Long COVID has attracted large prospective cohorts "
               "(RECOVER, PHOSP-COVID) and the largest clinical-trial pipeline of any post-infectious illness."),
    ),
    "me-cfs": dict(
        name="Myalgic Encephalomyelitis / Chronic Fatigue Syndrome", short="ME/CFS", alt=["ME/CFS", "CFS", "ME", "Systemic Exertion Intolerance Disease"],
        lit="me-cfs", feed="me-cfs.html", atlas="me-cfs-biomarkers.html",
        trial_mapped="ME/CFS", trial_re=None,
        cohort_pathogens={"unknown-trigger"}, cohort_name_re=r"me/cfs|chronic fatigue|decodeme",
        agent_cond={"ME/CFS"},
        blurb=("ME/CFS is a chronic, multi-system illness defined clinically by a substantial reduction in activity, "
               "post-exertional malaise (PEM), unrefreshing sleep and either cognitive impairment or orthostatic "
               "intolerance. It frequently begins after an infection, including mononucleosis (EBV), SARS, Q fever, "
               "Ross River virus and now SARS-CoV-2, but many cases have no identified trigger. There is no validated "
               "diagnostic test; research biomarkers centre on energy metabolism, immune signalling and autonomic function."),
    ),
    "pacvs": dict(
        name="Post-Acute COVID-19 Vaccination Syndrome", short="PACVS", alt=["PACVS", "PCVS", "Post-Vac Syndrome", "Post-vaccination syndrome"],
        lit="pacvs", feed="pacvs.html", atlas="pacvs-biomarkers.html",
        trial_mapped=None, trial_re=r"vaccination syndrome|post[- ]vac|vaccine injur|post-acute covid-19 vaccination|pacvs|pcvs",
        cohort_pathogens={"covid-19-vaccine"}, cohort_name_re=r"pacvs|post-vac|covid[- ]?19 vaccin|post-vaccination syndrome",
        agent_cond={"PACVS"},
        blurb=("PACVS (also written PCVS or post-vac syndrome) refers to persistent, Long COVID-like symptoms that begin "
               "shortly after SARS-CoV-2 vaccination and last for months in a small subset of recipients. It is not a "
               "recognised diagnostic entity in most countries and is defined differently across the handful of registry "
               "and survey cohorts that exist (Marburg, Yale LISTEN, VITAE). Research is early-stage: the literature is "
               "small, the biomarker evidence comes mainly from case series, and only a few interventional studies are registered."),
    ),
    "lyme": dict(
        name="Lyme Disease", short="Lyme disease", alt=["Lyme borreliosis", "Borrelia burgdorferi infection", "Post-treatment Lyme disease syndrome (PTLDS)", "Chronic Lyme"],
        lit="lyme", feed="lyme.html", atlas="lyme-biomarkers.html",
        trial_mapped=None, trial_re=r"\blyme\b|borrel|ptlds|post-tick",
        cohort_pathogens={"borrelia-burgdorferi"}, cohort_name_re=r"lyme|ptlds|borrel",
        agent_cond={"Lyme"},
        blurb=("Lyme disease is a tick-borne bacterial infection caused by Borrelia burgdorferi and related species. "
               "Early disease is diagnosed by the erythema migrans rash and two-tier serology, and treated with "
               "antibiotics. A minority of treated patients develop post-treatment Lyme disease syndrome (PTLDS): "
               "fatigue, musculoskeletal pain and cognitive symptoms lasting six months or longer. The OSMF literature "
               "feed for this condition focuses on the chronic and post-treatment phase, while the biomarker atlas spans "
               "acute serology through neuroborreliosis and persistent-symptom phenotypes."),
    ),
    "gulf-war-illness": dict(
        name="Gulf War Illness", short="Gulf War Illness", alt=["GWI", "Gulf War Syndrome", "Chronic Multisymptom Illness"],
        lit="gulf-war-illness", feed="gulf-war-illness.html", atlas="gulf-war-illness-biomarkers.html",
        trial_mapped=None, trial_re=r"gulf war|persian gulf",
        cohort_pathogens=set(), cohort_name_re=r"gulf war",
        agent_cond={"Gulf War Illness"},
        blurb=("Gulf War Illness is a chronic multisymptom condition affecting roughly a quarter to a third of the "
               "nearly 700,000 US and allied personnel deployed in the 1990-1991 Gulf War. It is defined by the Kansas "
               "or CDC criteria (fatigue, pain, cognitive and mood symptoms, gastrointestinal and respiratory complaints) "
               "rather than by a single exposure, though pyridostigmine bromide, pesticides and low-level nerve agents are "
               "the leading hypotheses. Unlike the other conditions compared here it has no infectious trigger, which makes "
               "its biomarker overlap with post-viral syndromes scientifically interesting."),
    ),
    "pots": dict(
        name="Postural Orthostatic Tachycardia Syndrome", short="POTS", alt=["POTS", "Postural tachycardia syndrome", "Dysautonomia"],
        lit="pots", feed="pots.html", atlas=None,
        trial_mapped=None, trial_re=r"postural (orthostatic )?tachycardia|\bpots\b",
        cohort_pathogens=set(), cohort_name_re=r"\bpots\b|postural",
        agent_cond={"POTS"},
        blurb=("POTS is a disorder of the autonomic nervous system defined by a sustained heart-rate rise of at least "
               "30 beats per minute (40 in adolescents) within ten minutes of standing, without orthostatic hypotension, "
               "together with chronic orthostatic symptoms. It is a diagnosis made by tilt-table or active-stand testing "
               "rather than a blood test. POTS commonly follows infection, including COVID-19, and overlaps heavily with "
               "ME/CFS and Long COVID; OSMF tracks it through a literature feed and clinical-trial registry rather than a "
               "dedicated biomarker atlas."),
    ),
    "mcas": dict(
        name="Mast Cell Activation Syndrome", short="MCAS", alt=["MCAS", "Mast cell activation disorder"],
        lit="mcas", feed="mcas.html", atlas=None,
        trial_mapped=None, trial_re=r"mast cell activation",
        cohort_pathogens=set(), cohort_name_re=r"mast cell|mcas",
        agent_cond={"MCAS"},
        blurb=("MCAS is characterised by episodic, multi-system symptoms (flushing, hives, gastrointestinal upset, "
               "wheeze, hypotension) caused by inappropriate release of mast-cell mediators, with laboratory evidence such "
               "as a rise in serum tryptase during an episode and a response to mast-cell-directed therapy. Diagnostic "
               "criteria remain contested between consensus groups. MCAS is frequently reported alongside POTS, "
               "hypermobility and post-infectious illness; OSMF follows it through a literature feed and clinical-trial "
               "registry rather than a dedicated biomarker atlas."),
    ),
}

# Hand-written relationship notes: why this particular pair is worth comparing.
PAIR_NOTES = {
    ("long-covid", "me-cfs"): "Roughly half of people with Long COVID lasting more than six months meet ME/CFS criteria, and the two conditions share post-exertional malaise as a defining feature. Much of the ME/CFS research community has reoriented toward Long COVID cohorts because the trigger and onset date are known, so findings flow in both directions.",
    ("long-covid", "pacvs"): "Both syndromes are attributed to exposure to the SARS-CoV-2 spike protein, by infection in one case and by vaccination in the other, and patients describe overlapping symptom clusters. The evidence base is radically asymmetric: Long COVID has hundreds of registered trials and thousands of papers; PACVS has a handful of each.",
    ("long-covid", "lyme"): "Post-treatment Lyme disease syndrome was, before 2020, the best-studied example of persistent symptoms after a treated infection. Comparing it with Long COVID tests whether a bacterial and a viral trigger converge on similar inflammatory and autonomic signatures.",
    ("long-covid", "gulf-war-illness"): "Gulf War Illness is the main chronic multisymptom illness without an infectious trigger, so it is the natural control case for asking which Long COVID biomarkers reflect persistent infection and which reflect a generic post-insult state.",
    ("me-cfs", "pacvs"): "PACVS cohorts report high rates of post-exertional malaise and fatigue, and some registries explicitly apply ME/CFS criteria. The comparison asks whether a vaccine-triggered syndrome follows the same immunometabolic track as classical ME/CFS.",
    ("me-cfs", "lyme"): "Persistent fatigue after treated Lyme disease is one of the historical arguments for an infectious origin of ME/CFS, and some PTLDS patients meet ME/CFS case definitions. Diagnostic serology exists for Lyme but not for ME/CFS, which shapes the biomarker tables below.",
    ("me-cfs", "gulf-war-illness"): "GWI and ME/CFS have been compared head-to-head in VA-funded studies for decades, sharing fatigue, pain, cognitive symptoms and reported mitochondrial and cholinergic abnormalities. Several registered GWI trials recruit under a chronic fatigue syndrome label.",
    ("pacvs", "lyme"): "Both conditions sit at the contested edge of medicine: persistent symptoms after a treated bacterial infection on one side and after vaccination on the other. Each has an established trigger but no accepted biomarker for the chronic phase.",
    ("pacvs", "gulf-war-illness"): "Both are exposure-attributed syndromes rather than infections: GWI to deployment-related chemicals and vaccines, PACVS to a vaccine. Autoimmune and autonomic markers appear in both literatures, which is the main reason to look at them side by side.",
    ("lyme", "gulf-war-illness"): "A tick-borne bacterial infection and a deployment-related exposure syndrome have little in common aetiologically, but both produce a chronic fatigue-pain-cognition phenotype and both have mature VA or NIH research programmes with long follow-up.",
    ("long-covid", "pots"): "POTS is one of the most frequent objectively confirmed diagnoses in Long COVID clinics, and most registered POTS trials in the OSMF registry now recruit post-COVID patients. The comparison is between a syndrome and one of its measurable phenotypes.",
    ("me-cfs", "pots"): "Orthostatic intolerance is part of the ME/CFS case definition, and many ME/CFS patients meet POTS criteria on tilt testing. Autonomic biomarkers in the ME/CFS atlas are the point of contact.",
    ("pacvs", "pots"): "Post-vaccination syndrome cohorts frequently report new-onset tachycardia and orthostatic intolerance, and some PACVS case series centre on POTS. Both have small evidence bases.",
    ("lyme", "pots"): "Autonomic dysfunction including POTS has been described after Lyme disease, and a trial of mast-cell therapy for post-tick-bite illness is registered. The overlap is narrower than for the viral syndromes.",
    ("gulf-war-illness", "pots"): "Autonomic abnormalities, including blunted heart-rate variability and orthostatic symptoms, are a recurring finding in GWI, which makes POTS a relevant phenotype to compare even though no GWI-specific POTS trials exist.",
    ("long-covid", "mcas"): "Mast-cell activation has been proposed as one mechanism of Long COVID, and antihistamines and mast-cell stabilisers are among the agents under investigation. Tryptase and histamine-pathway markers link the two literatures.",
    ("me-cfs", "mcas"): "MCAS is commonly diagnosed alongside ME/CFS, and some clinicians treat the two as part of one hypermobility-dysautonomia-mast cell cluster. The evidence that mast cells drive ME/CFS symptoms is still largely observational.",
    ("pacvs", "mcas"): "Mast-cell activation is one of several proposed mechanisms for post-vaccination syndrome, and antihistamine protocols are used empirically. Both conditions lack a consensus case definition.",
    ("lyme", "mcas"): "A registered trial of mast-cell treatment for post-tick-bite illness is the most direct link between these conditions; otherwise the connection rests on case reports of MCAS following Lyme disease.",
    ("gulf-war-illness", "mcas"): "There is little direct research connecting GWI and MCAS; the comparison is offered because both involve immune dysregulation with a chronic multisystem phenotype, and because readers searching for one often ask about the other.",
}

GREEK = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "κ": "kappa", "λ": "lambda", "μ": "mu",
         "ω": "omega", "σ": "sigma", "τ": "tau", "θ": "theta", "π": "pi", "ρ": "rho", "ζ": "zeta", "η": "eta", "ν": "nu", "ξ": "xi",
         "Α": "alpha", "Β": "beta", "Γ": "gamma", "Δ": "delta", "Ω": "omega", "Σ": "sigma", "Θ": "theta"}


def transliterate(s: str) -> str:
    s = "".join(GREEK.get(ch, ch) for ch in s)
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def marker_slug(name: str) -> str:
    """lowercase ASCII hyphenated, Greek transliterated, parentheses stripped."""
    s = transliterate(name).replace("≥", "ge").replace("≤", "le").lower()
    s = re.sub(r"[()\[\]]", "", s).replace("'", "").replace("’", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", transliterate(s).lower())


def marker_keys(m: dict) -> set:
    """Normalised keys for matching: full name, parenthetical abbreviation, base name, LOINC."""
    keys = set()
    name = m.get("name") or ""
    keys.add(norm_key(name))
    base = re.sub(r"\(.*?\)", "", name).strip()
    if base:
        keys.add(norm_key(base))
    for par in re.findall(r"\(([^)]+)\)", name):
        par = par.strip()
        # Only abbreviation-like parentheticals (e.g. "IL-6", "TNF-α", "CXCL8"); skip descriptors like "(composite)", "(plasma)".
        if 2 <= len(par) <= 14 and re.search(r"[A-Z0-9]", par) and not re.search(r"\s", par) and par.lower() not in ("composite", "panel", "plasma", "serum"):
            keys.add(norm_key(par))
    if m.get("loinc"):
        keys.add("loinc:" + str(m["loinc"]).strip())
    keys.discard("")
    return keys


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def fmt_date(s) -> str:
    if not s:
        return "n/a"
    try:
        return dt.date.fromisoformat(str(s)[:10]).strftime("%d %b %Y")
    except ValueError:
        return str(s)[:10]


def load_json(rel: str):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------------------
def load_all():
    data = {}
    for slug, c in CONDITIONS.items():
        d = {"slug": slug, **c}
        bm = load_json(f"data/biomarkers/{slug}.json")
        d["biomarkers"] = bm
        d["markers"] = (bm or {}).get("markers", []) if bm else []
        d["hero"] = ((bm or {}).get("page") or {}).get("hero") if bm else None
        d["atlas_modified"] = ((bm or {}).get("page") or {}).get("dateModified") if bm else None
        if bm and bm.get("condition"):
            d["alt"] = list(dict.fromkeys(bm["condition"].get("alternateNames", []) + c["alt"]))
        lit = load_json(f"data/{c['lit']}.json") or {}
        studies = [s for s in lit.get("studies", []) if s.get("pmid")]
        studies.sort(key=lambda s: s.get("pub_date") or "", reverse=True)
        d["studies"] = studies
        d["lit_updated"] = lit.get("last_updated")
        data[slug] = d

    trials_doc = load_json("data/clinical_trials/clinical_trials_current.json") or {"trials": []}
    trials = trials_doc.get("trials", [])
    for slug, d in data.items():
        mine = []
        for t in trials:
            hit = False
            if d["trial_mapped"] and d["trial_mapped"] in (t.get("mapped_conditions") or []):
                hit = True
            elif d["trial_re"]:
                hay = " | ".join((t.get("conditions_raw") or []) + [t.get("title") or ""]).lower()
                hit = re.search(d["trial_re"], hay) is not None
            if hit:
                mine.append(t)
        d["trials"] = mine
        d["trials_updated"] = trials_doc.get("last_run")

    cohorts = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "cohorts", "*.json"))):
        with open(p, encoding="utf-8") as f:
            cohorts.append(json.load(f))
    for slug, d in data.items():
        d["cohorts"] = [c for c in cohorts if (c.get("pathogen_id") in d["cohort_pathogens"]) or
                        re.search(d["cohort_name_re"], (c.get("name") or "") + " " + " ".join(c.get("aliases") or []), re.I)]

    agents_doc = load_json("data/therapeutic_agents.json") or {"agents": []}
    agent_slug_map = {}
    for rec in load_json("data/vocab/agent-slugs.json") or []:
        agent_slug_map[rec.get("display_name", "").strip().lower()] = rec.get("slug")
    flagged = {r.get("display_name", "").strip().lower() for r in load_json("data/vocab/agent-slugs-flagged.json") or []}
    noise_re = re.compile(
        r"intervention group|treatment as usual|usual care|standard (of )?care|placebo|\bcontrol\b|follow[- ]up|phone call|"
        r"transfer package|wearable device|no intervention|\bsham\b|questionnaire|\d+\s?mg\b|extension for community|"
        r"^to\b|measure|levels of|effect on|challenge|\bscore\b|compass|assessment|\bscale\b|^cytokines?$|^il-?\d+$|"
        r"microcrystalline cellulose|^group\b|\barm\b|data collection|blood (draw|sample)", re.I)

    def clean_agent(name: str):
        n = re.sub(r"\s+", " ", (name or "")).strip().rstrip(".").strip()
        if not n or len(n) > 60 or n.lower() in flagged or noise_re.search(n):
            return None
        return n

    for slug, d in data.items():
        names = set()
        for a in agents_doc.get("agents", []):
            if d["agent_cond"] & set(a.get("Primary Conditions") or []):
                names.add(a["Therapeutic Agent"].strip())
        for t in d["trials"]:
            for a in t.get("agents") or []:
                if a and a.strip():
                    names.add(a.strip())
        cleaned = {}
        for n in names:
            c = clean_agent(n)
            if c:
                cleaned.setdefault(c.lower(), c)
        d["agents"] = set(cleaned.values())
    # disease-agent-pairs: only applies if a pair's disease_slug matches one of ours (currently none do, kept for forward compat)
    pairs = load_json("data/disease-agent-pairs.json") or []
    slug_to_agent = {v: k for k, v in agent_slug_map.items()}
    for p in pairs:
        if p.get("disease_slug") in data and p.get("agent_slug") in slug_to_agent:
            data[p["disease_slug"]]["agents"].add(slug_to_agent[p["agent_slug"]].title())
    return data, agent_slug_map


# --------------------------------------------------------------------------------------
# Analysis helpers
# --------------------------------------------------------------------------------------
STATUS_GROUPS = [
    ("Recruiting / not yet recruiting", {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"}),
    ("Active, not recruiting", {"ACTIVE_NOT_RECRUITING"}),
    ("Completed", {"COMPLETED"}),
    ("Terminated / withdrawn / suspended", {"TERMINATED", "WITHDRAWN", "SUSPENDED"}),
    ("Unknown status", {"UNKNOWN"}),
]


def trial_status_counts(trials):
    c = Counter((t.get("status") or "UNKNOWN").upper() for t in trials)
    out = []
    for label, statuses in STATUS_GROUPS:
        out.append((label, sum(c[s] for s in statuses)))
    return out


def active_trial_count(trials):
    return sum(1 for t in trials if (t.get("status") or "").upper() in {"RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"})


def shared_markers(ma, mb):
    """Return list of (marker_a, marker_b, match_basis) and the sets of matched indices."""
    index_b = defaultdict(list)
    for j, m in enumerate(mb):
        for k in marker_keys(m):
            index_b[k].append(j)
    shared, used_a, used_b = [], set(), set()
    for i, m in enumerate(ma):
        for k in sorted(marker_keys(m), key=lambda x: (not x.startswith("loinc:"), -len(x))):
            cands = [j for j in index_b.get(k, []) if j not in used_b]
            if cands:
                j = cands[0]
                basis = "LOINC " + k[6:] if k.startswith("loinc:") else "name"
                shared.append((m, mb[j], basis))
                used_a.add(i)
                used_b.add(j)
                break
    return shared, used_a, used_b


def direction_label(d):
    return {"up": "Increased", "down": "Decreased", "mixed": "Mixed / conflicting"}.get((d or "").lower(), d or "n/a")


def direction_badge(d):
    d = (d or "").lower()
    cls = {"up": "up", "down": "down", "mixed": "mixed"}.get(d, "na")
    return f'<span class="dir dir-{cls}">{esc(direction_label(d))}</span>'


# --------------------------------------------------------------------------------------
# HTML building blocks
# --------------------------------------------------------------------------------------
CSS = """
:root{--blue:#0068f8;--blue-dark:#0052c7;--ink:#111827;--muted:#4b5563;--line:#e5e7eb;--bg2:#f8fafc;--bg:#ffffff;--amber-bg:#fff7ed;--amber:#c2410c;--green:#15803d;--red:#b91c1c}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--ink:#f3f4f6;--muted:#9ca3af;--line:#1f2937;--bg2:#111827;--bg:#0b1220;--amber-bg:#2a1a0a;--amber:#fdba74;--green:#4ade80;--red:#fca5a5}}
:root[data-theme="dark"]{--ink:#f3f4f6;--muted:#9ca3af;--line:#1f2937;--bg2:#111827;--bg:#0b1220;--amber-bg:#2a1a0a;--amber:#fdba74;--green:#4ade80;--red:#fca5a5}
*{box-sizing:border-box}html{overflow-x:clip}
body{margin:0;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif;font-size:16px;line-height:1.6;color:var(--ink);background:var(--bg)}
a{color:var(--blue)}a:hover{color:var(--blue-dark)}
.nav{border-bottom:1px solid var(--line);background:var(--bg)}
.nav .in{max-width:1100px;margin:0 auto;padding:.75rem 16px;display:flex;flex-wrap:wrap;gap:.5rem 1.25rem;align-items:center}
.nav .brand{font-weight:700;text-decoration:none;color:var(--ink)}.nav a.l{text-decoration:none;color:var(--muted);font-size:.9rem}.nav a.l:hover{color:var(--blue)}
main{max-width:1100px;margin:0 auto;padding:0 16px 3rem}
.bc{font-size:.85rem;color:var(--muted);margin:1rem 0}.bc a{text-decoration:none}.bc ol{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:.35rem}.bc li+li::before{content:"\\203A";margin-right:.35rem}
h1{font-size:clamp(1.6rem,4vw,2.4rem);line-height:1.2;margin:.5rem 0 .75rem}
h2{font-size:1.45rem;margin:2.5rem 0 .75rem;padding-top:.5rem;border-top:1px solid var(--line)}
h3{font-size:1.1rem;margin:1.5rem 0 .5rem}
.lede{font-size:1.1rem;color:var(--muted);max-width:60rem}
.pill{display:inline-block;font-size:.75rem;font-weight:600;padding:.15rem .6rem;border-radius:999px;background:var(--amber-bg);color:var(--amber);margin-left:.5rem;vertical-align:middle}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.25rem}
.card{border:1px solid var(--line);border-radius:10px;padding:1rem 1.25rem;background:var(--bg2)}
.card h3{margin-top:0}.card .alt{font-size:.85rem;color:var(--muted)}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:1rem 0}
table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{text-align:left;padding:.5rem .65rem;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--bg2);font-weight:600}
thead th{position:sticky;top:0}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.dir{display:inline-block;font-size:.78rem;font-weight:600;padding:.1rem .5rem;border-radius:999px;white-space:nowrap}
.dir-up{background:#fee2e2;color:#991b1b}.dir-down{background:#dbeafe;color:#1e40af}.dir-mixed{background:#fef3c7;color:#92400e}.dir-na{background:var(--line);color:var(--muted)}
.flag{color:var(--red);font-weight:600;font-size:.8rem}
ul.compact{columns:1;padding-left:1.2rem}@media(min-width:720px){ul.compact{columns:2;column-gap:2rem}}
ul.compact li{break-inside:avoid;margin:.15rem 0}
.muted{color:var(--muted)}.small{font-size:.85rem}
.faq details{border:1px solid var(--line);border-radius:8px;padding:.6rem 1rem;margin:.5rem 0;background:var(--bg2)}
.faq summary{font-weight:600;cursor:pointer}
.cite{border:1px solid var(--line);border-left:4px solid var(--blue);border-radius:8px;padding:1rem 1.25rem;background:var(--bg2);font-size:.92rem}
.cite code{display:block;white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem;margin-top:.5rem}
.disc{background:var(--amber-bg);border:1px solid var(--amber);border-radius:8px;padding:.75rem 1rem;font-size:.88rem;margin:1.5rem 0}
.cta{text-align:center;margin:2rem 0;padding:1.25rem;border:1px solid var(--line);border-radius:10px}
.cta a.btn{display:inline-block;background:var(--blue);color:#fff;text-decoration:none;padding:.6rem 1.2rem;border-radius:6px;font-weight:600}
.study{margin:.6rem 0}.study .t{font-weight:500}.study .m{font-size:.85rem;color:var(--muted)}
footer{border-top:1px solid var(--line);padding:1.5rem 16px;font-size:.85rem;color:var(--muted);text-align:center}
footer a{color:var(--muted)}
.related{display:flex;flex-wrap:wrap;gap:.5rem}.related a{font-size:.85rem;border:1px solid var(--line);border-radius:999px;padding:.25rem .75rem;text-decoration:none}
"""


def head(title, desc, canonical_path, jsonld_blocks, robots="index, follow, max-image-preview:large"):
    jl = "\n".join(f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>' for b in jsonld_blocks)
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
<meta name="description" content="{esc(desc)}">
<meta name="robots" content="{robots}">
<link rel="canonical" href="{SITE}{canonical_path}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Open Source Medicine Foundation">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{SITE}{canonical_path}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{esc(desc)}">
<link rel="sitemap" type="application/xml" title="Sitemap" href="/sitemap.xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
{jl}
</head>
<body>
<nav class="nav" aria-label="Main navigation"><div class="in">
<a class="brand" href="/index.html">OSMF Research Tracker</a>
<a class="l" href="/biomarker-atlas.html">Biomarker Atlases</a>
<a class="l" href="/clinical_trials.html">Clinical Trials</a>
<a class="l" href="/agents.html">Therapeutic Agents</a>
<a class="l" href="/compare/">Compare</a>
<a class="l" href="https://opensourcemed.info" rel="noopener">opensourcemed.info</a>
</div></nav>
<main>
"""


def footer(updated_text):
    return f"""
<div class="cta"><p><strong>Get OSMF research updates</strong><br><span class="muted small">New biomarker, trial and cohort data, summarised for patients and researchers.</span></p>
<a class="btn" href="{SUBSTACK}" rel="noopener">Subscribe on Substack</a></div>
<div class="disc"><strong>Disclaimer.</strong> This page is an automated, informational synthesis of public research data maintained by the Open Source Medicine Foundation. It is not medical advice, does not establish a diagnosis, and does not endorse any test or treatment. Biomarker directions summarise individual studies that often disagree; registered trials have not necessarily reported results. Discuss any testing or treatment decision with a qualified clinician.</div>
<p class="small muted">{esc(updated_text)}</p>
</main>
<footer>
<p>&copy; Open Source Medicine Foundation &middot; <a href="/index.html">Research Tracker</a> &middot; <a href="/biomarker-atlas.html">Biomarker Atlases</a> &middot; <a href="/clinical_trials.html">Clinical Trials</a> &middot; <a href="/pais-cohorts.html">PAIS Cohorts</a> &middot; <a href="https://opensourcemed.info" rel="noopener">opensourcemed.info</a></p>
<p><a href="https://github.com/MattH55/osmf-research-tracker" rel="noopener">Source code</a> &middot; <a href="/corrections/">Corrections</a></p>
</footer>
</body>
</html>
"""


def breadcrumbs_html(items):
    lis = []
    for i, (label, href) in enumerate(items):
        if href and i < len(items) - 1:
            lis.append(f'<li><a href="{esc(href)}">{esc(label)}</a></li>')
        else:
            lis.append(f'<li aria-current="page">{esc(label)}</li>')
    return f'<nav class="bc" aria-label="Breadcrumb"><ol>{"".join(lis)}</ol></nav>'


def breadcrumbs_jsonld(items):
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": label, "item": SITE + href} for i, (label, href) in enumerate(items)]}


def marker_link(cond, m, has_marker_dir):
    name = m.get("name") or ""
    if has_marker_dir:
        return f'/biomarkers/{cond["slug"]}/{marker_slug(name)}.html'
    return f'/{cond["atlas"]}#biomarker-database'


def plural(n, s, p=None):
    return f"{n} {s if n == 1 else (p or s + 's')}"


# --------------------------------------------------------------------------------------
# Page builder
# --------------------------------------------------------------------------------------
def build_pair(a, b, data, agent_slug_map, all_pairs):
    A, B = data[a], data[b]
    lit_only = not (A["biomarkers"] and B["biomarkers"])
    pair_key = (a, b) if (a, b) in PAIR_NOTES else (b, a)
    note = PAIR_NOTES.get(pair_key, "")
    fname = f"{a}-vs-{b}.html"
    path = f"/compare/{fname}"
    url = SITE + path

    has_dir = {s: os.path.isdir(os.path.join(ROOT, "biomarkers", s)) for s in (a, b)}
    agents_dir = os.path.join(ROOT, "agents")

    # ---- numbers ----
    nA, nB = len(A["markers"]), len(B["markers"])
    catA = Counter(m.get("category") for m in A["markers"] if m.get("category"))
    catB = Counter(m.get("category") for m in B["markers"] if m.get("category"))
    shared, usedA, usedB = shared_markers(A["markers"], B["markers"]) if not lit_only else ([], set(), set())
    disagree = [(x, y, k) for x, y, k in shared if (x.get("direction") or "").lower() != (y.get("direction") or "").lower()]
    distinctA = [m for i, m in enumerate(A["markers"]) if i not in usedA]
    distinctB = [m for i, m in enumerate(B["markers"]) if i not in usedB]
    stA, stB = trial_status_counts(A["trials"]), trial_status_counts(B["trials"])
    actA, actB = active_trial_count(A["trials"]), active_trial_count(B["trials"])
    both_trials = [t for t in A["trials"] if t in B["trials"]]
    both_trial_ids = {t["nct_id"] for t in both_trials}
    shared_agents = sorted(A["agents"] & B["agents"], key=str.lower)
    latestA = A["studies"][0]["pub_date"] if A["studies"] else None
    latestB = B["studies"][0]["pub_date"] if B["studies"] else None
    shared_cohorts = [c for c in A["cohorts"] if c in B["cohorts"]]

    # ---- title/meta ----
    title = f"{A['short']} vs {B['short']}: symptoms, biomarkers, trials and research compared"
    if lit_only:
        desc = (f"{A['short']} and {B['short']} compared from Open Source Medicine Foundation data: {len(A['studies']) + len(B['studies'])} tracked studies, "
                f"{len(A['trials']) + len(B['trials'])} registered trials, shared therapeutic agents and an evidence-based FAQ. Literature-level comparison.")
    else:
        desc = (f"{A['short']} vs {B['short']} side by side: {len(shared)} shared biomarkers out of {nA} and {nB} catalogued, "
                f"{len(A['trials'])} vs {len(B['trials'])} registered trials, latest PubMed studies, overlapping therapeutics and FAQ.")
    desc = desc[:300]

    crumbs = [("Research Tracker", "/index.html"), ("Compare conditions", "/compare/"), (f"{A['short']} vs {B['short']}", path)]

    # ---- FAQ ----
    faq = []
    # Q1: both
    if lit_only:
        q1 = (f"Yes. {B['short'] if b in LIT_ONLY else A['short']} is a syndrome diagnosed on clinical criteria and can be diagnosed in someone who also has "
              f"{A['short'] if b in LIT_ONLY else B['short']}; {len(both_trials)} registered trial{'s' if len(both_trials) != 1 else ''} in the OSMF registry "
              f"list both conditions, and {'they share ' + plural(len(shared_agents), 'therapeutic agent') + ' under investigation' if shared_agents else 'no therapeutic agent is currently tracked for both'}.")
    else:
        q1 = (f"They are not mutually exclusive. Both are diagnosed clinically, and a person can meet criteria for {A['short']} and {B['short']} at the same time. "
              f"In the OSMF data the two conditions share {len(shared)} catalogued biomarkers, {len(both_trials)} registered trial{'s' if len(both_trials) != 1 else ''} "
              f"list both conditions, and {plural(len(shared_cohorts), 'cohort')} in the PAIS database {'are' if len(shared_cohorts) != 1 else 'is'} relevant to both. "
              f"Overlap in a dataset is not evidence that one condition causes the other.")
    faq.append((f"Can you have both {A['short']} and {B['short']}?", q1))
    # Q2: biomarker profiles
    if lit_only:
        lo = A if a in LIT_ONLY else B
        hi = B if a in LIT_ONLY else A
        q2 = (f"OSMF does not maintain a biomarker atlas for {lo['short']}, which is diagnosed by physiological or clinical criteria rather than a laboratory panel, "
              f"so this is a literature-level comparison. {hi['short']} has {len(hi['markers'])} catalogued markers across {len(Counter(m.get('category') for m in hi['markers']))} categories "
              f"(most often {', '.join(k for k, _ in Counter(m.get('category') for m in hi['markers']).most_common(3))}).")
    else:
        topA = ", ".join(f"{k} ({v})" for k, v in catA.most_common(3))
        topB = ", ".join(f"{k} ({v})" for k, v in catB.most_common(3))
        q2 = (f"{A['short']} has {nA} catalogued markers, led by {topA}. {B['short']} has {nB}, led by {topB}. "
              f"{len(shared)} markers appear in both atlases"
              + (f", and {len(disagree)} of those are reported to move in different directions ({', '.join(x.get('name') for x, _, _ in disagree[:3])}{'...' if len(disagree) > 3 else ''})." if disagree else ", and all shared markers are reported in the same direction.")
              + f" Categories unique to {A['short']}: {', '.join(sorted(set(catA) - set(catB))) or 'none'}; unique to {B['short']}: {', '.join(sorted(set(catB) - set(catA))) or 'none'}.")
    faq.append(("How do the biomarker profiles differ?", q2))
    # Q3: trials
    if actA == actB:
        lead = f"Both have {actA} active or recruiting trials in the OSMF registry"
    else:
        w, l, wn, ln = (A, B, actA, actB) if actA > actB else (B, A, actB, actA)
        lead = f"{w['short']} has more: {wn} active or recruiting trials versus {ln} for {l['short']}"
    q3 = (f"{lead} (registry snapshot {fmt_date(A['trials_updated'])}). Totals including completed, terminated and unknown-status studies are "
          f"{len(A['trials'])} for {A['short']} and {len(B['trials'])} for {B['short']}. "
          f"{'Condition matching for ' + ', '.join(c['short'] for c in (A, B) if c['trial_mapped'] is None) + ' relies on keyword matching of registry condition fields and may miss trials. ' if any(c['trial_mapped'] is None for c in (A, B)) else ''}"
          f"Trial counts measure research attention, not treatment efficacy.")
    faq.append(("Which has more active clinical trials?", q3))
    # Q4: research volume
    q4 = (f"OSMF tracks {len(A['studies'])} recent PubMed-indexed studies for {A['short']} (latest {fmt_date(latestA)}) and {len(B['studies'])} for {B['short']} "
          f"(latest {fmt_date(latestB)}). The feeds hold a rolling window of recent publications, so they indicate current publication pace rather than lifetime output. "
          f"See the <a href=\"/{A['feed']}\">{esc(A['short'])} feed</a> and the <a href=\"/{B['feed']}\">{esc(B['short'])} feed</a> for the full lists.")
    faq.append(("Which condition has more recent research?", q4))
    # Q5: treatments
    if shared_agents:
        q5 = (f"{plural(len(shared_agents), 'agent')} appear in the trial registry or therapeutic-agent database for both conditions, including "
              f"{', '.join(shared_agents[:5])}. All of these are investigational for these indications; none is an approved treatment for either condition. "
              f"Overlap usually reflects shared hypotheses (immune modulation, autonomic support, antiviral or anti-inflammatory strategies) rather than demonstrated efficacy.")
    else:
        q5 = (f"No therapeutic agent is currently tracked for both {A['short']} and {B['short']} in the OSMF trial registry or agent database. "
              f"That reflects the small or non-overlapping evidence base rather than proof that treatments differ.")
    faq.append(("Are the same treatments being studied for both?", q5))
    # Q6: cohorts
    cohA, cohB = len(A["cohorts"]), len(B["cohorts"])
    q6 = (f"The PAIS cohort database lists {plural(cohA, 'named cohort')} for {A['short']} and {plural(cohB, 'named cohort')} for {B['short']}"
          + (f", the largest being {max(A['cohorts'], key=lambda c: c.get('n_enrolled') or 0)['name']} ({(max(A['cohorts'], key=lambda c: c.get('n_enrolled') or 0).get('n_enrolled') or 0):,} enrolled)" if A["cohorts"] else "")
          + (f" and {max(B['cohorts'], key=lambda c: c.get('n_enrolled') or 0)['name']} ({(max(B['cohorts'], key=lambda c: c.get('n_enrolled') or 0).get('n_enrolled') or 0):,} enrolled)" if B["cohorts"] else "")
          + ". Cohorts with stored biospecimens and open external access are the most useful for cross-condition biomarker validation.")
    faq.append(("Which has larger research cohorts?", q6))

    # ---- JSON-LD ----
    def med_cond(c):
        d = {"@context": "https://schema.org", "@type": "MedicalCondition", "name": c["name"], "alternateName": c["alt"],
             "url": SITE + "/" + (c["atlas"] or c["feed"])}
        if c["hero"]:
            d["description"] = c["hero"]
        return d
    jsonld = [
        breadcrumbs_jsonld(crumbs),
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", ans)}} for q, ans in faq]},
        med_cond(A), med_cond(B),
    ]

    # ---- robots gating (spec section 4) ----
    outbound_links = 3 + len(A["studies"][:5]) + len(B["studies"][:5])
    has_citation = any(s.get("pmid") for s in A["studies"] + B["studies"]) or any(m.get("reference", {}).get("doi") for m in A["markers"] + B["markers"])
    robots = "index, follow, max-image-preview:large" if (A["studies"] and B["studies"] and outbound_links >= 3 and has_citation) else "noindex, follow"

    out = [head(title, desc, path, jsonld, robots)]
    out.append(breadcrumbs_html(crumbs))
    out.append(f"<h1>{esc(A['short'])} vs {esc(B['short'])}: symptoms, biomarkers, trials and research{'<span class=\"pill\">literature-only comparison</span>' if lit_only else ''}</h1>")
    def full(c):
        return esc(c['name']) + (f" ({esc(c['short'])})" if c['short'].lower() != c['name'].lower() else "")
    out.append(f"<p class=\"lede\">A data-driven comparison of {full(A)} and {full(B)} built from the Open Source Medicine Foundation biomarker atlases, PubMed literature feeds, ClinicalTrials.gov registry extract and post-acute infection syndrome (PAIS) cohort database.</p>")
    if note:
        out.append(f"<p>{esc(note)}</p>")
    if lit_only:
        lo = A if not A["biomarkers"] else B
        out.append(f"<p class=\"small muted\">No biomarker atlas exists for {esc(lo['short'])}, so the biomarker sections below are limited to the other condition. This page compares literature, trials, therapeutics and cohorts.</p>")

    # ---- Overview ----
    out.append("<h2 id=\"overview\">What each condition is</h2><div class=\"grid2\">")
    for c in (A, B):
        alt = ", ".join(x for x in c["alt"] if x != c["short"])
        links = [f'<a href="/{c["feed"]}">literature feed</a>']
        if c["atlas"]:
            links.insert(0, f'<a href="/{c["atlas"]}">biomarker atlas</a>')
        out.append(f"<div class=\"card\"><h3>{esc(c['name'])}</h3>"
                   + (f"<p class=\"alt\">Also known as: {esc(alt)}</p>" if alt else "")
                   + f"<p>{esc(c['blurb'])}</p>"
                   + (f"<p class=\"small muted\">Atlas scope: {esc(c['hero'])}</p>" if c["hero"] else "")
                   + f"<p class=\"small\">OSMF resources: {' &middot; '.join(links)}</p></div>")
    out.append("</div>")

    # ---- Summary table ----
    out.append("<h2 id=\"at-a-glance\">Side-by-side summary</h2><div class=\"tw\"><table><thead><tr><th>Measure</th>"
               f"<th>{esc(A['short'])}</th><th>{esc(B['short'])}</th></tr></thead><tbody>")

    def row(label, va, vb):
        out.append(f"<tr><th scope=\"row\">{label}</th><td>{va}</td><td>{vb}</td></tr>")
    row("Biomarkers catalogued", f"{nA}" if A["biomarkers"] else "No atlas", f"{nB}" if B["biomarkers"] else "No atlas")
    row("Biomarker categories covered",
        esc(", ".join(f"{k} ({v})" for k, v in catA.most_common())) if catA else "&mdash;",
        esc(", ".join(f"{k} ({v})" for k, v in catB.most_common())) if catB else "&mdash;")
    row("Markers with LOINC codes", sum(1 for m in A["markers"] if m.get("loinc")) if A["biomarkers"] else "&mdash;", sum(1 for m in B["markers"] if m.get("loinc")) if B["biomarkers"] else "&mdash;")
    row("Literature studies tracked", len(A["studies"]), len(B["studies"]))
    row("Most recent tracked study", esc(fmt_date(latestA)), esc(fmt_date(latestB)))
    row("Registered trials (all statuses)", len(A["trials"]), len(B["trials"]))
    for (labA, cA), (labB, cB) in zip(stA, stB):
        row(f"&nbsp;&nbsp;{esc(labA)}", cA, cB)
    row("Named cohorts in PAIS database", cohA, cohB)
    row("Therapeutic agents tracked", len(A["agents"]), len(B["agents"]))
    out.append("</tbody></table></div>")
    out.append(f"<p class=\"small muted\">Trial condition matching: {esc(A['short'])} uses {'the registry’s mapped condition label' if A['trial_mapped'] else 'keyword matching on registry condition and title fields'}; "
               f"{esc(B['short'])} uses {'the registry’s mapped condition label' if B['trial_mapped'] else 'keyword matching on registry condition and title fields'}. Trials listing both conditions: {len(both_trials)}.</p>")

    # ---- Shared biomarkers ----
    if not lit_only:
        out.append(f"<h2 id=\"shared-biomarkers\">Shared biomarkers ({len(shared)})</h2>")
        if shared:
            out.append(f"<p>Markers catalogued in both atlases, matched by normalised name or LOINC code. {'Rows marked <span class=\"flag\">direction differs</span> are reported to change in opposite or inconsistent directions across the two literatures, which may reflect different comparison groups, assays or disease stages rather than true biology.' if disagree else 'All shared markers are reported in the same direction in both atlases.'}</p>")
            out.append(f"<div class=\"tw\"><table><thead><tr><th>Biomarker</th><th>Category</th><th>Direction in {esc(A['short'])}</th><th>Direction in {esc(B['short'])}</th><th>Matched by</th><th>Sources</th></tr></thead><tbody>")
            for x, y, basis in shared:
                flag = ' <span class="flag">direction differs</span>' if (x.get("direction") or "").lower() != (y.get("direction") or "").lower() else ""
                refs = []
                for c, m in ((A, x), (B, y)):
                    r = m.get("reference") or {}
                    if r.get("doi"):
                        refs.append(f'<a href="https://doi.org/{esc(r["doi"])}" rel="noopener">{esc(r.get("citation") or r["doi"])}</a>')
                    elif r.get("citation"):
                        refs.append(esc(r["citation"]))
                out.append("<tr>"
                           f"<td><a href=\"{marker_link(A, x, has_dir[a])}\">{esc(x.get('name'))}</a>" + (f"<br><span class=\"small muted\">{esc(y.get('name'))} in {esc(B['short'])}</span>" if norm_key(x.get('name') or '') != norm_key(y.get('name') or '') else "") + f"{flag}</td>"
                           f"<td>{esc(x.get('category'))}{(' / ' + esc(y.get('category'))) if y.get('category') != x.get('category') else ''}</td>"
                           f"<td>{direction_badge(x.get('direction'))}<br><span class=\"small muted\">vs {esc(x.get('comparison') or 'n/a')}</span></td>"
                           f"<td>{direction_badge(y.get('direction'))}<br><span class=\"small muted\">vs {esc(y.get('comparison') or 'n/a')}</span></td>"
                           f"<td class=\"small\">{esc(basis)}</td><td class=\"small\">{'; '.join(refs) or '&mdash;'}</td></tr>")
            out.append("</tbody></table></div>")
        else:
            out.append(f"<p>No marker in the {esc(A['short'])} atlas matches a marker in the {esc(B['short'])} atlas by name or LOINC code. This usually means the two literatures measure different analyte classes rather than that the conditions are biologically unrelated.</p>")

        # ---- Distinct ----
        out.append("<h2 id=\"distinct-biomarkers\">Distinct biomarkers</h2>"
                   f"<p>Top 15 markers catalogued for one condition but not matched in the other. Full lists are on the <a href=\"/{esc(A['atlas'])}\">{esc(A['short'])} atlas</a> and the <a href=\"/{esc(B['atlas'])}\">{esc(B['short'])} atlas</a>.</p><div class=\"grid2\">")
        for c, dist, slug in ((A, distinctA, a), (B, distinctB, b)):
            out.append(f"<div class=\"card\"><h3>Only in {esc(c['short'])} atlas ({len(dist)})</h3>")
            if dist:
                out.append("<ul class=\"compact\">")
                for m in dist[:15]:
                    out.append(f"<li><a href=\"{marker_link(c, m, has_dir[slug])}\">{esc(m.get('name'))}</a> {direction_badge(m.get('direction'))} <span class=\"small muted\">{esc(m.get('category') or '')}</span></li>")
                out.append("</ul>")
                if len(dist) > 15:
                    out.append(f"<p class=\"small muted\">+{len(dist) - 15} more in the <a href=\"/{esc(c['atlas'])}\">atlas</a>.</p>")
            else:
                out.append("<p class=\"muted\">Every catalogued marker is shared.</p>")
            out.append("</div>")
        out.append("</div>")
    else:
        hi = A if A["biomarkers"] else B
        lo = B if A["biomarkers"] else A
        out.append(f"<h2 id=\"biomarkers\">Biomarkers catalogued for {esc(hi['short'])}</h2>"
                   f"<p>{esc(lo['short'])} has no OSMF biomarker atlas, so no shared-marker matching is possible. The {esc(hi['short'])} atlas lists {len(hi['markers'])} markers; the 15 most relevant to this comparison are shown (autonomic, immune, inflammatory and vascular categories first).</p>")
        pri = {"autonomic": 0, "immune": 1, "inflammatory": 2, "vascular": 3, "functional": 4}
        sel = sorted(hi["markers"], key=lambda m: pri.get(m.get("category"), 9))[:15]
        out.append("<ul class=\"compact\">")
        for m in sel:
            out.append(f"<li><a href=\"{marker_link(hi, m, has_dir[hi['slug']])}\">{esc(m.get('name'))}</a> {direction_badge(m.get('direction'))} <span class=\"small muted\">{esc(m.get('category') or '')}</span></li>")
        out.append(f"</ul><p class=\"small\"><a href=\"/{esc(hi['atlas'])}\">Browse the full {esc(hi['short'])} atlas</a>.</p>")

    # ---- Therapeutics ----
    out.append(f"<h2 id=\"therapeutics\">Overlapping therapeutics under investigation ({len(shared_agents)})</h2>")
    if shared_agents:
        out.append(f"<p>Agents that appear in registered trials or the OSMF therapeutic-agent database for both {esc(A['short'])} and {esc(B['short'])}. Inclusion means an agent is being studied, not that it works.</p><ul class=\"compact\">")
        for ag in shared_agents:
            slug = agent_slug_map.get(ag.lower())
            if slug and os.path.exists(os.path.join(agents_dir, slug + ".html")):
                out.append(f"<li><a href=\"/agents/{esc(slug)}.html\">{esc(ag)}</a></li>")
            else:
                out.append(f"<li>{esc(ag)}</li>")
        out.append("</ul>")
    else:
        out.append(f"<p>No therapeutic agent is currently tracked for both conditions. {esc(A['short'])} has {len(A['agents'])} tracked agents and {esc(B['short'])} has {len(B['agents'])}; see the <a href=\"/agents.html\">therapeutic agents index</a>.</p>")
    if both_trials:
        out.append(f"<h3>Trials enrolling both conditions ({len(both_trials)})</h3><ul>")
        for t in sorted(both_trials, key=lambda t: t.get("start_date") or "", reverse=True)[:10]:
            out.append(f"<li><a href=\"https://clinicaltrials.gov/study/{esc(t['nct_id'])}\" rel=\"noopener\">{esc(t['nct_id'])}</a> &middot; {esc(t.get('title'))} <span class=\"small muted\">({esc((t.get('status') or '').replace('_', ' ').title())}{', ' + esc(t['phase'].replace('PHASE', 'Phase ')) if t.get('phase') and t['phase'] not in ('NA', 'N/A') else ''})</span></li>")
        out.append("</ul>")
        if len(both_trials) > 10:
            out.append(f"<p class=\"small muted\">Showing 10 of {len(both_trials)}; see the <a href=\"/clinical_trials.html\">trials tracker</a>.</p>")

    # ---- Cohorts ----
    if A["cohorts"] or B["cohorts"]:
        out.append("<h2 id=\"cohorts\">Research cohorts</h2><div class=\"grid2\">")
        for c in (A, B):
            out.append(f"<div class=\"card\"><h3>{esc(c['short'])} cohorts ({len(c['cohorts'])})</h3>")
            if c["cohorts"]:
                out.append("<ul>")
                for co in sorted(c["cohorts"], key=lambda x: -(x.get("n_enrolled") or 0)):
                    page = f"/pais-cohorts/{co['id']}.html" if os.path.exists(os.path.join(ROOT, "pais-cohorts", co["id"] + ".html")) else "/pais-cohorts.html"
                    n = co.get("n_enrolled")
                    out.append(f"<li><a href=\"{page}\">{esc(co['name'])}</a> <span class=\"small muted\">{esc(co.get('design') or '').replace('_', ' ')}{', n=' + format(n, ',') if n else ''}{', biobank ' + esc(co['biobank_status']) if co.get('biobank_status') else ''}</span></li>")
                out.append("</ul>")
            else:
                out.append("<p class=\"muted\">No named cohort for this condition in the PAIS database yet.</p>")
            out.append("</div>")
        out.append("</div>")

    # ---- Recent research ----
    out.append("<h2 id=\"recent-research\">Recent research</h2><div class=\"grid2\">")
    for c in (A, B):
        out.append(f"<div class=\"card\"><h3>Latest {esc(c['short'])} studies</h3>")
        for s in c["studies"][:5]:
            out.append(f"<div class=\"study\"><div class=\"t\"><a href=\"https://pubmed.ncbi.nlm.nih.gov/{esc(s['pmid'])}/\" rel=\"noopener\">{esc(s.get('title'))}</a></div>"
                       f"<div class=\"m\">{esc(s.get('journal') or 'Journal n/a')} &middot; {esc(fmt_date(s.get('pub_date')))} &middot; PMID {esc(s['pmid'])}</div></div>")
        if not c["studies"]:
            out.append("<p class=\"muted\">No studies in the current feed.</p>")
        out.append(f"<p class=\"small\"><a href=\"/{esc(c['feed'])}\">All {len(c['studies'])} tracked {esc(c['short'])} studies</a></p></div>")
    out.append("</div>")

    # ---- FAQ ----
    out.append("<h2 id=\"faq\">Frequently asked questions</h2><div class=\"faq\">")
    for q, ans in faq:
        out.append(f"<details open><summary>{esc(q)}</summary><p>{ans}</p></details>")
    out.append("</div>")

    # ---- Related ----
    others = [p for p in all_pairs if p != (a, b) and (a in p or b in p)]
    if others:
        out.append("<h2 id=\"related\">Related comparisons</h2><div class=\"related\">")
        for x, y in others:
            out.append(f"<a href=\"/compare/{x}-vs-{y}.html\">{esc(data[x]['short'])} vs {esc(data[y]['short'])}</a>")
        out.append("</div>")

    # ---- Cite ----
    data_dates = [d for d in (A["lit_updated"], B["lit_updated"], A["trials_updated"], A["atlas_modified"], B["atlas_modified"]) if d]
    data_as_of = max(str(d)[:10] for d in data_dates) if data_dates else TODAY
    out.append("<h2 id=\"cite\">Cite this page</h2><div class=\"cite\">"
               f"Open Source Medicine Foundation. <em>{esc(A['short'])} vs {esc(B['short'])}: symptoms, biomarkers, trials and research compared.</em> OSMF Research Tracker; data as of {esc(fmt_date(data_as_of))}, page generated {esc(fmt_date(TODAY))}. Available at: {esc(url)}"
               f"<code>@misc{{osmf_{a.replace('-', '')}_vs_{b.replace('-', '')},\n  author = {{Open Source Medicine Foundation}},\n  title = {{{esc(A['short'])} vs {esc(B['short'])}: symptoms, biomarkers, trials and research compared}},\n  year = {{{TODAY[:4]}}},\n  howpublished = {{\\url{{{esc(url)}}}}},\n  note = {{Data as of {esc(data_as_of)}}}\n}}</code></div>")

    updated = (f"Last updated {fmt_date(TODAY)} (page build). Underlying data: literature feeds {fmt_date(A['lit_updated'])} / {fmt_date(B['lit_updated'])}; "
               f"trial registry {fmt_date(A['trials_updated'])}; atlases {fmt_date(A['atlas_modified'])} / {fmt_date(B['atlas_modified'])}. Generated by scripts/build_compare_pages.py.")
    out.append(footer(updated))
    page = "\n".join(out)
    stats = dict(file=fname, title=title, lit_only=lit_only, shared=len(shared), disagree=len(disagree), robots=robots,
                 trialsA=len(A["trials"]), trialsB=len(B["trials"]), agents=len(shared_agents), both_trials=len(both_trials))
    return fname, page, stats


# --------------------------------------------------------------------------------------
# Index page
# --------------------------------------------------------------------------------------
def build_index(data, stats_list):
    title = "Compare post-viral and chronic illness conditions: Long COVID, ME/CFS, PACVS, Lyme, GWI, POTS, MCAS"
    desc = (f"{len(stats_list)} side-by-side comparisons of post-infectious and chronic multisymptom conditions built from OSMF biomarker atlases, "
            "PubMed feeds, the clinical-trial registry and the PAIS cohort database.")
    crumbs = [("Research Tracker", "/index.html"), ("Compare conditions", "/compare/")]
    jsonld = [breadcrumbs_jsonld(crumbs),
              {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "url": SITE + "/compare/", "description": desc,
               "hasPart": [{"@type": "WebPage", "name": s["title"], "url": f"{SITE}/compare/{s['file']}"} for s in stats_list]}]
    out = [head(title, desc, "/compare/", jsonld)]
    out.append(breadcrumbs_html(crumbs))
    out.append("<h1>Compare conditions</h1>")
    out.append("<p class=\"lede\">Each comparison page places two conditions side by side: what they are, how many biomarkers OSMF has catalogued and which are shared, "
               "how many trials are registered and in what status, which therapeutic agents are under investigation for both, the named research cohorts, and the latest PubMed studies.</p>")
    out.append("<h2 id=\"post-viral\">Post-infectious and multisymptom conditions</h2><p>Full biomarker-level comparisons between conditions that have an OSMF biomarker atlas.</p><div class=\"tw\"><table><thead><tr><th>Comparison</th><th>Shared biomarkers</th><th>Direction conflicts</th><th>Trials (A / B)</th><th>Shared agents</th></tr></thead><tbody>")
    for s in stats_list:
        if s["lit_only"]:
            continue
        out.append(f"<tr><td><a href=\"/compare/{s['file']}\">{esc(s['title'].split(':')[0])}</a></td><td class=\"num\">{s['shared']}</td><td class=\"num\">{s['disagree']}</td><td class=\"num\">{s['trialsA']} / {s['trialsB']}</td><td class=\"num\">{s['agents']}</td></tr>")
    out.append("</tbody></table></div>")
    out.append("<h2 id=\"literature-only\">Comparisons with POTS and MCAS (literature-only)</h2><p>POTS and MCAS have no OSMF biomarker atlas, so these pages compare literature, trials, therapeutics and cohorts.</p><div class=\"tw\"><table><thead><tr><th>Comparison</th><th>Trials (A / B)</th><th>Trials listing both</th><th>Shared agents</th></tr></thead><tbody>")
    for s in stats_list:
        if not s["lit_only"]:
            continue
        out.append(f"<tr><td><a href=\"/compare/{s['file']}\">{esc(s['title'].split(':')[0])}</a></td><td class=\"num\">{s['trialsA']} / {s['trialsB']}</td><td class=\"num\">{s['both_trials']}</td><td class=\"num\">{s['agents']}</td></tr>")
    out.append("</tbody></table></div>")
    out.append("<h2 id=\"conditions\">Conditions covered</h2><ul class=\"compact\">")
    for slug, c in data.items():
        links = [f'<a href="/{c["feed"]}">literature</a>']
        if c["atlas"]:
            links.insert(0, f'<a href="/{c["atlas"]}">biomarker atlas</a>')
        label = esc(c['name']) + (f" ({esc(c['short'])})" if c['short'].lower() != c['name'].lower() else "")
        out.append(f"<li><strong>{label}</strong> &middot; {' &middot; '.join(links)}</li>")
    out.append("</ul>")
    out.append("<h2 id=\"state-laws\">State healthcare law comparison</h2><p class=\"muted\">A separate tool for comparing healthcare-access laws across US states is under development. In the meantime, browse the <a href=\"/maps/\">Medical Freedom Maps layer maps</a> or <a href=\"/maps/states/\">state profiles</a>.</p>")
    out.append(footer(f"Last updated {fmt_date(TODAY)}. Generated by scripts/build_compare_pages.py."))
    return "\n".join(out)


# --------------------------------------------------------------------------------------
def main():
    data, agent_slug_map = load_all()
    pairs = list(itertools.combinations(POST_VIRAL, 2))
    for pv in POST_VIRAL:
        for lo in LIT_ONLY:
            if data[lo]["studies"]:
                pairs.append((pv, lo))
    os.makedirs(OUT_DIR, exist_ok=True)
    stats_list = []
    for a, b in pairs:
        fname, page, stats = build_pair(a, b, data, agent_slug_map, pairs)
        with open(os.path.join(OUT_DIR, fname), "w", encoding="utf-8", newline="\n") as f:
            f.write(page)
        stats_list.append(stats)
        print(f"wrote compare/{fname}  shared={stats['shared']} conflicts={stats['disagree']} trials={stats['trialsA']}/{stats['trialsB']} agents={stats['agents']} robots={stats['robots'].split(',')[0]}")
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8", newline="\n") as f:
        f.write(build_index(data, stats_list))
    print(f"wrote compare/index.html ({len(stats_list)} comparison pages)")
    noindex = [s["file"] for s in stats_list if s["robots"].startswith("noindex")]
    print(f"noindex pages: {len(noindex)} {noindex}")
    print("data gaps:")
    for slug, d in data.items():
        gaps = []
        if not d["biomarkers"]:
            gaps.append("no biomarker atlas")
        if not d["cohorts"]:
            gaps.append("no cohorts")
        if d["trial_mapped"] is None:
            gaps.append(f"trials by keyword only ({len(d['trials'])})")
        if len(d["studies"]) < 25:
            gaps.append(f"only {len(d['studies'])} studies")
        if gaps:
            print(f"  {slug}: {'; '.join(gaps)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
