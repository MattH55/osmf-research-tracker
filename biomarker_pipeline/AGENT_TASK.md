# Agent Task: Biomarker & Intervention Discovery Pipeline

## Objective
Run the biomarker-to-therapeutic-agent discovery pipeline for 8 chronic diseases and compile the results into a summary report. The pipeline queries DGIdb, Open Targets, PubMed, and Europe PMC for each gene target associated with each disease.

## Working directory
```
c:\Users\matth\OneDrive\Documents\OpenSourceMed\Opensource Medicine (1)\research-tracker\
```
All commands below are run from this directory.

---

## Step 1 — Install dependencies
```powershell
python -m pip install -r biomarker_pipeline/requirements.txt
```

## Step 2 — Verify the .env file exists
The file `research-tracker/.env` must contain at minimum:
```
NCBI_API_KEY=840aa1d841d0869ea10610dda7d8370e5708
```
If `ANTHROPIC_API_KEY` is also present, Stage 4 LLM extraction will run automatically.
If it is absent, Stage 4 is skipped — the pipeline still produces full DB + literature results.

## Step 3 — Run the full batch (all 8 diseases, 40 biomarkers)
```powershell
python -m biomarker_pipeline.run_for_diseases
```

To skip LLM extraction (faster, no Anthropic key needed):
```powershell
python -m biomarker_pipeline.run_for_diseases --skip-llm
```

To resume a partial run without re-fetching already-completed biomarkers:
```powershell
python -m biomarker_pipeline.run_for_diseases --skip-llm --skip-existing
```

---

## Diseases and their target biomarkers

| Disease | Gene targets (12–15 per disease) |
|---|---|
| Type 2 Diabetes | PPARG, GLP1R, DPP4, SLC5A2, INSR, IRS1, GCGR, FOXO1, PRKAA1, ADIPOQ, LEPR, SLC2A4 |
| Rheumatoid Arthritis | TNF, IL6, IL6R, IL1B, IL17A, JAK1, JAK2, JAK3, CD80, MS4A1, TNFSF11, MMP3, PTPN22 |
| Hypertension | ACE, AGTR1, AGTR2, REN, AGT, ADRB1, ADRB2, NOS3, CACNA1C, NR3C2, EDN1, NPR1, SLC12A3 |
| Major Depressive Disorder | SLC6A4, SLC6A2, SLC6A3, HTR2A, HTR1A, DRD2, MAOA, MAOB, GRIN2B, NTRK2, BDNF, FKBP5, CRH, IL6 |
| Epilepsy | SCN1A, SCN2A, SCN8A, KCNQ2, KCNQ3, KCNT1, GABRA1, GABRA2, GABRB3, SLC6A1, GRIN2A, GRIN2B, HCN1, MTOR |
| Hepatitis C | IFNL3, IFNL4, IFNAR1, DDX58, TLR3, MAVS, IRF3, STAT1, OAS1, MX1, IFIT1, PDCD1, HAVCR2, TGFB1 |
| Inflammatory Bowel Disease (Crohn's/UC) | TNF, IL12B, IL23A, IL23R, ITGA4, MADCAM1, JAK1, JAK2, TYK2, S1PR1, IL10, NOD2, ATG16L1, FOXP3 |
| Asthma | IL5, IL5RA, IL4, IL4R, IL13, IL13RA1, IL33, IL1RL1, TSLP, ADRB2, ALOX5, CYSLTR1, FCER1A, MS4A2, GATA3 |

---

## Step 4 — Run individual biomarkers (optional, for spot-checking)
```powershell
python -m biomarker_pipeline.run_pipeline --biomarker TNF --skip-llm
python -m biomarker_pipeline.run_pipeline --biomarker GLP1R --skip-llm
python -m biomarker_pipeline.run_pipeline --biomarker IL5 --skip-llm --output biomarker_pipeline/results/test/IL5.json
```

---

## Step 5 — Compile a summary report
After the batch run completes, run the following Python snippet to print a structured summary:

```python
import json, os, pathlib

results_dir = pathlib.Path("biomarker_pipeline/results/biomarkers")
summary = json.loads((results_dir / "run_summary.json").read_text())

for disease in summary:
    print(f"\n{'='*60}")
    print(f"Disease: {disease['disease']}")
    if "error" in disease:
        print(f"  ERROR: {disease['error']}")
        continue
    for bm in disease.get("biomarkers", []):
        if bm.get("skipped"):
            print(f"  {bm['biomarker']}: SKIPPED (existing)")
            continue
        if "error" in bm:
            print(f"  {bm['biomarker']}: FAILED — {bm['error']}")
            continue
        # Load the actual result file for agent breakdown
        path = pathlib.Path(bm["path"])
        if path.exists():
            data = json.loads(path.read_text())
            agents = data.get("agents", [])
            by_tier = {}
            for a in agents:
                by_tier.setdefault(a["evidence_tier"], []).append(a["agent_name"])
            tier_str = " | ".join(
                f"{t}: {len(by_tier[t])}"
                for t in ["clinical", "mechanistic", "correlative"]
                if t in by_tier
            )
            print(f"  {bm['biomarker']}: {len(agents)} agents  [{tier_str}]")
            # Show top 5 clinical or mechanistic agents
            top = by_tier.get("clinical", []) or by_tier.get("mechanistic", [])
            for name in top[:5]:
                print(f"    - {name}")
```

Save this as `biomarker_pipeline/print_summary.py` and run:
```powershell
python biomarker_pipeline/print_summary.py
```

---

## Expected outputs

- **Per-biomarker JSON**: `biomarker_pipeline/results/biomarkers/{disease-slug}/{GENE}.json`
  Each file contains `biomarker` (normalized identifiers), `agents` (list with name, direction, evidence tier, potency, sources), `coverage_notes`, and `generated_at`.

- **Run summary**: `biomarker_pipeline/results/biomarkers/run_summary.json`
  Lists every disease and biomarker processed, agent counts, and file paths.

- **Pipeline log**: `biomarker_pipeline/pipeline.log`
  Full per-stage log with API call details and timing.

---

## Error handling

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'tenacity'` | Dependencies not installed | Run Step 1 |
| `[OpenTargets] failed` with 400 | API schema changed | The query in `stage2_databases.py` uses `drugAndClinicalCandidates` — check the Open Targets schema if the error recurs |
| `[ChEMBL] failed` with 500 or timeout | ChEMBL API intermittent issue | Retry; results cached so previous successes are preserved |
| `[CTD] failed` with 302 | CTD batch endpoint redirect | CTD data is best-effort; pipeline continues without it |
| Stage 4 skipped | `ANTHROPIC_API_KEY` not in `.env` | Add the key to `.env` and re-run without `--skip-llm` |

---

## Data sources queried per biomarker

1. **Stage 1** — UniProt (canonical gene symbol, UniProt accession, Ensembl gene ID)
2. **Stage 2** — DGIdb GraphQL · Open Targets GraphQL · ChEMBL REST · CTD batch
3. **Stage 3** — PubMed E-utilities (esearch + efetch XML) · Europe PMC REST
4. **Stage 4** — Claude (claude-haiku-4-5) tool-use extraction from abstracts *(requires ANTHROPIC_API_KEY)*
5. **Stage 5** — Merge, deduplicate, rank by evidence tier → JSON output
