// Runs against the real src/lib/pricing.ts (Node strips the type annotations).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { headlinePrice, isReportedPrice, priceFloor, PRICE_CEILING } from '../src/lib/pricing.ts';

const row = (over = {}) => ({
  hospitalId: 'hosp-cms-050441', procedureId: 'proc-mri-brain', cashLow: 900, cashMedian: 1000, cashHigh: 1200,
  negotiatedLow: 700, negotiatedMedian: 800, negotiatedHigh: 1500, priceSource: 'trilliant_mrf',
  priceVintage: '2026-01-01', scope: 'facility_service', ...over,
});

test('cash and uninsured users see only the published cash price', () => {
  assert.deepEqual(headlinePrice(row(), 'cash'), { amount: 1000, kind: 'cash' });
  assert.deepEqual(headlinePrice(row(), 'uninsured'), { amount: 1000, kind: 'cash' });
});

test('a missing cash price is never filled from the negotiated rate or gross charge', () => {
  assert.equal(headlinePrice(row({ cashMedian: null, grossCharge: 5000 }), 'cash'), null);
});

test('insured users see the negotiated median, labelled as such, never a modelled out-of-pocket', () => {
  assert.deepEqual(headlinePrice(row(), 'ppo'), { amount: 800, kind: 'negotiated' });
  assert.deepEqual(headlinePrice(row(), 'hdhp'), { amount: 800, kind: 'negotiated' });
  assert.equal(headlinePrice(row({ negotiatedMedian: null }), 'ppo'), null);
});

test('only hospital price files count as reported; there is no sample or estimate source', () => {
  assert.equal(isReportedPrice(row()), true);
  assert.equal(isReportedPrice(row({ priceSource: 'hospital_mrf' })), true);
  for (const s of ['sample_mrf', 'estimated', 'medical_tourism_estimate']) {
    assert.equal(isReportedPrice(row({ priceSource: s })), false, s);
  }
});

test('bounds reject sentinels and implausibly small whole-stay prices', () => {
  assert.ok(999_999_999 >= PRICE_CEILING);
  assert.ok(priceFloor('inpatient_stay') >= 1000);
  assert.ok(priceFloor('facility_service') > 0);
});

test('no estimator, out-of-pocket model or seed price data remains in the app source', () => {
  const files = [];
  const walk = (d) => {
    for (const e of readdirSync(d, { withFileTypes: true })) {
      const p = `${d}/${e.name}`;
      if (e.isDirectory()) walk(p);
      else if (/\.(ts|tsx|js)$/.test(e.name)) files.push(p);
    }
  };
  walk(fileURLToPath(new URL('../src', import.meta.url)));
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    for (const banned of ['estimateProcedurePrice', 'oopPpo', 'oopHdhp', 'estimatedOop', 'sample_mrf', 'seed/prices', 'seed/hospitals', 'isEstimate']) {
      assert.ok(!src.includes(banned), `${f} still references ${banned}`);
    }
  }
});
