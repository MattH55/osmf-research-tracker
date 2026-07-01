/**
 * Build atlas pages: inject generated JSON-LD + wire shared JS/CSS
 */
const fs = require('fs');
const path = require('path');
const { generateAtlasJsonLd } = require('./lib/jsonld-generator');
const { CANONICAL } = require('./lib/site-config');
const { PAGES, keywordsToMeta, escapeAttr } = require('./lib/seo-keywords');

const ROOT = path.join(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'data', 'biomarkers');
const TRACKER_MODE =
  process.env.TRACKER_MODE === '1' ||
  process.env.TRACKER_MODE === 'true' ||
  fs.existsSync(path.join(ROOT, 'tracker.css'));

const HTML_MAP = {
  'long-covid': 'long-covid-biomarkers.html',
  'pacvs': 'pacvs-biomarkers.html',
  'me-cfs': 'me-cfs-biomarkers.html',
  'lyme': 'lyme-biomarkers.html',
  'gulf-war-illness': 'gulf-war-illness-biomarkers.html',
};

const JSONLD_MARKER_START = '<!-- BIOMARKER_JSONLD_START -->';
const JSONLD_MARKER_END = '<!-- BIOMARKER_JSONLD_END -->';

function injectJsonLd(html, jsonLd) {
  const block = `${JSONLD_MARKER_START}\n    <script type="application/ld+json">\n${JSON.stringify(jsonLd, null, 2).split('\n').map((l) => '    ' + l).join('\n')}\n    </script>\n    ${JSONLD_MARKER_END}`;
  const re = new RegExp(`${JSONLD_MARKER_START}[\\s\\S]*?${JSONLD_MARKER_END}`, 'm');
  if (re.test(html)) return html.replace(re, block);

  // Replace first application/ld+json block or insert before </head>
  const ldRe = /<script type="application\/ld\+json">[\s\S]*?<\/script>/;
  if (ldRe.test(html)) return html.replace(ldRe, block.trim());

  return html.replace('</head>', `    ${block}\n</head>`);
}

function ensureDatabaseSection(html) {
  if (html.includes('id="biomarker-database"')) return html;
  return html.replace(
    /<section class="overview-section">/,
    '<section class="overview-section" id="biomarker-database">'
  );
}

function ensureTrialsFilter(html) {
  let out = html;

  // Fix legacy malformed controls-bar markup from earlier injections.
  out = out.replace(
    /(<div class="filter-group" id="categoryFilters">[\s\S]*?<\/div>)\s*<\/div>\s*(?=<label class="filter-trials")/g,
    '$1\n                '
  );

  if (!out.includes('trialsOnlyFilter') && out.includes('id="categoryFilters"')) {
    const inject = `
                <label class="filter-trials"><input type="checkbox" id="trialsOnlyFilter"> Linked clinical trials</label>`;
    out = out.replace(
      /(<div class="filter-group" id="categoryFilters">[\s\S]*?<\/div>)/,
      `$1${inject}`
    );
  }
  if (!out.includes('commercialOnlyFilter') && out.includes('trialsOnlyFilter')) {
    const injectCommercial = `
                <label class="filter-trials"><input type="checkbox" id="commercialOnlyFilter"> Commercially orderable (lab)</label>`;
    out = out.replace(
      /(<label class="filter-trials"><input type="checkbox" id="trialsOnlyFilter">[\s\S]*?<\/label>)/,
      `$1${injectCommercial}`
    );
  }
  if (!out.includes('consumableOnlyFilter') && out.includes('commercialOnlyFilter')) {
    const injectConsumable = `
                <label class="filter-trials"><input type="checkbox" id="consumableOnlyFilter"> Also consumable product</label>`;
    out = out.replace(
      /(<label class="filter-trials"><input type="checkbox" id="commercialOnlyFilter">[\s\S]*?<\/label>)/,
      `$1${injectConsumable}`
    );
  }
  return out;
}

function ensureScriptOrder(html) {
  let out = html;
  const loader = '<script src="js/biomarker-data-loader.js" defer></script>';
  const atlas = '<script src="js/biomarker-atlas.js" defer></script>';

  out = out.replace(/\s*<script src="js\/biomarker-data-loader\.js" defer><\/script>\s*/g, '\n');
  out = out.replace(/\s*<script src="js\/biomarker-atlas\.js" defer><\/script>\s*/g, '\n');

  out = out.replace(
    '</body>',
    `    ${loader}\n    ${atlas}\n</body>`
  );
  return out;
}

function ensureSharedAssets(html, slug) {
  let out = html;

  if (!out.includes('css/biomarker-atlas.css')) {
    out = out.replace(
      /<link href="https:\/\/fonts\.googleapis\.com[^>]+>/,
      (m) => `${m}\n    <link rel="stylesheet" href="css/biomarker-atlas.css">`
    );
  }

  if (!out.includes('data-atlas=')) {
    out = out.replace('<body>', `<body data-atlas="${slug}">`);
  } else {
    out = out.replace(/<body[^>]*>/, `<body data-atlas="${slug}">`);
  }

  // Remove inline biomarker script block
  out = out.replace(/\s*<script>\s*const biomarkers = [\s\S]*?<\/script>/, '\n');

  out = ensureScriptOrder(out);

  return out;
}

function upsertMeta(html, name, content, prop = false) {
  const attr = prop ? 'property' : 'name';
  const re = new RegExp(`<meta ${attr}="${name}" content="[^"]*"\\s*/?>`, 'i');
  const tag = `<meta ${attr}="${name}" content="${escapeAttr(content)}">`;
  if (re.test(html)) return html.replace(re, tag);
  return html.replace('</head>', `    ${tag}\n</head>`);
}

function upsertCanonical(html, url) {
  const tag = `<link rel="canonical" href="${escapeAttr(url)}">`;
  if (/<link rel="canonical"/i.test(html)) {
    return html.replace(/<link rel="canonical" href="[^"]*"\s*\/?>/i, tag);
  }
  return html.replace('</head>', `    ${tag}\n</head>`);
}

function applySeoMeta(html, atlas, slug) {
  const seoExtra = PAGES[slug]?.keywords || [];
  const mergedKeywords = keywordsToMeta([...(atlas.page.keywords || []), ...seoExtra]);
  const p = atlas.page;

  let out = html;
  out = out.replace(/<title>[^<]*<\/title>/, `<title>${escapeAttr(p.title)}</title>`);
  out = upsertCanonical(out, p.canonical);
  out = upsertMeta(out, 'description', p.description);
  out = upsertMeta(out, 'keywords', mergedKeywords);
  out = upsertMeta(out, 'robots', 'index, follow, max-image-preview:large');
  out = upsertMeta(out, 'og:site_name', CANONICAL.siteName, true);
  out = upsertMeta(out, 'og:title', p.title, true);
  out = upsertMeta(out, 'og:description', p.description, true);
  out = upsertMeta(out, 'og:url', p.canonical, true);
  out = upsertMeta(out, 'twitter:title', p.title);
  out = upsertMeta(out, 'twitter:description', p.description);
  return out;
}

function buildOne(slug) {
  const jsonPath = path.join(DATA_DIR, `${slug}.json`);
  const htmlFile = HTML_MAP[slug];
  const htmlPath = path.join(ROOT, htmlFile);

  const atlas = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
  const htmlFileName = HTML_MAP[slug];
  atlas.page.canonical = `https://opensourcemed.info/research-tracker/${htmlFileName}`;
  if (PAGES[slug]?.keywords) {
    atlas.page.keywords = [...new Set([...(atlas.page.keywords || []), ...PAGES[slug].keywords])];
    fs.writeFileSync(jsonPath, JSON.stringify(atlas, null, 2), 'utf8');
  }

  const jsonLd = generateAtlasJsonLd(atlas);

  let html = fs.readFileSync(htmlPath, 'utf8');
  html = applySeoMeta(html, atlas, slug);
  html = injectJsonLd(html, jsonLd);
  if (!TRACKER_MODE) {
    html = ensureSharedAssets(html, slug);
    html = ensureDatabaseSection(html);
    html = ensureTrialsFilter(html);
  } else {
    html = ensureScriptOrder(html);
  }
  fs.writeFileSync(htmlPath, html, 'utf8');

  const subTestCount = atlas.markers.length;
  const loincCount = atlas.markers.filter((m) => m.loinc).length;
  console.log(`Built ${htmlFile}: JSON-LD panel with ${subTestCount} subTests (${loincCount} LOINC-coded)`);
}

for (const slug of Object.keys(HTML_MAP)) {
  buildOne(slug);
}

// Write machine-readable JSON-LD sidecar files for debugging / reuse
const jsonldDir = path.join(ROOT, 'data', 'jsonld');
if (!fs.existsSync(jsonldDir)) fs.mkdirSync(jsonldDir, { recursive: true });
for (const slug of Object.keys(HTML_MAP)) {
  const atlas = JSON.parse(fs.readFileSync(path.join(DATA_DIR, `${slug}.json`), 'utf8'));
  fs.writeFileSync(
    path.join(jsonldDir, `${slug}.jsonld`),
    JSON.stringify(generateAtlasJsonLd(atlas), null, 2),
    'utf8'
  );
}
console.log('Wrote data/jsonld/*.jsonld sidecars');