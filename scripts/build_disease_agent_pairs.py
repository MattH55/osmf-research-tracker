#!/usr/bin/env python3
"""
Ticket 6 — Build disease×agent join table from existing data.

Reads:
  data/disease-intelligence/*.json   — per-disease merged_ranked therapeutics
  data/therapeutic_agents.json       — per-agent mechanism/safety/trials
  data/vocab/agent-slugs.json        — agent name -> slug map

Writes:
  data/disease-agent-pairs.json      — [{disease_slug, agent_slug, evidence_tier, n_studies, match_confidence}]

Usage: python scripts/build_disease_agent_pairs.py [--limit N]
"""
import json, sys, re
from pathlib import Path
from difflib import SequenceMatcher

ROOT = Path(__file__).resolve().parent.parent
DI_DIR = ROOT / "data" / "disease-intelligence"
AGENTS_FILE = ROOT / "data" / "therapeutic_agents.json"
SLUGS_FILE = ROOT / "data" / "vocab" / "agent-slugs.json"
FLAGGED_FILE = ROOT / "data" / "vocab" / "agent-slugs-flagged.json"
PAIRS_OUT = ROOT / "data" / "disease-agent-pairs.json"


def normalize(name: str) -> str:
    """Normalize agent names for fuzzy matching."""
    return re.sub(r'\s+', ' ', name.lower().strip())


def load_agent_data() -> tuple[dict, dict, set]:
    """Return (name_to_agent, name_to_slug, flagged_names)."""
    with open(AGENTS_FILE, "r", encoding="utf-8") as f:
        agents_data = json.load(f)

    with open(SLUGS_FILE, "r", encoding="utf-8") as f:
        slug_list = json.load(f)

    flagged = set()
    if FLAGGED_FILE.exists():
        with open(FLAGGED_FILE, "r", encoding="utf-8") as f:
            flagged = {a["display_name"] for a in json.load(f)}

    name_to_slug = {s["display_name"]: s["slug"] for s in slug_list}
    name_to_agent = {}
    for a in agents_data.get("agents", []):
        name = a.get("Therapeutic Agent", "")
        if name and name not in flagged:
            name_to_agent[name] = a
    return name_to_agent, name_to_slug, flagged


def _build_normalized_lookup(name_to_slug: dict) -> dict[str, str]:
    """Pre-build normalized lookup: normalized_name -> slug."""
    lookup = {}
    for name, slug in name_to_slug.items():
        lookup[normalize(name)] = slug
    return lookup


def main():
    limit = None
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    name_to_agent, name_to_slug, flagged = load_agent_data()
    norm_lookup = _build_normalized_lookup(name_to_slug)

    pairs = []
    matched = 0
    unmatched = 0
    skipped_flagged = 0
    low_confidence = 0

    di_files = sorted(DI_DIR.glob("*.json"))
    for fp in di_files:
        data = json.loads(fp.read_text(encoding="utf-8"))
        disease_slug = data.get("slug", fp.stem)
        merged = data.get("therapeutics", {}).get("merged_ranked", [])
        if not merged:
            continue

        for agent_entry in merged:
            agent_name = agent_entry.get("name", "")
            if not agent_name:
                continue

            # Skip flagged agents
            if agent_name in flagged:
                skipped_flagged += 1
                continue

            # Exact match via normalized lookup
            norm_name = normalize(agent_name)
            agent_slug = norm_lookup.get(norm_name)
            if not agent_slug:
                # Also try direct match (field may use display name directly)
                agent_slug = name_to_slug.get(agent_name)
            if agent_slug:
                confidence = 1.0 if norm_name in norm_lookup else 0.95
                matched += 1
            else:
                unmatched += 1
                continue

            evidence_tier = agent_entry.get("evidence_tier", "D")
            pubmed_count = agent_entry.get("pubmed_count", 0)

            pairs.append({
                "disease_slug": disease_slug,
                "agent_slug": agent_slug,
                "evidence_tier": evidence_tier,
                "n_studies": pubmed_count,
                "match_confidence": round(confidence, 3),
            })

        if limit and len(pairs) >= limit:
            break

    # Deduplicate
    seen = set()
    unique = []
    for p in pairs:
        key = (p["disease_slug"], p["agent_slug"])
        if key not in seen:
            seen.add(key)
            unique.append(p)

    print(f"Join results: {len(unique)} unique pairs from {matched} matches, {unmatched} unmatched, {skipped_flagged} flagged skipped, {low_confidence} low-confidence fuzzy matches")

    with open(PAIRS_OUT, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)
    print(f"Wrote {PAIRS_OUT} ({len(unique)} pairs)")

    # Summary stats
    n_diseases = len({p["disease_slug"] for p in unique})
    n_agents = len({p["agent_slug"] for p in unique})
    has_studies = sum(1 for p in unique if p["n_studies"] > 0)
    print(f"Coverage: {n_diseases} diseases × {n_agents} agents | {has_studies} pairs with studies >= 1")

    return 0


if __name__ == "__main__":
    sys.exit(main())