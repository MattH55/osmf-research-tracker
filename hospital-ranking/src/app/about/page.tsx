import { Disclaimer } from "@/components/disclaimer";
import {
  DATA_VINTAGE,
  getDataMeta,
  getHospitalCount,
  getProcedures,
  PRICE_VINTAGE,
} from "@/lib/data";

export const metadata = {
  title: "About & data sources",
};

export default function AboutPage() {
  const meta = getDataMeta();
  const hospitalCount = meta.hospitalCount ?? getHospitalCount();
  const procedures = getProcedures();
  const categories = [...new Set(procedures.map((p) => p.category))].sort();

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
              <strong>Prices:</strong> Hospital Machine-Readable Files (CMS Hospital Price
              Transparency) and/or structured partners such as{" "}
              <a
                href="https://turquoise.health"
                className="text-teal-700 hover:underline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Turquoise Health
              </a>
              . Most hospitals show quality only today; a small sample has illustrative
              prices ({PRICE_VINTAGE}) while MRF ingestion is built out.
            </li>
            <li>
              <strong>Procedures:</strong> {procedures.length} CMS-aligned shoppable services
              with CPT / DRG mapping across {categories.join(", ")}.
            </li>
          </ul>
        </div>

        <div>
          <h2 className="text-xl font-semibold text-slate-900">Roadmap</h2>
          <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm">
            <li>Automated CMS quality ETL (`etl/cms_quality.py`)</li>
            <li>Production MRF ingestion or Turquoise API</li>
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