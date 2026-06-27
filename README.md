# Research Tracker

Automated daily-updating research feed for the **Open Source Medicine Foundation** (opensourcemed.info).

Live at: **https://opensourcemed.info/research-tracker/**

Tracks peer-reviewed PubMed studies on post-viral and chronic complex conditions using clean, transparent, professional pages.

## Conditions Tracked

| Page | Condition |
|------|-----------|
| [pacvs.html](pacvs.html) | PACVS – Post-Acute COVID-19 Vaccination Syndrome |
| [me-cfs.html](me-cfs.html) | ME/CFS – Myalgic Encephalomyelitis / Chronic Fatigue Syndrome |
| [long-covid.html](long-covid.html) | Long COVID – Post-Acute Sequelae of COVID-19 (PASC) |
| [lyme.html](lyme.html) | Chronic Lyme / PTLDS – Post-Treatment Lyme Disease Syndrome |
| [gulf-war-illness.html](gulf-war-illness.html) | Gulf War Illness (GWI) |
| [other-post-viral.html](other-post-viral.html) | Other Post-Viral & Post-Infectious Syndromes (non-COVID) |

## Repository Structure

```
research-tracker/
├── .github/workflows/
│   └── daily-research-update.yml     # GitHub Action for daily PubMed fetch + deploy
├── data/
│   ├── pacvs.json
│   ├── me-cfs.json
│   ├── long-covid.json
│   ├── lyme.json
│   ├── gulf-war-illness.json
│   └── other-post-viral.json
├── index.html                        # Main hub page with cards
├── pacvs.html
├── me-cfs.html
├── long-covid.html
├── lyme.html
├── gulf-war-illness.html
├── other-post-viral.html
├── update_research_tracker.py        # Python script (uses pymed)
└── README.md
```

## How It Works

1. **Python updater** (`update_research_tracker.py`):
   - Uses the `pymed` library to query the PubMed E-utilities API.
   - Runs a targeted query for each condition.
   - Normalizes results (title, date, journal, authors, abstract excerpt, direct PMID link).
   - Saves structured JSON into `data/`.

2. **Frontend**:
   - Pure static HTML + Tailwind CSS (CDN) + Font Awesome.
   - Each condition page loads its own JSON via `fetch()`.
   - Client-side search/filter across title / authors / journal / abstract.
   - Full abstract toggle + direct PubMed links.
   - Responsive + accessible.

3. **Automation**:
   - GitHub Actions runs the script once per day (`cron`).
   - Commits new `data/*.json` files back to the repo.
   - Deploys the entire site (HTML + data) to GitHub Pages.

## Local Development

```bash
# Clone
git clone https://github.com/YOUR_ORG/research-tracker.git
cd research-tracker

# Install Python deps
python -m pip install pymed

# Run the updater (overwrites data/*.json)
python update_research_tracker.py

# Serve locally (any static server)
python -m http.server 8000
# Open http://localhost:8000
```

## Deploying to GitHub Pages (Recommended)

This is a **pure static site** (HTML + CSS + JS + JSON). It works great on GitHub Pages with zero build step.

### Easiest Method (Deploy from Branch)

1. Make sure everything is committed and pushed:
   - All `.html` files in the root
   - `tracker.css`
   - The entire `data/` folder (including `therapeutic_agents.json`)
   - The `clinical_trials/data/clinical_trials_current.json` file

2. Go to your GitHub repository → **Settings → Pages**.

3. Under "Build and deployment":
   - **Source**: select **Deploy from a branch**
   - **Branch**: `main` (or `master`)
   - **Folder**: `/ (root)`
   - Click **Save**

4. GitHub will publish the site. It usually takes 30–60 seconds.

5. Your site will be live at:
   ```
   https://<your-username>.github.io/<repo-name>/
   ```
   Example: `https://matth.github.io/research-tracker/`

### Using GitHub Actions (Advanced)

If you already have a workflow that builds and deploys (see `.github/workflows/`), you can set Source to **GitHub Actions** instead. The Actions method is useful if you want to run the daily PubMed updater + deploy in one pipeline.

### Important Notes for This Project

- All `fetch()` calls use relative paths (`./data/...`, `./clinical_trials/data/...`). These work automatically on GitHub Pages.
- Links between `index.html` ↔ `agents.html` ↔ `clinical_trials.html` are relative → they work at any subpath.
- The `-local.html` files (agents-local.html, clinical_trials-local.html) are for offline/local double-click use only. You can keep them in the repo or add them to `.gitignore`.
- If deploying under a subfolder (e.g. `https://example.com/research-tracker/`), relative links still work fine.

### Custom Domain (e.g. opensourcemed.info)

1. In repo Settings → Pages, add your custom domain.
2. Create a `CNAME` file in the root of the repo containing your domain.
3. Configure DNS (usually a CNAME record pointing to `<username>.github.io`).
4. For a subpath like `/research-tracker/`, you may need to handle routing on the main site or use a dedicated Pages repo.

After deploying, the therapeutic agents page and clinical trials page should load their JSON data instantly over HTTPS. No local server required.

## Customization

- **Queries**: Edit the `CONDITIONS` dictionary inside `update_research_tracker.py`. Queries use standard PubMed syntax.
- **Result count**: Change `MAX_RESULTS`.
- **Branding / Styling**: The Tailwind CDN script + inline styles are self-contained in each HTML file. Update colors or logo block centrally if you extract a shared partial later.
- **Email / Tool name**: Change `PUBMED_TOOL` and `PUBMED_EMAIL` (recommended for production use).

## Disclaimers (present on every page)

> This is an **automated** feed of peer-reviewed studies pulled from PubMed.  
> It is provided for informational and research purposes only.  
> **Not medical advice.** Always consult a qualified healthcare professional.

All pages include clear attribution: "Data sourced from PubMed / NCBI".

## Future Improvements (Ideas)

- **LLM-generated short summaries** of abstracts (opt-in, with strong disclaimers).
- Add **RSS / Atom feeds** per condition (or a combined feed).
- **Post-EBV / other specific post-viral** pages (e.g. EBV, CMV, etc.).
- Better deduplication + historical archive (store all ever seen studies, not just latest N).
- Date-range filters + journal filters on the frontend.
- Add **citation export** (BibTeX, RIS) buttons.
- Weekly / monthly digest email via GitHub Actions + external service.
- Integrate with a lightweight backend (e.g. Cloudflare Workers) for faster search.
- Add study counts + sparklines showing publication volume over time.
- Link each condition card to a page on opensourcemed.info with foundation context.

## License & Attribution

- Code in this repository: Open source (recommend Apache 2.0 or MIT).
- All study data: Public domain / openly licensed via PubMed (NCBI/NLM). Cite PubMed records when using.

## Support the Work

The Open Source Medicine Foundation builds open evidence for underserved chronic conditions.

Visit: [https://opensourcemed.info](https://opensourcemed.info)

---

**Built with ❤️ for patients and researchers by the Open Source Medicine Foundation.**

## Modules

### 1. Research Tracker (Literature)
- Daily PubMed updates for PACVS, Long COVID, ME/CFS, etc.
- See update_research_tracker.py and HTML pages.

### 2. Clinical Trials Card Agent (New)
- Weekly extraction of interventional trials
- Therapeutic agent identification
- Structured Markdown cards + change detection
- Location: clinical_trials/
- Run with: python clinical_trials/clinical_trials_agent.py
- See clinical_trials/README.md for details
