"""add_missing_user_columns

Revision ID: 11096420bc74
Revises: 001
Create Date: 2026-01-30 17:23:57.789940+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "11096420bc74"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to users table."""
    # Add missing user columns
    op.add_column("users", sa.Column("username", sa.String(length=100), nullable=True), schema="omics")
    op.add_column("users", sa.Column("organization", sa.String(length=255), nullable=True), schema="omics")
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True), schema="omics")
    op.add_column("users", sa.Column("is_verified", sa.Boolean(), server_default="false", nullable=False), schema="omics")
    op.add_column("users", sa.Column("roles", sa.JSON(), server_default="[]", nullable=False), schema="omics")
    op.add_column("users", sa.Column("permissions", sa.JSON(), server_default="[]", nullable=False), schema="omics")
    op.add_column("users", sa.Column("settings", sa.JSON(), server_default="{}", nullable=False), schema="omics")
    op.add_column("users", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True), schema="omics")
    
    # Update existing users - set username to email for existing records
    op.execute("UPDATE omics.users SET username = email WHERE username IS NULL")
    
    # Make username not null and unique after backfilling
    op.alter_column("users", "username", nullable=False, schema="omics")
    op.create_index("ix_omics_users_username", "users", ["username"], unique=True, schema="omics")


def downgrade() -> None:
    """Remove added user columns."""
    op.drop_index("ix_omics_users_username", table_name="users", schema="omics")
    op.drop_column("users", "last_login", schema="omics")
    op.drop_column("users", "settings", schema="omics")
    op.drop_column("users", "permissions", schema="omics")
    op.drop_column("users", "roles", schema="omics")
    op.drop_column("users", "is_verified", schema="omics")
    op.drop_column("users", "bio", schema="omics")
    op.drop_column("users", "organization", schema="omics")
    op.drop_column("users", "username", schema="omics")
