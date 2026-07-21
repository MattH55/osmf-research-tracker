/**
 * @typedef {{label: string, min: number, max: number, count: number}} HistogramBin
 * @typedef {{count: number, trimmedMin: number | null, trimmedMax: number | null, bins: HistogramBin[], maxCount: number}} PriceHistogram
 */

/**
 * Build a trimmed histogram for reported procedure prices.
 * @param {Array<number | null | undefined>} prices
 * @returns {PriceHistogram}
 */
export function buildPriceHistogram(prices) {
  const values = prices
    .filter((price) => typeof price === "number" && Number.isFinite(price))
    .map((price) => price)
    .sort((a, b) => a - b);

  if (values.length === 0) {
    return {
      count: 0,
      trimmedMin: null,
      trimmedMax: null,
      bins: [],
      maxCount: 0,
    };
  }

  const trimCount = Math.max(1, Math.floor(values.length * 0.05));
  const trimmedValues = values.length > trimCount * 2
    ? values.slice(trimCount, values.length - trimCount)
    : values;

  if (trimmedValues.length === 0) {
    return {
      count: 0,
      trimmedMin: null,
      trimmedMax: null,
      bins: [],
      maxCount: 0,
    };
  }

  const min = trimmedValues[0];
  const max = trimmedValues[trimmedValues.length - 1];
  const range = max - min || 1;
  const binCount = Math.min(6, Math.max(4, Math.ceil(trimmedValues.length / 3)));
  const step = range / binCount;
  const bins = Array.from({ length: binCount }, (_, index) => {
    const low = min + index * step;
    const high = index === binCount - 1 ? max : min + (index + 1) * step;
    return {
      label: `$${Math.round(low)}-$${Math.round(high)}`,
      min: low,
      max: high,
      count: 0,
    };
  });

  for (const value of trimmedValues) {
    const index = Math.min(binCount - 1, Math.max(0, Math.floor((value - min) / (step || 1))));
    bins[index].count += 1;
  }

  const maxCount = Math.max(...bins.map((bin) => bin.count));

  return {
    count: trimmedValues.length,
    trimmedMin: min,
    trimmedMax: max,
    bins,
    maxCount,
  };
}

/**
 * Count the number of sites offering a procedure by state.
 * @param {Array<{ state?: string, procedureId?: string, price?: unknown }>} items
 * @param {string} procedureId
 * @returns {Array<{ state: string, count: number }>}
 */
export function summarizeStateCoverage(items, procedureId) {
  const counts = new Map();

  for (const item of items ?? []) {
    const state = item?.state?.trim().toUpperCase();
    if (!state) continue;

    const matchesProcedure = !procedureId || !item?.procedureId || item.procedureId === procedureId;
    if (!matchesProcedure || item?.price == null) continue;

    counts.set(state, (counts.get(state) ?? 0) + 1);
  }

  return Array.from(counts.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([state, count]) => ({ state, count }));
}
