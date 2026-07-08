import json
import csv
from datetime import datetime, timezone

print("Creating clean therapeutic agents list from PACVS_Evidence_Map.csv + quality trials...")

# Load gold standard from CSV
gold = {}
with open("clinical_trials/PACVS_Evidence_Map.csv", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = row["Therapy"].strip()
        if not name: continue
        gold[name.lower()] = {
            "Therapeutic Agent": name,
            "Primary Conditions": [row.get("Primary Condition", "PACVS – Post-Acute COVID-19 Vaccination Syndrome")],
            "Proposed Mechanism": row.get("Category", "See source"),
            "Evidence Level": row.get("Evidence Level", "Preliminary"),
            "Key Studies / References": [row.get("DOI / Source", "")] if row.get("DOI / Source") else [],
            "Ongoing Research": "",
            "Clinical Notes": row.get("Key Finding", "Review source for details.")[:450],
            "Last Updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "studies": [],
            "trials": [],
            "aliases": [],
            "types": [],
            "mechanisms": [],
            "trial_types": [],
            "trial_sizes": []
        }

print("Loaded", len(gold), "from CSV")

# Add quality agents from current trials (only real drugs/supplements that match our 5 conditions)
with open("clinical_trials/data/clinical_trials_current.json", encoding="utf-8") as f:
    ct = json.load(f)

quality_names = ["tirzepatide", "sirolimus", "paxlovid", "nirmatrelvir", "metformin", "fluvoxamine", 
                 "ivig", "ldn", "low-dose naltrexone", "nac", "n-acetylcysteine", "coq10", 
                 "rituximab", "montelukast", "ivabradine", "pyridostigmine", "creatine", "taurine",
                 "lumbrokinase", "nattokinase", "maraviroc", "pravastatin", "aspirin", "ketotifen",
                 "cromolyn", "midodrine", "fludrocortisone", "desmopressin", "propranolol", "rupatadine"]

for t in ct.get("trials", []):
    mapped = [c.lower() for c in t.get("mapped_conditions", [])]
    if not any("long covid" in m or "pasc" in m or "me/cfs" in m or "pots" in m or "mcas" in m or "pacvs" in m for m in mapped):
        continue
    for ag in t.get("agents", []):
        low = ag.lower().strip()
        if any(q in low for q in quality_names):
            key = ag.lower()
            if key not in gold:
                gold[key] = {
                    "Therapeutic Agent": ag,
                    "Primary Conditions": t.get("mapped_conditions", []),
                    "Proposed Mechanism": "See trial",
                    "Evidence Level": "Preliminary",
                    "Key Studies / References": [],
                    "Ongoing Research": t.get("status", "") if t.get("status","").upper() not in ["COMPLETED"] else "",
                    "Clinical Notes": "See the linked clinical trial for protocol details, inclusion criteria, and results when available.",
                    "Last Updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "studies": [],
                    "trials": [],
                    "aliases": [],
                    "types": [],
                    "mechanisms": [],
                    "trial_types": [],
                    "trial_sizes": []
                }
            g = gold[key]
            g["trials"].append({
                "nct_id": t["nct_id"],
                "title": t["title"][:120],
                "status": t.get("status"),
                "phase": t.get("phase"),
                "start_date": t.get("start_date"),
                "completion_date": t.get("completion_date")
            })
            for c in t.get("mapped_conditions", []):
                if c not in g.get("Primary Conditions", []):
                    g.setdefault("Primary Conditions", []).append(c)

print("After quality trials:", len(gold))

# Final output
final = {
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "count": len(gold),
    "agents": list(gold.values())
}

with open("data/therapeutic_agents.json", "w", encoding="utf-8") as f:
    json.dump(final, f, indent=2, ensure_ascii=False)

print("Saved clean data/therapeutic_agents.json with", len(gold), "agents")
print("Done. The agents.html should now reflect the focused, high-quality list.")
