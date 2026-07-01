/**
 * Shared VitalScan4PACVS site navigation (harmonized across subpages).
 */
const HOME = 'recruitment-page-v5.html';

function navLink(href, label, active, page) {
  const cls = page === active ? 'nav-link active' : 'nav-link';
  return `<a href="${href}" class="${cls}">${label}</a>`;
}

/**
 * @param {'home'|'science'|'protocol'|'biomarkers'|null} active
 * @param {{ enrollHref?: string, donateHref?: string, howHref?: string }} opts
 */
function vitalscanNav(active = null, opts = {}) {
  const enrollHref = opts.enrollHref || `${HOME}#enroll`;
  const donateHref = opts.donateHref || `${HOME}#donate`;
  const howHref = opts.howHref || `${HOME}#how-it-works`;

  return `<nav class="nav-minimal" aria-label="Main navigation">
    <div class="nav-container">
        <a href="${HOME}" class="logo">
            <img src="vitalscan-01.jpg" alt="VitalScan4PACVS">
        </a>
        <div class="nav-links">
            ${navLink(HOME, 'Home', active, 'home')}
            ${navLink('the-science.html', 'The Science', active, 'science')}
            ${navLink('the-protocol.html', 'The Protocol', active, 'protocol')}
            ${navLink('biomarker-atlas.html', 'Biomarker Atlases', active, 'biomarkers')}
            <a href="https://opensourcemed.info/research-tracker/" target="_blank" rel="noopener" class="nav-link">Research Tracker</a>
            <a href="${howHref}" class="nav-link">How It Works</a>
            <a href="${donateHref}" class="nav-donate">Donate</a>
            <a href="${enrollHref}" class="nav-cta">Register Interest</a>
        </div>
    </div>
</nav>`;
}

const NAV_EXTRA_CSS = `
        .logo img { height: 32px; width: auto; }
        .nav-links { display: flex; align-items: center; gap: 1.25rem; flex-wrap: wrap; }
        .nav-link { color: rgba(255,255,255,0.85); text-decoration: none; font-size: 0.875rem; font-weight: 500; transition: color 0.2s; }
        .nav-link:hover, .nav-link.active { color: white; }
        .nav-cta { background: var(--secondary, #ff9800); color: white !important; padding: 0.625rem 1.25rem; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.875rem; transition: all 0.2s; }
        .nav-cta:hover { background: var(--secondary-dark, #e99314); transform: translateY(-1px); }
        .nav-donate { background: transparent; color: white; border: 1.5px solid rgba(255,255,255,0.5); padding: 0.625rem 1.25rem; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.875rem; transition: all 0.2s; }
        .nav-donate:hover { border-color: white; background: rgba(255,255,255,0.1); }`;

module.exports = { HOME, vitalscanNav, NAV_EXTRA_CSS };