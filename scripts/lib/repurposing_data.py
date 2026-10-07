#!/usr/bin/env python3
"""
Shared data layer for the drug-repurposing explorer and the disease x agent
pair pages.

Merges two evidence tracks into one list of pair records:

  1. data/disease-intelligence/<slug>.json  (109 chronic diseases)
     therapeutics.merged_ranked[]  -> clinical_evidence{clinical_trials, literature}
  2. data/therapeutic_agents.json          (post-viral conditions)
     agents[] -> trials[] (joined to data/clinical_trials/clinical_trials_current.json
     for sponsor / mapped condition), studies[], Key Studies (PMIDs), and the
     PubMed literature caches in data/agent-literature/.

Also reads data/disease-agent-pairs.json (evidence tier join table),
data/vocab/agent-slugs.json, data/vocab/disease-slugs.yaml and
data/condition-categories.json.

Every record is a plain dict; see build_records() for the field list.
The evidence score is computed in score_record() and documented in
SCORE_DOC so the explorer and pair pages can show the same explanation.
"""
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DI_DIR = ROOT / "data" / "disease-intelligence"
TA_FILE = ROOT / "data" / "therapeutic_agents.json"
CT_FILE = ROOT / "data" / "clinical_trials" / "clinical_trials_current.json"
PAIRS_FILE = ROOT / "data" / "disease-agent-pairs.json"
AGENT_SLUGS_FILE = ROOT / "data" / "vocab" / "agent-slugs.json"
AGENT_FLAGGED_FILE = ROOT / "data" / "vocab" / "agent-slugs-flagged.json"
DISEASE_SLUGS_FILE = ROOT / "data" / "vocab" / "disease-slugs.yaml"
CATEGORIES_FILE = ROOT / "data" / "condition-categories.json"
LIT_DIR = ROOT / "data" / "agent-literature"
ONTOLOGY_FILE = ROOT / "data" / "clinical_trials" / "treatment-ontology.json"
AGENTS_DIR = ROOT / "agents"

SITE = "https://research.opensourcemed.info"

# ---------------------------------------------------------------------------
# Post-viral condition map (therapeutic_agents.json "Primary Conditions")
# ---------------------------------------------------------------------------
PV_CONDITIONS = {
    "Long COVID": ("long-covid", "Long COVID", "Long COVID / PASC", "long-covid.html"),
    "ME/CFS": ("me-cfs", "ME/CFS", "Myalgic Encephalomyelitis / Chronic Fatigue Syndrome", "me-cfs.html"),
    "POTS": ("pots", "POTS", "Postural Orthostatic Tachycardia Syndrome", "pots.html"),
    "MCAS": ("mcas", "MCAS", "Mast Cell Activation Syndrome", "mcas.html"),
    "PACVS": ("pacvs", "PACVS", "Post-Acute COVID Vaccination Syndrome", "pacvs.html"),
    "Lyme": ("lyme", "Lyme / PTLDS", "Lyme Disease and Post-Treatment Lyme Disease Syndrome", "lyme.html"),
    "Gulf War Illness": ("gulf-war-illness", "Gulf War Illness", "Gulf War Illness", "gulf-war-illness.html"),
}
PV_OTHER = ("other-post-viral", "Other post-viral syndromes", "Other Post-Infectious and Post-Viral Syndromes", "other-post-viral.html")

# clinical_trials_current.json mapped_conditions -> disease slug
CT_CONDITION_MAP = {
    "Long COVID / PASC": "long-covid",
    "ME/CFS": "me-cfs",
}

# ---------------------------------------------------------------------------
# Evidence score
# ---------------------------------------------------------------------------
TRIAL_STATUS_WEIGHT = {
    "RECRUITING": 3.0,
    "ENROLLING_BY_INVITATION": 3.0,
    "ACTIVE_NOT_RECRUITING": 3.0,
    "NOT_YET_RECRUITING": 2.0,
    "COMPLETED": 2.5,
    "UNKNOWN": 1.0,
    "TERMINATED": 0.5,
    "WITHDRAWN": 0.5,
    "SUSPENDED": 0.5,
}
TRIAL_PHASE_BONUS = {"PHASE4": 2.0, "PHASE3": 2.0, "PHASE2": 1.0, "PHASE1": 0.5, "EARLY_PHASE1": 0.5}
LIT_TYPE_WEIGHT = {
    "cochrane_review": 5.0,
    "meta_analysis": 4.0,
    "systematic_review": 3.0,
    "rct": 3.0,
    "clinical_trial": 2.0,
    "curated_reference": 1.5,
    "pubmed_search": 1.0,
    "other": 1.0,
}
TIER_POINTS = {"A": 15, "B": 10, "C": 5, "D": 0}
TIER_LABEL = {"A": "Strong", "B": "Moderate", "C": "Preliminary", "D": "Anecdotal"}
TRIAL_CAP = 30.0
LIT_CAP = 30.0
APPROVED_BONUS = 5.0

SCORE_DOC = [
    "Each registered trial scores by status (recruiting / active / enrolling 3, completed 2.5, not yet recruiting 2, unknown 1, terminated / withdrawn / suspended 0.5) plus a phase bonus (phase 3-4 +2, phase 2 +1, phase 1 +0.5). The trial component is capped at 30.",
    "Each literature item scores by design (Cochrane review 5, meta-analysis 4, systematic review 3, RCT 3, clinical trial publication 2, curated reference 1.5, other PubMed record 1). The literature component is capped at 30.",
    "The existing evidence tier adds 15 (A / Strong), 10 (B / Moderate), 5 (C / Preliminary) or 0 (D / Anecdotal).",
    "Agents approved for any indication (max clinical phase 4) add 5, because an approved agent has an established safety profile that lowers the barrier to repurposing trials.",
    "The score ranks what has been studied, not what works. It does not read effect sizes or directions of effect.",
]

STATUS_GROUP = {
    "RECRUITING": "recruiting",
    "ENROLLING_BY_INVITATION": "recruiting",
    "ACTIVE_NOT_RECRUITING": "active",
    "NOT_YET_RECRUITING": "active",
    "COMPLETED": "completed",
}

# drug_type_label (disease-intelligence) / types (therapeutic_agents) -> agent type bucket
DI_TYPE_MAP = {
    "Small molecule": "Drug",
    "Biologic": "Biologic",
    "Herbal": "Supplement",
    "Supplement": "Supplement",
    "Nutraceutical": "Supplement",
    "Cell therapy": "Advanced therapy",
    "Gene therapy": "Advanced therapy",
    "Lifestyle": "Behavioural",
    "Psychedelic": "Drug",
}
TA_TYPE_MAP = {
    "Drug (Pharmaceutical)": "Drug",
    "Biologic / Immunotherapy": "Biologic",
    "Supplement / Nutraceutical": "Supplement",
    "Medical Device": "Device",
    "Behavioral / Protocol / Exercise": "Behavioural",
    "Other / Unclassified": "Other",
}

JUNK_MECH = re.compile(r"Enrollment:|Sponsor Type|Unknown / General|^N/?A$", re.I)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text or "agent"


def _load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if s.lower() in ("none", "nan", "null", "n/a", "na", ""):
        return ""
    return s


def _year_of(s: str):
    m = re.search(r"(19|20)\d{2}", _clean(s))
    return int(m.group(0)) if m else None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_disease_labels() -> dict:
    """slug -> {label, mondo_id} from data/vocab/disease-slugs.yaml (no yaml dep needed)."""
    out = {}
    if not DISEASE_SLUGS_FILE.exists():
        return out
    cur = None
    for line in DISEASE_SLUGS_FILE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^- slug:\s*(\S+)", line)
        if m:
            cur = {"slug": m.group(1), "label": "", "mondo_id": ""}
            out[cur["slug"]] = cur
            continue
        if cur is None:
            continue
        m = re.match(r"^\s+canonical_label:\s*(.+)$", line)
        if m:
            cur["label"] = m.group(1).strip().strip('"').strip("'")
        m = re.match(r"^\s+mondo_id:\s*(\S+)", line)
        if m:
            cur["mondo_id"] = m.group(1)
    return out


def load_categories() -> dict:
    """slug -> {category_id, category_label, name, literature, biomarkers}."""
    out = {}
    data = _load_json(CATEGORIES_FILE, {"categories": []})
    for cat in data.get("categories", []):
        for c in cat.get("conditions", []):
            out[c["slug"]] = {
                "category_id": cat["id"],
                "category_label": cat["label"],
                "name": c.get("name", ""),
                "literature": c.get("literature", ""),
                "biomarkers": c.get("biomarkers", ""),
            }
    return out


def load_agent_slugs():
    slugs = _load_json(AGENT_SLUGS_FILE, [])
    flagged = {a["display_name"] for a in _load_json(AGENT_FLAGGED_FILE, [])}
    name_to_slug = {s["display_name"]: s["slug"] for s in slugs}
    existing = {s["slug"] for s in slugs if (AGENTS_DIR / s["slug"] / "index.html").exists()}
    return name_to_slug, flagged, existing


def load_pair_tiers() -> dict:
    return {(p["disease_slug"], p["agent_slug"]): p for p in _load_json(PAIRS_FILE, [])}


def load_literature_by_slug() -> dict:
    """treatment slug -> {pmid: {title, journal, year, url}} from the agent-literature caches.
    Only the Long COVID caches exist today; returns {condition_slug: {agent_slug: {...}}}."""
    out = defaultdict(lambda: defaultdict(dict))
    cache = _load_json(LIT_DIR / "biomarker-intervention-cache.json", {})
    for key, entry in cache.items():
        # key: treatment:<slug>|<condition>:<biomarker>
        try:
            left, right = key.split("|", 1)
        except ValueError:
            continue
        agent_slug = left.replace("treatment:", "")
        cond = right.split(":", 1)[0]
        for art in entry.get("articles", []):
            pmid = _clean(art.get("pmid"))
            if not pmid:
                continue
            out[cond][agent_slug][pmid] = {
                "pmid": pmid,
                "title": _clean(art.get("title")),
                "journal": _clean(art.get("journal")),
                "year": _year_of(art.get("pubDate", "")),
                "url": art.get("url") or f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "type": "pubmed_search",
                "type_label": "PubMed record (biomarker-intervention search)",
            }
    val = _load_json(LIT_DIR / "long-covid-validation-cache.json", {})
    type_map = {
        "systematic-review": ("systematic_review", "Systematic review"),
        "review": ("other", "Review"),
        "clinical-trial": ("clinical_trial", "Clinical trial publication"),
        "case-series": ("other", "Case series"),
        "case-study": ("other", "Case report"),
        "experimental": ("other", "Experimental study"),
    }
    for key, pmids in (val.get("agentQueries") or {}).items():
        try:
            left, kind = key.split("|", 1)
        except ValueError:
            continue
        agent_slug = left.replace("treatment:", "")
        t, tl = type_map.get(kind, ("other", kind))
        for pmid in pmids or []:
            pmid = _clean(pmid)
            if not pmid:
                continue
            cur = out["long-covid"][agent_slug].get(pmid)
            if cur and cur["type"] != "pubmed_search":
                continue
            out["long-covid"][agent_slug][pmid] = {
                "pmid": pmid,
                "title": "",
                "journal": "",
                "year": None,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "type": t,
                "type_label": tl + " (PubMed validation search)",
            }
    return out


def load_ontology_synonyms() -> dict:
    """lowercased synonym -> treatment slug (for linking literature caches to agents)."""
    out = {}
    ont = _load_json(ONTOLOGY_FILE, {})
    for term in ont.get("terms", []):
        slug = term.get("id", "").replace("treatment:", "")
        if not slug:
            continue
        for syn in [term.get("preferredTerm", "")] + list(term.get("synonyms", [])):
            if syn:
                out[syn.strip().lower()] = slug
    return out


# ---------------------------------------------------------------------------
# Record building
# ---------------------------------------------------------------------------
def _trial_rec(t: dict, sponsor: str = "", conditions=None) -> dict:
    nct = _clean(t.get("nct_id"))
    return {
        "nct_id": nct,
        "title": _clean(t.get("title")),
        "status": _clean(t.get("status")).upper() or "UNKNOWN",
        "phase": _clean(t.get("phase")).upper() or "NA",
        "enrollment": t.get("enrollment") if isinstance(t.get("enrollment"), int) else None,
        "year": t.get("year") if isinstance(t.get("year"), int) else _year_of(t.get("start_date", "")),
        "sponsor": _clean(sponsor),
        "url": t.get("url") or (f"https://clinicaltrials.gov/study/{nct}" if nct else ""),
        "conditions": conditions or [],
    }


def _lit_rec(l: dict) -> dict:
    pmid = _clean(l.get("pmid"))
    t = _clean(l.get("publication_type")) or "other"
    return {
        "pmid": pmid,
        "doi": _clean(l.get("doi")),
        "title": _clean(l.get("title")),
        "journal": _clean(l.get("journal")),
        "year": l.get("year") if isinstance(l.get("year"), int) else _year_of(str(l.get("year", ""))),
        "authors": _clean(l.get("authors")),
        "url": l.get("url") or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""),
        "type": t,
        "type_label": _clean(l.get("publication_type_label")) or t.replace("_", " ").title(),
    }


def score_record(rec: dict) -> dict:
    trial_pts = 0.0
    for t in rec["trials"]:
        trial_pts += TRIAL_STATUS_WEIGHT.get(t["status"], 1.0) + TRIAL_PHASE_BONUS.get(t["phase"], 0.0)
    lit_pts = 0.0
    for l in rec["literature"]:
        lit_pts += LIT_TYPE_WEIGHT.get(l["type"], 1.0)
    trial_pts = min(trial_pts, TRIAL_CAP)
    lit_pts = min(lit_pts, LIT_CAP)
    tier_pts = TIER_POINTS.get(rec["tier"], 0)
    appr = APPROVED_BONUS if rec.get("approved_any") else 0.0
    total = round(trial_pts + lit_pts + tier_pts + appr, 1)
    rec["score"] = total
    rec["score_parts"] = {
        "trials": round(trial_pts, 1),
        "literature": round(lit_pts, 1),
        "tier": tier_pts,
        "approved": appr,
    }
    return rec


def _status_breakdown(trials) -> dict:
    b = Counter()
    for t in trials:
        b[STATUS_GROUP.get(t["status"], "other")] += 1
    return {"total": len(trials), "recruiting": b["recruiting"], "active": b["active"],
            "completed": b["completed"], "other": b["other"]}


def _lit_breakdown(lit) -> dict:
    return dict(Counter(l["type"] for l in lit))


def build_records(verbose: bool = False):
    """Return (conditions, records). Records include every disease x agent pair
    that has at least one trial OR one literature item."""
    disease_labels = load_disease_labels()
    categories = load_categories()
    name_to_slug, flagged, existing_agent_pages = load_agent_slugs()
    pair_tiers = load_pair_tiers()
    lit_by_cond = load_literature_by_slug()
    syn_to_treat = load_ontology_synonyms()

    conditions = {}
    records = []

    # ---- Track 1: disease-intelligence ------------------------------------
    for fp in sorted(DI_DIR.glob("*.json")):
        d = _load_json(fp, {})
        slug = d.get("slug") or fp.stem
        cond = d.get("condition") or {}
        label = _clean(cond.get("name")) or disease_labels.get(slug, {}).get("label") or slug.replace("-", " ").title()
        short = _clean(cond.get("shortName")) or label
        ids = d.get("identifiers") or {}
        page = d.get("page") or {}
        cat = categories.get(slug, {})
        merged = (d.get("therapeutics") or {}).get("merged_ranked") or []
        remission = d.get("remission") or {}
        conditions[slug] = {
            "slug": slug,
            "name": label,
            "short": short,
            "aliases": [a for a in (cond.get("alternateNames") or []) if _clean(a)],
            "mondo_id": _clean(ids.get("mondo_id")) or disease_labels.get(slug, {}).get("mondo_id", ""),
            "track": "chronic",
            "category_id": cat.get("category_id", "chronic-disease"),
            "category_label": cat.get("category_label", "Chronic disease (RepurpOS)"),
            "url": f"/disease-intelligence/{slug}.html",
            "interventions_url": f"/chronic-disease-interventions/{slug}.html" if (ROOT / "chronic-disease-interventions" / f"{slug}.html").exists() else "",
            "n_candidates": len(merged),
            "updated": _clean(page.get("dateModified")) or _clean(remission.get("last_updated")),
            "remission_note": _clean(remission.get("spontaneous_remission_rate")),
            "best_intervention_note": _clean(remission.get("best_intervention_remission_rate")),
        }
        seen = set()
        for e in merged:
            ce = e.get("clinical_evidence") or {}
            trials = [_trial_rec(t) for t in ce.get("clinical_trials") or []]
            lit = [_lit_rec(l) for l in ce.get("literature") or []]
            if not trials and not lit:
                continue
            name = _clean(e.get("name"))
            if not name:
                continue
            aslug = name_to_slug.get(name) or slugify(name)
            if aslug in seen:
                aslug = f"{aslug}-{slugify(e.get('canonical_id') or e.get('chembl_id') or 'x')}"
            seen.add(aslug)
            tier = _clean(e.get("evidence_tier")).upper()[:1] or "D"
            if (slug, aslug) in pair_tiers:
                tier = pair_tiers[(slug, aslug)].get("evidence_tier", tier)
            dtype = _clean(e.get("drug_type_label"))
            display = name.title() if name.isupper() else name
            max_phase = e.get("max_phase")
            rec = {
                "disease_slug": slug,
                "disease_name": label,
                "disease_short": short,
                "agent_slug": aslug,
                "agent_name": display,
                "agent_type": DI_TYPE_MAP.get(dtype, "Other"),
                "agent_type_raw": dtype,
                "mechanism": "" if JUNK_MECH.search(_clean(e.get("mechanism"))) else _clean(e.get("mechanism")),
                "max_phase": max_phase if isinstance(max_phase, (int, float)) else None,
                "phase_label": _clean(e.get("phase_label")),
                "approved_any": (isinstance(max_phase, (int, float)) and max_phase >= 4) or _clean(e.get("phase_label")).lower() == "approved",
                "approved_indications": [_clean(x) for x in (e.get("approved_indications") or []) if _clean(x)],
                "tier": tier,
                "tier_label": TIER_LABEL.get(tier, tier),
                "source_track": "di",
                "sources": [_clean(s) for s in (e.get("sources") or []) if _clean(s)],
                "source_type": _clean(e.get("source_type")),
                "via_alteration": _clean(e.get("via_alteration")),
                "repurposing_signal": bool(e.get("repurposing_signal")),
                "chembl_id": _clean(e.get("chembl_id")),
                "external_links": [l for l in (e.get("external_links") or []) if l.get("url")],
                "search_links": ce.get("search_links") or {},
                "trials": trials,
                "literature": lit,
                "agent_url": f"/agents/{aslug}/" if aslug in existing_agent_pages else "",
                "safety": "",
                "dosing": "",
                "notes": "",
                "aliases": [],
                "last_updated": conditions[slug]["updated"],
            }
            records.append(rec)

    # ---- Track 2: therapeutic_agents.json (post-viral) ---------------------
    ta = _load_json(TA_FILE, {"agents": []})
    ct = {t["nct_id"]: t for t in (_load_json(CT_FILE, {"trials": []}).get("trials") or [])}
    pv_slugs = {v[0] for v in PV_CONDITIONS.values()} | {PV_OTHER[0]}
    for key, (cslug, short, long_name, lit_page) in list(PV_CONDITIONS.items()) + [("__other__", PV_OTHER)]:
        cat = categories.get(cslug, {})
        conditions[cslug] = {
            "slug": cslug,
            "name": long_name,
            "short": short,
            "aliases": [],
            "mondo_id": disease_labels.get(cslug, {}).get("mondo_id", ""),
            "track": "post-viral",
            "category_id": cat.get("category_id", "post-viral"),
            "category_label": cat.get("category_label", "Post-Viral & Complex Chronic Illness"),
            "url": "/" + (cat.get("literature") or lit_page),
            "interventions_url": ("/" + cat["biomarkers"]) if cat.get("biomarkers") else "",
            "n_candidates": 0,
            "updated": _clean(ta.get("last_updated"))[:10],
            "remission_note": "",
            "best_intervention_note": "",
        }

    for a in ta.get("agents", []):
        name = _clean(a.get("Therapeutic Agent"))
        if not name or name in flagged:
            continue
        aslug = name_to_slug.get(name) or slugify(name)
        prim = []
        for c in a.get("Primary Conditions") or []:
            if c in PV_CONDITIONS:
                prim.append(PV_CONDITIONS[c][0])
            elif c.startswith("Other Post-Viral"):
                prim.append(PV_OTHER[0])
        prim = list(dict.fromkeys(prim))
        if not prim:
            continue
        for p in prim:
            conditions[p]["n_candidates"] += 1

        # trials assigned per condition using the current-trials registry map
        trials_by_cond = defaultdict(list)
        for t in a.get("trials") or []:
            nct = _clean(t.get("nct_id"))
            cur = ct.get(nct, {})
            mapped = {CT_CONDITION_MAP.get(m) for m in (cur.get("mapped_conditions") or []) if CT_CONDITION_MAP.get(m)}
            targets = [c for c in prim if c in mapped] if mapped else list(prim)
            if mapped and not targets:
                targets = list(prim)
            merged = dict(t)
            merged.setdefault("url", cur.get("link") or f"https://clinicaltrials.gov/study/{nct}")
            merged.setdefault("enrollment", cur.get("enrollment"))
            rec_t = _trial_rec(merged, sponsor=cur.get("sponsor", ""), conditions=[m for m in (cur.get("mapped_conditions") or [])])
            for c in targets:
                trials_by_cond[c].append(rec_t)

        # literature: curated studies + Key Studies PMIDs + PubMed caches (long covid)
        base_lit = []
        seen_pmids = set()
        for ref in a.get("Key Studies / References") or []:
            m = re.search(r"PMID:?\s*(\d+)", str(ref), re.I)
            if m:
                pm = m.group(1)
                seen_pmids.add(pm)
                base_lit.append({"pmid": pm, "doi": "", "title": "", "journal": "", "year": None, "authors": "",
                                 "url": f"https://pubmed.ncbi.nlm.nih.gov/{pm}/", "type": "curated_reference",
                                 "type_label": "Curated reference"})
        for s in a.get("studies") or []:
            title = _clean(s.get("title"))
            if not title:
                continue
            m = re.search(r"PMID:?\s*(\d+)", title + " " + _clean(s.get("excerpt")), re.I)
            pm = m.group(1) if m else ""
            if pm and pm in seen_pmids:
                continue
            if pm:
                seen_pmids.add(pm)
            base_lit.append({"pmid": pm, "doi": "", "title": title[:240], "journal": _clean(s.get("source")),
                             "year": _year_of(s.get("pub_date", "")) or _year_of(title), "authors": "",
                             "url": f"https://pubmed.ncbi.nlm.nih.gov/{pm}/" if pm else "",
                             "type": "curated_reference", "type_label": "Curated reference (" + (_clean(s.get("source")) or "OSMF") + ")"})

        types = [TA_TYPE_MAP.get(t, "Other") for t in (a.get("types") or [])]
        agent_type = next((t for t in types if t != "Other"), "Other")
        mech_items = [m for m in (a.get("mechanisms") or []) if not JUNK_MECH.search(_clean(m))]
        mech = _clean(a.get("Proposed Mechanism"))
        if JUNK_MECH.search(mech):
            mech = "; ".join(mech_items)
        ev = _clean(a.get("Evidence Level"))
        tier = {"Strong": "A", "Moderate": "B", "Preliminary": "C", "Anecdotal": "D"}.get(ev, "D")
        treat_slug = syn_to_treat.get(name.lower()) or aslug

        for cslug in prim:
            lit = list(base_lit)
            cache = lit_by_cond.get(cslug, {}).get(treat_slug) or lit_by_cond.get(cslug, {}).get(aslug) or {}
            for pm, item in cache.items():
                if pm in seen_pmids:
                    continue
                lit.append({"pmid": pm, "doi": "", "title": item["title"], "journal": item["journal"],
                            "year": item["year"], "authors": "", "url": item["url"],
                            "type": item["type"], "type_label": item["type_label"]})
            trials = trials_by_cond.get(cslug, [])
            if not trials and not lit:
                continue
            t_pair = pair_tiers.get((cslug, aslug))
            c = conditions[cslug]
            rec = {
                "disease_slug": cslug,
                "disease_name": c["name"],
                "disease_short": c["short"],
                "agent_slug": aslug,
                "agent_name": name,
                "agent_type": agent_type,
                "agent_type_raw": ", ".join(a.get("types") or []),
                "mechanism": mech,
                "max_phase": None,
                "phase_label": "Investigational",
                "approved_any": False,
                "approved_indications": [],
                "tier": t_pair.get("evidence_tier", tier) if t_pair else tier,
                "tier_label": TIER_LABEL.get(t_pair.get("evidence_tier", tier) if t_pair else tier, ev),
                "source_track": "ta",
                "sources": ["OSMF therapeutic agent database", "ClinicalTrials.gov"] + (["PubMed"] if lit else []),
                "source_type": "",
                "via_alteration": "",
                "repurposing_signal": False,
                "chembl_id": "",
                "external_links": ([{"label": "PubChem", "url": a["PubChem"]}] if _clean(a.get("PubChem")) else []),
                "search_links": {
                    "clinicaltrials_gov": f"https://clinicaltrials.gov/search?cond={c['short'].replace(' ', '+')}&intr={name.replace(' ', '+')}",
                    "pubmed": f"https://pubmed.ncbi.nlm.nih.gov/?term={name.replace(' ', '+')}+AND+{c['short'].replace(' ', '+').replace('/', '')}",
                },
                "trials": trials,
                "literature": lit,
                "agent_url": f"/agents/{aslug}/" if aslug in existing_agent_pages else "",
                "safety": _clean(a.get("Safety")),
                "dosing": _clean(a.get("Dosing")),
                "notes": _clean(a.get("Clinical Notes")),
                "aliases": [_clean(x) for x in (a.get("aliases") or []) if _clean(x)],
                "last_updated": _clean(a.get("Last Updated")) or c["updated"],
            }
            records.append(rec)

    for rec in records:
        rec["trial_breakdown"] = _status_breakdown(rec["trials"])
        rec["lit_breakdown"] = _lit_breakdown(rec["literature"])
        rec["has_recruiting"] = rec["trial_breakdown"]["recruiting"] > 0
        rec["pair_eligible"] = bool(rec["trials"]) or len(rec["literature"]) >= 2
        rec["pair_url"] = f"/pairs/{rec['disease_slug']}/{rec['agent_slug']}.html" if rec["pair_eligible"] else ""
        score_record(rec)

    records.sort(key=lambda r: (r["disease_slug"], -r["score"], r["agent_name"].lower()))
    if verbose:
        n_di = sum(1 for r in records if r["source_track"] == "di")
        print(f"records: {len(records)} ({n_di} disease-intelligence, {len(records) - n_di} post-viral) across {len(conditions)} conditions")
    return conditions, records


if __name__ == "__main__":
    build_records(verbose=True)
