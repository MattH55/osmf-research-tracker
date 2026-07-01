/**
 * Canonical therapeutic agent labels from clinical trial arm descriptions.
 * Shared by treatment ontology and biomarker intervention linking.
 */

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
  { preferred: 'Immulina', aliases: ['immulina', 'immulina tm', 'immulina supplements'] },
  { preferred: 'Baricitinib', aliases: ['baricitinib', 'olumiant'] },
  { preferred: 'Anakinra', aliases: ['anakinra', 'kineret'] },
];

const EXCLUDED_AGENT_PATTERNS = [
  /\b(blood test|actigraphy|posture study|autonomic function testing|neuromuscular evaluation|maximal effort test)\b/i,
  /\b(exercise capacity test|cardiopulmonary exercise test|exercise test|stress test)\b/i,
  /\b(intervention group|follow up phone calls|follow-up phone calls|transfer package|healthy consultation|healthy consulation)\b/i,
  /^(active|inactive|intervention|comparator|control|sham|placebo)$/i,
  /\b(observation|monitoring|questionnaire|survey|assessment only)\b/i,
];

const CATEGORY_PATTERNS = [
  { category: 'pharmacologic', re: /\b(paxlovid|nirmatrelvir|ritonavir|pembrolizumab|fluvoxamine|modafinil|metformin|ivabradine|pyridostigmine|rituximab|remdesivir|amantadine|losartan|efgartigimod|droxidopa|naltrexone|sodium oxybate|sirolimus|clonidine|phenylephrine|ketamine|baricitinib|abrocitinib|anakinra)\b/i },
  { category: 'supplement', re: /\b(nac|acetylcysteine|vitamin|coenzyme|coq10|melatonin|zinc|probiotic|synbiotic|hydrogen water|lithium|bioarginina|arginine|immulina)\b/i },
  { category: 'rehabilitation', re: /\b(exercise|rehabilitation|physiotherapy|physical therapy|training|pacing|functional capacity|inspiratory muscle|manual therapy)\b/i },
  { category: 'neuromodulation', re: /\b(tdcs|vagus|vagal|ta-vns|tavns|stimulation|photobiomodulation|brainhq|stellate ganglion block)\b/i },
  { category: 'behavioral', re: /\b(cognitive behavioral|acceptance and commitment|mindfulness|pacing|cognitive rehabilitation|processing speed|reaction time)\b/i },
  { category: 'procedure', re: /\b(immunoadsorption|plasma exchange|saline|infusion|block|acupuncture|counterpressure)\b/i },
  { category: 'dietary', re: /\b(diet|dietary|nutrition|food)\b/i },
  { category: 'device', re: /\b(device|wearable|lighting|counterpulsation|compression|actigraphy)\b/i },
  { category: 'control', re: /\b(placebo|standard of care|treatment as usual|usual care|microcrystalline cellulose|control)\b/i },
];

function cleanLabel(label) {
  return (label || '')
    .replace(/\u00c2/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function agentKey(label) {
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
  return agentKey(text).replace(/\s+/g, '-').replace(/^-|-$/g, '') || 'unspecified';
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

function knownPreferred(agentKeyValue) {
  for (const item of KNOWN_ALIASES) {
    if (item.aliases.some((alias) => agentKey(alias) === agentKeyValue)) return item.preferred;
  }
  return null;
}

function canonicalAgent(label) {
  const k = agentKey(label);
  const known = knownPreferred(k);
  if (known) return known;

  for (const item of KNOWN_ALIASES) {
    if (item.aliases.some((alias) => k.includes(agentKey(alias)))) return item.preferred;
  }

  const noParen = cleanLabel(label).replace(/\([^)]*\)/g, ' ').replace(/\s+/g, ' ').trim();
  return titleCase(noParen || label);
}

function isExcludedAgent(label) {
  return EXCLUDED_AGENT_PATTERNS.some((re) => re.test(label));
}

function categorize(preferred, synonyms = []) {
  const text = [preferred, ...synonyms].join(' ');
  return [...new Set(
    CATEGORY_PATTERNS.filter(({ re }) => re.test(text)).map(({ category }) => category)
  )].sort();
}

function treatmentId(preferred) {
  return `treatment:${slugify(preferred)}`;
}

module.exports = {
  KNOWN_ALIASES,
  EXCLUDED_AGENT_PATTERNS,
  canonicalAgent,
  isExcludedAgent,
  categorize,
  treatmentId,
  agentKey,
  slugify,
};