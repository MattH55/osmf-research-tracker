import type { InsuranceType, ProcedurePrice } from "./types";

export function formatCurrency(amount: number | null | undefined): string {
  if (amount == null || Number.isNaN(amount)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatPriceRange(
  low: number | null | undefined,
  high: number | null | undefined,
): string {
  if (low == null && high == null) return "—";
  if (low != null && high != null && low !== high) {
    return `${formatCurrency(low)} – ${formatCurrency(high)}`;
  }
  return formatCurrency(low ?? high);
}

export function estimateOop(
  price: ProcedurePrice | null,
  insurance: InsuranceType,
): number | null {
  if (!price) return null;
  switch (insurance) {
    case "cash":
    case "uninsured":
      return price.cashMedian ?? price.oopUninsured;
    case "ppo":
      return price.oopPpo;
    case "hdhp":
      return price.oopHdhp;
    default:
      return price.cashMedian;
  }
}

export function starLabel(stars: number | null): string {
  if (stars == null) return "Not rated";
  return `${stars} ${stars === 1 ? "star" : "stars"}`;
}

export function percentLabel(value: number | null): string {
  if (value == null) return "—";
  return `${value.toFixed(1)}%`;
}