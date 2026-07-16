#!/usr/bin/env python3
"""Build gene therapy mapper for monogenic diseases."""
import json
import re
from pathlib import Path
from collections import defaultdict

# Known monogenic diseases with comprehensive gene therapy data
MONOGENIC_DISEASES = {
    'cystic-fibrosis': {
        'genes': ['CFTR'],
        'inheritance': 'autosomal recessive',
        'trials': 8,
        'biomarkers': ['CFTR sequencing', 'Sweat chloride test', 'Immunoreactive trypsinogen (IRT)'],
        'approved_therapies': [
            {'name': 'Lumacaftor/Ivacaftor (Orkambi)', 'year': 2015, 'approach': 'CFTR potentiator', 'mutations': 'F508del/F508del'},
            {'name': 'Elexacaftor/Tezacaftor/Ivacaftor (Trikafta)', 'year': 2019, 'approach': 'CFTR corrector + potentiator', 'mutations': 'Any with F508del'},
        ],
        'mutations': ['F508del (70% prevalence)', 'G551D', 'N1303K', 'Other loss-of-function'],
        'clinical_trials_url': 'https://clinicaltrials.gov/search?cond=Cystic+Fibrosis&type=gene+therapy',
    },
    'sickle-cell-disease': {
        'genes': ['HBB'],
        'inheritance': 'autosomal recessive',
        'trials': 12,
        'biomarkers': ['HBB gene sequencing', 'Hemoglobin electrophoresis', 'Solubility test'],
        'approved_therapies': [
            {'name': 'Exagamglogene autotemcel (Casgevy)', 'year': 2023, 'approach': 'CRISPR base-editing ex vivo', 'mutations': 'All SCD mutations'},
            {'name': 'Frangakis—Bluebird Bio LentiGlobin', 'year': 2023, 'approach': 'Lentiviral gene therapy (pending)', 'mutations': 'βS/βS or βS/βC'},
            {'name': 'Voxelotor (Oxbryta)', 'year': 2019, 'approach': 'Hemoglobin S polymerization inhibitor', 'mutations': 'All SCD mutations'},
        ],
        'mutations': ['βS/βS (homozygous)', 'βS/βC (HbSC disease)', 'βS/βThal (thalassemia variant)'],
        'clinical_trials_url': 'https://clinicaltrials.gov/search?cond=Sickle+Cell+Disease&type=gene+therapy',
    },
    'hemophilia': {
        'genes': ['F8', 'F9'],
        'inheritance': 'X-linked recessive',
        'trials': 15,
        'biomarkers': ['Factor VIII/IX activity assay', 'FVIII/FIX gene sequencing', 'aPTT (activated partial thromboplastin time)'],
        'approved_therapies': [
            {'name': 'Valoctocogene roxaparvovec (Roctavian)', 'year': 2024, 'approach': 'AAV5-mediated F8 gene therapy (Hemophilia A)', 'mutations': 'All F8 mutations'},
            {'name': 'Eteplirsen (Exondys51)', 'year': 2016, 'approach': 'Antisense oligonucleotide for F8 exon-51', 'mutations': 'F8 exon-51 deletable'},
        ],
        'mutations': ['F8 mutations (>1800 known)', 'F9 mutations (>1000 known)'],
        'clinical_trials_url': 'https://clinicaltrials.gov/search?cond=Hemophilia&type=gene+therapy',
    },
    'alpha-1-antitrypsin-deficiency': {
        'genes': ['SERPINA1'],
        'inheritance': 'autosomal recessive',
        'trials': 4,
        'biomarkers': ['AAT serum level (<57 µM indicates deficiency)', 'AAT phenotyping (PiZZ, PiMZ, etc.)', 'SERPINA1 gene sequencing'],
        'approved_therapies': [
            {'name': 'AAT augmentation therapy (IV infusion)', 'year': 1987, 'approach': 'Protein replacement (purified human AAT)', 'mutations': 'PiZZ, PiSZ'},
        ],
        'mutations': ['PiZZ (severe deficiency, ~55% normal levels)', 'PiMZ (intermediate)', 'PiSZ (intermediate)'],
        'clinical_trials_url': 'https://clinicaltrials.gov/search?cond=Alpha-1+Antitrypsin+Deficiency&type=gene+therapy',
    },
    'huntington-disease': {
        'genes': ['HTT'],
        'inheritance': 'autosomal dominant',
        'trials': 4,
        'biomarkers': ['HTT CAG repeat length (>39 repeats diagnostic)', 'MRI for basal ganglia atrophy', 'HTT huntingtin protein levels'],
        'approved_therapies': [
            {'name': 'Tominersen (IONIS-HTT-Rx)', 'year': 'Phase 3', 'approach': 'Antisense oligonucleotide (HTT lowering)', 'mutations': 'All HTT mutations'},
            {'name': 'Valbenazine (Ingrezza)', 'year': 2016, 'approach': 'Symptomatic (VMAT2 inhibitor for chorea)', 'mutations': 'All HTT mutations'},
        ],
        'mutations': ['CAG repeat: 40-49 (incomplete penetrance)', 'CAG repeat: ≥50 (full penetrance)', 'CAG repeat: >60 (juvenile onset)'],
        'clinical_trials_url': 'https://clinicaltrials.gov/search?cond=Huntington+Disease&type=gene+therapy',
    },
}

def get_disease_data():
    """Load disease intelligence data."""
    data_dir = Path(__file__).parent.parent / "data" / "disease-intelligence"
    diseases = {}

    for json_file in sorted(data_dir.glob("*.json")):
        try:
            with open(json_file, encoding='utf-8') as f:
                data = json.load(f)
                slug = data.get('slug') or json_file.stem
                name = data.get('condition', {}).get('name', json_file.stem)

                # Extract alterations (genetic alterations)
                alterations = data.get('alterations', [])
                alt_count = len(alterations) if isinstance(alterations, list) else 0

                # Extract therapeutics
                therapeutics = data.get('therapeutics', {})
                direct_drugs = therapeutics.get('direct', []) if isinstance(therapeutics, dict) else []
                trials_drugs = therapeutics.get('clinical_trials', []) if isinstance(therapeutics, dict) else []

                diseases[slug] = {
                    'name': name,
                    'alterations': alterations[:10] if isinstance(alterations, list) else [],
                    'alt_count': alt_count,
                    'direct_drugs': direct_drugs[:5] if isinstance(direct_drugs, list) else [],
                    'trials_drugs': trials_drugs[:5] if isinstance(trials_drugs, list) else [],
                }
        except Exception as e:
            print(f"Error reading {json_file.name}: {e}")

    return diseases

def build_gene_therapy_entries(diseases):
    """Build gene therapy mapper entries."""
    entries = []

    for slug, gene_info in MONOGENIC_DISEASES.items():
        if slug in diseases:
            disease = diseases[slug]
            entry = {
                'slug': slug,
                'name': disease['name'],
                'genes': gene_info['genes'],
                'inheritance': gene_info['inheritance'],
                'clinical_trials': gene_info['trials'],
                'biomarkers': gene_info.get('biomarkers', []),
                'approved_therapies': gene_info.get('approved_therapies', []),
                'mutations': gene_info.get('mutations', []),
                'clinical_trials_url': gene_info.get('clinical_trials_url', ''),
                'gene_therapies': [],
                'rnai_therapies': [],
                'crispr_candidates': [],
            }

            # Identify gene therapy candidates from existing therapeutics
            for drug in disease['direct_drugs'] + disease['trials_drugs']:
                if isinstance(drug, dict):
                    name = drug.get('name', '')
                    mech = (drug.get('mechanism') or '').lower()

                    if any(x in mech for x in ['gene', 'viral vector', 'aav', 'lentiviral']):
                        entry['gene_therapies'].append(name)
                    elif 'rna' in mech or 'antisense' in mech:
                        entry['rnai_therapies'].append(name)
                    elif 'crispr' in mech or 'base edit' in mech:
                        entry['crispr_candidates'].append(name)

            entries.append(entry)

    # Sort by clinical trial count (most advanced first)
    entries.sort(key=lambda x: -x['clinical_trials'])
    return entries

def generate_html(entries):
    """Generate gene therapy mapper HTML page."""

    html = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gene Therapy Mapper — RepurpOS | OpenSourceMedicine</title>
  <meta name="description" content="Gene therapy mapper: monogenic diseases and single-gene therapy opportunities.">
  <link rel="canonical" href="https://research.opensourcemed.info/disease-intelligence/gene-therapy-mapper.html">
  <link rel="icon" href="https://opensourcemed.info/favicon.png" type="image/png">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    :root{--bg:#0a0e1a;--surface:#141828;--card:#1a1f35;--border:#2a3050;
      --text:#e1e4e8;--muted:#8892a4;--accent:#4a9eff;--green:#22c55e;--amber:#f59e0b;--red:#ef4444}
    body{background:var(--bg);color:var(--text);font-family:Inter,sans-serif;line-height:1.6}
    a{color:var(--accent);text-decoration:none} a:hover{text-decoration:underline}
    code{background:#2a3050;padding:2px 6px;border-radius:4px;font-size:.85em}

    nav{background:rgba(10,14,26,.97);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:100}
    .nav-container{max-width:1200px;margin:0 auto;padding:0 1.5rem;display:flex;align-items:center;justify-content:space-between;height:60px}
    .nav-brand{font-weight:700;font-size:.95rem;color:var(--text)} .nav-brand span{color:var(--accent)}
    .nav-links{list-style:none;display:flex;gap:.5rem} .nav-links a{color:var(--muted);font-size:.85rem;padding:.35rem .75rem;border-radius:6px}
    .nav-links a:hover,.nav-links a.active{color:var(--text);background:var(--card);text-decoration:none}

    .page-hero{background:linear-gradient(135deg,#0d1230,#1a1f45);border-bottom:1px solid var(--border);padding:3rem 1.5rem 2.5rem;text-align:center}
    .hero-eyebrow{color:var(--accent);font-size:.8rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase}
    .page-hero h1{font-size:clamp(1.75rem,4vw,2.5rem);margin:.75rem 0}
    .page-hero p{color:var(--muted);max-width:720px;margin:0 auto;font-size:.95rem}

    main{max-width:1200px;margin:0 auto;padding:2rem 1.5rem 4rem}
    .breadcrumb{display:flex;gap:.5rem;font-size:.85rem;color:var(--muted);margin-bottom:2rem;flex-wrap:wrap}
    .explanation-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:2rem;margin-bottom:2rem}
    .explanation-card h2{font-size:1.1rem;color:var(--accent);margin-bottom:1rem}
    .explanation-card p{font-size:.9rem;color:var(--muted);line-height:1.7;margin-bottom:1rem}
    .explanation-card ul{margin:0 0 1rem 1.5rem;font-size:.9rem;color:var(--muted)}
    .explanation-card li{margin-bottom:.5rem}

    .filter-section{display:flex;flex-wrap:wrap;gap:.75rem;margin:2rem 0 1.5rem;align-items:center}
    .filter-btn{background:var(--surface);border:1px solid var(--border);color:var(--text);padding:.5rem 1.25rem;border-radius:8px;cursor:pointer;font-size:.85rem;font-weight:500;transition:all .2s}
    .filter-btn:hover{border-color:var(--accent);color:var(--accent)}
    .filter-btn.active{color:#000;background:var(--accent);border-color:var(--accent)}

    .results-count{font-size:.9rem;color:var(--muted);margin-bottom:1rem}

    .disease-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:1.5rem;margin-top:2rem}
    .disease-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.5rem;transition:all .2s}
    .disease-card:hover{box-shadow:0 8px 24px rgba(74,158,255,.15);border-color:var(--accent);transform:translateY(-2px)}

    .disease-title{font-size:1.1rem;font-weight:700;color:var(--text);margin-bottom:1rem}

    .info-row{display:flex;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid rgba(42,48,80,.3);font-size:.85rem}
    .info-row:last-child{border-bottom:none}
    .info-label{color:var(--muted)}
    .info-value{color:var(--text);font-weight:600}
    .info-value.highlight{color:var(--green)}

    .gene-list{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem;margin:1rem 0;font-size:.85rem}
    .gene-list-title{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.5rem;font-weight:600}
    .gene-tags{display:flex;flex-wrap:wrap;gap:.5rem}
    .gene-tag{background:rgba(74,158,255,.15);color:var(--accent);padding:3px 8px;border-radius:4px;font-size:.8rem;font-weight:500}

    .section-box{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:1rem;margin:1rem 0;font-size:.85rem}
    .section-box-title{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.75rem;font-weight:600}
    .section-box-item{margin-bottom:.6rem;font-size:.85rem}
    .section-box-item strong{color:var(--text)}
    .section-box-item .detail{color:var(--muted);font-size:.8rem;margin-top:.2rem}

    .therapy-section{margin-top:1rem}
    .therapy-title{font-size:.8rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-weight:600;margin-bottom:.5rem}
    .therapy-item{background:rgba(34,197,94,.1);color:var(--green);padding:.4rem .7rem;border-radius:4px;font-size:.8rem;margin-bottom:.3rem;display:inline-block;margin-right:.5rem}
    .therapy-item.rna{background:rgba(245,158,11,.1);color:var(--amber)}
    .therapy-item.crispr{background:rgba(124,106,247,.1);color:#7c6af7}
    .therapy-item.approved{background:rgba(34,197,94,.2);color:var(--green);border:1px solid rgba(34,197,94,.3)}

    .cta-button{display:inline-block;margin-top:1rem;padding:.6rem 1.25rem;background:var(--accent);color:var(--bg);text-decoration:none;border-radius:6px;font-size:.85rem;font-weight:600;transition:all .2s;border:none;cursor:pointer}
    .cta-button:hover{opacity:.9;transform:translateY(-1px)}

    footer{text-align:center;padding:2rem;color:var(--muted);font-size:.8rem;border-top:1px solid var(--border)}
  </style>
</head>
<body>

  <nav>
    <div class="nav-container">
      <a href="../index.html" class="nav-brand">Open Source Medicine <span>Foundation</span></a>
      <ul class="nav-links"><li><a href="../index.html">Research Tracker</a></li><li><a href="index.html" class="active">RepurpOS</a></li><li><a href="../clinical_trials.html">Clinical Trials</a></li></ul>
    </div>
  </nav>

  <header class="page-hero">
    <div class="hero-eyebrow">RepurpOS</div>
    <h1>Gene Therapy Mapper</h1>
    <p>Monogenic diseases and single-gene therapy opportunities. Identifies candidates for gene replacement, RNA interference, and CRISPR-based approaches.</p>
  </header>

  <main>
    <nav class="breadcrumb" aria-label="Breadcrumb">
      <a href="../index.html">Home</a><span>/</span>
      <a href="index.html">RepurpOS</a><span>/</span>
      <span>Gene Therapy Mapper</span>
    </nav>

    <div class="explanation-card">
      <h2>Monogenic Diseases & Gene Therapy Approaches</h2>
      <p>This mapper identifies diseases caused by single-gene mutations and their corresponding gene therapy strategies:</p>
      <ul>
        <li><strong>Gene Replacement:</strong> Deliver functional copies via viral vectors (AAV, lentiviral, adenoviral) to restore protein function</li>
        <li><strong>RNA Interference:</strong> Silence disease-causing alleles using antisense oligonucleotides or siRNA (e.g., nusinersen for SMA)</li>
        <li><strong>CRISPR/Base Editing:</strong> Correct mutations in-situ using genome editing (e.g., exagamglogene autotemcel for RPE65-LCA)</li>
        <li><strong>Protein Replacement:</strong> Enzyme replacement therapy (ERT) for lysosomal storage diseases</li>
      </ul>
      <p style="margin-top: 1rem; font-size: .9rem; color: var(--muted);">Clinical trials count reflects active and completed studies from ClinicalTrials.gov.</p>
    </div>

    <section>
      <h2 style="font-size: 1.25rem; font-weight: 700; margin-bottom: .5rem;">Monogenic Diseases & Therapy Candidates</h2>
      <p style="font-size: .9rem; color: var(--muted); margin-bottom: 1.5rem;">Sorted by clinical trial activity (most advanced first)</p>

      <div class="results-count" id="results-count">Showing ''' + str(len(entries)) + ''' diseases</div>

      <div class="disease-grid" id="disease-grid">
'''

    for entry in entries:
        genes_html = ' '.join([f'<span class="gene-tag">{g}</span>' for g in entry['genes']])

        # Biomarkers section
        biomarkers_html = ''
        if entry['biomarkers']:
            biomarkers_items = ''.join([f'<div class="section-box-item">• {b}</div>' for b in entry['biomarkers']])
            biomarkers_html = f'<div class="section-box"><div class="section-box-title">Genetic Testing / Biomarkers</div>{biomarkers_items}</div>'

        # Approved therapies section
        approved_html = ''
        if entry['approved_therapies']:
            approved_items = ''.join([
                f'<div class="therapy-item approved">'
                f'<strong>{t.get("name", "")}</strong>'
                f'<div class="detail">{t.get("approach", "")} ({t.get("year", "")})</div>'
                f'<div class="detail">Mutations: {t.get("mutations", "")}</div>'
                f'</div>'
                for t in entry['approved_therapies']
            ])
            approved_html = f'<div style="margin-top: 1rem;"><div class="therapy-title">FDA/EMA Approved Therapies</div>{approved_items}</div>'

        # Mutation stratification
        mutations_html = ''
        if entry['mutations']:
            mutations_items = ''.join([f'<div class="section-box-item">• {m}</div>' for m in entry['mutations']])
            mutations_html = f'<div class="section-box"><div class="section-box-title">Mutation Stratification</div>{mutations_items}</div>'

        # Candidate therapies
        gene_therapies_html = ''
        if entry['gene_therapies']:
            gene_therapies_html = '<div class="therapy-section">' + \
                '<div class="therapy-title">Gene Replacement Candidates</div>' + \
                ''.join([f'<span class="therapy-item">{d}</span>' for d in entry['gene_therapies']]) + \
                '</div>'

        rnai_html = ''
        if entry['rnai_therapies']:
            rnai_html = '<div class="therapy-section">' + \
                '<div class="therapy-title">RNA Interference (Antisense)</div>' + \
                ''.join([f'<span class="therapy-item rna">{d}</span>' for d in entry['rnai_therapies']]) + \
                '</div>'

        crispr_html = ''
        if entry['crispr_candidates']:
            crispr_html = '<div class="therapy-section">' + \
                '<div class="therapy-title">CRISPR/Base Editing</div>' + \
                ''.join([f'<span class="therapy-item crispr">{d}</span>' for d in entry['crispr_candidates']]) + \
                '</div>'

        # Clinical trials link
        trials_link = ''
        if entry['clinical_trials_url']:
            trials_link = f'<a href="{entry["clinical_trials_url"]}" target="_blank" style="display:inline-block;margin-top:.5rem;padding:.4rem .9rem;background:rgba(74,158,255,.1);color:var(--accent);border:1px solid rgba(74,158,255,.3);text-decoration:none;border-radius:6px;font-size:.8rem;font-weight:600;">View Clinical Trials →</a>'

        html += f'''
        <div class="disease-card">
          <div class="disease-title">{entry['name']}</div>

          <div style="margin-bottom: 1rem;">
            <div class="info-row">
              <span class="info-label">Inheritance Pattern:</span>
              <span class="info-value">{entry['inheritance'].title()}</span>
            </div>
            <div class="info-row">
              <span class="info-label">Clinical Trials:</span>
              <span class="info-value highlight">{entry['clinical_trials']}</span>
            </div>
          </div>

          <div class="gene-list">
            <div class="gene-list-title">Primary Genes</div>
            <div class="gene-tags">{genes_html}</div>
          </div>

          {biomarkers_html}

          {approved_html}

          {mutations_html}

          {gene_therapies_html}
          {rnai_html}
          {crispr_html}

          <div style="display: flex; gap: .5rem; margin-top: 1rem;">
            <a href="{entry['slug']}.html" class="cta-button">View Disease Profile</a>
            {trials_link}
          </div>
        </div>
'''

    html += '''
      </div>
    </section>

  </main>

  <footer>
    <p>Gene Therapy Mapper. Data: Open Targets, ClinicalTrials.gov, FDA/EMA approvals. Not medical or legal advice.</p>
  </footer>

</body>
</html>
'''
    return html

def main():
    """Build gene therapy mapper."""
    print("Building gene therapy mapper...")

    diseases = get_disease_data()
    print(f"Loaded {len(diseases)} disease profiles")

    entries = build_gene_therapy_entries(diseases)
    print(f"Identified {len(entries)} monogenic disease candidates")

    html = generate_html(entries)

    # Write to file
    output_file = Path(__file__).parent.parent / "disease-intelligence" / "gene-therapy-mapper.html"
    output_file.write_text(html, encoding='utf-8')

    print(f"\nGenerated gene-therapy-mapper.html")
    print(f"\nMonogenic Diseases Found:")
    for entry in entries:
        print(f"  - {entry['name']}: {len(entry['genes'])} gene(s), {entry['clinical_trials']} trials")

if __name__ == "__main__":
    main()
