import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex min-h-14 max-w-6xl items-center justify-between gap-2 px-4 py-2 sm:px-6">
        <Link href="/" className="flex min-w-0 items-center gap-2 font-semibold text-slate-900">
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-teal-600 text-sm font-bold text-white"
            aria-hidden
          >
            HR
          </span>
          <span className="truncate text-sm sm:text-base">
            Hospital<span className="text-teal-700">Compare</span>
          </span>
        </Link>
        <nav className="flex shrink-0 items-center gap-0.5 text-xs sm:gap-1 sm:text-sm" aria-label="Main">
          <Link
            href="/search?procedure=knee-replacement&zip=10016"
            className="rounded-md px-2 py-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900 sm:px-3"
          >
            Search
          </Link>
          <Link
            href="/about"
            className="rounded-md px-2 py-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900 sm:px-3"
          >
            About &amp; data
          </Link>
        </nav>
      </div>
    </header>
  );
}