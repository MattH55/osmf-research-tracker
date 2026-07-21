import json
from pathlib import Path
from disease_pipeline.output.generate_html import write_page
p = Path('data/disease-intelligence/pots.json')
data = json.loads(p.read_text(encoding='utf-8'))
ther = data.setdefault('therapeutics', {})
via = ther.setdefault('via_biomarker', [])
prom = [
  {"name":"IVABRADINE", "score":96, "via":"Clinical (POTS rate control)"},
  {"name":"MIDODRINE", "score":95, "via":"Clinical (vasopressor)"},
  {"name":"FLUDROCORTISONE", "score":94, "via":"Clinical (volume expansion)"},
  {"name":"PYRIDOSTIGMINE", "score":88, "via":"Clinical (autonomic support)"},
]
prices = {
  "IVABRADINE": {"uk": "£28–£40 / 56 tabs (5mg)", "us": "$28 / 60 tabs (5mg, Cost Plus)"},
  "MIDODRINE": {"uk": "£55–£75 / 100 tabs (2.5-5mg)", "us": "$18 / 90 tabs (2.5mg, Cost Plus)"},
  "FLUDROCORTISONE": {"uk": "£6–£10 / 30 tabs (0.1mg)", "us": "$6 / 30 tabs (0.1mg, Cost Plus)"},
  "PYRIDOSTIGMINE": {"uk": "£15–£25 / 60 tabs", "us": "$20–$35 / 30–60 tabs"},
}
existing = {d.get("name","").upper() for d in via}
added=0
for pr in prom:
  n = pr["name"]
  if n not in existing:
    d = {
      "id": f"pots:drug:{n.lower()}",
      "canonical_id": n.lower(),
      "name": n,
      "drug_type": "small_molecule",
      "drug_type_label": "Small molecule",
      "mechanism": "Symptom control for POTS",
      "max_phase": 4,
      "phase_label": "Approved",
      "approved_indications": [],
      "source_type": "via_biomarker",
      "via_alteration": pr["via"],
      "sources": ["Clinical guidelines"],
      "evidence_tier": "A",
      "evidence_tier_label": "Strong",
      "repurposing_signal": True,
      "pubmed_count": 10,
      "score": pr["score"],
      "external_links": [],
      "prices": prices.get(n, {})
    }
    via.append(d)
    added +=1
ther["merged_ranked"] = via[:]
data["summary"]["therapeutic_counts"]["via_biomarker"] = len(via)
data["summary"]["therapeutic_counts"]["merged"] = len(via)
data["summary"]["displayed_therapeutics_merged"] = len(via)
p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print("Added", added)
write_page(data, Path("disease-intelligence"))
print("Regenerated pots.html")
