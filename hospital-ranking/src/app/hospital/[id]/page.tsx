import Link from "next/link";
import { notFound } from "next/navigation";
import { Disclaimer } from "@/components/disclaimer";
import { StarRating } from "@/components/star-rating";
import {
  DATA_VINTAGE,
  getHospital,
  getPrice,
  getPricesForHospital,
  getProcedure,
  getProcedures,
} from "@/lib/data";
import { formatCurrency, formatPriceRange, percentLabel } from "@/lib/format";
import { priceSourceLabel, SCOPE_LABEL } from "@/lib/pricing";

export default async function HospitalPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const procedureSlug = Array.isArray(sp.procedure) ? sp.procedure[0] : sp.procedure;

  const hospital = getHospital(id);
  if (!hospital) notFound();

  const focusProcedure = procedureSlug ? getProcedure(procedureSlug) : undefined;
  const focusPrice =
    focusProcedure && getPrice(hospital.id, focusProcedure.id);

  const allPrices = getPricesForHospital(hospital.id);
  const procedures = getProcedures();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <nav className="text-sm text-slate-500 break-words" aria-label="Breadcrumb">
        <Link href="/" className="hover:text-teal-700">
          Home
        </Link>
        <span className="mx-2">/</span>
        {focusProcedure ? (
          <>
            <Link
              href={`/search?procedure=${focusProcedure.slug}&zip=${hospital.zip}`}
              className="hover:text-teal-700"
            >
              Search
            </Link>
            <span className="mx-2">/</span>
          </>
        ) : null}
        <span className="text-slate-800">{hospital.name}</span>
      </nav>

      <header className="mt-4">
        <h1 className="text-2xl font-bold break-words text-slate-900 sm:text-3xl">{hospital.name}</h1>
        <p className="mt-2 text-slate-600">
          {hospital.address}, {hospital.city}, {hospital.state} {hospital.zip}
        </p>
        {hospital.phone && (
          <p className="mt-1 text-sm text-slate-600">
            <a href={`tel:${hospital.phone.replace(/\D/g, "")}`} className="text-teal-700">
              {hospital.phone}
            </a>
          </p>
        )}
        {(hospital.hospitalType || hospital.ownership || hospital.emergencyServices) && (
          <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-sm text-slate-600">
            {hospital.hospitalType && (
              <div>
                <dt className="inline font-medium text-slate-700">Type: </dt>
                <dd className="inline">{hospital.hospitalType}</dd>
              </div>
            )}
            {hospital.ownership && (
              <div>
                <dt className="inline font-medium text-slate-700">Ownership: </dt>
                <dd className="inline">{hospital.ownership}</dd>
              </div>
            )}
            {hospital.emergencyServices && (
              <div>
                <dt className="inline font-medium text-slate-700">Emergency services: </dt>
                <dd className="inline">{hospital.emergencyServices}</dd>
              </div>
            )}
          </dl>
        )}
      </header>

      <Disclaimer />

      <section className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Quality ratings (CMS)</h2>
        <p className="text-xs text-slate-500">CMS data release: {DATA_VINTAGE}</p>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-xs font-medium uppercase text-slate-500">Overall stars</dt>
            <dd className="mt-1">
              <StarRating stars={hospital.cmsOverallStars} />
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-slate-500">Patient experience</dt>
            <dd className="mt-1 text-lg font-semibold">
              {hospital.hcahpsSummary ?? "—"}
              {hospital.hcahpsSummary != null && (
                <span className="text-sm font-normal text-slate-500"> /100 HCAHPS</span>
              )}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-slate-500">
              Readmission measures worse than U.S.
            </dt>
            <dd className="mt-1 text-lg font-semibold">
              {hospital.readmissionRate != null ? `${percentLabel(hospital.readmissionRate)} of measures` : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase text-slate-500">
              Mortality measures worse than U.S.
            </dt>
            <dd className="mt-1 text-lg font-semibold">
              {hospital.mortalityRate != null ? `${percentLabel(hospital.mortalityRate)} of measures` : "—"}
            </dd>
          </div>
        </dl>
        {hospital.cmsProviderId && (
          <p className="mt-4 text-xs text-slate-500">
            CMS Provider ID: {hospital.cmsProviderId} ·{" "}
            <a
              href={`https://www.medicare.gov/care-compare/details/hospital/${hospital.cmsProviderId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-teal-700 hover:underline"
            >
              View on Medicare Care Compare
            </a>
          </p>
        )}
      </section>

      {focusProcedure && (
        <section className="mt-8 rounded-xl border border-teal-200 bg-teal-50/30 p-6">
          <h2 className="text-lg font-semibold text-slate-900">
            {focusProcedure.plainName} at this hospital
          </h2>
          {focusPrice ? (
            <>
            <dl className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <dt className="text-xs font-medium uppercase text-slate-500">Published cash price</dt>
                <dd className="text-xl font-bold text-teal-800">
                  {formatCurrency(focusPrice.cashMedian)}
                </dd>
                {focusPrice.cashLow != null && (
                  <dd className="text-sm text-slate-600">
                    Range {formatPriceRange(focusPrice.cashLow, focusPrice.cashHigh)}
                  </dd>
                )}
                {focusPrice.cashMedian == null && (
                  <dd className="text-sm text-slate-600">This hospital publishes no cash price for it.</dd>
                )}
              </div>
              <div>
                <dt className="text-xs font-medium uppercase text-slate-500">
                  Median negotiated rate (paid by insurers)
                </dt>
                <dd className="text-xl font-bold text-slate-800">
                  {formatCurrency(focusPrice.negotiatedMedian)}
                </dd>
                {focusPrice.negotiatedLow != null && (
                  <dd className="text-sm text-slate-600">
                    Range {formatPriceRange(focusPrice.negotiatedLow, focusPrice.negotiatedHigh)}
                    {focusPrice.payerCount ? ` across ${focusPrice.payerCount} payer rates` : ""}
                  </dd>
                )}
              </div>
              {focusPrice.grossCharge != null && (
                <div>
                  <dt className="text-xs font-medium uppercase text-slate-500">
                    Gross charge (list price, rarely paid)
                  </dt>
                  <dd className="font-semibold">{formatCurrency(focusPrice.grossCharge)}</dd>
                </div>
              )}
            </dl>
            <p className="mt-3 text-sm text-slate-600">
              What you pay with insurance depends on your plan&apos;s deductible and coinsurance;
              ask your insurer for an estimate using the codes below.
            </p>
            </>
          ) : (
            <p className="mt-2 text-sm text-slate-600">
              This hospital&apos;s price file has no figure we could verify for this procedure. We don&apos;t
              estimate one.
            </p>
          )}
          {focusPrice && (
            <p className="mt-3 text-xs text-slate-500 [overflow-wrap:anywhere]">
              {focusPrice.scope ? `${SCOPE_LABEL[focusPrice.scope]} · ` : ""}
              {focusPrice.matchedCodes?.length ? `Codes ${focusPrice.matchedCodes.join(", ")} · ` : ""}
              {focusProcedure.codeNote ? `${focusProcedure.codeNote} · ` : ""}
              Published {focusPrice.priceVintage}
              {focusPrice.stale ? " (over 18 months old)" : ""} · Source:{" "}
              {priceSourceLabel(focusPrice.priceSource)}
              {focusPrice.mrfUrl && (
                <>
                  {" · "}
                  <a href={focusPrice.mrfUrl} target="_blank" rel="noopener noreferrer" className="text-teal-700 hover:underline">
                    hospital&apos;s price file
                  </a>
                </>
              )}
            </p>
          )}
        </section>
      )}

      <section className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">All procedures</h2>
        <div className="mt-4 overflow-x-auto [-webkit-overflow-scrolling:touch]">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <th className="py-2 pr-4">Procedure</th>
                <th className="py-2 pr-4">Cash price</th>
                <th className="py-2 pr-4">Negotiated median</th>
                <th className="py-2">Published</th>
              </tr>
            </thead>
            <tbody>
              {allPrices.map((pr) => {
                const proc = procedures.find((p) => p.id === pr.procedureId);
                if (!proc) return null;
                return (
                  <tr key={pr.procedureId} className="border-b border-slate-100">
                    <td className="py-3 pr-4 font-medium">{proc.plainName}</td>
                    <td className="py-3 pr-4">{formatCurrency(pr.cashMedian)}</td>
                    <td className="py-3 pr-4">{formatCurrency(pr.negotiatedMedian)}</td>
                    <td className="py-3 text-xs text-slate-500">
                      {pr.priceVintage}
                      {pr.stale ? " (old)" : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-8 flex flex-wrap gap-3">
        {hospital.shoppableUrl && (
          <a
            href={hospital.shoppableUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-700"
          >
            Hospital&apos;s own price tool
          </a>
        )}
        {hospital.website && (
          <a
            href={hospital.website}
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Hospital website
          </a>
        )}
      </section>
    </div>
  );
}