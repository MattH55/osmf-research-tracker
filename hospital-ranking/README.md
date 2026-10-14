# HospitalCompare

Free, public web app for U.S. patients to compare **hospital quality** (CMS star ratings) and **shoppable procedure prices** by ZIP code.

> **Hospital-published prices only; nothing is estimated.** Verify with your hospital and insurer. Not medical advice. No PHI stored.

## MVP features (Phase 1)

- Search by plain-language procedure + ZIP / radius
- Results ranked by distance, price, or quality
- Filters: CMS stars, max price, insurance type (cash / PPO / HDHP)
- Hospital detail pages with ratings breakdown and price tables
- Links to hospital shoppable / price transparency pages
- Mobile-first, accessible UI with disclaimers on every flow

## Quick start

```bash
cd hospital-ranking
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

**Try:** Knee replacement near `10016` (NYC), colonoscopy near `77030` (Houston).

## Project layout

```
hospital-ranking/
├── data/seed/procedures.json  # Procedures and their billing codes (with code sources)
├── data/cms/                  # Real data the app loads: hospitals, ZIP points, prices, quarantine
├── etl/
│   ├── build_dataset.py       # CMS hospitals + Census ZIP points + Census address geocoding
│   ├── ingest_trilliant.py    # Prices from Trilliant ORIA parsed hospital price files
│   ├── ingest_mrf_prices.py   # Prices from hospitals' own price files
│   └── priceos_validate.py    # Data contract validation (runs before every build)
├── tests/                     # node --test: pricing rules + real-data integrity checks
└── src/
    ├── app/                   # Next.js App Router pages & API
    ├── components/
    └── lib/                   # Data loading, search, geo, price labelling
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/procedures` | List searchable procedures |
| `GET /api/search?procedure=knee-replacement&zip=10016&radius=50` | JSON search results |

## Data pipeline

1. **Hospitals and locations:** `python etl/build_dataset.py` (CMS Hospital General Information,
   with its CMS release date as the vintage; Census Gazetteer ZIP points; Census address geocoding).
   Use `--regeocode` to refresh locations only.
2. **Prices:** `npm run ingest:trilliant` / `npm run ingest:prices`. Only hospital-published
   figures with an explicit code system, a single scope per procedure, a source date and a
   matched hospital are kept; everything else goes to `data/cms/quarantine.json` with a reason.
3. **Validate:** `npm run validate:data` (also runs automatically before `npm run build`).

## Environment variables (future)

```env
DATABASE_URL=postgresql://...
TURQUOISE_API_KEY=
GOOGLE_MAPS_API_KEY=
```

## Deploy (Vercel)

Production: **https://hospital-ranking.vercel.app**, served from the domain root (no `basePath`).
The project lives in the **research-tracker** monorepo with Root Directory `hospital-ranking`.

```bash
cd hospital-ranking
npx vercel link
npx vercel --prod
```

`npm run build` first runs the real-data integrity tests (`prebuild`, Node only, so it also
runs on Vercel), so a dataset that breaks the price contract cannot be deployed. After
regenerating data, also run the full schema validator: `npm run validate:data` (needs
`pip install jsonschema`).

Serving it under a sub-path such as opensourcemed.info/hospital-ranking would need
`basePath` restored in `next.config.ts`; a plain rewrite to the root deployment breaks
asset URLs.

## License

MIT — Open Source Medicine Foundation