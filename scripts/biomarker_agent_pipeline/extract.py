"""Stage 4: grounded extraction and evidence tiering."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import CACHE_DIR, openai_api_key
from .models import AgentRecord, Direction, EvidenceTier, NormalizedBiomarker, RawHit, SourceCitation

EXTRACTION_CACHE = CACHE_DIR / "extraction"

DIRECTION_PATTERNS = [
    (re.compile(r"\b(inhibit|inhibition|inhibitor|block|blocking|antagonist|suppress|reduced|decrease[ds]?|lower(?:ed)?)\b", re.I), "inhibits"),
    (re.compile(r"\b(activat|agonist|induc|increas(?:e|ed|es)|elevated|upregulat|stimulat)\b", re.I), "activates"),
    (re.compile(r"\b(decreas(?:e|ed|es)|reduc(?:e|ed|es)|downregulat|lower(?:ed)?)\b", re.I), "decreases"),
    (re.compile(r"\b(increas(?:e|ed|es)|elevated|upregulat|raised)\b", re.I), "increases"),
]

STUDY_TYPE_PATTERNS = [
    (re.compile(r"\brandomi[sz]ed\b|\bclinical trial\b|\bRCT\b", re.I), "clinical"),
    (re.compile(r"\bin vitro\b|\bcell line\b", re.I), "in_vitro"),
    (re.compile(r"\bin vivo\b|\bmouse\b|\bmurine\b|\brat\b", re.I), "in_vivo"),
    (re.compile(r"\bsystematic review\b|\bmeta-analysis\b", re.I), "review"),
    (re.compile(r"\bobservational\b|\bcohort\b", re.I), "observational"),
]

AGENT_IN_TEXT = re.compile(
    r"\b([A-Z][a-z]+(?:[- ][A-Z0-9][a-zA-Z0-9]+){0,4}|[a-z]+(?:mab|nib|vir|pril|sartan|statin|cycline|cillin))\b"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _map_direction(text: str, hint: str | None = None) -> Direction:
    if hint:
        h = hint.lower()
        if "inhibit" in h or "antagon" in h:
            return "inhibits"
        if "agon" in h or "activ" in h:
            return "activates"
        if "increase" in h or "up" in h:
            return "increases"
        if "decrease" in h or "down" in h:
            return "decreases"
    for pat, label in DIRECTION_PATTERNS:
        if pat.search(text):
            return label  # type: ignore
    return "unclear"


def _study_type(text: str) -> str:
    for pat, label in STUDY_TYPE_PATTERNS:
        if pat.search(text):
            return label
    return "other"


def _cache_get(key: str) -> list[dict] | None:
    path = EXTRACTION_CACHE / f"{hashlib.sha256(key.encode()).hexdigest()}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _cache_put(key: str, data: list[dict]) -> None:
    EXTRACTION_CACHE.mkdir(parents=True, exist_ok=True)
    path = EXTRACTION_CACHE / f"{hashlib.sha256(key.encode()).hexdigest()}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def extract_from_database_hits(hits: list[RawHit]) -> list[AgentRecord]:
    records: list[AgentRecord] = []
    mechanistic_sources = {"DGIdb", "ChEMBL", "OpenTargets"}
    for hit in hits:
        tier: EvidenceTier = "mechanistic" if hit.source in mechanistic_sources else "correlative"
        if hit.source == "OpenTargets":
            tier = "clinical"
        agent_id = {}
        if hit.agent_id:
            if str(hit.agent_id).startswith("rxcui:"):
                agent_id["rxnorm"] = str(hit.agent_id).split(":")[-1]
            elif str(hit.agent_id).startswith("CHEMBL"):
                agent_id["chembl_id"] = str(hit.agent_id)
            else:
                agent_id["concept_id"] = str(hit.agent_id)
        records.append(
            AgentRecord(
                agent_name=hit.agent.title() if hit.agent.isupper() else hit.agent,
                agent_id=agent_id,
                direction_of_effect=_map_direction(hit.interaction_type or "", hit.direction_hint),
                evidence_tier=tier,
                potency=hit.potency or {"value": None, "unit": None, "measure": None},
                sources=[
                    SourceCitation(
                        database=hit.source,
                        url=hit.source_url,
                        retrieved_at=_now(),
                    )
                ],
            )
        )
    return records


def _rule_extract_batch(articles: list[dict], norm: NormalizedBiomarker) -> list[dict]:
    claims = []
    biomarker_terms = [t.lower() for t in norm.synonyms[:8] if t]
    for art in articles:
        text = f"{art.get('title', '')} {art.get('abstract', '')}"
        if not any(bt in text.lower() for bt in biomarker_terms):
            continue
        sentences = re.split(r"(?<=[.!?])\s+", art.get("abstract", ""))
        for idx, sent in enumerate(sentences):
            if not any(bt in sent.lower() for bt in biomarker_terms):
                continue
            # crude agent detection: look for drug-like tokens near direction verbs
            if not re.search(r"\b(drug|treatment|therapy|inhibitor|agonist|supplement|administered)\b", sent, re.I):
                continue
            direction = _map_direction(sent)
            study = _study_type(text)
            # extract candidate agent phrase before 'reduced/increased/inhibited'
            agent = None
            m = re.search(
                r"([A-Z][a-zA-Z0-9-]+(?:\s+[a-z]+)?)\s+(?:significantly\s+)?(?:reduced|increased|inhibited|decreased|elevated|modulated)",
                sent,
            )
            if m:
                agent = m.group(1).strip()
            if not agent:
                continue
            claims.append(
                {
                    "agent_name": agent,
                    "direction_of_effect": direction,
                    "study_type": study,
                    "species": "human" if "patient" in sent.lower() or "clinical" in study else "unclear",
                    "locator": f"sentence_{idx}",
                    "pubmed_id": art.get("pmid"),
                    "source_text": sent[:400],
                }
            )
    return claims


def _llm_extract_batch(articles: list[dict], norm: NormalizedBiomarker) -> list[dict]:
    key = openai_api_key()
    if not key:
        return []
    try:
        import httpx
    except ImportError:
        return []

    batch_text = []
    for i, art in enumerate(articles[:10]):
        batch_text.append(
            f"DOC_{i} PMID:{art.get('pmid')}\nTITLE: {art.get('title')}\nABSTRACT: {art.get('abstract', '')[:2500]}"
        )
    user = "\n\n".join(batch_text)
    system = (
        "Extract ONLY explicit biomarker-agent claims from the provided documents. "
        f"Biomarker context: {norm.input}. Synonyms: {', '.join(norm.synonyms[:8])}. "
        "Return JSON array of objects with keys: agent_name, direction_of_effect "
        "(increases|decreases|inhibits|activates|modulates|unclear), study_type, species, "
        "pubmed_id, locator (sentence reference). Omit unsupported claims. Do not infer from drug class alone."
    )
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            data = json.loads(content)
            if isinstance(data, dict) and "claims" in data:
                return data["claims"]
            if isinstance(data, list):
                return data
    except Exception:
        return []
    return []


def extract_from_literature(articles: list[dict], norm: NormalizedBiomarker) -> list[AgentRecord]:
    if not articles:
        return []
    cache_key = "|".join(a.get("pmid") or a.get("title", "") for a in articles[:15])
    cached = _cache_get(cache_key)
    if cached is None:
        claims = _llm_extract_batch(articles, norm)
        if not claims:
            claims = _rule_extract_batch(articles, norm)
        _cache_put(cache_key, claims)
    else:
        claims = cached

    records = []
    for c in claims:
        pmid = c.get("pubmed_id")
        records.append(
            AgentRecord(
                agent_name=c.get("agent_name", "Unknown"),
                direction_of_effect=c.get("direction_of_effect", "unclear"),
                evidence_tier="correlative",
                sources=[
                    SourceCitation(
                        database="PubMed",
                        pubmed_id=str(pmid) if pmid else None,
                        url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                        study_type=c.get("study_type"),
                        species=c.get("species"),
                        locator=c.get("locator"),
                        retrieved_at=_now(),
                    )
                ],
            )
        )
    return records