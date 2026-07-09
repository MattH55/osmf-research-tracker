export function StarRating({ stars }: { stars: number | null }) {
  if (stars == null) {
    return (
      <span className="text-sm text-slate-500" aria-label="Not rated">
        Not rated
      </span>
    );
  }
  const full = Math.round(stars);
  return (
    <div className="flex items-center gap-1" aria-label={`${stars} out of 5 stars`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span
          key={i}
          className={i < full ? "text-amber-500" : "text-slate-300"}
          aria-hidden
        >
          ★
        </span>
      ))}
      <span className="ml-1 text-sm font-medium text-slate-700">{stars.toFixed(1)}</span>
    </div>
  );
}