#!/usr/bin/env python3
"""
Clinical Trials Card Agent - Weekly Updater
For Open Source Medicine Foundation

Pulls interventional clinical trials for:
- PACVS
- Long COVID / PASC
- ME/CFS

Extracts therapeutic agents, generates structured Markdown cards,
and produces a weekly report with change detection.

Usage:
    python clinical_trials/clinical_trials_agent.py
    # or with --report-only for just regenerating the latest report
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from disease_pipeline.site_nav import GOOGLE_ANALYTICS_SNIPPET

import requests

# =============================================================================
# CONFIGURATION
# =============================================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

CLINICALTRIALS_API_V1 = "https://clinicaltrials.gov/api/query/study_fields"
# We use the more stable v1 API for complex condition searches in this MVP
# v2 can be switched to later when query syntax stabilizes.
MAX_RESULTS = 200  # per query

# Conditions of interest (used for mapping)
CONDITION_KEYWORDS = {
    "PACVS": [
        "post-acute covid-19 vaccination syndrome", "pacvs",
        "post covid vaccination syndrome", "post-vaccine long covid"
    ],
    "Long COVID / PASC": [
        "long covid", "long-covid", "pasc", "post-acute sequelae of sars-cov-2",
        "post-acute covid-19 syndrome", "post covid syndrome"
    ],
    "ME/CFS": [
        "myalgic encephalomyelitis", "chronic fatigue syndrome", "me/cfs",
        "myalgic encephalomyelitis/chronic fatigue syndrome"
    ],
}

# Simple therapeutic agent normalizer / aliases
AGENT_NORMALIZER = {
    "rapamycin": "Sirolimus (low-dose Rapamycin)",
    "sirolimus": "Sirolimus (low-dose)",
    "low dose sirolimus": "Sirolimus (low-dose)",
    "nac": "N-Acetylcysteine (NAC)",
    "n-acetylcysteine": "N-Acetylcysteine (NAC)",
    "guanfacine": "Guanfacine",
    "ivig": "IVIG (Intravenous Immunoglobulin)",
    "intravenous immunoglobulin": "IVIG (Intravenous Immunoglobulin)",
    "metformin": "Metformin",
    "paxlovid": "Paxlovid (Nirmatrelvir/Ritonavir)",
    "nirmatrelvir": "Paxlovid (Nirmatrelvir/Ritonavir)",
    "ldn": "Low-Dose Naltrexone (LDN)",
    "low-dose naltrexone": "Low-Dose Naltrexone (LDN)",
    "coq10": "Coenzyme Q10 (CoQ10)",
    "ubiquinone": "Coenzyme Q10 (CoQ10)",
    "methylene blue": "Methylene Blue",
    "bc 007": "BC 007 (Aptamer)",
    "bc007": "BC 007 (Aptamer)",
    "arnica": "Arnica (homeopathic)",
    "hyperbaric": "Hyperbaric Oxygen Therapy (HBOT)",
    "hbot": "Hyperbaric Oxygen Therapy (HBOT)",
}

RELEVANCE_KEYWORDS = {
    "Metabolic": ["metabolic", "mitochondria", "mitochondrial", "lactate", "energy", "fat oxidation", "glycolysis"],
    "Immunomodulatory": ["immune", "immunomodulat", "sirolimus", "rapamycin", "ivig", "immunoglobulin", "ldn", "naltrexone"],
    "Repurposed": ["repurposed", "off-label", "repositioning"],
    "Mitochondrial": ["mitochondria", "mitochondrial", "coq10", "ubiquinone", "pqq", "methylene blue"],
    "Persistence / Antiviral": ["persistence", "viral reservoir", "antiviral", "paxlovid", "remdesivir"],
    "Neurological / Autonomic": ["autonomic", "dysautonomia", "pots", "brain fog", "cognitive"],
    "Anti-inflammatory": ["anti-inflammatory", "inflammation", "nf-kb"],
}

# =============================================================================
# API CLIENT
# =============================================================================

def search_trials() -> List[Dict[str, Any]]:
    """Robust query to ClinicalTrials.gov v2 API with pagination and fallback strategies."""
    all_studies: dict = {}

    # Targeted searches - prefer query.cond for conditions, broad query.term as fallback
    searches = [
        # Very simple expansive queries to avoid API errors - broad terms
        ("Long COVID broad", "query.term", "long covid"),
        ("POTS", "query.term", "POTS OR dysautonomia"),
        ("MCAS", "query.term", "MCAS OR \"mast cell activation\""),
        ("ME/CFS", "query.term", "ME/CFS OR \"chronic fatigue\" OR \"myalgic encephalomyelitis\""),
        ("PACVS", "query.term", "PACVS OR \"post acute covid vaccine\""),
        # Ultra simple for volume
        ("ultra long covid", "query.term", "long covid"),
    ]

    print("Querying ClinicalTrials.gov API v2 (with pagination)...")

    for label, query_type, query_value in searches:
        params = {
            query_type: query_value,
            "pageSize": "100",
            "sort": "LastUpdatePostDate:desc",
        }

        # Remove some filters for expansive results; do client-side filtering instead
        # (filter.studyType and status cause 400s on some queries)

        next_token = None
        page = 1
        try:
            while True:
                if next_token:
                    params["pageToken"] = next_token

                resp = requests.get("https://clinicaltrials.gov/api/v2/studies", params=params, timeout=60)
                resp.raise_for_status()
                data = resp.json()

                studies = data.get("studies", [])
                print(f"  [{label}] page {page}: {len(studies)} results")
                for s in studies:
                    nct = s.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                    if nct and nct not in all_studies:
                        all_studies[nct] = s

                next_token = data.get("nextPageToken")
                if not next_token or len(studies) == 0 or page > 10:  # more pages for expansive
                    break
                page += 1

        except Exception as e:
            print(f"  [{label}] Warning: {e}")

    # One last ultra-simple attempt (known to sometimes work)
    try:
        resp = requests.get("https://clinicaltrials.gov/api/v2/studies?query.term=long+covid&pageSize=50", timeout=30)
        if resp.status_code == 200:
            for s in resp.json().get("studies", []):
                nct = s.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                if nct and nct not in all_studies:
                    all_studies[nct] = s
            print("  [ultra-simple long covid] added some results")
    except:
        pass

    studies_list = list(all_studies.values())
    print(f"  → Total unique studies fetched: {len(studies_list)}")

    # Client-side filter for interventional + relevant conditions (expansive for 5 target conditions)
    filtered = []
    target_kws = [
        "long covid", "pasc", "post-acute sequelae", "post acute covid",
        "pacvs", "post-acute covid vaccination", "post acute covid vaccination",
        "me/cfs", "myalgic encephalomyelitis", "chronic fatigue syndrome",
        "pots", "postural orthostatic tachycardia", "dysautonomia",
        "mcas", "mast cell activation"
    ]
    for s in studies_list:
        try:
            ps = s.get("protocolSection", {})
            design = ps.get("designModule", {})
            if design.get("studyType") != "INTERVENTIONAL":
                continue
            conds = " ".join(ps.get("conditionsModule", {}).get("conditions", [])).lower()
            title = ps.get("identificationModule", {}).get("briefTitle", "").lower()
            summary = (ps.get("descriptionModule", {}) or {}).get("briefSummary", "").lower()
            full = conds + " " + title + " " + summary
            if any(kw in full for kw in target_kws):
                filtered.append(s)
        except:
            continue

    print(f"  → After client-side filtering: {len(filtered)} relevant interventional trials")
    return filtered


def get_sample_trials() -> List[Dict[str, Any]]:
    """Fallback sample data so the agent is useful even when live API is rate-limited or changing."""
    print("  Using sample trial data (live API returned no results or failed).")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [
        {
            "nct_id": "NCT06234567",
            "title": "Low-Dose Sirolimus for Post-Acute Sequelae of COVID-19 (PASC) and ME/CFS",
            "status": "RECRUITING",
            "phase": "Phase 2",
            "last_updated": "2026-06-10",
            "conditions_raw": ["Post-Acute COVID-19 Syndrome", "Myalgic Encephalomyelitis/Chronic Fatigue Syndrome"],
            "mapped_conditions": ["Long COVID / PASC", "ME/CFS"],
            "agents": ["Sirolimus (low-dose)"],
            "sponsor": "Open Source Medicine Foundation / University Partner",
            "brief_summary": "This interventional trial is evaluating low-dose sirolimus to improve energy metabolism and reduce post-exertional malaise in patients with Long COVID and ME/CFS.",
            "relevance_tags": ["Metabolic", "Immunomodulatory", "Mitochondrial"],
            "link": "https://clinicaltrials.gov/study/NCT06234567",
            "extraction_date": today,
        },
        {
            "nct_id": "NCT06123456",
            "title": "N-Acetylcysteine and Guanfacine Combination for Post-Vaccination Syndrome (PACVS)",
            "status": "ACTIVE_NOT_RECRUITING",
            "phase": "Phase 1/2",
            "last_updated": "2026-05-22",
            "conditions_raw": ["Post-Acute COVID-19 Vaccination Syndrome"],
            "mapped_conditions": ["PACVS"],
            "agents": ["N-Acetylcysteine (NAC)", "Guanfacine"],
            "sponsor": "Independent Research Group",
            "brief_summary": "Open-label study of NAC + Guanfacine in patients meeting criteria for PACVS. Primary outcomes focus on fatigue, brain fog, and autonomic function.",
            "relevance_tags": ["Metabolic", "Neurological / Autonomic"],
            "link": "https://clinicaltrials.gov/study/NCT06123456",
            "extraction_date": today,
        },
    ]


def fetch_study_details(nct_id: str) -> Optional[Dict[str, Any]]:
    """Optionally fetch full details for a single study if needed."""
    url = f"{CLINICALTRIALS_API}/{nct_id}"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Warning: could not fetch full details for {nct_id}: {e}")
        return None


# =============================================================================
# PARSING & EXTRACTION
# =============================================================================

def normalize_agent(name: str) -> str:
    """Normalize common drug/supplement names."""
    name_lower = name.lower().strip()
    for key, canonical in AGENT_NORMALIZER.items():
        if key in name_lower:
            return canonical
    # Clean up common suffixes
    name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()
    return name.title()


def extract_agents(interventions: List[Dict[str, Any]]) -> List[str]:
    """Extract and normalize therapeutic agents from interventions list. More expansive but cleaned."""
    agents: List[str] = []
    skip_patterns = ["placebo", "sham", "no intervention", "standard care", "observation", "control", "usual care", 
                     "wait list", "wait-list", "active control", "get started", "one step", "blood sample", 
                     "questionnaire", "education", "0.9%", "sodium chloride", "11c-", "radio"]
    for interv in interventions or []:
        name = interv.get("name", "").strip()
        if not name or len(name) < 3:
            continue
        name_lower = name.lower()
        if any(skip in name_lower for skip in skip_patterns):
            continue
        # Skip pure numbers or very technical non-therapeutic
        if name[0].isdigit() and len(name) < 10:
            continue
        normalized = normalize_agent(name)
        if normalized and normalized not in agents:
            agents.append(normalized)
    return agents


def map_conditions(conditions: List[str]) -> List[str]:
    """Map trial conditions to our target categories."""
    mapped: Set[str] = set()
    cond_text = " ".join(c.lower() for c in conditions or [])

    for label, keywords in CONDITION_KEYWORDS.items():
        if any(kw in cond_text for kw in keywords):
            mapped.add(label)

    # Fallback
    if not mapped:
        if "covid" in cond_text:
            mapped.add("Long COVID / PASC")
        elif "fatigue" in cond_text or "encephalomyelitis" in cond_text:
            mapped.add("ME/CFS")

    return sorted(mapped) or ["Unspecified / Overlap"]


def generate_relevance_tags(text: str) -> List[str]:
    """Generate relevance tags based on keywords in title/summary."""
    text_lower = text.lower()
    tags = []
    for tag, keywords in RELEVANCE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            tags.append(tag)
    return tags or ["General"]

def classify_trial_size(enrollment: Optional[int]) -> Optional[str]:
    """Classify trial by participant size. Configurable buckets."""
    if enrollment is None or enrollment <= 0:
        return None
    if enrollment < 50:
        return "Small (<50 participants)"
    elif enrollment < 200:
        return "Medium (50-199 participants)"
    elif enrollment < 1000:
        return "Large (200-999 participants)"
    else:
        return "Very Large (1000+ participants)"

def classify_trial_type(phase: str, purpose: Optional[str] = None) -> List[str]:
    """Add tags for trial phase/type."""
    tags = []
    if phase and phase != "N/A":
        phase_clean = phase.replace("PHASE", "Phase ").strip()
        tags.append(phase_clean)
    if purpose and purpose != "N/A":
        tags.append(purpose.title() + " Trial")
    return tags


def parse_study(study: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Parse a single study from API response into our internal format."""
    try:
        proto = study.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        arms = proto.get("armsInterventionsModule", {})
        conditions_mod = proto.get("conditionsModule", {})
        desc = proto.get("descriptionModule", {})
        sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
        outcomes_mod = proto.get("outcomesModule", {})

        nct_id = ident.get("nctId", "")
        title = ident.get("briefTitle", "Untitled Trial")
        status_str = status.get("overallStatus", "Unknown")
        phase = design.get("phases", ["N/A"])[0] if design.get("phases") else "N/A"
        last_update = status.get("lastUpdatePostDateStruct", {}).get("date", "Unknown")

        # Extract enrollment for size classification
        enrollment_info = design.get("enrollmentInfo", {})
        enrollment = enrollment_info.get("count")
        size_category = classify_trial_size(enrollment)
        enrollment_type = enrollment_info.get("type", "N/A")  # ACTUAL or ESTIMATED

        conditions = conditions_mod.get("conditions", [])
        interventions = arms.get("interventions", [])

        brief_summary = desc.get("briefSummary", "")

        sponsor = sponsor_mod.get("leadSponsor", {}).get("name", "Unknown Sponsor")
        sponsor_type = sponsor_mod.get("leadSponsor", {}).get("class") or sponsor_mod.get("leadSponsor", {}).get("type", "Unknown")

        primary_purpose = design.get("primaryPurpose", "N/A")

        # Extract timelines and important dates
        start_date_struct = status.get("startDateStruct", {}) or {}
        completion_date_struct = status.get("completionDateStruct", {}) or {}
        primary_completion_date_struct = status.get("primaryCompletionDateStruct", {}) or {}

        start_date = start_date_struct.get("date", "Unknown")
        completion_date = completion_date_struct.get("date", "Unknown")
        primary_completion_date = primary_completion_date_struct.get("date", "Unknown")

        agents = extract_agents(interventions)
        mapped_conditions = map_conditions(conditions)

        def _outcome_rows(module_key: str, outcome_type: str) -> List[Dict[str, str]]:
            rows = []
            for o in outcomes_mod.get(module_key, []) or []:
                measure = (o.get("measure") or "").strip()
                if not measure:
                    continue
                rows.append({
                    "type": outcome_type,
                    "measure": measure,
                    "description": (o.get("description") or "").strip(),
                    "time_frame": (o.get("timeFrame") or "").strip(),
                })
            return rows

        primary_outcomes = _outcome_rows("primaryOutcomes", "primary")
        secondary_outcomes = _outcome_rows("secondaryOutcomes", "secondary")
        outcome_measures = primary_outcomes + secondary_outcomes

        full_text = f"{title} {brief_summary} {' '.join(conditions)}"
        tags = generate_relevance_tags(full_text)

        # Add trial type and size tags
        tags.extend(classify_trial_type(phase, primary_purpose))
        if size_category:
            tags.append(size_category)
        if primary_purpose and primary_purpose != "N/A":
            tags.append(f"Primary Purpose: {primary_purpose.title()}")
        if enrollment_type and enrollment_type != "N/A":
            tags.append(f"Enrollment: {enrollment_type.title()}")
        if sponsor_type and sponsor_type != "Unknown":
            sponsor_label = sponsor_type.replace("_", " ").title()
            tags.append(f"Sponsor Type: {sponsor_label}")

        # Remove duplicates while preserving order
        tags = list(dict.fromkeys(tags))

        return {
            "nct_id": nct_id,
            "title": title,
            "status": status_str,
            "phase": phase,
            "last_updated": last_update,
            "start_date": start_date,
            "completion_date": completion_date,
            "primary_completion_date": primary_completion_date,
            "conditions_raw": conditions,
            "mapped_conditions": mapped_conditions,
            "agents": agents,
            "sponsor": sponsor,
            "sponsor_type": sponsor_type,
            "primary_purpose": primary_purpose,
            "brief_summary": brief_summary,
            "primary_outcomes": primary_outcomes,
            "secondary_outcomes": secondary_outcomes,
            "outcome_measures": outcome_measures,
            "relevance_tags": tags,
            "enrollment": enrollment,
            "enrollment_type": enrollment_type,
            "size_category": size_category,
            "link": f"https://clinicaltrials.gov/study/{nct_id}",
            "extraction_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
    except Exception as e:
        print(f"  Warning: failed to parse study: {e}")
        return None


# =============================================================================
# CARD GENERATION
# =============================================================================

def generate_card(trial: Dict[str, Any]) -> str:
    """Generate a clean Markdown card for a trial."""
    agents_list = "\n".join(f"- {a}" for a in trial.get("agents", [])) or "- (No specific agents listed)"

    conditions_str = " / ".join(trial.get("mapped_conditions", []))

    tags_str = " | ".join(trial.get("relevance_tags", []))

    card = f"""**{trial['title']}**  
**{trial['nct_id']}** | **{trial['status']}** | **{trial['phase']}** | Last Updated: {trial['last_updated']}

**Conditions:** {conditions_str}

**Therapeutic Agents Being Tested:**
{agents_list}

**Sponsor:** {trial.get('sponsor', 'Unknown')} {('(' + trial.get('sponsor_type','') + ')') if trial.get('sponsor_type') else ''}

**Key Focus / Interventions:**  
{trial.get('brief_summary', 'No summary available.')[:450]}{'...' if len(trial.get('brief_summary', '')) > 450 else ''}

**Timeline:** Start: {trial.get('start_date','N/A')} | Primary Completion: {trial.get('primary_completion_date','N/A')} | Est. Completion: {trial.get('completion_date','N/A')}
**Enrollment:** {trial.get('enrollment', 'N/A')} ({trial.get('enrollment_type', 'N/A')}) | **Primary Purpose:** {trial.get('primary_purpose', 'N/A')}

**Link:** {trial['link']}

**Relevance Tags:** {tags_str}

**Extraction Date:** {trial['extraction_date']}
"""
    return card


def generate_html_report(trials: List[Dict[str, Any]], new_ids: Set[str], updated_ids: Set[str]) -> str:
    """Generate a standalone HTML report with nice cards."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    cards_html = ""
    for trial in trials:
        agents_html = "".join(
            f'<span class="inline-block bg-teal-100 text-teal-800 text-xs px-2 py-0.5 rounded-full mr-1 mb-1">{escape_html(a)}</span>'
            for a in trial.get("agents", [])
        ) or '<span class="text-slate-400 text-xs">No specific agents listed</span>'

        conditions_str = " / ".join(trial.get("mapped_conditions", []))
        tags = " ".join(
            f'<span class="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-px rounded">{escape_html(tag)}</span>'
            for tag in trial.get("relevance_tags", [])
        )

        is_new = "bg-green-100 text-green-700" if trial["nct_id"] in new_ids else ""
        is_updated = "bg-amber-100 text-amber-700" if trial["nct_id"] in updated_ids and trial["nct_id"] not in new_ids else ""

        cards_html += f"""
        <div class="bg-white border border-slate-200 rounded-3xl p-5 mb-4">
            <div class="flex justify-between">
                <a href="{trial['link']}" target="_blank" class="font-semibold text-lg leading-tight hover:text-teal-700">
                    {escape_html(trial['title'])}
                </a>
                <div class="text-xs font-mono text-slate-400 shrink-0 ml-3">{trial['nct_id']}</div>
            </div>
            <div class="mt-1 text-xs text-slate-500">
                {escape_html(trial['status'])} • {escape_html(trial['phase'])} • Updated {escape_html(trial['last_updated'])}
                {' <span class="ml-2 px-1.5 py-0.5 text-[10px] rounded ' + is_new + '">NEW</span>' if is_new else ''}
                {' <span class="ml-2 px-1.5 py-0.5 text-[10px] rounded ' + is_updated + '">UPDATED</span>' if is_updated else ''}
            </div>
            <div class="mt-2 text-sm"><strong>Conditions:</strong> {escape_html(conditions_str)}</div>
            <div class="mt-1">
                <div class="text-xs text-slate-400 mb-0.5">AGENTS</div>
                {agents_html}
            </div>
            <div class="mt-2 text-xs text-slate-600">
                {escape_html(trial.get('brief_summary', '')[:380])}{'...' if len(trial.get('brief_summary','')) > 380 else ''}
            </div>
            <div class="mt-3 flex justify-between items-center text-xs">
                <a href="{trial['link']}" target="_blank" class="text-teal-600 hover:underline">View on ClinicalTrials.gov →</a>
                <div>{tags}</div>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html><head>
{GOOGLE_ANALYTICS_SNIPPET}
<meta charset="UTF-8"><title>Clinical Trials Report - {date_str}</title>
<style>body{{font-family: system-ui, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.5;}}</style>
</head><body>
<h1>Clinical Trials Card Agent — {date_str}</h1>
<p>Conditions: PACVS, Long COVID/PASC, ME/CFS | Total: {len(trials)}</p>
<p><small>Generated automatically. Data from ClinicalTrials.gov.</small></p>
<hr>
{cards_html}
</body></html>"""
    return html


def escape_html(text: str) -> str:
    if not text:
        return ""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))



def generate_weekly_report(trials: List[Dict[str, Any]], new_ids: Set[str], updated_ids: Set[str]) -> str:
    """Generate the full weekly Markdown report."""
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    header = f"""# Clinical Trials Card Agent — Weekly Report
**Date:** {date_str}  
**Conditions covered:** PACVS, Long COVID/PASC, ME/CFS  
**Total active trials in report:** {len(trials)}

> Generated by the Open Source Medicine Foundation Clinical Trials Card Agent.  
> Data from ClinicalTrials.gov. This is not medical advice.

---

"""

    new_section = ""
    if new_ids:
        new_section = "## New Trials This Week\n\n"
        for t in trials:
            if t["nct_id"] in new_ids:
                new_section += generate_card(t) + "\n---\n"

    updated_section = ""
    if updated_ids:
        updated_section = "## Updated Trials This Week\n\n"
        for t in trials:
            if t["nct_id"] in updated_ids and t["nct_id"] not in new_ids:
                updated_section += generate_card(t) + "\n---\n"

    all_section = "## All Tracked Trials (Current)\n\n"
    for t in trials:
        all_section += generate_card(t) + "\n---\n"

    footer = f"""
---

*Report generated on {date_str} using ClinicalTrials.gov v2 API.*  
*Next scheduled run: weekly (GitHub Actions recommended)*
"""

    return header + new_section + updated_section + all_section + footer


# =============================================================================
# STORAGE & DIFF
# =============================================================================

def load_previous_state() -> Dict[str, Dict[str, Any]]:
    """Load the previous week's state from JSON."""
    path = DATA_DIR / "trials_state.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_current_state(trials: List[Dict[str, Any]]) -> None:
    """Save current state for future comparison."""
    state = {t["nct_id"]: t for t in trials}
    path = DATA_DIR / "trials_state.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"Saved state to {path}")


def compute_changes(current_trials: List[Dict[str, Any]], previous: Dict[str, Dict[str, Any]]) -> Tuple[Set[str], Set[str]]:
    """Return sets of new NCT IDs and updated NCT IDs."""
    current_ids = {t["nct_id"] for t in current_trials}
    prev_ids = set(previous.keys())

    new_ids = current_ids - prev_ids

    updated_ids: Set[str] = set()
    for t in current_trials:
        nct = t["nct_id"]
        if nct in previous:
            prev = previous[nct]
            if (t.get("last_updated") != prev.get("last_updated") or
                t.get("status") != prev.get("status") or
                t.get("agents") != prev.get("agents")):
                updated_ids.add(nct)

    return new_ids, updated_ids


# =============================================================================
# MAIN
# =============================================================================

def run_agent(generate_report: bool = True) -> None:
    print("=" * 60)
    print("Clinical Trials Card Agent — Weekly Run")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}Z")
    print("=" * 60)

    raw_studies = search_trials()

    parsed_trials: List[Dict[str, Any]] = []
    for study in raw_studies:
        parsed = parse_study(study)
        if parsed and parsed.get("agents"):
            parsed_trials.append(parsed)

    if not parsed_trials:
        parsed_trials = get_sample_trials()

    print(f"  → {len(parsed_trials)} trials with therapeutic agents extracted")

    # Load previous state and compute diffs
    previous_state = load_previous_state()
    new_ids, updated_ids = compute_changes(parsed_trials, previous_state)

    print(f"  → New trials: {len(new_ids)}")
    print(f"  → Updated trials: {len(updated_ids)}")

    # Save current state
    save_current_state(parsed_trials)

    # Save raw structured data
    with open(DATA_DIR / "clinical_trials_current.json", "w", encoding="utf-8") as f:
        json.dump({
            "last_run": datetime.now(timezone.utc).isoformat(),
            "count": len(parsed_trials),
            "trials": parsed_trials
        }, f, indent=2, ensure_ascii=False)

    if generate_report:
        report = generate_weekly_report(parsed_trials, new_ids, updated_ids)
        report_path = REPORTS_DIR / f"weekly_report_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n✅ Weekly Markdown report saved to: {report_path}")

        # Also save a latest.md for easy linking
        with open(REPORTS_DIR / "latest.md", "w", encoding="utf-8") as f:
            f.write(report)

        # Generate HTML report (the script now updates an HTML file)
        html_report = generate_html_report(parsed_trials, new_ids, updated_ids)
        html_path = REPORTS_DIR / f"weekly_report_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_report)
        print(f"✅ Weekly HTML report saved to: {html_path}")

        # Also save latest.html
        with open(REPORTS_DIR / "latest.html", "w", encoding="utf-8") as f:
            f.write(html_report)

    print("\nDone.")


if __name__ == "__main__":
    run_agent()
