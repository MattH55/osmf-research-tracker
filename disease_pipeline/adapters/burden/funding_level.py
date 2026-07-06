"""Compute NIH funding level tier from funding vs disease burden."""
from __future__ import annotations


def _burden_units(row: dict) -> float | None:
    dalys = row.get("us_dalys")
    if dalys and float(dalys) > 0:
        return float(dalys)
    deaths = row.get("us_mortality") or row.get("us_deaths")
    if deaths and str(deaths) not in ("-", "+"):
        try:
            return float(deaths) * 10.0  # deaths → rough DALY proxy (10 YLL/death)
        except (TypeError, ValueError):
            pass
    return None


def funding_dollars_per_burden_unit(row: dict) -> float | None:
    funding_m = row.get("nih_funding_millions_usd")
    if funding_m is None or str(funding_m) in ("-", "+"):
        return None
    try:
        funding = float(funding_m) * 1_000_000.0
    except (TypeError, ValueError):
        return None
    burden = _burden_units(row)
    if not burden or burden <= 0:
        return None
    return funding / burden


def compute_funding_level(
    row: dict,
    *,
    corpus_ratios: list[float] | None = None,
) -> dict:
    ratio = funding_dollars_per_burden_unit(row)
    if ratio is None:
        return {
            "funding_level": "unknown",
            "funding_per_daly_usd": None,
            "note": "Insufficient funding or burden data",
        }

    tier = "moderate"
    if corpus_ratios:
        sorted_r = sorted(corpus_ratios)
        n = len(sorted_r)
        if n >= 4:
            q25 = sorted_r[n // 4]
            q50 = sorted_r[n // 2]
            q75 = sorted_r[(3 * n) // 4]
            if ratio < q25:
                tier = "severely underfunded"
            elif ratio < q50:
                tier = "underfunded"
            elif ratio < q75:
                tier = "moderate"
            else:
                tier = "well-funded"
        else:
            median = sorted_r[n // 2]
            if ratio < 0.5 * median:
                tier = "underfunded"
            elif ratio > 1.5 * median:
                tier = "well-funded"

    return {
        "funding_level": tier,
        "funding_per_daly_usd": round(ratio, 2),
        "note": "Tier from NIH FY funding ÷ US DALYs (or mortality proxy) vs corpus quartiles",
    }


def enrich_corpus_funding_levels(rows: dict[str, dict]) -> dict[str, dict]:
    """Recompute funding_level for all rows using corpus-wide quartiles."""
    ratios: list[tuple[str, float]] = []
    for slug, row in rows.items():
        r = funding_dollars_per_burden_unit(row)
        if r is not None:
            ratios.append((slug, r))
    corpus = [r for _, r in ratios]
    out: dict[str, dict] = {}
    for slug, row in rows.items():
        merged = dict(row)
        merged.update(compute_funding_level(row, corpus_ratios=corpus))
        out[slug] = merged
    return out