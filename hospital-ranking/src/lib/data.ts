import hospitalsJson from "../../data/seed/hospitals.json";
import proceduresJson from "../../data/seed/procedures.json";
import pricesJson from "../../data/seed/prices.json";
import type { Hospital, Procedure, ProcedurePrice } from "./types";

export const DATA_VINTAGE = "2025-10-01";
export const PRICE_VINTAGE = "2025-09-15";

const hospitals = hospitalsJson as Hospital[];
const procedures = proceduresJson as Procedure[];
const prices = pricesJson as ProcedurePrice[];

const hospitalById = new Map(hospitals.map((h) => [h.id, h]));
const procedureById = new Map(procedures.map((p) => [p.id, p]));
const procedureBySlug = new Map(procedures.map((p) => [p.slug, p]));

const priceKey = (hospitalId: string, procedureId: string) =>
  `${hospitalId}:${procedureId}`;

const priceByKey = new Map(
  prices.map((p) => [priceKey(p.hospitalId, p.procedureId), p]),
);

export function getHospitals(): Hospital[] {
  return hospitals;
}

export function getHospital(id: string): Hospital | undefined {
  return hospitalById.get(id);
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
  return priceByKey.get(priceKey(hospitalId, procedureId));
}

export function getPricesForHospital(hospitalId: string): ProcedurePrice[] {
  return prices.filter((p) => p.hospitalId === hospitalId);
}

export function getPricesForProcedure(procedureId: string): ProcedurePrice[] {
  return prices.filter((p) => p.procedureId === procedureId);
}