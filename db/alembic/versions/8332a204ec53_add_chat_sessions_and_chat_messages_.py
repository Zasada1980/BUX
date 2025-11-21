"""Add chat_sessions and chat_messages tables

Revision ID: 8332a204ec53
Revises: e2e002
Create Date: 2025-11-20 22:35:13.777696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8332a204ec53'
down_revision: Union[str, Sequence[str], None] = 'e2e002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
