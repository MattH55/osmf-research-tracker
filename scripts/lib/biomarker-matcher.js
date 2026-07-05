/**
 * Match biomarker atlas entries to clinical trial outcome measure text.
 */

function slugify(text) {
  return (text || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '');
}

function markerId(slug, marker) {
  return `${slug}:${slugify(marker.name)}`;
}

const GENERIC_TERMS = new Set([
  'blood', 'plasma', 'serum', 'level', 'levels', 'total', 'chain', 'protein',
  'marker', 'index', 'test', 'composite', 'score', 'function', 'physical',
  'component', 'change', 'measure', 'measured', 'assessment', 'scale',
  'symptom', 'symptoms', 'quality', 'exercise', 'heart', 'rate', 'variability',
  'concentration', 'plasmatic', 'sample', 'analysis', 'panel', 'standard',
  'cytokine', 'cytokines', 'inflammatory', 'pro-inflammatory',
  'anti-inflammatory', 'immunomodulatory', 'profile', 'signature',
  'soluble', 'receptor', 'binding', 'factor', 'alpha', 'beta', 'gamma',
]);

const GENERIC_PHRASES = new Set([
  'pro-inflammatory cytokine',
  'anti-inflammatory cytokine',
  'immunomodulatory cytokine',
  'fibrotic cytokine',
  'th1 cytokine',
  'peripheral immune signature',
]);

function normalizeTerm(text) {
  return (text || '')
    .toLowerCase()
    .replace(/\u03b1|\u00ce\u00b1/g, ' alpha ')
    .replace(/\u03b2|\u00ce\u00b2/g, ' beta ')
    .replace(/\u03b3|\u00ce\u00b3/g, ' gamma ')
    .replace(/\u03b4|\u00ce\u00b4/g, ' delta ')
    .replace(/\u03ba|\u00ce\u00ba/g, ' kappa ')
    .replace(/\u2013|\u2014|\u00e2\u20ac\u201c|\u00e2\u20ac\u201d/g, '-')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function addTerm(terms, term) {
  const normalized = normalizeTerm(term);
  if (normalized.length < 2) return;
  if (GENERIC_TERMS.has(normalized)) return;

  const words = normalized.split(' ').filter(Boolean);
  if (!words.length) return;
  if (words.length > 1 && words.every((w) => GENERIC_TERMS.has(w))) return;
  if (words.length === 1 && words[0].length < 4 && !/[0-9]/.test(words[0])) return;

  terms.add(normalized);
}

/** Extract distinctive phrases and abbreviations from a marker name / alias. */
function markerTerms(marker) {
  const raw = [marker.name, marker.alternateName].filter(Boolean);
  const terms = new Set();

  for (const line of raw) {
    const full = line.toLowerCase().trim();
    if (GENERIC_PHRASES.has(full)) continue;

    addTerm(terms, full.replace(/\([^)]*\)/g, ' '));
    for (const segment of full.split(/[;,/]+/)) {
      addTerm(terms, segment.replace(/\([^)]*\)/g, ' '));
    }

    const paren = line.match(/\(([^)]+)\)/g);
    if (paren) {
      for (const p of paren) {
        for (const inner of p.replace(/[()]/g, '').split(/[;,/]+/)) {
          addTerm(terms, inner);
        }
      }
    }
  }

  return [...terms].sort((a, b) => b.length - a.length);
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function termRegex(term) {
  const parts = term.split(' ').map(escapeRegex);
  return new RegExp(`\\b${parts.join('[^a-z0-9]+')}\\b`, 'i');
}

function compactTerm(text) {
  return normalizeTerm(text).replace(/\s+/g, '');
}

function isMatch(term, text) {
  if (termRegex(term).test(text)) return true;
  const compact = compactTerm(term);
  return compact.length >= 4 && compactTerm(text).includes(compact);
}

/** Returns match strength 0-1 or 0 if no match. */
function scoreMatch(terms, haystack) {
  const text = normalizeTerm(haystack);
  let best = 0;
  for (const term of terms) {
    if (term.length < 2) continue;
    if (isMatch(term, text)) {
      const score = Math.min(1, term.length / 12);
      best = Math.max(best, score);
    }
  }
  return best;
}

function matchMarkerToText(marker, text) {
  const terms = markerTerms(marker);
  const score = scoreMatch(terms, text);
  if (score < 0.5) return null;
  return { score, terms };
}

function extractOutcomes(study) {
  const outcomes = [];
  const mod = study?.protocolSection?.outcomesModule || {};
  for (const o of mod.primaryOutcomes || []) {
    outcomes.push({
      type: 'primary',
      measure: o.measure || '',
      description: o.description || '',
      timeFrame: o.timeFrame || '',
    });
  }
  for (const o of mod.secondaryOutcomes || []) {
    outcomes.push({
      type: 'secondary',
      measure: o.measure || '',
      description: o.description || '',
      timeFrame: o.timeFrame || '',
    });
  }
  return outcomes;
}

function outcomeText(o) {
  return [o.measure, o.description, o.timeFrame].filter(Boolean).join(' - ');
}

module.exports = {
  slugify,
  markerId,
  markerTerms,
  scoreMatch,
  matchMarkerToText,
  extractOutcomes,
  outcomeText,
};
