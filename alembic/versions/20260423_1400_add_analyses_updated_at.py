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
    """Add ``analyses.updated_at`` unless revision 001 already made it.

    This revision was written against ``analysis.analyses`` -- a table in an
    ``analysis`` schema that no revision creates. Retargeted at the public
    ``analyses``, it collides with 001, which already declares ``updated_at``
    on that table. The check keeps the revision meaningful for a database
    predating 001's column without aborting ``upgrade head`` on one that has
    it.
    """
    bind = op.get_bind()
    already = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'analyses' AND column_name = 'updated_at'"
        )
    ).scalar()
    if already:
        return
    op.add_column(
        "analyses",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analyses", "updated_at")
