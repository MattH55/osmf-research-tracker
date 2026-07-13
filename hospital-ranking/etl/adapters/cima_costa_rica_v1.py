#!/usr/bin/env python3
"""
Adapter for CIMA San José (Costa Rica).

CIMA is one of Costa Rica's premier medical tourism destinations,
known for orthopedic and cosmetic procedures.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from .base import FacilityAdapter, RawDocument, PriceObservation

FACILITY_ID = "intl-cima-sanjose-cr-01"
FACILITY_NAME = "CIMA San José - Costa Rica"
COUNTRY = "CR"
CITY = "San José"
SOURCE_URL = "https://www.cimacr.com"
ROBOTS_URL = "https://www.cimacr.com/robots.txt"


class CimaCostaRicaV1(FacilityAdapter):
    """CIMA San José adapter (Costa Rica)."""

    def __init__(self):
        self.facility_id = FACILITY_ID
        self.facility_name = FACILITY_NAME
        self.country = COUNTRY
        self.city = CITY
        self.source_url = SOURCE_URL
        self.robots_url = ROBOTS_URL
        super().__init__()

    def fetch(self) -> list[RawDocument]:
        """Fetch CIMA pricing pages."""
        docs = []

        pricing_urls = [
            "https://www.cimacr.com/orthopedics/knee-replacement/",
            "https://www.cimacr.com/orthopedics/hip-replacement/",
            "https://www.cimacr.com/surgery/bariatric-surgery/",
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
        """Extract prices from CIMA pages."""
        observations = []

        for doc in docs:
            content = self.load_document(doc.content_hash)
            if not content:
                content = doc.content

            if "knee" in doc.url.lower():
                observations.extend(self._extract_tka_prices(content, doc))
            elif "hip" in doc.url.lower():
                observations.extend(self._extract_tha_prices(content, doc))
            elif "bariatric" in doc.url.lower():
                observations.extend(self._extract_bariatric_prices(content, doc))

        return observations

    def _extract_tka_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract TKA prices (Costa Rica typically 20-30% higher than Mexico)."""
        observations = []

        patterns = [
            r"[\$USD]\s*([\d,]+).*?knee",
            r"knee.*?[\$USD]\s*([\d,]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    price_usd = float(match.group(1).replace(",", ""))
                    if 10000 < price_usd < 25000:
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
                                "physio_sessions": 8,
                                "device_brand": None,
                                "explicitly_excludes": [],
                                "completeness_score": 0.88,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:cima_v1",
                                "confidence": 0.78,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Costa Rica pricing typically 20-30% higher than Mexico.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations

    def _extract_tha_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract THA prices."""
        observations = []
        patterns = [
            r"[\$USD]\s*([\d,]+).*?hip",
            r"hip.*?[\$USD]\s*([\d,]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    price_usd = float(match.group(1).replace(",", ""))
                    if 11000 < price_usd < 28000:
                        obs = PriceObservation(
                            observation_id=str(uuid.uuid4()),
                            facility_id=self.facility_id,
                            procedure_slug="tha",
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
                                "physio_sessions": 8,
                                "device_brand": None,
                                "explicitly_excludes": [],
                                "completeness_score": 0.88,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:cima_v1",
                                "confidence": 0.78,
                            },
                            observation_date=date.today().isoformat(),
                            notes="THA pricing from CIMA San José.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations

    def _extract_bariatric_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract bariatric prices."""
        observations = []
        patterns = [
            r"[\$USD]\s*([\d,]+).*?(?:sleeve|bypass|bariatric)",
            r"(?:sleeve|bypass|bariatric).*?[\$USD]\s*([\d,]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    price_usd = float(match.group(1).replace(",", ""))
                    if 5000 < price_usd < 14000:
                        obs = PriceObservation(
                            observation_id=str(uuid.uuid4()),
                            facility_id=self.facility_id,
                            procedure_slug="sleeve",
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
                                    "inpatient_nights",
                                ],
                                "inpatient_nights": 1,
                                "physio_sessions": None,
                                "device_brand": None,
                                "explicitly_excludes": ["post_op_nutritional_support"],
                                "completeness_score": 0.72,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:cima_v1",
                                "confidence": 0.72,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Bariatric pricing from CIMA; nutritional support not explicitly included.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations
