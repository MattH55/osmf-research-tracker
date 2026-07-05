/**
 * Deploy canonical biomarker atlases into the OSM Research Tracker.
 */
const fs = require('fs');
const path = require('path');
const { CANONICAL, canonicalUrl } = require('./lib/site-config');
const { escapeAttr } = require('./lib/seo-keywords');
const { patchTrackerPages } = require('./patch-tracker-integration');

const ROOT = path.join(__dirname, '..');
const OSM_ROOT = path.join('C:', 'Users', 'matth', 'OneDrive', 'Documents', 'OpenSourceMed', 'Opensource Medicine (1)');
const TRACKER_ROOT = path.join(OSM_ROOT, 'research-tracker');

const HTML_FILES = [
  'biomarker-atlas.html',
  'long-covid-biomarkers.html',
  'pacvs-biomarkers.html',
  'me-cfs-biomarkers.html',
  'lyme-biomarkers.html',
  'gulf-war-illness-biomarkers.html',
];

const COPY_DIRS = [
  { src: 'data', dest: 'data' },
  { src: 'js', dest: 'js' },
  { src: 'js/generated', dest: 'js/generated' },
  { src: 'data/clinical_trials', dest: 'data/clinical_trials' },
  { src: 'data/commercial-tests', dest: 'data/commercial-tests' },
  { src: 'data/consumable-products', dest: 'data/consumable-products' },
];
const COPY_FILES = ['biomarkers.schema.json'];

const LITERATURE_LINKS = {
  'long-covid-biomarkers.html': { feed: 'long-covid.html', label: 'Long COVID Literature Feed' },
  'pacvs-biomarkers.html': { feed: 'pacvs.html', label: 'PACVS Literature Feed' },
  'me-cfs-biomarkers.html': { feed: 'me-cfs.html', label: 'ME/CFS Literature Feed' },
  'lyme-biomarkers.html': { feed: 'lyme.html', label: 'Lyme / PTLDS Literature Feed' },
  'gulf-war-illness-biomarkers.html': { feed: 'gulf-war-illness.html', label: 'Gulf War Illness Literature Feed' },
};

function trackerNav(active) {
  const link = (href, label, key) => {
    const cls = active === key ? ' class="nav-active"' : '';
    return `<li><a href="${href}"${cls}>${label}</a></li>`;
  };
  return `<nav>
  <div class="nav-container">
    <a href="https://opensourcemed.info" class="nav-brand">
      Open Source <span>Medicine</span>
      <span class="nav-brand-sub">Research Tracker</span>
    </a>
    <ul class="nav-links">
      ${link('index.html', 'All Conditions', 'hub')}
      ${link('pacvs.html', 'PACVS', 'pacvs')}
      ${link('long-covid.html', 'Long COVID', 'long-covid')}
      ${link('me-cfs.html', 'ME/CFS', 'me-cfs')}
      ${link('biomarker-atlas.html', 'Biomarkers', 'biomarkers')}
      ${link('clinical_trials.html', 'Clinical Trials', 'trials')}
      ${link('agents.html', 'Agents', 'agents')}
      <li><a href="https://www.paypal.com/ncp/payment/A2MK3BCVE4X7C" class="nav-support">Support Our Work</a></li>
    </ul>
  </div>
</nav>`;
}

const TRACKER_FOOTER = `<footer>
  <div class="footer-brand">Open Source Medicine Foundation</div>
  <div class="footer-links">
    <a href="https://opensourcemed.info">opensourcemed.info</a>
    <a href="index.html">Research Tracker</a>
    <a href="biomarker-atlas.html">Biomarker Atlases</a>
    <a href="clinical_trials.html">Clinical Trials</a>
    <a href="agents.html">Therapeutic Agents</a>
  </div>
  <div class="footer-note">Educational synthesis of peer-reviewed research. Not medical advice.</div>
</footer>`;

const TRACKER_STYLES = `  <link rel="icon" href="../favicon.png" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="tracker.css">
  <link rel="stylesheet" href="css/biomarker-atlas-tracker.css">`;

const NAV_RE = /<nav[^>]*>[\s\S]*?<\/nav>/;
const FOOTER_RE = /<footer[\s\S]*?<\/footer>/;
const INLINE_STYLE_RE = /\s*<style>[\s\S]*?<\/style>/;
const BIOMARKER_CSS_RE = /\s*<link rel="stylesheet" href="css\/biomarker-atlas[^"]*\.css">\s*/g;
const OSM_CSS_RE = /\s*<link rel="stylesheet" href="styles\.css">\s*/g;
const FONTS_LINK_RE = /\s*<link href="https:\/\/fonts\.googleapis\.com[^>]+>\s*/g;
const PRECONNECT_RE = /\s*<link rel="preconnect"[^>]+>\s*/g;

function copyRecursive(src, dest) {
  if (!fs.existsSync(src)) return;
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    if (!fs.existsSync(dest)) fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
    return;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

function upsertMeta(html, name, content, prop = false) {
  const attr = prop ? 'property' : 'name';
  const re = new RegExp(`<meta ${attr}="${name}" content="[^"]*"\\s*/?>`, 'i');
  const tag = `<meta ${attr}="${name}" content="${escapeAttr(content)}">`;
  if (re.test(html)) return html.replace(re, tag);
  return html.replace('</head>', `    ${tag}\n</head>`);
}

function rewriteCanonicalUrls(html) {
  let out = html;
  const pairs = [
    ['https://opensourcemed.info/biomarker-atlas.html', canonicalUrl('biomarker-atlas.html')],
    ['https://opensourcemed.info/long-covid-biomarkers.html', canonicalUrl('long-covid-biomarkers.html')],
    ['https://opensourcemed.info/pacvs-biomarkers.html', canonicalUrl('pacvs-biomarkers.html')],
    ['https://opensourcemed.info/me-cfs-biomarkers.html', canonicalUrl('me-cfs-biomarkers.html')],
    ['https://opensourcemed.info/lyme-biomarkers.html', canonicalUrl('lyme-biomarkers.html')],
    ['https://opensourcemed.info/gulf-war-illness-biomarkers.html', canonicalUrl('gulf-war-illness-biomarkers.html')],
    ['https://opensourcemed.info/data/biomarkers/', `${CANONICAL.origin}${CANONICAL.basePath}/data/biomarkers/`],
  ];
  for (const [from, to] of pairs) {
    out = out.split(from).join(to);
  }
  return out;
}

function injectTrackerStyles(html) {
  let out = html.replace(INLINE_STYLE_RE, '');
  out = out.replace(BIOMARKER_CSS_RE, '');
  out = out.replace(OSM_CSS_RE, '');
  out = out.replace(FONTS_LINK_RE, '');
  out = out.replace(PRECONNECT_RE, '');

  if (out.includes('biomarker-atlas-tracker.css')) return out;

  const anchor = out.includes('<!-- BIOMARKER_JSONLD_END -->')
    ? '<!-- BIOMARKER_JSONLD_END -->'
    : out.includes('<!-- BIOMARKER_HUB_JSONLD_END -->')
      ? '<!-- BIOMARKER_HUB_JSONLD_END -->'
      : '</head>';

  return out.replace(anchor, `${anchor}\n${TRACKER_STYLES}\n`);
}

function toPageHero(html) {
  return html
    .replace(
      /<header class="hero">\s*<div class="hero-container">([\s\S]*?)<\/div>\s*<\/header>/g,
      '<section class="page-hero">$1</section>'
    )
    .replace(/<header class="hero">([\s\S]*?)<\/header>/g, '<section class="page-hero">$1</section>');
}

function adaptHubHero(html) {
  return html
    .replace(
      /<section class="page-hero">\s*<h1>Biomarker Atlas Hub<\/h1>/,
      `<section class="page-hero">
  <div class="hero-eyebrow">Peer-Reviewed Literature Databases</div>
  <h1>Biomarker <span>Atlas Hub</span></h1>`
    )
    .replace(/<section>\s*<div class="container">/g, '<section class="atlas-hub-section"><div class="container">');
}

function adaptConditionHero(html) {
  return html.replace(/class="hero-badge"/g, 'class="hero-eyebrow"');
}

function addCrosslinks(html, filename) {
  const link = LITERATURE_LINKS[filename];
  if (!link || html.includes('tracker-crosslink')) return html;

  const block = `  <div class="section-inner">
    <div class="tracker-crosslink">
      <a href="${link.feed}">← ${link.label}</a>
      <a href="biomarker-atlas.html">All Biomarker Atlases</a>
      <a href="index.html">Research Tracker Home</a>
    </div>
  </div>\n`;

  return html.replace(/<main class="main-section">/, `<main class="main-section">\n${block}`);
}

function moveHeroBeforeMain(html) {
  const heroMatch = html.match(/<section class="page-hero">[\s\S]*?<\/section>/);
  if (!heroMatch) return html;
  let out = html.replace(heroMatch[0], '');
  return out.replace(/<\/nav>\s*/, `</nav>\n\n${heroMatch[0]}\n`);
}

function adaptForTracker(html, filename) {
  let out = html;

  out = out.replace(/<div class="mirror-notice"[\s\S]*?<\/div>\s*/g, '');
  out = rewriteCanonicalUrls(out);
  out = injectTrackerStyles(out);
  out = toPageHero(out);
  out = out.replace(NAV_RE, trackerNav(filename === 'biomarker-atlas.html' ? 'biomarkers' : 'biomarkers'));
  out = out.replace(FOOTER_RE, TRACKER_FOOTER);

  out = out.replace(/<body([^>]*)>/, (match, attrs) => {
    const cleaned = attrs.replace(/\s*class="[^"]*"/, '');
    return `<body class="biomarker-page"${cleaned}>`;
  });

  out = out.replace(/<main>/g, '<main class="main-section">');
  out = moveHeroBeforeMain(out);

  if (filename === 'biomarker-atlas.html') {
    out = adaptHubHero(out);
  } else {
    out = adaptConditionHero(out);
    out = addCrosslinks(out, filename);
  }

  const canonical = canonicalUrl(filename);
  out = out.replace(
    /<link rel="canonical" href="[^"]*"\s*\/?>/i,
    `<link rel="canonical" href="${escapeAttr(canonical)}">`
  );
  out = upsertMeta(out, 'robots', 'index, follow, max-image-preview:large');
  out = upsertMeta(out, 'og:site_name', CANONICAL.siteName, true);
  out = upsertMeta(out, 'og:url', canonical, true);

  out = out.replace(/href="biomarker-atlas\.html"/g, 'href="biomarker-atlas.html"');
  out = out.replace(/src="js\/biomarker-atlas\.js"/g, 'src="js/biomarker-atlas.js"');

  return out;
}

function writeRootRedirect(filename) {
  const target = `research-tracker/${filename}`;
  const canonical = canonicalUrl(filename);
  const html = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <link rel="canonical" href="${canonical}">
  <meta http-equiv="refresh" content="0; url=${target}">
  <title>Redirecting…</title>
  <script>location.replace('${target}');</script>
</head>
<body>
  <p>Moved to <a href="${target}">Research Tracker — ${filename}</a>.</p>
</body>
</html>`;
  fs.writeFileSync(path.join(OSM_ROOT, filename), html, 'utf8');
}

if (!fs.existsSync(TRACKER_ROOT)) {
  console.error(`Research tracker folder not found: ${TRACKER_ROOT}`);
  process.exit(1);
}

const cssDir = path.join(TRACKER_ROOT, 'css');
if (!fs.existsSync(cssDir)) fs.mkdirSync(cssDir, { recursive: true });
fs.copyFileSync(
  path.join(ROOT, 'css', 'biomarker-atlas-tracker.css'),
  path.join(cssDir, 'biomarker-atlas-tracker.css')
);

for (const { src, dest } of COPY_DIRS) {
  copyRecursive(path.join(ROOT, src), path.join(TRACKER_ROOT, dest));
}

for (const file of COPY_FILES) {
  const src = path.join(ROOT, file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(TRACKER_ROOT, file));
  }
}

for (const file of HTML_FILES) {
  const src = path.join(ROOT, file);
  const dest = path.join(TRACKER_ROOT, file);
  const html = adaptForTracker(fs.readFileSync(src, 'utf8'), file);
  fs.writeFileSync(dest, html, 'utf8');
  writeRootRedirect(file);
  console.log(`Synced ${file} → research-tracker/ (canonical)`);
}

patchTrackerPages(TRACKER_ROOT);
console.log(`Patched research tracker nav, hub, and cross-links`);
console.log(`Deployed biomarker atlases to ${TRACKER_ROOT}`);