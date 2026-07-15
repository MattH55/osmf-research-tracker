#!/usr/bin/env node
// Build-time validator for data/loops.json.
// Fails (non-zero exit) if any claim would render without proper evidentiary support.
// This is the structural enforcement of the "no claim without a verified citation" rule.

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_PATH = path.join(__dirname, 'data', 'loops.json');

let errors = [];
let warnings = [];

function fail(msg) {
  errors.push(msg);
}

function warn(msg) {
  warnings.push(msg);
}

let raw;
try {
  raw = readFileSync(DATA_PATH, 'utf8');
} catch (e) {
  console.error(`FATAL: could not read ${DATA_PATH}: ${e.message}`);
  process.exit(1);
}

let data;
try {
  data = JSON.parse(raw);
} catch (e) {
  console.error(`FATAL: ${DATA_PATH} is not valid JSON: ${e.message}`);
  process.exit(1);
}

const claims = data.claims || data; // allow either {claims:[...]} or a bare array
if (!Array.isArray(claims)) {
  console.error('FATAL: expected an array of claims (or {"claims": [...]})');
  process.exit(1);
}

const VALID_GRADES = new Set([
  'established_general',
  'established_disease',
  'supported',
  'emerging',
  'contested',
  'hypothesis',
]);

const seenIds = new Set();

for (const claim of claims) {
  const id = claim.id || '(missing id)';

  if (!claim.id) fail(`Claim missing "id" field: ${JSON.stringify(claim).slice(0, 80)}`);
  if (claim.id && seenIds.has(claim.id)) fail(`Duplicate claim id: ${claim.id}`);
  seenIds.add(claim.id);

  if (!claim.statement || claim.statement.trim().length === 0) {
    fail(`[${id}] missing "statement"`);
  }

  if (!claim.grade || !VALID_GRADES.has(claim.grade)) {
    fail(`[${id}] invalid or missing "grade": ${claim.grade}. Must be one of: ${[...VALID_GRADES].join(', ')}`);
  }

  if (typeof claim.disease_specific !== 'boolean') {
    fail(`[${id}] "disease_specific" must be a boolean`);
  }

  const citations = claim.citations || [];
  if (!Array.isArray(citations) || citations.length === 0) {
    fail(`[${id}] has zero citations — no claim may render without at least one citation`);
    continue;
  }

  const verifiedCitations = citations.filter(c => c.verified === true);
  if (verifiedCitations.length === 0) {
    fail(`[${id}] has ${citations.length} citation(s) but none marked verified:true`);
  }

  for (const c of citations) {
    const label = `${id} / ${c.authors || '(no authors)'} ${c.year || '?'}`;
    const hasIdentifier = !!(c.doi || c.pmid || c.pmcid);
    if (!hasIdentifier) {
      fail(`[${label}] has no DOI, PMID, or PMCID — a URL alone is not a valid identifier`);
    }
    if (c.verified === true && !hasIdentifier) {
      fail(`[${label}] marked verified:true but carries no resolvable identifier — contradiction`);
    }
    if (!c.source_tier) {
      fail(`[${label}] missing "source_tier" (expected "primary" or "secondary")`);
    }
  }

  // Contested claims need both sides
  if (claim.grade === 'contested') {
    const counterCitations = citations.filter(c => c.contested_counter === true);
    if (counterCitations.length === 0) {
      fail(`[${id}] graded "contested" but has zero citations flagged contested_counter:true — must show both sides`);
    }
    const supportCitations = citations.filter(c => c.contested_counter !== true);
    if (supportCitations.length === 0) {
      fail(`[${id}] graded "contested" but has zero supporting (non-counter) citations`);
    }
  }

  // Mechanistic (non-context) claims can't rest solely on secondary sources
  if (claim.claim_type !== 'context') {
    const primaryCount = citations.filter(c => c.source_tier === 'primary').length;
    if (primaryCount === 0) {
      fail(`[${id}] is a mechanistic claim (claim_type != "context") but has zero primary-source citations`);
    }
  }

  // disease_specific:true claims graded established_general is an internal inconsistency
  if (claim.disease_specific === true && claim.grade === 'established_general') {
    warn(`[${id}] marked disease_specific:true but graded established_general — check this is intentional`);
  }
  if (claim.disease_specific === false && (claim.grade === 'supported' || claim.grade === 'established_disease')) {
    warn(`[${id}] marked disease_specific:false but graded ${claim.grade}, which implies disease-specific evidence — check this is intentional`);
  }
}

console.log(`Checked ${claims.length} claims.`);

if (warnings.length) {
  console.log(`\n${warnings.length} warning(s):`);
  warnings.forEach(w => console.log(`  WARN: ${w}`));
}

if (errors.length) {
  console.log(`\n${errors.length} error(s) — BUILD FAILED:`);
  errors.forEach(e => console.log(`  FAIL: ${e}`));
  process.exit(1);
} else {
  console.log('\nAll claims pass validation.');
  process.exit(0);
}
