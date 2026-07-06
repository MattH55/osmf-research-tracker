"""Merge RCDC + GHE + GBD burden for a disease slug."""
from __future__ import annotations

from .funding_level import compute_funding_level, enrich_corpus_funding_levels, funding_dollars_per_burden_unit
from .gbd_burden import get_gbd_burden_from_seed
from .ghe_burden import get_ghe_burden_from_seed
from .rcdc import get_rcdc_burden, load_rcdc_by_slug

_corpus_enriched: dict[str, dict] | None = None


def _build_corpus() -> dict[str, dict]:
    global _corpus_enriched
    if _corpus_enriched is not None:
        return _corpus_enriched

    merged: dict[str, dict] = {}
    for slug, rcdc in load_rcdc_by_slug().items():
        row = dict(rcdc)
        ghe = get_ghe_burden_from_seed(slug)
        if ghe:
            row.update(ghe)
        gbd = get_gbd_burden_from_seed(slug)
        if gbd:
            for k, v in gbd.items():
                if row.get(k) is None:
                    row[k] = v
        merged[slug] = row

    # Include GHE-only slugs
    from .ghe_burden import BURDEN_SEED_PATH as GHE_SEED
    if GHE_SEED.exists():
        import json
        ghe_all = json.loads(GHE_SEED.read_text(encoding="utf-8")).get("by_slug", {})
        for slug, ghe in ghe_all.items():
            if slug not in merged:
                merged[slug] = dict(ghe)
            else:
                for k, v in ghe.items():
                    if merged[slug].get(k) is None:
                        merged[slug][k] = v

    # Include GBD-only slugs
    from .gbd_burden import BURDEN_SEED_PATH
    if BURDEN_SEED_PATH.exists():
        import json
        gbd_all = json.loads(BURDEN_SEED_PATH.read_text(encoding="utf-8")).get("by_slug", {})
        for slug, gbd in gbd_all.items():
            if slug not in merged:
                merged[slug] = dict(gbd)
            else:
                for k, v in gbd.items():
                    if merged[slug].get(k) is None:
                        merged[slug][k] = v

    _corpus_enriched = enrich_corpus_funding_levels(merged)
    return _corpus_enriched


def get_burden_for_slug(slug: str, disease_name: str = "") -> dict | None:
    corpus = _build_corpus()
    if slug in corpus:
        return dict(corpus[slug])

    rcdc = get_rcdc_burden(slug, disease_name)
    ghe = get_ghe_burden_from_seed(slug)
    gbd = get_gbd_burden_from_seed(slug)
    if not rcdc and not ghe and not gbd:
        return None

    row: dict = {}
    if rcdc:
        row.update(rcdc)
    if ghe:
        row.update({k: v for k, v in ghe.items() if row.get(k) is None})
    if gbd:
        row.update({k: v for k, v in gbd.items() if row.get(k) is None})

    ratios = [r for r in (funding_dollars_per_burden_unit(c) for c in corpus.values()) if r]
    row.update(compute_funding_level(row, corpus_ratios=ratios))
    return row