/**
 * Patch Research Tracker agents.html to collapse treatment synonyms via treatment ontology.
 */
const fs = require('fs');
const path = require('path');

const TRACKER_ROOT = path.join(
  'C:', 'Users', 'matth', 'OneDrive', 'Documents', 'OpenSourceMed', 'Opensource Medicine (1)',
  'research-tracker'
);
const AGENTS_HTML = path.join(TRACKER_ROOT, 'agents.html');

const CSS = `
    .agent { border: 1px solid #e5e7eb; border-radius: 10px; padding: 14px; margin-bottom: 12px; background: #fff; }
    .agent-name { font-weight: 700; font-size: 1rem; color: var(--primary-dark); }
    .agent-synonyms { margin-top: 0.25rem; font-size: 0.78rem; color: #64748b; }
    .trial-legend { display:flex; flex-wrap:wrap; gap:0.45rem; margin:0.75rem 0 1rem; font-size:0.76rem; color:#475569; }
    .legend-chip { display:inline-flex; align-items:center; gap:0.25rem; border:1px solid #e5e7eb; border-radius:999px; padding:0.2rem 0.5rem; background:#fff; }
    .agent-trials { display:flex; flex-wrap:wrap; gap:0.35rem; margin-top:0.4rem; }
    .trial-chip { display:inline-flex; align-items:center; gap:0.25rem; font-size:0.7rem; font-weight:650; padding:0.18rem 0.48rem; border-radius:5px; text-decoration:none; border:1px solid transparent; font-family:ui-monospace, SFMono-Regular, Menlo, monospace; }
    .trial-rel-core { background:#fff7ed; color:#9a3412; border-color:#fed7aa; }
    .trial-rel-adjacent { background:#ecfdf5; color:#047857; border-color:#a7f3d0; }
    .trial-rel-unrelated { background:#f8fafc; color:#475569; border-color:#cbd5e1; }
    .trial-stage-completed { color:#111827; }
    .trial-stage-progress { color:#6b7280; }
    .trial-stage-recruiting { border-style:dotted; border-width:2px; }
    .trial-stage-cancelled { text-decoration:line-through; opacity:0.62; }
    .trial-stage-cancelled::before { content:'x'; font-weight:800; margin-right:0.1rem; }
    .relation-counts { display:flex; flex-wrap:wrap; gap:0.3rem; margin-top:0.35rem; }
    .relation-counts span { font-size:0.68rem; border-radius:999px; padding:0.12rem 0.45rem; }
    .literature-layer { margin-top:0.45rem; border-top:1px solid #eef2f7; padding-top:0.45rem; }
    .lit-chips { display:flex; flex-wrap:wrap; gap:0.3rem; margin-top:0.25rem; }
    .lit-chip { display:inline-flex; align-items:center; gap:0.2rem; font-size:0.68rem; font-weight:650; border-radius:999px; padding:0.14rem 0.45rem; border:1px solid #e5e7eb; background:#fff; color:#334155; }
    .lit-review { background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe; }
    .lit-meta-analysis { background:#f5f3ff; color:#6d28d9; border-color:#ddd6fe; }
    .lit-clinical-study { background:#ecfdf5; color:#047857; border-color:#a7f3d0; }
    .lit-experimental-in-vivo { background:#fff7ed; color:#9a3412; border-color:#fed7aa; }
    .lit-experimental-in-vitro { background:#fefce8; color:#854d0e; border-color:#fde68a; }
    .lit-mechanistic { background:#f0fdfa; color:#0f766e; border-color:#99f6e4; }
    .lit-other { background:#f8fafc; color:#475569; border-color:#cbd5e1; }
    .literature-list { margin-top:0.35rem; display:flex; flex-direction:column; gap:0.28rem; }
    .literature-item { font-size:0.75rem; color:#475569; line-height:1.45; }
    .literature-item a { color:var(--primary-dark); font-weight:600; text-decoration:none; }
    .literature-item a:hover { color:var(--accent-orange); }
    .summary-table td, .summary-table th { font-size: 0.85rem; padding:0.35rem 0.5rem; border-bottom:1px solid #eef2f7; text-align:left; }
    /* OSMF design-system layer (navy/orange tokens from css/osmf-ui.css) */
    .ag-cta { max-width:1200px; margin:32px auto 0; padding:0 var(--ui-gutter, 24px); box-sizing:border-box; }
    .ag-cta__in { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px 24px; padding:18px 22px; background:var(--ui-bg-warm, #fffaf2); border:1px solid #f5dcb0; border-left:4px solid var(--ui-accent, #ff9800); border-radius:14px; font-size:15px; line-height:1.6; color:var(--ui-ink-2, #2a3160); }
    .ag-cta__in strong { color:var(--ui-ink, #0e1444); }
    .ag-cta__in span { flex:1 1 420px; min-width:0; }
    .ag-cta__btn { flex:none; display:inline-flex; align-items:center; gap:6px; background:var(--ui-ink, #0e1444); color:#fff !important; text-decoration:none !important; font-weight:600; font-size:14px; padding:10px 18px; border-radius:999px; white-space:nowrap; }
    .ag-cta__btn:hover { background:var(--ui-navy-700, #18206a); }
    body .main-section { padding:56px 0 24px; background:#fff; }
    body .main-section .section-inner { max-width:1200px; margin:0 auto; padding:0 var(--ui-gutter, 24px); box-sizing:border-box; }
    .main-section h2 { font-size:clamp(24px, 3vw, 30px); margin:0 0 12px; color:var(--ui-ink, #0e1444); }
    .main-section h3.ag-h3 { font-size:13px; letter-spacing:.1em; text-transform:uppercase; color:var(--ui-muted, #6b7194); font-weight:700; margin:0 0 10px; }
    #exec-summary { max-width:72ch; font-size:16.5px; line-height:1.7; color:var(--ui-text, #3d4466); }
    #exec-summary strong { color:var(--ui-ink, #0e1444); }
    #stats-row { display:grid; grid-template-columns:repeat(auto-fit, minmax(170px, 1fr)); gap:14px; margin:28px 0 44px; }
    #stats-row .osmf-stat { padding:18px 20px; }
    .ag-tables { display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1.6fr); gap:28px; align-items:start; }
    .ag-scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:14px; }
    table.summary-table { width:100%; border-collapse:separate; border-spacing:0; background:#fff; border:1px solid var(--ui-line, #e6e8f2); border-radius:14px; overflow:hidden; box-shadow:var(--ui-shadow-1); margin:0; }
    table.summary-table th { font-size:11.5px; letter-spacing:.08em; text-transform:uppercase; font-weight:700; color:var(--ui-muted, #6b7194); background:var(--ui-bg-soft, #f7f8fc); padding:11px 14px; border-bottom:1px solid var(--ui-line, #e6e8f2); text-align:left; white-space:nowrap; }
    table.summary-table td { font-size:14px; padding:11px 14px; border-bottom:1px solid var(--ui-line, #e6e8f2); color:var(--ui-ink-2, #2a3160); text-align:left; }
    table.summary-table tr:last-child td { border-bottom:0; }
    .ag-note { margin:28px 0 0; max-width:none; }
    .ag-rule { border:0; height:1px; background:var(--ui-line, #e6e8f2); margin:48px 0 32px; }
    .ag-filters { display:flex; flex-wrap:wrap; gap:10px; align-items:center; padding:16px; background:var(--ui-bg-soft, #f7f8fc); border:1px solid var(--ui-line, #e6e8f2); border-radius:14px; margin:0 0 12px; }
    .ag-filters input { flex:1 1 240px; min-width:0; }
    .ag-filters select { flex:0 1 auto; min-width:0; }
    #meta { font-size:13px; color:var(--ui-muted, #6b7194); margin:0 0 16px; }
    .agent { border:1px solid var(--ui-line, #e6e8f2); border-radius:14px; padding:20px 22px; margin-bottom:14px; background:#fff; box-shadow:var(--ui-shadow-1); }
    .agent-name { font-size:18px; letter-spacing:-.01em; color:var(--ui-ink, #0e1444); margin-bottom:4px; }
    .agent-synonyms { font-size:13px; color:var(--ui-muted, #6b7194); line-height:1.55; }
    .agent .meta { font-size:13.5px; line-height:1.6; color:var(--ui-text, #3d4466); margin-top:6px; }
    .agent .meta strong, .literature-layer > strong { color:var(--ui-ink, #0e1444); font-weight:600; }
    .agent .agent-notes { background:var(--ui-bg-soft, #f7f8fc); border-radius:10px; padding:10px 12px; margin-top:10px; }
    .agent .agent-foot { font-size:12px; color:var(--ui-muted, #6b7194); }
    .literature-layer { margin-top:12px; border-top:1px solid var(--ui-line, #e6e8f2); padding-top:12px; font-size:13.5px; }
    .literature-item { font-size:13px; }
    .literature-item a { color:var(--ui-link, #2f45c4); }
    .trial-legend { font-size:12px; margin:0 0 16px; }
    .lit-review { background:var(--ui-down-bg, #eaf0ff); color:var(--ui-down, #1d4ed8); border-color:#cfdcff; }
    .lit-meta-analysis { background:#eef0fb; color:var(--ui-ink-2, #2a3160); border-color:var(--ui-line-2, #d5d9ea); }
    @media (max-width: 860px) { .ag-tables { grid-template-columns:1fr; } }
    @media (max-width: 600px) { .ag-cta__btn { width:100%; justify-content:center; } .agent { padding:16px; } }
`;

const SCRIPT = `<script>
let allAgents = [];
let treatmentOntology = { terms: [] };
let renderedAgents = [];

function escape(str) {
  if (!str) return '';
  return String(str).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[m]);
}

function normKey(str) {
  return String(str || '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/\\+/g, ' plus ')
    .replace(/\\([^)]*\\)/g, ' ')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\\b(active|inactive|sham|placebo|high|low|intensity|group|arm|intervention|comparator)\\b/g, ' ')
    .replace(/\\s+/g, ' ')
    .trim();
}

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url + ' HTTP ' + res.status);
  return res.json();
}

async function loadOntology() {
  try {
    return await fetchJson('./data/clinical_trials/treatment-ontology.json');
  } catch (err) {
    await new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'js/generated/treatment-ontology.bundle.js';
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
    return window.__TREATMENT_ONTOLOGY__ || { terms: [] };
  }
}

async function load() {
  const metaEl = document.getElementById('meta');
  const listEl = document.getElementById('list');

  try {
    const [data, ontology] = await Promise.all([
      fetchJson('./data/therapeutic_agents.json'),
      loadOntology(),
    ]);
    allAgents = data.agents || [];
    treatmentOntology = ontology || { terms: [] };
    renderedAgents = collapseAgents(allAgents, treatmentOntology.terms || []);

    metaEl.textContent =
      'Last updated: ' + new Date(data.last_updated).toLocaleDateString() +
      ' - ' + renderedAgents.length + ' collapsed treatment concepts from ' + allAgents.length + ' source agent rows';

    renderSummary(data, renderedAgents);
    populateFilters(renderedAgents);
    filter();
  } catch (err) {
    console.error('Failed to load agents data:', err);
    metaEl.innerHTML = '<span style="color:#b91c1c;">Failed to load data.</span>';
    if (listEl) listEl.innerHTML = '<div style="padding:12px; border:1px solid #fee2e2; background:#fef2f2; color:#991b1b;">Could not load therapeutic agent data or ontology.</div>';
  }
}

function ontologyIndexes(terms) {
  const bySynonym = new Map();
  const byNct = new Map();
  for (const term of terms) {
    [term.preferredTerm, ...(term.synonyms || []), ...(term.rawAgentTerms || [])].forEach(s => {
      const k = normKey(s);
      if (k && !bySynonym.has(k)) bySynonym.set(k, term);
    });
    (term.nctIds || []).forEach(nct => {
      if (!byNct.has(nct)) byNct.set(nct, []);
      byNct.get(nct).push(term);
    });
  }
  return { bySynonym, byNct };
}

function findOntologyTerm(agent, indexes) {
  const name = agent['Therapeutic Agent'] || agent.name || '';
  const direct = indexes.bySynonym.get(normKey(name));
  if (direct) return direct;

  const hits = new Map();
  (agent.trials || []).forEach(t => {
    (indexes.byNct.get(t.nct_id) || []).forEach(term => hits.set(term.id, term));
  });
  if (hits.size === 1) return [...hits.values()][0];
  return null;
}

function evidenceRank(level) {
  return { Strong: 5, Moderate: 4, Preliminary: 3, Anecdotal: 2, Theoretical: 1 }[level] || 3;
}

function mergeUnique(arr, values) {
  const seen = new Set(arr.map(normKey));
  (values || []).forEach(v => {
    const k = normKey(v);
    if (k && !seen.has(k)) {
      seen.add(k);
      arr.push(v);
    }
  });
}

function mergeTrials(existing, trials) {
  const seen = new Set(existing.map(t => t.nct_id));
  (trials || []).forEach(t => {
    if (!t.nct_id || seen.has(t.nct_id)) return;
    seen.add(t.nct_id);
    existing.push(t);
  });
}

function studyKey(study) {
  return [study.pmid || '', study.title || '', study.excerpt || '', study.source || '', study.source_page || ''].join('|').toLowerCase();
}

function mergeStudies(existing, studies) {
  const seen = new Set(existing.map(studyKey));
  (studies || []).forEach(s => {
    const k = studyKey(s);
    if (!k || seen.has(k)) return;
    seen.add(k);
    existing.push({
      ...s,
      literatureCategory: classifyLiterature(s),
    });
  });
}

function classifyLiterature(study) {
  const text = [study.title, study.excerpt, study.source, study.source_page].filter(Boolean).join(' ').toLowerCase();
  if (/meta[- ]analysis|systematic review|pooled analysis|umbrella review/.test(text)) return 'meta-analysis';
  if (/review|narrative review|scoping review/.test(text)) return 'review';
  if (/randomi[sz]ed|double[- ]blind|placebo|clinical trial|phase\\s*[1-4]|cohort|case[- ]control|case report|case series|observational|prospective|retrospective|pilot study|open[- ]label|cross[- ]over|crossover|n\\s*=|patients?|participants?/.test(text)) return 'clinical-study';
  if (/in vivo|mouse|mice|rat|murine|animal model|xenograft|zebrafish/.test(text)) return 'experimental-in-vivo';
  if (/in vitro|cell culture|pbmc|cell line|organoid|ex vivo|assay|western blot|elisa/.test(text)) return 'experimental-in-vitro';
  if (/mechanistic|pathway|biomarker|metabolomic|proteomic|transcriptomic|cytokine|mitochondrial|immune/.test(text)) return 'mechanistic';
  return 'other';
}

function literatureLabel(category) {
  return {
    'review': 'Review article',
    'meta-analysis': 'Meta-analysis',
    'clinical-study': 'Clinical study',
    'experimental-in-vivo': 'Experimental in vivo',
    'experimental-in-vitro': 'Experimental in vitro',
    'mechanistic': 'Mechanistic / biomarker',
    'other': 'Other literature',
  }[category] || 'Other literature';
}

function literatureCounts(studies) {
  const counts = {};
  (studies || []).forEach(s => {
    const cat = s.literatureCategory || classifyLiterature(s);
    counts[cat] = (counts[cat] || 0) + 1;
  });
  return counts;
}

function collapseAgents(agents, ontologyTerms) {
  const indexes = ontologyIndexes(ontologyTerms);
  const out = new Map();

  agents.forEach(agent => {
    const term = findOntologyTerm(agent, indexes);
    const fallbackName = agent['Therapeutic Agent'] || agent.name || 'Unknown';
    const id = term?.id || 'agent:' + normKey(fallbackName);
    if (!out.has(id)) {
      out.set(id, {
        id,
        name: term?.preferredTerm || fallbackName,
        ontology: term || null,
        sourceAgents: [],
        conditions: [],
        tags: [],
        mechanisms: [],
        studies: [],
        trials: [],
        aliases: [],
        evidence: 'Preliminary',
        notes: [],
        refs: [],
        updated: '',
      });
    }
    const rec = out.get(id);
    rec.sourceAgents.push(agent);
    mergeUnique(rec.conditions, (agent['Primary Conditions'] || agent.conditions || []).map(collapseCondition));
    mergeUnique(rec.tags, [...(agent.types || []), ...(agent.trial_types || []), ...(agent.trial_sizes || [])]);
    mergeUnique(rec.mechanisms, agent.mechanisms || []);
    mergeUnique(rec.aliases, [fallbackName, ...(agent.aliases || []), ...(term?.synonyms || []).slice(0, 20)]);
    mergeUnique(rec.refs, Array.isArray(agent['Key Studies / References']) ? agent['Key Studies / References'] : [agent['Key Studies / References']].filter(Boolean));
    mergeUnique(rec.notes, [agent['Clinical Notes']].filter(Boolean));
    mergeStudies(rec.studies, agent.studies || []);
    mergeTrials(rec.trials, agent.trials || []);
    mergeTrials(rec.trials, term?.trials || []);
    if (evidenceRank(agent['Evidence Level']) > evidenceRank(rec.evidence)) rec.evidence = agent['Evidence Level'];
    rec.updated = agent['Last Updated'] || rec.updated;
  });

  return [...out.values()].sort((a, b) => b.trials.length - a.trials.length || a.name.localeCompare(b.name));
}

function getEvClass(level) {
  const l = (level || '').trim();
  if (l === 'Strong') return 'ev-Strong';
  if (l === 'Moderate') return 'ev-Moderate';
  if (l === 'Preliminary') return 'ev-Preliminary';
  if (l === 'Anecdotal') return 'ev-Anecdotal';
  if (l === 'Theoretical') return 'ev-Theoretical';
  return 'ev-Preliminary';
}

function collapseCondition(c) {
  const r = (c || '').toLowerCase();
  if (r.includes('pacvs') || r.includes('vaccin') || r.includes('longvax')) return 'PACVS';
  if (r.includes('long covid') || r.includes('pasc') || r.includes('post-covid')) return 'Long COVID';
  if (r.includes('me/cfs') || r.includes('chronic fatigue') || r.includes('myalgic')) return 'ME/CFS';
  if (r.includes('gulf')) return 'Gulf War Illness';
  if (r.includes('lyme') || r.includes('ptlds')) return 'Lyme';
  if (r.includes('mcas') || r.includes('mast cell')) return 'MCAS';
  if (r.includes('pots') || r.includes('dysautonomia') || r.includes('orthostatic')) return 'POTS';
  if (r.includes('post-infectious') || r.includes('post-viral') || r.includes('q-fever') || r.includes('ebv') || r.includes('dengue') || r.includes('chikungunya') || r.includes('parvovirus') || r.includes('mycoplasma') || r.includes('herpes')) return 'Other Post-Viral';
  return c || 'Other';
}

function relationForTrial(t) {
  if (t.relation) return t.relation;
  const text = [...(t.conditions || []), t.title || ''].join(' ').toLowerCase();
  if (text.includes('long covid') || text.includes('pasc') || text.includes('pacvs') || text.includes('vaccin')) return 'core';
  if (text.includes('me/cfs') || text.includes('chronic fatigue') || text.includes('lyme') || text.includes('pots') || text.includes('mcas') || text.includes('gulf war') || text.includes('post-viral') || text.includes('post-infectious')) return 'adjacent';
  return 'unrelated';
}

function stageForStatus(status) {
  const s = String(status || '').toUpperCase();
  if (s === 'COMPLETED') return 'completed';
  if (s.includes('RECRUITING')) return 'recruiting';
  if (['TERMINATED', 'WITHDRAWN', 'SUSPENDED'].includes(s)) return 'cancelled';
  return 'progress';
}

function trialChip(t) {
  const rel = relationForTrial(t);
  const stage = stageForStatus(t.status);
  const href = t.link || ('https://clinicaltrials.gov/study/' + t.nct_id);
  const title = [t.title, t.status, (t.conditions || []).join(', ')].filter(Boolean).join(' - ');
  return '<a class="trial-chip trial-rel-' + rel + ' trial-stage-' + stage + '" href="' + href + '" target="_blank" rel="noopener" title="' + escape(title) + '">' + escape(t.nct_id || 'Trial') + '</a>';
}

function renderSummary(data, agents) {
  const total = agents.length;
  const withTrials = agents.filter(a => a.trials.length).length;
  const totalAssoc = agents.reduce((n, a) => n + a.trials.length, 0);
  const condCounts = {};
  agents.forEach(a => a.conditions.forEach(c => { condCounts[c] = (condCounts[c] || 0) + 1; }));

  const topNames = agents.filter(x => x.trials.length).slice(0,5).map(x => x.name.split('(')[0].trim());
  document.getElementById('exec-summary').innerHTML =
    'This resource tracks <strong>' + total + ' collapsed therapeutic concepts</strong> after synonym normalization. ' +
    '<strong>' + withTrials + ' concepts</strong> are linked to registered clinical trials (<strong>' + totalAssoc + ' total trial associations</strong>). ' +
    'Trial colors distinguish Long COVID/PACVS, adjacent disease, and unrelated evidence; text/outline styling shows trial stage. Strongest trial-linked concepts include ' +
    topNames.slice(0,3).join(', ') + (topNames.length > 3 ? ' and others.' : '.');

  document.getElementById('stats-row').innerHTML =
    '<div class="stat osmf-card osmf-stat"><b>' + total + '</b><span>Collapsed concepts</span></div>' +
    '<div class="stat osmf-card osmf-stat"><b>' + allAgents.length + '</b><span>Source rows</span></div>' +
    '<div class="stat osmf-card osmf-stat"><b>' + withTrials + '</b><span>Concepts with trials</span></div>' +
    '<div class="stat osmf-card osmf-stat"><b>' + totalAssoc + '</b><span>Trial associations</span></div>' +
    '<div class="stat osmf-card osmf-stat"><b>' + (treatmentOntology.terms || []).length + '</b><span>Ontology terms</span></div>';

  let ch = '<tr><th>Condition</th><th>Concepts</th></tr>';
  Object.entries(condCounts).sort((a,b) => b[1] - a[1]).forEach(([c,n]) => {
    ch += '<tr><td>' + escape(c) + '</td><td>' + n + '</td></tr>';
  });
  document.getElementById('cond-table').innerHTML = ch;

  let th = '<tr><th>Treatment concept</th><th># Trials</th><th>Evidence Level</th></tr>';
  agents.slice(0,8).forEach(item => {
    th += '<tr><td>' + escape(item.name) + '</td><td>' + item.trials.length + '</td><td><span class="ev-pill ' + getEvClass(item.evidence) + '">' + escape(item.evidence) + '</span></td></tr>';
  });
  document.getElementById('top-table').innerHTML = th;
}

function populateFilters(agents) {
  const condSet = new Set(), tagSet = new Set(), litSet = new Set();
  agents.forEach(a => {
    a.conditions.forEach(c => condSet.add(c));
    a.tags.forEach(t => tagSet.add(t));
    a.mechanisms.forEach(m => tagSet.add(m));
    a.studies.forEach(s => litSet.add(s.literatureCategory || classifyLiterature(s)));
  });
  const csel = document.getElementById('condition');
  csel.innerHTML = '<option value="">All Conditions</option>';
  [...condSet].sort().forEach(c => {
    const o = document.createElement('option'); o.value = c; o.textContent = c; csel.appendChild(o);
  });
  const tsel = document.getElementById('tag');
  tsel.innerHTML = '<option value="">All Tags</option>';
  [...tagSet].sort().forEach(t => {
    const o = document.createElement('option'); o.value = t; o.textContent = t; tsel.appendChild(o);
  });
  const lsel = document.getElementById('litType');
  if (lsel) {
    lsel.innerHTML = '<option value="">All Literature</option>';
    [...litSet].sort().forEach(t => {
      const o = document.createElement('option'); o.value = t; o.textContent = literatureLabel(t); lsel.appendChild(o);
    });
  }
}

function filter() {
  const term = (document.getElementById('search').value || '').toLowerCase();
  const cond = document.getElementById('condition').value;
  const tag = document.getElementById('tag').value;
  const litType = document.getElementById('litType')?.value || '';

  const filtered = renderedAgents.filter(a => {
    const litHay = a.studies.map(s => [s.title, s.excerpt, s.pmid, s.source, s.source_page, literatureLabel(s.literatureCategory)].join(' ')).join(' ');
    const hay = [a.name, ...a.conditions, ...a.tags, ...a.mechanisms, ...a.aliases, litHay].join(' ').toLowerCase();
    return (!term || hay.includes(term)) &&
      (!cond || a.conditions.includes(cond)) &&
      (!tag || a.tags.includes(tag) || a.mechanisms.includes(tag)) &&
      (!litType || a.studies.some(s => (s.literatureCategory || classifyLiterature(s)) === litType));
  });
  render(filtered);
}

function render(list) {
  const el = document.getElementById('list');
  el.innerHTML = '<div class="trial-legend">' +
    '<span class="legend-chip trial-rel-core">Long COVID / PACVS</span>' +
    '<span class="legend-chip trial-rel-adjacent">Adjacent disease</span>' +
    '<span class="legend-chip trial-rel-unrelated">Unrelated trial</span>' +
    '<span class="legend-chip trial-stage-completed">Completed</span>' +
    '<span class="legend-chip trial-stage-progress">In progress</span>' +
    '<span class="legend-chip trial-stage-recruiting">Recruiting dotted</span>' +
    '<span class="legend-chip trial-stage-cancelled">Cancelled/suspended</span>' +
  '</div>';

  list.forEach(a => {
    const div = document.createElement('div');
    div.className = 'agent';
    const evPill = '<span class="ev-pill ' + getEvClass(a.evidence) + '">' + escape(a.evidence) + '</span>';
    const syns = a.aliases.filter(s => normKey(s) !== normKey(a.name)).slice(0,8);
    const rel = a.ontology?.relationCounts || { core: 0, adjacent: 0, unrelated: 0 };
    const litCounts = literatureCounts(a.studies);
    const litChips = Object.entries(litCounts)
      .sort((a,b) => b[1] - a[1])
      .map(([cat, n]) => '<span class="lit-chip lit-' + cat + '">' + escape(literatureLabel(cat)) + ' ' + n + '</span>')
      .join('');
    const litItems = a.studies.slice(0,5).map(s => {
      const href = s.pmid ? 'https://pubmed.ncbi.nlm.nih.gov/' + s.pmid + '/' : '';
      const label = escape((s.title || s.excerpt || 'Literature item').slice(0, 180));
      const prefix = '<span class="lit-chip lit-' + (s.literatureCategory || classifyLiterature(s)) + '">' + escape(literatureLabel(s.literatureCategory || classifyLiterature(s))) + '</span> ';
      return '<div class="literature-item">' + prefix + (href ? '<a href="' + href + '" target="_blank" rel="noopener">' + label + '</a>' : label) + (s.pub_date ? ' (' + escape(s.pub_date) + ')' : '') + '</div>';
    }).join('');
    const relHtml = '<div class="relation-counts">' +
      '<span class="trial-rel-core">Core ' + (rel.core || 0) + '</span>' +
      '<span class="trial-rel-adjacent">Adjacent ' + (rel.adjacent || 0) + '</span>' +
      '<span class="trial-rel-unrelated">Unrelated ' + (rel.unrelated || 0) + '</span>' +
    '</div>';
    const trials = a.trials.slice().sort((x,y) => relationForTrial(x).localeCompare(relationForTrial(y)) || String(x.status || '').localeCompare(String(y.status || '')));
    div.innerHTML =
      '<div class="agent-name">' + escape(a.name) + '</div>' +
      (syns.length ? '<div class="agent-synonyms"><strong>Synonyms collapsed:</strong> ' + escape(syns.join('; ')) + '</div>' : '') +
      '<div class="meta"><strong>Conditions:</strong> ' + escape(a.conditions.join(', ') || 'Other') + '</div>' +
      '<div class="meta"><strong>Categories:</strong> ' + escape((a.ontology?.categories || a.tags || []).join(', ')) + '</div>' +
      '<div class="meta"><strong>Mechanisms:</strong> ' + escape(a.mechanisms.slice(0,5).join(', ')) + '</div>' +
      '<div class="meta"><strong>Evidence Level:</strong> ' + evPill + '</div>' +
      relHtml +
      (a.studies.length ? '<div class="literature-layer"><strong>Published literature:</strong><div class="lit-chips">' + litChips + '</div><div class="literature-list">' + litItems + '</div></div>' : '') +
      '<div class="meta"><strong>Key Refs:</strong> ' + escape(a.refs.slice(0,4).join(' | ')) + '</div>' +
      '<div class="meta agent-notes"><strong>Clinical Notes:</strong> ' + escape(a.notes[0] || '') + '</div>' +
      '<div class="meta agent-foot">Source rows: ' + a.sourceAgents.length + ' | Studies: ' + a.studies.length + ' | Trials: ' + a.trials.length + '</div>' +
      (trials.length ? '<div class="meta"><strong>Trials:</strong><div class="agent-trials">' + trials.slice(0,24).map(trialChip).join('') + (trials.length > 24 ? '<span class="trial-chip trial-rel-unrelated">+' + (trials.length - 24) + '</span>' : '') + '</div></div>' : '');
    el.appendChild(div);
  });
}

load();
</script>`;

function main() {
  if (!fs.existsSync(AGENTS_HTML)) throw new Error(`agents.html not found: ${AGENTS_HTML}`);
  let html = fs.readFileSync(AGENTS_HTML, 'utf8');

  html = html.replace(/<style>[\s\S]*?<\/style>/, `<style>${CSS}\n  </style>`);
  if (!html.includes('id="litType"')) {
    html = html.replace(
      /(<select id="tag"[\s\S]*?<\/select>)/,
      `$1\n  <select id="litType" style="margin-left:6px;" onchange="filter()">\n    <option value="">All Literature</option>\n  </select>`
    );
  }
  html = html.replace(
    /document\.getElementById\('tag'\)\.value=''; filter\(\)/,
    `document.getElementById('tag').value=''; const lit=document.getElementById('litType'); if (lit) lit.value=''; filter()`
  );
  html = html.replace(/<script>\s*let allAgents = \[\];[\s\S]*?load\(\);\s*<\/script>/, SCRIPT);

  fs.writeFileSync(AGENTS_HTML, html, 'utf8');
  console.log(`Patched ${AGENTS_HTML}`);
}

main();
