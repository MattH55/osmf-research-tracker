/**
 * Tag biomarkers that are also oral consumable products (supplements, nutrients).
 */
const fs = require('fs');
const path = require('path');
const { markerId } = require('./lib/biomarker-matcher');

const ROOT = path.join(__dirname, '..');
const BIOMARKER_DIR = path.join(ROOT, 'data', 'biomarkers');
const CATALOG = path.join(ROOT, 'data', 'consumable-products', 'catalog.json');
const OUT = path.join(BIOMARKER_DIR, 'consumable-links.json');

const ATLAS_SLUGS = ['long-covid', 'pacvs', 'me-cfs', 'lyme', 'gulf-war-illness'];

function nameKey(marker) {
  return (marker.name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function matchConsumable(catalog, marker) {
  const key = nameKey(marker);
  if (catalog.byNameKey[key]) {
    return { ...catalog.byNameKey[key], matchedBy: 'nameKey', markerKey: key };
  }

  const hay = `${marker.name} ${marker.alternateName || ''}`.toLowerCase();
  for (const rule of catalog.namePatterns || []) {
    const re = new RegExp(rule.pattern, 'i');
    if (re.test(hay)) {
      return {
        productName: rule.productName,
        productType: rule.productType,
        note: rule.note,
        matchedBy: 'pattern',
        pattern: rule.pattern,
      };
    }
  }
  return null;
}

function main() {
  const catalog = JSON.parse(fs.readFileSync(CATALOG, 'utf8'));
  const markerConsumable = {};
  const byType = {};

  for (const slug of ATLAS_SLUGS) {
    const atlas = JSON.parse(fs.readFileSync(path.join(BIOMARKER_DIR, `${slug}.json`), 'utf8'));
    for (const marker of atlas.markers) {
      const entry = matchConsumable(catalog, marker);
      if (!entry) continue;
      const id = markerId(slug, marker);
      markerConsumable[id] = {
        consumable: true,
        productName: entry.productName,
        productType: entry.productType,
        note: entry.note || null,
        matchedBy: entry.matchedBy,
      };
      byType[entry.productType] = (byType[entry.productType] || 0) + 1;
    }
  }

  const payload = {
    generated: new Date().toISOString().slice(0, 10),
    disclaimer: 'Consumable tags indicate the analyte is also sold as an oral supplement or nutrient. This is not a product endorsement or medical advice.',
    counts: {
      total: Object.keys(markerConsumable).length,
      byType,
    },
    markerConsumable,
  };

  fs.writeFileSync(OUT, JSON.stringify(payload, null, 2), 'utf8');
  console.log(`Wrote ${OUT}`);
  console.log(`  ${payload.counts.total} markers tagged consumable`);
}

main();