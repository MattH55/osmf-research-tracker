import { existsSync, readFileSync } from "fs";
import path from "path";
import type { ZipCentroid } from "./types";

const EARTH_RADIUS_MI = 3958.8;

let _zipIndex: Record<string, ZipCentroid> | null = null;

/** Census Gazetteer ZCTA points (etl/build_dataset.py). Missing file = broken deploy, not demo data. */
function loadZipIndex(): Record<string, ZipCentroid> {
  if (_zipIndex) return _zipIndex;
  const file = path.join(process.cwd(), "data", "cms", "zip-centroids.json");
  if (!existsSync(file)) throw new Error("Required data file missing: data/cms/zip-centroids.json");
  _zipIndex = JSON.parse(readFileSync(file, "utf-8")) as Record<string, ZipCentroid>;
  return _zipIndex;
}

/** Digits only, first five. Short input is NOT zero-padded: "2134" is not 02134. */
export function normalizeZip(zip: string): string {
  return zip.replace(/\D/g, "").slice(0, 5);
}

export function lookupZip(zip: string): ZipCentroid | null {
  const key = normalizeZip(zip);
  if (key.length !== 5) return null;
  return loadZipIndex()[key] ?? null;
}

/** Rough bounding-box check before haversine (radius in miles). */
export function inRadiusBox(
  lat: number,
  lng: number,
  pointLat: number | null,
  pointLng: number | null,
  radiusMiles: number,
): boolean {
  if (pointLat == null || pointLng == null) return false;
  const latDelta = radiusMiles / 69;
  const lngDelta = radiusMiles / (69 * Math.cos((lat * Math.PI) / 180));
  return (
    Math.abs(pointLat - lat) <= latDelta &&
    Math.abs(pointLng - lng) <= lngDelta
  );
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