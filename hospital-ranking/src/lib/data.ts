import { existsSync, readFileSync } from "fs";
import path from "path";
import proceduresJson from "../../data/seed/procedures.json";
import { PRICE_CEILING, priceFloor } from "./pricing";
import type { Hospital, Procedure, ProcedurePrice } from "./types";

const CMS_DIR = path.join(process.cwd(), "data", "cms");

/** Real data only: a missing file is a broken deploy, never a reason to show demo data. */
function readRequired<T>(file: string): T {
  if (!existsSync(file)) {
    throw new Error(`Required data file missing: ${path.relative(process.cwd(), file)}`);
  }
  return JSON.parse(readFileSync(file, "utf-8")) as T;
}

function readOptional<T>(file: string, fallback: T): T {
  return existsSync(file) ? (JSON.parse(readFileSync(file, "utf-8")) as T) : fallback;
}

export interface DataMeta {
  hospitalCount?: number;
  zipCount?: number;
  builtAt?: string;
  cmsReleaseDate?: string;
  priceNote?: string;
}

let _hospitals: Hospital[] | null = null;
let _hospitalById: Map<string, Hospital> | null = null;
let _meta: DataMeta | null = null;

function loadHospitals(): Hospital[] {
  if (!_hospitals) _hospitals = readRequired<Hospital[]>(path.join(CMS_DIR, "hospitals.json"));
  return _hospitals;
}

function hospitalMap(): Map<string, Hospital> {
  if (!_hospitalById) {
    _hospitalById = new Map(loadHospitals().map((h) => [h.id, h]));
  }
  return _hospitalById;
}

export function getDataMeta(): DataMeta {
  if (!_meta) _meta = readRequired<DataMeta>(path.join(CMS_DIR, "meta.json"));
  return _meta;
}

/** CMS release date of the quality data (falls back to the build date only if CMS gave none). */
export const DATA_VINTAGE =
  getDataMeta().cmsReleaseDate ?? getDataMeta().builtAt ?? "unknown";

const procedures = proceduresJson as Procedure[];
const procedureById = new Map(procedures.map((p) => [p.id, p]));
const procedureBySlug = new Map(procedures.map((p) => [p.slug, p]));

/**
 * Second line of defence behind the ETL validator: a row that breaks the data contract
 * is dropped at load time rather than shown. The pipeline should already have
 * quarantined it; `getRejectedPriceCount()` makes any leak visible.
 */
let rejected = 0;
function acceptable(p: ProcedurePrice): boolean {
  const proc = procedureById.get(p.procedureId);
  const amounts = [p.cashLow, p.cashMedian, p.cashHigh, p.negotiatedLow, p.negotiatedMedian, p.negotiatedHigh]
    .filter((v): v is number => typeof v === "number");
  const headline = p.cashMedian ?? p.negotiatedMedian;
  const ok =
    !!proc &&
    (p.priceSource === "hospital_mrf" || p.priceSource === "trilliant_mrf") &&
    headline != null &&
    amounts.every((v) => v > 0 && v < PRICE_CEILING) &&
    headline >= priceFloor(p.scope) &&
    /^\d{4}-\d{2}-\d{2}$/.test(p.priceVintage ?? "") &&
    (p.mrfUrl == null || p.mrfUrl.startsWith("https://"));
  if (!ok) rejected++;
  return ok;
}

function loadPrices(file: string): ProcedurePrice[] {
  return readOptional<ProcedurePrice[]>(path.join(CMS_DIR, file), []).filter(acceptable);
}

/** Direct hospital MRF scrape (etl/ingest_mrf_prices.py) — highest priority */
const directMrfPrices = loadPrices("mrf-prices.json").filter((p) => p.priceSource === "hospital_mrf");
/** Trilliant ORIA bulk ingest (etl/ingest_trilliant.py) — nationwide MRF coverage */
const trilliantPrices = loadPrices("trilliant-prices.json");

function indexByCms(rows: ProcedurePrice[]): Map<string, ProcedurePrice> {
  const m = new Map<string, ProcedurePrice>();
  for (const p of rows) {
    const cmsId = p.cmsProviderId ?? p.hospitalId.replace(/^hosp-cms-/, "");
    m.set(`${cmsId}:${p.procedureId}`, p);
  }
  return m;
}

const directByCms = indexByCms(directMrfPrices);
const trilliantByCms = indexByCms(trilliantPrices);

export function getHospitalCount(): number {
  return loadHospitals().length;
}

export function getHospitals(): Hospital[] {
  return loadHospitals();
}

export function getHospital(id: string): Hospital | undefined {
  return hospitalMap().get(id);
}

export function getProcedures(): Procedure[] {
  return procedures;
}

export function getProcedure(slugOrId: string): Procedure | undefined {
  return procedureBySlug.get(slugOrId) ?? procedureById.get(slugOrId);
}

/** A hospital's own published price, or undefined. Nothing is ever modelled or imputed. */
export function getPrice(
  hospitalId: string,
  procedureId: string,
): ProcedurePrice | undefined {
  const h = hospitalMap().get(hospitalId);
  const cmsId = h?.cmsProviderId ?? hospitalId.replace(/^hosp-cms-/, "");
  const key = `${cmsId}:${procedureId}`;
  return directByCms.get(key) ?? trilliantByCms.get(key);
}

export function getMrfPriceMeta(): {
  count: number;
  directCount: number;
  trilliantCount: number;
  rejectedCount: number;
} {
  return {
    count: directMrfPrices.length + trilliantPrices.length,
    directCount: directMrfPrices.length,
    trilliantCount: trilliantPrices.length,
    rejectedCount: rejected,
  };
}

export function getPricesForHospital(hospitalId: string): ProcedurePrice[] {
  if (!hospitalMap().has(hospitalId)) return [];
  return procedures
    .map((proc) => getPrice(hospitalId, proc.id))
    .filter((p): p is ProcedurePrice => Boolean(p));
}

export function getPricesForProcedure(procedureId: string): ProcedurePrice[] {
  return loadHospitals()
    .map((h) => getPrice(h.id, procedureId))
    .filter((p): p is ProcedurePrice => Boolean(p));
}
