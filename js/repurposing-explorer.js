/* OSMF Drug Repurposing Explorer
 * Loads /js/generated/repurposing-index.json (built by scripts/build_repurposing_index.py)
 * and renders a filterable, sortable table with URL-hash state.
 */
(function () {
  'use strict';

  var INDEX_URL = '/js/generated/repurposing-index.json';
  var DATA = null;
  var CONDS = {};
  var state = { c: 'all', q: '', tier: '', type: '', rec: false, ap: false, sort: 'sc', asc: false };
  var ALL_LIMIT = 300;

  var $ = function (id) { return document.getElementById(id); };
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function num(n) { return (n || 0).toLocaleString(); }

  // ---- hash state -------------------------------------------------------
  function readHash() {
    var h = location.hash.replace(/^#/, '');
    if (!h) return;
    h.split('&').forEach(function (kv) {
      var p = kv.split('=');
      var k = decodeURIComponent(p[0] || '');
      var v = decodeURIComponent((p[1] || '').replace(/\+/g, ' '));
      if (k === 'c') state.c = v || 'all';
      else if (k === 'q') state.q = v;
      else if (k === 'tier') state.tier = v.toUpperCase();
      else if (k === 'type') state.type = v;
      else if (k === 'rec') state.rec = v === '1';
      else if (k === 'ap') state.ap = v === '1';
      else if (k === 'sort') state.sort = v;
      else if (k === 'asc') state.asc = v === '1';
    });
  }
  function writeHash() {
    var parts = [];
    if (state.c && state.c !== 'all') parts.push('c=' + encodeURIComponent(state.c));
    if (state.q) parts.push('q=' + encodeURIComponent(state.q));
    if (state.tier) parts.push('tier=' + state.tier);
    if (state.type) parts.push('type=' + encodeURIComponent(state.type));
    if (state.rec) parts.push('rec=1');
    if (state.ap) parts.push('ap=1');
    if (state.sort !== 'sc') parts.push('sort=' + state.sort);
    if (state.asc) parts.push('asc=1');
    var next = parts.length ? '#' + parts.join('&') : '';
    if (next !== location.hash) {
      if (history.replaceState) history.replaceState(null, '', location.pathname + location.search + next);
      else location.hash = next;
    }
  }
  function syncControls() {
    $('f-cond').value = CONDS[state.c] ? state.c : 'all';
    $('f-q').value = state.q;
    $('f-tier').value = state.tier;
    $('f-type').value = state.type;
    $('f-rec').checked = state.rec;
    $('f-ap').checked = state.ap;
  }

  // ---- filtering / sorting ---------------------------------------------
  function filtered() {
    var q = state.q.trim().toLowerCase();
    var rows = DATA.rows.filter(function (r) {
      if (state.c !== 'all' && r.d !== state.c) return false;
      if (state.tier && r.tier !== state.tier) return false;
      if (state.type && r.ty !== state.type) return false;
      if (state.rec && !(r.tb[1] > 0)) return false;
      if (state.ap && !r.ap) return false;
      if (q) {
        var hay = (r.n + ' ' + (r.m || '') + ' ' + (r.tyr || '') + ' ' + (CONDS[r.d] ? CONDS[r.d].short : '')).toLowerCase();
        if (hay.indexOf(q) < 0) return false;
      }
      return true;
    });
    var k = state.sort;
    var dir = state.asc ? 1 : -1;
    rows.sort(function (a, b) {
      var va, vb;
      if (k === 'n') { va = a.n.toLowerCase(); vb = b.n.toLowerCase(); return va < vb ? -dir : va > vb ? dir : 0; }
      if (k === 'd') { va = CONDS[a.d] ? CONDS[a.d].short.toLowerCase() : a.d; vb = CONDS[b.d] ? CONDS[b.d].short.toLowerCase() : b.d; if (va !== vb) return va < vb ? -dir : dir; return b.sc - a.sc; }
      if (k === 'm') { va = (a.m || '~').toLowerCase(); vb = (b.m || '~').toLowerCase(); return va < vb ? -dir : va > vb ? dir : 0; }
      if (k === 't') { va = a.tb[0]; vb = b.tb[0]; }
      else if (k === 'lit') { va = a.lit; vb = b.lit; }
      else { va = a.sc; vb = b.sc; }
      if (va !== vb) return (va - vb) * dir;
      return b.sc - a.sc || a.n.localeCompare(b.n);
    });
    return rows;
  }

  // ---- rendering --------------------------------------------------------
  function tierTag(t) {
    var lbl = DATA.tier_labels[t] || t;
    return '<span class="tag tier-' + esc(t) + '" title="Evidence tier ' + esc(t) + ': ' + esc(lbl) + '">' + esc(t) + ' · ' + esc(lbl) + '</span>';
  }
  function litTitle(lb) {
    var names = { cochrane_review: 'Cochrane', meta_analysis: 'meta-analysis', systematic_review: 'systematic review', rct: 'RCT', clinical_trial: 'trial publication', curated_reference: 'curated reference', pubmed_search: 'PubMed record', other: 'other' };
    return Object.keys(lb || {}).map(function (k) { return lb[k] + ' ' + (names[k] || k); }).join(', ');
  }
  function renderRows(rows) {
    var tb = $('rows');
    var showCond = state.c === 'all';
    document.body.classList.toggle('all-conds', showCond);
    $('th-d').style.display = showCond ? '' : 'none';
    if (!rows.length) {
      tb.innerHTML = '<tr><td colspan="7" class="empty">No records match these filters. Try clearing a filter.</td></tr>';
      return;
    }
    var slice = showCond ? rows.slice(0, ALL_LIMIT) : rows;
    var maxSc = 80;
    var html = slice.map(function (r) {
      var c = CONDS[r.d] || { short: r.d, url: '#' };
      var trials = r.tb[0]
        ? '<strong>' + r.tb[0] + '</strong><div>' +
          (r.tb[1] ? '<span class="tag rec">' + r.tb[1] + ' recruiting</span>' : '') +
          (r.tb[2] ? '<span class="tag act">' + r.tb[2] + ' active</span>' : '') +
          (r.tb[3] ? '<span class="tag done">' + r.tb[3] + ' completed</span>' : '') +
          (r.tb[4] ? '<span class="tag off">' + r.tb[4] + ' other</span>' : '') +
          (r.ph3 ? '<span class="tag" title="Trials at phase 3 or 4">' + r.ph3 + ' ph3/4</span>' : '') + '</div>'
        : '<span class="muted">0</span>';
      var lit = r.lit ? '<strong title="' + esc(litTitle(r.lb)) + '">' + r.lit + '</strong><div class="muted">' + esc(litTitle(r.lb)) + '</div>' : '<span class="muted">0</span>';
      var sp = r.sp || {};
      var summary = tierTag(r.tier) + (r.ap ? ' <span class="tag ap" title="Approved for at least one other indication">approved elsewhere</span>' : '') +
        '<div><span class="score" title="trials ' + sp.trials + ' + literature ' + sp.literature + ' + tier ' + sp.tier + ' + approved ' + sp.approved + '">' + r.sc + '</span> <span class="muted">score</span>' +
        '<div class="bar"><i style="width:' + Math.min(100, Math.round(r.sc / maxSc * 100)) + '%"></i></div></div>' +
        '<div class="muted">trials ' + sp.trials + ' · lit ' + sp.literature + ' · tier ' + sp.tier + (sp.approved ? ' · approved ' + sp.approved : '') + '</div>';
      var links = '';
      if (r.pu) links += '<a href="' + esc(r.pu) + '">Evidence page</a>';
      if (r.au) links += '<a href="' + esc(r.au) + '">Agent page</a>';
      (r.ext || []).forEach(function (e) { links += '<a href="' + esc(e.u) + '" target="_blank" rel="noopener">' + esc(e.l) + ' ↗</a>'; });
      var agentCell = (r.pu ? '<a href="' + esc(r.pu) + '">' + esc(r.n) + '</a>' : esc(r.n)) +
        '<div class="sub">' + esc(r.ty) + (r.tyr && r.tyr !== r.ty ? ' · ' + esc(r.tyr) : '') + (r.ph && r.ph !== 'Investigational' ? ' · ' + esc(r.ph) : '') + '</div>';
      return '<tr>' +
        '<td style="' + (showCond ? '' : 'display:none') + '"><a href="#c=' + esc(r.d) + '" data-cond="' + esc(r.d) + '">' + esc(c.short) + '</a></td>' +
        '<td class="agent">' + agentCell + '</td>' +
        '<td class="mech">' + (r.m ? esc(r.m) : '<span class="muted">—</span>') + '</td>' +
        '<td>' + summary + '</td>' +
        '<td>' + trials + '</td>' +
        '<td>' + lit + '</td>' +
        '<td class="links">' + links + '</td>' +
        '</tr>';
    }).join('');
    tb.innerHTML = html;
    if (showCond && rows.length > ALL_LIMIT) {
      tb.insertAdjacentHTML('beforeend', '<tr><td colspan="7" class="empty">Showing the top ' + ALL_LIMIT + ' of ' + num(rows.length) + ' records. Pick a condition to see all of its candidates.</td></tr>');
    }
  }
  function renderHead(rows) {
    var head = $('cond-head');
    var stats = $('stats');
    var t = 0, rec = 0, lit = 0, ap = 0;
    rows.forEach(function (r) { t += r.tb[0]; rec += r.tb[1]; lit += r.lit; ap += r.ap ? 1 : 0; });
    if (state.c === 'all') {
      head.innerHTML = '<h2>All conditions</h2><span class="muted">' + num(DATA.conditions.length) + ' conditions · ranked by evidence score</span>';
    } else {
      var c = CONDS[state.c];
      head.innerHTML = '<h2>' + esc(c.n) + '</h2>' +
        '<a href="' + esc(c.url) + '">Condition hub</a>' +
        '<a href="/pairs/' + esc(c.s) + '/">All ' + esc(c.short) + ' evidence pages</a>' +
        '<span class="muted">' + esc(c.cat) + (c.nCand ? ' · ' + num(c.nCand) + ' candidates logged, ' + num(c.nRows) + ' with trial or literature evidence' : '') + '</span>';
    }
    stats.innerHTML =
      '<div class="stat"><div class="v">' + num(rows.length) + '</div><div class="l">Matching records</div></div>' +
      '<div class="stat"><div class="v">' + num(t) + '</div><div class="l">Registered trials</div></div>' +
      '<div class="stat"><div class="v">' + num(rec) + '</div><div class="l">Recruiting trials</div></div>' +
      '<div class="stat"><div class="v">' + num(lit) + '</div><div class="l">Publications</div></div>' +
      '<div class="stat"><div class="v">' + num(ap) + '</div><div class="l">Approved elsewhere</div></div>';
  }
  function render() {
    var rows = filtered();
    renderHead(rows);
    renderRows(rows);
    $('count').textContent = num(rows.length) + ' record' + (rows.length === 1 ? '' : 's');
    document.querySelectorAll('th[data-k]').forEach(function (th) {
      th.classList.toggle('sorted', th.getAttribute('data-k') === state.sort);
      th.classList.toggle('asc', th.getAttribute('data-k') === state.sort && state.asc);
    });
    writeHash();
  }

  // ---- CSV ---------------------------------------------------------------
  function csv() {
    var rows = filtered();
    var cols = ['condition', 'agent', 'agent_type', 'mechanism', 'tier', 'score', 'trials_total', 'recruiting', 'active', 'completed', 'other', 'phase3_4', 'literature', 'approved_elsewhere', 'evidence_page', 'agent_page'];
    var out = [cols.join(',')];
    rows.forEach(function (r) {
      var vals = [CONDS[r.d] ? CONDS[r.d].short : r.d, r.n, r.ty, r.m || '', r.tier, r.sc, r.tb[0], r.tb[1], r.tb[2], r.tb[3], r.tb[4], r.ph3, r.lit, r.ap ? 'yes' : 'no',
        r.pu ? 'https://research.opensourcemed.info' + r.pu : '', r.au ? 'https://research.opensourcemed.info' + r.au : ''];
      out.push(vals.map(function (v) { v = String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }).join(','));
    });
    var blob = new Blob([out.join('\n')], { type: 'text/csv' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'osmf-repurposing-' + (state.c || 'all') + '.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
  }

  // ---- init --------------------------------------------------------------
  function populateConditions() {
    var sel = $('f-cond');
    var groups = {};
    var order = [];
    DATA.conditions.forEach(function (c) {
      CONDS[c.s] = c;
      if (!groups[c.cat]) { groups[c.cat] = []; order.push(c.cat); }
      groups[c.cat].push(c);
    });
    order.forEach(function (cat) {
      var og = document.createElement('optgroup');
      og.label = cat;
      groups[cat].sort(function (a, b) { return a.short.localeCompare(b.short); }).forEach(function (c) {
        var o = document.createElement('option');
        o.value = c.s;
        o.textContent = c.short + ' (' + c.nRows + ')';
        og.appendChild(o);
      });
      sel.appendChild(og);
    });
  }
  function bind() {
    $('f-cond').addEventListener('change', function () { state.c = this.value; render(); });
    $('f-q').addEventListener('input', function () { state.q = this.value; render(); });
    $('f-tier').addEventListener('change', function () { state.tier = this.value; render(); });
    $('f-type').addEventListener('change', function () { state.type = this.value; render(); });
    $('f-rec').addEventListener('change', function () { state.rec = this.checked; render(); });
    $('f-ap').addEventListener('change', function () { state.ap = this.checked; render(); });
    $('btn-reset').addEventListener('click', function () {
      state = { c: 'all', q: '', tier: '', type: '', rec: false, ap: false, sort: 'sc', asc: false };
      syncControls(); render();
    });
    $('btn-csv').addEventListener('click', csv);
    $('btn-share').addEventListener('click', function () {
      writeHash();
      var url = location.href;
      var btn = this;
      var done = function () { btn.textContent = 'Link copied'; setTimeout(function () { btn.textContent = 'Copy shareable link'; }, 1800); };
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () { window.prompt('Copy this link', url); });
      else window.prompt('Copy this link', url);
    });
    document.querySelectorAll('th[data-k]').forEach(function (th) {
      th.addEventListener('click', function () {
        var k = th.getAttribute('data-k');
        if (state.sort === k) state.asc = !state.asc; else { state.sort = k; state.asc = (k === 'n' || k === 'd' || k === 'm'); }
        render();
      });
    });
    $('rows').addEventListener('click', function (e) {
      var a = e.target.closest ? e.target.closest('a[data-cond]') : null;
      if (a) { e.preventDefault(); state.c = a.getAttribute('data-cond'); syncControls(); render(); window.scrollTo({ top: $('controls').offsetTop - 70, behavior: 'smooth' }); }
    });
    window.addEventListener('hashchange', function () { readHash(); syncControls(); render(); });
  }

  function init() {
    fetch(INDEX_URL).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
      DATA = d;
      populateConditions();
      var tt = 0, tl = 0;
      d.rows.forEach(function (r) { tt += r.tb[0]; tl += r.lit; });
      $('m-conds').textContent = num(d.conditions.length);
      $('m-rows').textContent = num(d.rows.length);
      $('m-trials').textContent = num(tt);
      $('m-lit').textContent = num(tl);
      $('generated').textContent = 'Index built ' + d.generated + ' from ' + num(d.rows.length) + ' disease-agent records. Only pairs with at least one registered trial or one publication are listed; candidates without clinical evidence are counted in the condition header but not shown.';
      $('score-doc').innerHTML = (d.score_doc || []).map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('');
      readHash();
      syncControls();
      bind();
      render();
    }).catch(function (err) {
      $('rows').innerHTML = '<tr><td colspan="7" class="empty">Could not load the index (' + esc(err.message) + '). Rebuild with <code>python scripts/build_repurposing_index.py</code>.</td></tr>';
      $('count').textContent = 'Index unavailable';
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
