"""Module 1: registry. Resolves phenotypes.csv against live EFO/MONDO terms
and fails if any pinned term is obsolete.
"""
from __future__ import annotations

from .adapters import ols
from .models import Phenotype


def check_registry(phenotypes: list[Phenotype]) -> dict:
    report = {"checked": [], "obsolete": [], "unmapped": []}
    for p in phenotypes:
        if p.mondo_id:
            try:
                current = ols.check_term_current(p.mondo_id, "mondo")
                report["checked"].append({"phenotype_id": p.phenotype_id, "term": p.mondo_id, "current": current})
                if not current:
                    report["obsolete"].append(p.phenotype_id)
            except ols.ObsoleteTermError:
                report["obsolete"].append(p.phenotype_id)
        elif p.efo_id:
            try:
                current = ols.check_term_current(p.efo_id, "efo")
                report["checked"].append({"phenotype_id": p.phenotype_id, "term": p.efo_id, "current": current})
                if not current:
                    report["obsolete"].append(p.phenotype_id)
            except ols.ObsoleteTermError:
                report["obsolete"].append(p.phenotype_id)
        elif p.search_state != "not_searched":
            # target/reference phenotypes without a resolvable term (e.g. PACVS)
            # are expected here; anything else with real evidence and no term
            # is a data-entry gap worth surfacing, not a build failure.
            report["unmapped"].append(p.phenotype_id)
    return report
