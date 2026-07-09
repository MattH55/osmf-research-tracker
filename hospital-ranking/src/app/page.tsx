import { Disclaimer } from "@/components/disclaimer";
import { SearchForm } from "@/components/search-form";
import { getDataMeta, getHospitalCount, getProcedures } from "@/lib/data";
import Link from "next/link";

const FEATURED = [
  { slug: "knee-replacement", zip: "10016", label: "Knee replacement · NYC" },
  { slug: "c-section", zip: "90210", label: "C-section · LA" },
  { slug: "mammogram", zip: "33139", label: "Mammogram · Miami" },
  { slug: "gallbladder-removal", zip: "78701", label: "Gallbladder · Austin" },
  { slug: "colonoscopy", zip: "77030", label: "Colonoscopy · Houston" },
  { slug: "heart-bypass", zip: "48202", label: "Heart bypass · Detroit" },
  { slug: "cataract-surgery", zip: "85054", label: "Cataract · Phoenix" },
  { slug: "mri-brain", zip: "60611", label: "Brain MRI · Chicago" },
];

export default function HomePage() {
  const procedures = getProcedures();
  const meta = getDataMeta();
  const hospitalCount = meta.hospitalCount ?? getHospitalCount();

  return (
    <div>
      <section className="border-b border-slate-200 bg-gradient-to-b from-teal-50 to-white px-4 py-16 sm:py-20">
        <div className="mx-auto max-w-3xl text-center">
          <p className="text-sm font-semibold uppercase tracking-wider text-teal-700">
            Free · Public · Patient-first
          </p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl lg:text-5xl">
            Shop smarter for hospital care
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-lg text-slate-600">
            Compare CMS quality ratings across{" "}
            <span className="font-medium text-slate-800">
              {hospitalCount.toLocaleString()} U.S. hospitals
            </span>{" "}
            with cash and insured price estimates for{" "}
            <span className="font-medium text-slate-800">
              {procedures.length} shoppable procedures
            </span>{" "}
            — all in plain language.
          </p>
        </div>
        <div className="mx-auto mt-10 max-w-2xl rounded-2xl border border-slate-200 bg-white p-6 shadow-lg sm:p-8">
          <SearchForm procedures={procedures} />
        </div>
        <div className="mx-auto mt-6 max-w-2xl">
          <Disclaimer compact />
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <h2 className="text-lg font-semibold text-slate-900">Try a quick search</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {FEATURED.map((f) => (
            <Link
              key={f.slug}
              href={`/search?procedure=${f.slug}&zip=${f.zip}`}
              className="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm hover:border-teal-300 hover:text-teal-800"
            >
              {f.label}
            </Link>
          ))}
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-3">
          {[
            {
              title: "Quality you can trust",
              body: "CMS Overall Star Ratings, patient experience (HCAHPS), and readmission rates — sourced from Medicare.gov.",
            },
            {
              title: "Prices that make sense",
              body: "Cash medians, negotiated ranges, and rough out-of-pocket estimates for shoppable services.",
            },
            {
              title: "Built for real decisions",
              body: "Filter by distance, stars, and budget. No account required. No PHI stored.",
            },
          ].map((card) => (
            <div
              key={card.title}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <h3 className="font-semibold text-slate-900">{card.title}</h3>
              <p className="mt-2 text-sm text-slate-600">{card.body}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}