// Data-contract tests over the REAL published price files (data/cms/*-prices.json).
// Mirrors etl/price_contract.py; `npm run validate:data` runs these before every build.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const readJson = (rel) => JSON.parse(readFileSync(path.join(ROOT, rel), 'utf8'));

const PRICE_CEILING = 500_000;
const SENTINELS = new Set([999999999, 99999999, 9999999, 999999, 99999.99, 999999.99, 9999999.99]);
const SCOPE_FLOOR = { inpatient_stay: 1500, facility_service: 15, professional: 15 };
const FORBIDDEN = ['oopUninsured', 'oopPpo', 'oopHdhp', 'estimatedOop', 'isEstimate'];
const NON_SURGICAL_TYPES = new Set(['Psychiatric', 'Long-term']);
const AMOUNT_FIELDS = ['cashLow', 'cashMedian', 'cashHigh', 'negotiatedLow', 'negotiatedMedian', 'negotiatedHigh'];

const procedures = readJson('data/seed/procedures.json');
const procById = new Map(procedures.map((p) => [p.id, p]));
const hospitals = new Map(readJson('data/cms/hospitals.json').map((h) => [h.id, h]));
const files = {
  'trilliant-prices.json': { rows: readJson('data/cms/trilliant-prices.json'), source: 'trilliant_mrf', meta: 'trilliant-meta.json' },
  'mrf-prices.json': { rows: readJson('data/cms/mrf-prices.json'), source: 'hospital_mrf', meta: 'mrf-meta.json' },
};

const normDrg = (c) => (/^\d+$/.test(c) ? String(Number(c)).padStart(3, '0') : c);
const floorFor = (p) => Math.max(Number(p.priceFloorUsd ?? 0), SCOPE_FLOOR[p.scope]);
function monthsBefore(iso, months) {
  const [y, m, d] = iso.split('-').map(Number);
  let yy = y;
  let mm = m - months;
  while (mm <= 0) { mm += 12; yy -= 1; }
  return `${yy}-${String(mm).padStart(2, '0')}-${String(Math.min(d, 28)).padStart(2, '0')}`;
}

// Collect violations per check so one failing assertion reports every offending row.
function check(rows, fn) {
  const bad = [];
  rows.forEach((r, i) => { const why = fn(r); if (why) bad.push(`[${i}] ${r.hospitalId}/${r.procedureId}: ${why}`); });
  return bad;
}
const show = (bad) => `${bad.length} violation(s):\n${bad.slice(0, 15).join('\n')}`;

test('procedure code map: every code belongs to exactly one procedure', () => {
  const owner = new Map();
  const dupes = [];
  for (const p of procedures) {
    for (const c of p.cptCodes ?? []) { const k = `CPT:${c}`; if (owner.has(k)) dupes.push(`${k} in ${owner.get(k)} and ${p.id}`); owner.set(k, p.id); }
    for (const c of p.drgCodes ?? []) { const k = `MS-DRG:${normDrg(c)}`; if (owner.has(k)) dupes.push(`${k} in ${owner.get(k)} and ${p.id}`); owner.set(k, p.id); }
  }
  assert.deepEqual(dupes, []);
});

test('procedure code map: one canonical scope per procedure, consistent with its code type, with a cited source', () => {
  const bad = [];
  for (const p of procedures) {
    if (!['inpatient_stay', 'facility_service', 'professional'].includes(p.scope)) bad.push(`${p.id}: scope ${p.scope}`);
    if (p.scope === 'inpatient_stay' && ((p.cptCodes ?? []).length || !(p.drgCodes ?? []).length)) bad.push(`${p.id}: inpatient_stay must be MS-DRG only`);
    if (p.scope === 'facility_service' && ((p.drgCodes ?? []).length || !(p.cptCodes ?? []).length)) bad.push(`${p.id}: facility_service must be CPT/HCPCS only`);
    if (!/^https:\/\/www\.cms\.gov\//.test(p.codeSource ?? '')) bad.push(`${p.id}: codeSource must cite a cms.gov URL`);
  }
  assert.deepEqual(bad, []);
});

test('knee and hip replacement are not priced from the shared MS-DRG 469/470', () => {
  for (const id of ['proc-knee-replacement', 'proc-hip-replacement']) {
    const p = procById.get(id);
    assert.ok(!(p.drgCodes ?? []).some((c) => ['469', '470'].includes(normDrg(c))), `${id} uses DRG 469/470`);
  }
});

for (const [name, { rows, source, meta }] of Object.entries(files)) {
  const metaJson = existsSync(path.join(ROOT, 'data/cms', meta)) ? readJson(`data/cms/${meta}`) : {};
  const ref = metaJson.referenceDate;

  test(`${name}: is an array of rows from ${source}`, () => {
    assert.ok(Array.isArray(rows));
    assert.deepEqual(check(rows, (r) => (r.priceSource !== source ? `priceSource ${r.priceSource}` : null)), []);
  });

  test(`${name}: no out-of-pocket or estimate fields`, () => {
    const bad = check(rows, (r) => { const f = FORBIDDEN.filter((k) => k in r); return f.length ? f.join(',') : null; });
    assert.equal(bad.length, 0, show(bad));
  });

  test(`${name}: hospital and procedure exist; hospitalId matches the CCN`, () => {
    const bad = check(rows, (r) => {
      if (!hospitals.has(r.hospitalId)) return 'unknown hospital';
      if (!procById.has(r.procedureId)) return 'unknown procedure';
      if (r.hospitalId !== `hosp-cms-${r.cmsProviderId}`) return 'hospitalId/cmsProviderId mismatch';
      return null;
    });
    assert.equal(bad.length, 0, show(bad));
  });

  test(`${name}: one canonical scope per procedure and codes from that procedure only`, () => {
    const bad = check(rows, (r) => {
      const p = procById.get(r.procedureId);
      if (!p) return 'unknown procedure';
      if (r.scope !== p.scope) return `scope ${r.scope} != ${p.scope}`;
      const expectType = p.scope === 'inpatient_stay' ? ['ms-drg'] : ['cpt', 'hcpcs'];
      if (!expectType.includes(r.matchType)) return `matchType ${r.matchType}`;
      if (!Array.isArray(r.matchedCodes) || !r.matchedCodes.length) return 'no matchedCodes';
      for (const c of r.matchedCodes) {
        const [t, v] = c.split(':');
        const ok = t === 'MS-DRG' ? (p.drgCodes ?? []).map(normDrg).includes(normDrg(v))
          : (t === 'CPT' || t === 'HCPCS') ? (p.cptCodes ?? []).includes(v) : false;
        if (!ok) return `code ${c} not in ${p.id}`;
      }
      return null;
    });
    assert.equal(bad.length, 0, show(bad));
  });

  test(`${name}: provenance (source vintage, stale flag, no local paths)`, () => {
    const bad = check(rows, (r) => {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(r.priceVintage ?? '')) return `priceVintage ${r.priceVintage}`;
      if (!ref) return 'meta has no referenceDate';
      if (r.priceVintage > ref) return `vintage ${r.priceVintage} after reference ${ref}`;
      if (r.stale !== (r.priceVintage < monthsBefore(ref, 18))) return `stale=${r.stale} inconsistent with ${r.priceVintage} vs ${ref}`;
      if (r.mrfUrl != null && (!r.mrfUrl.startsWith('https://') || r.mrfUrl.includes('oria-data.trillianthealth.com'))) return `mrfUrl ${r.mrfUrl}`;
      for (const k of ['mrfUrl', 'sourceDataset']) {
        const v = r[k];
        if (v != null && (!String(v).startsWith('https://') || /^[a-zA-Z]:[\\/]|\\/.test(String(v)))) return `${k} looks local: ${v}`;
      }
      if (!r.sourceDataset && !r.mrfUrl) return 'no source URL at all';
      if (!r.id || !/^[0-9a-f]{24}$/.test(r.id)) return `id ${r.id}`;
      return null;
    });
    assert.equal(bad.length, 0, show(bad));
  });

  test(`${name}: amounts within bounds and the procedure floor; a median is present`, () => {
    const bad = check(rows, (r) => {
      const p = procById.get(r.procedureId);
      if (r.cashMedian == null && r.negotiatedMedian == null) return 'no cash or negotiated median';
      for (const k of [...AMOUNT_FIELDS, 'grossCharge']) {
        const v = r[k];
        if (v == null) continue;
        if (typeof v !== 'number' || !(v > 0) || v >= PRICE_CEILING || SENTINELS.has(v)) return `${k}=${v} out of bounds`;
        if (k !== 'grossCharge' && v < floorFor(p)) return `${k}=${v} below floor ${floorFor(p)}`;
      }
      for (const [lo, mid, hi] of [['cashLow', 'cashMedian', 'cashHigh'], ['negotiatedLow', 'negotiatedMedian', 'negotiatedHigh']]) {
        if (r[mid] != null && !(r[lo] <= r[mid] && r[mid] <= r[hi])) return `${lo} <= ${mid} <= ${hi} violated`;
      }
      if (r.negotiatedMedian != null && !(Number.isInteger(r.payerCount) && r.payerCount >= 1)) return 'negotiated without payerCount';
      return null;
    });
    assert.equal(bad.length, 0, show(bad));
  });

  test(`${name}: no surgery or delivery at psychiatric / long-term hospitals; no stays at REHs`, () => {
    const bad = check(rows, (r) => {
      const h = hospitals.get(r.hospitalId);
      const p = procById.get(r.procedureId);
      if (!h || !p) return null;
      if (NON_SURGICAL_TYPES.has(h.hospitalType) && p.category !== 'Imaging') return `${p.id} at ${h.hospitalType} hospital`;
      if (h.hospitalType === 'Rural Emergency Hospital' && p.scope === 'inpatient_stay') return 'inpatient stay at REH';
      return null;
    });
    assert.equal(bad.length, 0, show(bad));
  });

  test(`${name}: no duplicate hospital+procedure`, () => {
    const seen = new Set();
    const bad = check(rows, (r) => { const k = `${r.hospitalId}|${r.procedureId}`; if (seen.has(k)) return 'duplicate'; seen.add(k); return null; });
    assert.equal(bad.length, 0, show(bad));
  });

  test(`${name}: rows are sorted by hospital then procedure (reproducible output)`, () => {
    const keys = rows.map((r) => `${r.hospitalId}|${r.procedureId}`);
    assert.deepEqual(keys, [...keys].sort());
  });
}

test('quarantine.json records counts by reason and at most 20 samples per reason', () => {
  const q = readJson('data/cms/quarantine.json');
  assert.ok(q.totalsByReason && typeof q.totalsByReason === 'object');
  for (const [section, s] of Object.entries(q.sections ?? {})) {
    for (const [reason, n] of Object.entries(s.counts ?? {})) {
      assert.ok(Number.isInteger(n) && n > 0, `${section}/${reason} count`);
      assert.ok((s.samples?.[reason] ?? []).length <= 20, `${section}/${reason} has > 20 samples`);
    }
  }
});

test('observation store carries no estimates and only https sources', () => {
  for (const f of ['data/observations/us-mrf-trilliant.jsonl', 'data/observations/us-mrf-direct.jsonl']) {
    if (!existsSync(path.join(ROOT, f))) continue;
    const lines = readFileSync(path.join(ROOT, f), 'utf8').split('\n').filter(Boolean);
    for (const line of lines) {
      const o = JSON.parse(line);
      assert.equal(o.is_estimate, false);
      assert.ok(o.provenance.source_url.startsWith('https://'), o.provenance.source_url);
      assert.ok(procById.has(o.procedure_id), o.procedure_id);
      assert.equal(o.scope, procById.get(o.procedure_id).scope);
    }
  }
});
