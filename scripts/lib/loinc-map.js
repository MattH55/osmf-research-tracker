/** LOINC codes for major lab markers — https://loinc.org (check digits verified; codes re-derived from the NLM Clinical Tables LOINC API, 2026-10) */
module.exports = {
  'Interleukin-6 (IL-6)': '26881-3',
  'Interleukin-1 (IL-1α/β)': '34407-7',
  'Interleukin-1α (IL-1α)': '33821-0',
  'Interleukin-8 (IL-8 / CXCL8)': '33211-4',
  'Interleukin-8 (IL-8)': '33211-4',
  'Interleukin-10 (IL-10)': '26848-2',
  'Tumor Necrosis Factor-α (TNF-α)': '3074-2',
  'Transforming Growth Factor-β (TGF-β)': '98861-8',
  'C-Reactive Protein (CRP)': '1988-5',
  'D-dimer': '48065-7',
  'Fibrinogen': '3255-7',
  'von Willebrand Factor (vWF)': '27816-8',
  'Ferritin': '2276-4',
  'Homocysteine': '13965-9',
  'Interferon-γ (IFN-γ)': '27415-9',
  'Lactate (blood)': '2524-7',
  'Lactate': '2524-7',
  'Cortisol (diurnal rhythm)': '2143-6',
  'Cortisol': '2143-6',
  'Vitamin D (25-OH)': '62292-8',
  'Neopterin': '9740-2',
  'Leptin': '21365-2',
  'NT-proBNP': '33762-6',
  'Troponin': '10839-9',
  'LDH (Lactate dehydrogenase)': '2532-0',
  'Neurofilament light chain (NfL)': '101281-4',
  'β2-microglobulin': '1952-1',
  'CSF protein elevation': '2880-3',
  'CSF glucose': '2342-4',
  'sCD14': null,
  'PAI-1': '22758-7',
  'Asymmetric dimethylarginine (ADMA)': '74363-3',
  'Endothelin-1': '49867-5',
  'Resistin': '75632-0',
  'IL-1β': '13629-1',
  'Serum Amyloid A (SAA)': '48498-0',
  'Anti-Spike (Anti-S) antibodies': null,
  'Anti-Nucleocapsid (Anti-N) antibodies': null,
};

module.exports.inferTestType = function inferTestType(marker) {
  const cat = marker.category || '';
  const name = (marker.name || '').toLowerCase();
  if (cat === 'csf' || name.startsWith('csf ')) return 'PathologyTest';
  if (cat === 'urinary' || name.includes('urinary')) return 'PathologyTest';
  if (['functional', 'ocular', 'autonomic'].includes(cat)) return 'MedicalTest';
  if (cat === 'molecular' && !name.includes('blood')) return 'MedicalTest';
  if (['serologic', 'autoimmune', 'inflammatory', 'metabolic', 'mitochondrial', 'immune', 'coagulation', 'vascular', 'neurological', 'exposure', 'chronic', 'coinfection', 'proteomic', 'lipidomic', 'microbiome'].includes(cat)) {
    return 'BloodTest';
  }
  return 'MedicalTest';
};

module.exports.lookupLoinc = function lookupLoinc(name, map) {
  if (map[name]) return map[name];
  const keys = Object.keys(map);
  for (const key of keys) {
    if (name.includes(key) || key.includes(name)) return map[key];
  }
  return null;
};