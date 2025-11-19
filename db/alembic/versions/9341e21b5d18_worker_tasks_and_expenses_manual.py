"""worker_tasks_and_expenses_manual

Revision ID: 9341e21b5d18
Revises: ebe7226fed2c
Create Date: 2025-11-14 11:06:32.468177

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9341e21b5d18'
down_revision: Union[str, Sequence[str], None] = 'ebe7226fed2c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create worker_tasks table
    op.create_table(
        'worker_tasks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('shift_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_tasks_user_id'), 'worker_tasks', ['user_id'], unique=False)
    op.create_index(op.f('ix_worker_tasks_shift_id'), 'worker_tasks', ['shift_id'], unique=False)
    
    # Create worker_expenses table
    op.create_table(
        'worker_expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('shift_id', sa.Integer(), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_worker_expenses_user_id'), 'worker_expenses', ['user_id'], unique=False)
    op.create_index(op.f('ix_worker_expenses_shift_id'), 'worker_expenses', ['shift_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_worker_expenses_shift_id'), table_name='worker_expenses')
    op.drop_index(op.f('ix_worker_expenses_user_id'), table_name='worker_expenses')
    op.drop_table('worker_expenses')
    op.drop_index(op.f('ix_worker_tasks_shift_id'), table_name='worker_tasks')
    op.drop_index(op.f('ix_worker_tasks_user_id'), table_name='worker_tasks')
    op.drop_table('worker_tasks')
