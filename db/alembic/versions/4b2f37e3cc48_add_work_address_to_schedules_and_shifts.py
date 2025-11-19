"""add_work_address_to_schedules_and_shifts

Revision ID: 4b2f37e3cc48
Revises: f8a4b9c12d3e
Create Date: 2025-11-14 10:44:26.723124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b2f37e3cc48'
down_revision: Union[str, Sequence[str], None] = 'f8a4b9c12d3e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add work_address to schedules table
    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('work_address', sa.String(500), nullable=True))
    
    # Add work_address to shifts table
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('work_address', sa.String(500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove work_address from shifts table
    with op.batch_alter_table('shifts', schema=None) as batch_op:
        batch_op.drop_column('work_address')
    
    # Remove work_address from schedules table
    with op.batch_alter_table('schedules', schema=None) as batch_op:
        batch_op.drop_column('work_address')
