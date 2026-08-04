"""Compare the ORM models against what the Alembic migrations declare.

``backend/app/models/`` was reconstructed from its call sites -- `.gitignore`'s
bare ``models/`` rule had matched the directory, so it was never committed.
The migrations in ``alembic/versions/`` were, from the initial commit onward,
which makes them an independent record of the schema and the only way to check
that reconstruction against something other than itself.

They do not currently agree, and nothing in the project noticed:

* ``backend.app.core.database.init_db`` builds the schema with
  ``Base.metadata.create_all``, so the application and the tests get whatever
  the models say and never consult a migration.
* No workflow runs ``alembic upgrade``.

That matters because README documents ``alembic upgrade head`` as the setup
step. On a database built that way, ``create_all`` adds tables that are missing
but does not add columns to tables that already exist -- so ``datasets`` would
have the migration's ``data_type``/``file_path`` while the code selects
``omics_type``/``storage_path``, and the query fails at runtime.

**The models are the authoritative side.** That is not a guess: only
``models/`` was lost, so every consumer of it survived in the initial commit
and says what the original columns were. In that commit,
``api/v1/routes/datasets.py`` constructs ``Dataset(omics_type=...,
data_format=..., source=..., source_id=..., clinical_data=...,
sample_metadata=..., status=...)``; across the original backend,
``dataset.storage_path`` appears 15 times, ``dataset.data_format`` 5 and
``dataset.omics_type`` 3, while ``dataset.data_type``, ``dataset.file_path``,
``dataset.file_format`` and ``dataset.file_size`` -- the migration's names --
appear zero times. The same holds for ``pipeline.default_parameters``,
``project.visibility``, ``project.project_type`` and
``analysis.current_step``. ``routes/pipelines.py`` imports ``PipelineRun``
from the models in that same commit, so the missing ``pipeline_runs``
migration is an omission rather than an invented table.

So the fix is to regenerate the migrations from the models, not to change the
models. That needs ``alembic revision --autogenerate`` against a real
PostgreSQL -- the migrations use ARRAY columns, which SQLite cannot render --
so it is left to a change that can run one.

Until then this module stops the drift from growing: the differences are
enumerated below, and the tests fail if a new one appears or a listed one is
fixed without updating the list.
"""

from __future__ import annotations

import ast
import contextlib
import pathlib

import pytest

from backend.app.core.database import Base

# Importing the package registers every model on Base.metadata.
import backend.app.models  # noqa: F401  isort:skip

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"

# audit_logs is deliberate, not drift. core/security_hardening.py writes to it
# with raw SQL -- "Persist to SQL when an ``audit_logs``-compatible table
# exists (optional migration)" -- and no ORM model was ever meant to map it.
# This entry should stay.
EXPECTED_TABLES_ONLY_IN_MIGRATIONS = {"audit_logs"}

# pipeline_runs is a missing migration. routes/pipelines.py imported
# PipelineRun from the models in the initial commit, so the table is real and
# `alembic upgrade head` simply never creates it -- only create_all does.
# This entry should go away once the migrations are regenerated.
EXPECTED_TABLES_ONLY_IN_MODELS = {"pipeline_runs"}

EXPECTED_COLUMNS_ONLY_IN_MIGRATIONS = {
    "analysis_results": {"metadata"},
    "datasets": {"data_type", "file_format", "file_path", "file_size"},
}

EXPECTED_COLUMNS_ONLY_IN_MODELS = {
    "analyses": {"current_step", "total_steps"},
    "analysis_results": {
        "description",
        "file_size",
        "file_type",
        "metrics",
        "name",
        "summary",
    },
    "datasets": {
        "clinical_data",
        "data_format",
        "feature_count",
        "normalization_method",
        "omics_type",
        "preprocessing_applied",
        "qc_metrics",
        "qc_passed",
        "sample_count",
        "sample_metadata",
        "source",
        "source_id",
        "status",
        "storage_path",
        "storage_type",
        "total_size",
    },
    "pipelines": {
        "author",
        "default_parameters",
        "is_active",
        "is_public",
        "max_retries",
        "omics_types",
        "tags",
        "timeout_seconds",
        "version",
    },
    "projects": {
        "collaborators",
        "config",
        "metadata",
        "omics_types",
        "project_type",
        "status",
        "visibility",
    },
}


def _migration_schema() -> dict[str, set[str]]:
    """Table -> column names, read statically from the migration scripts.

    Parsed rather than executed: the migrations use PostgreSQL ARRAY columns,
    so running them needs a real PostgreSQL and would make this test depend on
    a service. Only op.create_table and op.add_column are followed, which is
    what the migrations here use.
    """
    tables: dict[str, set[str]] = {}
    for path in sorted(VERSIONS_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = ast.unparse(node.func)
            if func.endswith("create_table") and node.args:
                first = node.args[0]
                if not isinstance(first, ast.Constant):
                    continue
                cols = tables.setdefault(first.value, set())
                for arg in node.args[1:]:
                    if (
                        isinstance(arg, ast.Call)
                        and ast.unparse(arg.func).endswith("Column")
                        and arg.args
                    ):
                        # A computed column name is not something to guess at;
                        # every migration here passes a literal.
                        with contextlib.suppress(ValueError):
                            cols.add(ast.literal_eval(arg.args[0]))
            elif func.endswith("add_column") and len(node.args) >= 2:
                first = node.args[0]
                col = node.args[1]
                if not isinstance(first, ast.Constant):
                    continue
                if isinstance(col, ast.Call) and col.args:
                    with contextlib.suppress(ValueError):
                        tables.setdefault(first.value, set()).add(ast.literal_eval(col.args[0]))
    return tables


def _model_schema() -> dict[str, set[str]]:
    return {
        table.name: {column.name for column in table.columns}
        for table in Base.metadata.sorted_tables
    }


def test_migrations_are_parseable():
    """The comparison is worthless if the migration scripts stop parsing."""
    schema = _migration_schema()
    assert schema, "no tables found in alembic/versions -- did the layout change?"
    assert "users" in schema


def test_no_unexpected_tables_only_in_migrations():
    """A migration-only table means nothing maps to it in the ORM."""
    extra = set(_migration_schema()) - set(_model_schema())
    assert extra == EXPECTED_TABLES_ONLY_IN_MIGRATIONS


def test_no_unexpected_tables_only_in_models():
    """A model-only table is never created by `alembic upgrade head`."""
    extra = set(_model_schema()) - set(_migration_schema())
    assert extra == EXPECTED_TABLES_ONLY_IN_MODELS


@pytest.mark.parametrize("table", sorted(set(_migration_schema()) & set(_model_schema())))
def test_column_drift_per_table(table):
    """Per table, the drift must match what is recorded above.

    Split per table so a failure names the table rather than dumping the whole
    schema, and so fixing one table does not require touching the others.
    """
    migration_cols = _migration_schema()[table]
    model_cols = _model_schema()[table]

    only_migrations = migration_cols - model_cols
    only_models = model_cols - migration_cols

    assert only_migrations == EXPECTED_COLUMNS_ONLY_IN_MIGRATIONS.get(
        table, set()
    ), f"{table}: columns in the migrations with no model attribute changed"
    assert only_models == EXPECTED_COLUMNS_ONLY_IN_MODELS.get(
        table, set()
    ), f"{table}: model attributes no migration creates changed"


def test_users_table_is_fully_reconciled():
    """users is the one table where both sides already agree.

    Kept as its own test so the property is asserted rather than left implicit
    in the empty allowlist entries -- if it ever drifts, that is a regression
    in something previously verified.
    """
    assert _migration_schema()["users"] == _model_schema()["users"]
