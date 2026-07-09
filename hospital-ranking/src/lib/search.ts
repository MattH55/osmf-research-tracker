import {
  getHospital,
  getHospitalCount,
  getHospitals,
  getPrice,
  getProcedure,
  getProcedures,
} from "./data";
import { distanceMiles, inRadiusBox, lookupZip, normalizeZip } from "./geo";
import { estimateOop } from "./format";
import { isReportedPrice } from "./pricing";
import type { Hospital, InsuranceType, Procedure, SearchParams, SearchResult } from "./types";

const DEFAULT_RADIUS = 50;
export const DEFAULT_RESULT_LIMIT = 50;
export const MAX_RESULT_LIMIT = 100;

function matchProcedure(query: string): Procedure | undefined {
  const q = query.trim().toLowerCase();
  if (!q) return undefined;

  const bySlug = getProcedure(q);
  if (bySlug) return bySlug;

  const all = getProcedures();
  return all.find(
    (p) =>
      p.plainName.toLowerCase() === q ||
      p.name.toLowerCase() === q ||
      p.slug === q ||
      p.searchTerms.some((t) => t.toLowerCase() === q) ||
      p.searchTerms.some((t) => t.toLowerCase().includes(q)) ||
      p.plainName.toLowerCase().includes(q) ||
      p.cptCodes.some((c) => c === q),
  );
}

function hospitalCandidates(
  origin: { lat: number; lng: number } | null,
  radiusMiles: number,
): Hospital[] {
  const all = getHospitals();
  if (!origin) return all;
  return all.filter(
    (h) =>
      h.latitude &&
      h.longitude &&
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
        "We couldn't match that procedure. Try knee replacement, cataract surgery, or colonoscopy.",
      ],
      total: 0,
      limit,
      offset,
    };
  }

  const zip = normalizeZip(raw.zip);
  const origin = lookupZip(zip);
  if (!origin) {
    warnings.push(
      `ZIP ${zip} was not found in our geocoder. Try a valid 5-digit U.S. ZIP code.`,
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
        hospital.latitude,
        hospital.longitude,
      );
      return {
        hospital,
        procedure,
        price,
        distanceMiles: dist,
        estimatedOop: estimateOop(price, insurance),
      };
    },
  );

  results = results.filter((r) => r.distanceMiles <= radius);

  if (minStars > 0) {
    results = results.filter(
      (r) => (r.hospital.cmsOverallStars ?? 0) >= minStars,
    );
  }

  if (maxPrice != null && maxPrice > 0) {
    results = results.filter((r) => {
      const oop = r.estimatedOop ?? r.price?.cashMedian;
      return oop == null || oop <= maxPrice;
    });
  }

  const sort = raw.sort ?? "distance";
  results.sort((a, b) => {
    if (sort === "quality") {
      return (b.hospital.cmsOverallStars ?? 0) - (a.hospital.cmsOverallStars ?? 0);
    }
    if (sort === "price") {
      const pa = a.estimatedOop ?? a.price?.cashMedian ?? Infinity;
      const pb = b.estimatedOop ?? b.price?.cashMedian ?? Infinity;
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

  const reported = results.filter((r) => r.price && isReportedPrice(r.price)).length;
  if (total > 0 && reported < total) {
    warnings.push(
      `Prices are modeled estimates for ${total - reported} of ${total} result(s) based on national benchmarks and your state. ${reported > 0 ? `${reported} have reported hospital MRF sample prices.` : "Verify with the hospital before scheduling."}`,
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

export function procedureSuggestions(query: string): Procedure[] {
  const q = query.trim().toLowerCase();
  if (!q) return getProcedures().slice(0, 6);
  return getProcedures().filter(
    (p) =>
      p.plainName.toLowerCase().includes(q) ||
      p.searchTerms.some((t) => t.toLowerCase().includes(q)),
  );
}

export { getHospital, getProcedure, getHospitalCount };