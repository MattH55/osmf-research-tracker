/**
 * Cross-cutting biomarker index: aggregates markers across every atlas listed
 * in data/condition-categories.json (any condition entry with a "biomarkers"
 * field), dedupes by marker name, and shows which conditions each marker
 * appears in. Deliberately independent of search-index.json / the trial-linking
 * build pipeline (scripts/build-biomarker-trial-links.js), which is hardcoded
 * to the 5 original post-viral conditions and does its own ClinicalTrials.gov
 * matching — this page only needs the atlas JSON files themselves.
 */
(function () {
  const tableBody = document.getElementById('crossIndexBody');
  const searchInput = document.getElementById('crossIndexSearch');
  const resultsCount = document.getElementById('crossIndexCount');
  const conditionFilter = document.getElementById('crossIndexConditionFilter');

  let allRows = [];

  // Greek letters used in cytokine/receptor nomenclature (IL-1α vs IL-1β are
  // *different* genes, so these are transliterated to a trailing letter, not
  // stripped, to avoid incorrectly merging distinct markers.
  const GREEK_MAP = { 'α': 'A', 'β': 'B', 'γ': 'G', 'δ': 'D', 'ε': 'E', 'κ': 'K', 'λ': 'L' };

  // Trailing parentheticals in this dataset are used two ways: a true
  // synonym/abbreviation ("Interleukin-6 (IL-6)") or a specimen/context
  // qualifier ("ATP (plasma)", "Heart rate variability (PTLDS)"). Only the
  // former identifies the same marker across atlases; treating the latter as
  // a synonym key would wrongly merge unrelated markers that just happen to
  // share a specimen type or disease-context tag.
  const QUALIFIER_STOPLIST = new Set([
    'plasma', 'serum', 'blood', 'urine', 'urinary', 'csf', 'tissue', 'panel',
    'composite', 'screening', 'exercise', 'diurnal', 'research', 'synovial',
    'flagellin', 'ptlds', 'mecfs', 'gwi', 'hc', 'r',
  ]);

  function escapeHtml(s) {
    return (s || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }

  /**
   * Collapse synonymous marker names to one grouping key.
   * "Interleukin-6 (IL-6)" and "IL-6" and "IL6" all -> "IL6", so the same
   * underlying marker groups together across atlases even though each atlas
   * was authored independently and spells the name differently. Multi-word
   * or stoplisted parentheticals (specimen type, disease-context tags) are
   * not treated as synonyms — the full name is used instead, so e.g.
   * "ATP (plasma)" and "Ceramides (plasma)" stay distinct.
   */
  function canonicalKey(name) {
    const parenMatch = /\(([^()]+)\)\s*$/.exec(name || '');
    const parenContent = parenMatch ? parenMatch[1].trim() : null;
    const isUsableAbbrev = parenContent
      && !/\s/.test(parenContent)
      && !QUALIFIER_STOPLIST.has(parenContent.toLowerCase());
    const source = isUsableAbbrev ? parenContent : (name || '');
    const translit = source.replace(/[α-ωΑ-Ω]/g, (c) => GREEK_MAP[c.toLowerCase()] || '');
    return translit.toUpperCase().replace(/[^A-Z0-9]/g, '');
  }

  function directionBadge(direction) {
    const cls = direction === 'up' ? 'direction-up' : direction === 'down' ? 'direction-down' : 'direction-mixed';
    const arrow = direction === 'up' ? '↑' : direction === 'down' ? '↓' : '↕';
    return `<span class="direction-badge ${cls}">${arrow} ${escapeHtml(direction)}</span>`;
  }

  function groupRows(rows) {
    const groups = new Map();
    for (const r of rows) {
      const key = canonicalKey(r.name) || r.name;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(r);
    }
    // Prefer the longest/most descriptive name in a group as the display label.
    return [...groups.values()]
      .map((members) => ({
        label: members.reduce((best, r) => (r.name.length > best.length ? r.name : best), members[0].name),
        members,
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }

  function render(rows) {
    const groups = groupRows(rows);
    resultsCount.textContent = `${rows.length} marker×condition entr${rows.length === 1 ? 'y' : 'ies'} across ${groups.length} distinct marker${groups.length === 1 ? '' : 's'}`;
    tableBody.innerHTML = groups.map((g) => {
      const memberRows = g.members.map((r) => `
        <tr>
          <td>${directionBadge(r.direction)}</td>
          <td><a href="${escapeHtml(r.page)}">${escapeHtml(r.conditionName)}</a></td>
          <td>${escapeHtml(r.comparison)}</td>
          <td>${r.doi ? `<a href="https://doi.org/${escapeHtml(r.doi)}" target="_blank" rel="noopener">${escapeHtml(r.citation)}</a>` : escapeHtml(r.citation)}</td>
        </tr>
      `).join('');
      const conditionNames = [...new Set(g.members.map((r) => r.conditionName))].join(', ');
      return `
        <tr class="cross-index-group-row">
          <td colspan="5">
            <details>
              <summary><strong>${escapeHtml(g.label)}</strong> <span class="cross-index-group-meta">— ${g.members.length} condition${g.members.length === 1 ? '' : 's'}: ${escapeHtml(conditionNames)}</span></summary>
              <table class="cross-index-group-table"><thead><tr><th>Direction</th><th>Condition</th><th>vs. Comparison</th><th>Key Reference</th></tr></thead><tbody>${memberRows}</tbody></table>
            </details>
          </td>
        </tr>
      `;
    }).join('');
  }

  function applyFilters() {
    const q = (searchInput.value || '').toLowerCase().trim();
    const cond = conditionFilter.value;
    const rows = allRows.filter((r) => {
      if (cond !== 'all' && r.conditionSlug !== cond) return false;
      if (!q) return true;
      return r.name.toLowerCase().includes(q) || r.conditionName.toLowerCase().includes(q);
    });
    render(rows);
  }

  async function getDataLoader() {
    if (window.ensureBiomarkerDataLoader) return window.ensureBiomarkerDataLoader();
    if (window.BiomarkerDataLoader) return window.BiomarkerDataLoader;
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

  async function init() {
    // scripts/embed-biomarker-index.js pre-aggregates this directly into the
    // page (matching agents-local.html's EMBEDDED_AGENTS_DATA convention) so
    // the page works standalone with zero fetch/bundle dependency. Fall back
    // to the loader-based fetch/bundle path if that hasn't been run yet.
    if (window.EMBEDDED_BIOMARKER_INDEX) {
      allRows = window.EMBEDDED_BIOMARKER_INDEX;
      const seenSlugs = new Set();
      const conditionOptions = ['<option value="all">All conditions</option>'];
      for (const r of allRows) {
        if (!seenSlugs.has(r.conditionSlug)) {
          seenSlugs.add(r.conditionSlug);
          conditionOptions.push(`<option value="${escapeHtml(r.conditionSlug)}">${escapeHtml(r.conditionName)}</option>`);
        }
      }
      conditionFilter.innerHTML = conditionOptions.join('');
      render(allRows);
      return;
    }

    const loader = await getDataLoader();

    const categoriesData = await loader.fetchOrBundle(
      'data/condition-categories.json',
      '__CONDITION_CATEGORIES__',
      'js/generated/condition-categories.bundle.js'
    );

    const atlasConditions = [];
    for (const category of categoriesData.categories) {
      for (const cond of category.conditions) {
        if (cond.biomarkers) atlasConditions.push(cond);
      }
    }

    const seenSlugs = new Set();
    const conditionOptions = ['<option value="all">All conditions</option>'];

    // Sequential, not Promise.all: every atlas bundle sets the SAME global
    // (__BIOMARKER_ATLAS__, matching biomarker-atlas.js's convention), so
    // fetching multiple atlases concurrently via the file:// bundle fallback
    // would race and let one slug's data clobber another's mid-flight.
    const atlasResults = [];
    for (const cond of atlasConditions) {
      try {
        delete window.__BIOMARKER_ATLAS__;
        const atlas = await loader.fetchOrBundle(
          `data/biomarkers/${cond.slug}.json`,
          '__BIOMARKER_ATLAS__',
          `js/generated/atlas-${cond.slug}.bundle.js`
        );
        atlasResults.push({ cond, atlas });
      } catch (_) {
        atlasResults.push(null);
      }
    }

    for (const result of atlasResults) {
      if (!result) continue;
      const { cond, atlas } = result;
      if (!seenSlugs.has(cond.slug)) {
        seenSlugs.add(cond.slug);
        conditionOptions.push(`<option value="${escapeHtml(cond.slug)}">${escapeHtml(cond.name)}</option>`);
      }
      for (const marker of atlas.markers || []) {
        allRows.push({
          name: marker.name,
          direction: marker.direction,
          comparison: marker.comparison,
          citation: marker.reference && marker.reference.citation,
          doi: marker.reference && marker.reference.doi,
          conditionSlug: cond.slug,
          conditionName: cond.name,
          page: cond.biomarkers,
        });
      }
    }

    allRows.sort((a, b) => a.name.localeCompare(b.name));
    conditionFilter.innerHTML = conditionOptions.join('');
    render(allRows);
  }

  searchInput.addEventListener('input', applyFilters);
  conditionFilter.addEventListener('change', applyFilters);
  init().catch((err) => {
    resultsCount.textContent = 'Failed to load biomarker index.';
    console.error(err);
  });
})();
