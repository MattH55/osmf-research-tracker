import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold text-slate-900">
          <span
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-600 text-sm font-bold text-white"
            aria-hidden
          >
            HR
          </span>
          <span>
            Hospital<span className="text-teal-700">Compare</span>
          </span>
        </Link>
        <nav className="flex items-center gap-1 text-sm" aria-label="Main">
          <Link
            href="/search?procedure=knee-replacement&zip=10016"
            className="rounded-md px-3 py-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            Search
          </Link>
          <Link
            href="/about"
            className="rounded-md px-3 py-2 text-slate-600 hover:bg-slate-100 hover:text-slate-900"
          >
            About &amp; data
          </Link>
        </nav>
      </div>
    </header>
  );
}