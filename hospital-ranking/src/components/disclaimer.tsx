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
      <strong className="font-semibold">Estimates only.</strong> Most prices are modeled
      from national benchmarks; some hospitals show reported MRF sample data. Verify all
      prices and coverage with the hospital and your insurer. Not medical advice — no PHI
      stored.
    </aside>
  );
}