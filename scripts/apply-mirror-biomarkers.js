/**
 * VitalScan4PACVS mirror copies: canonical → opensourcemed.info, noindex for Google.
 */
const fs = require('fs');
const path = require('path');
const { CANONICAL, MIRROR, canonicalUrl } = require('./lib/site-config');
const { escapeAttr } = require('./lib/seo-keywords');
const { vitalscanNav, NAV_EXTRA_CSS } = require('./lib/vitalscan-nav');

const ROOT = path.join(__dirname, '..');

const MIRROR_FILES = [
  'biomarker-atlas.html',
  'long-covid-biomarkers.html',
  'pacvs-biomarkers.html',
  'me-cfs-biomarkers.html',
  'lyme-biomarkers.html',
  'gulf-war-illness-biomarkers.html',
];

const MIRROR_NOTICE = `
    <div class="mirror-notice" style="background:#fff7ed;border-bottom:1px solid #fed7aa;padding:0.625rem 1.5rem;font-size:0.8125rem;color:#9a3412;text-align:center;">
        Canonical reference: <a href="{{CANONICAL}}" style="color:#c2410c;font-weight:600;">{{CANONICAL}}</a> (Open Source Medicine Foundation)
    </div>`;

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

const NAV_RE = /<nav class="nav-minimal"[\s\S]*?<\/nav>/;

function upsertMirrorNav(html) {
  const nav = vitalscanNav('biomarkers');
  if (NAV_RE.test(html)) {
    return html.replace(NAV_RE, nav);
  }
  return html.replace(/<body([^>]*)>/, `<body$1>\n    ${nav}`);
}

function upsertNavCss(html) {
  if (html.includes('.nav-donate')) return html;
  return html.replace('</style>', `${NAV_EXTRA_CSS}\n    </style>`);
}

function upsertMirrorNotice(html, osmUrl) {
  const notice = MIRROR_NOTICE.replace(/\{\{CANONICAL\}\}/g, osmUrl);
  if (html.includes('mirror-notice')) {
    return html.replace(/<div class="mirror-notice"[\s\S]*?<\/div>/, notice.trim());
  }
  return html.replace(/<body([^>]*)>/, `<body$1>${notice}`);
}

function applyMirror(filename) {
  const filePath = path.join(ROOT, filename);
  const osmUrl = canonicalUrl(filename);
  let html = fs.readFileSync(filePath, 'utf8');

  html = upsertCanonical(html, osmUrl);
  html = upsertMeta(html, 'robots', 'noindex, follow');
  html = upsertMeta(html, 'og:site_name', MIRROR.siteName, true);
  html = upsertMeta(html, 'og:url', osmUrl, true);
  html = upsertMirrorNotice(html, osmUrl);
  html = upsertNavCss(html);
  html = upsertMirrorNav(html);

  fs.writeFileSync(filePath, html, 'utf8');
  console.log(`Mirror SEO: ${filename} → canonical ${osmUrl}, noindex, nav harmonized`);
}

for (const file of MIRROR_FILES) {
  applyMirror(file);
}