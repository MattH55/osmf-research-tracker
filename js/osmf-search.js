/* Header search for the Research Tracker. The index loads on first use. */
(function () {
  'use strict';
  var INDEX_URL = '/js/generated/site-search.json?v=1';
  var TYPE_RANK = { Condition: 0, Tool: 1, Biomarker: 2, Therapy: 3, Trial: 4, Comparison: 5, Report: 6, Page: 7, 'Access map': 8, 'Condition + therapy': 9 };
  var index = null, loading = null;

  function load() {
    if (index) return Promise.resolve(index);
    if (!loading) {
      loading = fetch(INDEX_URL).then(function (r) {
        if (!r.ok) throw new Error('search index ' + r.status);
        return r.json();
      }).then(function (rows) {
        index = rows.map(function (r) { return { t: r[0], u: r[1], k: r[2], l: r[0].toLowerCase() }; });
        return index;
      }).catch(function (e) { loading = null; throw e; });
    }
    return loading;
  }

  function search(q) {
    var words = q.toLowerCase().split(/\s+/).filter(Boolean);
    if (!words.length) return [];
    var out = [];
    for (var i = 0; i < index.length; i++) {
      var row = index[i], score = 0, ok = true;
      for (var j = 0; j < words.length; j++) {
        var at = row.l.indexOf(words[j]);
        if (at < 0) { ok = false; break; }
        score += at === 0 ? 0 : (/[\s(\/-]/.test(row.l.charAt(at - 1)) ? 1 : 3);
      }
      if (ok) out.push({ row: row, s: score * 100 + (TYPE_RANK[row.k] === undefined ? 7 : TYPE_RANK[row.k]) * 10 + Math.min(row.l.length, 99) / 100 });
    }
    out.sort(function (a, b) { return a.s - b.s; });
    return out.slice(0, 8).map(function (x) { return x.row; });
  }

  function attach(box) {
    var input = box.querySelector('input'), list = box.querySelector('.osmf-search__results');
    if (!input || !list) return;
    var active = -1, seq = 0;

    function close() { list.hidden = true; list.textContent = ''; active = -1; input.setAttribute('aria-expanded', 'false'); }
    function mark() {
      var items = list.querySelectorAll('a');
      for (var i = 0; i < items.length; i++) items[i].classList.toggle('is-active', i === active);
      if (items[active]) items[active].scrollIntoView({ block: 'nearest' });
    }
    function message(text) {
      list.textContent = '';
      var p = document.createElement('div');
      p.className = 'osmf-search__empty';
      p.textContent = text;
      list.appendChild(p);
      list.hidden = false;
    }
    function render(rows, q) {
      list.textContent = '';
      active = -1;
      if (!rows.length) return message('No pages match “' + q + '”.');
      rows.forEach(function (r) {
        var a = document.createElement('a'), t = document.createElement('span'), k = document.createElement('span');
        a.href = r.u; a.setAttribute('role', 'option');
        t.className = 'osmf-search__title'; t.textContent = r.t;
        k.className = 'osmf-search__type'; k.textContent = r.k;
        a.appendChild(t); a.appendChild(k); list.appendChild(a);
      });
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }
    function run() {
      var q = input.value.trim(), mine = ++seq;
      if (q.length < 2) return close();
      load().then(function () { if (mine === seq) render(search(q), q); })
        .catch(function () { if (mine === seq) message('Search is unavailable right now.'); });
    }

    input.addEventListener('focus', function () { load().catch(function () {}); });
    input.addEventListener('input', run);
    input.addEventListener('keydown', function (e) {
      var items = list.querySelectorAll('a');
      if (e.key === 'ArrowDown' && items.length) { e.preventDefault(); active = (active + 1) % items.length; mark(); }
      else if (e.key === 'ArrowUp' && items.length) { e.preventDefault(); active = (active - 1 + items.length) % items.length; mark(); }
      else if (e.key === 'Enter') {
        var go = items[active < 0 ? 0 : active];
        if (go) { e.preventDefault(); window.location.href = go.href; }
      } else if (e.key === 'Escape') { close(); input.blur(); }
    });
    document.addEventListener('click', function (e) { if (!box.contains(e.target)) close(); });
  }

  function init() {
    var boxes = document.querySelectorAll('.osmf-search');
    for (var i = 0; i < boxes.length; i++) attach(boxes[i]);
    document.addEventListener('keydown', function (e) {
      var tag = (e.target.tagName || '').toLowerCase();
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || tag === 'input' || tag === 'textarea' || tag === 'select' || e.target.isContentEditable) return;
      var first = document.querySelector('.osmf-nav + .osmf-search input');
      if (first && first.offsetParent) { e.preventDefault(); first.focus(); }
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
