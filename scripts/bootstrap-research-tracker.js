/**
 * Copy biomarker build infrastructure into OSM research-tracker and deploy latest artifacts.
 * Run from Intervention Study: npm run bootstrap:tracker
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const TRACKER_ROOT = path.join(
  'C:',
  'Users',
  'matth',
  'OneDrive',
  'Documents',
  'OpenSourceMed',
  'Opensource Medicine (1)',
  'research-tracker'
);

const COPY_DIRS = [
  'scripts',
  'js',
  'css',
  'config',
];

const COPY_FILES = [
  'biomarkers.schema.json',
  'requirements-biomarker-pipeline.txt',
  '.gitignore',
];

const SKIP_DIR_NAMES = new Set(['__pycache__', 'node_modules', '.git']);

function copyRecursive(src, dest) {
  if (!fs.existsSync(src)) return;
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    if (SKIP_DIR_NAMES.has(path.basename(src))) return;
    if (!fs.existsSync(dest)) fs.mkdirSync(dest, { recursive: true });
    for (const entry of fs.readdirSync(src)) {
      copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
    return;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

function writeTrackerPackageJson() {
  const src = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
  const scripts = { ...src.scripts };
  delete scripts['sync:osm'];
  delete scripts['mirror:biomarkers'];
  delete scripts['bootstrap:tracker'];
  delete scripts['start'];
  delete scripts['build:seo'];
  scripts['build:all'] =
    'node scripts/apply-site-seo.js && npm run build:commercial && npm run build:consumable && npm run build:trials && npm run build:interventions && npm run build:treatments && npm run build:bundles && npm run build:hub && npm run build:atlases && node scripts/patch-tracker-integration.js';

  const pkg = {
    name: 'osm-research-tracker',
    version: '1.0.0',
    private: true,
    description: 'Open Source Medicine Research Tracker — canonical biomarker atlases and literature feeds',
    scripts,
    dependencies: {},
  };
  fs.writeFileSync(path.join(TRACKER_ROOT, 'package.json'), JSON.stringify(pkg, null, 2) + '\n', 'utf8');
}

function writeSecretsExample() {
  const example = path.join(ROOT, 'config', 'secrets.local.example.json');
  if (fs.existsSync(example)) {
    fs.copyFileSync(example, path.join(TRACKER_ROOT, 'config', 'secrets.local.example.json'));
  }
}

function main() {
  if (!fs.existsSync(TRACKER_ROOT)) {
    console.error(`Research tracker not found: ${TRACKER_ROOT}`);
    process.exit(1);
  }

  console.log('Running deploy (sync:osm)...');
  execSync('node scripts/sync-osm-biomarkers.js', { cwd: ROOT, stdio: 'inherit' });

  console.log('Copying build infrastructure...');
  for (const dir of COPY_DIRS) {
    copyRecursive(path.join(ROOT, dir), path.join(TRACKER_ROOT, dir));
  }
  for (const file of COPY_FILES) {
    const src = path.join(ROOT, file);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, path.join(TRACKER_ROOT, file));
    }
  }

  writeTrackerPackageJson();
  writeSecretsExample();

  console.log(`\nBootstrap complete: ${TRACKER_ROOT}`);
  console.log('  - Latest biomarker HTML, data/, js/ deployed via sync:osm');
  console.log('  - scripts/, package.json, css/ copied for in-place builds');
  console.log('\nFrom research-tracker folder, run: npm run build:all');
}

main();