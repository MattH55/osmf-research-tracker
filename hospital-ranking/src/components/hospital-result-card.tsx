import Link from "next/link";
import { formatCurrency, formatPriceRange } from "@/lib/format";
import { priceKindLabel, SCOPE_LABEL } from "@/lib/pricing";
import { formatDistance } from "@/lib/geo";
import type { SearchResult } from "@/lib/types";
import { StarRating } from "./star-rating";

export function HospitalResultCard({ result }: { result: SearchResult }) {
  const { hospital, price, distanceMiles, headline, procedure } = result;
  const detailHref = `/hospital/${hospital.id}?procedure=${procedure.slug}`;

  return (
    <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-teal-200 hover:shadow-md">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold break-words text-slate-900">
              <Link href={detailHref} className="hover:text-teal-700">
                {hospital.name}
              </Link>
            </h2>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
              {formatDistance(distanceMiles)}
            </span>
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {hospital.address}, {hospital.city}, {hospital.state} {hospital.zip}
          </p>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                CMS overall
              </p>
              <StarRating stars={hospital.cmsOverallStars} />
            </div>
            {hospital.hcahpsSummary != null && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Patient experience
                </p>
                <p className="font-medium text-slate-800">{hospital.hcahpsSummary}/100</p>
              </div>
            )}
            {hospital.readmissionRate != null && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Readmission measures worse than U.S.
                </p>
                <p className="font-medium text-slate-800">{hospital.readmissionRate}% of measures</p>
              </div>
            )}
          </div>
        </div>
        <div className="shrink-0 text-left sm:text-right">
          {price && headline ? (
            <>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {priceKindLabel(headline.kind)}
              </p>
              <p className="text-2xl font-bold text-teal-700">
                {formatCurrency(headline.amount)}
              </p>
              {headline.kind === "cash" && price.cashLow != null && (
                <p className="mt-1 text-xs text-slate-500">
                  Range {formatPriceRange(price.cashLow, price.cashHigh)}
                </p>
              )}
              {headline.kind === "negotiated" && (
                <p className="mt-1 text-xs text-slate-500">
                  Range {formatPriceRange(price.negotiatedLow, price.negotiatedHigh)}
                  {price.payerCount ? ` across ${price.payerCount} payer rates` : ""}. Your share depends on your plan.
                </p>
              )}
              {price.scope && <p className="text-xs text-slate-500">{SCOPE_LABEL[price.scope]}</p>}
              <p className="text-xs text-slate-500">
                Published {price.priceVintage}
                {price.stale && (
                  <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-amber-800">
                    Over 18 months old
                  </span>
                )}
              </p>
            </>
          ) : (
            <p className="text-sm italic text-slate-500">
              {price ? "No published figure of this kind" : "No published price"}
            </p>
          )}
          <Link
            href={detailHref}
            className="mt-3 inline-block text-sm font-medium text-teal-700 hover:underline"
          >
            View details →
          </Link>
        </div>
      </div>
    </article>
  );
}