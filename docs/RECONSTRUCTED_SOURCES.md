# Reconstructed source layers

Three parts of this repository were rebuilt from their call sites rather than
recovered. They were never committed: `.gitignore` carried a bare `models/`
rule, which git applies at any depth, so `backend/app/models/` and
`backend/ml/models/` were both ignored. `frontend/src/lib/` went the same way
via a bare `lib/`.

The code here satisfies every use that survives in the tree, and CI is green,
but green means "consistent with the rest of the reconstruction" — not
"identical to what was lost". This file records what was inferred, what it was
inferred from, and where it is now known to disagree with an independent
source.

| layer | files | how it is checked |
|---|---|---|
| `backend/ml/models/` | `base.py`, `traditional.py`, `__init__.py` | `tests/unit/test_ml_models_registry.py` — 22 tests pinning the contract `training.py`, `automl.py` and `ml_tasks.py` depend on |
| `backend/app/models/` | 5 ORM modules | `tests/unit/test_schema_matches_migrations.py` — compared against the Alembic migrations |
| `frontend/src/lib/api.ts` | 1 module | `frontend/src/lib/api.test.ts` — 11 cases |

## backend/ml/models

Reconstructed from three consumers, each of which constrains it differently:

- `backend/ml/training.py` — calls `fit`, `predict`, `predict_proba`, assigns
  `model.metrics`, and branches on `model.model_type == "classification"`.
- `backend/app/tasks/ml_tasks.py` — constructs the six model classes with
  `task=`, and loads a saved model with
  `joblib.load(path.with_suffix(".joblib"))`, reading `feature_names` from the
  sibling `.json`.
- `backend/ml/automl.py` and `backend/ml/__init__.py` — import `get_model` and
  `list_available_models`.

The awkward detail is that the constructors take `task=` while `training.py`
reads `model_type`. Both names had to exist, so `model_type` is the attribute
and `task` is a property returning it. That is recorded in `base.py` where
someone changing it will see it.

This layer has no independent source to check against — the contract *is* the
call sites. The tests are therefore characterization tests: they lock in what
the surviving code requires, so a future edit that breaks the contract fails
in the test rather than at runtime.

## backend/app/models — known to disagree with the migrations

Unlike the ML layer, this one *can* be checked independently. The Alembic
migrations in `alembic/versions/` were committed from the initial commit
onward and were never lost, so they are a record of the schema that does not
depend on the reconstruction.

**They do not agree.** `tests/unit/test_schema_matches_migrations.py`
enumerates the differences and fails if they change.

### Why nothing caught it

`backend.app.core.database.init_db` builds the schema with
`Base.metadata.create_all`, so the application and the tests both get whatever
the models declare. No workflow runs `alembic upgrade`. The two descriptions of
the schema have therefore never been compared by anything.

### Why it matters

`README.md` documents `alembic upgrade head` as the setup step, in three
places. On a database built that way:

- `create_all` adds tables that are **missing**, but does not add columns to
  tables that already **exist**.
- So `datasets` keeps the migration's `data_type`, `file_format`, `file_path`,
  `file_size` — and the application selects `omics_type`, `data_format`,
  `storage_path`, `total_size`, which are not there.
- That is a runtime failure on first use, not a startup error.

`pipeline_runs` is the mirror image: the model exists, no migration creates it,
so only `create_all` ever brings it into being.

### The differences

Tables:

| | |
|---|---|
| in migrations, no model | `audit_logs` (11 columns, from `20260423_1800_add_audit_logs`) |
| in models, no migration | `pipeline_runs` (17 columns) |

Columns, where both sides have the table:

| table | only in migrations | only in models |
|---|---|---|
| `users` | — | — (fully reconciled) |
| `analyses` | — | `current_step`, `total_steps` |
| `analysis_results` | `metadata` | `description`, `file_size`, `file_type`, `metrics`, `name`, `summary` |
| `datasets` | `data_type`, `file_format`, `file_path`, `file_size` | 16 columns incl. `omics_type`, `storage_path`, `qc_metrics`, `sample_metadata` |
| `pipelines` | — | 9 columns incl. `version`, `is_public`, `default_parameters` |
| `projects` | — | 7 columns incl. `visibility`, `collaborators`, `omics_types` |

`users` matching exactly across 16 columns is the useful signal here: where the
reconstruction could be checked, it was right. The tables that differ are the
ones where the routes needed fields the migrations never added — which is
consistent with the migrations having fallen behind the original models rather
than the reconstruction having invented them, but that is an inference, not a
verified fact.

### Resolving it

Deciding which side is authoritative is the owner's call. Two coherent routes:

1. **Models are current.** Generate one reconciling migration
   (`alembic revision --autogenerate` against a PostgreSQL instance — the
   migrations use `ARRAY`, so SQLite cannot run them) and add a model for
   `audit_logs`. Then `alembic upgrade head` and `create_all` agree.
2. **Migrations are current.** Then the extra model columns describe fields the
   original models did not have, and the routes using them need revisiting.

Either way, the allowlists in the test shrink as tables are reconciled, and the
test fails if anyone reconciles a table without updating them.

## frontend/src/lib/api.ts

Reconstructed from the pages and hooks that import it. Covered by
`frontend/src/lib/api.test.ts`. No independent source exists for this one
either; the OpenAPI schema the backend serves would be one, and generating the
client from it would remove the guesswork entirely.
