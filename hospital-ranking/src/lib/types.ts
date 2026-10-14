export type InsuranceType = "cash" | "ppo" | "hdhp" | "uninsured";

export interface Procedure {
  id: string;
  slug: string;
  name: string;
  plainName: string;
  description: string;
  cptCodes: string[];
  drgCodes: string[];
  category: string;
  isShoppable: boolean;
  searchTerms: string[];
  /** The one scope this procedure is priced at, so figures are comparable */
  scope?: PriceScope;
  matchType?: "ms-drg" | "cpt" | "hcpcs";
  /** Lowest plausible figure for the whole service; lower rows are quarantined */
  priceFloorUsd?: number;
  /** Where the code definitions were checked */
  codeSource?: string;
  /** Caveat about what the code covers */
  codeNote?: string;
}

export interface Hospital {
  id: string;
  cmsProviderId?: string;
  npi?: string;
  hospitalType?: string;
  ownership?: string;
  emergencyServices?: string;
  name: string;
  address: string;
  city: string;
  state: string;
  zip: string;
  phone?: string;
  website?: string;
  shoppableUrl?: string;
  latitude: number | null;
  longitude: number | null;
  /** How the coordinates were obtained (census_address_exact, zcta_point, none) */
  geocodeSource?: string;
  cmsOverallStars: number | null;
  hcahpsSummary: number | null;
  readmissionRate: number | null;
  mortalityRate: number | null;
  safetyRating: number | null;
  dataVintage: string;
}

export interface ProcedurePriceProvenance {
  /** Source category: mrf, clinic_website, disclosure_form, aggregator, etc. */
  sourceType: string;
  /** Live URL where price can be verified */
  sourceUrl?: string;
  /** When we retrieved/scraped the source (ISO 8601) */
  retrievedAt?: string;
  /** Who/what extracted this price */
  extractedBy?: string;
  /** Confidence in extraction accuracy (0.0–1.0) */
  confidence?: number;
  /** SHA256 hash of source document for reproducibility */
  sourceDocumentHash?: string;
}

export interface ProcedurePriceBundle {
  /** Components explicitly included in this price */
  includes: string[];
  /** Number of inpatient nights included, if specified */
  inpatientNights?: number | null;
  /** Number of post-op physical therapy sessions, if specified */
  physioSessions?: number | null;
  /** Brand of implant device, if specified */
  deviceBrand?: string | null;
  /** Components explicitly NOT included */
  explicitlyExcludes?: string[];
  /** Score indicating what % of canonical bundle is included (0.0–1.0) */
  completenessScore: number;
}

export type PriceScope = "inpatient_stay" | "facility_service" | "professional";

export interface ProcedurePrice {
  hospitalId: string;
  procedureId: string;
  cmsProviderId?: string;
  cashLow: number | null;
  cashMedian: number | null;
  cashHigh: number | null;
  negotiatedMedian: number | null;
  negotiatedLow?: number | null;
  negotiatedHigh?: number | null;
  /** Number of distinct payer/plan rates behind the negotiated figures */
  payerCount?: number | null;
  /** Hospital's list price; shown only as such, never as a cash price */
  grossCharge?: number | null;
  matchType?: "ms-drg" | "cpt" | "hcpcs" | null;
  /** e.g. ["MS-DRG:470"], ["CPT:45378"] */
  matchedCodes?: string[];
  /** What the figure covers; each procedure has exactly one canonical scope */
  scope?: PriceScope | null;
  priceSource: "hospital_mrf" | "trilliant_mrf";
  /** Date from the source file, never the build date */
  priceVintage: string;
  /** The hospital's own machine-readable file, when the source provides it */
  mrfUrl?: string | null;
  sourceDataset?: string | null;
  sourceDocumentHash?: string | null;
  /** True if the source date is more than 18 months before the dataset reference date */
  stale?: boolean;
  /** Data provenance metadata */
  provenance?: ProcedurePriceProvenance;
  /** Bundle composition if this price represents a bundled package */
  bundle?: ProcedurePriceBundle;
}

export interface SearchResult {
  hospital: Hospital;
  procedure: Procedure;
  price: ProcedurePrice | null;
  distanceMiles: number;
  /** The figure the result leads with (cash or negotiated), or null if the hospital publishes none */
  headline: { amount: number; kind: "cash" | "negotiated" } | null;
}

export interface SearchParams {
  procedure: string;
  zip: string;
  lat?: number;
  lng?: number;
  radiusMiles?: number;
  minStars?: number;
  maxPrice?: number;
  insurance?: InsuranceType;
  sort?: "distance" | "price" | "quality";
  limit?: number;
  offset?: number;
}

export interface ZipCentroid {
  lat: number;
  lng: number;
  city: string;
  state: string;
}
