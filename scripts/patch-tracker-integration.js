/**
 * Add biomarker atlas links to existing Research Tracker pages.
 */
const fs = require('fs');
const path = require('path');

const NAV_INSERT = `      <li><a href="biomarker-atlas.html">Biomarkers</a></li>
      <li><a href="clinical_trials.html">Clinical Trials</a></li>`;

const NAV_OLD = `      <li><a href="clinical_trials.html">Clinical Trials</a></li>`;

const FOOTER_OLD = `    <a href="clinical_trials.html">Clinical Trials</a>
    <a href="agents.html">Therapeutic Agents</a>`;

const FOOTER_NEW = `    <a href="biomarker-atlas.html">Biomarker Atlases</a>
    <a href="clinical_trials.html">Clinical Trials</a>
    <a href="agents.html">Therapeutic Agents</a>`;

const CONDITION_BIOMARKER_LINKS = {
  'long-covid.html': { href: 'long-covid-biomarkers.html', label: 'Long COVID Biomarker Atlas' },
  'pacvs.html': { href: 'pacvs-biomarkers.html', label: 'PACVS Biomarker Atlas' },
  'me-cfs.html': { href: 'me-cfs-biomarkers.html', label: 'ME/CFS Biomarker Atlas' },
  'lyme.html': { href: 'lyme-biomarkers.html', label: 'Lyme Biomarker Atlas' },
  'gulf-war-illness.html': { href: 'gulf-war-illness-biomarkers.html', label: 'Gulf War Illness Biomarker Atlas' },
};

const TRACKER_PAGES = [
  'index.html',
  'long-covid.html',
  'pacvs.html',
  'me-cfs.html',
  'lyme.html',
  'gulf-war-illness.html',
  'other-post-viral.html',
  'clinical_trials.html',
  'agents.html',
];

function patchNavAndFooter(html) {
  let out = html;
  if (!out.includes('href="biomarker-atlas.html">Biomarkers')) {
    out = out.replace(NAV_OLD, NAV_INSERT);
  }
  if (!out.includes('href="biomarker-atlas.html">Biomarker Atlases')) {
    out = out.replace(FOOTER_OLD, FOOTER_NEW);
  }
  return out;
}

function patchIndex(html) {
  return patchNavAndFooter(html);
}

function patchConditionPage(html, filename) {
  let out = patchNavAndFooter(html);
  const link = CONDITION_BIOMARKER_LINKS[filename];
  if (!link || out.includes('biomarker-callout')) return out;

  const callout = `
    <div class="biomarker-callout">
      <strong>Biomarker Atlas:</strong> Searchable blood test, cytokine, and metabolite alterations from peer-reviewed literature —
      <a href="${link.href}">${link.label} →</a>
    </div>
`;

  return out.replace('<div class="disclaimer">', `${callout}\n    <div class="disclaimer">`);
}

function patchTrackerPages(trackerRoot) {
  for (const file of TRACKER_PAGES) {
    const filePath = path.join(trackerRoot, file);
    if (!fs.existsSync(filePath)) continue;

    let html = fs.readFileSync(filePath, 'utf8');
    if (file === 'index.html') {
      html = patchIndex(html);
    } else if (CONDITION_BIOMARKER_LINKS[file]) {
      html = patchConditionPage(html, file);
    } else {
      html = patchNavAndFooter(html);
    }
    fs.writeFileSync(filePath, html, 'utf8');
    console.log(`  Patched ${file}`);
  }

  patchTrackerCss(path.join(trackerRoot, 'tracker.css'));
  patchTrackerSitemap(path.join(trackerRoot, 'sitemap.xml'));
}

function patchTrackerCss(cssPath) {
  if (!fs.existsSync(cssPath)) return;
  let css = fs.readFileSync(cssPath, 'utf8');

  if (!css.includes('.nav-active')) {
    css = css.replace(
      '.nav-links a:hover { color: var(--accent-orange); }',
      `.nav-links a:hover { color: var(--accent-orange); }
.nav-links a.nav-active { color: var(--accent-orange); font-weight: 600; }`
    );
  }

  if (!css.includes('.biomarker-callout')) {
    css += `

/* ── BIOMARKER CROSS-LINKS ── */
.biomarker-callout {
  background: linear-gradient(135deg, #fff8f0 0%, #f8f9fa 100%);
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent-orange);
  border-radius: 8px;
  padding: 1rem 1.25rem;
  margin-bottom: 1.25rem;
  font-size: 0.9rem;
  color: var(--text-gray);
  line-height: 1.6;
}
.biomarker-callout a {
  color: var(--primary-dark);
  font-weight: 600;
  text-decoration: none;
}
.biomarker-callout a:hover { color: var(--accent-orange); }

@media (min-width: 1100px) {
  .tracker-hub-grid { grid-template-columns: repeat(2, 1fr); }
}
`;
  }

  fs.writeFileSync(cssPath, css, 'utf8');
}

function patchTrackerSitemap(sitemapPath) {
  if (!fs.existsSync(sitemapPath)) return;
  let xml = fs.readFileSync(sitemapPath, 'utf8');
  if (xml.includes('biomarker-atlas.html')) return;

  const entries = `
  <url>
    <loc>https://research.opensourcemed.info/biomarker-atlas.html</loc>
    <lastmod>2026-06-29</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.95</priority>
  </url>
  <url>
    <loc>https://research.opensourcemed.info/long-covid-biomarkers.html</loc>
    <lastmod>2026-06-29</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.92</priority>
  </url>
  <url>
    <loc>https://research.opensourcemed.info/pacvs-biomarkers.html</loc>
    <lastmod>2026-06-29</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.92</priority>
  </url>
  <url>
    <loc>https://research.opensourcemed.info/me-cfs-biomarkers.html</loc>
    <lastmod>2026-06-29</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.92</priority>
  </url>
  <url>
    <loc>https://research.opensourcemed.info/lyme-biomarkers.html</loc>
    <lastmod>2026-06-29</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.92</priority>
  </url>
  <url>
    <loc>https://research.opensourcemed.info/gulf-war-illness-biomarkers.html</loc>
    <lastmod>2026-06-29</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.92</priority>
  </url>
  <url>
    <loc>https://research.opensourcemed.info/biomarkers.schema.json</loc>
    <lastmod>2026-06-29</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>`;

  xml = xml.replace('</urlset>', `${entries}\n</urlset>`);
  fs.writeFileSync(sitemapPath, xml, 'utf8');
}

module.exports = { patchTrackerPages };