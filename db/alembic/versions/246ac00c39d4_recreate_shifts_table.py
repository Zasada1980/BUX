"""recreate_shifts_table

Revision ID: 246ac00c39d4
Revises: c0e37aa46200
Create Date: 2025-11-11 19:26:23.604519

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '246ac00c39d4'
down_revision: Union[str, Sequence[str], None] = 'c0e37aa46200'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recreate shifts table with correct schema (SQLite no DROP COLUMN support)."""
    # 1. Rename old table
    op.rename_table('shifts', 'shifts_old')
    
    # 2. Create new table with correct schema
    op.create_table(
        'shifts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='open'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text("(datetime('now'))")),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_shifts_user_id'), 'shifts', ['user_id'], unique=False)
    
    # 3. Migrate data from old table
    op.execute("""
        INSERT INTO shifts (id, user_id, status, created_at)
        SELECT id, user_id, 'open', COALESCE(started_at, datetime('now'))
        FROM shifts_old
    """)
    
    # 4. Drop old table
    op.drop_table('shifts_old')


def downgrade() -> None:
    """Downgrade not supported (data loss)."""
    pass
