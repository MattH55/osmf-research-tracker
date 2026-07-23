#!/usr/bin/env python3
"""
Post-process generated HTML pages with JSON-LD + thin-content gate.

Ticket 3 — cohort detail pages: Dataset JSON-LD, min_words=150
Ticket 4 — disease-intelligence pages: MedicalCondition JSON-LD, min_words=250
           Phase-3 sample of 20 richest pages (>= 3 merged_ranked therapeutics)

Runs AFTER the respective generators finish.
Usage: python scripts/apply_seo_gating.py [--dry-run] [--ticket-4-sample]
"""
import json, os, sys, re
from pathlib import Path
from typing import Dict, Any, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DETAIL_DIR = ROOT / "pais-cohorts"
DI_DIR = ROOT / "disease-intelligence"
DI_DATA_DIR = ROOT / "data" / "disease-intelligence"
DATA_DIR = ROOT / "data"
CONTENT_DEBT_PATH = DATA_DIR / "content-debt.json"
REF_PATHOGENS = DATA_DIR / "ref" / "pathogens.json"
REF_MEASURES = DATA_DIR / "ref" / "measures.json"
COHORTS_DIR = DATA_DIR / "cohorts"
MIN_WORDS_COHORT = 150
MIN_WORDS_DISEASE = 250

sys.path.insert(0, str(ROOT))
from scripts.lib.dataset_jsonld import build_dataset_jsonld, to_jsonld_script, build_corpus_jsonld
from scripts.lib.medical_condition_jsonld import build_medical_condition_jsonld as build_mc_jsonld
from scripts.lib.thin_content_gate import gate


def load_pathogen_map():
    with open(REF_PATHOGENS, "r", encoding="utf-8") as f:
        return {p["id"]: p for p in json.load(f)["pathogens"]}


def load_measure_map():
    with open(REF_MEASURES, "r", encoding="utf-8") as f:
        return {"_by_id": {m["id"]: m for m in json.load(f)["measures"]}}


def load_cohort_record(cohort_id: str) -> Optional[dict]:
    fp = COHORTS_DIR / f"{cohort_id}.json"
    if not fp.exists():
        return None
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


def inject_jsonld(html_content: str, jsonld_script: str) -> str:
    if "</head>" in html_content:
        return html_content.replace("</head>", f"\n{jsonld_script}\n</head>", 1)
    if "<head>" in html_content:
        return html_content.replace("<head>", f"<head>\n{jsonld_script}", 1)
    return jsonld_script + "\n" + html_content


def inject_meta_robots(html_content: str, robots_value: str = "noindex,follow") -> str:
    pattern = re.compile(r'<meta\s+name\s*=\s*["\']robots["\'][^>]*>', re.IGNORECASE)
    if pattern.search(html_content):
        return pattern.sub(f'<meta name="robots" content="{robots_value}">', html_content, count=1)
    if '<meta charset' in html_content:
        idx = html_content.index('>', html_content.index('<meta charset')) + 1
        return html_content[:idx] + f'\n<meta name="robots" content="{robots_value}">' + html_content[idx:]
    if '<head>' in html_content:
        idx = html_content.index('<head>') + 6
        return html_content[:idx] + f'\n<meta name="robots" content="{robots_value}">' + html_content[idx:]
    return html_content


# ─── Ticket 3: Cohort pages ───────────────────────────────────────────────

def process_cohort_page(html_path: Path, pmap: dict, mmap: dict, content_debt: list, dry_run: bool):
    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    cohort_id = html_path.stem
    record = load_cohort_record(cohort_id)
    if not record:
        print(f"  SKIP {cohort_id}: no source record found")
        return

    jsonld_script = to_jsonld_script(build_dataset_jsonld(record, pmap, mmap))
    result = gate(html_content, min_words=MIN_WORDS_COHORT, corpus_dir=None)

    robots = "index,follow" if result.indexable else "noindex,follow"
    if result.indexable:
        print(f"  PASS {cohort_id}: words={result.word_count}")
    else:
        content_debt.append({
            "page": f"pais-cohorts/{cohort_id}.html", "type": "cohort_detail",
            "word_count": result.word_count, "has_citation": result.has_citation,
            "reasons": result.reasons,
        })
        print(f"  NOINDEX {cohort_id}: words={result.word_count} reasons={result.reasons}")

    modified = inject_jsonld(html_content, jsonld_script)
    modified = inject_meta_robots(modified, robots)

    if dry_run:
        print(f"    [dry-run] would write {len(modified)} bytes")
    else:
        html_path.write_text(modified, encoding="utf-8")
        print(f"    written")


def process_cohort_corpus_page(pmap: dict, n_cohorts: int, n_obs: int, dry_run: bool):
    html_path = ROOT / "pais-cohorts.html"
    if not html_path.exists():
        print("  pais-cohorts.html not found")
        return
    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    if "application/ld+json" in html_content:
        print("  corpus JSON-LD already present, skipping")
        return
    jsonld_script = to_jsonld_script(
        build_corpus_jsonld(n_cohorts, n_obs, [p["name"] for p in pmap.values()])
    )
    if dry_run:
        print(f"  [dry-run] would add corpus JSON-LD to pais-cohorts.html")
    else:
        html_path.write_text(inject_jsonld(html_content, jsonld_script), encoding="utf-8")
        print(f"  added corpus Dataset JSON-LD to pais-cohorts.html")


def run_ticket_3(dry_run: bool, content_debt: list):
    pmap = load_pathogen_map()
    mmap = load_measure_map()
    print("=== Ticket 3: Cohort pages ===")
    html_files = [f for f in sorted(DETAIL_DIR.glob("*.html")) if f.name != "index.html" and f.parent.name != "disease"]
    n_obs = 0
    for fp in html_files:
        record = load_cohort_record(fp.stem)
        if record:
            n_obs += len(record.get("observations", []))
        process_cohort_page(fp, pmap, mmap, content_debt, dry_run)
    process_cohort_corpus_page(pmap, len(html_files), n_obs, dry_run)
    return pmap  # return for reuse


# ─── Ticket 4: Disease-intelligence pages ──────────────────────────────────

def load_disease_json(slug: str) -> Optional[dict]:
    fp = DI_DATA_DIR / f"{slug}.json"
    if not fp.exists():
        return None
    with open(fp, "r", encoding="utf-8") as f:
        return json.load(f)


def sort_by_therapeutic_richness(slug: str) -> int:
    """Return merged_ranked count for sorting — higher = richer page."""
    data = load_disease_json(slug)
    if not data:
        return 0
    merged = data.get("therapeutics", {}).get("merged_ranked", [])
    return len(merged)


def process_disease_page(html_path: Path, content_debt: list, dry_run: bool, phase3_only: bool):
    slug = html_path.stem
    if slug in ("index", "gene-therapy-mapper", "right-to-try"):
        return  # skip non-disease pages

    html_content = html_path.read_text(encoding="utf-8", errors="replace")
    data = load_disease_json(slug)
    if not data:
        print(f"  SKIP {slug}: no source JSON")
        return

    # Check if this page qualifies for Phase-3 sample
    merged_count = len(data.get("therapeutics", {}).get("merged_ranked", []))
    if phase3_only and merged_count < 3:
        return  # not enough therapeutics for Phase-3 gate

    # Build MedicalCondition JSON-LD
    jsonld = build_mc_jsonld(data)
    jsonld_script = f'<script type="application/ld+json">\n{json.dumps(jsonld, ensure_ascii=False)}\n</script>'

    # Run thin-content gate
    result = gate(html_content, min_words=MIN_WORDS_DISEASE, corpus_dir=None)

    robots = "index,follow" if result.indexable else "noindex,follow"
    if result.indexable:
        print(f"  PASS disease/{slug}: words={result.word_count}")
    else:
        content_debt.append({
            "page": f"disease-intelligence/{slug}.html", "type": "disease_template_a",
            "word_count": result.word_count, "has_citation": result.has_citation,
            "merged_therapeutics": merged_count, "reasons": result.reasons,
        })
        print(f"  NOINDEX disease/{slug}: words={result.word_count} reasons={result.reasons}")

    modified = inject_jsonld(html_content, jsonld_script)
    modified = inject_meta_robots(modified, robots)

    if dry_run:
        print(f"    [dry-run] would write {len(modified)} bytes")
    else:
        html_path.write_text(modified, encoding="utf-8")
        print(f"    written: MedicalCondition JSON-LD + robots={robots}")


def run_ticket_4(dry_run: bool, content_debt: list):
    print("=== Ticket 4: Disease-intelligence pages (Template A) ===")
    di_html_files = sorted([f for f in DI_DIR.glob("*.html") if f.name != "index.html"])

    # Sort by therapeutic richness (merged_ranked count)
    scored = [(sort_by_therapeutic_richness(f.stem), f) for f in di_html_files]
    scored.sort(key=lambda x: -x[0])

    # Select Phase-3 sample: top 20 with >= 3 merged_ranked therapeutics
    phase3_sample = [f for count, f in scored if count >= 3][:20]
    print(f"Phase-3 sample: {len(phase3_sample)} pages with >= 3 merged therapeutics")

    phase3_set = set(f.stem for f in phase3_sample)
    processed = 0
    for fp in di_html_files:
        if fp.stem not in phase3_set:
            continue  # skip non-Phase-3 pages per Ticket 4 spec
        process_disease_page(fp, content_debt, dry_run, phase3_only=True)
        processed += 1

    print(f"Processed {processed} disease-intelligence pages (Phase-3 sample)")
    return processed


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    ticket_4_only = "--ticket-4" in sys.argv

    content_debt = []
    if CONTENT_DEBT_PATH.exists():
        with open(CONTENT_DEBT_PATH, "r", encoding="utf-8") as f:
            content_debt = json.load(f)

    if not ticket_4_only:
        run_ticket_3(dry_run, content_debt)

    run_ticket_4(dry_run, content_debt)

    if not dry_run:
        with open(CONTENT_DEBT_PATH, "w", encoding="utf-8") as f:
            json.dump(content_debt, f, indent=2, ensure_ascii=False)
        n_cohort = sum(1 for d in content_debt if d.get("type") == "cohort_detail")
        n_disease = sum(1 for d in content_debt if d.get("type") == "disease_template_a")
        print(f"\nContent debt: {len(content_debt)} total ({n_cohort} cohort, {n_disease} disease)")

    print("Done.")


if __name__ == "__main__":
    main()