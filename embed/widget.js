/*! Open Source Medicine Research Tracker — latest research embed widget
 *  https://research.opensourcemed.info/embed/
 *  Usage:
 *    <script src="https://research.opensourcemed.info/embed/widget.js"
 *            data-condition="long-covid" data-limit="5" data-theme="light" async></script>
 *  data-condition : one key or a comma list (long-covid, me-cfs, pacvs, lyme,
 *                   gulf-war-illness, pots, mcas, other-post-viral)
 *  data-limit     : number of studies (1-25, default 5)
 *  data-theme     : light (default) or dark
 *  data-title     : optional heading override
 *  No dependencies, no global CSS (styles live in a shadow root), fails
 *  silently to a plain link if the feed cannot be fetched.
 *  Programmatic use: OSMResearchWidget.render(element, {condition, limit, theme}).
 */
(function (win, doc) {
  'use strict';
  var BASE = 'https://research.opensourcemed.info/';
  var LABELS = {
    'long-covid': 'Long COVID', 'me-cfs': 'ME/CFS', 'pacvs': 'PACVS', 'lyme': 'Lyme Disease',
    'gulf-war-illness': 'Gulf War Illness', 'pots': 'POTS', 'mcas': 'MCAS', 'other-post-viral': 'Other Post-Viral Illness'
  };
  var KEYS = Object.keys(LABELS);

  var CSS = [
    ':host{all:initial;display:block;contain:content}',
    '.w{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:14px;line-height:1.45;',
    'color:#1f2937;background:#fff;border:1px solid #e5e7eb;border-radius:12px;box-sizing:border-box;width:100%;max-width:100%;overflow:hidden;display:flex;flex-direction:column;max-height:480px}',
    '.w.dark{color:#e5e7eb;background:#111827;border-color:#374151}',
    '.h{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid #e5e7eb;background:#0068f8;color:#fff}',
    '.w.dark .h{border-color:#374151}',
    '.h .t{font-weight:700;font-size:14px;flex:1;margin:0}',
    '.h .n{font-size:11px;opacity:.85;white-space:nowrap}',
    '.b{overflow-y:auto;flex:1;-webkit-overflow-scrolling:touch}',
    'ol{list-style:none;margin:0;padding:0}',
    'li{padding:10px 14px;border-bottom:1px solid #f1f5f9}',
    '.w.dark li{border-color:#1f2937}',
    'li:last-child{border-bottom:0}',
    'a.s{color:#0068f8;text-decoration:none;font-weight:600;display:block}',
    '.w.dark a.s{color:#60a5fa}',
    'a.s:hover{text-decoration:underline}',
    '.m{font-size:12px;color:#6b7280;margin-top:3px}',
    '.w.dark .m{color:#9ca3af}',
    '.c{display:inline-block;font-size:10px;font-weight:700;letter-spacing:.03em;text-transform:uppercase;padding:1px 6px;border-radius:50px;background:#eff6ff;color:#2563eb;margin-right:6px;vertical-align:middle}',
    '.w.dark .c{background:#1e3a8a;color:#bfdbfe}',
    '.f{padding:8px 14px;font-size:11px;color:#6b7280;border-top:1px solid #e5e7eb;background:#f8fafc}',
    '.w.dark .f{border-color:#374151;background:#0b1220;color:#9ca3af}',
    '.f a{color:inherit;text-decoration:none;font-weight:600}',
    '.f a:hover{text-decoration:underline}',
    '.p{padding:14px;color:#6b7280;font-size:13px}'
  ].join('');

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmtDate(s) {
    if (!s) { return ''; }
    var d = new Date(s);
    if (isNaN(d.getTime())) { return String(s).slice(0, 10); }
    try { return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' }); } catch (e) { return String(s).slice(0, 10); }
  }
  function utm(url, extra) {
    return url + (url.indexOf('?') >= 0 ? '&' : '?') + 'utm_source=embed&utm_medium=widget' + (extra || '');
  }
  function parseConditions(v) {
    var out = [];
    String(v || 'long-covid').toLowerCase().split(/[\s,]+/).forEach(function (k) {
      if (k && LABELS.hasOwnProperty(k) && out.indexOf(k) < 0) { out.push(k); }
    });
    return out.length ? out : ['long-covid'];
  }
  function clampLimit(v) {
    var n = parseInt(v, 10);
    if (isNaN(n)) { n = 5; }
    return Math.max(1, Math.min(25, n));
  }

  function makeRoot(host) {
    var shadow = null;
    if (host.attachShadow) {
      try { shadow = host.shadowRoot || host.attachShadow({ mode: 'open' }); } catch (e) { shadow = null; }
    }
    var root = shadow || host;
    if (!shadow) {
      /* Fallback for very old browsers: inline, element-scoped styles only. */
      host.style.cssText = 'display:block;font-family:Inter,-apple-system,sans-serif;font-size:14px;border:1px solid #e5e7eb;border-radius:12px;max-height:480px;overflow:auto;';
    } else {
      root.innerHTML = '';
      var style = doc.createElement('style');
      style.textContent = CSS;
      root.appendChild(style);
    }
    return root;
  }

  function fallbackHTML(opts) {
    var k = opts.conditions[0];
    return '<div class="w' + (opts.theme === 'dark' ? ' dark' : '') + '"><div class="p">Latest ' + esc(LABELS[k]) + ' research: ' +
      '<a class="s" style="display:inline" href="' + esc(utm(BASE + k + '.html')) + '" target="_blank" rel="noopener">view on Open Source Medicine Research Tracker</a></div></div>';
  }

  function render(host, options) {
    var opts = {
      conditions: parseConditions(options.condition),
      limit: clampLimit(options.limit),
      theme: String(options.theme || 'light').toLowerCase() === 'dark' ? 'dark' : 'light',
      title: options.title || '',
      base: options.base || BASE
    };
    var root = makeRoot(host);
    var container = doc.createElement('div');
    root.appendChild(container);
    container.innerHTML = '<div class="w' + (opts.theme === 'dark' ? ' dark' : '') + '"><div class="p">Loading latest research…</div></div>';

    var fetches = opts.conditions.map(function (k) {
      return fetch(opts.base + 'data/' + k + '.json', { method: 'GET', mode: 'cors', credentials: 'omit', cache: 'default' })
        .then(function (r) { if (!r.ok) { throw new Error(String(r.status)); } return r.json(); })
        .then(function (d) { return { key: k, data: d }; })
        .catch(function () { return null; });
    });

    Promise.all(fetches).then(function (feeds) {
      feeds = feeds.filter(Boolean);
      if (!feeds.length) { container.innerHTML = fallbackHTML(opts); return; }
      var studies = [];
      var updated = '';
      feeds.forEach(function (f) {
        var label = (f.data && f.data.condition) ? String(f.data.condition).split(/\s[–—-]\s/)[0] : LABELS[f.key];
        if (f.data && f.data.last_updated && f.data.last_updated > updated) { updated = f.data.last_updated; }
        (f.data && f.data.studies || []).forEach(function (s) {
          if (s && s.title) { studies.push({ key: f.key, label: label, s: s }); }
        });
      });
      studies.sort(function (a, b) { return String(b.s.pub_date || '').localeCompare(String(a.s.pub_date || '')); });
      studies = studies.slice(0, opts.limit);

      var multi = feeds.length > 1;
      var title = opts.title || ('Latest ' + (multi ? 'post-viral' : LABELS[feeds[0].key]) + ' research');
      var primary = feeds[0].key;
      var html = '<div class="w' + (opts.theme === 'dark' ? ' dark' : '') + '" role="region" aria-label="' + esc(title) + '">' +
        '<div class="h"><h2 class="t">' + esc(title) + '</h2><span class="n">PubMed · ' + studies.length + ' newest</span></div>' +
        '<div class="b"><ol>';
      if (!studies.length) {
        html += '<li class="p">No studies available right now.</li>';
      }
      studies.forEach(function (it) {
        var s = it.s;
        var pm = s.pmid ? 'https://pubmed.ncbi.nlm.nih.gov/' + encodeURIComponent(String(s.pmid)) + '/' : utm(opts.base + it.key + '.html');
        html += '<li>' + (multi ? '<span class="c">' + esc(it.label) + '</span>' : '') +
          '<a class="s" href="' + esc(pm) + '" target="_blank" rel="noopener">' + esc(s.title) + '</a>' +
          '<div class="m">' + esc(fmtDate(s.pub_date)) + (s.journal ? ' · ' + esc(s.journal) : '') +
          (s.authors ? ' · ' + esc(String(s.authors).split(',').slice(0, 2).join(',')) + (String(s.authors).indexOf('et al') >= 0 || String(s.authors).split(',').length > 2 ? ' et al.' : '') : '') + '</div></li>';
      });
      html += '</ol></div>' +
        '<div class="f">Updated ' + esc(fmtDate(updated) || 'daily') + ' · via <a href="' + esc(utm(opts.base + primary + '.html')) + '" target="_blank" rel="noopener">Open Source Medicine Research Tracker</a></div>' +
        '</div>';
      container.innerHTML = html;
    }).catch(function () {
      container.innerHTML = fallbackHTML(opts);
    });
    return host;
  }

  function autoInit() {
    var script = doc.currentScript;
    if (!script) {
      var all = doc.querySelectorAll('script[src*="widget.js"][data-condition], script[src*="embed/widget.js"]');
      script = all[all.length - 1];
    }
    if (!script || script.getAttribute('data-manual') !== null) { return; }
    var host = doc.createElement('div');
    host.className = 'osm-research-widget';
    host.setAttribute('data-osm-widget', '');
    script.parentNode.insertBefore(host, script.nextSibling);
    render(host, {
      condition: script.getAttribute('data-condition'),
      limit: script.getAttribute('data-limit'),
      theme: script.getAttribute('data-theme'),
      title: script.getAttribute('data-title'),
      base: script.getAttribute('data-base') || undefined
    });
  }

  win.OSMResearchWidget = { render: render, conditions: KEYS, labels: LABELS, version: '1.0.0' };
  try { autoInit(); } catch (e) { /* fail silently */ }
})(window, document);
