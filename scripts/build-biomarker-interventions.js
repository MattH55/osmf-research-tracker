/**
 * Link biomarkers to literature-validated therapeutic interventions.
 * Pipeline: extract agents from trials with biomarker outcome measures,
 * then narrow via PubMed search of therapeutic–biomarker pairs.
 */
const fs = require('fs');
const path = require('path');
const { markerId, markerTerms } = require('./lib/biomarker-matcher');
const {
  canonicalAgent,
  isExcludedAgent,
  categorize,
  treatmentId,
} = require('./lib/treatment-canonical');

const ROOT = path.join(__dirname, '..');
const BIOMARKER_DIR = path.join(ROOT, 'data', 'biomarkers');
const TRIALS_SRC = path.join(
  'C:', 'Users', 'matth', 'OneDrive', 'Documents', 'OpenSourceMed', 'Opensource Medicine (1)',
  'research-tracker', 'clinical_trials', 'data', 'clinical_trials_current.json'
);
const TRIALS_LOCAL = path.join(ROOT, 'data', 'clinical_trials', 'clinical_trials_current.json');
const TRIAL_LINKS = path.join(BIOMARKER_DIR, 'trial-links.json');
const CACHE_PATH = path.join(ROOT, 'data', 'agent-literature', 'biomarker-intervention-cache.json');
const OUT = path.join(BIOMARKER_DIR, 'intervention-links.json');

const ATLAS_SLUGS = ['long-covid', 'pacvs', 'me-cfs', 'lyme', 'gulf-war-illness'];
const PUBMED_TOOL = 'OSMF-BiomarkerInterventions';
const PUBMED_EMAIL = 'research@opensourcemed.info';
const RATE_LIMIT_MS = 340;
const RETMAX = 6;
const SKIP_LITERATURE = process.argv.includes('--skip-literature');

const EXCLUDED_CATEGORIES = new Set(['control']);

function loadTrials() {
  const src = fs.existsSync(TRIALS_SRC) ? TRIALS_SRC : TRIALS_LOCAL;
  if (!fs.existsSync(src)) throw new Error(`Trials file not found: ${src}`);
  return JSON.parse(fs.readFileSync(src, 'utf8')).trials || [];
}

function loadAtlases() {
  const entries = [];
  for (const slug of ATLAS_SLUGS) {
    const atlas = JSON.parse(fs.readFileSync(path.join(BIOMARKER_DIR, `${slug}.json`), 'utf8'));
    for (const marker of atlas.markers) {
      entries.push({
        id: markerId(slug, marker),
        slug,
        condition: atlas.condition.shortName,
        marker,
      });
    }
  }
  return entries;
}

function loadTrialLinks() {
  if (!fs.existsSync(TRIAL_LINKS)) return {};
  return JSON.parse(fs.readFileSync(TRIAL_LINKS, 'utf8')).markerTrials || {};
}

function loadCache() {
  if (!fs.existsSync(CACHE_PATH)) return {};
  return JSON.parse(fs.readFileSync(CACHE_PATH, 'utf8'));
}

function saveCache(cache) {
  fs.mkdirSync(path.dirname(CACHE_PATH), { recursive: true });
  fs.writeFileSync(CACHE_PATH, JSON.stringify(cache, null, 2), 'utf8');
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function biomarkerSearchTerms(marker) {
  const terms = [];
  const seen = new Set();
  const add = (t) => {
    const clean = (t || '').replace(/\s+/g, ' ').trim();
    if (!clean || clean.length < 3) return;
    const key = clean.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    terms.push(clean);
  };

  add(marker.name);
  add(marker.name.replace(/\s*\([^)]*\)/g, '').trim());
  add(marker.alternateName);
  for (const term of markerTerms(marker)) add(term);
  if (marker.loinc) add(`LOINC ${marker.loinc}`);
  return terms.slice(0, 6);
}

function agentSearchTerms(preferred, rawAgents = []) {
  const terms = [preferred];
  for (const raw of rawAgents) {
    const canon = canonicalAgent(raw);
    if (canon && canon !== preferred) terms.push(canon);
    if (raw.length >= 4 && raw.length <= 60) terms.push(raw);
  }
  const out = [];
  const seen = new Set();
  for (const t of terms) {
    const key = t.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(t);
    if (out.length >= 4) break;
  }
  return out;
}

function pubmedQuote(term) {
  return `"${term.replace(/"/g, '')}"[tiab]`;
}

function buildPairQuery(agentTerms, biomarkerTerms) {
  const agentParts = agentTerms.map(pubmedQuote).filter(Boolean);
  const markerParts = biomarkerTerms
    .filter((t) => t.length >= 3)
    .slice(0, 4)
    .map(pubmedQuote);

  if (!agentParts.length || !markerParts.length) return '';

  const agentClause = agentParts.length === 1
    ? agentParts[0]
    : `(${agentParts.join(' OR ')})`;
  const markerClause = markerParts.length === 1
    ? markerParts[0]
    : `(${markerParts.join(' OR ')})`;

  return `${agentClause} AND ${markerClause}`;
}

async function pubmedEsearch(query) {
  const params = new URLSearchParams({
    db: 'pubmed',
    term: query,
    retmax: String(RETMAX),
    retmode: 'json',
    tool: PUBMED_TOOL,
    email: PUBMED_EMAIL,
  });
  const url = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?${params}`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`PubMed esearch ${res.status}`);
  const data = await res.json();
  return data?.esearchresult?.idlist || [];
}

async function pubmedEsummary(pmids) {
  if (!pmids.length) return [];
  const params = new URLSearchParams({
    db: 'pubmed',
    id: pmids.join(','),
    retmode: 'json',
    tool: PUBMED_TOOL,
    email: PUBMED_EMAIL,
  });
  const url = `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?${params}`;
  const res = await fetch(url, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`PubMed esummary ${res.status}`);
  const data = await res.json();
  const result = data?.result || {};
  return pmids.map((id) => {
    const item = result[id] || {};
    return {
      pmid: id,
      title: item.title || '',
      pubDate: item.pubdate || '',
      journal: item.fulljournalname || item.source || '',
      url: `https://pubmed.ncbi.nlm.nih.gov/${id}/`,
    };
  });
}

function extractTrialAgents(trials, nctIds) {
  const byNct = new Map(trials.map((t) => [t.nct_id, t]));
  const agentMap = new Map();

  for (const nctId of nctIds) {
    const trial = byNct.get(nctId);
    if (!trial) continue;
    for (const raw of trial.agents || []) {
      if (isExcludedAgent(raw)) continue;
      const preferred = canonicalAgent(raw);
      const id = treatmentId(preferred);
      const categories = categorize(preferred, [raw]);
      if (categories.every((c) => EXCLUDED_CATEGORIES.has(c))) continue;

      if (!agentMap.has(id)) {
        agentMap.set(id, {
          id,
          preferredTerm: preferred,
          categories,
          rawAgents: [],
          nctIds: [],
          trials: [],
        });
      }
      const entry = agentMap.get(id);
      if (!entry.rawAgents.includes(raw)) entry.rawAgents.push(raw);
      if (!entry.nctIds.includes(nctId)) {
        entry.nctIds.push(nctId);
        entry.trials.push({
          nct_id: nctId,
          title: trial.title,
          link: trial.link || `https://clinicaltrials.gov/study/${nctId}`,
        });
      }
    }
  }

  return [...agentMap.values()].sort((a, b) => b.nctIds.length - a.nctIds.length);
}

async function validateLiterature(agentEntry, markerEntryId, marker, cache) {
  const cacheKey = `${agentEntry.id}|${markerEntryId}`;
  if (cache[cacheKey]) return cache[cacheKey];

  const agentTerms = agentSearchTerms(agentEntry.preferredTerm, agentEntry.rawAgents);
  const biomarkerTerms = biomarkerSearchTerms(marker);
  const query = buildPairQuery(agentTerms, biomarkerTerms);

  if (!query) {
    const empty = { validated: false, query: '', pmids: [], articles: [] };
    cache[cacheKey] = empty;
    return empty;
  }

  await sleep(RATE_LIMIT_MS);
  try {
    const pmids = await pubmedEsearch(query);
    await sleep(RATE_LIMIT_MS);
    const articles = pmids.length ? await pubmedEsummary(pmids.slice(0, RETMAX)) : [];
    const result = {
      validated: pmids.length > 0,
      query,
      pmids,
      articles,
    };
    cache[cacheKey] = result;
    return result;
  } catch (err) {
    const fallback = { validated: false, query, pmids: [], articles: [], error: err.message };
    cache[cacheKey] = fallback;
    return fallback;
  }
}

async function main() {
  const trials = loadTrials();
  const atlasEntries = loadAtlases();
  const markerTrials = loadTrialLinks();
  const cache = loadCache();
  const trialByNct = new Map(trials.map((t) => [t.nct_id, t]));

  const markerInterventions = {};
  let totalTrialAgents = 0;
  let totalValidated = 0;

  const linkedEntries = atlasEntries.filter((e) => (markerTrials[e.id] || []).length > 0);
  console.log(`Processing ${linkedEntries.length} markers with trial outcome links…`);

  for (let i = 0; i < linkedEntries.length; i++) {
    const entry = linkedEntries[i];
    const marker = entry.marker;
    const trialLinks = markerTrials[entry.id] || [];
    const nctIds = [...new Set(trialLinks.map((t) => t.nct_id))];
    const trialAgents = extractTrialAgents(trials, nctIds);
    totalTrialAgents += trialAgents.length;

    process.stdout.write(`  [${i + 1}/${linkedEntries.length}] ${entry.id} — ${trialAgents.length} trial agents\r`);

    const validated = [];
    const provisional = [];

    for (const agent of trialAgents) {
      let literature;
      if (SKIP_LITERATURE) {
        literature = { validated: true, query: '', pmids: [], articles: [], skipped: true };
      } else {
        literature = await validateLiterature(agent, entry.id, marker, cache);
        if (i % 10 === 0) saveCache(cache);
      }

      const enriched = {
        ...agent,
        literature: {
          validated: literature.validated,
          query: literature.query,
          pmidCount: literature.pmids?.length || 0,
          topArticles: (literature.articles || []).slice(0, 3),
        },
      };

      if (literature.validated) {
        validated.push(enriched);
        totalValidated += 1;
      } else {
        provisional.push(enriched);
      }
    }

    if (validated.length || provisional.length) {
      markerInterventions[entry.id] = {
        markerId: entry.id,
        markerName: marker.name,
        slug: entry.slug,
        condition: entry.condition,
        trialOutcomeCount: trialLinks.length,
        trialAgentCount: trialAgents.length,
        interventions: validated,
        provisional,
        pipeline: 'clinical-trial agents with biomarker outcome → PubMed therapeutic–biomarker pair validation',
      };
    }
  }

  saveCache(cache);

  const payload = {
    generated: new Date().toISOString().slice(0, 10),
    disclaimer: 'Interventions are hypothesis-generating links from trial outcome usage and literature co-occurrence. Not treatment recommendations.',
    literatureSkipped: SKIP_LITERATURE,
    markerCount: Object.keys(markerInterventions).length,
    validatedInterventionCount: totalValidated,
    trialSourcedAgentCount: totalTrialAgents,
    markerInterventions,
  };

  fs.writeFileSync(OUT, JSON.stringify(payload, null, 2), 'utf8');
  patchSearchIndex(markerInterventions);
  console.log(`\nWrote ${OUT}`);
  console.log(`  ${payload.markerCount} markers with intervention data`);
  console.log(`  ${totalTrialAgents} trial-sourced agents → ${totalValidated} literature-validated`);
}

function patchSearchIndex(markerInterventions) {
  const indexPath = path.join(BIOMARKER_DIR, 'search-index.json');
  if (!fs.existsSync(indexPath)) return;

  const index = JSON.parse(fs.readFileSync(indexPath, 'utf8'));
  for (const entry of index.markers || []) {
    const info = markerInterventions[entry.id];
    if (!info) {
      entry.interventions = null;
      continue;
    }
    entry.interventions = {
      count: (info.interventions || []).length,
      agents: (info.interventions || []).slice(0, 6).map((a) => ({
        preferredTerm: a.preferredTerm,
        categories: a.categories || [],
        trialCount: a.nctIds?.length || 0,
        pmidCount: a.literature?.pmidCount || 0,
        topArticle: a.literature?.topArticles?.[0] || null,
      })),
    };
    const agentTerms = (info.interventions || []).map((a) => a.preferredTerm).join(' ').toLowerCase();
    if (agentTerms) {
      entry.searchText = `${entry.searchText || ''} ${agentTerms}`.trim();
    }
  }
  index.generated = new Date().toISOString().slice(0, 10);
  fs.writeFileSync(indexPath, JSON.stringify(index, null, 2), 'utf8');
  console.log(`Patched ${indexPath} with intervention summaries`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});