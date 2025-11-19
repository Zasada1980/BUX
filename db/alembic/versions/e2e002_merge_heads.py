"""merge_heads

Revision ID: e2e002
Revises: e2e001, f7cc81eb3cc7
Create Date: 2025-11-19 20:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'e2e002'
down_revision: Union[str, Sequence[str], None] = ('e2e001', 'f7cc81eb3cc7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge two migration heads (no schema changes)."""
    pass


def downgrade() -> None:
    """Downgrade merge (no schema changes)."""
    pass
