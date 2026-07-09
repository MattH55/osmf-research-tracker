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