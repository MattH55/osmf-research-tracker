import { Disclaimer } from "@/components/disclaimer";
import {
  DATA_VINTAGE,
  getDataMeta,
  getHospitalCount,
  getMrfPriceMeta,
  getProcedures,
} from "@/lib/data";
import { PRICE_CEILING, STALE_MONTHS } from "@/lib/pricing";

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
    <div className="mx-auto max-w-3xl px-4 py-10 sm:px-6 [overflow-wrap:anywhere]">
      <h1 className="text-2xl font-bold text-slate-900 sm:text-3xl">About HospitalCompare</h1>
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
              — Overall Hospital Quality Star Rating and the share of readmission and mortality
              measures on which each hospital is worse than the U.S. rate, for{" "}
              {hospitalCount.toLocaleString()} U.S. hospitals (CMS release {DATA_VINTAGE}).
            </li>
            <li>
              <strong>Coverage:</strong> Acute care, critical access, children&apos;s,
              psychiatric, long-term, rural emergency, VA, and DoD facilities from CMS
              Hospital General Information.
            </li>
            <li>
              <strong>Prices:</strong> Reported charges from CMS-required{" "}
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
                ? ` — ${mrfMeta.trilliantCount.toLocaleString()} prices (growing via ORIA batch ingest; ~7,600 hospitals in source)`
                : ""}
              ). Per-hospital direct scrape via <code className="text-xs">cms-hpt.txt</code> (
              <code className="text-xs">etl/ingest_mrf_prices.py</code>
              {mrfMeta.directCount > 0
                ? ` — ${mrfMeta.directCount.toLocaleString()} prices`
                : ""}
              ). Nothing is modelled: a hospital without a verifiable published figure shows none.
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
              {procedures.length} procedures&apos; codes (MS-DRG for inpatient stays, CPT/HCPCS for
              outpatient services, with the code type checked) and match each file to a CMS
              hospital by CMS certification number, or by exact name and location; uncertain
              matches are discarded, not guessed
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

        <div id="what-we-exclude">
          <h2 className="text-xl font-semibold text-slate-900">What we leave out, and why</h2>
          <p className="mt-2 text-sm">
            A price is shown only if it passes every check below. Rows that fail are set aside
            with the reason recorded (<code className="text-xs">data/cms/quarantine.json</code>),
            and the build fails if one slips through.
          </p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">
            <li>The billing code must be labelled with its code system (a bare &ldquo;470&rdquo; could be an MS-DRG, an APR-DRG or a revenue code).</li>
            <li>Each procedure is priced at one scope only, so figures are comparable: the whole inpatient stay (MS-DRG) or the hospital&apos;s facility fee for an outpatient service. Physician-only fees are excluded.</li>
            <li>Cash, negotiated and gross (list) prices are kept separate; a list price is never shown as a cash price.</li>
            <li>Values of zero or less, at or above {PRICE_CEILING.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 })} (placeholder values like 999,999,999), or too low to be the whole service are excluded.</li>
            <li>The price must carry the date from the hospital&apos;s file; figures more than {STALE_MONTHS} months older than the dataset are flagged.</li>
            <li>The file must match the hospital, and the procedure must fit the hospital type (no surgery prices on psychiatric hospitals).</li>
          </ul>
          {mrfMeta.rejectedCount > 0 && (
            <p className="mt-2 text-sm text-amber-800">
              {mrfMeta.rejectedCount} row(s) failed these checks at load time and are hidden.
            </p>
          )}
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">What this tool can&apos;t tell you</h2>
          <p className="mt-2 text-sm">
            Your own cost with insurance depends on your plan&apos;s deductible, coinsurance and
            network, and on the care you actually receive. We show what the hospital publishes:
            its cash price and the range of rates it negotiated with insurers. Ask your insurer for
            an estimate using the codes shown on each hospital page.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">Locations</h2>
          <p className="mt-2 text-sm">
            ZIP codes are located with the U.S. Census Bureau&apos;s ZIP Code Tabulation Areas
            (Gazetteer). Hospitals are placed by geocoding their CMS street address with the Census
            geocoder, or at their ZIP&apos;s point when the address doesn&apos;t match.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">Privacy</h2>
          <p className="mt-2 text-sm">
            We do not collect or store protected health information. Always confirm prices with
            the hospital and your insurer before care.
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