"""idempotency_keys table for G4 bulk operations

Revision ID: a1b2c3d4e5f6
Revises: e2fb58c4fcc2
Create Date: 2025-11-12 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e2fb58c4fcc2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add idempotency_keys table for G4."""
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("scope_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="applied"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_idem_scope", "idempotency_keys", ["scope_hash"])


def downgrade() -> None:
    """Downgrade schema: drop idempotency_keys table."""
    op.drop_index("ix_idem_scope", "idempotency_keys")
    op.drop_table("idempotency_keys")
