"""Stage 4b — LLM extraction of disease-vs-control marker direction.

Distinct from stage4_llm.py, which extracts drug->gene effect direction
(direction_of_effect: increases/decreases/inhibits/activates/modulates).
This stage asks a different, grounded question: is the marker itself
elevated, reduced, or unchanged in the disease state compared to healthy
controls (or another named comparison population)? That's the field the
biomarkers.schema.json atlas format actually requires.

Same grounding discipline as stage4_llm.py: Claude Haiku, tool-use, batches
of 10 abstracts, extraction cached by content hash, verbatim quote required,
no parametric knowledge.
"""
import asyncio
import hashlib
import json
import logging

from .cache import cache_get, cache_set
from .models import MarkerDirectionClaim, MarkerLiteratureRef, NormalizedBiomarker

log = logging.getLogger(__name__)
BATCH_SIZE = 10

DIRECTION_TOOL = {
    "name": "record_marker_direction_claims",
    "description": (
        "Record claims, explicitly stated in the provided abstracts, about whether a "
        "biomarker's level is elevated, reduced, or unchanged in a disease state "
        "compared to a named comparison population (e.g. healthy controls)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "claims": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["up", "down", "mixed", "unclear"],
                            "description": (
                                "'up' if the marker is reported higher/elevated in the disease "
                                "state vs. the comparison population; 'down' if lower/reduced; "
                                "'mixed' if the text reports both directions across subgroups; "
                                "'unclear' if not explicitly stated."
                            ),
                        },
                        "comparison_population": {
                            "type": "string",
                            "description": "e.g. 'healthy controls', 'age-matched controls', 'disease-matched patients', 'pre-treatment baseline'",
                        },
                        "symptoms": {
                            "type": "string",
                            "description": "Symptoms or clinical features explicitly linked to the marker level in the text, if any; empty string if none stated",
                        },
                        "supporting_quote": {
                            "type": "string",
                            "description": "Short verbatim excerpt from the abstract supporting this claim",
                        },
                        "pmid": {"type": "string"},
                    },
                    "required": ["direction", "comparison_population", "supporting_quote", "pmid"],
                },
            }
        },
        "required": ["claims"],
    },
}


def _batch_hash(refs: list[MarkerLiteratureRef]) -> str:
    content = json.dumps(
        [r.pmid + (r.abstract[:200]) for r in refs],
        sort_keys=True,
    )
    return hashlib.md5(content.encode()).hexdigest()


def _call_claude(marker_name: str, disease_name: str, refs: list[MarkerLiteratureRef], client) -> list[dict]:
    """Synchronous Claude call (run via asyncio.to_thread)."""
    cache_key = _batch_hash(refs)
    cached = cache_get("stage4b", cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    refs_text = "\n\n".join(
        f"[PMID:{r.pmid}] {r.title}\n{r.abstract}"
        for r in refs
    )
    system = (
        "You are a biomedical literature extractor. "
        "STRICT RULES: "
        "(1) Extract ONLY claims about marker level vs. a comparison population that are "
        "explicitly stated in the text provided below — never infer, hypothesise, or draw "
        "on training knowledge. "
        "(2) Do not confuse 'the marker is elevated in disease' with 'a drug increases/decreases "
        "the marker' — only extract disease-state-vs-comparison-population claims. "
        "(3) Omit any claim not directly supported by the text. "
        "(4) Include a short verbatim quote for every claim."
    )
    user = (
        f"Marker of interest: {marker_name}\n"
        f"Disease of interest: {disease_name}\n\n"
        f"--- ABSTRACTS ---\n{refs_text}\n--- END ABSTRACTS ---\n\n"
        f"Extract all claims about {marker_name} levels in {disease_name} patients compared to "
        f"a named comparison population, from these abstracts only."
    )
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            system=system,
            tools=[DIRECTION_TOOL],
            tool_choice={"type": "tool", "name": "record_marker_direction_claims"},
            messages=[{"role": "user", "content": user}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "record_marker_direction_claims":
                claims = block.input.get("claims", [])
                cache_set("stage4b", cache_key, claims)
                return claims
    except Exception as e:
        log.warning("[Stage4b] LLM call failed for batch: %s", e)
    return []


def _prompts(marker_name: str, disease_name: str, refs: list[MarkerLiteratureRef]) -> tuple[str, str]:
    refs_text = "\n\n".join(f"[PMID:{r.pmid}] {r.title}\n{r.abstract}" for r in refs)
    system = (
        "You are a biomedical literature extractor. "
        "STRICT RULES: "
        "(1) Extract ONLY claims about marker level vs. a comparison population that are "
        "explicitly stated in the text provided below — never infer, hypothesise, or draw "
        "on training knowledge. "
        "(2) Do not confuse 'the marker is elevated in disease' with 'a drug increases/decreases "
        "the marker' — only extract disease-state-vs-comparison-population claims. "
        "(3) Omit any claim not directly supported by the text. "
        "(4) Include a short verbatim quote for every claim."
    )
    user = (
        f"Marker of interest: {marker_name}\n"
        f"Disease of interest: {disease_name}\n\n"
        f"--- ABSTRACTS ---\n{refs_text}\n--- END ABSTRACTS ---\n\n"
        f"Extract all claims about {marker_name} levels in {disease_name} patients compared to "
        f"a named comparison population, from these abstracts only."
    )
    return system, user


def _call_nanogpt(marker_name: str, disease_name: str, refs: list[MarkerLiteratureRef], cfg: dict) -> list[dict]:
    """Same extraction through an OpenAI-compatible endpoint (NanoGPT).

    No tool-use there, so the tool's input schema is sent as the required JSON
    shape and the reply is parsed; anything that does not validate is dropped.
    """
    import httpx

    cache_key = _batch_hash(refs)
    cached = cache_get("stage4b", cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    system, user = _prompts(marker_name, disease_name, refs)
    schema = json.dumps(DIRECTION_TOOL["input_schema"])
    user += (
        "\n\nRespond with a single JSON object only, no prose, matching this JSON schema exactly: "
        + schema
        + "\nIf no claim is supported by the text, respond with {\"claims\": []}."
    )
    body = {
        "model": cfg["model"],
        "temperature": 0,
        "max_tokens": 2048,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    try:
        r = httpx.post(
            f"{cfg['base_url']}/chat/completions",
            headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
            json=body,
            timeout=120,
        )
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[text.find("{"):]
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
        allowed = {"up", "down", "mixed", "unclear"}
        claims = [
            c for c in data.get("claims", [])
            if isinstance(c, dict) and c.get("direction") in allowed
            and c.get("supporting_quote") and c.get("pmid")
        ]
        for c in claims:
            c["pmid"] = str(c["pmid"]).replace("PMID:", "").strip()
            c.setdefault("comparison_population", "")
            c.setdefault("symptoms", "")
        cache_set("stage4b", cache_key, claims)
        return claims
    except Exception as e:
        log.warning("[Stage4b] NanoGPT call failed for batch: %s", e)
    return []


def nanogpt_config() -> dict | None:
    """NanoGPT settings from the environment; None when no key is set."""
    import os

    key = os.environ.get("NANOGPT_API_KEY", "").strip()
    if not key:
        return None
    return {
        "api_key": key,
        "base_url": (os.environ.get("NANOGPT_BASE_URL") or "https://nano-gpt.com/api/v1").rstrip("/"),
        "model": (os.environ.get("NANOGPT_MODEL") or "deepseek/deepseek-v4-flash-0731").strip(),
    }


async def extract_marker_direction(
    norm: NormalizedBiomarker,
    disease_name: str,
    refs: list[MarkerLiteratureRef],
    anthropic_api_key: str,
) -> tuple[list[MarkerDirectionClaim], list[str]]:
    notes: list[str] = []
    nano = nanogpt_config()
    if not anthropic_api_key and not nano:
        notes.append("Neither NANOGPT_API_KEY nor ANTHROPIC_API_KEY set — Stage 4b LLM extraction skipped.")
        return [], notes
    if not refs:
        notes.append("No literature refs available for Stage 4b extraction.")
        return [], notes

    client = None
    if not nano:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_api_key)
        except ImportError:
            notes.append("'anthropic' package not installed — Stage 4b skipped.  Run: pip install anthropic")
            return [], notes

    marker_name = norm.symbol or norm.input_name
    batches = [refs[i : i + BATCH_SIZE] for i in range(0, len(refs), BATCH_SIZE)]
    ref_by_pmid = {r.pmid: r for r in refs}

    all_claims: list[dict] = []
    for batch in batches:
        if nano:
            claims = await asyncio.to_thread(_call_nanogpt, marker_name, disease_name, batch, nano)
        else:
            claims = await asyncio.to_thread(_call_claude, marker_name, disease_name, batch, client)
        all_claims.extend(claims)

    results: list[MarkerDirectionClaim] = []
    for c in all_claims:
        if c.get("direction") == "unclear" or not c.get("pmid"):
            continue
        ref = ref_by_pmid.get(c["pmid"])
        citation = ""
        doi = ""
        if ref:
            if ref.first_author and ref.pub_year:
                citation = f"{ref.first_author} et al. {ref.pub_year}"
            doi = ref.doi or ""
        results.append(MarkerDirectionClaim(
            direction=c.get("direction", "unclear"),
            comparison_population=c.get("comparison_population", ""),
            symptoms=c.get("symptoms", ""),
            supporting_quote=c.get("supporting_quote", ""),
            pmid=c["pmid"],
            citation=citation,
            doi=doi,
        ))

    notes.append(
        f"Stage4b extraction: {len(refs)} refs, {len(batches)} batch(es) → {len(results)} grounded direction claim(s)."
    )
    return results, notes
