"""Add queued value to analysis status enum where applicable.

Revision ID: add_queued_status
Revises: 11096420bc74
Create Date: 2026-04-23

PostgreSQL native enums created for AnalysisStatus may omit ``queued``;
the application sets ``AnalysisStatus.QUEUED`` after Celery enqueue.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "add_queued_status"
down_revision: str | None = "11096420bc74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add ``queued`` to the ``analysisstatus`` enum, if one exists.

    The existence check is not defensive padding -- without it this revision
    aborts ``alembic upgrade head`` on every database this project creates.
    Revision 001 makes ``analyses.status`` a ``VARCHAR(50)``, and the model
    backs it with ``SAEnum(..., native_enum=False)``, so no ``analysisstatus``
    type is ever created and ``ALTER TYPE`` has nothing to alter. The statement
    is kept for databases that were built with a native enum by some other
    route.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    exists = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'analysisstatus'")
    ).scalar()
    if not exists:
        return
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE analysisstatus ADD VALUE IF NOT EXISTS 'queued'"))


def downgrade() -> None:
    """Enum values cannot be removed safely in PostgreSQL; no-op."""
    pass
