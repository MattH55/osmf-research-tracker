/**
 * Shared biomarker atlas renderer — loads data/biomarkers/{slug}.json + trial links
 */
(function () {
  const slug = document.body.dataset.atlas;
  if (!slug) return;

  const DIRECTION_LABELS = {
    up: { text: '↑ Elevated', class: 'direction-up' },
    down: { text: '↓ Reduced', class: 'direction-down' },
    mixed: { text: '↕ Altered', class: 'direction-mixed' },
  };

  let atlas = null;
  let trialLinks = {};
  let commercialLinks = {};
  let consumableLinks = {};
  let interventionLinks = {};
  let agentDiscoveryLinks = {};
  let activeFilter = 'all';
  let trialsOnly = false;
  let commercialOnly = false;
  let consumableOnly = false;

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

  function markerKey(marker) {
    const base = (marker.name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    return `${slug}:${base}`;
  }

  function anchorFromKey(key) {
    return `marker-${String(key).replace(/:/g, '-')}`;
  }

  function keyFromAnchor(anchor) {
    if (!anchor || !anchor.startsWith('marker-')) return null;
    const parts = anchor.slice(7).split('-');
    const slugPart = parts[0];
    if (slugPart !== slug) return null;
    return `${slug}:${parts.slice(1).join('-')}`;
  }

  function findMarkerByKey(key) {
    return atlas?.markers?.find((m) => markerKey(m) === key) || null;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function ensureExtraColumns() {
    const table = document.getElementById('biomarkerTable');
    if (!table) return;
    const headRow = table.querySelector('thead tr');
    if (!headRow) return;
    const trialsTh = headRow.querySelector('[data-col-trials]');
    const interventionsTh = headRow.querySelector('[data-col-interventions]');
    if (!headRow.querySelector('[data-col-labs]')) {
      const th = document.createElement('th');
      th.setAttribute('data-col-labs', '');
      th.textContent = 'Lab Tests';
      if (trialsTh) headRow.insertBefore(th, trialsTh);
      else if (interventionsTh) headRow.insertBefore(th, interventionsTh);
      else headRow.appendChild(th);
    }
    if (!trialsTh) {
      const th = document.createElement('th');
      th.setAttribute('data-col-trials', '');
      th.textContent = 'Clinical Trials (Outcome)';
      if (interventionsTh) headRow.insertBefore(th, interventionsTh);
      else headRow.appendChild(th);
    }
    if (!interventionsTh) {
      const th = document.createElement('th');
      th.setAttribute('data-col-interventions', '');
      th.textContent = 'Interventions';
      headRow.appendChild(th);
    }
  }

  function markerDetailHref(key) {
    return `#${anchorFromKey(key)}`;
  }

  function renderInterventionCell(marker, key) {
    const info = interventionLinks[key];
    const agents = info?.interventions || [];
    if (!agents.length) {
      return '<td class="intervention-cell"><span class="intervention-none">—</span></td>';
    }
    const chips = agents.slice(0, 3).map((a) => {
      const title = [
        a.preferredTerm,
        a.categories?.length ? `(${a.categories.join(', ')})` : '',
        `${a.nctIds?.length || 0} trial(s)`,
        a.literature?.pmidCount ? `${a.literature.pmidCount} PubMed hit(s)` : '',
      ].filter(Boolean).join(' — ');
      return `<span class="intervention-chip intervention-chip-preview" title="${escapeAttr(title)}">${escapeAttr(a.preferredTerm)}</span>`;
    }).join('');
    const more = agents.length > 3
      ? `<a class="marker-detail-link" href="${markerDetailHref(key)}">+${agents.length - 3} more</a>`
      : '';
    const viewAll = `<a class="marker-detail-link" href="${markerDetailHref(key)}">All ${agents.length} interventions →</a>`;
    return `<td class="intervention-cell"><div class="intervention-chips scroll-panel-sm">${chips}${more}</div>${viewAll}</td>`;
  }

  function renderCommercialCell(marker, key) {
    const info = commercialLinks[key];
    if (!info || !info.vendors?.length) {
      return '<td class="lab-cell"><span class="lab-none">—</span></td>';
    }
    const chips = info.vendors.slice(0, 2).map((v) =>
      `<a class="lab-chip lab-${info.availability}" href="${escapeAttr(v.url)}" target="_blank" rel="noopener" title="${escapeAttr(info.testName || marker.name)}">${escapeAttr(v.vendor)}</a>`
    ).join('');
    const moreLabs = info.vendors.length > 2
      ? `<a class="marker-detail-link" href="${markerDetailHref(key)}">+${info.vendors.length - 2} labs</a>`
      : '';
    const note = info.note
      ? `<div class="lab-note">${escapeAttr(info.note)}</div>`
      : '';
    return `<td class="lab-cell"><div class="lab-chips scroll-panel-sm">${chips}${moreLabs}</div>${note}</td>`;
  }

  function renderTrialCell(marker, key) {
    const trials = trialLinks[key] || [];
    if (!trials.length) {
      return '<td class="trial-cell"><span class="trial-none">—</span></td>';
    }
    const nctSet = new Set();
    const chips = trials.slice(0, 3).map((t) => {
      if (nctSet.has(t.nct_id)) return '';
      nctSet.add(t.nct_id);
      const type = t.outcomeType === 'primary' ? 'primary' : 'secondary';
      const title = `${t.title} — ${t.outcomeMeasure} (${t.outcomeType})`;
      return `<a class="trial-chip trial-${type}" href="${escapeAttr(t.link)}" target="_blank" rel="noopener" title="${escapeAttr(title)}">${t.nct_id}</a>`;
    }).filter(Boolean).join('');
    const uniqueNct = new Set(trials.map((t) => t.nct_id)).size;
    const more = trials.length > 3
      ? `<a class="marker-detail-link" href="${markerDetailHref(key)}">+${trials.length - 3} outcomes</a>`
      : '';
    const viewAll = `<a class="marker-detail-link" href="${markerDetailHref(key)}">All ${uniqueNct} trial${uniqueNct === 1 ? '' : 's'} →</a>`;
    return `<td class="trial-cell"><div class="trial-chips scroll-panel-sm">${chips}${more}</div>${viewAll}</td>`;
  }

  function escapeAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
  }

  function highlight(text, query) {
    if (!query || query.length < 2) return text;
    const re = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(re, '<mark>$1</mark>');
  }

  function renderConsumableTag(marker, key) {
    const info = consumableLinks[key];
    if (!info?.consumable) return '';
    const title = escapeAttr(info.note || info.productName || marker.name);
    return `<a class="consumable-chip" href="${markerDetailHref(key)}" title="${title}">Consumable</a>`;
  }

  function renderMarkerLink(name, key, query) {
    return `<a href="${markerDetailHref(key)}" class="marker-link">${highlight(name, query)}</a>`;
  }

  function renderDetailTrials(trials) {
    if (!trials.length) {
      return '<p class="marker-detail-empty">No clinical trials linked as outcome measures for this marker.</p>';
    }
    return `<ul class="marker-detail-list marker-detail-trials">${trials.map((t) => {
      const type = t.outcomeType === 'primary' ? 'primary' : 'secondary';
      const desc = t.outcomeDescription
        ? `<div class="marker-detail-desc">${escapeHtml(t.outcomeDescription)}</div>`
        : '';
      const conds = (t.mapped_conditions || []).length
        ? `<div class="marker-detail-meta">${escapeHtml(t.mapped_conditions.join(', '))}</div>`
        : '';
      return `<li>
        <div class="marker-detail-item-head">
          <a class="trial-chip trial-${type}" href="${escapeAttr(t.link)}" target="_blank" rel="noopener">${escapeHtml(t.nct_id)}</a>
          <span class="marker-detail-outcome-type">${escapeHtml(t.outcomeType)} outcome</span>
          ${t.phase ? `<span class="marker-detail-phase">${escapeHtml(t.phase)}</span>` : ''}
          ${t.status ? `<span class="marker-detail-status">${escapeHtml(t.status)}</span>` : ''}
        </div>
        <div class="marker-detail-item-title">${escapeHtml(t.title)}</div>
        <div class="marker-detail-measure"><strong>Outcome measure:</strong> ${escapeHtml(t.outcomeMeasure)}</div>
        ${desc}
        ${conds}
      </li>`;
    }).join('')}</ul>`;
  }

  function renderDetailInterventions(agents, provisional, label, emptyText) {
    if (!agents.length) {
      return provisional?.length
        ? ''
        : `<p class="marker-detail-empty">${emptyText}</p>`;
    }
    return `<div class="marker-detail-subsection">
      <h4>${escapeHtml(label)} (${agents.length})</h4>
      <ul class="marker-detail-list marker-detail-interventions">${agents.map((a) => {
        const trialList = (a.trials || []).map((t) =>
          `<a href="${escapeAttr(t.link)}" target="_blank" rel="noopener" class="trial-chip trial-secondary">${escapeHtml(t.nct_id)}</a>`
        ).join(' ');
        const articles = (a.literature?.topArticles || []).map((art) =>
          `<li><a href="${escapeAttr(art.url)}" target="_blank" rel="noopener">${escapeHtml(art.title)}</a>
            <span class="marker-detail-article-meta">${escapeHtml(art.journal)} · ${escapeHtml(art.pubDate)}</span></li>`
        ).join('');
        const articleBlock = articles
          ? `<ul class="marker-detail-articles">${articles}</ul>`
          : '';
        const litQuery = a.literature?.query
          ? `<div class="marker-detail-query"><strong>PubMed query:</strong> <code>${escapeHtml(a.literature.query)}</code></div>`
          : '';
        return `<li>
          <div class="marker-detail-item-head">
            <span class="intervention-chip">${escapeHtml(a.preferredTerm)}</span>
            ${(a.categories || []).map((c) => `<span class="marker-detail-cat">${escapeHtml(c)}</span>`).join('')}
          </div>
          ${a.rawAgents?.length ? `<div class="marker-detail-meta">Trial labels: ${escapeHtml(a.rawAgents.join('; '))}</div>` : ''}
          ${trialList ? `<div class="marker-detail-trial-refs">${trialList}</div>` : ''}
          ${a.literature?.pmidCount ? `<div class="marker-detail-meta">${a.literature.pmidCount} PubMed hit(s)</div>` : ''}
          ${litQuery}
          ${articleBlock}
        </li>`;
      }).join('')}</ul>
    </div>`;
  }

  function renderDetailPharmacology(key) {
    const entry = agentDiscoveryLinks[key];
    const pipeline = entry?.pipeline;
    const agents = pipeline?.agents || [];
    if (!agents.length) return '';

    const tierOrder = ['mechanistic', 'clinical', 'correlative'];
    const byTier = {};
    for (const a of agents) {
      const t = a.evidence_tier || 'correlative';
      if (!byTier[t]) byTier[t] = [];
      byTier[t].push(a);
    }

    const sections = tierOrder.filter((t) => byTier[t]?.length).map((tier) => {
      const items = byTier[tier].slice(0, 40).map((a) => {
        const sources = (a.sources || []).map((s) => {
          if (s.url) {
            return `<a href="${escapeAttr(s.url)}" target="_blank" rel="noopener">${escapeHtml(s.database || 'source')}</a>`;
          }
          if (s.pubmed_id) {
            return `<a href="https://pubmed.ncbi.nlm.nih.gov/${escapeAttr(s.pubmed_id)}/" target="_blank" rel="noopener">PMID ${escapeHtml(s.pubmed_id)}</a>`;
          }
          return escapeHtml(s.database || '');
        }).filter(Boolean).join(', ');
        const potency = a.potency?.value
          ? `<span class="marker-detail-meta">${escapeHtml(String(a.potency.measure || ''))} ${escapeHtml(String(a.potency.value))} ${escapeHtml(String(a.potency.unit || ''))}</span>`
          : '';
        const ncts = (a.clinical_trial_refs || []).map((n) =>
          `<a class="trial-chip trial-secondary" href="https://clinicaltrials.gov/study/${escapeAttr(n)}" target="_blank" rel="noopener">${escapeHtml(n)}</a>`
        ).join(' ');
        return `<li>
          <div class="marker-detail-item-head">
            <span class="intervention-chip">${escapeHtml(a.agent_name)}</span>
            <span class="marker-detail-cat">${escapeHtml(a.direction_of_effect || 'unclear')}</span>
          </div>
          ${potency}
          ${sources ? `<div class="marker-detail-meta">Sources: ${sources}</div>` : ''}
          ${ncts ? `<div class="marker-detail-trial-refs">${ncts}</div>` : ''}
        </li>`;
      }).join('');
      return `<div class="marker-detail-subsection"><h4>${escapeHtml(tier)} (${byTier[tier].length})</h4><ul class="marker-detail-list">${items}</ul></div>`;
    }).join('');

    const notes = (pipeline.coverage_notes || []).map((n) => `<li>${escapeHtml(n)}</li>`).join('');
    return `<div class="marker-detail-block">
      <h4>Pharmacology pipeline (DGIdb / Open Targets / ChEMBL / CTD / PubMed)</h4>
      <p class="marker-detail-note">Evidence-tiered agents from structured databases and grounded literature extraction. DrugBank excluded.</p>
      ${sections}
      ${notes ? `<ul class="marker-detail-note">${notes}</ul>` : ''}
    </div>`;
  }

  function renderMarkerDetail(key) {
    const marker = findMarkerByKey(key);
    if (!marker || !atlas) return '';

    const dir = DIRECTION_LABELS[marker.direction] || DIRECTION_LABELS.mixed;
    const trials = trialLinks[key] || [];
    const labInfo = commercialLinks[key];
    const consumable = consumableLinks[key];
    const interventionInfo = interventionLinks[key];
    const validated = interventionInfo?.interventions || [];
    const provisional = interventionInfo?.provisional || [];

    const labBlock = labInfo?.vendors?.length
      ? `<div class="marker-detail-block">
          <h4>Lab tests (${escapeHtml(labInfo.availability)})</h4>
          <div class="marker-detail-test-name">${escapeHtml(labInfo.testName || marker.name)}</div>
          <div class="lab-links">${labInfo.vendors.map((v) =>
            `<a class="lab-chip lab-${labInfo.availability}" href="${escapeAttr(v.url)}" target="_blank" rel="noopener">${escapeHtml(v.vendor)}</a>`
          ).join('')}</div>
          ${labInfo.note ? `<p class="marker-detail-note">${escapeHtml(labInfo.note)}</p>` : ''}
        </div>`
      : '';

    const consumableBlock = consumable?.consumable
      ? `<div class="marker-detail-block">
          <h4>Consumable product</h4>
          <p><span class="consumable-chip">Consumable</span> ${escapeHtml(consumable.productName || marker.name)}
            ${consumable.productType ? `<span class="marker-detail-cat">${escapeHtml(consumable.productType)}</span>` : ''}</p>
          ${consumable.note ? `<p class="marker-detail-note">${escapeHtml(consumable.note)}</p>` : ''}
        </div>`
      : '';

    return `<div class="marker-detail-header">
        <div>
          <h3 id="${anchorFromKey(key)}-title">${escapeHtml(marker.name)}</h3>
          ${marker.alternateName ? `<div class="marker-detail-alias">${escapeHtml(marker.alternateName)}</div>` : ''}
        </div>
        <button type="button" class="marker-detail-close" aria-label="Close marker detail">×</button>
      </div>
      <div class="marker-detail-badges">
        <span class="direction-badge ${dir.class}">${dir.text}</span>
        <span class="category-tag cat-${marker.category}">${escapeHtml(atlas.categories[marker.category] || marker.category)}</span>
        ${marker.loinc ? `<span class="marker-loinc">LOINC ${escapeHtml(marker.loinc)}</span>` : ''}
      </div>
      <div class="marker-detail-grid">
        <div class="marker-detail-block">
          <h4>Comparison</h4>
          <p>${escapeHtml(marker.comparison || '—')}</p>
        </div>
        <div class="marker-detail-block">
          <h4>Associated symptoms</h4>
          <p>${escapeHtml(marker.symptoms || '—')}</p>
        </div>
        <div class="marker-detail-block">
          <h4>Key reference</h4>
          <p><a class="ref-link" href="https://doi.org/${escapeAttr(marker.reference.doi)}" target="_blank" rel="noopener">${escapeHtml(marker.reference.citation)}</a></p>
        </div>
      </div>
      ${labBlock}
      ${consumableBlock}
      <div class="marker-detail-block">
        <h4>Clinical trials (outcome measures)</h4>
        ${renderDetailTrials(trials)}
      </div>
      <div class="marker-detail-block">
        <h4>Interventions</h4>
        <p class="marker-detail-note">Agents from trials measuring this biomarker as an outcome, narrowed by PubMed therapeutic–biomarker literature search.</p>
        ${renderDetailInterventions(validated, provisional, 'Literature-validated', 'No literature-validated interventions for this marker yet.')}
        ${provisional.length ? renderDetailInterventions(provisional, [], 'Trial-sourced only (no PubMed pair hit)', '') : ''}
      </div>
      ${renderDetailPharmacology(key)}`;
  }

  function ensureDetailPanel() {
    if (document.getElementById('markerDetailPanel')) return;
    const section = document.querySelector('#biomarker-database .table-wrapper')
      || document.getElementById('tableBody')?.closest('.table-wrapper')
      || document.getElementById('tableBody')?.parentElement;
    if (!section) return;

    const panel = document.createElement('div');
    panel.id = 'markerDetailPanel';
    panel.className = 'marker-detail-panel';
    panel.hidden = true;
    panel.setAttribute('aria-hidden', 'true');
    panel.innerHTML = '<div class="marker-detail-inner" id="markerDetailContent"></div>';
    section.parentNode.insertBefore(panel, section.nextSibling);

    panel.addEventListener('click', (e) => {
      if (e.target.classList.contains('marker-detail-close')) {
        closeMarkerDetail();
      }
    });
  }

  function openMarkerDetail(key) {
    const panel = document.getElementById('markerDetailPanel');
    const content = document.getElementById('markerDetailContent');
    if (!panel || !content) return;

    const html = renderMarkerDetail(key);
    if (!html) return;

    content.innerHTML = html;
    panel.hidden = false;
    panel.setAttribute('aria-hidden', 'false');
    document.body.classList.add('marker-detail-open');

    const anchor = anchorFromKey(key);
    if (location.hash !== `#${anchor}`) {
      history.replaceState(null, '', `#${anchor}`);
    }

    const row = document.getElementById(anchor);
    if (row) row.classList.add('marker-row-active');
    panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function closeMarkerDetail() {
    const panel = document.getElementById('markerDetailPanel');
    if (panel) {
      panel.hidden = true;
      panel.setAttribute('aria-hidden', 'true');
    }
    document.body.classList.remove('marker-detail-open');
    document.querySelectorAll('.marker-row-active').forEach((el) => el.classList.remove('marker-row-active'));
    if (location.hash.startsWith('#marker-')) {
      history.replaceState(null, '', `${location.pathname}${location.search}`);
    }
  }

  function syncDetailFromHash() {
    const anchor = location.hash.replace(/^#/, '');
    const key = keyFromAnchor(anchor);
    if (key && findMarkerByKey(key)) {
      openMarkerDetail(key);
      return;
    }
    closeMarkerDetail();
  }

  function renderTable(data) {
    const tbody = document.getElementById('tableBody');
    const countEl = document.getElementById('resultsCount');
    if (!tbody || !atlas) return;

    const categories = atlas.categories;
    const searchInput = document.getElementById('searchInput');
    const query = (searchInput?.value || '').trim();

    tbody.innerHTML = data.map((b) => {
      const dir = DIRECTION_LABELS[b.direction] || DIRECTION_LABELS.mixed;
      const loincBadge = b.loinc
        ? `<div class="marker-loinc">LOINC ${b.loinc}</div>`
        : '';
      const key = markerKey(b);
      const hasTrials = (trialLinks[key] || []).length > 0;
      const labInfo = commercialLinks[key];
      const hasCommercial = labInfo && labInfo.availability === 'commercial';
      const hasConsumable = !!(consumableLinks[key]?.consumable);
      const anchor = anchorFromKey(key);
      return `<tr id="${anchor}" data-marker-key="${escapeAttr(key)}" data-category="${b.category}" data-has-trials="${hasTrials ? '1' : '0'}" data-has-commercial="${hasCommercial ? '1' : '0'}" data-has-consumable="${hasConsumable ? '1' : '0'}">
        <td>
          <div class="marker-name">${renderMarkerLink(b.name, key, query)}${renderConsumableTag(b, key)}</div>
          <div class="marker-alias">${highlight(b.alternateName || '', query)}</div>
          ${loincBadge}
        </td>
        <td><span class="direction-badge ${dir.class}">${dir.text}</span></td>
        <td><span class="category-tag cat-${b.category}">${categories[b.category] || b.category}</span></td>
        <td>${b.comparison}</td>
        <td>${b.symptoms || ''}</td>
        <td><a class="ref-link" href="https://doi.org/${b.reference.doi}" target="_blank" rel="noopener">${b.reference.citation}</a></td>
        ${renderCommercialCell(b, key)}
        ${renderTrialCell(b, key)}
        ${renderInterventionCell(b, key)}
      </tr>`;
    }).join('');

    if (countEl) {
      const label = atlas.slug === 'lyme' ? 'markers' : 'alterations';
      const trialNote = trialsOnly ? ' with trial outcome links' : '';
      countEl.textContent = `Showing ${data.length} of ${atlas.markers.length} ${label}${trialNote}`;
    }

    const activeAnchor = location.hash.replace(/^#/, '');
    if (activeAnchor.startsWith('marker-')) {
      document.getElementById(activeAnchor)?.classList.add('marker-row-active');
    }
  }

  function tokenizeSearch(q) {
    return q
      .toLowerCase()
      .split(/[\s,;/]+/)
      .map((t) => t.replace(/^[()[\]{}]+|[()[\]{}]+$/g, ''))
      .filter((t) => t.length >= 1);
  }

  function filterData() {
    const searchInput = document.getElementById('searchInput');
    const raw = (searchInput?.value || '').trim().toLowerCase();
    const tokens = tokenizeSearch(raw);

    return atlas.markers.filter((b) => {
      const matchCategory = activeFilter === 'all' || b.category === activeFilter;
      const searchStr = [
        b.name, b.alternateName, b.symptoms, b.category, b.comparison,
        b.reference?.citation, b.loinc, b.testType,
        atlas.categories[b.category],
      ].filter(Boolean).join(' ').toLowerCase();

      const key = markerKey(b);
      const trialTexts = (trialLinks[key] || []).map((t) =>
        `${t.nct_id} ${t.title} ${t.outcomeMeasure} ${t.outcomeDescription || ''}`
      ).join(' ').toLowerCase();
      const interventionTexts = (interventionLinks[key]?.interventions || [])
        .map((a) => `${a.preferredTerm} ${(a.categories || []).join(' ')}`)
        .join(' ').toLowerCase();
      const full = `${searchStr} ${trialTexts} ${interventionTexts}`;

      const matchSearch = !tokens.length || tokens.every((tok) => full.includes(tok));
      const matchTrials = !trialsOnly || (trialLinks[key] || []).length > 0;
      const labInfo = commercialLinks[key];
      const matchCommercial = !commercialOnly || (labInfo && labInfo.availability === 'commercial');
      const matchConsumable = !consumableOnly || consumableLinks[key]?.consumable;
      return matchCategory && matchSearch && matchTrials && matchCommercial && matchConsumable;
    });
  }

  function buildFilters() {
    const container = document.getElementById('categoryFilters');
    if (!container || !atlas) return;

    const buttons = ['<button class="filter-btn active" data-filter="all">All</button>'];
    for (const key of atlas.filters) {
      const label = atlas.categories[key] || key;
      buttons.push(`<button class="filter-btn" data-filter="${key}">${label}</button>`);
    }
    container.innerHTML = buttons.join('');

    container.addEventListener('click', (e) => {
      if (!e.target.classList.contains('filter-btn')) return;
      container.querySelectorAll('.filter-btn').forEach((btn) => btn.classList.remove('active'));
      e.target.classList.add('active');
      activeFilter = e.target.dataset.filter;
      renderTable(filterData());
    });
  }

  function bindTrialsToggle() {
    const toggle = document.getElementById('trialsOnlyFilter');
    if (toggle) {
      toggle.addEventListener('change', () => {
        trialsOnly = toggle.checked;
        renderTable(filterData());
      });
    }
    const commercialToggle = document.getElementById('commercialOnlyFilter');
    if (commercialToggle) {
      commercialToggle.addEventListener('change', () => {
        commercialOnly = commercialToggle.checked;
        renderTable(filterData());
      });
    }
    const consumableToggle = document.getElementById('consumableOnlyFilter');
    if (consumableToggle) {
      consumableToggle.addEventListener('change', () => {
        consumableOnly = consumableToggle.checked;
        renderTable(filterData());
      });
    }
  }

  async function init() {
    const countEl = document.getElementById('resultsCount');
    if (countEl) countEl.textContent = 'Loading biomarker data…';

    try {
      const loader = await getDataLoader();

      delete window.__BIOMARKER_ATLAS__;
      delete window.__BIOMARKER_TRIAL_LINKS__;
      delete window.__BIOMARKER_COMMERCIAL__;
      delete window.__BIOMARKER_CONSUMABLE__;
      delete window.__BIOMARKER_INTERVENTIONS__;
      delete window.__BIOMARKER_AGENT_DISCOVERY__;

      const [atlasData, trialData, commercialData, consumableData, interventionData, agentDiscoveryData] = await Promise.all([
        loader.fetchOrBundle(
          `data/biomarkers/${slug}.json`,
          '__BIOMARKER_ATLAS__',
          `js/generated/atlas-${slug}.bundle.js`
        ),
        loader.fetchOrBundle(
          'data/biomarkers/trial-links.json',
          '__BIOMARKER_TRIAL_LINKS__',
          `js/generated/trial-links-${slug}.bundle.js`
        ).catch(() => ({ markerTrials: {} })),
        loader.fetchOrBundle(
          'data/biomarkers/commercial-links.json',
          '__BIOMARKER_COMMERCIAL__',
          'js/generated/commercial-links.bundle.js'
        ).catch(() => ({ markerCommercial: {} })),
        loader.fetchOrBundle(
          'data/biomarkers/consumable-links.json',
          '__BIOMARKER_CONSUMABLE__',
          'js/generated/consumable-links.bundle.js'
        ).catch(() => ({ markerConsumable: {} })),
        loader.fetchOrBundle(
          'data/biomarkers/intervention-links.json',
          '__BIOMARKER_INTERVENTIONS__',
          'js/generated/intervention-links.bundle.js'
        ).catch(() => ({ markerInterventions: {} })),
        loader.fetchOrBundle(
          'data/biomarkers/agent-discovery.json',
          '__BIOMARKER_AGENT_DISCOVERY__',
          'js/generated/agent-discovery.bundle.js'
        ).catch(() => ({ markerAgents: {} })),
      ]);

      atlas = atlasData;
      trialLinks = trialData.markerTrials || {};
      commercialLinks = commercialData.markerCommercial || {};
      consumableLinks = consumableData.markerConsumable || {};
      interventionLinks = interventionData.markerInterventions || {};
      agentDiscoveryLinks = Object.fromEntries(
        Object.entries(agentDiscoveryData.markerAgents || {}).map(([k, v]) => [k, v])
      );

      ensureExtraColumns();
      ensureDetailPanel();
      buildFilters();
      bindTrialsToggle();
      renderTable(atlas.markers);
      syncDetailFromHash();
      window.addEventListener('hashchange', syncDetailFromHash);

      const searchInput = document.getElementById('searchInput');
      if (searchInput) {
        searchInput.addEventListener('input', () => renderTable(filterData()));
        searchInput.placeholder = 'Search markers, symptoms, LOINC, or linked trial outcomes…';
      }
    } catch (err) {
      if (countEl) countEl.textContent = `Failed to load biomarker data: ${err.message}`;
      console.error('Biomarker atlas load error:', err);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();