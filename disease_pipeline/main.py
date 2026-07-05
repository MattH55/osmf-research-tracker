#!/usr/bin/env python3
"""CLI entry point for the Disease Intelligence Pipeline."""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import sys
from pathlib import Path

from .options import PipelineOptions, options_for_phase
from .output.assembler import to_spec_json
from .output.generate_html import build_index_html, write_page
from .output.web_export import to_web_json
from .pipeline import build_batch, build_disease_page

DATA_DIR = Path(__file__).parent.parent / "data" / "disease-intelligence"
HTML_DIR = Path(__file__).parent.parent / "disease-intelligence"

log = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def _main_async(args: argparse.Namespace) -> int:
    opts = options_for_phase(
        args.phase,
        use_cache=not args.no_cache,
        skip_pubmed=args.skip_pubmed,
        skip_hmdb=args.skip_hmdb,
        skip_evidence=args.skip_evidence,
        max_genes_for_drugs=args.max_genes,
        max_pubmed_items=args.max_pubmed,
        max_evidence_drugs=args.max_evidence_drugs,
        disease_timeout_sec=args.timeout,
        batch_concurrency=args.concurrency,
    )

    if args.batch:
        names = _load_disease_list(args.batch)
        log.info("Batch: %d diseases, phase=%d, concurrency=%d", len(names), args.phase, args.concurrency)
        pages = await build_batch(names, opts)
        log.info("Completed %d/%d diseases", len(pages), len(names))
        return 0

    page = await build_disease_page(args.disease, opts)

    if args.web:
        web = to_web_json(page, cap_display=args.cap)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        json_path = DATA_DIR / f"{web['slug']}.json"
        json_path.write_text(json.dumps(web, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("Wrote web JSON %s", json_path)
        if args.html:
            write_page(web, HTML_DIR)
            log.info("Wrote HTML %s", HTML_DIR / f"{web['slug']}.html")
        if args.output:
            Path(args.output).write_text(json.dumps(web, indent=2, ensure_ascii=False), encoding="utf-8")
        return 0

    out = to_spec_json(page)
    text = json.dumps(out, indent=2, ensure_ascii=False)

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        log.info("Wrote %s", path)
    else:
        print(text)

    return 0


def _load_disease_list(path: Path) -> list[str]:
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            col = "disease" if "disease" in (reader.fieldnames or []) else (reader.fieldnames or ["disease"])[0]
            return [row[col].strip() for row in reader if row.get(col, "").strip()]
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Disease Intelligence Pipeline — run in phases to avoid API hangs.",
        epilog=(
            "Phases: 1=OT skeleton, 2=+clinical, 3=+via-biomarker drugs, "
            "4=+DisGeNET/PubMed, 5=+UniProt/HMDB, 6=+trial/literature evidence"
        ),
    )
    parser.add_argument("disease", nargs="?", help='Disease name, e.g. "Type 2 Diabetes Mellitus"')
    parser.add_argument("-o", "--output", help="Write JSON output path")
    parser.add_argument("--phase", type=int, default=1, choices=[1, 2, 3, 4, 5, 6])
    parser.add_argument("--batch", type=Path, help="CSV or text file of disease names")
    parser.add_argument("--concurrency", type=int, default=2, help="Batch concurrency (default 2)")
    parser.add_argument("--timeout", type=float, default=90.0, help="Per-disease timeout seconds")
    parser.add_argument("--max-genes", type=int, default=10, help="Max genes for via-biomarker lookup")
    parser.add_argument("--max-pubmed", type=int, default=15, help="Max tier-C PubMed validations")
    parser.add_argument("--max-evidence-drugs", type=int, default=25, help="Top agents for trial/literature evidence (phase 6)")
    parser.add_argument("--skip-evidence", action="store_true", help="Skip clinical trial + literature evidence layer")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--skip-pubmed", action="store_true")
    parser.add_argument("--skip-hmdb", action="store_true", default=True)
    parser.add_argument("--web", action="store_true", help="Export web-ready JSON to data/disease-intelligence/")
    parser.add_argument("--html", action="store_true", help="Generate HTML page (requires --web)")
    parser.add_argument("--cap", action="store_true", help="Cap displayed lists (80 alts, 50 merged drugs)")
    parser.add_argument("--full", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    if not args.disease and not args.batch:
        parser.error("Provide a disease name or --batch file")

    _configure_logging(args.verbose)
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        log.error("Pipeline failed: %s", e)
        if args.verbose:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())