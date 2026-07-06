#!/usr/bin/env python3
"""Enrich disease-intelligence JSON with remission data (DB100 + GBD + PubMed)."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from disease_pipeline.adapters.remission.db100 import get_db100_remission
from disease_pipeline.adapters.remission.merge import merge_remission_layers
from disease_pipeline.adapters.remission.runner import enrich_remission
from disease_pipeline.http_util import default_session
from disease_pipeline.models import DiseaseIdentifiers
from disease_pipeline.options import PipelineOptions
from disease_pipeline.output.generate_html import write_page

DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"

log = logging.getLogger(__name__)


async def enrich_one(path: Path, opts: PipelineOptions, *, write_html: bool, db100_only: bool) -> dict | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    name = data["condition"]["name"]
    ids_raw = data.get("identifiers", {})
    identifiers = DiseaseIdentifiers(
        name=name,
        mondo_id=ids_raw.get("mondo_id"),
        efo_id=ids_raw.get("efo_id"),
        omim_id=ids_raw.get("omim_id"),
        orpha_id=ids_raw.get("orpha_id"),
        mesh_id=ids_raw.get("mesh_id"),
        umls_cui=ids_raw.get("umls_cui"),
    )
    slug = data.get("slug", path.stem)

    if db100_only:
        db100 = get_db100_remission(slug, name)
        if not db100:
            log.info("'%s': no DB100 remission entry", name)
            return None
        remission = merge_remission_layers(db100=db100, gbd=None, pubmed_rows=[])
    else:
        async with default_session() as session:
            remission = await enrich_remission(
                identifiers, session, disease_slug=slug, options=opts
            )

    if not remission.get("spontaneous_remission_rate") and not remission.get("best_intervention_remission_rate"):
        if not remission.get("layers"):
            return None

    data["remission"] = remission
    summary = data.setdefault("summary", {})
    summary["has_remission_data"] = True
    sources = summary.setdefault("sources_queried", [])
    for src in ("disease_db_100", "GBD", "PubMed Remission"):
        if src not in sources:
            sources.append(src)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if write_html:
        write_page(data, HTML_DIR)

    log.info("'%s': remission enriched -> %s (layers=%s)", name, path.name, remission.get("layers"))
    return {"slug": slug, "name": name, "layers": remission.get("layers", [])}


async def run_batch(
    opts: PipelineOptions,
    *,
    write_html: bool,
    only_slug: str | None,
    db100_only: bool,
) -> list[dict]:
    paths = sorted(DATA_DIR.glob("*.json"))
    if only_slug:
        paths = [p for p in paths if p.stem == only_slug]
    if not paths:
        log.error("No matching disease JSON files")
        return []

    sem = asyncio.Semaphore(opts.batch_concurrency)

    async def bounded(p: Path) -> dict | None:
        async with sem:
            try:
                return await asyncio.wait_for(
                    enrich_one(p, opts, write_html=write_html, db100_only=db100_only),
                    timeout=opts.disease_timeout_sec,
                )
            except asyncio.TimeoutError:
                log.error("Timeout: %s", p.name)
            except Exception as e:
                log.error("Failed %s: %s", p.name, e)
            return None

    results = await asyncio.gather(*[bounded(p) for p in paths])
    return [r for r in results if r]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich diseases with remission/chronicity data")
    parser.add_argument("--slug", help="Single disease slug")
    parser.add_argument("--db100-only", action="store_true", help="Bootstrap from disease_db_100 only (no API)")
    parser.add_argument("--skip-gbd", action="store_true")
    parser.add_argument("--skip-pubmed", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    opts = PipelineOptions(
        skip_gbd_remission=args.skip_gbd or args.db100_only,
        skip_pubmed_remission=args.skip_pubmed or args.db100_only,
        skip_llm_extract=args.db100_only,
        batch_concurrency=args.concurrency,
        disease_timeout_sec=args.timeout,
    )
    results = asyncio.run(
        run_batch(opts, write_html=args.html, only_slug=args.slug, db100_only=args.db100_only)
    )
    log.info("Done: %d diseases with remission data", len(results))
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())