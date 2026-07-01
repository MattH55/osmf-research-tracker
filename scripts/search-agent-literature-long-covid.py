#!/usr/bin/env python3
"""
PubMed literature validation: each Long COVID therapeutic agent × article type,
plus symptom/biomarker linkage panel from long-covid biomarker atlas.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ONTOLOGY_PATH = ROOT / "data" / "clinical_trials" / "treatment-ontology.json"
ATLAS_PATH = ROOT / "data" / "biomarkers" / "long-covid.json"
OUT_DIR = ROOT / "data" / "agent-literature"
OUT_PATH = OUT_DIR / "long-covid-validation.json"
CACHE_PATH = OUT_DIR / "long-covid-validation-cache.json"

PUBMED_TOOL = "OSMF-AgentLiterature"
PUBMED_EMAIL = "research@opensourcemed.info"
RATE_LIMIT_SEC = 0.34
RETMAX_AGENT = 8
RETMAX_PANEL = 12

LC_QUERY = (
    '("long covid"[tiab] OR "long-covid"[tiab] OR "post-acute sequelae of COVID-19"[tiab] '
    'OR PASC[tiab] OR "post-acute COVID-19 syndrome"[tiab] OR "long hauler"[tiab] '
    'OR ("post-COVID"[tiab] AND (syndrome[tiab] OR fatigue[tiab] OR sequelae[tiab])))'
)

ARTICLE_TYPES = {
    "systematic-review": '("Systematic Review"[pt] OR "Meta-Analysis"[pt])',
    "review": '("Review"[pt]) NOT ("Systematic Review"[pt] OR "Meta-Analysis"[pt])',
    "clinical-trial": (
        '("Randomized Controlled Trial"[pt] OR "Clinical Trial"[pt] '
        'OR "Controlled Clinical Trial"[pt] OR "Pragmatic Clinical Trial"[pt])'
    ),
    "case-series": '("case series"[tiab])',
    "case-study": '("Case Reports"[pt])',
    "experimental": (
        '("in vitro"[tiab] OR "in vivo"[tiab] OR "animal model"[tiab] '
        'OR "preclinical"[tiab] OR "murine"[tiab] OR "mouse model"[tiab])'
    ),
}

MECHANISTIC_SYMPTOM_SKIP = re.compile(
    r"activation|metabolism|hypothesis|pathway|production|injury|dysbiosis|"
    r"coagulation cascade|complement-mediated|antigen persistence|elevated at|"
    r"impairment$|deficit$|involvement$|persistence",
    re.I,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def agent_search_terms(term: dict, max_terms: int = 4) -> list[str]:
    terms = [term["preferredTerm"]]
    for s in term.get("synonyms") or []:
        if len(s) < 4 or len(s) > 60:
            continue
        if s.lower() in {"exercise", "training", "therapy", "program", "group", "active", "sham"}:
            continue
        terms.append(s)
        if len(terms) >= max_terms:
            break
    out = []
    seen = set()
    for t in terms:
        k = norm_key(t)
        if k and k not in seen:
            seen.add(k)
            out.append(t)
    return out[:max_terms]


def build_agent_query(terms: list[str]) -> str:
    parts = []
    for t in terms:
        safe = t.replace('"', "")
        if len(safe) < 3:
            continue
        parts.append(f'"{safe}"[tiab]')
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return "(" + " OR ".join(parts) + ")"


def http_get_json(url: str, retries: int = 5) -> dict:
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=45) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as err:
            last_err = err
            time.sleep(min(2 ** attempt, 20))
    raise last_err


def pubmed_esearch(query: str, retmax: int = RETMAX_AGENT) -> list[str]:
    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "term": query,
            "retmax": retmax,
            "retmode": "json",
            "tool": PUBMED_TOOL,
            "email": PUBMED_EMAIL,
        }
    )
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{params}"
    data = http_get_json(url)
    return data.get("esearchresult", {}).get("idlist", [])


def pubmed_esummary(pmids: list[str]) -> dict[str, dict]:
    if not pmids:
        return {}
    params = urllib.parse.urlencode(
        {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
            "tool": PUBMED_TOOL,
            "email": PUBMED_EMAIL,
        }
    )
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?{params}"
    data = http_get_json(url)
    result = {}
    for uid, item in (data.get("result") or {}).items():
        if uid == "uids":
            continue
        result[uid] = {
            "pmid": uid,
            "title": item.get("title", ""),
            "pub_date": item.get("pubdate", ""),
            "journal": item.get("fulljournalname") or item.get("source", ""),
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
        }
    return result


def classify_literature(title: str) -> str:
    t = (title or "").lower()
    if re.search(r"meta-analysis|systematic review|umbrella review|pooled analysis", t):
        return "systematic-review"
    if re.search(r"\breview\b|narrative review|scoping review", t):
        return "review"
    if re.search(r"randomized|randomised|clinical trial|phase [iiv]+|rct|cohort study|pilot study", t):
        return "clinical-trial"
    if re.search(r"case series", t):
        return "case-series"
    if re.search(r"case report", t):
        return "case-study"
    if re.search(r"in vitro|in vivo|mouse|murine|animal model|preclinical", t):
        return "experimental"
    return "other"


def extract_symptoms_and_biomarkers(atlas: dict) -> tuple[list[dict], list[dict]]:
    symptom_map: dict[str, set[str]] = {}
    biomarkers = []

    for marker in atlas.get("markers", []):
        name = marker.get("name", "")
        biomarkers.append(
            {
                "id": f"biomarker:{norm_key(name).replace(' ', '-')}",
                "name": name,
                "alternateName": marker.get("alternateName", ""),
                "direction": marker.get("direction"),
                "category": marker.get("category"),
                "loinc": marker.get("loinc"),
                "searchTerms": list(
                    dict.fromkeys(
                        t
                        for t in [
                            name,
                            re.sub(r"\s*\([^)]*\)", "", name).strip(),
                            marker.get("alternateName", ""),
                        ]
                        if t and len(t) >= 3
                    )
                ),
            }
        )
        for part in (marker.get("symptoms") or "").split(","):
            s = part.strip()
            if not s or len(s) < 4 or MECHANISTIC_SYMPTOM_SKIP.search(s):
                continue
            key = norm_key(s)
            if key not in symptom_map:
                symptom_map[key] = {"label": s, "markers": set()}
            symptom_map[key]["markers"].add(name)

    symptoms = [
        {
            "id": f"symptom:{k.replace(' ', '-')}",
            "name": v["label"],
            "linkedMarkers": sorted(v["markers"]),
            "searchTerms": [v["label"]],
        }
        for k, v in sorted(symptom_map.items(), key=lambda x: x[1]["label"])
    ]
    return symptoms, biomarkers


def build_agent_matcher(lc_agents: list[dict]) -> list[dict]:
    matchers = []
    for term in lc_agents:
        keys = set()
        for field in ["preferredTerm", *(term.get("synonyms") or []), *(term.get("rawAgentTerms") or [])]:
            k = norm_key(field)
            if len(k) >= 4:
                keys.add(k)
        matchers.append(
            {
                "id": term["id"],
                "preferredTerm": term["preferredTerm"],
                "matchKeys": sorted(keys, key=len, reverse=True),
            }
        )
    return matchers


def find_agents_in_text(text: str, matchers: list[dict]) -> list[str]:
    t = norm_key(text)
    hits = []
    for m in matchers:
        for k in m["matchKeys"]:
            if len(k) >= 5 and k in t:
                hits.append(m["id"])
                break
            if len(k) >= 4 and re.search(rf"\b{re.escape(k)}\b", t):
                hits.append(m["id"])
                break
    return hits


def main():
    ontology = load_json(ONTOLOGY_PATH)
    atlas = load_json(ATLAS_PATH)
    lc_label = "Long COVID / PASC"
    lc_agents = [t for t in ontology["terms"] if lc_label in (t.get("conditions") or [])]
    symptoms, biomarkers = extract_symptoms_and_biomarkers(atlas)
    matchers = build_agent_matcher(lc_agents)

    cache = load_json(CACHE_PATH) if CACHE_PATH.exists() else {"agentQueries": {}, "panelQueries": {}}
    agent_queries = cache.setdefault("agentQueries", {})
    panel_queries = cache.setdefault("panelQueries", {})

    agent_results = {}
    total_queries = len(lc_agents) * len(ARTICLE_TYPES)
    done = 0

    print(f"Long COVID agents: {len(lc_agents)}")
    print(f"Article types: {list(ARTICLE_TYPES.keys())}")
    print(f"Symptoms (patient-facing): {len(symptoms)} | Biomarkers: {len(biomarkers)}")

    for term in lc_agents:
        agent_id = term["id"]
        search_terms = agent_search_terms(term)
        agent_q = build_agent_query(search_terms)
        if not agent_q:
            continue

        by_type = {}
        for type_key, type_filter in ARTICLE_TYPES.items():
            cache_key = f"{agent_id}|{type_key}"
            done += 1
            if cache_key in agent_queries:
                pmids = agent_queries[cache_key]
            else:
                query = f"{agent_q} AND {LC_QUERY} AND {type_filter}"
                try:
                    pmids = pubmed_esearch(query, RETMAX_AGENT)
                except Exception as err:
                    print(f"  WARN {term['preferredTerm']} / {type_key}: {err}")
                    pmids = []
                agent_queries[cache_key] = pmids
                time.sleep(RATE_LIMIT_SEC)
                if done % 50 == 0:
                    save_json(CACHE_PATH, cache)
                    print(f"  Agent searches {done}/{total_queries}…")

            try:
                summaries = pubmed_esummary(pmids)
            except Exception as err:
                print(f"  WARN esummary {term['preferredTerm']} / {type_key}: {err}")
                summaries = {}
            time.sleep(RATE_LIMIT_SEC)
            studies = []
            for pmid in pmids:
                s = summaries.get(pmid)
                if not s:
                    continue
                studies.append({**s, "literatureCategory": type_key, "classifiedAs": classify_literature(s["title"])})
            by_type[type_key] = studies

        total_hits = sum(len(v) for v in by_type.values())
        agent_results[agent_id] = {
            "id": agent_id,
            "preferredTerm": term["preferredTerm"],
            "searchTermsUsed": search_terms,
            "trialCount": term.get("trialCount", 0),
            "relationCounts": term.get("relationCounts", {}),
            "literatureByType": by_type,
            "totalHits": total_hits,
        }

    # Symptom / biomarker panel: LC + entity, then match agents in titles
    panel = {"symptoms": [], "biomarkers": []}

    def run_panel(entity_type: str, entities: list[dict]):
        for entity in entities:
            cache_key = f"{entity_type}:{entity['id']}"
            if cache_key in panel_queries:
                pmids = panel_queries[cache_key]
            else:
                ent_q = " OR ".join(f'"{t.replace(chr(34), "")}"[tiab]' for t in entity["searchTerms"][:2])
                query = f"({ent_q}) AND {LC_QUERY}"
                try:
                    pmids = pubmed_esearch(query, RETMAX_PANEL)
                except Exception as err:
                    print(f"  WARN panel {entity['name']}: {err}")
                    pmids = []
                panel_queries[cache_key] = pmids
                time.sleep(RATE_LIMIT_SEC)

            summaries = pubmed_esummary(pmids)
            time.sleep(RATE_LIMIT_SEC)

            linked_agents: dict[str, dict] = {}
            studies = []
            for pmid in pmids:
                s = summaries.get(pmid)
                if not s:
                    continue
                agent_ids = find_agents_in_text(s["title"], matchers)
                cat = classify_literature(s["title"])
                studies.append({**s, "literatureCategory": cat, "matchedAgentIds": agent_ids})
                for aid in agent_ids:
                    if aid not in linked_agents:
                        pref = next((a["preferredTerm"] for a in lc_agents if a["id"] == aid), aid)
                        linked_agents[aid] = {"id": aid, "preferredTerm": pref, "studyCount": 0}
                    linked_agents[aid]["studyCount"] += 1

            entry = {
                **entity,
                "totalStudies": len(studies),
                "linkedAgents": sorted(linked_agents.values(), key=lambda x: (-x["studyCount"], x["preferredTerm"])),
                "studies": studies,
            }
            if entity_type == "symptom":
                panel["symptoms"].append(entry)
            else:
                panel["biomarkers"].append(entry)

    print("Running symptom panel searches…")
    run_panel("symptom", symptoms)
    print("Running biomarker panel searches…")
    run_panel("biomarker", biomarkers)

    # Reverse-map panel hits onto each agent (no extra PubMed queries)
    for agent_data in agent_results.values():
        agent_data["symptomBiomarkerLinks"] = {"symptoms": [], "biomarkers": []}

    for entity_type, entries in [("symptoms", panel["symptoms"]), ("biomarkers", panel["biomarkers"])]:
        for entry in entries:
            for agent_link in entry.get("linkedAgents", []):
                aid = agent_link["id"]
                if aid not in agent_results:
                    continue
                agent_results[aid]["symptomBiomarkerLinks"][entity_type].append(
                    {
                        "entityId": entry["id"],
                        "entityName": entry["name"],
                        "hitCount": agent_link["studyCount"],
                        "linkedMarkers": entry.get("linkedMarkers"),
                    }
                )

    save_json(CACHE_PATH, cache)

    agents_with_lit = sum(1 for a in agent_results.values() if a["totalHits"] > 0)
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "condition": "Long COVID / PASC",
        "agentCount": len(lc_agents),
        "agentsWithLiterature": agents_with_lit,
        "articleTypes": list(ARTICLE_TYPES.keys()),
        "symptomCount": len(symptoms),
        "biomarkerCount": len(biomarkers),
        "agents": agent_results,
        "symptomBiomarkerPanel": panel,
    }
    save_json(OUT_PATH, payload)

    print(f"\nWrote {OUT_PATH}")
    print(f"  {agents_with_lit}/{len(lc_agents)} agents with ≥1 literature hit")
    print(f"  Symptoms with linked agents: {sum(1 for s in panel['symptoms'] if s['linkedAgents'])}")
    print(f"  Biomarkers with linked agents: {sum(1 for b in panel['biomarkers'] if b['linkedAgents'])}")


if __name__ == "__main__":
    main()