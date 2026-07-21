import { getHospitals, getPrice, getPricesForProcedure } from "@/lib/data";
import { formatCurrency } from "@/lib/format";
import { buildPriceHistogram, summarizeStateCoverage } from "@/lib/procedure-insights";
import type { Procedure } from "@/lib/types";

const HISTOGRAM_WHITELIST = new Set([
  "proc-chest-xray",
  "proc-ct-abdomen",
  "proc-mri-brain",
  "proc-mri-lumbar",
  "proc-mri-knee",
  "proc-mammogram",
  "proc-upper-endoscopy",
  "proc-colonoscopy",
  "proc-breast-biopsy",
  "proc-hernia",
  "proc-knee-arthroscopy",
  "proc-rotator-cuff",
  "proc-cataract",
]);

export function ProcedureInsights({ procedure }: { procedure: Procedure }) {
  const allowHistogram = HISTOGRAM_WHITELIST.has(procedure.id);
  const reportedPrices = getPricesForProcedure(procedure.id)
    .map((price) => price.cashMedian ?? price.negotiatedMedian ?? null)
    .filter((value): value is number => value != null);

  const histogram = buildPriceHistogram(reportedPrices);
  const states = summarizeStateCoverage(
    getHospitals().map((hospital) => ({
      state: hospital.state,
      procedureId: procedure.id,
      price: getPrice(hospital.id, procedure.id),
    })),
    procedure.id,
  );

  const totalSites = states.reduce((sum, state) => sum + state.count, 0);

  return (
    <div className={`grid gap-4 ${allowHistogram ? "lg:grid-cols-[1.2fr_0.8fr]" : "lg:grid-cols-1"}`}>
      {allowHistogram ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Price distribution</h3>
              <p className="text-xs text-slate-500">
                Trimmed to remove the bottom and top 5% of reported prices
              </p>
            </div>
            <span className="rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-600 shadow-sm">
              {histogram.count} reported sites
            </span>
          </div>

          {histogram.bins.length === 0 ? (
            <p className="mt-4 text-sm text-slate-600">
              We do not have enough reported prices yet for a histogram.
            </p>
          ) : (
            <div className="mt-4 space-y-3">
              {histogram.bins.map((bin) => {
                const height = histogram.maxCount > 0 ? (bin.count / histogram.maxCount) * 100 : 0;
                return (
                  <div key={bin.label} className="flex items-center gap-3">
                    <div className="w-20 text-sm font-medium text-slate-600">{bin.label}</div>
                    <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-200">
                      <div
                        className="h-full rounded-full bg-teal-600"
                        style={{ width: `${Math.max(10, height)}%` }}
                      />
                    </div>
                    <div className="w-12 text-right text-sm text-slate-600">{bin.count}</div>
                  </div>
                );
              })}
            </div>
          )}

          {histogram.trimmedMin != null && histogram.trimmedMax != null ? (
            <p className="mt-4 text-sm text-slate-600">
              Typical reported range after trimming: {formatCurrency(histogram.trimmedMin)} – {formatCurrency(histogram.trimmedMax)}
            </p>
          ) : null}
        </div>
      ) : null}

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-900">Availability by state</h3>
        <p className="mt-1 text-sm text-slate-600">
          {procedure.plainName} is currently reported at {totalSites} site{totalSites === 1 ? "" : "s"} across {states.length} state{states.length === 1 ? "" : "s"}.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {states.map((state) => (
            <div
              key={state.state}
              className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm"
            >
              <div className="font-semibold text-slate-900">{state.state}</div>
              <div className="text-slate-600">{state.count} site{state.count === 1 ? "" : "s"}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
