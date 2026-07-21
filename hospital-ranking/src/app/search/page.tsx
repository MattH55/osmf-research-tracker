import { Suspense } from "react";
import { Disclaimer } from "@/components/disclaimer";
import { HospitalResultCard } from "@/components/hospital-result-card";
import { MedicalTourismPanel } from "@/components/medical-tourism-panel";
import { ProcedureInsights } from "@/components/procedure-insights";
import { SearchFilters } from "@/components/search-filters";
import { SearchPagination } from "@/components/search-pagination";
import { SearchForm } from "@/components/search-form";
import { getProcedures } from "@/lib/data";
import { medianUsCashFromResults } from "@/lib/medical-tourism";
import { isReportedPrice } from "@/lib/pricing";
import { DEFAULT_RESULT_LIMIT, searchHospitals } from "@/lib/search";
import type { InsuranceType, SearchParams } from "@/lib/types";

function FiltersBar() {
  return (
    <Suspense fallback={<div className="h-16 animate-pulse rounded-xl bg-slate-100" />}>
      <SearchFilters />
    </Suspense>
  );
}

function parseSearchParams(
  sp: Record<string, string | string[] | undefined>,
): SearchParams {
  const get = (k: string) => {
    const v = sp[k];
    return Array.isArray(v) ? v[0] : v;
  };
  const page = Math.max(Number(get("page")) || 1, 1);
  const limit = DEFAULT_RESULT_LIMIT;
  return {
    procedure: get("procedure") ?? "",
    zip: get("zip") ?? "",
    lat: get("lat") ? Number(get("lat")) : undefined,
    lng: get("lng") ? Number(get("lng")) : undefined,
    radiusMiles: Number(get("radius")) || 50,
    minStars: Number(get("minStars")) || 0,
    maxPrice: get("maxPrice") ? Number(get("maxPrice")) : undefined,
    insurance: (get("insurance") as InsuranceType) ?? "cash",
    sort: (get("sort") as SearchParams["sort"]) ?? "distance",
    limit,
    offset: (page - 1) * limit,
  };
}

function PaginationBar({
  total,
  limit,
  offset,
}: {
  total: number;
  limit: number;
  offset: number;
}) {
  return (
    <Suspense fallback={null}>
      <SearchPagination total={total} limit={limit} offset={offset} />
    </Suspense>
  );
}

function SearchResults({ sp }: { sp: Record<string, string | string[] | undefined> }) {
  const params = parseSearchParams(sp);
  const { results, procedure, zip, origin, warnings, total, limit, offset } =
    searchHospitals(params);

  const localUsMedian = procedure
    ? medianUsCashFromResults(
        results
          .filter((r) => r.price && isReportedPrice(r.price))
          .map((r) => r.price?.cashMedian),
      )
    : undefined;

  if (!params.procedure || (!params.zip && (params.lat == null || params.lng == null))) {
    return (
      <p className="text-slate-600">
        Enter a procedure and ZIP code above to see hospitals near you, or use your current location.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {procedure && (
        <div className="rounded-xl border border-teal-100 bg-teal-50/50 px-4 py-3">
          <p className="text-sm text-teal-900">
            <span className="font-semibold">{procedure.plainName}</span>
            {origin
              ? ` near ${origin.city}${origin.state ? `, ${origin.state}` : ""}${zip ? ` (${zip})` : ""}`
              : zip
                ? ` · ZIP ${zip}`
                : " near your current location"}
            {" · "}
            {total} {total === 1 ? "facility" : "facilities"} found
            {total > results.length && (
              <span className="text-teal-800/70">
                {" "}
                (showing {results.length} on this page)
              </span>
            )}
          </p>
          <p className="mt-1 text-xs text-teal-800/80">{procedure.description}</p>
        </div>
      )}

      {warnings.map((w) => (
        <p key={w} className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {w}
        </p>
      ))}

      {procedure && (
        <>
          <ProcedureInsights procedure={procedure} />
          <MedicalTourismPanel procedure={procedure} usBaseline={localUsMedian} />
        </>
      )}

      <h2 className="text-lg font-semibold text-slate-900">U.S. hospitals near you</h2>

      <FiltersBar />

      <Disclaimer compact />

      <div className="space-y-4" role="list" aria-label="Hospital results">
        {results.map((r) => (
          <HospitalResultCard key={r.hospital.id} result={r} />
        ))}
      </div>

      <PaginationBar total={total} limit={limit} offset={offset} />
    </div>
  );
}

export default async function SearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const procedures = getProcedures();
  const procedure = Array.isArray(sp.procedure) ? sp.procedure[0] : sp.procedure;
  const zip = Array.isArray(sp.zip) ? sp.zip[0] : sp.zip;

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <h1 className="text-2xl font-bold text-slate-900">Search results</h1>
      <p className="mt-1 text-slate-600">
        Hospitals ranked by your sort preference with quality and price side by side.
      </p>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4">
        <SearchForm
          procedures={procedures}
          defaultProcedure={procedure ?? ""}
          defaultZip={zip ?? ""}
        />
      </div>

      <div className="mt-8">
        <SearchResults sp={sp} />
      </div>
    </div>
  );
}