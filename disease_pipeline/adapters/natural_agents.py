"""OSMF narrative-review natural agents from opensourcemed.info/chronic-disease.html."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from ..adapters.normalize import seed_key
from ..models import EvidenceTier, Therapeutic

log = logging.getLogger(__name__)

NATURAL_AGENTS_PATH = Path(__file__).resolve().parent.parent / "seeds" / "natural_agents.json"
OSMF_CHRONIC_DISEASE_URL = "https://opensourcemed.info/chronic-disease.html"


def _slug(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower()).strip("-")


def _load_catalog() -> dict[str, dict]:
    if not NATURAL_AGENTS_PATH.exists():
        return {}
    try:
        return json.loads(NATURAL_AGENTS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Failed to load natural agents seed: %s", e)
        return {}


def _review_summary(review: dict) -> str:
    parts = [review.get("title", "")]
    if review.get("authors"):
        parts.append(review["authors"])
    if review.get("year"):
        parts.append(str(review["year"]))
    return " · ".join(p for p in parts if p)


def get_for_disease(disease_name: str) -> tuple[list[Therapeutic], dict | None]:
    """
    Return natural-agent therapeutics and review metadata for a disease seed key.
    Only diseases covered on the OSMF chronic-disease page are populated.
    """
    key = seed_key(disease_name)
    entry = _load_catalog().get(key)
    if not entry:
        return [], None

    review = entry.get("review", {})
    mechanism = _review_summary(review)
    source_page = entry.get("source_page", OSMF_CHRONIC_DISEASE_URL)
    agents: list[Therapeutic] = []

    for agent in entry.get("agents", []):
        name = agent.get("name", "").strip()
        if not name:
            continue
        canonical_id = f"natural:{_slug(name)}"
        display = name
        aliases = agent.get("aliases") or []
        if aliases:
            display = f"{name} ({aliases[0]})" if len(aliases) == 1 else name

        agents.append(
            Therapeutic(
                canonical_id=canonical_id,
                name=display,
                drug_type=agent.get("drug_type", "supplement"),
                mechanism=mechanism,
                max_phase=0,
                source_type="natural_agent",
                sources=["OSMF Chronic Disease Review"],
                evidence_tier=EvidenceTier.C,
                score=30,
            )
        )

    meta = {
        "condition_label": entry.get("condition_label"),
        "source_page": source_page,
        "review": review,
        "agent_count": len(agents),
    }
    if agents:
        log.info(
            "[Natural agents] %s → %d agents from OSMF chronic-disease review",
            disease_name,
            len(agents),
        )
    return agents, meta