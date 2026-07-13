#!/usr/bin/env python3
"""
PriceOS comparison engine.

Compares US vs international prices for the same procedure with honesty:
- NOT_COMPARABLE if completeness scores differ by >0.15 (hard rule)
- Savings range (never a point estimate) when comparable
- Explicit component-by-component transparency

USAGE:
  from comparison_engine import compare_prices

  result = compare_prices(
    us_price=us_observation,
    intl_price=intl_observation,
    procedure_slug="tka",
  )

  if result.status == "NOT_COMPARABLE":
    print(f"Cannot compare: {result.reason}")
  else:
    print(f"Savings: {result.savings_low:.0%} to {result.savings_high:.0%}")
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ComparisonStatus(Enum):
    """Status of price comparison."""
    COMPARABLE = "comparable"
    NOT_COMPARABLE = "not_comparable"
    MISSING_DATA = "missing_data"


@dataclass
class ComparisonResult:
    """Result of comparing two price observations."""
    status: ComparisonStatus
    us_price: dict
    intl_price: dict
    procedure_slug: str

    # Completeness scores
    us_completeness: float
    intl_completeness: float
    completeness_gap: float  # abs(us - intl)

    # Savings calculation (only if COMPARABLE)
    savings_low: Optional[float] = None  # 1 - (intl_high / us_low)
    savings_high: Optional[float] = None  # 1 - (intl_low / us_high)

    # Why not comparable
    reason: Optional[str] = None

    # Component transparency
    us_components_missing: list[str] = None
    intl_components_missing: list[str] = None

    def __post_init__(self):
        if self.us_components_missing is None:
            self.us_components_missing = []
        if self.intl_components_missing is None:
            self.intl_components_missing = []

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "status": self.status.value,
            "procedure_slug": self.procedure_slug,
            "us_price_usd": self.us_price.get("amount_usd"),
            "intl_price_usd": self.intl_price.get("amount_usd"),
            "us_completeness": round(self.us_completeness, 2),
            "intl_completeness": round(self.intl_completeness, 2),
            "completeness_gap": round(self.completeness_gap, 2),
            "savings_low": round(self.savings_low, 3) if self.savings_low else None,
            "savings_high": round(self.savings_high, 3) if self.savings_high else None,
            "savings_range": (
                f"{self.savings_low:.0%} to {self.savings_high:.0%}"
                if self.savings_low and self.savings_high else None
            ),
            "reason": self.reason,
            "us_components_missing": self.us_components_missing,
            "intl_components_missing": self.intl_components_missing,
            "us_facility": self.us_price.get("facility_id"),
            "intl_facility": self.intl_price.get("facility_id"),
        }


COMPLETENESS_GATE = 0.15  # Hard rule: if |us - intl| > 0.15, NOT_COMPARABLE


def compare_prices(
    us_price: dict,
    intl_price: dict,
    procedure_slug: str,
    canonical_bundle: dict = None,
) -> ComparisonResult:
    """
    Compare US vs international price for the same procedure.

    Args:
        us_price: US price observation dict
        intl_price: International price observation dict
        procedure_slug: Procedure slug (e.g., 'tka')
        canonical_bundle: Canonical bundle definition (for component names)

    Returns:
        ComparisonResult with status, savings range, component analysis

    Hard rule (from brief §6):
        if abs(completeness(us) - completeness(intl)) > 0.15:
            return NOT_COMPARABLE

    Savings calculation (when comparable):
        savings_low  = 1 - (intl_high / us_low)
        savings_high = 1 - (intl_low  / us_high)
    """
    # Extract completeness scores
    us_bundle = us_price.get("bundle", {})
    intl_bundle = intl_price.get("bundle", {})

    us_completeness = us_bundle.get("completeness_score", 0.0)
    intl_completeness = intl_bundle.get("completeness_score", 0.0)
    completeness_gap = abs(us_completeness - intl_completeness)

    # Extract amounts
    us_amount = us_price.get("amount_usd", 0)
    intl_amount = intl_price.get("amount_usd", 0)

    if not us_amount or not intl_amount:
        return ComparisonResult(
            status=ComparisonStatus.MISSING_DATA,
            us_price=us_price,
            intl_price=intl_price,
            procedure_slug=procedure_slug,
            us_completeness=us_completeness,
            intl_completeness=intl_completeness,
            completeness_gap=completeness_gap,
            reason="Missing amount_usd for one or both prices",
        )

    # Analyze component differences
    us_includes = set(us_bundle.get("includes", []))
    intl_includes = set(intl_bundle.get("includes", []))
    us_missing = sorted(intl_includes - us_includes)
    intl_missing = sorted(us_includes - intl_includes)

    # Apply completeness gate (hard rule)
    if completeness_gap > COMPLETENESS_GATE:
        return ComparisonResult(
            status=ComparisonStatus.NOT_COMPARABLE,
            us_price=us_price,
            intl_price=intl_price,
            procedure_slug=procedure_slug,
            us_completeness=us_completeness,
            intl_completeness=intl_completeness,
            completeness_gap=completeness_gap,
            reason=(
                f"Completeness scores differ by {completeness_gap:.2f} (threshold: {COMPLETENESS_GATE}). "
                f"US: {us_completeness:.0%} (includes {len(us_includes)} components), "
                f"Intl: {intl_completeness:.0%} (includes {len(intl_includes)} components). "
                f"US missing: {', '.join(us_missing) if us_missing else 'none'}. "
                f"Intl missing: {', '.join(intl_missing) if intl_missing else 'none'}."
            ),
            us_components_missing=us_missing,
            intl_components_missing=intl_missing,
        )

    # Compute price ranges
    # For US: use allowed-amount p10/p90 if available, else assume point estimate
    us_low = us_price.get("cashLow") or us_price.get("allowed_p10") or us_amount
    us_high = us_price.get("cashHigh") or us_price.get("allowed_p90") or us_amount

    # For international: use advertised minimum as floor
    # If is_advertised_minimum=True, intl_low is a floor, not typical
    intl_low = intl_price.get("amount_usd")
    intl_high = intl_price.get("amount_usd")  # If single quote, low = high

    # Look for price range in notes (some facilities quote ranges)
    intl_notes = intl_price.get("notes", "")
    if "–" in intl_notes or "-" in intl_notes:
        # TODO: parse ranges from notes if present
        pass

    # Savings calculation
    # savings_low = scenario where intl is most expensive relative to cheapest US
    # savings_high = scenario where intl is cheapest relative to most expensive US
    savings_low = 1 - (intl_high / us_low) if us_low > 0 else 0
    savings_high = 1 - (intl_low / us_high) if us_high > 0 else 0

    # Clamp to [0, 1] (don't report "800% savings")
    savings_low = max(0, min(1, savings_low))
    savings_high = max(0, min(1, savings_high))

    # Ensure low < high
    if savings_low > savings_high:
        savings_low, savings_high = savings_high, savings_low

    # Flag if international is actually MORE expensive
    if savings_low < 0 or savings_high < 0:
        reason_suffix = (
            " (Intl is more expensive than US; consider domestic options)"
            if savings_high < 0
            else ""
        )
    else:
        reason_suffix = ""

    return ComparisonResult(
        status=ComparisonStatus.COMPARABLE,
        us_price=us_price,
        intl_price=intl_price,
        procedure_slug=procedure_slug,
        us_completeness=us_completeness,
        intl_completeness=intl_completeness,
        completeness_gap=completeness_gap,
        savings_low=savings_low,
        savings_high=savings_high,
        reason=(
            f"Comparable. US: ${us_low:,.0f}–${us_high:,.0f} (completeness {us_completeness:.0%}). "
            f"Intl: ${intl_low:,.0f} (completeness {intl_completeness:.0%}). "
            f"Savings range: {savings_low:.0%}–{savings_high:.0%}.{reason_suffix}"
        ),
        us_components_missing=us_missing,
        intl_components_missing=intl_missing,
    )


def compare_multiple(
    us_prices: list[dict],
    intl_prices: list[dict],
    procedure_slug: str,
) -> list[ComparisonResult]:
    """
    Compare all combinations of US and international prices for a procedure.

    Args:
        us_prices: List of US price observations
        intl_prices: List of international price observations
        procedure_slug: Procedure slug

    Returns:
        List of ComparisonResult objects (cross product)
    """
    results = []
    for us_price in us_prices:
        for intl_price in intl_prices:
            result = compare_prices(us_price, intl_price, procedure_slug)
            results.append(result)
    return results


def summarize_comparisons(results: list[ComparisonResult]) -> dict:
    """
    Summarize comparison results for a procedure.

    Args:
        results: List of ComparisonResult objects

    Returns:
        Summary stats (avg savings, comparable count, etc.)
    """
    comparable = [r for r in results if r.status == ComparisonStatus.COMPARABLE]
    not_comparable = [r for r in results if r.status == ComparisonStatus.NOT_COMPARABLE]

    if not comparable:
        return {
            "procedure_slug": results[0].procedure_slug if results else None,
            "total_comparisons": len(results),
            "comparable": 0,
            "not_comparable": len(not_comparable),
            "avg_savings": None,
            "savings_range": None,
            "reason": "No comparable price pairs (completeness mismatch)",
        }

    savings_low_values = [r.savings_low for r in comparable if r.savings_low is not None]
    savings_high_values = [r.savings_high for r in comparable if r.savings_high is not None]

    avg_low = sum(savings_low_values) / len(savings_low_values) if savings_low_values else 0
    avg_high = sum(savings_high_values) / len(savings_high_values) if savings_high_values else 0

    return {
        "procedure_slug": results[0].procedure_slug if results else None,
        "total_comparisons": len(results),
        "comparable": len(comparable),
        "not_comparable": len(not_comparable),
        "avg_savings_low": round(avg_low, 3),
        "avg_savings_high": round(avg_high, 3),
        "avg_savings_range": f"{avg_low:.0%}–{avg_high:.0%}",
        "us_avg_completeness": round(
            sum(r.us_completeness for r in comparable) / len(comparable), 2
        ) if comparable else None,
        "intl_avg_completeness": round(
            sum(r.intl_completeness for r in comparable) / len(comparable), 2
        ) if comparable else None,
    }
