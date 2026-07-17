# MedFreedom data schemas

Machine-readable contracts for the arbitrage map. Human design notes live in  
`../../medical-freedom-arbitrage-schema.md`.

| File | Purpose |
|------|---------|
| [`therapy.schema.json`](./therapy.schema.json) | Therapy / procedure row axis |
| [`jurisdiction_regulation.schema.json`](./jurisdiction_regulation.schema.json) | Place + national/subnational regulation profile |
| [`access_cell.schema.json`](./access_cell.schema.json) | Therapy × jurisdiction join (legal status, pathway, clinics, setup) |

## Core idea

- **Therapy** answers *what is it?* (modality, diseases, evidence links, practitioner baseline).
- **Jurisdiction / regulation** answers *where and under which legal system?* (regulator, default psychedelic/cannabis/MAID posture, key statutes).
- **Access cell** answers *for this pair, is it allowed, offered, prohibited, or changing?*

**Prohibited is a first-class status.** Absence of a row is not the same as prohibited — empty means unresearched. Explicit `legal_status: Prohibited` + `access_pathway: None` + `legal_basis` citation is required for national bans.

## Validation

```bash
# optional: ajv-cli or check-jsonschema
check-jsonschema --schemafile schemas/therapy.schema.json path/to/therapy.json
```

Runtime API uses SQLAlchemy models in `backend/app/models.py` and Pydantic helpers in `backend/app/schemas.py`.
