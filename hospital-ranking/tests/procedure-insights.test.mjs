import test from 'node:test';
import assert from 'node:assert/strict';
import { buildPriceHistogram, summarizeStateCoverage } from '../src/lib/procedure-insights.js';

test('buildPriceHistogram trims the bottom and top 5% before plotting', () => {
  const histogram = buildPriceHistogram([100, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220]);

  assert.equal(histogram.count, 10);
  assert.equal(histogram.trimmedMin, 120);
  assert.equal(histogram.trimmedMax, 210);
  assert.equal(histogram.bins.length, 4);
  assert.equal(histogram.bins[0].label, '$120-$150');
});

test('summarizeStateCoverage counts sites by state for a procedure', () => {
  const coverage = summarizeStateCoverage([
    { id: 'a', state: 'CA', price: { cashMedian: 100 } },
    { id: 'b', state: 'CA', price: { cashMedian: 110 } },
    { id: 'c', state: 'TX', price: { cashMedian: 120 } },
  ], 'proc-1');

  assert.deepEqual(coverage, [
    { state: 'CA', count: 2 },
    { state: 'TX', count: 1 },
  ]);
});
