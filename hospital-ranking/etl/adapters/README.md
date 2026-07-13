# International Facility Adapters

Adapters extract price observations from international healthcare facility websites.

Each adapter:
1. **Fetches** raw HTML documents from facility website
2. **Caches** raw content with SHA256 hash (for reproducibility and dispute resolution)
3. **Extracts** structured price observations with LLM or regex
4. **Maps** facility's bundle format to canonical bundles
5. **Respects** robots.txt and rate-limits to ≤1 req/30s

---

## Directory Structure

```
etl/adapters/
├── __init__.py                          # Package exports
├── base.py                              # FacilityAdapter abstract base class
├── hospital_angeles_mexico_v1.py        # Example: Hospital Ángeles (Mexico)
└── README.md                            # This file

data/adapters/
├── cache/                               # Raw cached documents
│   ├── intl-hospital-angeles-mx-01/
│   │   ├── sha256_hash.html             # Raw HTML
│   │   └── sha256_hash.jsonl            # Metadata
│   └── intl-clinic-xyz-th-01/
│       └── ...
└── facility_registry.json               # Global facility index
```

---

## Running Adapters

### List available adapters
```bash
python etl/run_adapters.py --list
```

### Run a single adapter (dry-run, no write)
```bash
python etl/run_adapters.py --adapter hospital_angeles_mexico_v1 --dry-run
```

### Run and write to observation store
```bash
python etl/run_adapters.py --adapter hospital_angeles_mexico_v1
```

Output goes to `data/observations/intl-{facility_id}.jsonl`

---

## How to Add a New Adapter

### 1. Create the adapter file

```python
# etl/adapters/clinic_xyz_thailand_v1.py

from .base import FacilityAdapter, RawDocument, PriceObservation

class ClinicXyzThailandV1(FacilityAdapter):
    
    def __init__(self):
        self.facility_id = "intl-clinic-xyz-th-01"
        self.facility_name = "Clinic XYZ - Bangkok"
        self.country = "TH"
        self.city = "Bangkok"
        self.source_url = "https://clinicxyz.th"
        self.robots_url = "https://clinicxyz.th/robots.txt"
        super().__init__()
    
    def fetch(self) -> list[RawDocument]:
        """Fetch pricing pages."""
        docs = []
        # 1. Check robots.txt with self.can_fetch(url)
        # 2. Fetch with self.fetch_url(url) (handles retries, rate-limiting)
        # 3. Cache with self.cache_document(doc)
        # 4. Return list of RawDocument
        return docs
    
    def extract(self, docs: list[RawDocument]) -> list[PriceObservation]:
        """Extract prices from documents."""
        observations = []
        for doc in docs:
            content = self.load_document(doc.content_hash)  # or doc.content
            # Parse HTML/PDF, extract prices
            # Create PriceObservation for each price
            # Set bundle.includes, bundle.completeness_score
        return observations
```

### 2. Register the adapter

```python
# etl/adapters/__init__.py

from .clinic_xyz_thailand_v1 import ClinicXyzThailandV1

ADAPTER_CLASSES = {
    "clinic_xyz_thailand_v1": ClinicXyzThailandV1,
}
```

### 3. Test it

```bash
python etl/run_adapters.py --adapter clinic_xyz_thailand_v1 --dry-run
```

### 4. Run and validate

```bash
python etl/run_adapters.py --adapter clinic_xyz_thailand_v1
python etl/priceos_validate.py --report text
```

---

## Design Principles

### Raw Document Caching

Every raw HTML/PDF is cached alongside its SHA256 hash:

```
data/adapters/cache/intl-hospital-angeles-mx-01/
├── a7f3d91e2c....html     (raw cached HTML)
└── a7f3d91e2c....jsonl    (metadata: URL, retrieved_at, content_type)
```

This allows:
- **Reproducibility**: Same document → same hash → same extract
- **Audit trail**: "Here's the page as we saw it on 2026-07-12"
- **Dispute resolution**: "You changed your prices after we scraped"

Hash is computed over full HTML content (after decompression).

### LLM-Assisted Extraction

When parsing unstructured HTML (e.g., "Knee replacement package includes: surgery, 2-night stay, airport transfer. $13,500"), use LLM to:

1. Parse bundle components and prices
2. Set `extracted_by: "llm_extraction"` in provenance
3. Set `confidence: 0.75` if uncertain
4. Flag low-confidence extractions (< 0.8) for human review in `review/pending/`

Example:
```json
{
  "provenance": {
    "extracted_by": "llm_extraction",
    "confidence": 0.75,
    "llm_prompt": "Extract knee replacement price and components from: ...",
    "llm_model": "claude-opus-4"
  }
}
```

### Bundle Mapping

Map facility's described bundle to canonical bundle:

```
Facility says:     Canonical bundle
"Surgery"    →     ["surgeon_fee", "facility_fee"]
"Implant"    →     ["implant_device"]
"Stay"       →     ["inpatient_nights"]
"PT"         →     ["post_op_physio"]

Completeness = Σ weight(c) for c in observed = 0.20 + 0.45 + 0.15 + 0.04 = 0.84
```

### Rate-Limiting & Robots.txt

The adapter framework enforces:

1. **Check robots.txt before each request** (`adapter.can_fetch(url)`)
2. **Rate-limit to 1 request per 30 seconds** (sleeps between requests)
3. **Retry with exponential backoff** on network errors
4. **Identify honestly** in User-Agent: `OpenSourceMed-PriceOS/1.0 (+https://opensourcemed.info)`

Never:
- Submit contact/inquiry forms
- Create fake patient accounts
- Bypass robots.txt
- Flood servers

### Confidence & Staleness

Every price observation carries:

```json
{
  "provenance": {
    "confidence": 0.9,      // 0.0–1.0; <0.8 flagged for review
    "extracted_by": "adapter:hospital_angeles_v1"
  },
  "observation_date": "2026-07-12",  // When price was valid
  "stale": false           // Marked true if >18 months old
}
```

---

## Example: Hospital Ángeles (Mexico)

`hospital_angeles_mexico_v1.py` demonstrates:

- ✅ Fetching multiple pricing pages
- ✅ Regex extraction of prices from HTML
- ✅ Mapping to canonical bundles (TKA, sleeve, cataract)
- ✅ Setting completeness scores (0.70–0.90)
- ✅ Flagging "from $X" as advertised minimums
- ✅ Caching raw documents

To run:
```bash
python etl/run_adapters.py --adapter hospital_angeles_mexico_v1
```

Output: `data/observations/intl-hospital-angeles-mx-01.jsonl`

---

## Adapters Roadmap

### Phase 1 (Pilot)
- [ ] Hospital Ángeles (Mexico) — *done*
- [ ] CIMA San José (Costa Rica)

### Phase 2 (Expansion)
- [ ] Samitivej Hospital (Thailand)
- [ ] Apollo Hospitals (India)
- [ ] American Hospital (Turkey)

### Phase 3 (Structured Data)
- [ ] Adapters for facilities with public APIs
- [ ] JSON-based pricing feeds (vs. HTML scraping)

---

## Disclosure Form Alternative

The brief also mentions a **disclosure form** path: facilities fill in pricing voluntarily.

This could be:
1. Web form (`disclosure/form.html`)
2. Google Forms integration
3. Email template

**NOT IMPLEMENTED YET** — adapters cover the "scrape public websites" path. Disclosure forms are additive (lower-effort path for willing facilities).

---

## Testing & Validation

After running adapters, validate:

```bash
python etl/priceos_validate.py --report text
```

Checks:
- Schema conformance (all observations valid JSON Schema)
- Staleness (flags observations >18 months old)
- FX sanity (fx_rate matches computed USD)
- Completeness scores (make sense relative to bundle)
- Orphaned FKs (facility_id must exist in facility registry)

Example expected output:
```
Total observations: 45 (intl) + 11,340 (US) = 11,385
Valid: 11,385
Schema errors: 0
Data quality issues: 3
Stale: 0

Observations by source:
  trilliant_mrf: 11,326
  hospital_mrf: 14
  clinic_website: 45

Completeness scores: min=0.70, max=0.95, mean=0.82
```

---

## Ethical Guidelines

From the brief (§8):

> **Do not submit inquiry forms, do not request quotes under a patient persona, do not create fake patient accounts.** Not a performance concern — a credibility one.

This system:
- ✅ Scrapes public website content (allowed by robots.txt)
- ✅ Caches documents for transparency
- ✅ Attributes all sources
- ❌ Does NOT impersonate patients
- ❌ Does NOT create fake accounts
- ❌ Does NOT circumvent robots.txt

If a facility's site doesn't publish pricing publicly, we don't ingest it (yet). The disclosure form path allows opt-in instead.

---

## Troubleshooting

### Adapter returns no observations
- Check `robots.txt` — facility may disallow scraping
- Check `fetch()` — URLs may be wrong or pricing page structure changed
- Look at cached documents in `data/adapters/cache/{facility_id}/`

### "robots.txt disallows" message
- Facility's `robots.txt` blocks scraping — respect it
- Advocate for disclosure form instead (opt-in path)

### Completeness score seems wrong
- Verify bundle mapping in `extract()` method
- Check canonical bundle weights in `ontology/canonical_bundles/`
- Ensure `bundle.includes` lists only what facility explicitly stated

### Low confidence extractions (< 0.8)
- LLM may be uncertain about bundle components
- Flag for human review in `review/pending/`
- Consider manual override if reviewer confirms
