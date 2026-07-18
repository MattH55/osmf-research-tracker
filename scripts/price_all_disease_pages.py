#!/usr/bin/env python3
"""
Add prices (or consistent price guidance) to *every* therapeutic entry
across all disease-intelligence JSON files.

Specific prices are provided for common / clinically relevant drugs
(UK via openprescribing.net style, US via Cost Plus Drugs / GoodRx).

Everything else gets a clear fallback pointing users to the sources.

Then regenerates all HTML pages and the index.
"""
import json
import glob
from pathlib import Path
from disease_pipeline.output.generate_html import write_page, build_index_html
from disease_pipeline.published_conditions import is_publishable

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "disease-intelligence"
HTML_DIR = ROOT / "disease-intelligence"

# Expanded map of specific approximate prices.
# Keys are UPPERCASE drug names (we do partial matching too).
# Values are dicts with "uk" and "us".
# These are best-effort snapshots — always verify on the sites.
SPECIFIC_PRICES = {
    # From previous POTS/MCAS work + common ones
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
    "NALTREXONE HYDROCHLORIDE": {"uk": "£15–£30 / 28–50 tabs (low-dose)", "us": "$20–$40 / 30 tabs"},
    "CANNABIDIOL": {"uk": "Varies (specialist)", "us": "$30–$80 / 30-day (varies by product)"},
    "CETIRIZINE": {"uk": "£1–£2 / 30 tabs (10mg)", "us": "$4 / 30 tabs (GoodRx)"},
    "FAMOTIDINE": {"uk": "£2–£4 / 28–60 tabs", "us": "$5–$10 / 30–60 tabs (Cost Plus)"},
    "MONTELUKAST": {"uk": "£2–£5 / 28 tabs", "us": "$5–$12 / 30 tabs"},
    "LORATADINE": {"uk": "£1–£2 / 30 tabs", "us": "$3–$6 / 30 tabs"},
    "KETOTIFEN": {"uk": "£8–£15 / 30–60 tabs", "us": "$10–$20 / supply"},
    "CROMOLYN SODIUM": {"uk": "£10–£20 / inhaler or amps", "us": "$15–$30 / supply"},
    "FEXOFENADINE": {"uk": "£3–£6 / 30 tabs (120-180mg)", "us": "$8–$15 / 30 tabs"},
    "ACETYLCYSTEINE": {"uk": "£5–£12 / 30 tabs or effervescent", "us": "$8–$15 / 30-60 tabs (NAC)"},
    "ALLOPURINOL": {"uk": "£1–£3 / 28 tabs", "us": "$4–$10 / 30-90 tabs"},
    "SILDENAFIL": {"uk": "£2–£8 / 4–8 tabs (generic)", "us": "$5–$15 / 10-30 tabs"},
    "RIVAROXABAN": {"uk": "£20–£50 / 28 tabs (varies by dose)", "us": "$30–$80 / 30 tabs"},
    "APIXABAN": {"uk": "£20–£50 / 28-60 tabs", "us": "$30–$70 / 30-60 tabs"},
    "METFORMIN": {"uk": "£1–£3 / 28–56 tabs", "us": "$4–$10 / 30–90 tabs"},
    "ATORVASTATIN": {"uk": "£1–£4 / 28 tabs", "us": "$5–$12 / 30–90 tabs"},
    "SIMVASTATIN": {"uk": "£1–£3 / 28 tabs", "us": "$4–$10 / 30–90 tabs"},
    "OMEPRAZOLE": {"uk": "£1–£3 / 28 tabs", "us": "$5–$12 / 30–90 tabs"},
    "PREDNISONE": {"uk": "£2–£5 / 28–30 tabs", "us": "$4–$8 / 30 tabs"},
    "PREDNISOLONE": {"uk": "£2–£5 / 28 tabs", "us": "$5–$10 / 30 tabs"},
    "IBUPROFEN": {"uk": "Very low cost OTC/prescription", "us": "Very low cost"},
    "ASPIRIN": {"uk": "Very low cost", "us": "Very low cost"},
    "LEVOTHYROXINE": {"uk": "£1–£4 / 28–30 tabs", "us": "$5–$15 / 30–90 tabs"},
    "AMITRIPTYLINE": {"uk": "£1–£3 / 28 tabs", "us": "$4–$10 / 30 tabs"},
    "DIAZEPAM": {"uk": "£1–£3 / 28 tabs", "us": "$3–$8 / 30 tabs"},
    "PHENYTOIN": {"uk": "£3–£8 / supply", "us": "$6–$15 / 30 tabs"},
    "GABAPENTIN": {"uk": "£2–£5 / 28–100 tabs", "us": "$5–$12 / 30–90 tabs"},  # already above
}

FALLBACK_NOTE = "Varies — check openprescribing.net (UK) or costplusdrugs.com / GoodRx (US)"

def attach_price(drug: dict):
    name = (drug.get("name") or "").upper().strip()
    if not name:
        drug["price_note"] = FALLBACK_NOTE
        return

    if name in SPECIFIC_PRICES:
        drug["prices"] = SPECIFIC_PRICES[name]
        return

    # Partial match for common stems / salts
    for key, val in SPECIFIC_PRICES.items():
        if key in name or name in key:
            drug["prices"] = val
            return

    # Hospital / specialty / chemo agents
    hospital_keywords = ["CISPLATIN", "DOXORUBICIN", "CARBOPLATIN", "OXALIPLATIN", "IRINOTECAN", "ETOPOSIDE",
                         "FLUDARABINE", "METHOTREXATE", "CYCLOPHOSPHAMIDE", "GEMCITABINE", "VINORELBINE",
                         "EPIRUBICIN", "MITOXANTRONE", "DOCETAXEL", "PACLITAXEL", "BORTEZOMIB", "RITUXIMAB",
                         "CETUXIMAB", "TRASTUZUMAB", "PEMBROLIZUMAB", "NIVOLUMAB", "IPILIMUMAB"]
    if any(kw in name for kw in hospital_keywords):
        drug["price_note"] = "Hospital / IV specialty — prices per vial or dose (often hundreds–thousands USD/GBP)"
        return

    # Research / experimental
    if "COMPOUND" in name or "PMID" in name or len(name) < 5 or name.startswith(("(+)", "(-)", "2-", "3-", "4-", "5-", "6-", "7-", "8-", "9-")):
        drug["price_note"] = "Research / experimental compound — pricing not applicable for routine clinical use"
        return

    # Default for everything else
    drug["price_note"] = FALLBACK_NOTE

def process_all():
    json_files = sorted(glob.glob(str(DATA_DIR / "*.json")))
    print(f"Processing {len(json_files)} condition JSONs...")

    for jf in json_files:
        data = json.loads(Path(jf).read_text(encoding="utf-8"))
        ther = data.get("therapeutics", {})
        count = 0
        for section in ["direct", "via_biomarker", "merged_ranked"]:
            for d in ther.get(section, []):
                attach_price(d)
                count += 1
        # Also top-level if present in older formats
        for d in data.get("therapeutics_merged", []) or []:
            attach_price(d)
            count += 1

        Path(jf).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  Enriched {Path(jf).name}: {count} entries")

    print("\nRegenerating all HTML pages...")
    pages = []
    for jf in json_files:
        data = json.loads(Path(jf).read_text(encoding="utf-8"))
        if is_publishable(data):
            write_page(data, HTML_DIR)
            pages.append(data)
            print(f"  Wrote {data.get('slug', Path(jf).stem)}.html")

    print("\nRebuilding index...")
    idx_html = build_index_html(pages)
    (HTML_DIR / "index.html").write_text(idx_html, encoding="utf-8")
    print(f"  Wrote index.html with {len(pages)} conditions")

    print("\nDone! All therapeutics now have price info or guidance.")

if __name__ == "__main__":
    process_all()