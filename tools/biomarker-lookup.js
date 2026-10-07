/* Biomarker lookup — match your lab results to the OSMF biomarker atlases.
   Vanilla JS, no dependencies. Loads data/biomarkers/<slug>.json for every
   condition atlas, builds a cross-condition marker index, and ranks
   conditions by how many of the user's flagged markers move in the
   direction the literature reports. Direction only; no reference ranges
   are interpreted. Not a diagnostic tool. */
(function () {
  'use strict';

  var DATA_BASE = '../data/biomarkers/';
  var SITE_BASE = '../';
  var CONDITION_SLUGS = [
    'long-covid', 'me-cfs', 'pacvs', 'lyme', 'gulf-war-illness',
    'alzheimer-s-disease-and-other-dementias', 'asthma', 'atrial-fibrillation',
    'chronic-kidney-disease', 'copd', 'epilepsy', 'gerd-gastroesophageal-reflux-disease',
    'hepatitis-c', 'hypertension', 'hypothyroidism', 'inflammatory-bowel-disease-crohn-s-uc',
    'low-back-pain', 'major-depressive-disorder', 'migraine', 'multiple-sclerosis',
    'nafld-mash-metabolic-associated-steatohepatitis', 'osteoarthritis',
    'rheumatoid-arthritis', 'type-1-diabetes', 'type-2-diabetes'
  ];

  /* Typical adult reference ranges. These vary by laboratory, assay, age and
     sex; they are shown only as orientation and are never used for scoring. */
  var REFERENCE_RANGES = [
    ['C-reactive protein (CRP)', '< 10 mg/L (hs-CRP < 3 mg/L)', 'mg/L'],
    ['Ferritin', 'Men 30–400; women 15–150', 'ng/mL'],
    ['D-dimer', '< 0.5 mg/L FEU (< 500 ng/mL FEU)', 'mg/L FEU'],
    ['Interleukin-6 (IL-6)', '< 7 (assay-dependent)', 'pg/mL'],
    ['TNF-alpha', '< 8 (assay-dependent)', 'pg/mL'],
    ['Cortisol (serum, morning)', '5–25 µg/dL (140–690 nmol/L)', 'µg/dL'],
    ['Vitamin D (25-OH)', '30–100 ng/mL (75–250 nmol/L); deficiency < 20 ng/mL', 'ng/mL'],
    ['Vitamin B12', '200–900 pg/mL (150–660 pmol/L)', 'pg/mL'],
    ['TSH', '0.4–4.0', 'mIU/L'],
    ['Free T4', '0.8–1.8 ng/dL (10–23 pmol/L)', 'ng/dL'],
    ['hs-Troponin T', '< 14 (99th percentile; troponin I assays differ)', 'ng/L'],
    ['NT-proBNP', '< 125 (under 75 y); < 450 (75 y and over)', 'pg/mL'],
    ['Lactate (venous)', '0.5–2.2', 'mmol/L'],
    ['Creatine kinase (CK)', 'Men 39–308; women 26–192', 'U/L'],
    ['ESR', 'Men < 15 (< 20 over 50 y); women < 20 (< 30 over 50 y)', 'mm/h'],
    ['ANA', 'Negative at 1:80 (titres of 1:160 and above are more significant)', 'titre'],
    ['Complement C3', '90–180', 'mg/dL'],
    ['Complement C4', '10–40', 'mg/dL'],
    ['Fibrinogen', '200–400 mg/dL (2–4 g/L)', 'mg/dL'],
    ['Homocysteine', '5–15', 'µmol/L'],
    ['HbA1c', '< 5.7 % (39 mmol/mol); 5.7–6.4 % prediabetes range', '%'],
    ['Glucose (fasting)', '70–99 mg/dL (3.9–5.5 mmol/L)', 'mg/dL'],
    ['Insulin (fasting)', '2–25 (lab-dependent)', 'µIU/mL'],
    ['ALT', '7–55', 'U/L'],
    ['AST', '8–48', 'U/L'],
    ['GGT', 'Men 8–61; women 5–36', 'U/L'],
    ['eGFR', '90 or more (60–89 mildly decreased)', 'mL/min/1.73 m²'],
    ['Hemoglobin', 'Men 13.5–17.5; women 12.0–15.5', 'g/dL'],
    ['White blood cells (WBC)', '4.0–11.0', '×10⁹/L'],
    ['Lymphocytes', '1.0–4.0 (20–40 % of WBC)', '×10⁹/L'],
    ['Platelets', '150–400', '×10⁹/L']
  ];

  var GREEK = {
    'α': 'alpha', 'β': 'beta', 'γ': 'gamma', 'δ': 'delta',
    'ε': 'epsilon', 'ζ': 'zeta', 'η': 'eta', 'θ': 'theta',
    'ι': 'iota', 'κ': 'kappa', 'λ': 'lambda', 'μ': 'mu',
    'µ': 'mu', 'ν': 'nu', 'ξ': 'xi', 'ο': 'omicron',
    'π': 'pi', 'ρ': 'rho', 'σ': 'sigma', 'τ': 'tau',
    'υ': 'upsilon', 'φ': 'phi', 'χ': 'chi', 'ψ': 'psi',
    'ω': 'omega',
    'Α': 'alpha', 'Β': 'beta', 'Γ': 'gamma', 'Δ': 'delta',
    'Θ': 'theta', 'Κ': 'kappa', 'Λ': 'lambda', 'Σ': 'sigma',
    'Ω': 'omega', '₂': '2', '₁': '1', '₃': '3', '₀': '0'
  };

  function slugify(name) {
    var s = String(name || '');
    s = s.replace(/[Ͱ-Ͽµ₀-₃]/g, function (c) { return GREEK[c] || ''; });
    s = s.replace(/≥/g, 'ge').replace(/≤/g, 'le');
    s = s.replace(/[()\[\]]/g, '').replace(/['’]/g, '');
    if (s.normalize) { s = s.normalize('NFKD'); }
    s = s.replace(/[̀-ͯ]/g, '');
    s = s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    return s;
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function $(id) { return document.getElementById(id); }

  /* ------------------------------------------------------------------ */
  /* Data model                                                          */
  /* ------------------------------------------------------------------ */
  var conditions = {};   // slug -> {slug, name, shortName, page, markers:[]}
  var groups = {};       // groupKey -> {key, name, aliases:Set, loinc, entries:[{slug, marker}]}
  var groupList = [];
  var panel = [];        // [{key, status:'high'|'low'|'normal', value:'', unit:''}]
  var loadErrors = [];

  function groupKeyFor(marker) {
    if (marker.loinc && /^\d{3,}-\d$/.test(String(marker.loinc).trim())) {
      return 'loinc-' + String(marker.loinc).trim();
    }
    return slugify(marker.name);
  }

  function ingest(slug, data) {
    var cond = data.condition || {};
    var c = {
      slug: slug,
      name: cond.name || slug,
      shortName: cond.shortName || cond.name || slug,
      alternateNames: cond.alternateNames || [],
      page: slug + '-biomarkers.html',
      markers: []
    };
    (data.markers || []).forEach(function (m) {
      if (!m || !m.name) { return; }
      var markerSlug = slugify(m.name);
      var entry = {
        slug: slug,
        name: m.name,
        markerSlug: markerSlug,
        alternateName: m.alternateName || '',
        direction: (m.direction || '').toLowerCase(),
        category: m.category || '',
        comparison: m.comparison || '',
        symptoms: m.symptoms || '',
        loinc: m.loinc || '',
        reference: m.reference || null
      };
      c.markers.push(entry);
      var key = groupKeyFor(m);
      var g = groups[key];
      if (!g) {
        g = groups[key] = { key: key, name: m.name, aliases: {}, loinc: m.loinc || '', entries: [] };
        groupList.push(g);
      }
      if (m.loinc && !g.loinc) { g.loinc = m.loinc; }
      if (m.name !== g.name) { g.aliases[m.name] = true; }
      if (m.alternateName) { g.aliases[m.alternateName] = true; }
      g.entries.push(entry);
    });
    conditions[slug] = c;
  }

  function loadAll() {
    var tasks = CONDITION_SLUGS.map(function (slug) {
      return fetch(DATA_BASE + slug + '.json', { cache: 'default' })
        .then(function (r) { if (!r.ok) { throw new Error(r.status); } return r.json(); })
        .then(function (d) { ingest(slug, d); })
        .catch(function () { loadErrors.push(slug); });
    });
    return Promise.all(tasks).then(function () {
      groupList.forEach(function (g) {
        g.searchText = (g.name + ' ' + Object.keys(g.aliases).join(' ') + ' ' + (g.loinc || '')).toLowerCase();
        g.searchSlug = slugify(g.searchText);
        g.conditionCount = {};
        g.entries.forEach(function (e) { g.conditionCount[e.slug] = true; });
        g.nConditions = Object.keys(g.conditionCount).length;
      });
      groupList.sort(function (a, b) {
        return b.nConditions - a.nConditions || a.name.localeCompare(b.name);
      });
    });
  }

  /* ------------------------------------------------------------------ */
  /* URL state                                                           */
  /* ------------------------------------------------------------------ */
  function encodeState() {
    if (!panel.length) { return ''; }
    return 'm=' + panel.map(function (p) {
      return [p.key, p.status, p.value || '', p.unit || ''].map(encodeURIComponent).join('~');
    }).join('|');
  }

  function writeHash() {
    var h = encodeState();
    var url = location.pathname + location.search + (h ? '#' + h : '');
    if (history.replaceState) { history.replaceState(null, '', url); } else { location.hash = h; }
    var shareLink = $('shareLink');
    if (shareLink) { shareLink.value = location.href; }
  }

  function readHash() {
    var h = location.hash.replace(/^#/, '');
    if (!h) { return; }
    var m = /(?:^|&)m=([^&]*)/.exec(h);
    if (!m) { return; }
    panel = [];
    m[1].split('|').forEach(function (part) {
      var f = part.split('~').map(function (x) { try { return decodeURIComponent(x); } catch (e) { return ''; } });
      if (!f[0] || !groups[f[0]]) { return; }
      var status = (f[1] === 'high' || f[1] === 'low' || f[1] === 'normal') ? f[1] : 'high';
      if (!panel.some(function (p) { return p.key === f[0]; })) {
        panel.push({ key: f[0], status: status, value: (f[2] || '').slice(0, 20), unit: (f[3] || '').slice(0, 20) });
      }
    });
  }

  /* ------------------------------------------------------------------ */
  /* Search / autocomplete                                               */
  /* ------------------------------------------------------------------ */
  var activeIndex = -1;
  var currentResults = [];

  function search(q) {
    q = q.trim().toLowerCase();
    if (!q) { return []; }
    var qs = slugify(q);
    var out = [];
    for (var i = 0; i < groupList.length && out.length < 40; i++) {
      var g = groupList[i];
      var score = 0;
      var nameL = g.name.toLowerCase();
      if (nameL === q || (g.loinc && g.loinc === q)) { score = 100; }
      else if (nameL.indexOf(q) === 0) { score = 80; }
      else if (nameL.indexOf(q) >= 0) { score = 60; }
      else if (g.searchText.indexOf(q) >= 0) { score = 40; }
      else if (qs && g.searchSlug.indexOf(qs) >= 0) { score = 30; }
      if (score) { out.push({ g: g, score: score + Math.min(g.nConditions, 9) }); }
    }
    out.sort(function (a, b) { return b.score - a.score || a.g.name.localeCompare(b.g.name); });
    return out.slice(0, 12).map(function (x) { return x.g; });
  }

  function renderSuggestions(list) {
    var box = $('suggestions');
    currentResults = list;
    activeIndex = -1;
    $('markerSearch').setAttribute('aria-expanded', list.length ? 'true' : 'false');
    if (!list.length) { box.innerHTML = ''; box.hidden = true; return; }
    box.innerHTML = list.map(function (g, i) {
      var inPanel = panel.some(function (p) { return p.key === g.key; });
      var alias = Object.keys(g.aliases).slice(0, 2).join(' · ');
      return '<li role="option" data-i="' + i + '" id="sug-' + i + '"' + (inPanel ? ' class="in-panel"' : '') + '>' +
        '<span class="sug-name">' + esc(g.name) + '</span>' +
        (alias ? '<span class="sug-alias">' + esc(alias) + '</span>' : '') +
        '<span class="sug-meta">' + g.nConditions + ' condition' + (g.nConditions === 1 ? '' : 's') +
        (g.loinc ? ' · LOINC ' + esc(g.loinc) : '') + (inPanel ? ' · added' : '') + '</span></li>';
    }).join('');
    box.hidden = false;
  }

  function setActive(i) {
    var items = $('suggestions').querySelectorAll('li');
    if (!items.length) { return; }
    activeIndex = (i + items.length) % items.length;
    for (var k = 0; k < items.length; k++) { items[k].classList.toggle('active', k === activeIndex); }
    $('markerSearch').setAttribute('aria-activedescendant', 'sug-' + activeIndex);
  }

  function addMarker(key, status) {
    if (!groups[key]) { return; }
    if (panel.some(function (p) { return p.key === key; })) { flash('Already in your panel.'); return; }
    panel.push({ key: key, status: status || 'high', value: '', unit: '' });
    $('markerSearch').value = '';
    renderSuggestions([]);
    renderPanel();
    compute();
    var row = $('panelList').lastElementChild;
    if (row) { row.classList.add('just-added'); }
  }

  function removeMarker(key) {
    panel = panel.filter(function (p) { return p.key !== key; });
    renderPanel();
    compute();
  }

  function flash(msg) {
    var el = $('flash');
    el.textContent = msg;
    el.hidden = false;
    clearTimeout(flash.t);
    flash.t = setTimeout(function () { el.hidden = true; }, 2200);
  }

  /* ------------------------------------------------------------------ */
  /* Panel rendering                                                     */
  /* ------------------------------------------------------------------ */
  function renderPanel() {
    var list = $('panelList');
    var empty = $('panelEmpty');
    if (!panel.length) {
      list.innerHTML = '';
      empty.hidden = false;
      $('panelActions').hidden = true;
      return;
    }
    empty.hidden = true;
    $('panelActions').hidden = false;
    list.innerHTML = panel.map(function (p) {
      var g = groups[p.key];
      var conds = Object.keys(g.conditionCount).map(function (s) { return conditions[s].shortName; }).sort().join(', ');
      return '<li class="panel-row" data-key="' + esc(p.key) + '">' +
        '<div class="panel-head"><div><strong class="panel-name">' + esc(g.name) + '</strong>' +
        '<div class="panel-conds">Reported in: ' + esc(conds) + (g.loinc ? ' · LOINC ' + esc(g.loinc) : '') + '</div></div>' +
        '<button type="button" class="btn-remove" data-remove="' + esc(p.key) + '" aria-label="Remove ' + esc(g.name) + '">×</button></div>' +
        '<div class="panel-controls">' +
        '<div class="seg" role="radiogroup" aria-label="Your result for ' + esc(g.name) + '">' +
        ['high', 'low', 'normal'].map(function (s) {
          return '<button type="button" class="seg-btn seg-' + s + (p.status === s ? ' on' : '') + '" role="radio" aria-checked="' + (p.status === s) + '" data-status="' + s + '">' +
            (s === 'high' ? '↑ High' : s === 'low' ? '↓ Low' : '– Normal') + '</button>';
        }).join('') + '</div>' +
        '<label class="val-label"><span class="sr-only">Value (optional)</span>' +
        '<input type="text" inputmode="decimal" class="val-input" placeholder="value (optional)" maxlength="20" value="' + esc(p.value) + '" data-field="value"></label>' +
        '<label class="val-label"><span class="sr-only">Unit (optional)</span>' +
        '<input type="text" class="unit-input" placeholder="unit" maxlength="20" value="' + esc(p.unit) + '" data-field="unit" list="unitList"></label>' +
        '</div></li>';
    }).join('');
    $('panelCount').textContent = panel.length;
  }

  /* ------------------------------------------------------------------ */
  /* Scoring                                                             */
  /* ------------------------------------------------------------------ */
  function compute() {
    var results = $('results');
    var flagged = panel.filter(function (p) { return p.status !== 'normal'; });
    writeHash();
    if (!panel.length) {
      results.innerHTML = '<p class="results-empty">Add at least one marker above to see which conditions in the atlases report it moving in the same direction.</p>';
      return;
    }
    var scores = {};
    panel.forEach(function (p) {
      var g = groups[p.key];
      g.entries.forEach(function (e) {
        var sc = scores[e.slug] || (scores[e.slug] = { slug: e.slug, score: 0, concordant: [], half: [], discordant: [], normal: [] });
        var dir = e.direction;
        if (p.status === 'normal') {
          sc.normal.push({ e: e, p: p });
        } else if (dir === 'mixed') {
          sc.score += 0.5; sc.half.push({ e: e, p: p });
        } else if ((dir === 'up' && p.status === 'high') || (dir === 'down' && p.status === 'low')) {
          sc.score += 1; sc.concordant.push({ e: e, p: p });
        } else if (dir === 'up' || dir === 'down') {
          sc.discordant.push({ e: e, p: p });
        }
      });
    });
    var ranked = Object.keys(scores).map(function (k) { return scores[k]; });
    ranked.sort(function (a, b) {
      return b.score - a.score || a.discordant.length - b.discordant.length ||
        (b.normal.length) - (a.normal.length) || conditions[a.slug].name.localeCompare(conditions[b.slug].name);
    });
    var html = '<div class="results-summary">' +
      '<strong>' + flagged.length + '</strong> flagged marker' + (flagged.length === 1 ? '' : 's') +
      (panel.length - flagged.length ? ' and <strong>' + (panel.length - flagged.length) + '</strong> normal' : '') +
      ' compared against <strong>' + Object.keys(conditions).length + '</strong> condition atlases. ' +
      'Score = concordant markers (mixed-direction markers count as 0.5). Higher is more overlap with published findings, nothing more.</div>';
    html += '<ol class="rank-list">' + ranked.map(function (r, i) {
      var c = conditions[r.slug];
      var total = c.markers.length;
      var cls = r.score > 0 ? '' : ' muted';
      return '<li class="rank-card' + cls + '">' +
        '<div class="rank-head"><span class="rank-n">' + (i + 1) + '</span>' +
        '<div class="rank-title"><h3><a href="' + SITE_BASE + esc(c.page) + '">' + esc(c.name) + '</a></h3>' +
        '<div class="rank-sub">' + total + ' markers in atlas · ' + r.concordant.length + ' concordant' +
        (r.half.length ? ' · ' + r.half.length + ' mixed' : '') +
        (r.discordant.length ? ' · ' + r.discordant.length + ' discordant' : '') +
        (r.normal.length ? ' · ' + r.normal.length + ' normal on your labs' : '') + '</div></div>' +
        '<div class="rank-score" aria-label="score"><span>' + formatScore(r.score) + '</span><small>of ' + flagged.length + '</small></div></div>' +
        renderMatchGroup('Concordant', 'ok', r.concordant.concat(r.half)) +
        renderMatchGroup('Discordant', 'bad', r.discordant) +
        renderMatchGroup('Normal on your labs (reported altered in this condition)', 'neutral', r.normal) +
        '<div class="rank-links"><a href="' + SITE_BASE + esc(c.page) + '">Open ' + esc(c.shortName) + ' atlas →</a></div>' +
        '</li>';
    }).join('') + '</ol>';
    var unmatched = Object.keys(conditions).filter(function (s) { return !scores[s]; });
    if (unmatched.length) {
      html += '<p class="results-note">No overlap with your panel: ' + unmatched.map(function (s) {
        return '<a href="' + SITE_BASE + esc(conditions[s].page) + '">' + esc(conditions[s].shortName) + '</a>';
      }).join(', ') + '.</p>';
    }
    results.innerHTML = html;
  }

  function formatScore(n) { return (Math.round(n * 10) / 10).toString(); }

  function dirArrow(d) { return d === 'up' ? '↑' : d === 'down' ? '↓' : '↕'; }
  function dirWord(d) { return d === 'up' ? 'higher' : d === 'down' ? 'lower' : 'mixed'; }
  function statusWord(s) { return s === 'high' ? 'high' : s === 'low' ? 'low' : 'normal'; }

  function renderMatchGroup(label, cls, items) {
    if (!items.length) { return ''; }
    return '<div class="match-group match-' + cls + '"><div class="match-label">' + esc(label) + '</div><ul>' +
      items.map(function (it) {
        var e = it.e, p = it.p;
        var ref = e.reference && e.reference.citation ? esc(e.reference.citation) : '';
        var doi = e.reference && e.reference.doi ? '<a href="https://doi.org/' + esc(e.reference.doi) + '" rel="noopener" target="_blank">DOI</a>' : '';
        return '<li><a class="m-link" href="' + SITE_BASE + 'biomarkers/' + esc(e.slug) + '/' + esc(e.markerSlug) + '.html">' + esc(e.name) + '</a>' +
          ' <span class="dir dir-' + esc(e.direction) + '">' + dirArrow(e.direction) + ' ' + dirWord(e.direction) + ' in literature</span>' +
          ' <span class="yours">· yours: ' + statusWord(p.status) + (p.value ? ' (' + esc(p.value) + (p.unit ? ' ' + esc(p.unit) : '') + ')' : '') + '</span>' +
          (e.comparison ? ' <span class="cmp" title="Comparison group">vs ' + esc(e.comparison) + '</span>' : '') +
          (ref ? ' <span class="ref">' + ref + (doi ? ' ' + doi : '') + '</span>' : '') +
          '</li>';
      }).join('') + '</ul></div>';
  }

  /* ------------------------------------------------------------------ */
  /* Clinician summary                                                   */
  /* ------------------------------------------------------------------ */
  function clinicianSummary() {
    var lines = [];
    lines.push('Biomarker lookup summary (Open Source Medicine Foundation research tracker)');
    lines.push('Generated: ' + new Date().toISOString().slice(0, 10));
    lines.push('Shareable link: ' + location.href);
    lines.push('');
    lines.push('This is an educational cross-reference of patient-entered lab flags against published biomarker direction-of-change in research cohorts. It is not a diagnosis, a test result, or a recommendation.');
    lines.push('');
    lines.push('My lab flags (' + panel.length + '):');
    panel.forEach(function (p) {
      var g = groups[p.key];
      lines.push('  - ' + g.name + (g.loinc ? ' [LOINC ' + g.loinc + ']' : '') + ': ' + statusWord(p.status).toUpperCase() +
        (p.value ? ' (' + p.value + (p.unit ? ' ' + p.unit : '') + ')' : ''));
    });
    lines.push('');
    var scores = {};
    panel.forEach(function (p) {
      groups[p.key].entries.forEach(function (e) {
        var sc = scores[e.slug] || (scores[e.slug] = { slug: e.slug, score: 0, c: [], d: [] });
        if (p.status === 'normal') { return; }
        if (e.direction === 'mixed') { sc.score += 0.5; sc.c.push(e.name + ' (mixed)'); }
        else if ((e.direction === 'up' && p.status === 'high') || (e.direction === 'down' && p.status === 'low')) { sc.score += 1; sc.c.push(e.name); }
        else if (e.direction) { sc.d.push(e.name); }
      });
    });
    var ranked = Object.keys(scores).map(function (k) { return scores[k]; }).filter(function (r) { return r.score > 0; });
    ranked.sort(function (a, b) { return b.score - a.score; });
    lines.push('Conditions whose published biomarker direction matches my flags (top ' + Math.min(5, ranked.length) + '):');
    ranked.slice(0, 5).forEach(function (r, i) {
      var c = conditions[r.slug];
      lines.push('  ' + (i + 1) + '. ' + c.name + ' — score ' + formatScore(r.score) + '; concordant: ' + (r.c.join(', ') || 'none') +
        (r.d.length ? '; discordant: ' + r.d.join(', ') : '') + '; atlas: https://research.opensourcemed.info/' + c.page);
    });
    if (!ranked.length) { lines.push('  (none)'); }
    lines.push('');
    lines.push('Sources: OSMF Biomarker Atlases (peer-reviewed literature syntheses with DOI citations), https://research.opensourcemed.info/biomarker-atlas.html');
    return lines.join('\n');
  }

  function copyText(text, okMsg) {
    function done() { flash(okMsg || 'Copied.'); }
    function fallback() {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', ''); ta.style.position = 'fixed'; ta.style.top = '-1000px';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); done(); } catch (e) { flash('Copy failed — select the text and copy manually.'); }
      document.body.removeChild(ta);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else { fallback(); }
  }

  /* ------------------------------------------------------------------ */
  /* Reference table                                                     */
  /* ------------------------------------------------------------------ */
  function renderReferenceTable() {
    var tb = $('refTableBody');
    if (!tb) { return; }
    tb.innerHTML = REFERENCE_RANGES.map(function (r) {
      return '<tr><td>' + esc(r[0]) + '</td><td>' + esc(r[1]) + '</td><td>' + esc(r[2]) + '</td></tr>';
    }).join('');
  }

  /* ------------------------------------------------------------------ */
  /* Wiring                                                              */
  /* ------------------------------------------------------------------ */
  function wire() {
    var input = $('markerSearch');
    var sug = $('suggestions');

    input.addEventListener('input', function () { renderSuggestions(search(input.value)); });
    input.addEventListener('focus', function () { if (input.value.trim()) { renderSuggestions(search(input.value)); } });
    input.addEventListener('keydown', function (ev) {
      if (sug.hidden) { if (ev.key === 'Enter') { ev.preventDefault(); } return; }
      if (ev.key === 'ArrowDown') { ev.preventDefault(); setActive(activeIndex + 1); }
      else if (ev.key === 'ArrowUp') { ev.preventDefault(); setActive(activeIndex - 1); }
      else if (ev.key === 'Enter') {
        ev.preventDefault();
        var pick = currentResults[activeIndex >= 0 ? activeIndex : 0];
        if (pick) { addMarker(pick.key); }
      } else if (ev.key === 'Escape') { renderSuggestions([]); }
    });
    sug.addEventListener('mousedown', function (ev) {
      var li = ev.target.closest('li[data-i]');
      if (!li) { return; }
      ev.preventDefault();
      addMarker(currentResults[+li.getAttribute('data-i')].key);
    });
    document.addEventListener('click', function (ev) {
      if (!ev.target.closest('.search-wrap')) { renderSuggestions([]); }
    });

    $('panelList').addEventListener('click', function (ev) {
      var rm = ev.target.closest('[data-remove]');
      if (rm) { removeMarker(rm.getAttribute('data-remove')); return; }
      var sb = ev.target.closest('[data-status]');
      if (sb) {
        var key = sb.closest('.panel-row').getAttribute('data-key');
        var p = panel.filter(function (x) { return x.key === key; })[0];
        if (p) { p.status = sb.getAttribute('data-status'); renderPanel(); compute(); }
      }
    });
    $('panelList').addEventListener('input', function (ev) {
      var f = ev.target.getAttribute('data-field');
      if (!f) { return; }
      var key = ev.target.closest('.panel-row').getAttribute('data-key');
      var p = panel.filter(function (x) { return x.key === key; })[0];
      if (p) { p[f] = ev.target.value.slice(0, 20); writeHash(); }
    });
    $('panelList').addEventListener('change', function (ev) {
      if (ev.target.getAttribute('data-field')) { compute(); }
    });

    $('btnClear').addEventListener('click', function () {
      if (!panel.length || confirm('Remove all markers from your panel?')) { panel = []; renderPanel(); compute(); }
    });
    $('btnCopyLink').addEventListener('click', function () { writeHash(); copyText(location.href, 'Link copied.'); });
    $('btnCopySummary').addEventListener('click', function () { copyText(clinicianSummary(), 'Summary copied — paste it into a note or email for your clinician.'); });
    $('btnPrint').addEventListener('click', function () { window.print(); });

    var quick = document.querySelectorAll('[data-quick]');
    for (var i = 0; i < quick.length; i++) {
      quick[i].addEventListener('click', function (ev) {
        ev.preventDefault();
        var q = this.getAttribute('data-quick');
        var hit = search(q)[0];
        if (hit) { addMarker(hit.key, this.getAttribute('data-quick-status') || 'high'); }
      });
    }

    window.addEventListener('hashchange', function () {
      readHash(); renderPanel(); compute();
    });
  }

  function init() {
    renderReferenceTable();
    var status = $('loadStatus');
    loadAll().then(function () {
      var nMarkers = 0;
      Object.keys(conditions).forEach(function (s) { nMarkers += conditions[s].markers.length; });
      status.textContent = 'Loaded ' + nMarkers + ' marker entries (' + groupList.length + ' distinct markers) across ' +
        Object.keys(conditions).length + ' condition atlases' + (loadErrors.length ? '; could not load: ' + loadErrors.join(', ') : '') + '.';
      status.className = 'load-status ok';
      $('markerSearch').disabled = false;
      $('markerSearch').placeholder = 'Type a marker, e.g. ferritin, IL-6, D-dimer, 1988-5';
      var dl = $('markerList');
      if (dl) {
        dl.innerHTML = groupList.map(function (g) { return '<option value="' + esc(g.name) + '">'; }).join('');
      }
      wire();
      readHash();
      renderPanel();
      compute();
    }).catch(function (e) {
      status.textContent = 'Could not load the biomarker data (' + (e && e.message ? e.message : 'network error') + '). If you opened this file directly from disk, serve it over HTTP.';
      status.className = 'load-status err';
    });
  }

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }

  window.OSMBiomarkerLookup = { slugify: slugify, getPanel: function () { return panel.slice(); }, groups: groups, conditions: conditions };
})();
