"""Bounded pipeline options — prevents hangs via limits and phase gating."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PipelineOptions:
    """
    Phase gates (each phase includes all lower phases):
      1 — seeds + Open Targets genes/drugs + basic dedupe
      2 — + HPO + ClinicalTrials endpoints + LOINC lookup table
      3 — + via-biomarker drugs (ChEMBL + DGIdb, capped gene fan-out)
      4 — + DisGeNET + PubMed validation (tier C only, capped)
      5 — + UniProt enrichment + HMDB bulk cache + API normalize fallback
      6 — + clinical trial registry + literature evidence (Cochrane, meta-analyses, trials)
      7 — + natural products (PubMed/CT.gov clinical + ChEMBL mechanistic + GMI/Examine)
      8 — + full 20-database NP repurposing pipeline (clinical + traditional + structural + dietary)
    """

    phase: int = 1
    use_cache: bool = True
    skip_pubmed: bool = False
    skip_hmdb: bool = True
    skip_disgenet: bool = False
    skip_via_biomarker: bool = False
    skip_clinical: bool = False
    skip_evidence: bool = False
    skip_natural_products: bool = False
    skip_llm_extract: bool = False
    skip_pubchem_enrich: bool = False
    skip_greenmedinfo: bool = False
    skip_examine: bool = False
    skip_clinical_np: bool = False
    skip_mechanistic_np: bool = False
    skip_np_evidence: bool = False
    skip_np_synthesis: bool = False
    skip_nccih: bool = False
    skip_tcmsp: bool = False
    skip_batman_tcm: bool = False
    skip_imppat: bool = False
    skip_etcm: bool = False
    skip_symmap: bool = False
    skip_npass: bool = False
    skip_dukes: bool = False
    skip_knapsack: bool = False
    skip_dsld: bool = False
    skip_phenol_explorer: bool = False
    skip_foodb: bool = False
    skip_coconut: bool = False
    use_playwright: bool = False
    max_np_evidence: int = 20
    max_genes_for_drugs: int = 15
    max_pubmed_items: int = 20
    max_pubmed_np_results: int = 50
    max_ct_studies: int = 50
    max_evidence_drugs: int = 25
    max_trials_per_drug: int = 8
    max_literature_per_type: int = 5
    disease_timeout_sec: float = 90.0
    batch_concurrency: int = 2
    sources_queried: list[str] = field(default_factory=list)

    def includes(self, required_phase: int) -> bool:
        return self.phase >= required_phase

    def note_source(self, name: str) -> None:
        if name not in self.sources_queried:
            self.sources_queried.append(name)


def options_for_phase(phase: int, **kwargs) -> PipelineOptions:
    opts = PipelineOptions(phase=phase, **kwargs)
    if phase < 4:
        opts.skip_pubmed = True
    if phase < 3:
        opts.skip_via_biomarker = True
    if phase < 2:
        opts.skip_clinical = True
    if phase < 4:
        opts.skip_disgenet = True
    if phase < 6:
        opts.skip_evidence = True
    return opts