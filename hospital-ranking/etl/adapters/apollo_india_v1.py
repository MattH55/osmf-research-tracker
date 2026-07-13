#!/usr/bin/env python3
"""
Adapter for Apollo Hospitals (India).

Apollo is India's largest private hospital chain with strong medical tourism
presence. JCI accredited with international patient department.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from .base import FacilityAdapter, RawDocument, PriceObservation

FACILITY_ID = "intl-apollo-delhi-in-01"
FACILITY_NAME = "Apollo Hospitals - Delhi"
COUNTRY = "IN"
CITY = "Delhi"
SOURCE_URL = "https://www.apollohospitals.com"
ROBOTS_URL = "https://www.apollohospitals.com/robots.txt"


class ApolloIndiaV1(FacilityAdapter):
    """Apollo Hospitals adapter (India)."""

    def __init__(self):
        self.facility_id = FACILITY_ID
        self.facility_name = FACILITY_NAME
        self.country = COUNTRY
        self.city = CITY
        self.source_url = SOURCE_URL
        self.robots_url = ROBOTS_URL
        super().__init__()

    def fetch(self) -> list[RawDocument]:
        """Fetch Apollo pricing pages."""
        docs = []

        pricing_urls = [
            "https://www.apollohospitals.com/international-patient/specialties/orthopedics/",
            "https://www.apollohospitals.com/international-patient/specialties/ophthalmology/",
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
        """Extract prices from Apollo pages."""
        observations = []

        for doc in docs:
            content = self.load_document(doc.content_hash)
            if not content:
                content = doc.content

            if "orthopedic" in doc.url.lower():
                observations.extend(self._extract_orthopedic_prices(content, doc))
            elif "ophthalmology" in doc.url.lower():
                observations.extend(self._extract_cataract_prices(content, doc))

        return observations

    def _extract_orthopedic_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract TKA/THA prices (India most affordable of all destinations)."""
        observations = []

        patterns = [
            r"[\$USD]\s*([\d,]+).*?(?:knee|hip|joint)",
            r"(?:knee|hip|joint).*?[\$USD]\s*([\d,]+)",
            r"₹\s*([\d,]+).*?(?:knee|hip)",  # Indian Rupee
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(",", "")
                    price_value = float(amount_str)

                    # If Indian Rupees, convert to USD (~0.012 INR/USD)
                    if "₹" in match.group(0):
                        price_usd = price_value * 0.012
                    else:
                        price_usd = price_value

                    # TKA sanity check (India ~$3k-$8k range)
                    if 2500 < price_usd < 12000:
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
                                "inpatient_nights": 3,
                                "physio_sessions": 6,
                                "device_brand": None,
                                "explicitly_excludes": [],
                                "completeness_score": 0.82,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:apollo_v1",
                                "confidence": 0.74,
                            },
                            observation_date=date.today().isoformat(),
                            notes="India pricing ~70-75% lower than US. Apollo is JCI-accredited. Exchange rate: 1 INR = $0.012 USD.",
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
                    if 500 < price_usd < 2500:
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
                                "completeness_score": 0.90,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:apollo_v1",
                                "confidence": 0.80,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Apollo Ophthalmology pricing. India offers ~80% savings vs US for cataract.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations
