"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Procedure } from "@/lib/types";

export function SearchForm({
  procedures,
  defaultProcedure = "",
  defaultZip = "",
}: {
  procedures: Procedure[];
  defaultProcedure?: string;
  defaultZip?: string;
}) {
  const router = useRouter();
  const [procedure, setProcedure] = useState(defaultProcedure);
  const [zip, setZip] = useState(defaultZip);
  const [open, setOpen] = useState(false);

  const filtered = procedures.filter((p) => {
    const q = procedure.toLowerCase();
    if (!q) return true;
    return (
      p.plainName.toLowerCase().includes(q) ||
      p.slug.includes(q) ||
      p.searchTerms.some((t) => t.toLowerCase().includes(q))
    );
  });

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const slug =
      procedures.find(
        (p) =>
          p.slug === procedure ||
          p.plainName.toLowerCase() === procedure.toLowerCase(),
      )?.slug ?? procedure.trim().toLowerCase().replace(/\s+/g, "-");
    const params = new URLSearchParams({
      procedure: slug,
      zip: zip.replace(/\D/g, "").slice(0, 5),
    });
    router.push(`/search?${params.toString()}`);
  }

  return (
    <form onSubmit={submit} className="space-y-4" role="search" aria-label="Find hospitals">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="relative">
          <label htmlFor="procedure" className="mb-1.5 block text-sm font-medium text-slate-700">
            Procedure
          </label>
          <input
            id="procedure"
            name="procedure"
            type="text"
            autoComplete="off"
            required
            placeholder="e.g. knee replacement, colonoscopy"
            value={procedure}
            onChange={(e) => {
              setProcedure(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
            list="procedure-list"
          />
          <datalist id="procedure-list">
            {procedures.map((p) => (
              <option key={p.id} value={p.plainName} />
            ))}
          </datalist>
          {open && filtered.length > 0 && procedure.length > 0 && (
            <ul
              className="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
              role="listbox"
            >
              {filtered.slice(0, 6).map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className="w-full px-4 py-2 text-left text-sm hover:bg-teal-50"
                    onMouseDown={() => {
                      setProcedure(p.plainName);
                      setOpen(false);
                    }}
                  >
                    <span className="font-medium">{p.plainName}</span>
                    <span className="ml-2 text-slate-500">{p.category}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <label htmlFor="zip" className="mb-1.5 block text-sm font-medium text-slate-700">
            Your ZIP code
          </label>
          <input
            id="zip"
            name="zip"
            type="text"
            inputMode="numeric"
            pattern="[0-9]{5}"
            maxLength={5}
            required
            placeholder="e.g. 10016"
            value={zip}
            onChange={(e) => setZip(e.target.value)}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
        </div>
      </div>
      <button
        type="submit"
        className="w-full rounded-lg bg-teal-600 px-6 py-3.5 text-base font-semibold text-white shadow-sm transition hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-teal-500 focus:ring-offset-2 sm:w-auto"
      >
        Compare hospitals near me
      </button>
    </form>
  );
}