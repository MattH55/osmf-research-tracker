"""Full 20-database NP repurposing orchestrator."""
from __future__ import annotations

import asyncio
import logging

import aiohttp

from ...models import Alteration, AlterationType, DiseaseIdentifiers, NaturalProduct
from ...options import PipelineOptions
from ..natural_products.score_np import apply_safety, load_safety_map
from . import merge, score, synthesis
from .browser import BrowserManager
from .clinical import clinicaltrials, examine, greenmedinfo, nccih, pubmed_np
from .dietary import dukes, dsld, foodb, knapsack, phenol_explorer
from .local_data import get_local_data
from .normalize import load_np_synonyms
from .slug_map import get_slug, load_slug_map
from .structural import chembl_np, coconut, lotus, npass, pubchem_np
from .traditional import batman_tcm, etcm, imppat, symmap, tcmsp

log = logging.getLogger(__name__)


async def _empty() -> list:
    return []


async def _empty_gmi() -> tuple[list, str, list]:
    return [], "", []


async def _empty_examine() -> tuple[list, str]:
    return [], ""


async def build_np_repurposing_leads(
    identifiers: DiseaseIdentifiers,
    type_a_alterations: list[Alteration],
    session: aiohttp.ClientSession,
    bm: BrowserManager,
    local_data: dict | None = None,
    *,
    disease_slug: str = "",
    options: PipelineOptions | None = None,
    extra_meta: dict | None = None,
) -> list[NaturalProduct]:
    opts = options or PipelineOptions()
    if opts.skip_natural_products:
        return []

    local = local_data or get_local_data()
    slug_map = load_slug_map()
    syn_idx = load_np_synonyms()
    slug = disease_slug or identifiers.name

    gmi_slug = get_slug(slug, identifiers.name, "greenmedinfo", slug_map)
    ex_slug = get_slug(slug, identifiers.name, "examine", slug_map)

    gene_symbols = [a.name for a in type_a_alterations if a.alteration_type == AlterationType.A]
    activity_terms = local.get("duke_activity_map", {}).get(slug.replace("-", " "), [])
    if not activity_terms:
        for key, terms in local.get("duke_activity_map", {}).items():
            if key in identifiers.name.lower():
                activity_terms = terms
                break

    gmi_coro = (
        greenmedinfo.fetch_disease_substances(gmi_slug, identifiers.name, bm, session)
        if not opts.skip_greenmedinfo and gmi_slug
        else _empty_gmi()
    )
    ex_coro = (
        examine.fetch_condition_hem(ex_slug, identifiers.name, bm, session)
        if not opts.skip_examine and ex_slug
        else _empty_examine()
    )

    (
        gmi_pack, ex_pack, nccih_r, ct_r, pubmed_r,
        tcmsp_r, batman_r, imppat_r, etcm_r, symmap_r,
    ) = await asyncio.gather(
        gmi_coro,
        ex_coro,
        nccih.fetch_disease_nps(identifiers.name, session) if not opts.skip_nccih else _empty(),
        clinicaltrials.fetch_supplement_trials(identifiers, session) if not opts.skip_clinical_np else _empty(),
        pubmed_np.search_and_extract(identifiers, session, opts) if not opts.skip_clinical_np else _empty(),
        tcmsp.query_disease_herbs(identifiers.name, local.get("tcmsp", {}), session) if not opts.skip_tcmsp else _empty(),
        batman_tcm.query_disease_ingredients(identifiers.name, session) if not opts.skip_batman_tcm else _empty(),
        imppat.query_disease(identifiers.name, local.get("imppat_db")) if not opts.skip_imppat else _empty(),
        etcm.query_disease(identifiers.name, session) if not opts.skip_etcm else _empty(),
        symmap.query_disease_herbs(identifiers.name, session) if not opts.skip_symmap else _empty(),
    )

    gmi_rows, gmi_url, gmi_articles = gmi_pack if isinstance(gmi_pack, tuple) else ([], "", [])
    ex_rows, ex_url = ex_pack if isinstance(ex_pack, tuple) else ([], "")

    target_map = await chembl_np.resolve_genes_to_targets(gene_symbols, session) if gene_symbols else {}

    lotus_r, coconut_r, npass_r, chembl_r, pubchem_r = await asyncio.gather(
        lotus.search_nps_for_targets(type_a_alterations, session) if not opts.skip_mechanistic_np else _empty(),
        coconut.search_nps_for_targets(gene_symbols, session) if not opts.skip_mechanistic_np else _empty(),
        asyncio.to_thread(npass.query_for_disease_targets, gene_symbols, local.get("npass_db"))
        if not opts.skip_npass else _empty(),
        chembl_np.get_np_compounds_for_targets(target_map, session) if not opts.skip_mechanistic_np else _empty(),
        pubchem_np.get_active_nps_for_genes(gene_symbols, session) if not opts.skip_mechanistic_np else _empty(),
    )

    dukes_r, knap_r, dsld_r, phenol_r, foodb_r = await asyncio.gather(
        dukes.query_disease(identifiers.name, local.get("dukes", {}), local.get("duke_activity_map", {}))
        if not opts.skip_dukes else _empty(),
        knapsack.query_disease(identifiers.name, session) if not opts.skip_knapsack else _empty(),
        dsld.get_top_supplement_dosing(identifiers.name, session) if not opts.skip_dsld else _empty(),
        phenol_explorer.get_compounds_for_disease(identifiers, session, activity_terms)
        if not opts.skip_phenol_explorer else _empty(),
        asyncio.to_thread(foodb.query_disease, identifiers.name, local.get("foodb_db"), activity_terms)
        if not opts.skip_foodb else _empty(),
    )

    all_raw = {
        "gmi": gmi_rows,
        "examine": ex_rows,
        "nccih": nccih_r,
        "ct": ct_r,
        "pubmed": pubmed_r,
        "tcmsp": tcmsp_r,
        "batman": batman_r,
        "imppat": imppat_r,
        "etcm": etcm_r,
        "symmap": symmap_r,
        "lotus": lotus_r,
        "coconut": coconut_r,
        "npass": npass_r,
        "chembl_np": chembl_r,
        "pubchem": pubchem_r,
        "dukes": dukes_r,
        "knapsack": knap_r,
        "dsld": dsld_r,
        "phenol": phenol_r,
        "foodb": foodb_r,
    }

    nps, hits_by_id = await merge.build_np_records(all_raw, identifiers, syn_idx, session)
    nps = apply_safety(nps, load_safety_map())

    type_a_genes = set(gene_symbols)
    for i, np in enumerate(nps):
        np_hits = hits_by_id.get(np.canonical_id, {})
        nps[i] = np.model_copy(update={
            "score": score.compute_repurposing_score(
                np, identifiers.name,
                source_hits=np_hits,
                type_a_genes=type_a_genes,
            ),
        })
    nps.sort(key=lambda x: x.score, reverse=True)

    if not opts.skip_np_synthesis:
        summaries = await synthesis.synthesise_top_nps(identifiers.name, nps)
        for i, np in enumerate(nps):
            if np.canonical_id in summaries:
                nps[i] = np.model_copy(update={"key_findings": summaries[np.canonical_id]})

    if extra_meta is not None:
        extra_meta["np_lookup_links"] = {
            k: v for k, v in {
                "Examine.com": ex_url,
            }.items() if v
        }
        if not opts.skip_greenmedinfo:
            if gmi_url:
                extra_meta["np_lookup_links"]["GreenMedInfo"] = gmi_url
            if gmi_articles:
                extra_meta["gmi_articles"] = gmi_articles
        extra_meta["np_source_counts"] = {k: len(v) for k, v in all_raw.items() if v}

    log.info("[NP-20] %d natural products for '%s' from 20-database pipeline", len(nps), identifiers.name)
    return nps