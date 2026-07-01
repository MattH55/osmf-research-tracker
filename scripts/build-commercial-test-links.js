/**
 * Map biomarker atlas entries to commercially available lab test ordering links.
 */
const fs = require('fs');
const path = require('path');
const { markerId } = require('./lib/biomarker-matcher');

const ROOT = path.join(__dirname, '..');
const BIOMARKER_DIR = path.join(ROOT, 'data', 'biomarkers');
const CATALOG = path.join(ROOT, 'data', 'commercial-tests', 'catalog.json');
const OUT = path.join(BIOMARKER_DIR, 'commercial-links.json');

const ATLAS_SLUGS = ['long-covid', 'pacvs', 'me-cfs', 'lyme', 'gulf-war-illness'];

function nameKey(marker) {
  return (marker.name || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

const SEARCH_URL_RE = /\/(?:test\/search|test-menu\/search)(?:\?|$)/i;

function isSearchUrl(url) {
  return SEARCH_URL_RE.test(url || '');
}

function assertDirectVendorUrls(entry) {
  for (const vendor of entry.vendors || []) {
    if (isSearchUrl(vendor.url)) {
      throw new Error(
        `Vendor "${vendor.vendor}" for "${entry.testName}" still uses a search URL: ${vendor.url}. `
        + 'Add a specific test page to data/commercial-tests/catalog.json.'
      );
    }
  }
}

function lookupEntry(catalog, marker) {
  if (marker.loinc && catalog.byLoinc[marker.loinc]) {
    const entry = { ...catalog.byLoinc[marker.loinc], loinc: marker.loinc, matchedBy: 'loinc' };
    assertDirectVendorUrls(entry);
    return entry;
  }
  const key = nameKey(marker);
  if (catalog.byNameKey[key]) {
    const entry = { ...catalog.byNameKey[key], matchedBy: 'name' };
    assertDirectVendorUrls(entry);
    return entry;
  }
  if (marker.loinc) {
    return {
      testName: marker.name,
      availability: 'reference',
      matchedBy: 'loinc-only',
      loinc: marker.loinc,
      vendors: [
        { vendor: 'LOINC', url: `https://loinc.org/${marker.loinc}` },
      ],
      note: 'No curated commercial lab test page yet; LOINC reference only.',
    };
  }
  return null;
}

function main() {
  const catalog = JSON.parse(fs.readFileSync(CATALOG, 'utf8'));
  const markerCommercial = {};
  let commercial = 0;
  let specialty = 0;
  let reference = 0;

  for (const slug of ATLAS_SLUGS) {
    const atlas = JSON.parse(fs.readFileSync(path.join(BIOMARKER_DIR, `${slug}.json`), 'utf8'));
    for (const marker of atlas.markers) {
      const entry = lookupEntry(catalog, marker);
      if (!entry) continue;
      const id = markerId(slug, marker);
      markerCommercial[id] = entry;
      if (entry.availability === 'commercial') commercial += 1;
      else if (entry.availability === 'specialty') specialty += 1;
      else reference += 1;
    }
  }

  const payload = {
    generated: new Date().toISOString().slice(0, 10),
    disclaimer: 'Links are for reference only. Test availability, specimen requirements, and insurance coverage vary by location. Not medical advice.',
    counts: {
      commercial,
      specialty,
      reference,
      total: Object.keys(markerCommercial).length,
    },
    markerCommercial,
  };

  fs.writeFileSync(OUT, JSON.stringify(payload, null, 2), 'utf8');
  console.log(`Wrote ${OUT}`);
  console.log(`  ${payload.counts.total} markers with lab links (${commercial} commercial, ${specialty} specialty, ${reference} search/reference)`);
}

main();