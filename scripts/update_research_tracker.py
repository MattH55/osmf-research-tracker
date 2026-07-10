#!/usr/bin/env python3
"""
Research Tracker Updater for Open Source Medicine Foundation
Queries PubMed daily via pymed and updates per-condition JSON files in data/.
"""

import json
import os
import re
import time
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pymed import PubMed
except ImportError:
    print("ERROR: pymed not installed. Run: pip install pymed")
    raise

# Output directory (repo root data/, not scripts/data/)
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# PubMed configuration
PUBMED_TOOL = "OSMF-ResearchTracker"
PUBMED_EMAIL = "research@opensourcemed.info"  # Update if needed; public use only

# Max results per condition (keep reasonable to avoid huge files + rate limits)
MAX_RESULTS = 75

# Condition definitions: filename stem -> config
CONDITIONS = {
    "pacvs": {
        "display_name": "PACVS – Post-Acute COVID-19 Vaccination Syndrome",
        "short_name": "PACVS",
        "query": (
            '(PACVS OR "post-acute COVID-19 vaccination syndrome" OR "post COVID vaccination syndrome" OR '
            '("COVID-19 vaccination" AND ("chronic" OR "post-acute" OR sequelae OR "post-vaccination" OR "long term")) AND (syndrome OR fatigue OR illness))'
        ),
        "description": "Peer-reviewed studies on Post-Acute COVID-19 Vaccination Syndrome and related post-vaccination chronic sequelae.",
    },
    "me-cfs": {
        "display_name": "ME/CFS – Myalgic Encephalomyelitis / Chronic Fatigue Syndrome",
        "short_name": "ME/CFS",
        "query": (
            '("myalgic encephalomyelitis" OR "chronic fatigue syndrome" OR "ME/CFS" OR '
            '"myalgic encephalomyelitis/chronic fatigue syndrome")'
        ),
        "description": "Studies on Myalgic Encephalomyelitis/Chronic Fatigue Syndrome (ME/CFS), including diagnostic criteria, mechanisms, and treatments.",
    },
    "long-covid": {
        "display_name": "Long COVID – Post-Acute Sequelae of COVID-19",
        "short_name": "Long COVID",
        "query": (
            '("long covid" OR "long-covid" OR "post-acute sequelae of COVID-19" OR PASC OR '
            '"post-acute COVID-19 syndrome" OR "long hauler" OR ("post-COVID" AND (syndrome OR fatigue OR sequelae)))'
        ),
        "description": "Research on Long COVID (PASC), the post-acute sequelae following SARS-CoV-2 infection.",
    },
    "lyme": {
        "display_name": "Chronic Lyme / PTLDS – Post-Treatment Lyme Disease Syndrome",
        "short_name": "Chronic Lyme / PTLDS",
        "query": (
            '("post-treatment Lyme disease syndrome" OR PTLDS OR "chronic Lyme disease" OR '
            '("Lyme disease" AND ("post-treatment" OR "post treatment" OR chronic)))'
        ),
        "description": "Studies on Chronic Lyme disease and Post-Treatment Lyme Disease Syndrome (PTLDS).",
    },
    "gulf-war-illness": {
        "display_name": "Gulf War Illness – Gulf War Illness (GWI)",
        "short_name": "Gulf War Illness",
        "query": (
            '("gulf war illness" OR "gulf war syndrome" OR "gulf war veteran illness" OR '
            '("Persian Gulf" AND veteran AND (illness OR syndrome OR "unexplained illness")))'
        ),
        "description": "Peer-reviewed literature on Gulf War Illness (GWI) affecting veterans of the 1990-91 Gulf War.",
    },
    "other-post-viral": {
        "display_name": "Other Post-Viral & Post-Infectious Syndromes",
        "short_name": "Other Post-Viral",
        "query": (
            '(("post-viral" OR "post viral" OR "post-infectious" OR "post infectious") AND '
            '(syndrome OR fatigue OR illness OR encephalomyelitis OR "chronic fatigue")) NOT '
            '(COVID OR "SARS-CoV-2" OR "SARS CoV" OR coronavirus OR "long covid" OR PASC OR '
            '"gulf war" OR lyme OR "gulf war illness")'
        ),
        "description": "Research on other post-viral and post-infectious syndromes (non-COVID, non-Lyme, non-GWI).",
    },
    "pots": {
        "display_name": "POTS – Postural Orthostatic Tachycardia Syndrome",
        "short_name": "POTS",
        "query": (
            '("postural orthostatic tachycardia syndrome" OR "postural tachycardia syndrome" OR '
            '("POTS" AND (dysautonomia OR orthostatic OR autonomic OR tachycardia)))'
        ),
        "description": "Studies on POTS, dysautonomia, and orthostatic intolerance.",
    },
    "mcas": {
        "display_name": "MCAS – Mast Cell Activation Syndrome",
        "short_name": "MCAS",
        "query": (
            '("mast cell activation syndrome" OR MCAS OR "mast cell activation" OR '
            '("mast cell" AND (activation OR mediator OR histamine)))'
        ),
        "description": "Research on Mast Cell Activation Syndrome and mast cell mediator disorders.",
    },
}


def parse_pub_date(pub_date: Any) -> Optional[str]:
    """Convert various pymed pub date formats to YYYY-MM-DD or YYYY-MM."""
    if not pub_date:
        return None
    if isinstance(pub_date, (date, datetime)):
        return pub_date.isoformat()[:10]
    if isinstance(pub_date, str):
        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m", "%Y/%m", "%b %Y", "%B %Y", "%Y"):
            try:
                dt = datetime.strptime(pub_date.strip(), fmt)
                return dt.strftime("%Y-%m-%d") if "%d" in fmt else dt.strftime("%Y-%m")
            except ValueError:
                continue
        # Fallback: extract year at minimum
        match = re.search(r"\b(19|20)\d{2}\b", pub_date)
        if match:
            return match.group(0)
    return None


def get_authors_string(authors: Any, max_authors: int = 4) -> str:
    """Format authors list into a readable string, truncating long lists."""
    if not authors:
        return "Authors not listed"
    names = []
    for a in authors:
        if isinstance(a, dict):
            last = a.get("lastname") or a.get("last_name") or ""
            fore = a.get("firstname") or a.get("fore_name") or ""
            name = f"{last}, {fore}".strip(", ").strip()
            if name:
                names.append(name)
        elif isinstance(a, str):
            names.append(a)
    if not names:
        return "Authors not listed"
    if len(names) > max_authors:
        return ", ".join(names[:max_authors]) + " et al."
    return ", ".join(names)


def extract_article_data(article: Any) -> Optional[Dict[str, Any]]:
    """Extract normalized fields from a pymed Article object."""
    try:
        raw_pmid = str(getattr(article, "pubmed_id", "")).strip()
        # pymed occasionally returns multiple ids separated by newlines or spaces for some records.
        # Take the first clean numeric PMID.
        pmid = ""
        for part in re.split(r'[\s\n,]+', raw_pmid):
            part = part.strip()
            if part.isdigit():
                pmid = part
                break
        if not pmid:
            return None

        title = (getattr(article, "title", "") or "").strip()
        if not title:
            return None

        journal = (getattr(article, "journal", "") or "Unknown Journal").strip()

        pub_date_raw = getattr(article, "publication_date", None)
        pub_date = parse_pub_date(pub_date_raw) or "Unknown date"

        authors_raw = getattr(article, "authors", None) or []
        authors_str = get_authors_string(authors_raw)

        abstract = (getattr(article, "abstract", "") or "").strip()
        if not abstract:
            abstract = "No abstract available."

        # Clean up abstract a bit
        abstract = re.sub(r"\s+", " ", abstract).strip()

        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

        return {
            "pmid": pmid,
            "title": title,
            "pub_date": pub_date,
            "journal": journal,
            "authors": authors_str,
            "abstract": abstract,
            "url": url,
        }
    except Exception as e:
        print(f"  Warning: failed to parse one article: {e}")
        return None


def fetch_for_condition(pubmed: PubMed, condition_key: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Run query for one condition and return cleaned list of studies."""
    query = config["query"]
    print(f"[{condition_key}] Querying PubMed: {query[:80]}...")

    articles = []
    try:
        results = pubmed.query(query, max_results=MAX_RESULTS)
        for article in results:
            data = extract_article_data(article)
            if data:
                articles.append(data)
        print(f"  → {len(articles)} valid studies fetched")

        # Post-filter for PACVS to increase relevance (the term is new/emerging)
        if condition_key == "pacvs":
            def is_relevant_pacvs(s):
                text = (s.get("title", "") + " " + s.get("abstract", "")).lower()
                return ("vaccin" in text and ("pacvs" in text or "post-acute" in text or "post vaccination" in text or ("chronic" in text and "syndrome" in text)))
            filtered = [s for s in articles if is_relevant_pacvs(s)]
            if filtered:
                articles = filtered[:MAX_RESULTS]
                print(f"    PACVS post-filter reduced to {len(articles)} more relevant studies")
    except Exception as e:
        print(f"  ERROR fetching {condition_key}: {e}")
        # Return empty on error so we don't overwrite good data accidentally? 
        # For daily run, better to return what we have or keep previous. 
        # Here we will return [] and let caller decide.
        return []

    # Sort by pub_date descending (newest first). Handle partial dates.
    def sort_key(item: Dict[str, Any]):
        d = item.get("pub_date", "")
        # Prefer full dates; fallback to string reverse for rough recency
        if re.match(r"\d{4}-\d{2}-\d{2}", d):
            return d
        if re.match(r"\d{4}-\d{2}", d):
            return d + "-31"  # approximate end of month
        if re.match(r"\d{4}", d):
            return d + "-12-31"
        return "0000-00-00"

    articles.sort(key=sort_key, reverse=True)
    return articles


def save_json(key: str, studies: List[Dict[str, Any]], display_name: str):
    """Write the JSON file with metadata wrapper."""
    payload = {
        "condition": display_name,
        "key": key,
        "last_updated": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "count": len(studies),
        "source": "PubMed (NCBI)",
        "studies": studies,
    }
    out_path = DATA_DIR / f"{key}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"  Saved {len(studies)} studies → {out_path}")


def load_existing(key: str) -> Optional[Dict[str, Any]]:
    """Load previous data so we can fall back on failure."""
    path = DATA_DIR / f"{key}.json"
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def pick_condition_for_today() -> tuple[str, dict]:
    """
    Return (key, config) for the condition to update today.

    Rotates through CONDITIONS in order using day-of-year mod len(CONDITIONS),
    so each condition is updated once every N days (N = number of conditions).

    Override by setting the TRACKER_CONDITION env var to a condition key,
    e.g. TRACKER_CONDITION=long-covid for a manual workflow_dispatch run.
    """
    condition_keys = list(CONDITIONS.keys())

    override = os.environ.get("TRACKER_CONDITION", "").strip()
    if override:
        if override not in CONDITIONS:
            raise ValueError(
                f"TRACKER_CONDITION='{override}' is not a valid key. "
                f"Valid keys: {condition_keys}"
            )
        print(f"Override via TRACKER_CONDITION: '{override}'")
        return override, CONDITIONS[override]

    day_index = datetime.now(timezone.utc).timetuple().tm_yday % len(condition_keys)
    key = condition_keys[day_index]
    print(f"Day-of-year rotation → updating condition {day_index + 1}/{len(condition_keys)}: '{key}'")
    return key, CONDITIONS[key]


def main():
    print("=" * 60)
    print("Open Source Medicine Foundation – Research Tracker Updater")
    print(f"Started: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}")
    print("=" * 60)

    key, config = pick_condition_for_today()
    print(f"Condition: {config['display_name']}")
    print("-" * 60)

    pubmed = PubMed(tool=PUBMED_TOOL, email=PUBMED_EMAIL)
    time.sleep(0.5)

    existing = load_existing(key)
    studies = fetch_for_condition(pubmed, key, config)

    if not studies:
        print(f"[{key}] No studies fetched – keeping previous data if available.")
        if not existing:
            save_json(key, [], config["display_name"])
    else:
        save_json(key, studies, config["display_name"])

    print("\nDone.")


if __name__ == "__main__":
    main()
