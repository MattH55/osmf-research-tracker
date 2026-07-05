/**
 * Cross-condition biomarker database search on biomarker-atlas.html hub.
 */
(function () {
  const hub = document.getElementById('biomarkerDatabase');
  if (!hub) return;

  let index = [];
  let ready = false;
  let debounceTimer = null;

  async function getDataLoader() {
    if (window.BiomarkerDataLoader) return window.BiomarkerDataLoader;
    for (let i = 0; i < 100; i++) {
      await new Promise((r) => setTimeout(r, 10));
      if (window.BiomarkerDataLoader) return window.BiomarkerDataLoader;
    }
    await new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'js/biomarker-data-loader.js';
      s.onload = resolve;
      s.onerror = () => reject(new Error('data loader missing'));
      document.head.appendChild(s);
    });
    if (!window.BiomarkerDataLoader) throw new Error('data loader missing');
    return window.BiomarkerDataLoader;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function markerDetailUrl(page, id) {
    return `${page}#marker-${String(id).replace(/:/g, '-')}`;
  }

  function tokenize(q) {
    return q
      .toLowerCase()
      .split(/[\s,;/]+/)
      .map((t) => t.replace(/^[()[\]{}]+|[()[\]{}]+$/g, ''))
      .filter((t) => t.length >= 1);
  }

  function renderConsumableInterventionChip(marker, detailUrl) {
    if (!marker.consumable?.consumable) return '';
    const title = escapeHtml(
      marker.consumable.note || marker.consumable.productName || 'Consumable product'
    );
    return `<a class="intervention-chip intervention-chip-consumable consumable-chip" href="${detailUrl}" title="${title}">Consumable</a>`;
  }

  function renderInterventionChips(marker, detailUrl) {
    const consumableChip = renderConsumableInterventionChip(marker, detailUrl);
    const agents = marker.interventions?.agents || [];
    const agentChips = agents.slice(0, 3).map((a) => {
      const label = escapeHtml(a.preferredTerm);
      const title = escapeHtml(`${a.preferredTerm} — ${a.trialCount} trial(s), ${a.pmidCount} PubMed hit(s)`);
      return `<span class="intervention-chip intervention-chip-preview" title="${title}">${label}</span>`;
    }).join('');
    const moreAgents = agents.length > 3
      ? `<a href="${detailUrl}" class="marker-detail-link">+${marker.interventions.count - 3} more</a>`
      : '';

    if (consumableChip || agentChips) {
      return `${consumableChip}${agentChips}${moreAgents}`;
    }
    return '<span class="intervention-none">No validated intervention link</span>';
  }

  function renderLoading() {
    const el = document.getElementById('databaseResults');
    const countEl = document.getElementById('databaseCount');
    if (el) {
      el.innerHTML = '<p class="database-empty">Loading biomarker database…</p>';
    }
    if (countEl) countEl.textContent = '';
  }

  function renderResults(items) {
    const el = document.getElementById('databaseResults');
    const countEl = document.getElementById('databaseCount');
    if (!el) return;

    if (!ready) {
      renderLoading();
      return;
    }

    if (!items.length) {
      el.innerHTML = '<p class="database-empty">No markers match your search. Try a biomarker name, condition, or NCT ID.</p>';
      if (countEl) countEl.textContent = '0 results';
      return;
    }

    if (countEl) countEl.textContent = `${items.length} result${items.length === 1 ? '' : 's'}`;

    el.innerHTML = items.slice(0, 80).map((m) => {
      const detailUrl = markerDetailUrl(m.page, m.id);
      const trials = m.trials || [];
      const trialChips = trials.length
        ? `${trials.slice(0, 3).map((t) =>
          `<a href="${t.link}" target="_blank" rel="noopener" class="trial-chip trial-${t.outcomeType}" title="${escapeHtml(t.outcomeMeasure)}">${t.nct_id}</a>`
        ).join('')}${m.trialCount > 3 ? `<a href="${detailUrl}" class="marker-detail-link">+${m.trialCount - 3} trials</a>` : ''}`
        : '<span class="trial-none">No trial outcome link</span>';
      const labChips = m.commercial?.vendors?.length
        ? m.commercial.vendors.map((v) =>
          `<a href="${v.url}" target="_blank" rel="noopener" class="lab-chip lab-${m.commercial.availability}">${escapeHtml(v.vendor)}</a>`
        ).join('')
        : '<span class="lab-none">No commercial lab link</span>';
      const consumableHtml = m.consumable?.consumable
        ? `<a class="consumable-chip" href="${detailUrl}" title="${escapeHtml(m.consumable.note || m.consumable.productName || '')}">Consumable</a>`
        : '';
      const interventionChips = renderInterventionChips(m, detailUrl);
      return `<article class="db-row">
        <div class="db-main">
          <a href="${detailUrl}" class="db-name">${escapeHtml(m.name)}</a>${consumableHtml}
          ${m.alternateName ? `<div class="db-alias">${escapeHtml(m.alternateName)}</div>` : ''}
          <div class="db-meta">
            <span class="db-condition">${escapeHtml(m.condition)}</span>
            <span class="db-cat">${escapeHtml(m.categoryLabel)}</span>
            ${m.loinc ? `<span class="db-loinc">LOINC ${m.loinc}</span>` : ''}
          </div>
        </div>
        <div class="db-side">
          <div class="db-side-section db-side-labs">
            <span class="db-side-label">Lab tests</span>
            <div class="db-labs scroll-panel-sm">${labChips}</div>
          </div>
          <div class="db-side-section db-side-trials">
            <span class="db-side-label">Clinical trials</span>
            <div class="db-trials scroll-panel-sm">${trialChips}</div>
          </div>
          <div class="db-side-section db-side-interventions">
            <span class="db-side-label">Interventions</span>
            <div class="db-interventions scroll-panel-sm">${interventionChips}</div>
          </div>
          <a href="${detailUrl}" class="db-view">Full marker details →</a>
        </div>
      </article>`;
    }).join('');

    if (items.length > 80) {
      el.innerHTML += `<p class="database-more">Showing 80 of ${items.length}. Refine your search or open a condition atlas.</p>`;
    }
  }

  function filterIndex() {
    const q = (document.getElementById('databaseSearch')?.value || '').trim();
    const condition = document.getElementById('databaseCondition')?.value || 'all';
    const trialsOnly = document.getElementById('databaseTrialsOnly')?.checked;
    const tokens = tokenize(q);

    return index.filter((m) => {
      if (condition !== 'all' && m.slug !== condition) return false;
      if (trialsOnly && !m.trialCount) return false;
      if (!tokens.length) return true;
      const hay = `${m.searchText || ''} ${(m.trials || []).map((t) => `${t.nct_id} ${t.outcomeMeasure}`).join(' ')} ${(m.interventions?.agents || []).map((a) => a.preferredTerm).join(' ')} ${m.consumable?.consumable ? 'consumable' : ''}`.toLowerCase();
      return tokens.every((tok) => hay.includes(tok));
    });
  }

  function onSearch() {
    renderResults(filterIndex());
  }

  function bindControls() {
    const search = document.getElementById('databaseSearch');
    const cond = document.getElementById('databaseCondition');
    const trialsOnly = document.getElementById('databaseTrialsOnly');

    if (search) {
      search.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(onSearch, 120);
      });
    }
    if (cond) cond.addEventListener('change', onSearch);
    if (trialsOnly) trialsOnly.addEventListener('change', onSearch);
  }

  async function init() {
    renderLoading();
    try {
      const loader = await getDataLoader();

      const data = await loader.fetchOrBundle(
        'data/biomarkers/search-index.json',
        '__BIOMARKER_SEARCH_INDEX__',
        'js/generated/search-index.bundle.js'
      );
      index = data.markers || [];
      ready = true;
      bindControls();
      onSearch();
    } catch (err) {
      ready = true;
      const el = document.getElementById('databaseResults');
      if (el) {
        el.innerHTML = `<p class="database-empty">Database index unavailable (${escapeHtml(err.message)}). Run npm run build:seo.</p>`;
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();