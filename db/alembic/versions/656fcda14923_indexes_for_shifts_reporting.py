"""indexes_for_shifts_reporting

Revision ID: 656fcda14923
Revises: 246ac00c39d4
Create Date: 2025-11-11 19:35:35.471020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '656fcda14923'
down_revision: Union[str, Sequence[str], None] = '246ac00c39d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create indexes for shifts reporting queries."""
    op.execute("CREATE INDEX IF NOT EXISTS ix_shifts_user_id ON shifts(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_shifts_created_at ON shifts(created_at)")


def downgrade() -> None:
    """Remove reporting indexes."""
    op.execute("DROP INDEX IF EXISTS ix_shifts_user_id")
    op.execute("DROP INDEX IF EXISTS ix_shifts_created_at")
