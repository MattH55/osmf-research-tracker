# HospitalCompare

Free, public web app for U.S. patients to compare **hospital quality** (CMS star ratings) and **shoppable procedure prices** by ZIP code.

> **Estimates only.** Verify with your hospital and insurer. Not medical advice. No PHI stored.

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
├── data/seed/          # Demo hospitals, procedures, prices, ZIP centroids
├── db/schema.sql       # PostgreSQL + PostGIS schema for production
├── etl/
│   ├── cms_quality.py  # CMS Provider Data importer (skeleton)
│   └── requirements.txt
└── src/
    ├── app/            # Next.js App Router pages & API
    ├── components/
    └── lib/            # Search, geo, formatting
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/procedures` | List searchable procedures |
| `GET /api/search?procedure=knee-replacement&zip=10016&radius=50` | JSON search results |

## Data pipeline (production)

1. **Quality** — Run `etl/cms_quality.py` against [data.cms.gov/provider-data](https://data.cms.gov/provider-data/) (quarterly).
2. **Prices** — Integrate [Turquoise Health API](https://turquoise.health) or parse hospital MRFs ([CMS HPT tools](https://github.com/CMSgov/hospital-price-transparency)).
3. **Load** — Upsert into PostgreSQL (`db/schema.sql`); add PostGIS geocoding for all ZIPs.
4. **Search** — Optional Meilisearch / Typesense for fuzzy procedure names.

## Environment variables (future)

```env
DATABASE_URL=postgresql://...
TURQUOISE_API_KEY=
GOOGLE_MAPS_API_KEY=
```

## Deploy

Optimized for [Vercel](https://vercel.com):

```bash
npm run build
```

## License

MIT — Open Source Medicine Foundation