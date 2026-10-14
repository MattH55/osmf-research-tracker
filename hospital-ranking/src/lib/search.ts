import {
  getHospital,
  getHospitalCount,
  getHospitals,
  getPrice,
  getProcedure,
  getProcedures,
} from "./data";
import { distanceMiles, inRadiusBox, lookupZip, normalizeZip } from "./geo";
import { matchProcedures } from "./procedure-match";
import { headlinePrice } from "./pricing";
import type { Hospital, InsuranceType, Procedure, SearchParams, SearchResult } from "./types";

const DEFAULT_RADIUS = 50;
export const DEFAULT_RESULT_LIMIT = 50;
export const MAX_RESULT_LIMIT = 100;

function matchProcedure(query: string): Procedure | undefined {
  const q = query.trim();
  if (!q) return undefined;
  const bySlug = getProcedure(q);
  if (bySlug) return bySlug;
  return matchProcedures(q, getProcedures())[0];
}

function hospitalCandidates(
  origin: { lat: number; lng: number } | null,
  radiusMiles: number,
): Hospital[] {
  const all = getHospitals();
  if (!origin) return all;
  return all.filter((h) =>
    inRadiusBox(origin.lat, origin.lng, h.latitude, h.longitude, radiusMiles),
  );
}

export function searchHospitals(
  raw: SearchParams & { limit?: number; offset?: number },
): {
  results: SearchResult[];
  procedure: Procedure | null;
  zip: string;
  origin: { lat: number; lng: number; city: string; state: string } | null;
  warnings: string[];
  total: number;
  limit: number;
  offset: number;
} {
  const warnings: string[] = [];
  const procedure = matchProcedure(raw.procedure);
  const limit = Math.min(
    Math.max(raw.limit ?? DEFAULT_RESULT_LIMIT, 1),
    MAX_RESULT_LIMIT,
  );
  const offset = Math.max(raw.offset ?? 0, 0);

  if (!procedure) {
    return {
      results: [],
      procedure: null,
      zip: normalizeZip(raw.zip),
      origin: null,
      warnings: [
        "We couldn't match that procedure. Try knee replacement, C-section, mammogram, or gallbladder removal.",
      ],
      total: 0,
      limit,
      offset,
    };
  }

  const zip = normalizeZip(raw.zip);
  const origin =
    Number.isFinite(raw.lat) && Number.isFinite(raw.lng)
      ? { lat: raw.lat!, lng: raw.lng!, city: "your location", state: "" }
      : lookupZip(zip);

  if (!origin) {
    warnings.push(
      zip.length === 5
        ? `ZIP ${zip} isn't in the Census ZIP code tabulation areas (PO-box-only ZIPs aren't). Try your home ZIP.`
        : "Enter a 5-digit U.S. ZIP code.",
    );
    return {
      results: [],
      procedure,
      zip,
      origin: null,
      warnings,
      total: 0,
      limit,
      offset,
    };
  }

  const radius = raw.radiusMiles ?? DEFAULT_RADIUS;
  const insurance = (raw.insurance ?? "cash") as InsuranceType;
  const minStars = raw.minStars ?? 0;
  const maxPrice = raw.maxPrice;

  let results: SearchResult[] = hospitalCandidates(origin, radius).map(
    (hospital) => {
      const price = getPrice(hospital.id, procedure.id) ?? null;
      const dist = distanceMiles(
        origin.lat,
        origin.lng,
        hospital.latitude!,
        hospital.longitude!,
      );
      return {
        hospital,
        procedure,
        price,
        distanceMiles: dist,
        headline: headlinePrice(price, insurance),
      };
    },
  );

  results = results.filter((r) => r.distanceMiles <= radius);

  if (minStars > 0) {
    const before = results.length;
    results = results.filter(
      (r) => r.hospital.cmsOverallStars != null && r.hospital.cmsOverallStars >= minStars,
    );
    const unrated = before - results.length;
    if (unrated > 0) {
      warnings.push(
        `The star filter hides ${unrated} hospital(s) that are below it or that CMS doesn't rate.`,
      );
    }
  }

  // A price cap can only be checked against a published price: hospitals without one are excluded.
  if (maxPrice != null && maxPrice > 0) {
    results = results.filter((r) => r.headline != null && r.headline.amount <= maxPrice);
  }

  const sort = raw.sort ?? "distance";
  results.sort((a, b) => {
    if (sort === "quality") {
      // Unrated hospitals sort after every rated one; they are not treated as zero stars.
      const sa = a.hospital.cmsOverallStars ?? -1;
      const sb = b.hospital.cmsOverallStars ?? -1;
      if (sa !== sb) return sb - sa;
      return a.distanceMiles - b.distanceMiles;
    }
    if (sort === "price") {
      // Only published figures of the same kind are compared; hospitals without one go last.
      const pa = a.headline?.amount ?? Infinity;
      const pb = b.headline?.amount ?? Infinity;
      if (pa !== pb) return pa - pb;
      return a.distanceMiles - b.distanceMiles;
    }
    return a.distanceMiles - b.distanceMiles;
  });

  const total = results.length;

  if (total === 0) {
    warnings.push(
      "No hospitals matched your filters. Try widening the radius or lowering the quality threshold.",
    );
  }

  const withPrice = results.filter((r) => r.headline).length;
  if (total > 0 && withPrice < total) {
    const what = insurance === "cash" || insurance === "uninsured" ? "cash price" : "negotiated rate";
    warnings.push(
      `${total - withPrice} of ${total} hospital(s) have no published ${what} for this procedure in our data. We show only figures from hospitals' own price files, never estimates.`,
    );
  }

  return {
    results: results.slice(offset, offset + limit),
    procedure,
    zip,
    origin,
    warnings,
    total,
    limit,
    offset,
  };
}

export function procedureSuggestions(query: string, limit = 10): Procedure[] {
  const all = getProcedures();
  if (!query.trim()) return all.slice(0, limit);
  return matchProcedures(query, all).slice(0, limit);
}

export { getHospital, getProcedure, getHospitalCount };