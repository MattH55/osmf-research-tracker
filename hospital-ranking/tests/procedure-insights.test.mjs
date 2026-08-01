import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPriceHistogram, summarizeStateCoverage } from '../src/lib/procedure-insights.js';

test('buildPriceHistogram trims the bottom and top 5% before plotting', () => {
  const histogram = buildPriceHistogram([100, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220]);

  assert.equal(histogram.count, 10);
  assert.equal(histogram.trimmedMin, 120);
  assert.equal(histogram.trimmedMax, 210);
  assert.equal(histogram.bins.length, 4);
  // Verify all bins are within trimmed range
  for (const bin of histogram.bins) {
    assert.ok(bin.min >= 120, `bin.min ${bin.min} should be >= 120`);
    assert.ok(bin.max <= 210, `bin.max ${bin.max} should be <= 210`);
    assert.ok(bin.count > 0, `bin count should be > 0`);
  }
  // Total count across bins should match
  const totalInBins = histogram.bins.reduce((sum, b) => sum + b.count, 0);
  assert.equal(totalInBins, histogram.count);
});

test('buildPriceHistogram handles empty input', () => {
  const histogram = buildPriceHistogram([]);
  assert.equal(histogram.count, 0);
  assert.equal(histogram.trimmedMin, null);
  assert.equal(histogram.trimmedMax, null);
  assert.equal(histogram.bins.length, 0);
  assert.equal(histogram.maxCount, 0);
});

test('buildPriceHistogram filters non-finite values', () => {
  // [NaN, Infinity, -Infinity, null, undefined] are all filtered out
  // 18 valid values → trimCount = max(1, floor(18*0.05)) = 1, removes 1 from each end → 16 remaining
  // After sorting: [100, 110, 120, ..., 270], slice(1, 17) = [110, 120, ..., 260]
  const histogram = buildPriceHistogram([
    100, 110, 120, 130, 140, 150, 160, 170, 180, 190,
    200, 210, 220, 230, 240, 250, 260, 270,
    NaN, Infinity, -Infinity, null, undefined
  ]);
  assert.equal(histogram.count, 16);
  assert.equal(histogram.trimmedMin, 110);
  assert.equal(histogram.trimmedMax, 260);
});

test('summarizeStateCoverage counts sites by state for a procedure', () => {
  const coverage = summarizeStateCoverage([
    { state: 'CA', price: { cashMedian: 100 } },
    { state: 'CA', price: { cashMedian: 110 } },
    { state: 'TX', price: { cashMedian: 120 } },
  ], 'proc-1');

  assert.deepEqual(coverage, [
    { state: 'CA', count: 2 },
    { state: 'TX', count: 1 },
  ]);
});

test('summarizeStateCoverage handles null/undefined input gracefully', () => {
  const coverage = summarizeStateCoverage(null, 'proc-1');
  assert.deepEqual(coverage, []);

  const coverage2 = summarizeStateCoverage(undefined, 'proc-1');
  assert.deepEqual(coverage2, []);
});

test('summarizeStateCoverage skips items without prices', () => {
  const coverage = summarizeStateCoverage([
    { state: 'CA', price: null },
    { state: 'CA', price: { cashMedian: 100 } },
    { state: 'TX' },
  ], 'proc-1');

  assert.deepEqual(coverage, [{ state: 'CA', count: 1 }]);
});