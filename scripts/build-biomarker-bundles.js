/**
 * Emit JS bundles for biomarker data so atlases work via file:// and when fetch fails.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'data', 'biomarkers');
const CLINICAL_TRIALS_DIR = path.join(ROOT, 'data', 'clinical_trials');
const OUT_DIR = path.join(ROOT, 'js', 'generated');

const SLUGS = ['long-covid', 'pacvs', 'me-cfs', 'lyme', 'gulf-war-illness'];

function readJson(name) {
  return JSON.parse(fs.readFileSync(path.join(DATA_DIR, name), 'utf8'));
}

function readClinicalTrialsJson(name) {
  return JSON.parse(fs.readFileSync(path.join(CLINICAL_TRIALS_DIR, name), 'utf8'));
}

function writeBundle(filename, globalVar, payload) {
  const body = `window.${globalVar}=${JSON.stringify(payload)};`;
  fs.writeFileSync(path.join(OUT_DIR, filename), body, 'utf8');
}

function subsetTrials(markerTrials, slug) {
  const prefix = `${slug}:`;
  const out = {};
  for (const [key, trials] of Object.entries(markerTrials)) {
    if (key.startsWith(prefix)) out[key] = trials;
  }
  return out;
}

function subsetOntology(terms, slug) {
  return (terms || []).filter((term) => term.slug === slug);
}

function main() {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const searchIndex = readJson('search-index.json');
  writeBundle('search-index.bundle.js', '__BIOMARKER_SEARCH_INDEX__', searchIndex);

  const commercial = readJson('commercial-links.json');
  writeBundle('commercial-links.bundle.js', '__BIOMARKER_COMMERCIAL__', commercial);

  if (fs.existsSync(path.join(DATA_DIR, 'consumable-links.json'))) {
    const consumable = readJson('consumable-links.json');
    writeBundle('consumable-links.bundle.js', '__BIOMARKER_CONSUMABLE__', consumable);
  }

  if (fs.existsSync(path.join(DATA_DIR, 'intervention-links.json'))) {
    const interventions = readJson('intervention-links.json');
    writeBundle('intervention-links.bundle.js', '__BIOMARKER_INTERVENTIONS__', interventions);
  }

  if (fs.existsSync(path.join(DATA_DIR, 'agent-discovery.json'))) {
    const discovery = readJson('agent-discovery.json');
    writeBundle('agent-discovery.bundle.js', '__BIOMARKER_AGENT_DISCOVERY__', discovery);
  }

  let outcomeOntology = { terms: [] };
  if (fs.existsSync(path.join(DATA_DIR, 'outcome-ontology.json'))) {
    outcomeOntology = readJson('outcome-ontology.json');
  }
  writeBundle('outcome-ontology.bundle.js', '__BIOMARKER_OUTCOME_ONTOLOGY__', outcomeOntology);

  let treatmentOntology = { terms: [] };
  if (fs.existsSync(path.join(CLINICAL_TRIALS_DIR, 'treatment-ontology.json'))) {
    treatmentOntology = readClinicalTrialsJson('treatment-ontology.json');
  }
  writeBundle('treatment-ontology.bundle.js', '__TREATMENT_ONTOLOGY__', treatmentOntology);

  let trialLinks = { markerTrials: {}, trialMeta: {} };
  if (fs.existsSync(path.join(DATA_DIR, 'trial-links.json'))) {
    trialLinks = readJson('trial-links.json');
  }

  for (const slug of SLUGS) {
    const atlas = readJson(`${slug}.json`);
    writeBundle(`atlas-${slug}.bundle.js`, '__BIOMARKER_ATLAS__', atlas);

    const trials = subsetTrials(trialLinks.markerTrials || {}, slug);
    writeBundle(`trial-links-${slug}.bundle.js`, '__BIOMARKER_TRIAL_LINKS__', {
      markerTrials: trials,
      outcomeOntology: subsetOntology(trialLinks.outcomeOntology || outcomeOntology.terms || [], slug),
    });
  }

  console.log(`Wrote biomarker bundles to ${path.relative(ROOT, OUT_DIR)}/`);
  console.log(`  search-index (${searchIndex.count || searchIndex.markers?.length || 0} markers)`);
  console.log(`  commercial-links + outcome/treatment ontologies + ${SLUGS.length} atlas + trial bundles`);
}

main();
