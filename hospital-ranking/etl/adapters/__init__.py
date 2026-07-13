"""
International facility price adapters.

Each adapter:
1. Fetches raw documents from a facility website
2. Extracts structured price observations
3. Caches raw content with SHA256 hash for reproducibility
4. Respects robots.txt and rate-limiting
"""

from .base import FacilityAdapter, RawDocument, PriceObservation, register_facility
from .hospital_angeles_mexico_v1 import HospitalAngelesMexicoV1
from .cima_costa_rica_v1 import CimaCostaRicaV1
from .samitivej_thailand_v1 import SamitivejThailandV1
from .apollo_india_v1 import ApolloIndiaV1
from .american_hospital_turkey_v1 import AmericanHospitalTurkeyV1

__all__ = [
    "FacilityAdapter",
    "RawDocument",
    "PriceObservation",
    "register_facility",
    "HospitalAngelesMexicoV1",
    "CimaCostaRicaV1",
    "SamitivejThailandV1",
    "ApolloIndiaV1",
    "AmericanHospitalTurkeyV1",
]
