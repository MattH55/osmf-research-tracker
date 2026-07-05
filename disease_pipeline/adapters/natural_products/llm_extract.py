"""NP-5 — Claude API abstract extraction for natural products."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re

from ...cache import cache_get, cache_set
from ...config import get_anthropic_api_key
from ...options import PipelineOptions

log = logging.getLogger(__name__)

_llm_sem = asyncio.Semaphore(5)

EXTRACTION_PROMPT = """You are extracting structured data from PubMed abstracts about natural products and {disease_name}.

Abstracts:
{abstract_text}

Extract ALL natural products, supplements, herbs, vitamins, minerals, or food compounds mentioned as interventions.
For each, return a JSON object with these fields:
- np_name: common name (string)
- np_scientific: scientific/IUPAC name if mentioned (string or null)
- np_type: one of ["botanical","nutraceutical","probiotic","amino_acid","food_compound","tcm_herb","vitamin","mineral","other"]
- dosage: dosage if mentioned (string or null)
- outcome: "positive" | "negative" | "neutral" | "unclear"
- outcome_note: 1 sentence describing the result
- study_type: "meta_analysis" | "systematic_review" | "rct" | "observational" | "other"
- mechanism: mechanism mentioned if any (string or null)
- pmid: PMID of the source abstract (string)

Return ONLY a JSON array. If no natural products are mentioned as interventions, return [].
Do not include pharmaceutical drugs or medical devices.
"""


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def _parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    match = re.search(r"\[[\s\S]*\]", text)
    if not match:
        return []
    try:
        data = json.loads(match.group())
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


async def extract_np_from_abstract_batch(
    batch: list[dict],
    disease_name: str,
    client,
) -> list[dict]:
    parts = []
    for ab in batch:
        parts.append(
            f"PMID: {ab.get('pmid', '')}\n"
            f"Title: {ab.get('title', '')}\n"
            f"Year: {ab.get('year', '')}\n"
            f"Types: {', '.join(ab.get('pub_types', []))}\n"
            f"Abstract: {ab.get('abstract_text', '')}\n"
            "---"
        )
    prompt = EXTRACTION_PROMPT.format(
        disease_name=disease_name,
        abstract_text="\n".join(parts),
    )

    async with _llm_sem:
        try:
            response = await asyncio.to_thread(
                client.messages.create,
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text if response.content else "[]"
            items = _parse_json_array(raw)
            out = []
            for item in items:
                if not item.get("np_name"):
                    continue
                pmid = item.get("pmid") or (batch[0].get("pmid") if len(batch) == 1 else "")
                source = next((b for b in batch if str(b.get("pmid")) == str(pmid)), batch[0])
                out.append({
                    **item,
                    "pmid": source.get("pmid"),
                    "year": source.get("year"),
                    "title": source.get("title"),
                    "pub_types": source.get("pub_types", []),
                    "study_type": item.get("study_type") or source.get("study_type", "other"),
                })
            return out
        except Exception as e:
            log.warning("[LLM NP] extraction failed: %s", e)
            return []


async def extract_np_from_abstracts(
    abstracts: list[dict],
    disease_name: str,
    options: PipelineOptions | None = None,
) -> list[dict]:
    opts = options or PipelineOptions()
    if opts.skip_llm_extract or not abstracts:
        return []

    api_key = get_anthropic_api_key()
    if not api_key:
        log.info("[LLM NP] No ANTHROPIC_API_KEY — skipping extraction")
        return []

    try:
        import anthropic
    except ImportError:
        log.warning("[LLM NP] anthropic package not installed — skipping")
        return []

    client = anthropic.Anthropic(api_key=api_key)
    all_extracted: list[dict] = []
    batch_size = 5

    for i in range(0, len(abstracts), batch_size):
        batch = abstracts[i : i + batch_size]
        batch_key = _cache_key("".join(a.get("abstract_text", "") for a in batch))
        cached = cache_get("llm_np", batch_key)
        if cached is not None:
            all_extracted.extend(cached.get("items", []))
            continue

        items = await extract_np_from_abstract_batch(batch, disease_name, client)
        cache_set("llm_np", batch_key, {"items": items})
        all_extracted.extend(items)

    log.info("[LLM NP] extracted %d NP mentions for '%s'", len(all_extracted), disease_name)
    return all_extracted