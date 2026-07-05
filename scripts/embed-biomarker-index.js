/**
 * Embed the aggregated cross-condition biomarker index directly into
 * biomarker-index.html, matching this repo's established "-local.html"
 * convention (see agents-local.html's EMBEDDED_AGENTS_DATA) for pages that
 * must work standalone with zero fetch/bundle dependency — just open the
 * file and the data is already there.
 *
 * Idempotent: re-running replaces the previous embedded block via markers,
 * same pattern as build-atlases.js's JSON-LD injection.
 */
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'data', 'biomarkers');
const HTML_PATH = path.join(ROOT, 'biomarker-index.html');

const START = '<!-- EMBEDDED_BIOMARKER_INDEX_START -->';
const END = '<!-- EMBEDDED_BIOMARKER_INDEX_END -->';

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function buildRows() {
  const categoriesData = readJson(path.join(ROOT, 'data', 'condition-categories.json'));
  const atlasConditions = [];
  for (const category of categoriesData.categories) {
    for (const cond of category.conditions) {
      if (cond.biomarkers) atlasConditions.push(cond);
    }
  }

  const rows = [];
  for (const cond of atlasConditions) {
    const atlasPath = path.join(DATA_DIR, `${cond.slug}.json`);
    if (!fs.existsSync(atlasPath)) continue;
    const atlas = readJson(atlasPath);
    for (const marker of atlas.markers || []) {
      rows.push({
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
  rows.sort((a, b) => a.name.localeCompare(b.name));
  return rows;
}

function main() {
  const rows = buildRows();
  const block = `${START}\n<script>window.EMBEDDED_BIOMARKER_INDEX = ${JSON.stringify(rows)};</script>\n${END}`;

  let html = fs.readFileSync(HTML_PATH, 'utf8');
  const re = new RegExp(`${START}[\\s\\S]*?${END}`, 'm');
  if (re.test(html)) {
    html = html.replace(re, block);
  } else {
    html = html.replace(
      '<script src="js/biomarker-cross-index.js" defer></script>',
      `${block}\n<script src="js/biomarker-cross-index.js" defer></script>`
    );
  }
  fs.writeFileSync(HTML_PATH, html, 'utf8');
  console.log(`Embedded ${rows.length} biomarker×condition rows into ${path.relative(ROOT, HTML_PATH)}`);
}

main();
