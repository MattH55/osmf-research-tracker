import test from 'node:test';
import assert from 'node:assert/strict';
import { estimateProcedurePrice, getUsReferenceMedian, isReportedPrice, priceSourceLabel, hospitalJitter } from '../src/lib/pricing-logic.js';

test('estimateProcedurePrice returns complete ProcedurePrice with all required fields', () => {
  const hospital = {
    id: 'hosp-cms-12345',
    cmsProviderId: '12345',
    name: 'Test Hospital',
    state: 'CA',
    hospitalType: 'Acute Care Hospitals',
    ownership: 'Voluntary non-profit - Private',
    cmsOverallStars: 4,
    latitude: 34.0522,
    longitude: -118.2437,
  };

  const price = estimateProcedurePrice(hospital, 'proc-knee-replacement');
  assert.ok(price, 'estimate should return a price object');

  assert.ok(typeof price.hospitalId === 'string' && price.hospitalId.length > 0);
  assert.ok(typeof price.procedureId === 'string' && price.procedureId.length > 0);
  assert.ok(typeof price.cashLow === 'number' && price.cashLow > 0, `cashLow=${price.cashLow}`);
  assert.ok(typeof price.cashMedian === 'number' && price.cashMedian > 0, `cashMedian=${price.cashMedian}`);
  assert.ok(typeof price.cashHigh === 'number' && price.cashHigh > 0, `cashHigh=${price.cashHigh}`);
  assert.ok(typeof price.negotiatedMedian === 'number' && price.negotiatedMedian > 0);
  assert.ok(typeof price.priceSource === 'string' && price.priceSource.length > 0);
  assert.ok(typeof price.priceVintage === 'string' && price.priceVintage.length > 0);

  assert.ok(price.cashLow < price.cashMedian, `${price.cashLow} < ${price.cashMedian}`);
  assert.ok(price.cashMedian < price.cashHigh, `${price.cashMedian} < ${price.cashHigh}`);
  assert.ok(price.negotiatedMedian < price.cashMedian);
});

test('estimateProcedurePrice returns undefined for unknown procedure', () => {
  const hospital = {
    id: 'hosp-x',
    cmsProviderId: 'x',
    name: 'X',
    state: 'CA',
    latitude: 34,
    longitude: -118,
  };
  assert.equal(estimateProcedurePrice(hospital, 'nonexistent'), undefined);
});

test('estimateProcedurePrice varies by state cost index (CA > TX)', () => {
  const caH = { id: 'ca-h', cmsProviderId: 'ca-1', name: 'CA', state: 'CA', latitude: 34, longitude: -118 };
  const txH = { id: 'tx-h', cmsProviderId: 'tx-1', name: 'TX', state: 'TX', latitude: 32.7, longitude: -96.8 };
  const caP = estimateProcedurePrice(caH, 'proc-knee-replacement');
  const txP = estimateProcedurePrice(txH, 'proc-knee-replacement');
  assert.ok(caP && txP, 'both prices should be defined');
  // CA has higher cost index (1.32) than TX (0.98)
  assert.ok(caP.cashMedian > txP.cashMedian, `CA (${caP.cashMedian}) should exceed TX (${txP.cashMedian})`);
});

test('estimateProcedurePrice applies hospital type modifier', () => {
  const acuteH = { id: 'acute-h', cmsProviderId: 'a-1', name: 'Acute', state: 'TX', hospitalType: 'Acute Care Hospitals', latitude: 32.7, longitude: -96.8 };
  const caH = { id: 'ca-hosp', cmsProviderId: 'ca-1', name: 'Critical Access', state: 'TX', hospitalType: 'Critical Access Hospitals', latitude: 32.7, longitude: -96.8 };
  const acuteP = estimateProcedurePrice(acuteH, 'proc-knee-replacement');
  const caP = estimateProcedurePrice(caH, 'proc-knee-replacement');
  assert.ok(acuteP && caP);
  // Critical Access Hospitals have 0.74x multiplier vs 1.0x for Acute Care
  assert.ok(caP.cashMedian < acuteP.cashMedian, `CA (${caP.cashMedian}) < acute (${acuteP.cashMedian})`);
});

test('estimateProcedurePrice applies ownership modifier', () => {
  const propH = { id: 'prop-h', cmsProviderId: 'p-1', name: 'Proprietary', state: 'TX', ownership: 'Proprietary', latitude: 32.7, longitude: -96.8 };
  const npH = { id: 'np-h', cmsProviderId: 'n-1', name: 'Nonprofit', state: 'TX', ownership: 'Voluntary non-profit - Private', latitude: 32.7, longitude: -96.8 };
  const propP = estimateProcedurePrice(propH, 'proc-knee-replacement');
  const npP = estimateProcedurePrice(npH, 'proc-knee-replacement');
  assert.ok(propP && npP);
  // Proprietary has 1.06x vs 1.0x for nonprofit
  assert.ok(propP.cashMedian > npP.cashMedian);
});

test('estimateProcedurePrice applies stars modifier', () => {
  const star5 = { id: 'star5-h', cmsProviderId: 's5', name: '5-star', state: 'TX', cmsOverallStars: 5 };
  const star1 = { id: 'star1-h', cmsProviderId: 's1', name: '1-star', state: 'TX', cmsOverallStars: 1 };
  const p5 = estimateProcedurePrice(star5, 'proc-knee-replacement');
  const p1 = estimateProcedurePrice(star1, 'proc-knee-replacement');
  assert.ok(p5 && p1);
  // 5-star gets 1.06x, 1-star gets 0.92x
  assert.ok(p5.cashMedian > p1.cashMedian);
});

test('getUsReferenceMedian returns correct national medians', () => {
  assert.equal(getUsReferenceMedian('proc-knee-replacement'), 28500);
  assert.equal(getUsReferenceMedian('proc-hip-replacement'), 35200);
  assert.equal(getUsReferenceMedian('proc-cataract'), 3800);
  assert.equal(getUsReferenceMedian('proc-colonoscopy'), 1750);
  assert.equal(getUsReferenceMedian('nonexistent'), undefined);
});

test('isReportedPrice identifies MRF-sourced prices', () => {
  assert.equal(isReportedPrice({ priceSource: 'hospital_mrf', hospitalId: 'x', procedureId: 'y', cashLow: null, cashMedian: null, cashHigh: null }), true);
  assert.equal(isReportedPrice({ priceSource: 'trilliant_mrf', hospitalId: 'x', procedureId: 'y', cashLow: null, cashMedian: null, cashHigh: null }), true);
  assert.equal(isReportedPrice({ priceSource: 'sample_mrf', hospitalId: 'x', procedureId: 'y', cashLow: null, cashMedian: null, cashHigh: null }), true);
  assert.equal(isReportedPrice({ priceSource: 'estimated', hospitalId: 'x', procedureId: 'y', cashLow: null, cashMedian: null, cashHigh: null }), false);
  assert.equal(isReportedPrice({ priceSource: 'unknown', hospitalId: 'x', procedureId: 'y', cashLow: null, cashMedian: null, cashHigh: null }), false);
});

test('priceSourceLabel returns human-readable labels', () => {
  assert.equal(priceSourceLabel('hospital_mrf'), 'Hospital MRF (published)');
  assert.equal(priceSourceLabel('trilliant_mrf'), 'Hospital MRF (Trilliant ORIA)');
  assert.equal(priceSourceLabel('sample_mrf'), 'Hospital MRF (sample)');
  assert.equal(priceSourceLabel('estimated'), 'Modeled estimate (not hospital-reported)');
  assert.equal(priceSourceLabel('custom_source'), 'custom_source');
});

test('hospital jitter is deterministic (same ID always same value)', () => {
  const j1 = hospitalJitter('hosp-deterministic');
  const j2 = hospitalJitter('hosp-deterministic');
  assert.equal(j1, j2);
  // Jitter formula: 0.94 + (hash % 13) / 100 produces values in [0.94, 1.06]
  // When hash%13=12, result is exactly 1.06, so upper bound is inclusive
  assert.ok(j1 >= 0.94 && j1 <= 1.06, `jitter ${j1} should be in [0.94, 1.06]`);
});

test('different hospitals produce different jitter values', () => {
  const j1 = hospitalJitter('hosp-a');
  const j2 = hospitalJitter('hosp-b');
  assert.notEqual(j1, j2, 'different IDs should produce different jitter');
});

test('national medians cover all expected procedures', () => {
  const expectedProcedures = [
    'proc-knee-replacement', 'proc-hip-replacement', 'proc-cataract',
    'proc-colonoscopy', 'proc-appendectomy', 'proc-cholecystectomy',
    'proc-cabg', 'proc-cardiac-cath', 'proc-mri-brain', 'proc-mammogram',
  ];
  for (const proc of expectedProcedures) {
    const median = getUsReferenceMedian(proc);
    assert.ok(median != null && median > 0, `${proc} should have a valid median: ${median}`);
  }
});

test('USD prices: cashMedian equals oopUninsured (fx_rate = 1.0)', () => {
  const h = { id: 'usd-test', cmsProviderId: 'u-1', name: 'US', state: 'CA', latitude: 34, longitude: -118 };
  const price = estimateProcedurePrice(h, 'proc-knee-replacement');
  assert.equal(price.cashMedian, price.oopUninsured);
});

test('price ratios match benchmark OOP ratios', () => {
  const h = { id: 'ratio-test', cmsProviderId: 'r-1', name: 'Ratio', state: 'TX', latitude: 32.7, longitude: -96.8 };
  const price = estimateProcedurePrice(h, 'proc-knee-replacement');
  assert.ok(price);
  // oopPpo should be ~15% of cashMedian
  const ppoRatio = price.oopPpo / price.cashMedian;
  assert.ok(ppoRatio > 0.14 && ppoRatio < 0.16, `PPO ratio ${ppoRatio} should be ~0.15`);
  // oopHdhp should be ~22% of cashMedian
  const hdhpRatio = price.oopHdhp / price.cashMedian;
  assert.ok(hdhpRatio > 0.21 && hdhpRatio < 0.23, `HDHP ratio ${hdhpRatio} should be ~0.22`);
});