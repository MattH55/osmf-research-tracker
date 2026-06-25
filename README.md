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

## Enabling GitHub Pages

1. Go to your repository **Settings → Pages**.
2. Under "Build and deployment":
   - **Source**: GitHub Actions (recommended)
3. The workflow file already contains a `deploy` job that uses the official `actions/deploy-pages` + artifact upload. No extra configuration is needed.
4. After the first successful run of the workflow, the site will be live at:
   - `https://<your-username>.github.io/research-tracker/`
   - Or, if using a custom domain like `opensourcemed.info`, configure the custom domain in the repo settings + add the appropriate `CNAME` file / DNS record pointing the `/research-tracker` subpath (or use a dedicated repo and custom path).

**Tip**: To host at exactly `https://opensourcemed.info/research-tracker/`, the main site can either:
- Submodule this repo
- Or serve the built static assets under a `/research-tracker/` folder from the main site repo.

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
