# Configuration Guide

## Environment Variables

Copy `.env.example` to `.env` and set values as needed.

### Application

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment (development, staging, production) | development |
| `DEBUG` | Enable debug mode | false |
| `SECRET_KEY` | Secret for signing; **must change in production** | — |

### Database

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async URL, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | Redis URL for cache and Celery |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Neo4j connection |

### Celery

| Variable | Description |
|----------|-------------|
| `CELERY_BROKER_URL` | Broker URL (e.g. Redis) |
| `CELERY_RESULT_BACKEND` | Result backend URL |

### API Keys for Data Collectors

These are **optional** but required for full access to external cancer/omics APIs.

| Variable | Source | Purpose |
|----------|--------|---------|
| `COSMIC_API_KEY` | [COSMIC registration](https://cancer.sanger.ac.uk/cosmic/register) | Somatic mutations (email + key) |
| `COSMIC_EMAIL` | Same account | Used with COSMIC_API_KEY for Basic auth |
| `ONCOKB_API_TOKEN` | [OncoKB API Access](https://www.oncokb.org/apiAccess) | Variant annotation, treatment info |
| `DRUGBANK_API_KEY` | [DrugBank](https://go.drugbank.com/) | Drug/target data (license may apply) |
| `DEPMAP_API_KEY` | [DepMap Portal](https://depmap.org/portal/) | CCLE cell line data |
| `CBIOPORTAL_API_KEY` | [cBioPortal](https://www.cbioportal.org/) | Cancer genomics |
| `CIVIC_API_KEY` | [CIViC](https://civicdb.org/) | Clinical interpretations |
| `PHARMGKB_API_KEY` | [PharmGKB](https://www.pharmgkb.org/) | Pharmacogenomics |
| `STRING_API_KEY` | [STRING](https://string-db.org/) | Protein interactions |
| `TCIA_API_KEY` | [TCIA](https://www.cancerimagingarchive.net/) | Imaging |
| `NCBI_API_KEY` | [NCBI](https://www.ncbi.nlm.nih.gov/account/) | Entrez rate limits |
| `NCBI_EMAIL` | Your email | Required for NCBI |

### Frontend

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend base URL; leave empty to use dev proxy (`/api` → backend) |

### Bioinformatics tools (`/api/v1/tools`)

| Variable | Description | Default |
|----------|-------------|---------|
| `TOOLS_API_KEY` | If set, requests with matching `X-API-Key` header may use tools routes without JWT | empty |
| `TOOLS_ALLOW_ANONYMOUS` | Allow unauthenticated access to tools routes (**unsafe** in production) | `false` |
| `TOOLS_CHEMISTRY_RATE_LIMIT` | Max chemistry-tool requests per client IP per window (`0` = off) | `30` |
| `TOOLS_CHEMISTRY_RATE_PERIOD_SECONDS` | Sliding window length in seconds | `60` |
| `TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND` | `auto` (Redis when `REDIS_URL` works, else memory), `redis`, or `memory` | `auto` |
| `PIPELINE_ARTIFACTS_DIR` | Celery pipeline steps spill large JSON/GFF here when over the embed limit | `./data/pipeline_artifacts` |
| `PIPELINE_ARTIFACT_MAX_EMBED_BYTES` | Max serialized step result kept inline in `step_results` | `95000` |

Optional **Prodigal** executable: install [Prodigal](https://github.com/hyattpd/Prodigal) and add to `PATH`, then pass `use_prodigal_binary: true` in API bodies or Celery integration parameters. For heavy MD in production, extend `backend/computational_chemistry/external_md.py` (OpenMM / GROMACS notes).

## Setting API Keys

1. Copy `.env.example` to `.env`.
2. For each data source you need, sign up at the link above and obtain an API key or token.
3. Add the variable to `.env`, e.g.:
   ```bash
   COSMIC_EMAIL=your@email.com
   COSMIC_API_KEY=your-cosmic-key
   ONCOKB_API_TOKEN=your-oncokb-token
   ```
4. Restart the API and Celery workers so they pick up the new env.

Collectors will skip or limit results when keys are missing; see logs for messages like "API key not configured".
