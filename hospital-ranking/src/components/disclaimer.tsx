export function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <aside
      role="note"
      className={
        compact
          ? "rounded-lg border border-amber-200/80 bg-amber-50 px-3 py-2 text-xs text-amber-950"
          : "rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
      }
    >
      <strong className="font-semibold">Hospital-published prices only.</strong> Every figure comes
      from a hospital&apos;s own CMS-required price file, with its date and source. Where a hospital
      publishes nothing we can verify, we show nothing; we never estimate. Your actual cost depends
      on your insurance and care, so confirm with the hospital and your insurer. Not medical
      advice; no personal data stored.
    </aside>
  );
}