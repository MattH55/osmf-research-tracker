/** LOINC codes for major lab markers — https://loinc.org */
module.exports = {
  'Interleukin-6 (IL-6)': '26881-5',
  'Interleukin-1 (IL-1α/β)': '26864-3',
  'Interleukin-1α (IL-1α)': '26864-3',
  'Interleukin-8 (IL-8 / CXCL8)': '26998-9',
  'Interleukin-8 (IL-8)': '26998-9',
  'Interleukin-10 (IL-10)': '26862-5',
  'Tumor Necrosis Factor-α (TNF-α)': '3074-8',
  'Transforming Growth Factor-β (TGF-β)': '27999-4',
  'C-Reactive Protein (CRP)': '1988-5',
  'D-dimer': '48065-7',
  'Fibrinogen': '3255-7',
  'von Willebrand Factor (vWF)': '27816-0',
  'Ferritin': '2276-4',
  'Homocysteine': '13965-9',
  'Interferon-γ (IFN-γ)': '14477-8',
  'Lactate (blood)': '2524-7',
  'Lactate': '2524-7',
  'Cortisol (diurnal rhythm)': '2143-6',
  'Cortisol': '2143-6',
  'Vitamin D (25-OH)': '1989-3',
  'Neopterin': '3254-0',
  'Leptin': '21365-2',
  'NT-proBNP': '33762-6',
  'Troponin': '10839-9',
  'LDH (Lactate dehydrogenase)': '2532-0',
  'Neurofilament light chain (NfL)': '94635-5',
  'β2-microglobulin': '1952-1',
  'CSF protein elevation': '2880-3',
  'CSF glucose': '2340-8',
  'sCD14': '30180-5',
  'PAI-1': '3242-4',
  'Asymmetric dimethylarginine (ADMA)': '10988-1',
  'Endothelin-1': '27940-8',
  'Resistin': '42702-4',
  'IL-1β': '26864-3',
  'Serum Amyloid A (SAA)': '35648-5',
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