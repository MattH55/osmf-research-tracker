"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

export function SearchPagination({
  total,
  limit,
  offset,
}: {
  total: number;
  limit: number;
  offset: number;
}) {
  const params = useSearchParams();
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const start = total === 0 ? 0 : offset + 1;
  const end = Math.min(offset + limit, total);

  if (total <= limit) return null;

  function pageHref(page: number) {
    const next = new URLSearchParams(params.toString());
    if (page <= 1) next.delete("page");
    else next.set("page", String(page));
    const qs = next.toString();
    return qs ? `/search?${qs}` : "/search";
  }

  const prevPage = currentPage > 1 ? currentPage - 1 : null;
  const nextPage = currentPage < totalPages ? currentPage + 1 : null;

  return (
    <nav
      className="flex flex-col items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-4 sm:flex-row sm:justify-between"
      aria-label="Result pages"
    >
      <p className="text-sm text-slate-600">
        Showing <span className="font-medium text-slate-800">{start}–{end}</span> of{" "}
        <span className="font-medium text-slate-800">{total}</span> facilities
      </p>
      <div className="flex items-center gap-2">
        {prevPage ? (
          <Link
            href={pageHref(prevPage)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            ← Previous
          </Link>
        ) : (
          <span className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-400">
            ← Previous
          </span>
        )}
        <span className="px-2 text-sm text-slate-600">
          Page {currentPage} of {totalPages}
        </span>
        {nextPage ? (
          <Link
            href={pageHref(nextPage)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Next →
          </Link>
        ) : (
          <span className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-400">
            Next →
          </span>
        )}
      </div>
    </nav>
  );
}