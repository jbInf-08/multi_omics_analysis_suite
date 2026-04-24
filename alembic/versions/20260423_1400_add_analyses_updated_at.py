"""Add analyses.updated_at.

Revision ID: analyses_updated_at
Revises: add_queued_status
Create Date: 2026-04-23

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "analyses_updated_at"
down_revision: str | None = "add_queued_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="analysis",
    )


def downgrade() -> None:
    op.drop_column("analyses", "updated_at", schema="analysis")
