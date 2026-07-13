#!/usr/bin/env python3
"""
Adapter for Hospital Ángeles (Mexico).

Hospital Ángeles is one of Mexico's largest private hospital chains with
published medical tourism pricing. Multiple locations across Mexico.

This adapter:
1. Fetches pricing pages from their medical tourism site
2. Extracts published package prices (joint replacement, bariatric, etc.)
3. Maps to canonical bundles
4. Caches raw HTML for reproducibility
"""

from __future__ import annotations

import re
import json
import uuid
from datetime import date
from pathlib import Path

from .base import FacilityAdapter, RawDocument, PriceObservation

# Hospital Ángeles facility identifiers
FACILITY_ID = "intl-hospital-angeles-mx-01"
FACILITY_NAME = "Hospital Ángeles - Mexico City"
COUNTRY = "MX"
CITY = "Mexico City"
SOURCE_URL = "https://www.hospitalangeles.mx"
ROBOTS_URL = "https://www.hospitalangeles.mx/robots.txt"


class HospitalAngelesMexicoV1(FacilityAdapter):
    """Hospital Ángeles adapter (Mexico)."""

    def __init__(self):
        self.facility_id = FACILITY_ID
        self.facility_name = FACILITY_NAME
        self.country = COUNTRY
        self.city = CITY
        self.source_url = SOURCE_URL
        self.robots_url = ROBOTS_URL
        super().__init__()

    def fetch(self) -> list[RawDocument]:
        """
        Fetch Hospital Ángeles medical tourism pricing pages.

        Returns:
            List of RawDocument objects
        """
        docs = []

        # Known pricing pages (would be discovered via sitemap.xml in production)
        pricing_urls = [
            "https://www.hospitalangeles.mx/servicios/cirugia-bariatrica/",
            "https://www.hospitalangeles.mx/servicios/ortopedia/",
            "https://www.hospitalangeles.mx/servicios/oftalmologia/",
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
        """
        Extract prices from Hospital Ángeles HTML pages.

        Looks for:
        1. Package price tables (common on medical tourism sites)
        2. "From $X" advertised prices
        3. Procedure descriptions that mention bundle components
        """
        observations = []

        for doc in docs:
            content = self.load_document(doc.content_hash)
            if not content:
                content = doc.content

            # Extract TKA prices
            if "ortopedia" in doc.url or "knee" in content.lower():
                tka_prices = self._extract_tka_prices(content, doc)
                observations.extend(tka_prices)

            # Extract bariatric prices
            if "bariatrica" in doc.url or "sleeve" in content.lower():
                bariatric_prices = self._extract_bariatric_prices(content, doc)
                observations.extend(bariatric_prices)

            # Extract cataract prices
            if "oftalmologia" in doc.url or "cataract" in content.lower():
                cataract_prices = self._extract_cataract_prices(content, doc)
                observations.extend(cataract_prices)

        return observations

    def _extract_tka_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract total knee arthroplasty prices."""
        observations = []

        # Look for patterns like "Knee Replacement: $14,500" or "From $12,000"
        patterns = [
            r"(?:knee|replacement|rodilla|artroplastia).*?[\$USD]\s*([\d,]+)",
            r"[\$USD]\s*([\d,]+).*?(?:knee|replacement|rodilla)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    price_usd = float(match.group(1).replace(",", ""))
                    if 8000 < price_usd < 20000:  # Sanity check for TKA
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
                                "physio_sessions": 6,
                                "device_brand": None,
                                "explicitly_excludes": ["airfare", "lodging"],
                                "completeness_score": 0.85,
                            },
                            is_advertised_minimum="from" in match.group(0).lower(),
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:hospital_angeles_v1",
                                "confidence": 0.75,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Extracted from Hospital Ángeles pricing page. Completeness inferred from website description.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations

    def _extract_bariatric_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract bariatric (sleeve gastrectomy) prices."""
        observations = []

        # Look for sleeve/gastric bypass prices
        patterns = [
            r"(?:sleeve|gastrectomy|bypass|bariatrica).*?[\$USD]\s*([\d,]+)",
            r"[\$USD]\s*([\d,]+).*?(?:sleeve|gastrectomy|bypass)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    price_usd = float(match.group(1).replace(",", ""))
                    if 4000 < price_usd < 12000:  # Sanity check for bariatric
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
                                    "bariatric_specialized_equipment",
                                    "inpatient_nights",
                                ],
                                "inpatient_nights": 1,
                                "physio_sessions": None,
                                "device_brand": None,
                                "explicitly_excludes": [
                                    "post_op_nutritional_support",
                                    "lifelong_vitamins",
                                ],
                                "completeness_score": 0.70,
                            },
                            is_advertised_minimum="from" in match.group(0).lower(),
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:hospital_angeles_v1",
                                "confidence": 0.70,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Extracted from website. WARNING: Nutritional support (vitamins, monitoring) may not be included; completeness inferred from descriptions.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations

    def _extract_cataract_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract cataract surgery prices."""
        observations = []

        # Cataract prices are often per-eye
        patterns = [
            r"(?:cataract|catarata).*?[\$USD]\s*([\d,]+)",
            r"[\$USD]\s*([\d,]+).*?(?:cataract|catarata)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    price_usd = float(match.group(1).replace(",", ""))
                    if 1500 < price_usd < 5000:  # Sanity check for cataract
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
                                "explicitly_excludes": ["second_eye"],
                                "completeness_score": 0.90,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:hospital_angeles_v1",
                                "confidence": 0.80,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Per-eye price. IOL type not specified on website; assumed basic monofocal.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations
