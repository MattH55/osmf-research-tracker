import { existsSync, readFileSync } from "fs";
import path from "path";
import proceduresJson from "../../data/seed/procedures.json";
import pricesJson from "../../data/seed/prices.json";
import seedHospitalsJson from "../../data/seed/hospitals.json";
import { estimateProcedurePrice } from "./pricing";
import type { Hospital, Procedure, ProcedurePrice } from "./types";

const CMS_DIR = path.join(process.cwd(), "data", "cms");

function readJson<T>(file: string): T | null {
  if (!existsSync(file)) return null;
  return JSON.parse(readFileSync(file, "utf-8")) as T;
}

export interface DataMeta {
  hospitalCount?: number;
  zipCount?: number;
  builtAt?: string;
  priceNote?: string;
}

let _hospitals: Hospital[] | null = null;
let _hospitalById: Map<string, Hospital> | null = null;
let _meta: DataMeta | null = null;

function loadHospitals(): Hospital[] {
  if (_hospitals) return _hospitals;
  const cms = readJson<Hospital[]>(path.join(CMS_DIR, "hospitals.json"));
  _hospitals = cms ?? (seedHospitalsJson as Hospital[]);
  return _hospitals;
}

function hospitalMap(): Map<string, Hospital> {
  if (!_hospitalById) {
    _hospitalById = new Map(loadHospitals().map((h) => [h.id, h]));
  }
  return _hospitalById;
}

export function getDataMeta(): DataMeta {
  if (!_meta) {
    _meta = readJson<DataMeta>(path.join(CMS_DIR, "meta.json")) ?? {
      hospitalCount: loadHospitals().length,
      builtAt: "seed",
    };
  }
  return _meta;
}

export const DATA_VINTAGE =
  getDataMeta().builtAt ?? "2025-10-01";
export const PRICE_VINTAGE = "2025-09-15";

const procedures = proceduresJson as Procedure[];
const prices = pricesJson as ProcedurePrice[];
const seedHospitals = seedHospitalsJson as Hospital[];

const procedureById = new Map(procedures.map((p) => [p.id, p]));
const procedureBySlug = new Map(procedures.map((p) => [p.slug, p]));

/** Map sample demo prices onto CMS hospitals via cmsProviderId */
const priceByCmsAndProcedure = new Map<string, ProcedurePrice>();
for (const sh of seedHospitals) {
  const cmsId = sh.cmsProviderId;
  if (!cmsId) continue;
  for (const p of prices) {
    if (p.hospitalId === sh.id) {
      priceByCmsAndProcedure.set(`${cmsId}:${p.procedureId}`, {
        ...p,
        hospitalId: `hosp-cms-${cmsId}`,
      });
    }
  }
}

const priceByHospitalProcedure = new Map(
  prices.map((p) => [`${p.hospitalId}:${p.procedureId}`, p]),
);

/** Real prices scraped from hospital MRF files (etl/ingest_mrf_prices.py) */
const mrfPrices = readJson<ProcedurePrice[]>(path.join(CMS_DIR, "mrf-prices.json")) ?? [];
const mrfByCmsAndProcedure = new Map<string, ProcedurePrice>();
const mrfByHospitalProcedure = new Map<string, ProcedurePrice>();
for (const p of mrfPrices) {
  mrfByHospitalProcedure.set(`${p.hospitalId}:${p.procedureId}`, p);
  const cmsId =
    p.cmsProviderId ?? p.hospitalId.replace(/^hosp-cms-/, "");
  if (cmsId) mrfByCmsAndProcedure.set(`${cmsId}:${p.procedureId}`, p);
}

const ALLOW_MODELED_ESTIMATES = process.env.ALLOW_MODELED_ESTIMATES === "1";

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

export function getPrice(
  hospitalId: string,
  procedureId: string,
): ProcedurePrice | undefined {
  const mrfDirect = mrfByHospitalProcedure.get(`${hospitalId}:${procedureId}`);
  if (mrfDirect) return mrfDirect;

  const h = hospitalMap().get(hospitalId);
  if (h?.cmsProviderId) {
    const mrfCms = mrfByCmsAndProcedure.get(`${h.cmsProviderId}:${procedureId}`);
    if (mrfCms) return mrfCms;
  }

  const direct = priceByHospitalProcedure.get(`${hospitalId}:${procedureId}`);
  if (direct) return direct;
  if (!h) return undefined;
  if (h.cmsProviderId) {
    const cms = priceByCmsAndProcedure.get(`${h.cmsProviderId}:${procedureId}`);
    if (cms) return cms;
  }
  if (ALLOW_MODELED_ESTIMATES) {
    return estimateProcedurePrice(h, procedureId);
  }
  return undefined;
}

export function getMrfPriceMeta(): {
  count: number;
  allowModeledEstimates: boolean;
} {
  return {
    count: mrfPrices.length,
    allowModeledEstimates: ALLOW_MODELED_ESTIMATES,
  };
}

export function getPricesForHospital(hospitalId: string): ProcedurePrice[] {
  const h = hospitalMap().get(hospitalId);
  if (!h) return [];
  return procedures
    .map((proc) => getPrice(hospitalId, proc.id))
    .filter((p): p is ProcedurePrice => Boolean(p));
}

export function getPricesForProcedure(procedureId: string): ProcedurePrice[] {
  return loadHospitals()
    .map((h) => getPrice(h.id, procedureId))
    .filter((p): p is ProcedurePrice => Boolean(p));
}