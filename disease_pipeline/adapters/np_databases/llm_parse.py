"""LLM extraction from raw HTML/text for scraped NP databases."""
from __future__ import annotations

import json
import logging
import re

from ...config import get_anthropic_api_key
from ..natural_products.llm_extract import _parse_json_array

log = logging.getLogger(__name__)


async def _claude_extract(prompt: str) -> list[dict] | dict:
    api_key = get_anthropic_api_key()
    if not api_key:
        return []
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text if msg.content else ""
        parsed = _parse_json_array(text)
        if parsed:
            return parsed
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
    except Exception as e:
        log.warning("[LLM parse] failed: %s", e)
    return []


async def extract_gmi_disease(html_text: str, disease_name: str) -> list[dict]:
    prompt = f"""Extract natural product substances from this GreenMedInfo disease page for {disease_name}.
Return JSON array: [{{"substance_name": str, "gmi_slug": str, "study_count": int,
"evidence_tier": "GOLD"|"SILVER"|"BRONZE", "pharmacological_actions": [str]}}]

Page text:
{html_text[:12000]}"""
    result = await _claude_extract(prompt)
    return result if isinstance(result, list) else []


async def extract_examine_hem(html_text: str, condition_name: str) -> list[dict]:
    prompt = f"""Extract Human Effect Matrix rows from this Examine.com condition page for {condition_name}.
Return JSON array: [{{"supplement_name": str, "examine_slug": str, "effect_direction": str,
"evidence_grade": "A"|"B"|"C"|"D", "study_count": int, "health_outcome": str}}]

Page text:
{html_text[:12000]}"""
    result = await _claude_extract(prompt)
    return result if isinstance(result, list) else []


async def extract_nccih_factsheet(html_text: str, np_name: str) -> dict:
    prompt = f"""Extract NCCIH fact sheet data for {np_name}.
Return JSON: {{"what_science_says": str, "safety_concerns": [str], "drug_interactions": [str],
"bottom_line": str, "conditions_studied": [str]}}

Page text:
{html_text[:10000]}"""
    result = await _claude_extract(prompt)
    return result if isinstance(result, dict) else {}