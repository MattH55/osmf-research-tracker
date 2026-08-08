// Medical Freedom Maps -- Embeddable Choropleth Component
// Usage: <script src="/maps/embed.js" data-layer="scope-of-practice" data-dimension="np_practice_authority"></script>
// Renders in a shadow DOM. Attribution link is non-removable.
// Data is embedded at build time; no runtime API call needed.

(function(){
  var scripts = document.querySelectorAll('script[data-layer]');
  scripts.forEach(function(script) {
    var layer = script.getAttribute('data-layer');
    var dimension = script.getAttribute('data-dimension') || '';
    var target = script.getAttribute('data-target') || null;
    var container;

    if (target) {
      container = document.querySelector(target);
    } else {
      container = document.createElement('div');
      script.parentNode.insertBefore(container, script);
    }

    var shadow = container.attachShadow({mode: 'open'});
    shadow.innerHTML = '<style>' +
      ':host{display:block;font-family:system-ui,-apple-system,sans-serif;font-size:14px;line-height:1.5;max-width:800px;margin:1rem 0}' +
      '.mw{background:#fff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden}' +
      '.mh{padding:.5rem .75rem;background:#f8fafc;border-bottom:1px solid #e2e8f0;display:flex;justify-content:space-between;align-items:center}' +
      '.mh h4{margin:0;font-size:.875rem;color:#1a1a2e}' +
      '.mh a{font-size:.75rem;color:#2563eb;text-decoration:none}' +
      '.mm{height:300px}' +
      '.ml{padding:.5rem .75rem;font-size:.75rem;color:#64748b;text-align:center;border-top:1px solid #e2e8f0}' +
      '.ml a{color:#94a3b8}' +
      '.leaflet-container{background:#f8fafc}' +
      '.legend{padding:.25rem .5rem;background:rgba(255,255,255,.9);border-radius:4px;font-size:.75rem;line-height:1.4}' +
      '.legend i{width:12px;height:12px;float:left;margin-right:4px;border-radius:2px;opacity:.85}' +
    '</style>' +
    '<div class="mw">' +
      '<div class="mh"><h4>Medical Freedom Maps</h4><a href="https://opensourcemed.info/maps/" target="_blank" rel="noopener">View Full Map</a></div>' +
      '<div class="mm" id="emap-' + (dimension||layer) + '"></div>' +
      '<div class="ml">Data: <a href="https://opensourcemed.info/" target="_blank" rel="noopener">OpenSourceMed.info</a> | CC BY 4.0 | Not legal advice</div>' +
    '</div>';

    // Load Leaflet CSS + JS in the shadow DOM
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
    shadow.appendChild(link);

    var leafletScript = document.createElement('script');
    leafletScript.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    leafletScript.onload = function() {
      initMap(shadow, layer, dimension);
    };
    shadow.appendChild(leafletScript);

    function initMap(shadow, layer, dimension) {
      var mapEl = shadow.getElementById('emap-' + (dimension||layer));
      if (!mapEl) return;
      var map = L.map(mapEl, {scrollWheelZoom: false, zoomControl: true}).setView([39.8, -98.5], 4);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap | <a href="https://opensourcemed.info/maps/">OpenSourceMed Medical Freedom Maps</a>',
        maxZoom: 18
      }).addTo(map);
      // Data is injected at build time below
    }
  });
})();
