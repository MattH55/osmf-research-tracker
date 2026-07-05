/**
 * Build a treatment ontology from clinical trial agent labels.
 * Collapses common brand/generic, acronym, casing, route, and spelling variants.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const TRIALS_SRC = path.join(
  'C:', 'Users', 'matth', 'OneDrive', 'Documents', 'OpenSourceMed', 'Opensource Medicine (1)',
  'research-tracker', 'clinical_trials', 'data', 'clinical_trials_current.json'
);
const TRIALS_LOCAL = path.join(ROOT, 'data', 'clinical_trials', 'clinical_trials_current.json');
const OUT = path.join(ROOT, 'data', 'clinical_trials', 'treatment-ontology.json');

const CONDITION_PATTERNS = [
  { label: 'Long COVID / PASC', relation: 'core', re: /\b(long covid|long-covid|long haul covid|post[-\s]?covid|post acute sequelae of sars|pasc|post-acute covid|post covid condition|post covid-19 condition)\b/i },
  { label: 'PACVS / post-vaccination syndrome', relation: 'core', re: /\b(post[-\s]?(acute\s*)?(covid[-\s]?19\s*)?vaccination syndrome|post[-\s]?covid[-\s]?19 vaccine injury|vaccine adverse reaction|post[-\s]?vaccin|pacvs|longvax)\b/i },
  { label: 'ME/CFS', relation: 'adjacent', re: /\b(myalgic encephalomyelitis|chronic fatigue syndrome|me\/cfs|me-cfs|systemic exertion intolerance disease|seid|postviral fatigue syndrome|post-viral fatigue syndrome)\b/i },
  { label: 'POTS / dysautonomia', relation: 'adjacent', re: /\b(postural (orthostatic )?tachycardia syndrome|postural tachycardia syndrome|pots|dysautonomia|orthostatic intolerance)\b/i },
  { label: 'MCAS', relation: 'adjacent', re: /\b(mast cell activation syndrome|mast cell activation disease|mast cell activation disorder|mcas|mcad)\b/i },
  { label: 'Lyme / PTLDS', relation: 'adjacent', re: /\b(lyme|borrelia|post-treatment lyme|ptlds)\b/i },
  { label: 'Gulf War Illness', relation: 'adjacent', re: /\b(gulf war illness|gulf war syndrome|gwi)\b/i },
  { label: 'Other post-viral illness', relation: 'adjacent', re: /\b(post[-\s]?viral|post[-\s]?infectious|q[-\s]?fever|ebv|epstein[-\s]?barr|dengue|chikungunya|parvovirus|mycoplasma|herpes|mononucleosis|viral fatigue)\b/i },
];

const KNOWN_ALIASES = [
  { preferred: 'Paxlovid', aliases: ['paxlovid', 'nirmatrelvir ritonavir', 'nirmatrelvir/ritonavir', 'nirmatrelvir and ritonavir'] },
  { preferred: 'Pembrolizumab', aliases: ['keytruda', 'pembrolizumab'] },
  { preferred: 'Intravenous immunoglobulin', aliases: ['ivig', 'intravenous immunoglobulin', 'igpro20', 'gamunex c', 'gamunex-c'] },
  { preferred: 'N-acetylcysteine', aliases: ['n acetylcysteine', 'n-acetylcysteine', 'nac', 'acetylcysteine'] },
  { preferred: 'Hyperbaric oxygen therapy', aliases: ['hyperbaric oxygen therapy', 'hbot', 'hyperbaric oxygen'] },
  { preferred: 'Low-dose naltrexone', aliases: ['low dose naltrexone', 'low-dose naltrexone', 'ldn'] },
  { preferred: 'Coenzyme Q10', aliases: ['coenzyme q10', 'coq10', 'coq 10'] },
  { preferred: 'Transcranial direct current stimulation', aliases: ['tdcs', 'active tdcs', 'tdcs active', 'tdcs-active', 'transcranial direct current stimulation'] },
  { preferred: 'Transcutaneous auricular vagus nerve stimulation', aliases: ['ta-vns', 'tavns', 'trans auricular vagus nerve stimulation', 'trans-auricular vagus nerve stimulation', 'auricular vagus nerve stimulation'] },
  { preferred: 'Vagus nerve stimulation', aliases: ['vagal stimulation', 'vagus nerve stimulation', 'vns', 'non invasive vagal neurostimulation', 'nvns'] },
  { preferred: 'Stellate ganglion block', aliases: ['stellate ganglion block', 'sgb'] },
  { preferred: 'Normal saline', aliases: ['normal saline', 'iv normal saline', 'intravenous saline', 'iv saline'] },
  { preferred: 'Standard of care', aliases: ['standard of care', 'treatment as usual', 'usual care', 'control group', 'attention control group', 'no physical exercise'] },
  { preferred: 'Cognitive behavioral therapy', aliases: ['cognitive behavioral therapy', 'cbt'] },
  { preferred: 'Acceptance and commitment therapy', aliases: ['acceptance and commitment therapy', 'act', 'balance acceptance and commitment therapy', 'balance act'] },
  { preferred: 'Cognitive rehabilitation', aliases: ['cognitive rehabilitation', 'processing speed training', 'reaction time training'] },
  { preferred: 'Photobiomodulation therapy', aliases: ['photobiomodulation therapy', 'photobiomodulation', 'pbm'] },
  { preferred: 'Inspiratory muscle training', aliases: ['inspiratory muscle training', 'imt'] },
  { preferred: 'Diaphragmatic breathing exercise', aliases: ['diaphragmatic breathing exercise', 'breathing retraining exercises', 'slow paced breathing', 'slow-paced breathing'] },
  { preferred: 'Exercise therapy', aliases: ['exercise', 'exercise training', 'training program', 'physical training', 'rehabilitation program', 'personalized cardiopulmonary rehabilitation', 'cardiac rehabilitation'] },
  { preferred: 'Physiotherapy', aliases: ['physiotherapy', 'physical therapy', 'manual therapy'] },
  { preferred: 'Telerehabilitation', aliases: ['telerehabilitation', 'tele exercise training program', 'tele-exercise training program'] },
  { preferred: 'Dietary intervention', aliases: ['dietary intervention', 'whole diet approach', 'anti inflammatory diet', 'anti-inflammatory diet'] },
  { preferred: 'Probiotics', aliases: ['probiotics', 'directed probiotics', 'synbiotic therapy'] },
  { preferred: 'Melatonin plus zinc', aliases: ['melatonin plus zinc', 'melatonin zinc'] },
  { preferred: 'Vitamin D', aliases: ['vitamin d', 'vitamin d3', 'cholecalciferol'] },
  { preferred: 'Metformin', aliases: ['metformin'] },
  { preferred: 'Fluvoxamine', aliases: ['fluvoxamine'] },
  { preferred: 'Modafinil', aliases: ['modafinil'] },
  { preferred: 'Ivabradine', aliases: ['ivabradine'] },
  { preferred: 'Pyridostigmine', aliases: ['pyridostigmine'] },
  { preferred: 'Rituximab', aliases: ['rituximab'] },
  { preferred: 'Remdesivir', aliases: ['remdesivir'] },
  { preferred: 'Amantadine', aliases: ['amantadine'] },
  { preferred: 'Losartan', aliases: ['losartan'] },
  { preferred: 'Efgartigimod', aliases: ['efgartigimod'] },
  { preferred: 'Droxidopa', aliases: ['droxidopa', 'northera'] },
  { preferred: 'Sodium oxybate', aliases: ['sodium oxybate', 'low sodium oxybate', 'lxb'] },
];

const KNOWN_CATEGORIES = new Map([
  ['Exercise therapy', ['rehabilitation']],
  ['Acceptance and commitment therapy', ['behavioral']],
  ['Cognitive rehabilitation', ['behavioral', 'rehabilitation']],
  ['Transcranial direct current stimulation', ['neuromodulation']],
  ['Transcutaneous auricular vagus nerve stimulation', ['neuromodulation']],
  ['Vagus nerve stimulation', ['neuromodulation']],
  ['Hyperbaric oxygen therapy', ['procedure']],
  ['Intravenous immunoglobulin', ['pharmacologic', 'procedure']],
  ['Normal saline', ['control', 'procedure']],
  ['Standard of care', ['control']],
]);

const EXCLUDED_AGENT_PATTERNS = [
  /\b(blood test|actigraphy|posture study|autonomic function testing|neuromuscular evaluation|maximal effort test)\b/i,
  /\b(exercise capacity test|cardiopulmonary exercise test|exercise test|stress test)\b/i,
  /\b(intervention group|follow up phone calls|follow-up phone calls|transfer package|healthy consultation|healthy consulation)\b/i,
  /^(active|inactive|intervention|comparator|control)$/i,
];

const CATEGORY_PATTERNS = [
  { category: 'pharmacologic', re: /\b(paxlovid|nirmatrelvir|ritonavir|pembrolizumab|fluvoxamine|modafinil|metformin|ivabradine|pyridostigmine|rituximab|remdesivir|amantadine|losartan|efgartigimod|droxidopa|naltrexone|sodium oxybate|sirolimus|clonidine|phenylephrine|ketamine|baricitinib|abrocitinib|anakinra)\b/i },
  { category: 'supplement', re: /\b(nac|acetylcysteine|vitamin|coenzyme|coq10|melatonin|zinc|probiotic|synbiotic|hydrogen water|lithium|bioarginina|arginine)\b/i },
  { category: 'rehabilitation', re: /\b(exercise|rehabilitation|physiotherapy|physical therapy|training|pacing|functional capacity|inspiratory muscle|manual therapy)\b/i },
  { category: 'neuromodulation', re: /\b(tdcs|vagus|vagal|ta-vns|tavns|stimulation|photobiomodulation|brainhq|stellate ganglion block)\b/i },
  { category: 'behavioral', re: /\b(cognitive behavioral|acceptance and commitment|mindfulness|pacing|cognitive rehabilitation|processing speed|reaction time)\b/i },
  { category: 'procedure', re: /\b(immunoadsorption|plasma exchange|saline|infusion|block|acupuncture|counterpressure)\b/i },
  { category: 'dietary', re: /\b(diet|dietary|nutrition|food)\b/i },
  { category: 'device', re: /\b(device|wearable|lighting|counterpulsation|compression|actigraphy)\b/i },
  { category: 'control', re: /\b(placebo|standard of care|treatment as usual|usual care|microcrystalline cellulose|control)\b/i },
];

function loadTrials() {
  const src = fs.existsSync(TRIALS_SRC) ? TRIALS_SRC : TRIALS_LOCAL;
  if (!fs.existsSync(src)) throw new Error(`Trials file not found: ${src}`);
  return JSON.parse(fs.readFileSync(src, 'utf8')).trials || [];
}

function classifyTrial(trial) {
  const labels = new Set();
  let relation = 'unrelated';
  const raw = [
    trial.title,
    trial.brief_summary,
    ...(trial.conditions_raw || []),
    ...(trial.mapped_conditions || []),
  ].filter(Boolean).join(' | ');

  for (const { label, relation: patternRelation, re } of CONDITION_PATTERNS) {
    if (!re.test(raw)) continue;
    labels.add(label);
    if (patternRelation === 'core') relation = 'core';
    if (patternRelation === 'adjacent' && relation !== 'core') relation = 'adjacent';
  }

  if (!labels.size) {
    for (const c of trial.mapped_conditions || []) labels.add(c);
    if (!labels.size) labels.add('Unrelated / other');
  }

  return { conditions: [...labels], relation };
}

function cleanLabel(label) {
  return (label || '')
    .replace(/\u00c2/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function key(label) {
  return cleanLabel(label)
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/\+/g, ' plus ')
    .replace(/\([^)]*\)/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\b(active|inactive|sham|placebo|high|low|intensity|group|arm|intervention|comparator)\b/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function slugify(text) {
  return key(text).replace(/\s+/g, '-').replace(/^-|-$/g, '') || 'unspecified';
}

function titleCase(text) {
  const keepUpper = new Set(['IVIG', 'NAC', 'HBOT', 'LDN', 'Q10', 'ACT', 'CBT']);
  return cleanLabel(text)
    .split(/\s+/)
    .map((word) => {
      const up = word.toUpperCase();
      if (keepUpper.has(up)) return up;
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    })
    .join(' ');
}

function addValue(out, seen, value) {
  const clean = cleanLabel(value);
  if (!clean) return;
  const k = key(clean);
  if (!k || /^\d+$/.test(k)) return;
  if (!k || seen.has(k)) return;
  seen.add(k);
  out.push(clean);
}

function extractSynonyms(label) {
  const out = [];
  const seen = new Set();
  const clean = cleanLabel(label);
  addValue(out, seen, clean);

  const base = clean.replace(/\([^)]*\)/g, ' ');
  addValue(out, seen, base);

  const parens = clean.match(/\(([^)]+)\)/g) || [];
  for (const p of parens) {
    const inner = p.replace(/[()]/g, '');
    addValue(out, seen, inner);
    for (const part of inner.split(/[;/,+]| and /i)) addValue(out, seen, part);
  }

  for (const part of clean.split(/[;]| and /i)) addValue(out, seen, part);
  return out;
}

function knownPreferred(agentKey) {
  for (const item of KNOWN_ALIASES) {
    if (item.aliases.some((alias) => key(alias) === agentKey)) return item.preferred;
  }
  return null;
}

function canonicalAgent(label) {
  const k = key(label);
  const known = knownPreferred(k);
  if (known) return known;

  for (const item of KNOWN_ALIASES) {
    if (item.aliases.some((alias) => k.includes(key(alias)))) return item.preferred;
  }

  const noParen = cleanLabel(label).replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();
  return titleCase(noParen || label);
}

function categorize(preferred, synonyms) {
  if (KNOWN_CATEGORIES.has(preferred)) return KNOWN_CATEGORIES.get(preferred);
  const text = [preferred, ...synonyms].join(' ');
  const categories = CATEGORY_PATTERNS.filter(({ re }) => re.test(text)).map(({ category }) => category);
  return [...new Set(categories)].sort();
}

function buildOntology(trials) {
  const termMap = new Map();

  for (const trial of trials) {
    const { conditions, relation } = classifyTrial(trial);

    for (const rawAgent of trial.agents || []) {
      if (EXCLUDED_AGENT_PATTERNS.some((re) => re.test(rawAgent))) continue;
      const preferredTerm = canonicalAgent(rawAgent);
      const id = `treatment:${slugify(preferredTerm)}`;
      if (!termMap.has(id)) {
        termMap.set(id, {
          id,
          preferredTerm,
          synonyms: [],
          rawAgentTerms: [],
          categories: [],
          trialCount: 0,
          nctIds: [],
          trials: [],
          conditions: [],
          relationCounts: { core: 0, adjacent: 0, unrelated: 0 },
          source: 'ClinicalTrials.gov trial agent labels',
          _synSeen: new Set(),
          _rawSeen: new Set(),
          _nctSeen: new Set(),
          _conditionSeen: new Set(),
        });
      }

      const term = termMap.get(id);
      addValue(term.synonyms, term._synSeen, preferredTerm);
      for (const synonym of extractSynonyms(rawAgent)) addValue(term.synonyms, term._synSeen, synonym);
      addValue(term.rawAgentTerms, term._rawSeen, rawAgent);

      if (!term._nctSeen.has(trial.nct_id)) {
        term._nctSeen.add(trial.nct_id);
        term.nctIds.push(trial.nct_id);
        term.trials.push({
          nct_id: trial.nct_id,
          title: trial.title,
          status: trial.status,
          phase: trial.phase,
          link: trial.link || `https://clinicaltrials.gov/study/${trial.nct_id}`,
          conditions,
          relation,
          start_date: trial.start_date,
          completion_date: trial.completion_date,
          last_updated: trial.last_updated,
        });
        term.relationCounts[relation] = (term.relationCounts[relation] || 0) + 1;
      }
      for (const condition of conditions) {
        if (!term._conditionSeen.has(condition)) {
          term._conditionSeen.add(condition);
          term.conditions.push(condition);
        }
      }
    }
  }

  const terms = [...termMap.values()].map((term) => {
    term.trialCount = term.nctIds.length;
    term.categories = categorize(term.preferredTerm, term.synonyms);
    if (!term.categories.length) term.categories = ['other'];
    delete term._synSeen;
    delete term._rawSeen;
    delete term._nctSeen;
    delete term._conditionSeen;
    return term;
  });

  terms.sort((a, b) => b.trialCount - a.trialCount || a.preferredTerm.localeCompare(b.preferredTerm));
  return terms;
}

function main() {
  const trials = loadTrials();
  const terms = buildOntology(trials);
  const payload = {
    generated: new Date().toISOString().slice(0, 10),
    trialCount: trials.length,
    termCount: terms.length,
    terms,
  };

  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, JSON.stringify(payload, null, 2), 'utf8');
  console.log(`Wrote ${OUT}`);
  console.log(`  ${terms.length} treatment ontology terms`);
}

main();
