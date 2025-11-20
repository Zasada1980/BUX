"""preview_tokens_ttl_once

Revision ID: e2fb58c4fcc2
Revises: b644702de65f
Create Date: 2025-11-11 22:02:56.638804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2fb58c4fcc2'
down_revision: Union[str, Sequence[str], None] = 'b644702de65f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
