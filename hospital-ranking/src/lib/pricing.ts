import type { InsuranceType, PriceScope, ProcedurePrice } from "./types";

/**
 * Every price shown is a hospital's own published figure from its CMS-required
 * machine-readable file. Nothing is modelled, imputed or adjusted.
 */

/** No published price for a shoppable service legitimately reaches this; 999,999,999-style sentinels do. */
export const PRICE_CEILING = 500_000;

/** Below these a figure can't be the whole service it claims to price (e.g. a supply line matched as a stay). */
const SCOPE_FLOOR: Record<PriceScope, number> = {
  inpatient_stay: 1500,
  facility_service: 15,
  professional: 15,
};

export function priceFloor(scope: PriceScope | null | undefined): number {
  return scope ? SCOPE_FLOOR[scope] : SCOPE_FLOOR.facility_service;
}

/** Months after which a published price is flagged as old (CMS requires annual updates). */
export const STALE_MONTHS = 18;

export function isReportedPrice(price: ProcedurePrice): boolean {
  return price.priceSource === "hospital_mrf" || price.priceSource === "trilliant_mrf";
}

export function priceSourceLabel(source: string): string {
  if (source === "hospital_mrf") return "Hospital price file (downloaded directly)";
  if (source === "trilliant_mrf") return "Hospital price file (via Trilliant Health ORIA)";
  return source;
}

export type PriceKind = "cash" | "negotiated";

/**
 * The single figure a search result leads with, and what it is.
 * Cash/uninsured: the hospital's published discounted cash price.
 * Insured: the median of the hospital's published payer-negotiated rates. That is what
 * the plan pays the hospital, not the patient's share, which depends on the plan.
 */
export function headlinePrice(
  price: ProcedurePrice | null,
  insurance: InsuranceType,
): { amount: number; kind: PriceKind } | null {
  if (!price) return null;
  if (insurance === "cash" || insurance === "uninsured") {
    return price.cashMedian != null ? { amount: price.cashMedian, kind: "cash" } : null;
  }
  return price.negotiatedMedian != null ? { amount: price.negotiatedMedian, kind: "negotiated" } : null;
}

export function priceKindLabel(kind: PriceKind): string {
  return kind === "cash" ? "Published cash price" : "Median negotiated rate (paid by insurers)";
}

export const SCOPE_LABEL: Record<PriceScope, string> = {
  inpatient_stay: "Whole hospital stay (MS-DRG facility rate)",
  facility_service: "Hospital facility fee for the service",
  professional: "Physician fee",
};
