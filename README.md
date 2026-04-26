# Multi-Omics Analysis Suite

A multi-omics analysis platform: FastAPI API (REST + GraphQL + WebSockets), Celery workers, PostgreSQL/Redis/Neo4j, a React (Vite) UI, and a large set of registered omics module types and bioinformatics libraries. **Package/classifiers: Beta** — not every listed capability is production-hardened end-to-end; depth varies by area.

## What is implemented today

- **API & jobs**: `backend/app` — auth, projects, analyses, `POST /api/v1/omics/modules/{module}/analyze` (Celery), GraphQL including `analysisProgress` (JWT on WebSocket in production), `/api/v1/tools` for gene annotation, structure/MD, docking, pipelines.
- **Omics modules**: 50+ `OmicsModuleBase` classes under `backend/omics/`; registration and discovery live in `backend/omics/base/registry.py` (see `OmicsRegistry.discover_and_register_modules`).
- **Domain libraries**: `backend/bioinformatics/`, `backend/assembly/`, `backend/alignment/`, `backend/computational_chemistry/`, `backend/single_cell`-related deps, `backend/data_collection/`, etc. — not all are wired to every API surface.
- **UI**: Vite + React 18, Tailwind — `npm run dev` in `frontend/`, dev server proxies `/api` and `/graphql` to the backend.
- **Dual UI model**: `frontend/` (React/Vite) is the primary product UI; `dashboards/` (Dash) is retained for analytics-heavy specialist views and experiments.
- **Ops**: `docker-compose.yml` (API, workers, DBs, Kafka, MinIO, Prometheus, Grafana, Jupyter, …), `infrastructure/kubernetes/`, `infrastructure/terraform/`, `infrastructure/helm/multi-omics-suite/`, `monitoring/`.
- **CI**: [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — `main` / `develop` — ruff, black, targeted mypy, pytest (unit + integration, with **continue-on-error** on the broad integration and property jobs), Vitest/frontend build, security scans.

## Technology stack

- **Backend**: Python 3.10+, FastAPI, Celery, Strawberry GraphQL, SQLAlchemy, Alembic, Redis, optional Kafka clients.
- **Databases / infra**: PostgreSQL, Redis, Neo4j; Docker Compose and Kubernetes/Helm/Terraform layouts in `infrastructure/`.
- **ML / scientific stack**: PyTorch, PyG, scikit-learn, XGBoost, scanpy/scvi/muon/squidpy, biopython, and others — see `pyproject.toml` dependencies.
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, TanStack Query, Zustand.

## Quick start

### Prerequisites

- Python 3.10+
- Docker (Compose v2 recommended) for databases and optional full stack
- Node.js 18+ for the frontend

### Backend (local Python)

```bash
git clone https://github.com/jbInf-08/multi_omics_analysis_suite.git
cd multi_omics_analysis_suite

python -m venv venv
# Linux/macOS:  source venv/bin/activate
# Windows:      .\venv\Scripts\activate

pip install -e ".[dev,notebooks,dash]"

# Copy and edit environment (defaults in backend Settings align with local Docker: Postgres on 5433 when using compose — see below)
copy .env.example .env   # Windows
# or: cp .env.example .env
```

**Match `DATABASE_URL` to how you run Postgres** — the backend default in code is `postgresql+asyncpg://omics:omics_secret@localhost:5433/omics_db` (port **5433** matches `docker-compose.yml`’s host mapping). The `.env.example` file may still show a different URL; for Compose-backed DBs, use user `omics`, password `omics_secret`, database `omics_db`, port `5433`.

```bash
# Start only what you need for dev, e.g.:
docker compose up -d postgres redis neo4j

alembic upgrade head
uvicorn backend.app.main:app --reload
```

- **OpenAPI**: http://localhost:8000/docs  
- **ReDoc**: http://localhost:8000/redoc  
- **GraphQL** (HTTP): http://localhost:8000/graphql  
- **GraphQL subscriptions** (`analysisProgress`) require a **Bearer JWT**. Over WebSocket (graphql-transport-ws), send `connection_init` with `connection_params` containing `Authorization: "Bearer <token>"`. When `DEBUG=false`, connections without a valid token are rejected at connect time.

### Full stack (Docker Compose)

```bash
docker compose up -d
# Then run migrations if the API image does not (local dev often runs alembic from the host)
alembic upgrade head
```

This starts the API, Celery worker/beat, Flower, Dash, frontend container, PostgreSQL, Redis, Neo4j, Kafka+ZooKeeper, MinIO, Prometheus, Grafana, Jupyter, etc. The frontend compose service uses `VITE_*` variables, while local `npm run dev` generally relies on the Vite proxy. For a production build, set `VITE_API_URL` when the UI must call an absolute API URL.

For a faster local bring-up with fewer services, use `docker-compose.minimal.yml` (API + PostgreSQL + Redis only):

```bash
docker compose -f docker-compose.minimal.yml up -d
```

### Using the CLI

The package installs two entry points: **`omics`** and **`moas`** (identical; Typer help name is `moas`).

```bash
# List registered omics modules (via discovery)
moas info

# Examples of implemented analyze subcommands (not “omics analyze genomics”)
moas analyze de <expression.csv> <metadata.csv> -o results/de
moas analyze pathway <gene_list> -o results/pathway
moas analyze qc <data.csv> -o results/qc
```

**Server-side** analysis (same path as the REST `POST` that queues Celery) — with API running and token from `POST /api/v1/auth/login`:

```bash
# Linux / macOS / Git Bash
export MOAS_API_BASE_URL=http://localhost:8000
export MOAS_API_TOKEN=<your_access_token>
moas api module-analyze single_cell clustering <project-uuid> --dataset-ids "" --parameters-json '{"k": 10}'

# Windows (cmd)
set MOAS_API_BASE_URL=http://localhost:8000
set MOAS_API_TOKEN=<your_access_token>
moas api module-analyze single_cell clustering <project-uuid> --dataset-ids "" --parameters-json "{\"k\": 10}"
```

`POST /api/v1/omics/modules/{module_name}/analyze` expects JSON with **`project_id`**, **`analysis_type`**, optional **`parameters`**, optional **`dataset_ids`**. Response is **201** with the Analysis resource (id, `celery_task_id`, status, etc.).

### API — bioinformatics tools (`/api/v1/tools`)

Use a normal **Bearer JWT** or, for automation, **`X-API-Key`** if `TOOLS_API_KEY` is set, or `TOOLS_ALLOW_ANONYMOUS=true` **only in local dev**. Chemistry routes share Redis-backed rate limits when `REDIS_URL` is available — see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

Quick manual check:

1. Run API and frontend: `uvicorn …`, `cd frontend && npm run dev` — **Tools** page: http://localhost:3000/tools (Vite proxies `/api` to :8000).
2. **CI** runs `tests/integration/test_bioinformatics_tools_api.py` and `tests/integration/test_omics_analyze_api.py` on every push/PR to `main` and `develop`.

### Configuration and API keys

Copy `.env.example` to `.env`. Full variable notes: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

### Testing

```bash
pytest tests/unit -v
pytest tests/integration -v
pytest tests/property -v
pytest tests/unit tests/integration -v
```

`pyproject.toml` adds default coverage to pytest; narrow runs may use `pytest ... --no-cov`.

**Frontend** (from `frontend/`):

```bash
npm ci
npm test
npm run build
```

## Repository layout

```
multi_omics_analysis_suite/
├── backend/                 # FastAPI app, omics modules, bioinformatics, ML, pipelines, collectors
│   ├── app/                 # API, tasks, models, core config
│   ├── omics/                # OmicsModuleBase implementations + registry
│   ├── bioinformatics/       # Sequences, parsers, alignment helpers, …
│   ├── assembly/, alignment/, computational_chemistry/, …
│   ├── data_collection/      # Public data collectors
│   └── …
├── cli/                      # Typer CLI (moas / omics)
├── frontend/                 # Vite + React
├── dashboards/              # Dash apps
├── docker/                  # Dockerfiles
├── infrastructure/
│   ├── kubernetes/            # Example manifests
│   ├── helm/multi-omics-suite/   # Helm chart
│   └── terraform/            # Cloud IaC
├── monitoring/               # Prometheus/Grafana as used by Compose
├── notebooks/
├── tests/                    # unit, integration, property, snapshot
├── alembic/
└── docs/                     # e.g. CONFIGURATION.md
```

## Architecture (omics modules)

Each omics type is a class extending `OmicsModuleBase` (`backend/omics/base/omics_base.py`) with `load_data`, `preprocess`, `quality_control`, `normalize`, `analyze`, `visualize`, `get_available_pipelines`, and `get_available_analyses`. The registry batches concrete module instances in `OmicsRegistry.discover_and_register_modules`.

## Deployment

**Kubernetes** (examples in-repo):

```bash
kubectl apply -f infrastructure/kubernetes/namespace.yaml
# Apply other manifests as appropriate for your cluster
# Helm: chart under infrastructure/helm/multi-omics-suite/
```

**Helm** (name/version in `infrastructure/helm/multi-omics-suite/Chart.yaml`):

```bash
helm install multi-omics infrastructure/helm/multi-omics-suite
```

**Terraform**: `infrastructure/terraform/`

## Data collectors

`backend/data_collection` includes clients for many public resources; some require API keys. Collectors may skip or throttle when keys are missing.

## Example imports (core libraries)

```python
from backend.bioinformatics import DNASequence, GlobalAligner, FastaParser
from backend.assembly import DeBruijnAssembler, AssemblyQC
from backend.computational_chemistry import Molecule, MolecularDocking
from backend.systems_biology import ODEModel, SteadyStateAnalysis
```

Adjust imports to the actual public API of each submodule; see package `__init__.py` files.

## ML / multi-omics

Shared dependencies support deep learning, GNNs, traditional ML, and integrative analyses; implementation is spread across `backend/ml/`, `backend/omics/integration/`, and app-layer tasks. Treat feature depth as **module-specific**.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Default integration branch in workflow docs is **`develop`**.

## License

MIT License — see [LICENSE](LICENSE).

## Citation

If you use this software in your research, please cite:

```bibtex
@software{multi_omics_suite,
  title={Multi-Omics Analysis Suite},
  author={Boyer, Juan Valentin},
  year={2026},
  url={https://github.com/jbInf-08/multi_omics_analysis_suite}
}
```
