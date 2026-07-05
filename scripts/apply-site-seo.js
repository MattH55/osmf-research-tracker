/**
 * Apply SEO meta tags to main site pages (non-atlas HTML)
 */
const fs = require('fs');
const path = require('path');
const { canonicalUrl } = require('./lib/site-config');
const { PAGES, keywordsToMeta, escapeAttr } = require('./lib/seo-keywords');

const ROOT = path.join(__dirname, '..');

const FILES = {
  index: 'recruitment-page-v5.html',
  'index-redirect': 'index.html',
  'the-science': 'the-science.html',
  'the-protocol': 'the-protocol.html',
  'biomarker-atlas': 'biomarker-atlas.html',
};

function upsertMeta(html, name, content, prop = false) {
  const attr = prop ? 'property' : 'name';
  const re = new RegExp(`<meta ${attr}="${name}" content="[^"]*"\\s*/?>`, 'i');
  const tag = `<meta ${attr}="${name}" content="${escapeAttr(content)}">`;
  if (re.test(html)) return html.replace(re, tag);
  return html.replace('</head>', `    ${tag}\n</head>`);
}

function upsertTitle(html, title) {
  return html.replace(/<title>[^<]*<\/title>/, `<title>${escapeAttr(title)}</title>`);
}

function ensureRobots(html) {
  if (html.includes('name="robots"')) return html;
  return html.replace('</head>', '    <meta name="robots" content="index, follow, max-image-preview:large">\n</head>');
}

function patchIndexRedirect(html, seo, canonical) {
  let out = html;
  out = upsertTitle(out, seo.title);
  out = upsertMeta(out, 'description', seo.description);
  out = upsertMeta(out, 'keywords', keywordsToMeta(seo.keywords));
  if (!out.includes('rel="canonical"')) {
    out = out.replace('</head>', `    <link rel="canonical" href="${escapeAttr(canonical)}">\n</head>`);
  } else {
    out = out.replace(/<link rel="canonical" href="[^"]*"\s*\/?>/i, `<link rel="canonical" href="${escapeAttr(canonical)}">`);
  }
  out = ensureRobots(out);
  out = ensureOgTwitter(out, seo, canonical);
  return out;
}

function ensureOgTwitter(html, seo, canonical) {
  let out = html;
  out = upsertMeta(out, 'og:type', 'website', true);
  out = upsertMeta(out, 'og:site_name', 'VitalScan4PACVS', true);
  out = upsertMeta(out, 'og:title', seo.ogTitle || seo.title, true);
  out = upsertMeta(out, 'og:description', seo.ogDescription || seo.description, true);
  out = upsertMeta(out, 'og:url', canonical, true);
  out = upsertMeta(out, 'og:locale', 'en_US', true);
  out = upsertMeta(out, 'twitter:card', 'summary_large_image');
  out = upsertMeta(out, 'twitter:title', seo.ogTitle || seo.title);
  out = upsertMeta(out, 'twitter:description', seo.ogDescription || seo.description);
  return out;
}

function patchFile(key, filename) {
  const seoKey = key === 'index-redirect' ? 'index' : key;
  const seo = PAGES[seoKey];
  const filePath = path.join(ROOT, filename);
  let html = fs.readFileSync(filePath, 'utf8');

  const canonicalMatch = html.match(/<link rel="canonical" href="([^"]+)"/);
  const canonical = key === 'biomarker-atlas'
    ? canonicalUrl('biomarker-atlas.html')
    : key === 'index-redirect'
      ? 'https://vitalscan4pacvs.com/recruitment-page-v5.html'
      : canonicalMatch
        ? canonicalMatch[1]
        : `https://vitalscan4pacvs.com/${filename === 'index.html' ? '' : filename}`;

  if (key === 'index-redirect') {
    html = patchIndexRedirect(html, seo, canonical);
  } else {
    html = upsertTitle(html, seo.title);
    html = upsertMeta(html, 'description', seo.description);
    html = upsertMeta(html, 'keywords', keywordsToMeta(seo.keywords));
    html = ensureRobots(html);
    html = ensureOgTwitter(html, seo, canonical);
  }

  fs.writeFileSync(filePath, html, 'utf8');
  console.log(`SEO updated: ${filename} (${seo.keywords.length} keywords)`);
}

for (const [key, file] of Object.entries(FILES)) {
  patchFile(key, file);
}