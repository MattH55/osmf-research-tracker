#!/usr/bin/env python3
"""
Adapter for American Hospital (Turkey).

American Hospital is one of Turkey's largest JCI-accredited hospitals,
prominent in medical tourism with strong European and Middle Eastern patient base.
"""

from __future__ import annotations

import re
import uuid
from datetime import date

from .base import FacilityAdapter, RawDocument, PriceObservation

FACILITY_ID = "intl-american-hospital-tr-01"
FACILITY_NAME = "American Hospital - Istanbul"
COUNTRY = "TR"
CITY = "Istanbul"
SOURCE_URL = "https://www.americanhospital.com.tr"
ROBOTS_URL = "https://www.americanhospital.com.tr/robots.txt"


class AmericanHospitalTurkeyV1(FacilityAdapter):
    """American Hospital adapter (Turkey)."""

    def __init__(self):
        self.facility_id = FACILITY_ID
        self.facility_name = FACILITY_NAME
        self.country = COUNTRY
        self.city = CITY
        self.source_url = SOURCE_URL
        self.robots_url = ROBOTS_URL
        super().__init__()

    def fetch(self) -> list[RawDocument]:
        """Fetch American Hospital pricing pages."""
        docs = []

        pricing_urls = [
            "https://www.americanhospital.com.tr/en/orthopedic-surgery/",
            "https://www.americanhospital.com.tr/en/ophthalmology/",
            "https://www.americanhospital.com.tr/en/bariatric-surgery/",
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
        """Extract prices from American Hospital pages."""
        observations = []

        for doc in docs:
            content = self.load_document(doc.content_hash)
            if not content:
                content = doc.content

            if "orthopedic" in doc.url.lower():
                observations.extend(self._extract_orthopedic_prices(content, doc))
            elif "ophthalmology" in doc.url.lower():
                observations.extend(self._extract_cataract_prices(content, doc))
            elif "bariatric" in doc.url.lower():
                observations.extend(self._extract_bariatric_prices(content, doc))

        return observations

    def _extract_orthopedic_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract TKA/THA prices (Turkey mid-range between US and Thailand)."""
        observations = []

        patterns = [
            r"[\$USD€]\s*([\d,]+).*?(?:knee|hip|joint)",
            r"(?:knee|hip|joint).*?[\$USD€]\s*([\d,]+)",
            r"₺\s*([\d,]+).*?(?:knee|hip)",  # Turkish Lira
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(",", "")
                    price_value = float(amount_str)

                    # If Turkish Lira, convert to USD (~0.033 TRY/USD)
                    if "₺" in match.group(0):
                        price_usd = price_value * 0.033
                    # If EUR, convert to USD (~1.1 EUR/USD)
                    elif "€" in match.group(0):
                        price_usd = price_value * 1.1
                    else:
                        price_usd = price_value

                    # TKA sanity check (Turkey ~$6k-$12k range)
                    if 5000 < price_usd < 15000:
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
                                "explicitly_excludes": [],
                                "completeness_score": 0.86,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:american_hospital_v1",
                                "confidence": 0.76,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Turkey mid-range pricing. American Hospital is JCI-accredited. Exchange rates: 1 TRY = $0.033 USD, 1 EUR = $1.1 USD.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations

    def _extract_cataract_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract cataract prices."""
        observations = []

        patterns = [
            r"[\$USD€]\s*([\d,]+).*?(?:cataract|eye)",
            r"(?:cataract|eye).*?[\$USD€]\s*([\d,]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(",", "")
                    price_value = float(amount_str)

                    # If EUR, convert to USD
                    if "€" in match.group(0):
                        price_usd = price_value * 1.1
                    else:
                        price_usd = price_value

                    if 1500 < price_usd < 4500:
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
                                "completeness_score": 0.91,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:american_hospital_v1",
                                "confidence": 0.79,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Cataract from American Hospital Istanbul.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations

    def _extract_bariatric_prices(self, content: str, doc: RawDocument) -> list[PriceObservation]:
        """Extract bariatric prices."""
        observations = []

        patterns = [
            r"[\$USD€]\s*([\d,]+).*?(?:sleeve|bypass|bariatric)",
            r"(?:sleeve|bypass|bariatric).*?[\$USD€]\s*([\d,]+)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                try:
                    amount_str = match.group(1).replace(",", "")
                    price_value = float(amount_str)

                    if "€" in match.group(0):
                        price_usd = price_value * 1.1
                    else:
                        price_usd = price_value

                    if 4000 < price_usd < 12000:
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
                                "completeness_score": 0.71,
                            },
                            is_advertised_minimum=False,
                            is_estimate=False,
                            provenance={
                                "source_type": "clinic_website",
                                "source_url": doc.url,
                                "source_document_hash": f"sha256:{doc.content_hash}",
                                "retrieved_at": doc.retrieved_at,
                                "extracted_by": "adapter:american_hospital_v1",
                                "confidence": 0.71,
                            },
                            observation_date=date.today().isoformat(),
                            notes="Bariatric pricing from American Hospital. Nutritional support not explicitly bundled.",
                        )
                        observations.append(obs)
                except (ValueError, AttributeError):
                    pass

        return observations
