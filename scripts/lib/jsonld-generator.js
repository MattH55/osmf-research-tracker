const LOINC_MAP = require('./loinc-map');
const { CANONICAL } = require('./site-config');

const DIRECTION_LABELS = {
  up: 'Elevated or positive vs comparison group',
  down: 'Reduced vs comparison group',
  mixed: 'Altered or heterogeneous across studies',
};

function scholarlyArticle(ref) {
  if (!ref?.doi) return null;
  return {
    '@type': 'ScholarlyArticle',
    name: ref.citation || ref.ref || ref.name,
    identifier: `doi:${ref.doi}`,
    url: `https://doi.org/${ref.doi}`,
  };
}

function markerToSubTest(marker, index, pageUrl) {
  const testType = marker.testType || LOINC_MAP.inferTestType(marker);
  const loinc = marker.loinc || LOINC_MAP.lookupLoinc(marker.name, LOINC_MAP);
  const entry = {
    '@type': testType,
    '@id': `${pageUrl}#marker-${index + 1}`,
    name: marker.name,
    alternateName: marker.alternateName || marker.alias,
    description: [
      marker.symptoms || marker.context,
      marker.comparison ? `Comparison: ${marker.comparison}` : null,
      marker.direction ? `Direction: ${DIRECTION_LABELS[marker.direction] || marker.direction}` : null,
    ].filter(Boolean).join('. '),
    medicineSystem: 'https://schema.org/EvidenceBasedMedicine',
  };

  if (loinc) {
    entry.code = {
      '@type': 'MedicalCode',
      codeValue: loinc,
      codingSystem: 'http://loinc.org',
      name: marker.name,
    };
  }

  const ref = marker.reference || (marker.ref && marker.doi ? { citation: marker.ref, doi: marker.doi } : null);
  const citation = scholarlyArticle(ref);
  if (citation) entry.citation = citation;

  if (marker.symptoms) {
    entry.signDetected = {
      '@type': 'MedicalSign',
      name: marker.symptoms.split(',')[0].trim(),
    };
  }

  return entry;
}

function generateAtlasJsonLd(atlas) {
  const pageUrl = atlas.page.canonical;
  const hubUrl = `${CANONICAL.origin}${CANONICAL.basePath}/${CANONICAL.hubFile}`;
  const condition = {
    '@type': 'MedicalCondition',
    name: atlas.condition.name,
    alternateName: atlas.condition.alternateNames || [],
  };

  const subTests = (atlas.markers || []).map((m, i) => markerToSubTest(m, i, pageUrl));

  const graph = [
    {
      '@type': ['MedicalWebPage', 'Dataset'],
      '@id': `${pageUrl}#webpage`,
      url: pageUrl,
      name: atlas.page.title,
      description: atlas.page.description,
      dateModified: atlas.page.dateModified || new Date().toISOString().slice(0, 10),
      inLanguage: 'en',
      isPartOf: { '@id': `${hubUrl}#webpage` },
      about: condition,
      keywords: (atlas.page.keywords || []).join(', '),
      publisher: {
        '@type': 'Organization',
        name: CANONICAL.publisherName,
        url: CANONICAL.publisherUrl,
      },
      distribution: {
        '@type': 'DataDownload',
        encodingFormat: 'application/json',
        contentUrl: `${CANONICAL.origin}${CANONICAL.basePath}/data/biomarkers/${atlas.slug}.json`,
      },
      variableMeasured: subTests.map((t) => t.name),
    },
    {
      '@type': 'MedicalTestPanel',
      '@id': `${pageUrl}#panel`,
      name: `${atlas.condition.shortName || atlas.condition.name} Biomarker Panel`,
      description: atlas.page.description,
      url: pageUrl,
      usedToDiagnose: condition,
      medicineSystem: 'https://schema.org/EvidenceBasedMedicine',
      subTest: subTests,
      recognizingAuthority: {
        '@type': 'Organization',
        name: 'Peer-reviewed literature synthesis',
      },
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: CANONICAL.publisherUrl },
        { '@type': 'ListItem', position: 2, name: 'Biomarker Atlases', item: hubUrl },
        { '@type': 'ListItem', position: 3, name: atlas.page.breadcrumbName || atlas.condition.shortName, item: pageUrl },
      ],
    },
  ];

  if (atlas.faq?.length) {
    graph.push({
      '@type': 'FAQPage',
      mainEntity: atlas.faq.map((item) => ({
        '@type': 'Question',
        name: item.question,
        acceptedAnswer: { '@type': 'Answer', text: item.answer },
      })),
    });
  }

  return { '@context': 'https://schema.org', '@graph': graph };
}

module.exports = { generateAtlasJsonLd, markerToSubTest, DIRECTION_LABELS };