# Contributing to Multi-Omics Analysis Suite

Thank you for your interest in contributing. This document describes how to work on the repository in its **current** layout and tooling.

## Code of Conduct

By participating, you agree to be respectful and constructive. There is no separate `CODE_OF_CONDUCT.md` in this repo; follow standard open-source collaboration norms when interacting in issues and pull requests.

## Getting started

### Prerequisites

- Python 3.10+ (3.10–3.12 are exercised in CI)
- Node.js 18+
- Docker and Docker Compose (optional but used for local Postgres, Redis, Neo4j, etc.)
- Git

### Development environment

1. **Clone the repository** (use your fork URL if you forked on GitHub):

   ```bash
   git clone https://github.com/jbInf-08/multi_omics_analysis_suite.git
   cd multi_omics_analysis_suite
   ```

2. **Create a virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/macOS
   # or
   .\venv\Scripts\activate    # Windows
   ```

3. **Install the package in editable mode:**

   ```bash
   pip install -e ".[dev,notebooks,dash]"
   ```

4. **Pre-commit (optional, matches CI style checks locally):**

   ```bash
   pip install pre-commit
   pre-commit install
   ```

5. **Configuration:** copy `.env.example` to `.env` and set variables. The backend’s default `DATABASE_URL` in `backend/app/core/config.py` is aligned with **docker-compose** PostgreSQL (host port **5433**, user `omics`, DB `omics_db`). If you use a different database, set `DATABASE_URL` accordingly.

6. **Start dependencies** (typical local dev: only the services you need):

   ```bash
   docker compose up -d postgres redis neo4j
   ```

7. **Migrations:**

   ```bash
   alembic upgrade head
   ```

8. **Run the API:**

   ```bash
   uvicorn backend.app.main:app --reload
   ```

9. **Frontend (optional):** from `frontend/`, `npm ci` and `npm run dev`. The Vite config proxies `/api` and `/graphql` to `http://localhost:8000`. For production builds, you can set `VITE_API_URL` (see `frontend/src/lib/api.ts`).

## Development workflow

### Branches and PRs

CI runs on **push and pull request** to **`main`** and **`develop`**. For new work, use **`develop`** as the base branch if it exists in your remote:

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature
```

If your workflow only has `main`, branch from `main` instead.

### Branch naming (convention)

- `feature/` — new features
- `fix/` — bug fixes
- `docs/` — documentation
- `refactor/`, `test/`, `chore/` — as needed

### Commits

[Conventional Commits](https://www.conventionalcommits.org/) are encouraged, e.g. `feat(api): add endpoint`, `fix(cli): handle missing token`.

### Before opening a PR

- Run `pytest tests/unit` at minimum; integration tests need Postgres/Redis (see `tests/integration/conftest.py` and GitHub Actions env).
- Run or rely on CI for `black`, `ruff`, and the subset of `mypy` in `.github/workflows/ci.yml`.

## Code standards

- **Python:** PEP 8, type hints where practical, line length 100 (Black/ Ruff in repo config).
- **TypeScript / React:** functional components, hooks; Tailwind for layout.

## Adding or extending omics modules

1. **Add a new package** under `backend/omics/…` (e.g. `backend/omics/specialized/my_omics/`) with a class extending `OmicsModuleBase` in `backend/omics/base/omics_base.py` — use existing modules (e.g. `backend/omics/core/genomics.py`) as a template. Implement the abstract methods (`name`, `category`, `description`, `load_data`, `preprocess`, `quality_control`, `normalize`, `analyze`, `visualize`, `get_available_pipelines`, `get_available_analyses`).

2. **Register the module** by importing the class in `backend/omics/base/registry.py` inside `OmicsRegistry.discover_and_register_modules` and appending an instance to the appropriate list (core, modification, interaction, clinical, or specialized) so it is passed to `self.register(…)`.

3. **Tests** — add tests under `tests/` following existing patterns.

There is no separate `OMICS_MODULES` string dict; discovery is **explicit** in `discover_and_register_modules`.

## Documentation

- Update [README.md](README.md) or [docs/CONFIGURATION.md](docs/CONFIGURATION.md) if you change user-visible behavior, env vars, or defaults.
- FastAPI routes: prefer `summary` / `description` / `response_model` for OpenAPI.

## Reporting issues

For bugs: steps to reproduce, expected vs actual behavior, OS/Python version, and relevant logs. For features: use case and constraints.

## License

Contributions are licensed under the same terms as the project (MIT) — see [LICENSE](LICENSE).

Thank you for contributing.
