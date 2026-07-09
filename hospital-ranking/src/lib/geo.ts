import zipCentroids from "../../data/seed/zip-centroids.json";
import type { ZipCentroid } from "./types";

const EARTH_RADIUS_MI = 3958.8;

export function normalizeZip(zip: string): string {
  return zip.replace(/\D/g, "").slice(0, 5);
}

export function lookupZip(zip: string): ZipCentroid | null {
  const key = normalizeZip(zip);
  const hit = (zipCentroids as Record<string, ZipCentroid>)[key];
  return hit ?? null;
}

/** Haversine distance in miles between two lat/lng points. */
export function distanceMiles(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
): number {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  return EARTH_RADIUS_MI * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

export function formatDistance(miles: number): string {
  if (miles < 0.5) return "< 0.5 mi";
  if (miles < 10) return `${miles.toFixed(1)} mi`;
  return `${Math.round(miles)} mi`;
}