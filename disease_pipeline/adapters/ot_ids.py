"""Open Targets disease ID normalization."""
from __future__ import annotations

from ..models import DiseaseIdentifiers


def ot_disease_id(identifiers: DiseaseIdentifiers) -> str | None:
    """Open Targets v4 expects underscore IDs e.g. MONDO_0005148."""
    if identifiers.mondo_id:
        return identifiers.mondo_id.replace(":", "_")
    if identifiers.efo_id:
        return identifiers.efo_id.replace(":", "_")
    return None