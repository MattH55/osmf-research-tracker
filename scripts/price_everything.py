#!/usr/bin/env python3
"""
Price everything in POTS and MCAS therapeutics.
Attaches specific prices (where known from openprescribing.net / Cost Plus / GoodRx)
or a consistent "see sources" note to every drug entry.
Then regenerates the HTML pages.
"""
import json
from pathlib import Path
from disease_pipeline.output.generate_html import write_page

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "disease-intelligence"

# Specific prices (approximate, common formulations; verify live)
# UK: typical NHS tariff / openprescribing pack prices
# US: Cost Plus Drugs or GoodRx cash prices for 30-90 day supply where applicable
SPECIFIC_PRICES = {
    # POTS key clinical
    "IVABRADINE": {"uk": "£28–£40 / 56 tabs (5mg)", "us": "$28 / 60 tabs (5mg, Cost Plus)"},
    "MIDODRINE": {"uk": "£55–£75 / 100 tabs (2.5-5mg)", "us": "$18 / 90 tabs (2.5mg, Cost Plus)"},
    "FLUDROCORTISONE": {"uk": "£6–£10 / 30 tabs (0.1mg)", "us": "$6 / 30 tabs (0.1mg, Cost Plus)"},
    "PROPRANOLOL": {"uk": "£2–£5 / 28–56 tabs", "us": "$4–$10 / 30–60 tabs"},
    "ATENOLOL": {"uk": "£1–£3 / 28 tabs", "us": "$3–$8 / 30 tabs"},
    "METOPROLOL": {"uk": "£2–£4 / 28 tabs", "us": "$4–$9 / 30 tabs"},
    "CARVEDILOL": {"uk": "£2–£5 / 28 tabs", "us": "$5–$10 / 30 tabs"},
    "PRAZOSIN": {"uk": "£2–£6 / 28–60 tabs", "us": "$5–$12 / 30–60 tabs"},
    "VERAPAMIL": {"uk": "£2–£5 / 28 tabs", "us": "$4–$10 / 30–60 tabs"},
    "PYRIDOSTIGMINE": {"uk": "£15–£25 / 60 tabs", "us": "$20–$35 / 30–60 tabs"},
    "ACETAZOLAMIDE": {"uk": "£3–£8 / 28–56 tabs", "us": "$8–$15 / 30 tabs"},
    "GABAPENTIN": {"uk": "£2–£5 / 28–100 tabs", "us": "$5–$12 / 30–90 tabs"},
    "SERTRALINE": {"uk": "£1–£3 / 28 tabs", "us": "$4–$9 / 30 tabs"},
    "PAROXETINE": {"uk": "£2–£4 / 28 tabs", "us": "$5–$10 / 30 tabs"},
    "NALTREXONE HYDROCHLORIDE": {"uk": "£15–£30 / 28–50 tabs (low-dose common)", "us": "$20–$40 / 30 tabs (low dose)"},
    "CANNABIDIOL": {"uk": "Varies widely (specialist)", "us": "$30–$80 / 30-day supply (varies by product)"},
    "EPHEDRINE": {"uk": "£5–£15 / supply (hospital/OTC limits)", "us": "$10–$25 / supply"},
    "PHENYLEPHRINE HYDROCHLORIDE": {"uk": "Low cost generic", "us": "Very low cost"},
    "SILDENAFIL": {"uk": "£2–£8 / 4–8 tabs (generic)", "us": "$5–$15 / 10–30 tabs (generic)"},
    "SIROLIMUS": {"uk": "Specialty — £100s per pack", "us": "$50–$200+ / supply (varies)"},
    "TACROLIMUS ANHYDROUS": {"uk": "Specialty", "us": "$30–$100+ / supply"},
    "PREDNISONE": {"uk": "£2–£5 / 28–30 tabs", "us": "$4–$8 / 30 tabs"},
    "PREDNISOLONE": {"uk": "£2–£5 / 28 tabs", "us": "$5–$10 / 30 tabs"},
    "SODIUM CHLORIDE": {"uk": "Very low (tablets or solution)", "us": "Very low"},
    "INDAPAMIDE": {"uk": "£2–£4 / 28 tabs", "us": "$5–$10 / 30 tabs"},
    "INDOMETHACIN": {"uk": "£3–£8 / 28–56 tabs", "us": "$6–$15 / 30–60 tabs"},
    "CLOMIPRAMINE": {"uk": "£5–£12 / 28 tabs", "us": "$8–$20 / 30 tabs"},
    "IMIPRAMINE": {"uk": "Low cost", "us": "Low cost"},
    "PHENOBARBITAL": {"uk": "£3–£10 / supply", "us": "$5–$15 / 30 tabs"},
    "PHENYTOIN": {"uk": "£3–£8 / supply", "us": "$6–$15 / 30 tabs"},
    "LEVODOPA": {"uk": "Varies (often combo)", "us": "Varies"},
    "METHYLPHENIDATE": {"uk": "£10–£25 / 28–30 tabs (generic)", "us": "$15–$40 / 30 tabs"},
    "ATOMOXETINE": {"uk": "£20–£40 / 28 tabs", "us": "$30–$70 / 30 tabs"},
    "AMPHETAMINE": {"uk": "Controlled — specialist pricing", "us": "Varies (branded higher)"},
    "DIAZEPAM": {"uk": "£1–£3 / 28 tabs", "us": "$3–$8 / 30 tabs"},
    "NALTREXONE HYDROCHLORIDE": {"uk": "£15–£30 / 28–50 tabs", "us": "$20–$40 / 30 tabs"},

    # MCAS (already good coverage)
    "CETIRIZINE": {"uk": "£1–£2 / 30 tabs (10mg)", "us": "$4 / 30 tabs (GoodRx)"},
    "FAMOTIDINE": {"uk": "£2–£4 / 28–60 tabs", "us": "$5–$10 / 30–60 tabs (Cost Plus)"},
    "MONTELUKAST": {"uk": "£2–£5 / 28 tabs", "us": "$5–$12 / 30 tabs"},
    "LORATADINE": {"uk": "£1–£2 / 30 tabs", "us": "$3–$6 / 30 tabs"},
    "KETOTIFEN": {"uk": "£8–£15 / 30–60 tabs", "us": "$10–$20 / supply"},
    "CROMOLYN SODIUM": {"uk": "£10–£20 / inhaler or amps", "us": "$15–$30 / supply"},
    "FEXOFENADINE": {"uk": "£3–£6 / 30 tabs (120-180mg)", "us": "$8–$15 / 30 tabs"},

    # Common others that appear
    "ACETYLCYSTEINE": {"uk": "£5–£12 / 30 tabs or effervescent", "us": "$8–$15 / 30-60 tabs (NAC)"},
    "ALLOPURINOL": {"uk": "£1–£3 / 28 tabs", "us": "$4–$10 / 30-90 tabs"},
    "SILDENAFIL": {"uk": "£2–£8 / 4–8 tabs generic", "us": "$5–$15 / 10-30 tabs"},
    "RIVAROXABAN": {"uk": "£20–£50 / 28 tabs (varies by dose)", "us": "$30–$80 / 30 tabs"},
    "APIXABAN": {"uk": "£20–£50 / 28-60 tabs", "us": "$30–$70 / 30-60 tabs"},
}

FALLBACK_NOTE = "Varies — check openprescribing.net (UK) or costplusdrugs.com / GoodRx (US)"

def attach_price(drug: dict):
    name = (drug.get("name") or "").upper().strip()
    if name in SPECIFIC_PRICES:
        drug["prices"] = SPECIFIC_PRICES[name]
        return
    # Try partial match for common stems
    for key, val in SPECIFIC_PRICES.items():
        if key in name or name in key:
            drug["prices"] = val
            return
    # Special handling for hospital/chemo agents
    if any(x in name for x in ["CISPLATIN", "DOXORUBICIN", "CARBOPLATIN", "OXALIPLATIN", "IRINOTECAN", "ETOPOSIDE", "FLUDARABINE", "METHOTREXATE", "CYCLOPHOSPHAMIDE", "GEMCITABINE", "VINORELBINE", "EPIRUBICIN", "MITOXANTRONE", "DOCETAXEL", "PACLITAXEL", "BORTEZOMIB", "RITUXIMAB", "CETUXIMAB", "TRASTUZUMAB", "PEMBROLIZUMAB"]):
        drug["price_note"] = "Hospital / IV specialty agent — prices per vial/dose (often hundreds to thousands USD/GBP)"
        return
    # Experimental or named compounds
    if "COMPOUND" in name or "PMID" in name or len(name) < 4:
        drug["price_note"] = "Research / experimental — pricing not applicable for routine use"
        return
    drug["price_note"] = FALLBACK_NOTE

def enrich_file(slug: str):
    path = DATA_DIR / f"{slug}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    ther = data.get("therapeutics", {})
    count = 0
    for section in ["direct", "via_biomarker", "merged_ranked"]:
        for d in ther.get(section, []):
            attach_price(d)
            count += 1
    # Also handle top-level if any
    for d in data.get("therapeutics_merged", []) or []:
        attach_price(d)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Enriched {slug}: {count} entries processed")
    return data

def main():
    for slug in ["pots", "mcas"]:
        data = enrich_file(slug)
        write_page(data, DATA_DIR.parent / "disease-intelligence")
        print(f"Regenerated disease-intelligence/{slug}.html")

if __name__ == "__main__":
    main()
    print("All done — every therapeutic now has a price / price info cell.")