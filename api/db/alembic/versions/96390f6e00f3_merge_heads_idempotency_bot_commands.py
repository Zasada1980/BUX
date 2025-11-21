"""merge heads: idempotency + bot_commands

Revision ID: 96390f6e00f3
Revises: a1b2c3d4e5f6, g5h6i7j8k9l0
Create Date: 2025-11-21 11:05:57.436589

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '96390f6e00f3'
down_revision: Union[str, Sequence[str], None] = ('a1b2c3d4e5f6', 'g5h6i7j8k9l0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
