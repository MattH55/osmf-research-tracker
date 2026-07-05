"""Stage 4 — LLM extraction and evidence tiering.

Uses Claude (claude-haiku-4-5-20251001) with tool use to extract
agent–biomarker relationships from PubMed / EuropePMC abstracts.

GROUNDING RULE: the model is instructed to extract only what is explicitly
stated in the provided text.  It must not draw on parametric (training)
knowledge.  Each extracted relationship must include a short verbatim quote.

Abstracts are processed in batches of BATCH_SIZE.  Results are cached by
a hash of the batch content so identical abstract sets are not re-queried.
"""
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

from .cache import cache_get, cache_set
from .models import Agent, NormalizedBiomarker, SourceRef

log = logging.getLogger(__name__)
BATCH_SIZE = 10


# ─── Tool schema ─────────────────────────────────────────────────────────────

EXTRACTION_TOOL = {
    "name": "record_agent_biomarker_relationships",
    "description": (
        "Record therapeutic agent–biomarker relationships that are explicitly "
        "stated in the provided abstracts."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "relationships": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": "Drug or compound name exactly as it appears in the text",
                        },
                        "direction": {
                            "type": "string",
                            "enum": ["increases", "decreases", "inhibits", "activates", "modulates", "unclear"],
                        },
                        "study_type": {
                            "type": "string",
                            "enum": ["in_vitro", "in_vivo", "clinical", "observational", "review", "unclear"],
                        },
                        "species": {
                            "type": "string",
                            "description": "e.g. human, mouse, rat, unclear",
                        },
                        "supporting_quote": {
                            "type": "string",
                            "description": "Short verbatim excerpt from the abstract supporting this claim",
                        },
                        "pmid": {"type": "string"},
                    },
                    "required": ["agent_name", "direction", "study_type", "pmid"],
                },
            }
        },
        "required": ["relationships"],
    },
}


def _batch_hash(abstracts: list[dict]) -> str:
    content = json.dumps(
        [a.get("pmid", "") + (a.get("abstract", "")[:200]) for a in abstracts],
        sort_keys=True,
    )
    return hashlib.md5(content.encode()).hexdigest()


def _study_type_to_tier(study_type: str) -> str:
    if study_type in ("clinical", "observational"):
        return "clinical"
    if study_type == "in_vitro":
        return "mechanistic"
    return "correlative"


def _call_claude(biomarker_name: str, abstracts: list[dict], client) -> list[dict]:
    """Synchronous Claude call (run via asyncio.to_thread)."""
    cache_key = _batch_hash(abstracts)
    cached = cache_get("stage4", cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    abstracts_text = "\n\n".join(
        f"[PMID:{a['pmid']}] {a.get('title', '')}\n{a.get('abstract', '')}"
        for a in abstracts
    )
    system = (
        "You are a biomedical literature extractor. "
        "STRICT RULES: "
        "(1) Extract ONLY relationships explicitly stated in the text provided below — "
        "never infer, hypothesise, or draw on training knowledge. "
        "(2) Omit any claim not directly supported by the text. "
        "(3) Include a short verbatim quote for every claim."
    )
    user = (
        f"Biomarker of interest: {biomarker_name}\n\n"
        f"--- ABSTRACTS ---\n{abstracts_text}\n--- END ABSTRACTS ---\n\n"
        f"Extract all agent–{biomarker_name} relationships from these abstracts only."
    )
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system,
            tools=[EXTRACTION_TOOL],
            tool_choice={"type": "tool", "name": "record_agent_biomarker_relationships"},
            messages=[{"role": "user", "content": user}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "record_agent_biomarker_relationships":
                rels = block.input.get("relationships", [])
                cache_set("stage4", cache_key, rels)
                return rels
    except Exception as e:
        log.warning("[Stage4] LLM call failed for batch: %s", e)
    return []


# ─── Public entry point ───────────────────────────────────────────────────────

async def extract_agents_from_literature(
    norm: NormalizedBiomarker,
    abstracts: list[dict],
    anthropic_api_key: str,
) -> tuple[list[Agent], list[str]]:
    notes: list[str] = []
    if not anthropic_api_key:
        notes.append("ANTHROPIC_API_KEY not set — Stage 4 LLM extraction skipped.")
        return [], notes
    if not abstracts:
        notes.append("No abstracts available for Stage 4 extraction.")
        return [], notes

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=anthropic_api_key)
    except ImportError:
        notes.append("'anthropic' package not installed — Stage 4 skipped.  Run: pip install anthropic")
        return [], notes

    biomarker_name = norm.symbol or norm.input_name
    batches = [abstracts[i : i + BATCH_SIZE] for i in range(0, len(abstracts), BATCH_SIZE)]

    all_rels: list[dict] = []
    for batch in batches:
        rels = await asyncio.to_thread(_call_claude, biomarker_name, batch, client)
        all_rels.extend(rels)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    seen: dict[str, Agent] = {}
    for rel in all_rels:
        name_key = (rel.get("agent_name") or "").strip().lower()
        if not name_key:
            continue
        tier = _study_type_to_tier(rel.get("study_type", "unclear"))
        source = SourceRef(
            pubmed_id=rel.get("pmid"),
            study_type=rel.get("study_type"),
            species=rel.get("species"),
            retrieved_at=now,
        )
        if name_key in seen:
            existing = seen[name_key]
            existing.sources.append(source)
            if tier == "mechanistic" and existing.evidence_tier == "correlative":
                existing.evidence_tier = "mechanistic"
            elif tier == "clinical":
                existing.evidence_tier = "clinical"
        else:
            seen[name_key] = Agent(
                agent_name=rel["agent_name"],
                direction_of_effect=rel.get("direction", "unclear"),
                evidence_tier=tier,
                sources=[source],
            )

    notes.append(
        f"LLM extraction: {len(abstracts)} abstracts, {len(batches)} batch(es) "
        f"→ {len(seen)} unique agents."
    )
    return list(seen.values()), notes
