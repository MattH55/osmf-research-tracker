"""LLM synthesis pass for top NP candidates."""
from __future__ import annotations

import json
import logging

from ...config import get_anthropic_api_key
from ...models import NaturalProduct

log = logging.getLogger(__name__)

SYNTHESIS_PROMPT = """You are summarising natural product evidence for a disease intelligence platform.

Disease: {disease_name}
Top NP candidates (by score):
{np_json_summary}

For each candidate, write ONE sentence summarising the evidence strength and primary mechanism.
Focus on: what the best evidence shows, what the primary mechanism is, and any key safety notes.

Return ONLY a JSON object: {{ "canonical_id": "one_sentence_summary", ... }}
"""


async def synthesise_top_nps(
    disease_name: str,
    ranked_nps: list[NaturalProduct],
    *,
    top_n: int = 15,
) -> dict[str, str]:
    api_key = get_anthropic_api_key()
    if not api_key or not ranked_nps:
        return {}

    summary_rows = []
    for np in ranked_nps[:top_n]:
        summary_rows.append({
            "canonical_id": np.canonical_id,
            "name": np.name,
            "score": np.score,
            "sources": np.sources,
            "tier": np.np_evidence_tier.value,
            "mechanism": np.mechanism,
            "key_findings": np.key_findings,
            "safety": np.safety_tier.value,
        })

    prompt = SYNTHESIS_PROMPT.format(
        disease_name=disease_name,
        np_json_summary=json.dumps(summary_rows, indent=2),
    )

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        msg = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text if msg.content else "{}"
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
    except Exception as e:
        log.warning("[NP synthesis] failed: %s", e)
    return {}