import { Suspense } from "react";
import { Disclaimer } from "@/components/disclaimer";
import { HospitalResultCard } from "@/components/hospital-result-card";
import { SearchFilters } from "@/components/search-filters";
import { SearchForm } from "@/components/search-form";
import { getProcedures } from "@/lib/data";
import { searchHospitals } from "@/lib/search";
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
  return {
    procedure: get("procedure") ?? "",
    zip: get("zip") ?? "",
    radiusMiles: Number(get("radius")) || 50,
    minStars: Number(get("minStars")) || 0,
    maxPrice: get("maxPrice") ? Number(get("maxPrice")) : undefined,
    insurance: (get("insurance") as InsuranceType) ?? "cash",
    sort: (get("sort") as SearchParams["sort"]) ?? "distance",
  };
}

function SearchResults({ sp }: { sp: Record<string, string | string[] | undefined> }) {
  const params = parseSearchParams(sp);
  const { results, procedure, zip, origin, warnings } = searchHospitals(params);

  if (!params.procedure || !params.zip) {
    return (
      <p className="text-slate-600">
        Enter a procedure and ZIP code above to see hospitals near you.
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
              ? ` near ${origin.city}, ${origin.state} (${zip})`
              : ` · ZIP ${zip}`}
            {" · "}
            {results.length} {results.length === 1 ? "facility" : "facilities"}
          </p>
          <p className="mt-1 text-xs text-teal-800/80">{procedure.description}</p>
        </div>
      )}

      {warnings.map((w) => (
        <p key={w} className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
          {w}
        </p>
      ))}

      <FiltersBar />

      <Disclaimer compact />

      <div className="space-y-4" role="list" aria-label="Hospital results">
        {results.map((r) => (
          <HospitalResultCard key={r.hospital.id} result={r} />
        ))}
      </div>
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