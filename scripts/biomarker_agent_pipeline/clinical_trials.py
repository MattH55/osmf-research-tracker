"""ClinicalTrials.gov cross-reference for clinical-tier evidence."""
from __future__ import annotations

import re

from .http_util import request_json
from .models import NormalizedBiomarker

CT_API = "https://clinicaltrials.gov/api/v2/studies"


def _terms(norm: NormalizedBiomarker) -> list[str]:
    out = []
    for t in [norm.symbol, norm.input, *norm.synonyms[:4]]:
        if t and len(t) >= 3:
            out.append(t)
    return list(dict.fromkeys(out))[:5]


def search_trials_for_biomarker(norm: NormalizedBiomarker, agent: str) -> list[str]:
    nct_ids: list[str] = []
    for term in _terms(norm):
        params = {
            "query.term": f"{agent} {term}",
            "pageSize": "8",
            "format": "json",
        }
        try:
            data = request_json(
                "clinicaltrials",
                f"{agent}|{term}",
                "GET",
                CT_API,
                params=params,
            )
        except Exception:
            continue
        for study in data.get("studies", []):
            nct = study.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
            if not nct:
                continue
            outcomes = []
            out_mod = study.get("protocolSection", {}).get("outcomesModule", {})
            for bucket in ("primaryOutcomes", "secondaryOutcomes"):
                for o in out_mod.get(bucket, []) or []:
                    outcomes.append(o.get("measure", ""))
            outcome_text = " ".join(outcomes).lower()
            term_l = term.lower()
            if re.search(re.escape(term_l[:12]), outcome_text) or term_l in outcome_text:
                nct_ids.append(nct)
    return list(dict.fromkeys(nct_ids))[:10]