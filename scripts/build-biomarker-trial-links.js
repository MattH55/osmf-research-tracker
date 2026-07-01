/**
 * Build searchable biomarker index + clinical trial outcome links.
 * Reads OSM clinical trials feed, fetches outcome measures from ClinicalTrials.gov,
 * and matches to atlas markers.
 */
const fs = require('fs');
const path = require('path');
const {
  markerId,
  markerTerms,
  matchMarkerToText,
  extractOutcomes,
  outcomeText,
} = require('./lib/biomarker-matcher');

const ROOT = path.join(__dirname, '..');
const BIOMARKER_DIR = path.join(ROOT, 'data', 'biomarkers');
const TRIALS_SRC = path.join(
  'C:', 'Users', 'matth', 'OneDrive', 'Documents', 'OpenSourceMed', 'Opensource Medicine (1)',
  'research-tracker', 'clinical_trials', 'data', 'clinical_trials_current.json'
);
const TRIALS_LOCAL = path.join(ROOT, 'data', 'clinical_trials', 'clinical_trials_current.json');
const OUTCOMES_CACHE = path.join(ROOT, 'data', 'clinical_trials', 'outcomes-cache.json');
const LINKS_OUT = path.join(BIOMARKER_DIR, 'trial-links.json');
const INDEX_OUT = path.join(BIOMARKER_DIR, 'search-index.json');
const ONTOLOGY_OUT = path.join(BIOMARKER_DIR, 'outcome-ontology.json');

const ATLAS_SLUGS = ['long-covid', 'pacvs', 'me-cfs', 'lyme', 'gulf-war-illness'];
const ATLAS_PAGES = {
  'long-covid': 'long-covid-biomarkers.html',
  pacvs: 'pacvs-biomarkers.html',
  'me-cfs': 'me-cfs-biomarkers.html',
  lyme: 'lyme-biomarkers.html',
  'gulf-war-illness': 'gulf-war-illness-biomarkers.html',
};

const ALLOWED_CONDITION_LABELS = new Set([
  'Long COVID / PASC',
  'ME/CFS',
]);

const ALLOWED_CONDITION_PATTERNS = [
  { label: 'Long COVID / PASC', re: /\b(long covid|long-covid|post[-\s]?covid|post acute sequelae of sars|pasc|post-acute covid|post covid condition|post covid-19 condition)\b/i },
  { label: 'Post-vaccination syndrome', re: /\b(post[-\s]?(acute\s*)?(covid[-\s]?19\s*)?vaccination syndrome|post[-\s]?covid[-\s]?19 vaccine injury|vaccine adverse reaction|post[-\s]?vaccin|pacvs)\b/i },
  { label: 'MCAS', re: /\b(mast cell activation syndrome|mast cell activation disease|mast cell activation disorder|mcas|mcad)\b/i },
  { label: 'POTS', re: /\b(postural (orthostatic )?tachycardia syndrome|postural tachycardia syndrome|pots)\b/i },
  { label: 'ME/CFS', re: /\b(myalgic encephalomyelitis|chronic fatigue syndrome|me\/cfs|me-cfs|systemic exertion intolerance disease|seid)\b/i },
];

const BATCH = 40;
const API = 'https://clinicaltrials.gov/api/v2/studies';

function loadTrials() {
  const src = fs.existsSync(TRIALS_SRC) ? TRIALS_SRC : TRIALS_LOCAL;
  if (!fs.existsSync(src)) throw new Error(`Trials file not found: ${src}`);
  const data = JSON.parse(fs.readFileSync(src, 'utf8'));
  fs.mkdirSync(path.dirname(TRIALS_LOCAL), { recursive: true });
  fs.copyFileSync(src, TRIALS_LOCAL);
  return data.trials || [];
}

function loadAtlases() {
  const entries = [];
  for (const slug of ATLAS_SLUGS) {
    const file = path.join(BIOMARKER_DIR, `${slug}.json`);
    const atlas = JSON.parse(fs.readFileSync(file, 'utf8'));
    for (const marker of atlas.markers) {
      entries.push({
        id: markerId(slug, marker),
        slug,
        condition: atlas.condition.shortName,
        conditionName: atlas.condition.name,
        page: ATLAS_PAGES[slug],
        category: marker.category,
        categoryLabel: atlas.categories[marker.category] || marker.category,
        marker,
      });
    }
  }
  return entries;
}

function loadOutcomeCache() {
  if (!fs.existsSync(OUTCOMES_CACHE)) return {};
  return JSON.parse(fs.readFileSync(OUTCOMES_CACHE, 'utf8'));
}

function saveOutcomeCache(cache) {
  fs.mkdirSync(path.dirname(OUTCOMES_CACHE), { recursive: true });
  fs.writeFileSync(OUTCOMES_CACHE, JSON.stringify(cache, null, 2), 'utf8');
}

async function fetchStudyOutcomes(nctIds) {
  const missing = nctIds.filter((id) => id);
  if (!missing.length) return {};

  const params = new URLSearchParams({
    'filter.ids': missing.join(','),
    pageSize: String(Math.min(100, missing.length)),
    format: 'json',
  });

  const url = `${API}?${params}`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`ClinicalTrials.gov API ${res.status}: ${url}`);

  const data = await res.json();
  const out = {};
  for (const study of data.studies || []) {
    const nct = study?.protocolSection?.identificationModule?.nctId;
    if (!nct) continue;
    out[nct] = extractOutcomes(study);
  }
  return out;
}

async function enrichOutcomes(trials) {
  const cache = loadOutcomeCache();
  const nctIds = trials.map((t) => t.nct_id).filter(Boolean);
  const need = nctIds.filter((id) => !cache[id]);

  console.log(`Outcomes cache: ${Object.keys(cache).length} cached, ${need.length} to fetch`);

  for (let i = 0; i < need.length; i += BATCH) {
    const batch = need.slice(i, i + BATCH);
    process.stdout.write(`  Fetching outcomes ${i + 1}–${Math.min(i + BATCH, need.length)} / ${need.length}…\r`);
    try {
      const fetched = await fetchStudyOutcomes(batch);
      Object.assign(cache, fetched);
      // Mark empty arrays for NCT IDs with no outcomes in response
      for (const id of batch) {
        if (!cache[id]) cache[id] = [];
      }
      saveOutcomeCache(cache);
      await new Promise((r) => setTimeout(r, 350));
    } catch (err) {
      console.warn(`\n  Batch fetch warning: ${err.message}`);
    }
  }
  console.log('');
  return cache;
}

function buildLinks(atlasEntries, trials, outcomesCache) {
  const markerTrials = {};
  const trialMeta = {};

  for (const trial of trials) {
    const allowedConditions = getAllowedConditions(trial);
    if (!allowedConditions.length) continue;
    trialMeta[trial.nct_id] = {
      nct_id: trial.nct_id,
      title: trial.title,
      status: trial.status,
      phase: trial.phase,
      mapped_conditions: allowedConditions,
      link: trial.link || `https://clinicaltrials.gov/study/${trial.nct_id}`,
    };
  }

  for (const entry of atlasEntries) {
    const links = [];

    for (const trial of trials) {
      const allowedConditions = getAllowedConditions(trial);
      if (!allowedConditions.length) continue;
      const outcomes = outcomesCache[trial.nct_id] || [];
      for (const outcome of outcomes) {
        const text = outcomeText(outcome);
        const match = matchMarkerToText(entry.marker, text);
        if (!match) continue;
        links.push({
          nct_id: trial.nct_id,
          title: trial.title,
          status: trial.status,
          phase: trial.phase,
          mapped_conditions: allowedConditions,
          link: trial.link || `https://clinicaltrials.gov/study/${trial.nct_id}`,
          outcomeType: outcome.type,
          outcomeMeasure: outcome.measure,
          outcomeDescription: outcome.description || '',
          matchScore: Math.round(match.score * 100) / 100,
        });
      }
    }

    // One best outcome per trial per marker, cap list size
    const byNct = new Map();
    for (const l of links) {
      const prev = byNct.get(l.nct_id);
      if (!prev || l.matchScore > prev.matchScore) byNct.set(l.nct_id, l);
    }
    const sorted = [...byNct.values()]
      .sort((a, b) => b.matchScore - a.matchScore)
      .slice(0, 25);
    if (sorted.length) {
      const ontologyId = `outcome:${entry.id}`;
      markerTrials[entry.id] = sorted.map((l) => ({
        ...l,
        outcomeOntologyId: ontologyId,
      }));
    }
  }

  return { markerTrials, trialMeta };
}

function normalizeSynonym(text) {
  return (text || '')
    .replace(/\u00c2/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function canonicalKey(text) {
  return normalizeSynonym(text)
    .toLowerCase()
    .replace(/\u03b1/g, 'alpha')
    .replace(/\u03b2/g, 'beta')
    .replace(/\u03b3/g, 'gamma')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function addSynonym(out, seen, value) {
  const synonym = normalizeSynonym(value);
  if (!synonym) return;
  const key = canonicalKey(synonym);
  if (!key || seen.has(key)) return;
  seen.add(key);
  out.push(synonym);
}

function bestOutcomeTerm(marker, trials) {
  const terms = markerTerms(marker).map(canonicalKey).filter(Boolean);
  const candidates = [];

  for (const trial of trials) {
    const measure = normalizeSynonym(trial.outcomeMeasure);
    if (!measure) continue;
    const measureKey = canonicalKey(measure);
    const descriptionKey = canonicalKey(trial.outcomeDescription || '');
    const measureContainsMarker = terms.some((term) => measureKey.includes(term));
    const descriptionContainsMarker = terms.some((term) => descriptionKey.includes(term));
    const generic = /^(change in blood labs|secondary endpoint|inflammatory parameters|serum level change of inflammatory factors)$/i.test(measure);
    const specificity = (measureContainsMarker ? 5 : 0) + (descriptionContainsMarker ? 1 : 0);
    const brevity = measure.length <= 90 ? 1 : 0;
    candidates.push({
      term: measure,
      score: specificity + brevity + trial.matchScore - (generic ? 1 : 0),
      key: measureKey,
    });
  }

  candidates.sort((a, b) => b.score - a.score || a.term.length - b.term.length);
  return candidates[0]?.term || normalizeSynonym(marker.name);
}

function buildOutcomeOntology(atlasEntries, markerTrials) {
  const byId = new Map(atlasEntries.map((entry) => [entry.id, entry]));
  const terms = [];

  for (const [id, trials] of Object.entries(markerTrials)) {
    const entry = byId.get(id);
    if (!entry) continue;

    const seen = new Set();
    const synonyms = [];
    const clinicalOutcomeTerms = [];
    const marker = entry.marker;
    const preferredTerm = bestOutcomeTerm(marker, trials);

    addSynonym(synonyms, seen, preferredTerm);
    addSynonym(synonyms, seen, marker.name);
    addSynonym(synonyms, seen, marker.alternateName);
    for (const term of markerTerms(marker)) addSynonym(synonyms, seen, term);
    if (marker.loinc) addSynonym(synonyms, seen, `LOINC ${marker.loinc}`);

    const clinicalSeen = new Set();
    for (const trial of trials) {
      addSynonym(clinicalOutcomeTerms, clinicalSeen, trial.outcomeMeasure);
      addSynonym(synonyms, seen, trial.outcomeMeasure);
    }

    terms.push({
      id: `outcome:${id}`,
      markerId: id,
      slug: entry.slug,
      markerName: marker.name,
      preferredTerm,
      synonyms,
      clinicalOutcomeTerms,
      trialCount: new Set(trials.map((t) => t.nct_id)).size,
      nctIds: [...new Set(trials.map((t) => t.nct_id))],
      conditions: [...new Set(trials.flatMap((t) => t.mapped_conditions || []))],
      category: entry.category,
      loinc: marker.loinc || null,
      source: 'ClinicalTrials.gov outcome measures matched to biomarker atlas entries',
    });
  }

  return terms.sort((a, b) => a.slug.localeCompare(b.slug) || a.markerName.localeCompare(b.markerName));
}

function getAllowedConditions(trial) {
  const labels = new Set();
  for (const c of trial.mapped_conditions || []) {
    if (ALLOWED_CONDITION_LABELS.has(c)) labels.add(c);
  }

  const raw = [
    trial.title,
    ...(trial.conditions_raw || []),
  ].filter(Boolean).join(' | ');

  for (const { label, re } of ALLOWED_CONDITION_PATTERNS) {
    if (re.test(raw)) labels.add(label);
  }

  return [...labels];
}

function loadCommercialLinks() {
  const p = path.join(BIOMARKER_DIR, 'commercial-links.json');
  if (!fs.existsSync(p)) return {};
  return JSON.parse(fs.readFileSync(p, 'utf8')).markerCommercial || {};
}

function loadConsumableLinks() {
  const p = path.join(BIOMARKER_DIR, 'consumable-links.json');
  if (!fs.existsSync(p)) return {};
  return JSON.parse(fs.readFileSync(p, 'utf8')).markerConsumable || {};
}

function loadInterventionLinks() {
  const p = path.join(BIOMARKER_DIR, 'intervention-links.json');
  if (!fs.existsSync(p)) return {};
  return JSON.parse(fs.readFileSync(p, 'utf8')).markerInterventions || {};
}

function buildSearchIndex(atlasEntries, markerTrials, commercialLinks, consumableLinks, interventionLinks, outcomeOntology) {
  const ontologyByMarker = new Map(outcomeOntology.map((term) => [term.markerId, term]));
  return atlasEntries.map((e) => {
    const m = e.marker;
    const trials = markerTrials[e.id] || [];
    const uniqueNct = [...new Set(trials.map((t) => t.nct_id))];
    const commercial = commercialLinks[e.id] || null;
    const consumable = consumableLinks[e.id] || null;
    const interventionInfo = interventionLinks[e.id] || null;
    const ontology = ontologyByMarker.get(e.id) || null;
    return {
      id: e.id,
      slug: e.slug,
      condition: e.condition,
      conditionName: e.conditionName,
      page: e.page,
      name: m.name,
      alternateName: m.alternateName || '',
      direction: m.direction,
      category: e.category,
      categoryLabel: e.categoryLabel,
      comparison: m.comparison,
      symptoms: m.symptoms || '',
      loinc: m.loinc || null,
      reference: m.reference,
      trialCount: uniqueNct.length,
      trials: trials.slice(0, 8),
      outcomeOntology: ontology ? {
        id: ontology.id,
        preferredTerm: ontology.preferredTerm,
        synonyms: ontology.synonyms.slice(0, 12),
      } : null,
      commercial: commercial ? {
        availability: commercial.availability,
        testName: commercial.testName,
        vendors: (commercial.vendors || []).slice(0, 3),
        note: commercial.note || null,
      } : null,
      consumable: consumable?.consumable ? {
        productName: consumable.productName,
        productType: consumable.productType,
        note: consumable.note || null,
      } : null,
      interventions: interventionInfo ? {
        count: (interventionInfo.interventions || []).length,
        agents: (interventionInfo.interventions || []).slice(0, 6).map((a) => ({
          preferredTerm: a.preferredTerm,
          categories: a.categories || [],
          trialCount: a.nctIds?.length || 0,
          pmidCount: a.literature?.pmidCount || 0,
          topArticle: a.literature?.topArticles?.[0] || null,
        })),
      } : null,
      searchText: [
        m.name, m.alternateName, e.condition, e.conditionName,
        e.categoryLabel, m.comparison, m.symptoms, m.loinc,
        m.reference?.citation, ontology?.preferredTerm,
        consumable?.productName, consumable?.productType,
        ...(interventionInfo?.interventions || []).map((a) => a.preferredTerm),
        ...(ontology?.synonyms || []),
      ].filter(Boolean).join(' ').toLowerCase(),
    };
  });
}

async function main() {
  const trials = loadTrials();
  const atlasEntries = loadAtlases();
  console.log(`Loaded ${atlasEntries.length} markers, ${trials.length} trials`);

  const outcomesCache = await enrichOutcomes(trials);
  const { markerTrials, trialMeta } = buildLinks(atlasEntries, trials, outcomesCache);
  const outcomeOntology = buildOutcomeOntology(atlasEntries, markerTrials);
  const commercialLinks = loadCommercialLinks();
  const consumableLinks = loadConsumableLinks();
  const interventionLinks = loadInterventionLinks();
  const searchIndex = buildSearchIndex(atlasEntries, markerTrials, commercialLinks, consumableLinks, interventionLinks, outcomeOntology);

  const linkedMarkers = Object.keys(markerTrials).length;
  const totalLinks = Object.values(markerTrials).reduce((n, arr) => n + arr.length, 0);

  const payload = {
    generated: new Date().toISOString().slice(0, 10),
    trialCount: trials.length,
    markerCount: atlasEntries.length,
    linkedMarkerCount: linkedMarkers,
    totalOutcomeLinks: totalLinks,
    markerTrials,
    outcomeOntology,
    trialMeta,
  };

  fs.writeFileSync(LINKS_OUT, JSON.stringify(payload, null, 2), 'utf8');
  fs.writeFileSync(ONTOLOGY_OUT, JSON.stringify({
    generated: payload.generated,
    count: outcomeOntology.length,
    terms: outcomeOntology,
  }, null, 2), 'utf8');
  fs.writeFileSync(INDEX_OUT, JSON.stringify({
    generated: payload.generated,
    count: searchIndex.length,
    markers: searchIndex,
  }, null, 2), 'utf8');

  console.log(`Wrote ${LINKS_OUT}`);
  console.log(`  ${linkedMarkers} markers linked to trials (${totalLinks} outcome matches)`);
  console.log(`Wrote ${ONTOLOGY_OUT} (${outcomeOntology.length} ontology terms)`);
  console.log(`Wrote ${INDEX_OUT} (${searchIndex.length} searchable entries)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
