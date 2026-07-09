import Link from "next/link";
import { getTourismEstimates } from "@/lib/medical-tourism";
import { formatCurrency, formatPriceRange } from "@/lib/format";
import type { Procedure } from "@/lib/types";

export function MedicalTourismPanel({
  procedure,
  usBaseline,
}: {
  procedure: Procedure;
  usBaseline?: number;
}) {
  const estimates = getTourismEstimates(procedure.id, { usBaseline });
  if (!estimates.length) return null;

  const baseline = estimates[0].usReferenceMedian;
  const baselineLabel = usBaseline
    ? "median near you"
    : "U.S. national median";

  return (
    <section
      className="rounded-xl border border-indigo-200 bg-gradient-to-br from-indigo-50/80 to-white p-5 shadow-sm"
      aria-labelledby="medical-tourism-heading"
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-indigo-700">
            Medical tourism
          </p>
          <h2
            id="medical-tourism-heading"
            className="mt-1 text-lg font-semibold text-slate-900"
          >
            {procedure.plainName} abroad — estimated packages
          </h2>
          <p className="mt-1 text-sm text-slate-600">
            Compare typical all-inclusive cash packages in popular destinations.
            Savings vs. {formatCurrency(baseline)} {baselineLabel}.
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-800">
          Clinic links coming soon
        </span>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[520px] text-left text-sm">
          <thead>
            <tr className="border-b border-indigo-100 text-xs uppercase tracking-wide text-slate-500">
              <th className="pb-2 pr-4 font-medium">Destination</th>
              <th className="pb-2 pr-4 font-medium">Est. package</th>
              <th className="pb-2 pr-4 font-medium">Range</th>
              <th className="pb-2 font-medium">vs. U.S.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-indigo-50">
            {estimates.map((est) => (
              <tr key={est.destinationId} className="text-slate-800">
                <td className="py-3 pr-4">
                  <span className="mr-1.5" aria-hidden>
                    {est.destination.flagEmoji}
                  </span>
                  <span className="font-medium">{est.destination.country}</span>
                  <p className="mt-0.5 text-xs text-slate-500">
                    {est.destination.hubCities.slice(0, 2).join(", ")}
                    {est.destination.hubCities.length > 2 ? "…" : ""}
                  </p>
                </td>
                <td className="py-3 pr-4 font-semibold text-indigo-800">
                  {formatCurrency(est.cashMedian)}
                </td>
                <td className="py-3 pr-4 text-slate-600">
                  {formatPriceRange(est.cashLow, est.cashHigh)}
                </td>
                <td className="py-3">
                  <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-800">
                    ~{est.savingsPercent}% less
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <details className="mt-4 text-sm text-slate-600">
        <summary className="cursor-pointer font-medium text-slate-700 hover:text-indigo-800">
          What&apos;s included · travel notes
        </summary>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Typically includes
            </p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {estimates[0].packageIncludes.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Usually excludes
            </p>
            <ul className="mt-1 list-disc space-y-0.5 pl-4">
              {estimates[0].packageExcludes.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
        <ul className="mt-3 space-y-2">
          {estimates.slice(0, 3).map((est) => (
            <li key={est.destinationId} className="text-xs">
              <strong>{est.destination.country}:</strong>{" "}
              {est.destination.travelFromUs}
            </li>
          ))}
        </ul>
      </details>

      <p className="mt-4 text-xs text-slate-500">
        <strong className="text-slate-600">Estimates only</strong> — not quotes from
        individual clinics. Verify credentials (e.g. JCI), language support, and
        follow-up care before traveling.{" "}
        <Link href="/about#medical-tourism" className="text-indigo-700 hover:underline">
          Methodology
        </Link>
      </p>
    </section>
  );
}