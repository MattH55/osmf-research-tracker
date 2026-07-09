import {
  getHospital,
  getHospitals,
  getPrice,
  getProcedure,
  getProcedures,
} from "./data";
import { distanceMiles, lookupZip, normalizeZip } from "./geo";
import { estimateOop } from "./format";
import type { InsuranceType, Procedure, SearchParams, SearchResult } from "./types";

const DEFAULT_RADIUS = 50;

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

export function searchHospitals(raw: SearchParams): {
  results: SearchResult[];
  procedure: Procedure | null;
  zip: string;
  origin: { lat: number; lng: number; city: string; state: string } | null;
  warnings: string[];
} {
  const warnings: string[] = [];
  const procedure = matchProcedure(raw.procedure);
  if (!procedure) {
    return {
      results: [],
      procedure: null,
      zip: normalizeZip(raw.zip),
      origin: null,
      warnings: ["We couldn't match that procedure. Try knee replacement, cataract surgery, or colonoscopy."],
    };
  }

  const zip = normalizeZip(raw.zip);
  const origin = lookupZip(zip);
  if (!origin) {
    warnings.push(
      `ZIP ${zip} isn't in our demo geocoder yet. Showing all sample hospitals — add this ZIP to data/seed/zip-centroids.json or connect a geocoding API.`,
    );
  }

  const radius = raw.radiusMiles ?? DEFAULT_RADIUS;
  const insurance = (raw.insurance ?? "cash") as InsuranceType;
  const minStars = raw.minStars ?? 0;
  const maxPrice = raw.maxPrice;

  let results: SearchResult[] = getHospitals().map((hospital) => {
    const price = getPrice(hospital.id, procedure.id) ?? null;
    const dist = origin
      ? distanceMiles(origin.lat, origin.lng, hospital.latitude, hospital.longitude)
      : 0;
    return {
      hospital,
      procedure,
      price,
      distanceMiles: dist,
      estimatedOop: estimateOop(price, insurance),
    };
  });

  if (origin) {
    results = results.filter((r) => r.distanceMiles <= radius);
  }

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
      return pa - pb;
    }
    return a.distanceMiles - b.distanceMiles;
  });

  if (results.length === 0) {
    warnings.push(
      "No hospitals matched your filters. Try widening the radius or lowering the quality threshold.",
    );
  }

  const missingPrice = results.filter((r) => !r.price).length;
  if (missingPrice > 0) {
    warnings.push(
      `${missingPrice} hospital(s) lack price data for this procedure in our current sample dataset.`,
    );
  }

  return { results, procedure, zip, origin, warnings };
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

export { getHospital, getProcedure };