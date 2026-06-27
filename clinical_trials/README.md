# Clinical Trials Card Agent

Weekly automated extractor of interventional clinical trials for:

- PACVS (Post-Acute COVID-19 Vaccination Syndrome)
- Long COVID / PASC
- ME/CFS

## Purpose

This agent is the first module in the Open Source Medicine Foundation's therapeutic evidence tracker. It identifies trials testing specific therapeutic agents and presents them as clean, structured cards.

## Quick Start

```bash
cd clinical_trials
pip install -r ../requirements.txt
python clinical_trials_agent.py
```

This will:
1. Query ClinicalTrials.gov for relevant interventional trials
2. Extract and normalize therapeutic agents
3. Generate a weekly Markdown report in `reports/`
4. Save structured JSON in `data/`
5. Perform change detection (new / updated trials)

## Output

- `reports/latest.md` — Always-up-to-date weekly report
- `reports/weekly_report_YYYY-MM-DD.md` — Archived weekly reports
- `data/clinical_trials_current.json` — Structured data
- `data/trials_state.json` — Previous run state (for diffs)

## LLM Enhancement (Optional but Recommended)

The `llm_prompts.py` file contains high-quality prompts you can use with Grok, Claude, or GPT to improve agent extraction and tagging.

Example usage with an LLM API:
```python
from llm_prompts import SYSTEM_PROMPT, get_extraction_prompt

prompt = get_extraction_prompt(...)
# Send to your LLM with SYSTEM_PROMPT
```

## Scheduling

**Recommended:** GitHub Actions (weekly)

A ready-to-use GitHub Actions workflow has been added at:
`.github/workflows/clinical-trials-weekly.yml`

It runs every Monday, executes the agent, and commits updates to reports + data. You can also trigger it manually from the Actions tab.

## Success Criteria (MVP)

- Pulls relevant interventional trials for the target conditions
- Clearly extracts therapeutic agents
- Produces readable Markdown cards
- Detects new and updated trials
- Runs reliably on a schedule

## Future Work

- Integration with PubMed literature agent
- Web dashboard or Notion sync
- Multi-registry support (EU CTR, WHO ICTRP)
- Better agent normalization using embeddings

---

Built for the Open Source Medicine Foundation.
