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
  latitude: number;
  longitude: number;
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
  oopUninsured: number | null;
  oopPpo: number | null;
  oopHdhp: number | null;
  priceSource: string;
  priceVintage: string;
  mrfUrl?: string;
  /** True if this price is modeled/estimated rather than observed */
  isEstimate?: boolean;
  /** True if observation is >18 months old */
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
  estimatedOop: number | null;
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

export type TourismClinicStatus = "coming_soon" | "active";

export interface TourismClinic {
  id: string;
  name: string | null;
  city: string;
  url: string | null;
  accreditation?: string;
  status: TourismClinicStatus;
}

export interface TourismDestination {
  id: string;
  country: string;
  flagEmoji: string;
  region: string;
  hubCities: string[];
  accreditationNote: string;
  travelFromUs: string;
  multipliers: { low: number; median: number; high: number };
  clinics: TourismClinic[];
}

export interface TourismEstimate {
  procedureId: string;
  destinationId: string;
  destination: TourismDestination;
  cashLow: number;
  cashMedian: number;
  cashHigh: number;
  usReferenceMedian: number;
  savingsPercent: number;
  packageIncludes: string[];
  packageExcludes: string[];
  priceSource: "medical_tourism_estimate";
  priceVintage: string;
}