import json
import os
import requests
from datetime import datetime, timedelta
from pymed import PubMed

# ================== CONFIG ==================
EMAIL = "contact@opensourcemed.info"
TOOL_NAME = "OpenSourceMed_Research_Tracker"
DAYS_BACK = 30
MAX_RESULTS = 50
DATA_DIR = "data"
POSTED_FILE = "posted_pmids.json"

# Make.com Webhook URL (set this as GitHub Secret)
MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL")
# ============================================

os.makedirs(DATA_DIR, exist_ok=True)

CONDITIONS = {
    "pacvs": {
        "name": "PACVS",
        "query": '(("post-acute covid vaccination syndrome" OR PACVS OR PCVS) OR ("COVID-19 Vaccines/adverse effects"[Mesh] AND (persistent OR chronic OR syndrome)))'
    },
    "long-covid": {
        "name": "Long COVID",
        "query": '("long covid" OR PACS OR "post-acute sequelae of covid")'
    },
    "me-cfs": {
        "name": "ME/CFS",
        "query": '("myalgic encephalomyelitis" OR "chronic fatigue syndrome" OR ME/CFS)'
    },
    "lyme": {
        "name": "Chronic Lyme / PTLDS",
        "query": '("Lyme disease" OR borreliosis) AND (chronic OR persistent OR "post-treatment" OR PTLDS)'
    },
    "gulf-war-illness": {
        "name": "Gulf War Illness",
        "query": '("gulf war illness" OR "gulf war syndrome" OR GWI)'
    },
    "other-post-viral": {
        "name": "Other Post-Viral Illnesses",
        "query": '("post-viral" OR "post viral" OR "post-infectious") AND (fatigue OR syndrome) NOT covid'
    }
}

def load_posted_pmids():
    if os.path.exists(POSTED_FILE):
        with open(POSTED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_posted_pmids(pmids):
    with open(POSTED_FILE, "w") as f:
        json.dump(list(pmids), f, indent=2)

def search_papers(config):
    pubmed = PubMed(tool=TOOL_NAME, email=EMAIL)
    results = pubmed.query(config["query"], max_results=MAX_RESULTS)
    cutoff = datetime.now() - timedelta(days=DAYS_BACK)
    
    papers = []
    for article in results:
        try:
            pub_date = datetime.strptime(str(article.publication_date), "%Y-%m-%d")
            if pub_date >= cutoff:
                papers.append({
                    "pmid": article.pubmed_id,
                    "title": article.title,
                    "journal": article.journal or "",
                    "pub_date": str(pub_date.date()),
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{article.pubmed_id}/",
                    "condition": config["name"]
                })
        except:
            continue
    return papers

def send_to_make(papers):
    if not MAKE_WEBHOOK_URL or not papers:
        return
    try:
        response = requests.post(MAKE_WEBHOOK_URL, json={"studies": papers}, timeout=30)
        if response.status_code == 200:
            print(f"Sent {len(papers)} new studies to Make.com")
        else:
            print(f"Make.com error: {response.status_code}")
    except Exception as e:
        print(f"Error sending to Make.com: {e}")

def main():
    posted_pmids = load_posted_pmids()
    new_studies = []

    for key, config in CONDITIONS.items():
        print(f"Checking {config['name']}...")
        papers = search_papers(config)
        
        new_papers = [p for p in papers if p["pmid"] not in posted_pmids]
        
        if new_papers:
            print(f"  → {len(new_papers)} new studies")
            new_studies.extend(new_papers)
        
        # Save JSON for website
        json_path = os.path.join(DATA_DIR, f"{key}.json")
        with open(json_path, "w") as f:
            json.dump(papers, f, indent=2)

    if new_studies:
        send_to_make(new_studies)
        for study in new_studies:
            posted_pmids.add(study["pmid"])
        save_posted_pmids(posted_pmids)
    else:
        print("No new studies today.")

if __name__ == "__main__":
    main()
