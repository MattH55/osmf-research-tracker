"""Pipeline configuration — secrets from env or config/secrets.local.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "agent-pipeline" / "cache"
LOG_DIR = ROOT / "data" / "agent-pipeline" / "logs"
RESULTS_DIR = ROOT / "data" / "agent-pipeline" / "results"

NCBI_TOOL = "OSMF-BiomarkerAgentPipeline"
NCBI_EMAIL = os.environ.get("NCBI_EMAIL", "research@opensourcemed.info")

CACHE_TTL_DAYS = 30
SOURCE_TIMEOUT_S = 10
SOURCE_MAX_RETRIES = 2
LITERATURE_MAX_ABSTRACTS = 80
PUBMED_RATE_LIMIT_S = 0.11  # with API key, up to 10 req/s
GENERIC_RATE_LIMIT_S = 0.2

EXCLUDED_SOURCES = {"drugbank"}


def load_secrets() -> dict:
    secrets = {}
    path = ROOT / "config" / "secrets.local.json"
    if path.exists():
        secrets.update(json.loads(path.read_text(encoding="utf-8")))
    if os.environ.get("NCBI_API_KEY"):
        secrets["NCBI_API_KEY"] = os.environ["NCBI_API_KEY"]
    if os.environ.get("OPENAI_API_KEY"):
        secrets["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
    return secrets


def ncbi_api_key() -> str | None:
    return load_secrets().get("NCBI_API_KEY")


def openai_api_key() -> str | None:
    return load_secrets().get("OPENAI_API_KEY")