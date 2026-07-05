/**
 * One-time / repeatable extraction: HTML atlas pages -> data/biomarkers/*.json
 */
const fs = require('fs');
const path = require('path');
const LOINC_MAP = require('./lib/loinc-map');

const ROOT = path.join(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'data', 'biomarkers');

const ATLAS_META = {
  'long-covid-biomarkers.html': {
    slug: 'long-covid',
    id: 'long-covid-biomarkers',
    condition: {
      name: 'Long COVID',
      shortName: 'Long COVID',
      alternateNames: ['PASC', 'Post-Acute Sequelae of COVID-19'],
    },
    page: {
      title: 'Long COVID Biomarker Atlas | PASC Blood Tests & Metabolite Alterations',
      breadcrumbName: 'Long COVID Biomarkers',
      description: 'Searchable atlas of long COVID (PASC) biomarkers — cytokines, metabolomics, coagulation, vascular, neurological, and proteomic alterations vs healthy and recovered individuals, from peer-reviewed systematic reviews.',
      keywords: ['long COVID biomarkers', 'PASC biomarkers', 'post-acute COVID syndrome blood tests', 'long COVID cytokines', 'long COVID metabolomics', 'D-dimer long COVID', 'microclots long COVID'],
      canonical: 'https://research.opensourcemed.info/long-covid-biomarkers.html',
      hero: 'Molecular, metabolic, and immunological alterations reported in post-acute sequelae of COVID-19 (PASC / long COVID) compared to healthy controls and fully recovered individuals.',
      dateModified: '2026-06-29',
    },
    categories: {
      inflammatory: 'Inflammatory', metabolic: 'Metabolic', coagulation: 'Coagulation', vascular: 'Vascular',
      neurological: 'Neurological', immune: 'Immune', proteomic: 'Proteomic', lipidomic: 'Lipidomic',
      microbiome: 'Microbiome', viral: 'Viral',
    },
    filters: ['inflammatory', 'metabolic', 'coagulation', 'vascular', 'neurological', 'immune', 'lipidomic', 'proteomic', 'microbiome'],
  },
  'pacvs-biomarkers.html': {
    slug: 'pacvs',
    id: 'pacvs-biomarkers',
    condition: { name: 'Post-Acute COVID-19 Vaccination Syndrome', shortName: 'PACVS', alternateNames: ['PACVS', 'PCVS'] },
    page: {
      title: 'PACVS Biomarker Atlas | Post-Vaccination Syndrome Blood Tests & Spike Markers',
      breadcrumbName: 'PACVS Biomarkers',
      description: 'Searchable atlas of PACVS biomarkers — spike protein persistence, GPCR autoantibodies, serologic discrimination, mitochondrial dysfunction, and coagulation markers vs healthy controls, from peer-reviewed literature.',
      keywords: ['PACVS biomarkers', 'post-vaccination syndrome blood tests', 'spike protein persistence', 'GPCR autoantibodies', 'post COVID vaccine syndrome'],
      canonical: 'https://research.opensourcemed.info/pacvs-biomarkers.html',
      hero: 'Molecular, metabolic, and immunological alterations in Post-Acute COVID-19 Vaccination Syndrome (PACVS) — persistent symptoms following SARS-CoV-2 vaccination — compared to healthy, pre-vaccination baselines and recovered individuals.',
      dateModified: '2026-06-29',
    },
    categories: {
      spike: 'Spike Antigen', serologic: 'Serologic', autoimmune: 'Autoimmune', metabolic: 'Metabolic',
      coagulation: 'Coagulation', vascular: 'Vascular', molecular: 'Molecular', proteomic: 'Proteomic',
      inflammatory: 'Inflammatory', functional: 'Functional',
    },
    filters: ['spike', 'serologic', 'autoimmune', 'metabolic', 'coagulation', 'vascular', 'molecular', 'functional'],
  },
  'me-cfs-biomarkers.html': {
    slug: 'me-cfs',
    id: 'me-cfs-biomarkers',
    condition: { name: 'Myalgic Encephalomyelitis / Chronic Fatigue Syndrome', shortName: 'ME/CFS', alternateNames: ['ME/CFS', 'CFS', 'ME'] },
    page: {
      title: 'ME/CFS Biomarker Atlas | Myalgic Encephalomyelitis / Chronic Fatigue Syndrome',
      breadcrumbName: 'ME/CFS Biomarkers',
      description: 'Searchable atlas of biomarker, metabolite, cytokine, mitochondrial, and autonomic alterations in ME/CFS vs healthy controls — synthesized from peer-reviewed systematic reviews and meta-analyses.',
      keywords: ['ME/CFS biomarkers', 'myalgic encephalomyelitis biomarkers', 'chronic fatigue syndrome blood tests', 'PEM biomarkers', 'acylcarnitines ME/CFS'],
      canonical: 'https://research.opensourcemed.info/me-cfs-biomarkers.html',
      hero: 'Molecular, metabolic, immunological, and autonomic alterations in myalgic encephalomyelitis / chronic fatigue syndrome (ME/CFS) compared to healthy sedentary and active controls — including post-exertional malaise (PEM) phenotypes.',
      dateModified: '2026-06-29',
    },
    categories: {
      inflammatory: 'Inflammatory', metabolic: 'Metabolic', mitochondrial: 'Mitochondrial', immune: 'Immune',
      autoimmune: 'Autoimmune', autonomic: 'Autonomic', neurological: 'Neurological', urinary: 'Urinary', functional: 'Functional',
    },
    filters: ['inflammatory', 'metabolic', 'mitochondrial', 'immune', 'autoimmune', 'autonomic', 'neurological', 'urinary', 'functional'],
    faq: [
      { question: 'Is there a single diagnostic biomarker for ME/CFS?', answer: 'No. ME/CFS remains a clinical diagnosis. Multiple biomarker domains show group-level differences vs healthy controls but none are FDA-validated as standalone diagnostic tests.' },
      { question: 'What biomarkers are most replicated in ME/CFS research?', answer: 'Meta-analyses report altered cytokines (IL-1, TGF-β), elevated acylcarnitines, reduced heart rate variability, mitochondrial abnormalities, and urinary metabolite signatures.' },
    ],
  },
  'lyme-biomarkers.html': {
    slug: 'lyme',
    id: 'lyme-biomarkers',
    condition: { name: 'Lyme Disease', shortName: 'Lyme Disease', alternateNames: ['Lyme borreliosis', 'Borrelia burgdorferi infection'] },
    page: {
      title: 'Lyme Disease Biomarker Atlas | Serology, CSF & Chronic Lyme Markers',
      breadcrumbName: 'Lyme Disease Biomarkers',
      description: 'Searchable atlas of Lyme disease biomarkers — two-tier serology, C6 peptide ELISA, CSF indices, CXCL13, and inflammatory markers for early, disseminated, and post-treatment Lyme — from peer-reviewed literature.',
      keywords: ['Lyme disease biomarkers', 'Lyme serology', 'C6 peptide ELISA', 'neuroborreliosis CSF', 'CXCL13 Lyme', 'chronic Lyme biomarkers'],
      canonical: 'https://research.opensourcemed.info/lyme-biomarkers.html',
      hero: 'Serologic, cerebrospinal fluid, molecular, and inflammatory biomarkers in Borrelia burgdorferi infection — from early localized disease through disseminated, neuroborreliosis, and post-treatment persistent symptom phenotypes.',
      dateModified: '2026-06-29',
    },
    categories: {
      serologic: 'Serologic', csf: 'CSF', inflammatory: 'Inflammatory', molecular: 'Molecular',
      coinfection: 'Co-infection', chronic: 'Chronic/PTLDS', functional: 'Functional',
    },
    filters: ['serologic', 'csf', 'inflammatory', 'molecular', 'coinfection', 'chronic', 'functional'],
    faq: [
      { question: 'What is the standard Lyme disease blood test?', answer: 'CDC-recommended two-tier testing: an EIA for Borrelia burgdorferi antibodies, followed by IgM and/or IgG immunoblot if the EIA is positive or equivocal. The C6 peptide ELISA is an alternative first-tier test.' },
      { question: 'Are there biomarkers for chronic Lyme or post-treatment Lyme disease?', answer: 'No validated chronic Lyme biomarker panel exists. Persistent symptoms after standard antibiotic therapy (PTLDS) overlap clinically with ME/CFS.' },
    ],
  },
  'gulf-war-illness-biomarkers.html': {
    slug: 'gulf-war-illness',
    id: 'gulf-war-illness-biomarkers',
    condition: { name: 'Gulf War Illness', shortName: 'Gulf War Illness', alternateNames: ['GWI', 'Gulf War Syndrome', 'Chronic Multisymptom Illness'] },
    page: {
      title: 'Gulf War Illness Biomarker Atlas | GWI / Gulf War Syndrome Markers',
      breadcrumbName: 'Gulf War Illness Biomarkers',
      description: 'Searchable atlas of Gulf War Illness (GWI) biomarkers — chronic inflammation, homocysteine, IFN-γ, autoantibodies, cholinergic dysfunction, and exposure-related markers vs healthy veterans, from peer-reviewed literature.',
      keywords: ['Gulf War Illness biomarkers', 'Gulf War Syndrome blood tests', 'GWI inflammation', 'homocysteine Gulf War', 'chronic multisymptom illness veterans'],
      canonical: 'https://research.opensourcemed.info/gulf-war-illness-biomarkers.html',
      hero: 'Inflammatory, autoimmune, metabolic, cholinergic, and exposure-related biomarker alterations in Gulf War Illness (GWI / chronic multisymptom illness) compared to healthy deployed and non-deployed Gulf War veterans.',
      dateModified: '2026-06-29',
    },
    categories: {
      inflammatory: 'Inflammatory', autoimmune: 'Autoimmune', exposure: 'Exposure', metabolic: 'Metabolic',
      neurological: 'Neurological', autonomic: 'Autonomic', ocular: 'Ocular', functional: 'Functional',
    },
    filters: ['inflammatory', 'autoimmune', 'exposure', 'metabolic', 'neurological', 'autonomic', 'ocular', 'functional'],
    faq: [
      { question: 'Is there a validated diagnostic biomarker for Gulf War Illness?', answer: 'No. A 2021 systematic review found no single validated diagnostic biomarker for GWI. Chronic inflammation, homocysteine, IFN-γ, and cholinergic autoantibodies are recurring research findings.' },
      { question: 'What exposures are linked to Gulf War Illness biomarker research?', answer: 'GWI research examines pesticide exposures, pyridostigmine bromide, oil well fire smoke, depleted uranium, and multiple vaccinations.' },
    ],
  },
};

function normalizeMarker(raw) {
  const marker = {
    name: raw.name,
    alternateName: raw.alias,
    direction: raw.direction,
    category: raw.category,
    comparison: raw.comparison,
    symptoms: raw.symptoms || raw.context,
    reference: { citation: raw.ref, doi: raw.doi },
    testType: LOINC_MAP.inferTestType(raw),
    loinc: LOINC_MAP.lookupLoinc(raw.name, LOINC_MAP) || undefined,
  };
  if (!marker.loinc) delete marker.loinc;
  return marker;
}

function extractFromHtml(filename) {
  const html = fs.readFileSync(path.join(ROOT, filename), 'utf8');
  const m = html.match(/const biomarkers = (\[[\s\S]*?\]);/);
  if (!m) throw new Error(`No biomarkers array in ${filename}`);
  const rawMarkers = eval(m[1]);
  const meta = ATLAS_META[filename];
  return {
    ...meta,
    markers: rawMarkers.map(normalizeMarker),
  };
}

if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

for (const file of Object.keys(ATLAS_META)) {
  const atlas = extractFromHtml(file);
  const outPath = path.join(OUT_DIR, `${atlas.slug}.json`);
  fs.writeFileSync(outPath, JSON.stringify(atlas, null, 2), 'utf8');
  const loincCount = atlas.markers.filter((m) => m.loinc).length;
  console.log(`Wrote ${outPath} (${atlas.markers.length} markers, ${loincCount} with LOINC)`);
}