import { Disclaimer } from "@/components/disclaimer";
import {
  DATA_VINTAGE,
  getDataMeta,
  getHospitalCount,
  getMrfPriceMeta,
  getProcedures,
} from "@/lib/data";
import { ESTIMATE_METHODOLOGY } from "@/lib/pricing";

export const metadata = {
  title: "About & data sources",
};

export default function AboutPage() {
  const meta = getDataMeta();
  const hospitalCount = meta.hospitalCount ?? getHospitalCount();
  const procedures = getProcedures();
  const categories = [...new Set(procedures.map((p) => p.category))].sort();
  const mrfMeta = getMrfPriceMeta();

  return (
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6">
      <h1 className="text-3xl font-bold text-slate-900">About HospitalCompare</h1>
      <p className="mt-4 text-lg text-slate-600">
        A free, public tool to help U.S. patients compare hospital quality and shoppable
        procedure prices before scheduling elective care.
      </p>

      <Disclaimer />

      <section className="mt-10 space-y-6 text-slate-700">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Data sources</h2>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm">
            <li>
              <strong>Quality:</strong>{" "}
              <a
                href="https://data.cms.gov/provider-data/"
                className="text-teal-700 hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                CMS Provider Data Catalog
              </a>{" "}
              — Overall Hospital Quality Star Rating, readmissions, and safety measures for{" "}
              {hospitalCount.toLocaleString()} U.S. hospitals (vintage {DATA_VINTAGE}).
            </li>
            <li>
              <strong>Coverage:</strong> Acute care, critical access, children&apos;s,
              psychiatric, long-term, rural emergency, VA, and DoD facilities from CMS
              Hospital General Information.
            </li>
            <li>
              <strong>Prices:</strong> Hospital-reported charges from CMS-required{" "}
              <a
                href="https://www.cms.gov/priorities/key-initiatives/hospital-price-transparency"
                className="text-teal-700 hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Machine-Readable Files (MRF)
              </a>
              . Nationwide coverage via{" "}
              <a
                href="https://oria-data.trillianthealth.com/docs"
                className="text-teal-700 hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Trilliant Health ORIA
              </a>{" "}
              parsed DuckDB bulk ingest (
              <code className="text-xs">etl/ingest_trilliant.py</code>
              {mrfMeta.trilliantCount > 0
                ? ` — ${mrfMeta.trilliantCount.toLocaleString()} prices`
                : ""}
              ). Per-hospital direct scrape via <code className="text-xs">cms-hpt.txt</code> (
              <code className="text-xs">etl/ingest_mrf_prices.py</code>
              {mrfMeta.directCount > 0
                ? ` — ${mrfMeta.directCount.toLocaleString()} prices`
                : ""}
              ). We do <strong>not</strong> show modeled guesses unless{" "}
              <code className="text-xs">ALLOW_MODELED_ESTIMATES=1</code> is set.
            </li>
            <li>
              <strong>Procedures:</strong> {procedures.length} CMS-aligned shoppable services
              with CPT / DRG mapping across {categories.join(", ")}.
            </li>
          </ul>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">How prices are ingested</h2>
          <p className="mt-2 text-sm font-medium text-slate-800">
            Primary: Trilliant ORIA bulk dataset
          </p>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">
            <li>
              Download the consolidated DuckDB archive from{" "}
              <a
                href="https://oria.trillianthealth.com/full-data-download"
                className="text-teal-700 hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Oria Full Data Download
              </a>{" "}
              (free account) and place it under{" "}
              <code className="text-xs">data/trilliant/</code>
            </li>
            <li>
              Run{" "}
              <code className="text-xs">
                npm run ingest:trilliant -- --consolidated data/trilliant/consolidated.duckdb
              </code>{" "}
              — or use <code className="text-xs">--oria</code> to pull per-hospital parsed
              DuckDB files from the public directory
            </li>
            <li>
              Query <code className="text-xs">standard_charges</code> for our{" "}
              {procedures.length} CPT/DRG codes and match facilities to CMS hospitals by
              name, state, and ZIP
            </li>
            <li>
              Output <code className="text-xs">data/cms/trilliant-prices.json</code> with{" "}
              <code className="text-xs">priceSource: trilliant_mrf</code>
            </li>
          </ol>
          <p className="mt-4 text-sm font-medium text-slate-800">
            Supplemental: direct per-hospital MRF scrape
          </p>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-sm">
            <li>
              Fetch <code className="text-xs">cms-hpt.txt</code> from hospital domains
            </li>
            <li>Download each <code className="text-xs">mrf-url</code> and extract CPT/DRG</li>
            <li>
              Direct scrape wins when both sources have a price for the same hospital +
              procedure
            </li>
          </ol>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Deprecated: modeled estimates
          </h2>
          <p className="mt-2 text-sm">{ESTIMATE_METHODOLOGY.summary}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
            {ESTIMATE_METHODOLOGY.sources.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">Roadmap</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">
            <li>Run full Trilliant consolidated ingest for all ~5,000+ ORIA hospitals</li>
            <li>Automated CMS quality ETL (`etl/cms_quality.py`)</li>
            <li>PostgreSQL + PostGIS, Meilisearch procedure index</li>
            <li>Insurance plan selector for personalized OOP</li>
            <li>Maps view and procedure explainer guides</li>
          </ol>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">Legal & privacy</h2>
          <p className="mt-2 text-sm">
            We do not collect or store protected health information (PHI). Consult an
            attorney before production launch for terms of service and privacy policy.
            All figures are estimates — always confirm with your hospital and insurer.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">License</h2>
          <p className="mt-2 text-sm">MIT — see LICENSE in the repository.</p>
        </div>
      </section>
    </div>
  );
}