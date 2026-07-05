/**
 * Build biomarker-atlas.html hub with canonical OSM URLs and CollectionPage JSON-LD.
 */
const fs = require('fs');
const path = require('path');
const { CANONICAL, canonicalUrl } = require('./lib/site-config');
const { PAGES, keywordsToMeta, escapeAttr } = require('./lib/seo-keywords');

const ROOT = path.join(__dirname, '..');
const HUB_FILE = 'biomarker-atlas.html';
const hubUrl = canonicalUrl(HUB_FILE);
const dateModified = '2026-06-29';

const ATLASES = [
  { name: 'Long COVID Biomarker Atlas', file: 'long-covid-biomarkers.html' },
  { name: 'PACVS Biomarker Atlas', file: 'pacvs-biomarkers.html' },
  { name: 'ME/CFS Biomarker Atlas', file: 'me-cfs-biomarkers.html' },
  { name: 'Lyme Disease Biomarker Atlas', file: 'lyme-biomarkers.html' },
  { name: 'Gulf War Illness Biomarker Atlas', file: 'gulf-war-illness-biomarkers.html' },
];

const JSONLD_MARKER_START = '<!-- BIOMARKER_HUB_JSONLD_START -->';
const JSONLD_MARKER_END = '<!-- BIOMARKER_HUB_JSONLD_END -->';

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

function buildJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'CollectionPage',
        '@id': `${hubUrl}#webpage`,
        url: hubUrl,
        name: 'Biomarker Atlas Hub',
        description: PAGES['biomarker-atlas'].description,
        dateModified,
        inLanguage: 'en',
        publisher: {
          '@type': 'Organization',
          name: CANONICAL.publisherName,
          url: CANONICAL.publisherUrl,
        },
        hasPart: ATLASES.map((a) => ({
          '@type': 'MedicalWebPage',
          name: a.name,
          url: canonicalUrl(a.file),
        })),
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          { '@type': 'ListItem', position: 1, name: 'Home', item: CANONICAL.publisherUrl },
          { '@type': 'ListItem', position: 2, name: 'Biomarker Atlases', item: hubUrl },
        ],
      },
    ],
  };
}

function injectJsonLd(html, jsonLd) {
  const block = `${JSONLD_MARKER_START}\n    <script type="application/ld+json">\n${JSON.stringify(jsonLd, null, 2).split('\n').map((l) => '    ' + l).join('\n')}\n    </script>\n    ${JSONLD_MARKER_END}`;
  const re = new RegExp(`${JSONLD_MARKER_START}[\\s\\S]*?${JSONLD_MARKER_END}`, 'm');
  if (re.test(html)) return html.replace(re, block);

  const ldRe = /<script type="application\/ld\+json">[\s\S]*?<\/script>/;
  if (ldRe.test(html)) return html.replace(ldRe, block.trim());

  return html.replace('</head>', `    ${block}\n</head>`);
}

const seo = PAGES['biomarker-atlas'];
const filePath = path.join(ROOT, HUB_FILE);
let html = fs.readFileSync(filePath, 'utf8');

html = html.replace(/<title>[^<]*<\/title>/, `<title>${escapeAttr(seo.title)}</title>`);
html = upsertMeta(html, 'description', seo.description);
html = upsertMeta(html, 'keywords', keywordsToMeta(seo.keywords));
html = upsertMeta(html, 'robots', 'index, follow, max-image-preview:large');
html = upsertCanonical(html, hubUrl);
html = upsertMeta(html, 'og:type', 'website', true);
html = upsertMeta(html, 'og:site_name', CANONICAL.siteName, true);
html = upsertMeta(html, 'og:title', seo.ogTitle || seo.title, true);
html = upsertMeta(html, 'og:description', seo.ogDescription || seo.description, true);
html = upsertMeta(html, 'og:url', hubUrl, true);
html = upsertMeta(html, 'twitter:title', seo.ogTitle || seo.title);
html = upsertMeta(html, 'twitter:description', seo.ogDescription || seo.description);
html = injectJsonLd(html, buildJsonLd());

const DATABASE_SECTION = `
        <section class="database-section" id="biomarkerDatabase">
            <div class="container">
                <div class="section-header">
                    <h2>Search the <span class="highlight">Biomarker Database</span></h2>
                    <p>Search all conditions at once — filter by condition, biomarker name, LOINC, or clinical trial outcome (NCT ID).</p>
                </div>
                <div class="database-panel">
                    <div class="database-controls">
                        <div class="search-box">
                            <input type="search" id="databaseSearch" placeholder="e.g. IL-6, D-dimer, spike protein, NCT06967428…" autocomplete="off">
                        </div>
                        <select id="databaseCondition" aria-label="Filter by condition">
                            <option value="all">All conditions</option>
                            <option value="long-covid">Long COVID</option>
                            <option value="pacvs">PACVS</option>
                            <option value="me-cfs">ME/CFS</option>
                            <option value="lyme">Lyme</option>
                            <option value="gulf-war-illness">Gulf War Illness</option>
                        </select>
                        <label class="filter-trials"><input type="checkbox" id="databaseTrialsOnly"> Has clinical trial outcome</label>
                    </div>
                    <div class="database-count" id="databaseCount"></div>
                    <div class="database-results" id="databaseResults"></div>
                    <p class="database-disclaimer" style="font-size:0.75rem;color:#6b7280;margin-top:1rem;line-height:1.5;">Lab links (Quest, LabCorp, Ulta Lab Tests, specialty vendors) are for reference only. Availability, specimen type, and insurance coverage vary by location — confirm with your clinician and laboratory.</p>
                </div>
            </div>
        </section>`;

if (!html.includes('id="biomarkerDatabase"')) {
  html = html.replace(
    /<section>\s*\n\s*<div class="container">\s*\n\s*<div class="section-header">\s*\n\s*<h2>Condition/,
    `${DATABASE_SECTION}
        <section>
            <div class="container">
                <div class="section-header">
                    <h2>Condition`
  );
}

html = html.replace(/\s*<script src="js\/biomarker-data-loader\.js" defer><\/script>\s*/g, '\n');
html = html.replace(/\s*<script src="js\/biomarker-hub-search\.js" defer><\/script>\s*/g, '\n');
html = html.replace(
  '</body>',
  '    <script src="js/biomarker-data-loader.js" defer></script>\n    <script src="js/biomarker-hub-search.js" defer></script>\n</body>'
);
if (!html.includes('css/biomarker-atlas.css')) {
  html = html.replace('</head>', '    <link rel="stylesheet" href="css/biomarker-atlas.css">\n</head>');
}

fs.writeFileSync(filePath, html, 'utf8');
console.log(`Built ${HUB_FILE} with canonical ${hubUrl}`);