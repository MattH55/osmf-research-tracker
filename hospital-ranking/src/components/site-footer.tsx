import { DATA_VINTAGE, getDataMeta, getHospitalCount } from "@/lib/data";

export function SiteFooter() {
  const meta = getDataMeta();
  const hospitalCount = meta.hospitalCount ?? getHospitalCount();

  return (
    <footer className="mt-auto border-t border-slate-200 bg-slate-50">
      <div className="mx-auto max-w-6xl px-4 py-8 text-sm text-slate-600 sm:px-6">
        <p className="font-medium text-slate-800">HospitalCompare — free &amp; public</p>
        <p className="mt-2 max-w-2xl">
          Compare CMS hospital quality ratings across {hospitalCount.toLocaleString()} U.S.
          hospitals with shoppable procedure price estimates. Quality data vintage:{" "}
          {DATA_VINTAGE}. MIT licensed — contributions welcome.
        </p>
        <p className="mt-4 text-xs text-slate-500">
          © {new Date().getFullYear()} Open Source Medicine Foundation · Not medical or legal advice
        </p>
      </div>
    </footer>
  );
}