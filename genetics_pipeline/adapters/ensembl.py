"""Ensembl REST client — module 4 (locus-to-gene) distance-window fallback.

Open Targets Platform bulk Parquet (credible sets, L2G scores, colocalisation)
is the preferred source for locus-to-gene assignment but is not fetched in
this build (multi-GB per-release downloads, out of scope for an on-demand
pipeline run). Per the spec's own fallback rule, gene assignment here uses a
distance window around the lead variant instead.
"""
from __future__ import annotations

import httpx

from ..config import ENSEMBL_BASE


def gene_lookup(symbol: str, species: str = "homo_sapiens") -> dict:
    resp = httpx.get(
        f"{ENSEMBL_BASE}/lookup/symbol/{species}/{symbol}",
        params={"content-type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def genes_overlapping_region(chrom: str, start: int, end: int, species: str = "homo_sapiens") -> list[dict]:
    resp = httpx.get(
        f"{ENSEMBL_BASE}/overlap/region/{species}/{chrom}:{start}-{end}",
        params={"feature": "gene", "content-type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()


def distance_window_locus(chrom: str, lead_pos: int, window: int = 50_000) -> tuple[int, int]:
    return max(0, lead_pos - window), lead_pos + window
