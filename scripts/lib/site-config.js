/**
 * Canonical biomarker atlases live under the OSM Research Tracker.
 * VitalScan4PACVS hosts mirror copies with rel=canonical pointing here.
 */
const CANONICAL = {
  origin: 'https://research.opensourcemed.info',
  basePath: '',
  publisherName: 'Open Source Medicine Foundation',
  publisherUrl: 'https://opensourcemed.info/',
  siteName: 'Open Source Medicine Foundation',
  hubFile: 'biomarker-atlas.html',
};

const MIRROR = {
  origin: 'https://vitalscan4pacvs.com',
  publisherName: 'VitalScan4PACVS',
  publisherUrl: 'https://vitalscan4pacvs.com/',
  siteName: 'VitalScan4PACVS',
};

function canonicalUrl(filename) {
  const base = `${CANONICAL.origin}${CANONICAL.basePath}`;
  return filename ? `${base}/${filename}` : `${base}/`;
}

function mirrorUrl(filename) {
  return `${MIRROR.origin}/${filename}`;
}

const GOOGLE_ANALYTICS_ID = 'G-XRCGK1QTB5';
const GOOGLE_ANALYTICS_SNIPPET = `  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=${GOOGLE_ANALYTICS_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());

    gtag('config', '${GOOGLE_ANALYTICS_ID}');
  </script>`;

module.exports = { CANONICAL, MIRROR, canonicalUrl, mirrorUrl, GOOGLE_ANALYTICS_SNIPPET };