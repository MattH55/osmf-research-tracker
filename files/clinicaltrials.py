"""
clinicaltrials.py
-----------------
ClinicalTrials.gov API v2 (the v1 /api/query endpoints were retired mid-2024).

Base: https://clinicaltrials.gov/api/v2/studies

Used for two things:
  count_trials(cond)        -> how much clinical activity exists for a disease
  post_acute_signal(disease)-> trials mentioning the chronic/post-acute phase,
                               a live supplement to the curated POST_ACUTE table.
"""

from __future__ import annotations
import requests

CT_URL = "https://clinicaltrials.gov/api/v2/studies"


def _count(params: dict, timeout: int = 30) -> int:
    q = dict(params)
    q.update({"countTotal": "true", "pageSize": 1, "fields": "NCTId"})
    try:
        r = requests.get(CT_URL, params=q, timeout=timeout)
        r.raise_for_status()
        return int(r.json().get("totalCount", 0))
    except Exception as e:
        print(f"  [ct.gov] count failed for {params}: {e}")
        return -1  # -1 = lookup error (distinguish from a true zero)


def count_trials(condition: str) -> int:
    """Total registered studies for a condition."""
    return _count({"query.cond": condition})


def post_acute_signal(condition: str, post_acute_terms: list[str]) -> dict:
    """
    Count trials that pair the disease with chronic/post-acute language.
    Returns counts so you can see whether the research community is actively
    studying the post-acute phase (evidence the syndrome is real & tractable).
    """
    total = count_trials(condition)
    chronic_terms = ["chronic", "post-acute", "sequelae", "persistent"] + list(post_acute_terms)
    # one combined term query keeps it to a single request
    term = f'{condition} AND ({" OR ".join(set(chronic_terms))})'
    chronic = _count({"query.term": term})
    return {
        "trials_total": total,
        "trials_post_acute": chronic,
        "post_acute_share": round(chronic / total, 3) if total > 0 else None,
    }
