# Configuration Guide

## Environment file

Copy `.env.example` to `.env` and set values. The **authoritative** names and defaults for the application are `pydantic-settings` fields in `backend/app/core/config.py` (plus any keys read only in other modules, e.g. data collectors). If `.env.example` disagrees with `config.py` on a variable, **trust `config.py`** and update your `.env` to match the code you are running.

### Application

| Variable | Description | Default in code (see `Settings`) |
|----------|-------------|----------------------------------|
| `APP_NAME` | Display name | `Multi-Omics Analysis Suite` |
| `APP_VERSION` | Version string | `1.0.0` |
| `DEBUG` | Debug mode (affects e.g. GraphQL subscription auth) | `false` |
| `ENVIRONMENT` | e.g. development, staging, production | `development` |
| `SECRET_KEY` | Signing/secret; **change in production** | dev placeholder string |

> **Note:** Some earlier docs referred to `APP_ENV`; the runtime uses **`ENVIRONMENT`**.

### Database and services

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | Async PostgreSQL URL, e.g. `postgresql+asyncpg://user:pass@host:port/db` |
| `REDIS_URL` | Redis (cache, Celery, optional tools rate limit) |
| `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Graph database (see `config.py`) |
| `CELERY_BROKER_URL` | Celery broker (e.g. Redis) |
| `CELERY_RESULT_BACKEND` | Celery results |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka clients (default `localhost:9092`) |

**Local + Docker Compose:** the compose file maps PostgreSQL to host port **5433** to avoid clashing with a local Postgres. The app default in `config.py` uses that port and user `omics` / DB `omics_db` when you follow the default compose credentials.

**MinIO** (S3-compatible; defaults in `config.py`): `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `MINIO_SECURE`.

### API keys for data collectors

These are **optional**; without them, collectors may skip or limit calls.

| Variable | Source (overview) | Purpose |
|----------|------------------|---------|
| `COSMIC_API_KEY` + `COSMIC_EMAIL` | [COSMIC](https://cancer.sanger.ac.uk/cosmic/register) | Somatic mutations |
| `ONCOKB_API_TOKEN` | [OncoKB](https://www.oncokb.org/apiAccess) | Variant / therapy |
| `DRUGBANK_API_KEY` | [DrugBank](https://go.drugbank.com/) | Drug data (license may apply) |
| `DEPMAP_API_KEY` | [DepMap](https://depmap.org/portal/) | CCLE / DepMap |
| `CBIOPORTAL_API_KEY` | [cBioPortal](https://www.cbioportal.org/) | Cancer genomics |
| `CIVIC_API_KEY` | [CIViC](https://civicdb.org/) | Clinical interpretations |
| `PHARMGKB_API_KEY` | [PharmGKB](https://www.pharmgkb.org/) | Pharmacogenomics |
| `STRING_API_KEY` | [STRING](https://string-db.org/) | Protein interactions |
| `TCIA_API_KEY` | [TCIA](https://www.cancerimagingarchive.net/) | Imaging |
| `NCBI_API_KEY` | [NCBI](https://www.ncbi.nlm.nih.gov/account/) | Entrez rate limits |
| `NCBI_EMAIL` | — | Good practice for Entrez |

### Frontend (Vite)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | If set, used as the API origin prefix. If **empty** (dev default), the client uses relative `/api/v1` and the Vite dev server proxy. See `frontend/src/lib/api.ts`. |

### Bioinformatics tools (`/api/v1/tools`)

| Variable | Description | Default |
|----------|-------------|---------|
| `TOOLS_API_KEY` | If set, `X-API-Key` with the same value can authenticate tools routes | empty |
| `TOOLS_ALLOW_ANONYMOUS` | Allow unauthenticated access to tools routes (**not for production**) | `false` |
| `TOOLS_CHEMISTRY_RATE_LIMIT` | Max chemistry-tool requests per client IP per window (`0` = off) | `30` |
| `TOOLS_CHEMISTRY_RATE_PERIOD_SECONDS` | Sliding window (seconds) | `60` |
| `TOOLS_CHEMISTRY_RATE_LIMIT_BACKEND` | `auto` (Redis when `REDIS_URL` works, else memory), `redis`, or `memory` | `auto` |
| `PIPELINE_ARTIFACTS_DIR` | Large pipeline JSON/GFF spillover directory | `./data/pipeline_artifacts` |
| `PIPELINE_ARTIFACT_MAX_EMBED_BYTES` | Max inline `step_results` size | `95000` |

Optional **Prodigal** binary: install [Prodigal](https://github.com/hyattpd/Prodigal) and add to `PATH`, then pass `use_prodigal_binary: true` in request bodies or Celery parameters. For production MD, see `backend/computational_chemistry/external_md.py` and extend with OpenMM / GROMACS as needed.

## Setting API keys

1. Copy `.env.example` to `.env`.
2. For each data source, register and obtain a key or token.
3. Add the variables to `.env` and restart the API and Celery workers.

Watch logs for messages like “API key not configured” when collectors run without keys.
