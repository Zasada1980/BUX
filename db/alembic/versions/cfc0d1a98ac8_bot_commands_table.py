"""bot_commands_table

Revision ID: cfc0d1a98ac8
Revises: 0100_employees_auth
Create Date: 2025-11-15 17:22:29.396641

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cfc0d1a98ac8'
down_revision: Union[str, Sequence[str], None] = '0100_employees_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
