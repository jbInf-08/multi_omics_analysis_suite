"""Add queued value to analysis status enum where applicable.

Revision ID: add_queued_status
Revises: 11096420bc74
Create Date: 2026-04-23

PostgreSQL native enums created for AnalysisStatus may omit ``queued``;
the application sets ``AnalysisStatus.QUEUED`` after Celery enqueue.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add_queued_status"
down_revision: Union[str, None] = "11096420bc74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ``queued`` to PostgreSQL ``analysisstatus`` enum (requires autocommit)."""
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    with op.get_context().autocommit_block():
        op.execute(sa.text("ALTER TYPE analysisstatus ADD VALUE IF NOT EXISTS 'queued'"))


def downgrade() -> None:
    """Enum values cannot be removed safely in PostgreSQL; no-op."""
    pass
