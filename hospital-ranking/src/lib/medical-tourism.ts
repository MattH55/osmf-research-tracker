import tourismJson from "../../data/seed/medical-tourism.json";
import { getUsReferenceMedian } from "./pricing";
import type { TourismDestination, TourismEstimate } from "./types";

interface TourismSeed {
  vintage: string;
  methodology: string;
  sources: string[];
  packageIncludesDefault: string[];
  packageExcludesDefault: string[];
  destinations: TourismDestination[];
}

const seed = tourismJson as TourismSeed;

function roundTourismPrice(amount: number): number {
  if (amount >= 10000) return Math.round(amount / 100) * 100;
  if (amount >= 1000) return Math.round(amount / 50) * 50;
  return Math.round(amount / 10) * 10;
}

export const TOURISM_METHODOLOGY = {
  summary: seed.methodology,
  sources: seed.sources,
  vintage: seed.vintage,
};

export function getTourismDestinations(): TourismDestination[] {
  return seed.destinations;
}

export function getTourismDestination(id: string): TourismDestination | undefined {
  return seed.destinations.find((d) => d.id === id);
}

export function getTourismEstimates(
  procedureId: string,
  options?: { usBaseline?: number },
): TourismEstimate[] {
  const usRef =
    options?.usBaseline ?? getUsReferenceMedian(procedureId) ?? undefined;
  if (!usRef) return [];

  const estimates: TourismEstimate[] = [];
  for (const dest of seed.destinations) {
    const cashLow = roundTourismPrice(usRef * dest.multipliers.low);
    const cashMedian = roundTourismPrice(usRef * dest.multipliers.median);
    const cashHigh = roundTourismPrice(usRef * dest.multipliers.high);
    const savingsPercent = Math.round((1 - cashMedian / usRef) * 100);

    estimates.push({
      procedureId,
      destinationId: dest.id,
      destination: dest,
      cashLow,
      cashMedian,
      cashHigh,
      usReferenceMedian: usRef,
      savingsPercent: Math.max(0, savingsPercent),
      packageIncludes: seed.packageIncludesDefault,
      packageExcludes: seed.packageExcludesDefault,
      priceSource: "medical_tourism_estimate",
      priceVintage: seed.vintage,
    });
  }

  return estimates.sort((a, b) => a.cashMedian - b.cashMedian);
}

/** Median reported U.S. cash price from a set of search results, if any. */
export function medianUsCashFromResults(
  cashMedians: (number | null | undefined)[],
): number | undefined {
  const sane = cashMedians.filter(
    (v): v is number => v != null && v >= 75,
  );
  if (!sane.length) return undefined;
  sane.sort((a, b) => a - b);
  const mid = Math.floor(sane.length / 2);
  return sane.length % 2 === 0
    ? Math.round((sane[mid - 1] + sane[mid]) / 2)
    : sane[mid];
}

export function hasActiveClinics(destination: TourismDestination): boolean {
  return destination.clinics.some((c) => c.status === "active" && c.url);
}