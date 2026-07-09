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
}

export interface ZipCentroid {
  lat: number;
  lng: number;
  city: string;
  state: string;
}