#!/usr/bin/env python3
"""
Base adapter protocol for international facility price extraction.

Each facility adapter:
1. Fetches raw HTML/PDF documents (caches with SHA256 hash)
2. Extracts structured price observations
3. Respects robots.txt and rate-limits
4. Tracks extraction confidence (especially for LLM-extracted fields)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
import hashlib
import json
import time
import urllib.request
import urllib.robotparser

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "adapters" / "cache"
FACILITY_REGISTRY = ROOT / "data" / "adapters" / "facility_registry.json"

USER_AGENT = (
    "Mozilla/5.0 (compatible; OpenSourceMed-PriceOS/1.0; "
    "+https://opensourcemed.info; medical-price-research)"
)


@dataclass
class RawDocument:
    """Cached raw document from facility website."""
    facility_id: str
    url: str
    content: str  # Raw HTML/text
    content_hash: str  # SHA256
    retrieved_at: str  # ISO 8601
    content_type: str  # "text/html", "application/pdf", etc.
    status_code: int  # HTTP status


@dataclass
class PriceObservation:
    """Extracted price observation (maps to schema/price_observation.schema.json)."""
    observation_id: str
    facility_id: str
    procedure_slug: str
    price_type: str
    amount_native: float
    currency: str
    fx_rate_to_usd: float
    fx_rate_date: str
    amount_usd: float
    bundle: dict
    is_advertised_minimum: bool
    is_estimate: bool
    provenance: dict
    observation_date: str
    notes: Optional[str] = None


class FacilityAdapter(ABC):
    """Abstract base class for facility price adapters."""

    facility_id: str  # Unique identifier (e.g., "intl-hospital-angeles-mx-01")
    facility_name: str
    country: str  # ISO 3166-1 alpha-2
    city: str
    source_url: str  # Base website URL
    robots_url: str  # robots.txt URL

    def __init__(self):
        """Initialize adapter with facility metadata."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.robot_parser = urllib.robotparser.RobotFileParser()
        self.robot_parser.set_url(self.robots_url)
        try:
            self.robot_parser.read()
        except Exception:
            # If robots.txt fails, assume OK but rate-limit aggressively
            pass

    @abstractmethod
    def fetch(self) -> list[RawDocument]:
        """
        Fetch raw documents from facility website.

        Returns:
            List of RawDocument objects (one per page/document)

        Must:
        - Respect robots.txt (check before each request)
        - Rate-limit to <=1 req/30s per host
        - Cache raw content with SHA256 hash
        - Handle redirects, retries, timeouts
        - Return None or skip if robots.txt disallows
        """
        pass

    @abstractmethod
    def extract(self, docs: list[RawDocument]) -> list[PriceObservation]:
        """
        Extract price observations from raw documents.

        Args:
            docs: List of RawDocument objects from fetch()

        Returns:
            List of PriceObservation objects

        Must:
        - Map facility's pricing format to canonical bundle
        - Set completeness_score based on what's included
        - Mark LLM-extracted fields with confidence <1.0
        - Set is_advertised_minimum=True if "from $X" (floor price)
        - Set observation_date to when price was valid (not when scraped)
        """
        pass

    def can_fetch(self, url: str) -> bool:
        """Check if robots.txt allows fetching this URL."""
        if not self.robot_parser.can_fetch(USER_AGENT, url):
            return False
        return True

    def fetch_url(self, url: str, timeout: int = 30, retries: int = 3) -> Optional[str]:
        """
        Fetch a single URL with retries and rate-limiting.

        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
            retries: Number of retries on failure

        Returns:
            Response text, or None if all retries failed
        """
        if not self.can_fetch(url):
            print(f"robots.txt disallows: {url}")
            return None

        last_err = None
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    content = resp.read().decode("utf-8", errors="replace")
                    # Rate-limit: 1 req per 30 sec
                    if attempt < retries - 1:
                        time.sleep(30)
                    return content
            except Exception as exc:
                last_err = exc
                if attempt < retries - 1:
                    wait = 10 * (attempt + 1)
                    print(f"Fetch failed ({attempt + 1}/{retries}); retry in {wait}s: {exc}")
                    time.sleep(wait)
        print(f"Fetch failed after {retries} retries: {last_err}")
        return None

    def cache_document(self, doc: RawDocument) -> Path:
        """
        Cache raw document with SHA256 hash filename.

        Args:
            doc: RawDocument to cache

        Returns:
            Path to cached file
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        doc_dir = CACHE_DIR / self.facility_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        # Filename: SHA256 hash (ensures dedup and reproducibility)
        filename = doc_dir / f"{doc.content_hash}.jsonl"
        if filename.exists():
            return filename

        # Write JSONL: one line = one document
        with open(filename, "w", encoding="utf-8") as f:
            doc_dict = {
                "facility_id": doc.facility_id,
                "url": doc.url,
                "content_hash": doc.content_hash,
                "retrieved_at": doc.retrieved_at,
                "content_type": doc.content_type,
                "status_code": doc.status_code,
                "note": "Raw content omitted (see .html file)",
            }
            f.write(json.dumps(doc_dict) + "\n")

        # Also cache raw HTML
        html_path = doc_dir / f"{doc.content_hash}.html"
        html_path.write_text(doc.content, encoding="utf-8")

        return filename

    def load_document(self, content_hash: str) -> Optional[str]:
        """Load cached document by hash."""
        html_path = CACHE_DIR / self.facility_id / f"{content_hash}.html"
        if html_path.exists():
            return html_path.read_text(encoding="utf-8")
        return None

    @staticmethod
    def hash_content(content: str) -> str:
        """Compute SHA256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


def register_facility(adapter: FacilityAdapter) -> None:
    """Register facility adapter in global registry."""
    FACILITY_REGISTRY.parent.mkdir(parents=True, exist_ok=True)

    registry = {}
    if FACILITY_REGISTRY.exists():
        registry = json.loads(FACILITY_REGISTRY.read_text(encoding="utf-8"))

    registry[adapter.facility_id] = {
        "name": adapter.facility_name,
        "country": adapter.country,
        "city": adapter.city,
        "source_url": adapter.source_url,
        "adapter_class": adapter.__class__.__name__,
        "registered_at": datetime.now().isoformat(),
    }

    FACILITY_REGISTRY.write_text(json.dumps(registry, indent=2), encoding="utf-8")
