"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { matchProcedures, resolveProcedureSlug } from "@/lib/procedure-match";
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
  const listboxId = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  const initialProc = procedures.find(
    (p) => p.slug === defaultProcedure || p.plainName.toLowerCase() === defaultProcedure.toLowerCase(),
  );

  const [query, setQuery] = useState(initialProc?.plainName ?? defaultProcedure);
  const [zip, setZip] = useState(defaultZip);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);

  const suggestions = matchProcedures(query, procedures).slice(0, 10);
  const showList = open && suggestions.length > 0;

  const selectProcedure = useCallback((p: Procedure) => {
    setQuery(p.plainName);
    setOpen(false);
    setActiveIndex(-1);
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const slug = resolveProcedureSlug(query, procedures);
    const params = new URLSearchParams({
      procedure: slug,
      zip: zip.replace(/\D/g, "").slice(0, 5),
    });
    router.push(`/search?${params.toString()}`);
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!showList) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        setOpen(true);
        setActiveIndex(0);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      selectProcedure(suggestions[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  useEffect(() => {
    setActiveIndex(-1);
  }, [query]);

  return (
    <form onSubmit={submit} className="space-y-4" role="search" aria-label="Find hospitals">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="relative">
          <label htmlFor="procedure" className="mb-1.5 block text-sm font-medium text-slate-700">
            Procedure
          </label>
          <input
            ref={inputRef}
            id="procedure"
            name="procedure"
            type="search"
            autoComplete="off"
            role="combobox"
            aria-expanded={showList}
            aria-controls={listboxId}
            aria-autocomplete="list"
            aria-activedescendant={
              activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined
            }
            required
            placeholder="Start typing: knee, mammogram, C-section, 27447…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            onKeyDown={onKeyDown}
            className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-teal-500 focus:outline-none focus:ring-2 focus:ring-teal-500/20"
          />
          {showList && (
            <ul
              id={listboxId}
              className="absolute z-10 mt-1 max-h-56 w-full overflow-auto rounded-lg border border-slate-200 bg-white py-1 shadow-lg"
              role="listbox"
            >
              {suggestions.map((p, i) => (
                <li
                  key={p.id}
                  id={`${listboxId}-opt-${i}`}
                  role="option"
                  aria-selected={i === activeIndex}
                >
                  <button
                    type="button"
                    className={`w-full px-4 py-2.5 text-left text-sm ${
                      i === activeIndex ? "bg-teal-50" : "hover:bg-teal-50"
                    }`}
                    onMouseDown={() => selectProcedure(p)}
                    onMouseEnter={() => setActiveIndex(i)}
                  >
                    <span className="font-medium text-slate-900">{p.plainName}</span>
                    <span className="ml-2 text-slate-500">{p.category}</span>
                    {p.cptCodes.length > 0 && (
                      <span className="mt-0.5 block text-xs text-slate-400">
                        CPT {p.cptCodes.join(", ")}
                      </span>
                    )}
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