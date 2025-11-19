"""add status and created_at to shifts

Revision ID: c0e37aa46200
Revises: d3ed53414051
Create Date: 2025-11-11 21:12:10.275929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c0e37aa46200'
down_revision: Union[str, Sequence[str], None] = 'd3ed53414051'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns
    op.add_column("shifts", sa.Column("status", sa.String, nullable=True))
    op.add_column("shifts", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    
    # Set default values for existing rows
    op.execute("UPDATE shifts SET status = 'open' WHERE status IS NULL")
    op.execute("UPDATE shifts SET created_at = datetime('now') WHERE created_at IS NULL")
    
    # Make columns non-nullable (SQLite doesn't support ALTER COLUMN, but we can set defaults)
    # Note: In SQLite, we cannot change column constraints without recreating the table
    # For simplicity, we'll leave them nullable in the database but enforce in application


def downgrade() -> None:
    """Downgrade schema."""
    # SQLite doesn't support DROP COLUMN directly
    # For a proper downgrade, we'd need to recreate the table
    # For now, leaving as-is (columns will remain but unused)
    pass
