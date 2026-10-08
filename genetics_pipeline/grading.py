"""Display-grade computation (build spec section 2).

A single A-D badge is computed from tier + quality flags, never curated by
hand, so the rule lives here in versioned code:

  A = T1, genome-wide significant, replicated
  B = T1, significant, unreplicated
  C = T1 suggestive, or any T2
  D = T3 only

A `tested_null` result records absence of evidence, not a graded finding, so
it carries no letter grade.
"""
from __future__ import annotations

from .models import Association


def compute_grade(assoc: Association) -> str | None:
    if assoc.result == "tested_null":
        return None

    if assoc.tier == "T1":
        if assoc.result == "significant":
            return "A" if assoc.replicated else "B"
        if assoc.result == "suggestive":
            return "C"
        return None

    if assoc.tier == "T2":
        return "C"

    if assoc.tier == "T3":
        return "D"

    return None


def grade_all(associations: list[Association]) -> list[Association]:
    for a in associations:
        a.grade = compute_grade(a)
    return associations
