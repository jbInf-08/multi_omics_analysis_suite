# Changelog

All notable changes to the Multi-Omics Analysis Suite are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Documentation
- README, CONTRIBUTING, and `docs/CONFIGURATION.md` updated to match the repository layout (`infrastructure/`, `docker/`, `monitoring/`), CLI (`moas` / `omics`, `info`, `analyze` subcommands), env vars in `backend/app/core/config.py`, module registration via `OmicsRegistry.discover_and_register_modules`, and CI behavior (see `.github/workflows/ci.yml`).
- `pyproject.toml` `project.urls` Documentation now points to the repository README (no ReadTheDocs site in-repo).

### Changed
- `.env.example` default `DATABASE_URL` aligned with `Settings` / docker-compose host port 5433; added optional `VITE_API_URL` for the Vite frontend; Neo4j password comment aligned with compose default.

## [1.0.0] - 2024-12-01

### Added
- FastAPI application with REST v1, GraphQL, WebSocket progress, and Celery-backed analyses.
- Typer CLI (`moas` / `omics`) for local analysis helpers and `api` subcommands.
- 50+ `OmicsModuleBase` modules under `backend/omics/`, registered in `OmicsRegistry`.
- Bioinformatics, assembly, alignment, computational chemistry, and related packages under `backend/`.
- React (Vite) frontend, Dash dashboards, Docker Compose stack, Kubernetes/Helm/Terraform examples, monitoring assets.
- Test layout: `tests/unit`, `tests/integration`, `tests/property`, `tests/snapshot`.
- GitHub Actions CI for `main` and `develop` (lint, tests, frontend build, security tools).
- Pre-commit configuration; Dependabot; CodeQL/Dependabot as configured in `.github/`.

### Security
- JWT-based API authentication; tools routes support optional `X-API-Key` and rate limiting for chemistry endpoints.

---

## Version history format

- **Added** — new features  
- **Changed** — changes in existing behavior  
- **Deprecated** — soon to be removed  
- **Removed** — removed features  
- **Fixed** — bug fixes  
- **Security** — vulnerability-related fixes  
