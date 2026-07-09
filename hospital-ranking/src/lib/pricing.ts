import type { Hospital, ProcedurePrice } from "./types";

const ESTIMATE_VINTAGE = "2025-09-15";

/** National cash medians derived from published shoppable-service benchmarks. */
export const NATIONAL_MEDIANS: Record<
  string,
  { cashMedian: number; oopPpoRatio: number; oopHdhpRatio: number }
> = {
  "proc-knee-replacement": { cashMedian: 28500, oopPpoRatio: 0.15, oopHdhpRatio: 0.22 },
  "proc-hip-replacement": { cashMedian: 35200, oopPpoRatio: 0.14, oopHdhpRatio: 0.21 },
  "proc-shoulder-replacement": { cashMedian: 22400, oopPpoRatio: 0.14, oopHdhpRatio: 0.22 },
  "proc-knee-arthroscopy": { cashMedian: 8600, oopPpoRatio: 0.15, oopHdhpRatio: 0.25 },
  "proc-rotator-cuff": { cashMedian: 11400, oopPpoRatio: 0.14, oopHdhpRatio: 0.24 },
  "proc-spinal-fusion": { cashMedian: 52800, oopPpoRatio: 0.12, oopHdhpRatio: 0.2 },
  "proc-cataract": { cashMedian: 3800, oopPpoRatio: 0.17, oopHdhpRatio: 0.28 },
  "proc-colonoscopy": { cashMedian: 1750, oopPpoRatio: 0.16, oopHdhpRatio: 0.3 },
  "proc-upper-endoscopy": { cashMedian: 3200, oopPpoRatio: 0.16, oopHdhpRatio: 0.28 },
  "proc-appendectomy": { cashMedian: 17200, oopPpoRatio: 0.14, oopHdhpRatio: 0.23 },
  "proc-cholecystectomy": { cashMedian: 14500, oopPpoRatio: 0.14, oopHdhpRatio: 0.23 },
  "proc-hernia": { cashMedian: 9600, oopPpoRatio: 0.14, oopHdhpRatio: 0.24 },
  "proc-hysterectomy": { cashMedian: 23200, oopPpoRatio: 0.13, oopHdhpRatio: 0.22 },
  "proc-cesarean": { cashMedian: 18800, oopPpoRatio: 0.13, oopHdhpRatio: 0.21 },
  "proc-vaginal-delivery": { cashMedian: 12800, oopPpoRatio: 0.14, oopHdhpRatio: 0.22 },
  "proc-cabg": { cashMedian: 78500, oopPpoRatio: 0.11, oopHdhpRatio: 0.18 },
  "proc-cardiac-cath": { cashMedian: 19200, oopPpoRatio: 0.13, oopHdhpRatio: 0.22 },
  "proc-mri-brain": { cashMedian: 1450, oopPpoRatio: 0.18, oopHdhpRatio: 0.32 },
  "proc-mri-lumbar": { cashMedian: 1680, oopPpoRatio: 0.18, oopHdhpRatio: 0.32 },
  "proc-mri-knee": { cashMedian: 1380, oopPpoRatio: 0.18, oopHdhpRatio: 0.32 },
  "proc-ct-abdomen": { cashMedian: 1280, oopPpoRatio: 0.17, oopHdhpRatio: 0.3 },
  "proc-mammogram": { cashMedian: 380, oopPpoRatio: 0.2, oopHdhpRatio: 0.35 },
  "proc-chest-xray": { cashMedian: 290, oopPpoRatio: 0.2, oopHdhpRatio: 0.35 },
  "proc-breast-biopsy": { cashMedian: 2150, oopPpoRatio: 0.17, oopHdhpRatio: 0.3 },
};

const STATE_COST_INDEX: Record<string, number> = {
  AK: 1.15, AL: 0.88, AR: 0.86, AZ: 1.02, CA: 1.32, CO: 1.05, CT: 1.18, DC: 1.22,
  DE: 1.08, FL: 1.0, GA: 0.95, HI: 1.28, IA: 0.92, ID: 0.94, IL: 1.08, IN: 0.92,
  KS: 0.93, KY: 0.9, LA: 0.92, MA: 1.25, MD: 1.12, ME: 1.02, MI: 0.98, MN: 1.05,
  MO: 0.9, MS: 0.84, MT: 0.95, NC: 0.96, ND: 0.96, NE: 0.94, NH: 1.08, NJ: 1.15,
  NM: 0.95, NV: 1.08, NY: 1.28, OH: 0.94, OK: 0.9, OR: 1.12, PA: 1.06, RI: 1.1,
  SC: 0.94, SD: 0.93, TN: 0.92, TX: 0.98, UT: 0.98, VA: 1.02, VT: 1.05, WA: 1.15,
  WI: 1.0, WV: 0.88, WY: 0.98,
};

const TYPE_MULTIPLIER: Record<string, number> = {
  "Acute Care Hospitals": 1.0,
  "Critical Access Hospitals": 0.74,
  Childrens: 1.06,
  Psychiatric: 0.82,
  "Long-term": 0.68,
  "Rural Emergency Hospital": 0.76,
  "Acute Care - Veterans Administration": 0.88,
  "Acute Care - Department of Defense": 0.9,
};

const OWNERSHIP_MULTIPLIER: Record<string, number> = {
  Proprietary: 1.06,
  "Government - Federal": 0.9,
  "Government - State": 0.92,
  "Government - Local": 0.94,
  "Voluntary non-profit - Private": 1.0,
  "Voluntary non-profit - Other": 0.98,
  "Voluntary non-profit - Church": 0.97,
  Tribal: 0.9,
  "Department of Defense": 0.9,
};

function starsMultiplier(stars: number | null): number {
  if (stars == null) return 1.0;
  if (stars >= 5) return 1.06;
  if (stars >= 4) return 1.03;
  if (stars >= 3) return 1.0;
  if (stars >= 2) return 0.96;
  return 0.92;
}

/** Stable 0.94–1.06 variation per hospital so estimates don't look identical. */
function hospitalJitter(hospitalId: string): number {
  let hash = 0;
  for (let i = 0; i < hospitalId.length; i++) {
    hash = (hash * 31 + hospitalId.charCodeAt(i)) | 0;
  }
  return 0.94 + (Math.abs(hash) % 13) / 100;
}

function roundPrice(n: number): number {
  return Math.round(n / 10) * 10;
}

/** U.S. national cash median benchmark for a procedure (medical-tourism comparison baseline). */
export function getUsReferenceMedian(procedureId: string): number | undefined {
  return NATIONAL_MEDIANS[procedureId]?.cashMedian;
}

export function isReportedPrice(price: ProcedurePrice): boolean {
  return (
    price.priceSource === "hospital_mrf" ||
    price.priceSource === "trilliant_mrf" ||
    price.priceSource === "sample_mrf"
  );
}

export function priceSourceLabel(source: string): string {
  if (source === "hospital_mrf") return "Hospital MRF (published)";
  if (source === "trilliant_mrf") return "Hospital MRF (Trilliant ORIA)";
  if (source === "sample_mrf") return "Hospital MRF (sample)";
  if (source === "estimated") return "Modeled estimate (not hospital-reported)";
  return source;
}

/** Documented formula — only used when ALLOW_MODELED_ESTIMATES=1 */
export const ESTIMATE_METHODOLOGY = {
  summary:
    "National shoppable-service medians × state cost index × hospital-type/ownership/stars × per-hospital jitter. Not from any hospital file.",
  sources: [
    "Procedure medians: CMS shoppable-service / FAIR Health public benchmarks (hand-curated)",
    "State index: approximate Medicare geographic adjustment factors",
    "Hospital modifiers: CMS hospital type, ownership, overall star rating",
  ],
};

export function estimateProcedurePrice(
  hospital: Hospital,
  procedureId: string,
): ProcedurePrice | undefined {
  const bench = NATIONAL_MEDIANS[procedureId];
  if (!bench) return undefined;

  const stateIdx = STATE_COST_INDEX[hospital.state] ?? 1.0;
  const typeIdx = TYPE_MULTIPLIER[hospital.hospitalType ?? ""] ?? 1.0;
  const ownIdx = OWNERSHIP_MULTIPLIER[hospital.ownership ?? ""] ?? 1.0;
  const starIdx = starsMultiplier(hospital.cmsOverallStars);
  const jitter = hospitalJitter(hospital.id);

  const cashMedian = roundPrice(
    bench.cashMedian * stateIdx * typeIdx * ownIdx * starIdx * jitter,
  );
  const cashLow = roundPrice(cashMedian * 0.78);
  const cashHigh = roundPrice(cashMedian * 1.28);
  const negotiatedMedian = roundPrice(cashMedian * 0.84);

  return {
    hospitalId: hospital.id,
    procedureId,
    cashLow,
    cashMedian,
    cashHigh,
    negotiatedMedian,
    oopUninsured: cashMedian,
    oopPpo: roundPrice(cashMedian * bench.oopPpoRatio),
    oopHdhp: roundPrice(cashMedian * bench.oopHdhpRatio),
    priceSource: "estimated",
    priceVintage: ESTIMATE_VINTAGE,
  };
}