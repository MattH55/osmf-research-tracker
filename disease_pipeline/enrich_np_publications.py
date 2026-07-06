#!/usr/bin/env python3
"""Expand natural-product publication coverage from cache and PubMed."""
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

import aiohttp

from disease_pipeline.adapters.clinical_evidence import (
    _condition_clause,
    _drug_clause,
    _pubmed_hits,
    _pubmed_summaries,
    resolve_mesh_descriptor,
)
from disease_pipeline.http_util import default_session
from disease_pipeline.models import DiseaseIdentifiers
from disease_pipeline.np_publications import enrich_disease_publications, resolve_np_publications
from disease_pipeline.output.generate_html import write_page

log = logging.getLogger(__name__)
DATA_DIR = _ROOT / "data" / "disease-intelligence"
HTML_DIR = _ROOT / "disease-intelligence"


async def _pubmed_publications_for_np(
    np: dict,
    identifiers: DiseaseIdentifiers,
    mesh_term: str | None,
    session: aiohttp.ClientSession,
    *,
    limit: int = 3,
) -> list[dict]:
    drug_q = _drug_clause(np.get("name", ""))
    condition = _condition_clause(mesh_term, identifiers)
    term = (
        f"{drug_q} AND {condition} AND "
        '("meta-analysis"[Publication Type] OR "systematic review"[Publication Type] '
        'OR "randomized controlled trial"[Publication Type])'
    )
    pmids, _ = await _pubmed_hits(session, term, limit=limit)
    if not pmids:
        term = f"{drug_q} AND {condition}"
        pmids, _ = await _pubmed_hits(session, term, limit=limit)
    if not pmids:
        return []

    pubs: list[dict] = []
    for rec in await _pubmed_summaries(session, pmids[:limit]):
        pmid = rec.get("pmid")
        if not pmid:
            continue
        pubs.append({
            "title": rec.get("title") or f"PubMed {pmid}",
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "source": "PubMed",
            "pmid": pmid,
        })
    return pubs


async def _pubmed_backfill_disease(
    data: dict,
    session: aiohttp.ClientSession,
    *,
    max_nps: int = 25,
) -> bool:
    condition = data.get("condition") or {}
    disease_name = condition.get("name") or condition.get("shortName") or ""
    identifiers = DiseaseIdentifiers(
        name=disease_name,
        mesh_id=condition.get("mesh_id"),
        omim_id=condition.get("omim_id"),
        efo_id=condition.get("efo_id"),
    )
    mesh_term = await resolve_mesh_descriptor(identifiers.mesh_id or "", session)

    candidates = [
        np for np in data.get("natural_products", [])
        if not resolve_np_publications(
            np,
            gmi_articles=(data.get("summary") or {}).get("gmi_articles"),
            extra_evidence=data.get("natural_product_evidence"),
            disease_name=disease_name,
        )
    ]
    candidates.sort(key=lambda row: row.get("score", 0), reverse=True)
    candidates = candidates[:max_nps]
    if not candidates:
        return False

    changed = False
    nps = list(data.get("natural_products", []))
    by_id = {np.get("canonical_id"): i for i, np in enumerate(nps)}

    for np in candidates:
        pubs = await _pubmed_publications_for_np(
            np, identifiers, mesh_term, session, limit=3,
        )
        if not pubs:
            continue
        idx = by_id.get(np.get("canonical_id"))
        if idx is None:
            continue
        row = dict(nps[idx])
        row["supporting_publications"] = pubs
        nps[idx] = row
        changed = True
        await asyncio.sleep(0.15)

    if changed:
        data["natural_products"] = nps
    return changed


def enrich_all(
    *,
    slug: str | None = None,
    refresh_gmi: bool = True,
    pubmed: bool = False,
    html: bool = False,
    max_pubmed_per_disease: int = 25,
) -> tuple[int, int, int]:
    paths = sorted(DATA_DIR.glob("*.json"))
    if slug:
        paths = [p for p in paths if p.stem == slug]

    updated = 0
    before_pubs = 0
    after_pubs = 0

    async def _run() -> None:
        nonlocal updated, before_pubs, after_pubs
        async with default_session() as session:
            for path in paths:
                data = json.loads(path.read_text(encoding="utf-8"))
                before_pubs += sum(
                    1 for np in data.get("natural_products", [])
                    if np.get("supporting_publications")
                )
                changed = enrich_disease_publications(data, refresh_gmi=refresh_gmi)
                if pubmed:
                    changed = await _pubmed_backfill_disease(
                        data,
                        session,
                        max_nps=max_pubmed_per_disease,
                    ) or changed
                after_pubs += sum(
                    1 for np in data.get("natural_products", [])
                    if np.get("supporting_publications")
                )
                if changed:
                    path.write_text(
                        json.dumps(data, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    updated += 1
                    log.info("Updated %s", path.stem)
                    if html:
                        write_page(data, HTML_DIR)

    asyncio.run(_run())
    return updated, before_pubs, after_pubs


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Enrich natural product publication links")
    parser.add_argument("--slug", help="Single disease slug to process")
    parser.add_argument("--no-refresh-gmi", action="store_true", help="Skip GMI cache refresh")
    parser.add_argument("--pubmed", action="store_true", help="PubMed backfill for top missing NPs")
    parser.add_argument("--html", action="store_true", help="Regenerate HTML for updated diseases")
    parser.add_argument("--max-pubmed-per-disease", type=int, default=25)
    args = parser.parse_args(argv)

    updated, before, after = enrich_all(
        slug=args.slug,
        refresh_gmi=not args.no_refresh_gmi,
        pubmed=args.pubmed,
        html=args.html,
        max_pubmed_per_disease=args.max_pubmed_per_disease,
    )
    log.info(
        "Updated %d diseases — publications %d -> %d",
        updated,
        before,
        after,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())