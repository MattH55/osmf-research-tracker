#!/usr/bin/env python3
"""
Adapter for Samitivej Hospital (Thailand).

Samitivej is one of Thailand's largest private hospitals with strong
international patient base. Based in Bangkok.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from .base import FacilityAdapter, RawDocument, PriceObservation

FACILITY_ID = "intl-samitivej-th-01"
FACILITY_NAME = "Samitivej Hospital - Bangkok"
COUNTRY = "TH"
CITY = "Bangkok"
SOURCE_URL = "https://www.samitivejhospitals.com"
ROBOTS_URL = "https://www.samitivejhospitals.com/robots.txt"


class SamitivejThailandV1(FacilityAdapter):
    """Samitivej Hospital adapter (Thailand)."""

    def __init__(self):
        self.facility_id = FACILITY_ID
        self.facility_name = FACILITY_NAME
        self.country = COUNTRY
        self.city = CITY
        self.source_url = SOURCE_URL
        self.robots_url = ROBOTS_URL
        super().__init__()

    def fetch(self) -> list[RawDocument]:
        """Fetch Samitivej pricing pages."""
        docs = []

        pricing_urls = [
            "https://www.samitivejhospitals.com/international/orthopedic-surgery/",
            "https://www.samitivejhospitals.com/international/eye-center/",
        ]

        for url in pricing_urls:
            print(f"Fetching {url}…")
            content = self.fetch_url(url)
            if content:
                content_hash = self.hash_content(content)
                doc = RawDocument(
                    facility_id=self.facility_id,
                    url=url,
                    content=content,
                    content_hash=content_hash,
                    retrieved_at=date.today().isoformat() + "T00:00:00Z",
                    content_type="text/html",
                    status_code=200,
                )
                self.cache_document(doc)
                docs.append(doc)

        return docs

    def extract(self, docs: list[RawDocument]) -> list[PriceObservation]:
        """Extract prices from Samitivej pages."""
        observations = []

        for doc in docs:
            content = self.load_document(doc.content_hash)
            if not content:
                content = doc.content

            if "orthopedic" in doc.url.lower():
                observations.extend(self._extract_orthopedic_prices(content, doc))
            elif "eye" in doc.url.lower():
                observations.extend(self._extract_cataract_prices(content, doc))

        return observations

    def _extract_orthopedic_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract TKA/THA prices (Thailand significantly cheaper than US/CR/MX)."""
        observations = []

        # Look for both USD and THB prices
        patterns = [
            r"[\$USD]\s*([\d,]+).*?(?:knee|hip|joint)",
            r"(?:knee|hip|joint).*?[\$USD]\s*([\d,]+)",
            r"฿\s*([\d,]+).*?(?:knee|hip)",  # Thai Baht
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(",", "")
                    price_value = float(amount_str)

                    # If Thai Baht, convert to USD (~0.028 THB/USD)
                    if "฿" in match.group(0):
                        price_usd = price_value * 0.028
                    else:
                        price_usd = price_value

                    # TKA sanity check (Thailand ~$5k-$10k range)
                    if 4000 < price_usd < 15000:
                        obs = PriceObservation(
                            observation_id=str(uuid.uuid4()),
                            facility_id=self.facility_id,
                            procedure_slug="tka",
                            price_type="published_package",
                            amount_native=price_usd,
                            currency="USD",
                            fx_rate_to_usd=1.0,
                            fx_rate_date=date.today().isoformat(),
                            amount_usd=price_usd,
                            bundle={
                                "includes": [
                                    "facility_fee",
                                    "surgeon_fee",
                                    "anesthesia",
                                    "implant_device",
                                    "inpatient_nights",
                                    "post_op_physio",
                                ],
                                "inpatient_nights": 2,
                                "physio_sessions": 4,
                                "device_brand": None,
                                "explicitly_excludes": [],
                                "completeness_score": 0.85,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:samitivej_v1",
                                "confidence": 0.75,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Thailand pricing ~50-60% lower than US. Exchange rate: 1 THB = $0.028 USD.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations

    def _extract_cataract_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract cataract prices."""
        observations = []

        patterns = [
            r"[\$USD]\s*([\d,]+).*?(?:cataract|eye)",
            r"(?:cataract|eye).*?[\$USD]\s*([\d,]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    price_usd = float(match.group(1).replace(",", ""))
                    if 1000 < price_usd < 4000:
                        obs = PriceObservation(
                            observation_id=str(uuid.uuid4()),
                            facility_id=self.facility_id,
                            procedure_slug="cataract",
                            price_type="published_package",
                            amount_native=price_usd,
                            currency="USD",
                            fx_rate_to_usd=1.0,
                            fx_rate_date=date.today().isoformat(),
                            amount_usd=price_usd,
                            bundle={
                                "includes": [
                                    "surgeon_fee",
                                    "facility_fee",
                                    "intraocular_lens",
                                    "anesthesia",
                                ],
                                "inpatient_nights": 0,
                                "physio_sessions": None,
                                "device_brand": None,
                                "explicitly_excludes": [],
                                "completeness_score": 0.92,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:samitivej_v1",
                                "confidence": 0.80,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Cataract from Samitivej. Premium IOL may cost extra.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations
