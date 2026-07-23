#!/usr/bin/env python3
"""
Ticket 0 — Build vocabulary/slug files for all content types.

Generates:
  data/vocab/disease-slugs.yaml   — one entry per disease-intelligence/*.json
  data/vocab/agent-slugs.json     — slug map for therapeutic_agents.json
  data/vocab/agent-slugs-flagged.json — dosing-instruction artifacts to skip
  data/vocab/cohort-slugs.json    — slug map for data/cohorts/*.json

Usage:
  python scripts/build_vocab.py
"""

import json, yaml, os, re, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

def slugify(text: str) -> str:
    """Kebab-case: lowercase, punctuation → hyphens, collapse whitespace/hyphens."""
    s = text.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)          # strip punctuation except hyphens
    s = re.sub(r"[\s_]+", "-", s)               # whitespace/underscore → hyphen
    s = re.sub(r"-{2,}", "-", s)                # collapse multiple hyphens
    return s.strip("-")

def has_dosing_pattern(name: str) -> bool:
    """Return True if name looks like a dosing instruction rather than an agent name."""
    # Contains a numeric value + unit pattern: e.g. "140 Ml Per Day Of..."
    return bool(re.search(r"\b\d+\s*(ml|mg|g|mcg|µg|iu|oz|lb|kg|day|week|month|hour|per)\b", name, re.IGNORECASE))

# ---------------------------------------------------------------------------
# 1. Disease slugs
# ---------------------------------------------------------------------------
def build_disease_slugs():
    di_dir = DATA / "disease-intelligence"
    entries = []
    # First pass: collect all entries
    for fp in sorted(di_dir.glob("*.json")):
        if fp.name in ("mcas.html", "pots.html"):  # actually .json files despite listing as .html — skip non-JSON
            continue
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  SKIP (not valid JSON): {fp.name}", file=sys.stderr)
            continue

        slug = fp.stem
        mondo_id = None
        if "identifiers" in data and isinstance(data["identifiers"], dict):
            mondo_id = data["identifiers"].get("mondo_id")
        canonical_label = None
        if "condition" in data and isinstance(data["condition"], dict):
            canonical_label = data["condition"].get("name")
        if not canonical_label and "page" in data and isinstance(data["page"], dict):
            canonical_label = data["page"].get("title")
        if not canonical_label:
            canonical_label = slug.replace("-", " ").title()

        n_chars = os.path.getsize(fp)

        entries.append({
            "slug": slug,
            "mondo_id": mondo_id,
            "canonical_label": canonical_label,
            "_file_size": n_chars,
            "_filename": fp.name,
        })

    # Detect near-duplicate slugs (edit distance ≤ 3)
    def levenshtein(a: str, b: str) -> int:
        """Simple Levenshtein distance."""
        if len(a) < len(b):
            return levenshtein(b, a)
        if len(b) == 0:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                insert = prev[j + 1] + 1
                delete = curr[j] + 1
                replace = prev[j] + (0 if ca == cb else 1)
                curr.append(min(insert, delete, replace))
            prev = curr
        return prev[-1]

    # Group by mondo_id for dedup
    by_mondo = defaultdict(list)
    for e in entries:
        if e["mondo_id"]:
            by_mondo[e["mondo_id"]].append(e)

    # Also check near-duplicate slugs
    aliased = set()
    for i, a in enumerate(entries):
        if a["slug"] in aliased:
            continue
        for j in range(i + 1, len(entries)):
            b = entries[j]
            if b["slug"] in aliased:
                continue
            dist = levenshtein(a["slug"], b["slug"])
            if dist <= 3 and dist > 0:
                # Pick canonical: larger file wins
                if a["_file_size"] >= b["_file_size"]:
                    b["alias_of"] = a["slug"]
                    aliased.add(b["slug"])
                else:
                    a["alias_of"] = b["slug"]
                    aliased.add(a["slug"])

    # Dedup by mondo_id: pick largest file as canonical
    for mondo, group in by_mondo.items():
        if len(group) > 1:
            group.sort(key=lambda x: x["_file_size"], reverse=True)
            canonical_slug = group[0]["slug"]
            for dup in group[1:]:
                if dup["slug"] not in aliased:
                    dup["alias_of"] = canonical_slug
                    aliased.add(dup["slug"])

    # Build output list (clean internal keys)
    output = []
    for e in entries:
        out = {
            "slug": e["slug"],
            "mondo_id": e["mondo_id"],
            "canonical_label": e["canonical_label"],
        }
        if "alias_of" in e:
            out["alias_of"] = e["alias_of"]
        output.append(out)

    out_path = DATA / "vocab" / "disease-slugs.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(output, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        print(f"Wrote {len(output)} disease entries -> {out_path} (aliased: {len(aliased)})")

    # Validate: no two non-alias entries share a mondo_id
    non_aliased_mondo = defaultdict(list)
    for e in output:
        if "alias_of" not in e and e["mondo_id"]:
            non_aliased_mondo[e["mondo_id"]].append(e["slug"])
    dup_mondo = {m: slugs for m, slugs in non_aliased_mondo.items() if len(slugs) > 1}
    if dup_mondo:
        print(f"WARNING: duplicate mondo_id among non-alias entries: {dup_mondo}", file=sys.stderr)
    else:
        print("  [OK] No duplicate mondo_id among non-alias entries")

    return output

# ---------------------------------------------------------------------------
# 2. Agent slugs
# ---------------------------------------------------------------------------
def build_agent_slugs():
    agents_path = DATA / "therapeutic_agents.json"
    with open(agents_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    agents = data.get("agents", [])
    slug_map = {}
    flagged = []
    collisions = defaultdict(list)

    for agent in agents:
        # There are two possible field names: "Therapeutic Agent" or "name"
        name = agent.get("Therapeutic Agent") or agent.get("name", "")
        if not name:
            continue

        base_slug = slugify(name)
        if not base_slug:
            continue

        # Check for dosing-instruction patterns
        if has_dosing_pattern(name):
            flagged.append({
                "slug": base_slug,
                "display_name": name,
                "reason": "dosing_instruction_pattern",
                "primary_conditions": agent.get("Primary Conditions", []),
            })
            continue

        collisions[base_slug].append(name)

    # Resolve collisions with numeric suffix
    seen = {}
    for base_slug, names in collisions.items():
        if len(names) == 1:
            slug = base_slug
        else:
            # Multiple agents share same slugified name — disambiguate
            for idx, name in enumerate(names):
                dedup_slug = f"{base_slug}-{idx+1}" if idx > 0 else base_slug
                # But check we don't collide with another base_slug
                while dedup_slug in seen:
                    idx += 1
                    dedup_slug = f"{base_slug}-{idx+1}"
                slug_map[dedup_slug] = {"slug": dedup_slug, "display_name": name}
                seen[dedup_slug] = True
            continue

        slug_map[base_slug] = {"slug": base_slug, "display_name": names[0]}

    # Output valid agent slugs
    valid_list = list(slug_map.values())
    out_path = DATA / "vocab" / "agent-slugs.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(valid_list, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(valid_list)} agent slugs -> {out_path}")

    # Output flagged
    flag_path = DATA / "vocab" / "agent-slugs-flagged.json"
    with open(flag_path, "w", encoding="utf-8") as f:
        json.dump(flagged, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(flagged)} flagged agent entries -> {flag_path}")

    # Validate no duplicate slugs
    slug_counts = defaultdict(int)
    for r in valid_list:
        slug_counts[r["slug"]] += 1
    dups = [s for s, c in slug_counts.items() if c > 1]
    if dups:
        print(f"ERROR: duplicate agent slugs: {dups}", file=sys.stderr)
        sys.exit(1)
    else:
        print("  [OK] No duplicate agent slugs")

    return valid_list, flagged

# ---------------------------------------------------------------------------
# 3. Cohort slugs
# ---------------------------------------------------------------------------
def build_cohort_slugs():
    cohorts_dir = DATA / "cohorts"
    entries = []
    for fp in sorted(cohorts_dir.glob("*.json")):
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError):
            print(f"  SKIP (not valid JSON): {fp.name}", file=sys.stderr)
            continue

        cid = data.get("id", fp.stem)
        name = data.get("name", cid)
        short_slug = slugify(name)[:80]  # truncate to reasonable URL length

        entries.append({
            "id": cid,
            "name": name,
            "short_slug": short_slug,
        })

    out_path = DATA / "vocab" / "cohort-slugs.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(entries)} cohort slug entries -> {out_path}")
    return entries

# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Building disease-slugs.yaml ===")
    build_disease_slugs()
    print()
    print("=== Building agent-slugs.json ===")
    build_agent_slugs()
    print()
    print("=== Building cohort-slugs.json ===")
    build_cohort_slugs()
    print()
    print("Ticket 0 complete.")