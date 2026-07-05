#!/usr/bin/env python3
"""Run Stage 1 (normalize) + Stage 3b (marker-vs-disease literature) +
Stage 4b (grounded direction extraction) for every gene mapped to a disease
in disease_biomarkers.py, writing one MarkerAtlasCandidate JSON per gene.

This is the atlas-curation counterpart to run_for_diseases.py, which runs
the drug-repurposing pipeline (Stage 2-4) instead.

Results land in:
    biomarker_pipeline/results/atlas/{slug}/{GENE}.json

Usage (from research-tracker/):
    python -m biomarker_pipeline.run_atlas_for_disease --disease "Asthma" --slug asthma
    python -m biomarker_pipeline.run_atlas_for_disease --disease "Asthma" --slug asthma --skip-llm

Environment variables:
    NCBI_API_KEY        — optional NCBI E-utilities key
    ANTHROPIC_API_KEY    — required for Stage 4b LLM extraction; without it,
                            candidates are still written (with empty claims)
                            so Stage 3b coverage can be inspected, but
                            export_atlas_schema.py will exclude every marker
                            since none will have a grounded direction claim.
"""
import argparse
import asyncio
import logging
import os
import re
import sys
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).parent.parent
if str(_PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_ROOT))

import httpx

from biomarker_pipeline.disease_biomarkers import get_biomarkers_for_disease
from biomarker_pipeline.disease_clinical_biomarkers import get_clinical_biomarkers_for_disease
from biomarker_pipeline.models import MarkerAtlasCandidate, NormalizedBiomarker
from biomarker_pipeline.run_pipeline import _configure_logging
from biomarker_pipeline.stage1_normalize import normalize_biomarker
from biomarker_pipeline.stage3b_marker_literature import mine_marker_literature
from biomarker_pipeline.stage4b_marker_direction import extract_marker_direction

log = logging.getLogger(__name__)

RESULTS_DIR = Path(__file__).parent / "results" / "atlas"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def _process_gene(
    gene: str,
    disease_name: str,
    ncbi_key: str,
    anthropic_key: str,
    max_literature: int,
    client: httpx.AsyncClient,
    is_gene_symbol: bool = True,
) -> MarkerAtlasCandidate:
    if is_gene_symbol:
        norm = await normalize_biomarker(gene, client)
    else:
        # Skip stage1's UniProt/HGNC gene-symbol lookup entirely for clinical
        # biomarkers — it false-positives on real biomarker names that
        # happen to collide with an unrelated gene (observed live: "Blood
        # Eosinophil Count" -> gene "MPE", "Sputum Eosinophils" -> "FAF2").
        # The input name IS the correct canonical identity here; no ID
        # resolution is needed for the literature search or the atlas schema.
        norm = NormalizedBiomarker(input_name=gene, symbol=gene, synonyms=[gene], entity_type="biomarker")
    refs, lit_notes = await mine_marker_literature(norm, disease_name, client, ncbi_key, max_literature)
    claims, llm_notes = await extract_marker_direction(norm, disease_name, refs, anthropic_key)
    return MarkerAtlasCandidate(
        symbol=gene,
        synonyms=norm.synonyms,
        entity_type=norm.entity_type,
        claims=claims,
        coverage_notes=lit_notes + llm_notes,
    )


async def _main(args: argparse.Namespace) -> None:
    if args.marker_source == "gene":
        genes = get_biomarkers_for_disease(args.disease)
        source_desc = "disease_biomarkers.py (drug-target genes)"
    else:
        genes = get_clinical_biomarkers_for_disease(args.disease)
        source_desc = "disease_clinical_biomarkers.py (real lab/clinical biomarkers)"
    if not genes:
        log.error("No marker mapping found for disease '%s' in %s", args.disease, source_desc)
        sys.exit(1)

    slug = args.slug or _slug(args.disease)
    out_dir = RESULTS_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    ncbi_key = os.environ.get("NCBI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not anthropic_key and not args.skip_llm:
        log.warning(
            "ANTHROPIC_API_KEY not set — Stage 4b will be skipped. Candidates will be written with "
            "empty claims; export_atlas_schema.py will exclude every marker until this is set and rerun."
        )

    log.info("Disease: %s (%d genes) → %s", args.disease, len(genes), out_dir)

    async with httpx.AsyncClient(
        headers={"User-Agent": "OSMF-BiomarkerAtlasPipeline/0.1 (research@opensourcemed.info)"},
        follow_redirects=True,
        timeout=30,
    ) as client:
        for gene in genes:
            # Clinical biomarker names can contain slashes/spaces/parens
            # ("FEV1/FVC ratio") that aren't filename-safe, unlike bare gene
            # symbols — slug the filename, keep `gene` itself as the actual
            # search term passed to normalize/mine/extract below.
            out_path = out_dir / f"{_slug(gene)}.json"
            if args.skip_existing and out_path.exists():
                log.info("  SKIP existing: %s", gene)
                continue
            log.info("  Processing %s / %s", args.disease, gene)
            try:
                candidate = await _process_gene(
                    gene, args.disease, ncbi_key,
                    "" if args.skip_llm else anthropic_key,
                    args.max_literature, client,
                    is_gene_symbol=(args.marker_source == "gene"),
                )
                out_path.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
                grounded = sum(1 for c in candidate.claims if c.citation and c.doi)
                log.info("    → %d refs, %d grounded direction claim(s)", len(candidate.claims), grounded)
            except Exception as e:
                log.error("    FAILED %s / %s: %s", args.disease, gene, e)
            await asyncio.sleep(1.5)

    log.info("Done. Run: python -m biomarker_pipeline.export_atlas_schema --slug %s --disease \"%s\"", slug, args.disease)


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Run atlas curation (Stage 1+3b+4b) for one disease")
    parser.add_argument("--disease", required=True, help='Canonical disease name, e.g. "Asthma"')
    parser.add_argument("--slug", default=None, help="URL slug (default: derived from --disease)")
    parser.add_argument(
        "--marker-source", choices=["clinical", "gene"], default="clinical",
        help="'clinical' (default): real lab/clinical biomarkers from disease_clinical_biomarkers.py. "
             "'gene': the drug-target gene panel from disease_biomarkers.py (legacy behavior).",
    )
    parser.add_argument("--max-literature", type=int, default=30, help="Max refs to mine per marker")
    parser.add_argument("--skip-llm", action="store_true", help="Skip Stage 4b LLM extraction")
    parser.add_argument("--skip-existing", action="store_true", help="Skip genes that already have output")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    asyncio.run(_main(args))


if __name__ == "__main__":
    main()
