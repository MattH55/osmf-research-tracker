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
      <strong className="font-semibold">Prices are estimates and reported charges.</strong> We show
      hospital-reported charges when available and modeled estimates for other hospitals
      when direct price data is missing. Verify all amounts with the hospital and
      your insurer. Not medical advice — no PHI stored.
    </aside>
  );
}