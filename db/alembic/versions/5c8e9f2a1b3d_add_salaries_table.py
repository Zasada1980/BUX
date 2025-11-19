"""Add salaries table

Revision ID: 5c8e9f2a1b3d
Revises: 4b2f37e3cc48
Create Date: 2025-11-14 13:17:00

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = '5c8e9f2a1b3d'
down_revision = '4b2f37e3cc48'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создание таблицы salaries
    op.create_table(
        'salaries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('worker_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='manual'),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], name='fk_salaries_worker_id'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Создание индексов для быстрого поиска
    op.create_index('idx_salaries_worker_id', 'salaries', ['worker_id'])
    op.create_index('idx_salaries_date', 'salaries', ['date'])
    op.create_index('idx_salaries_source', 'salaries', ['source'])


def downgrade() -> None:
    op.drop_index('idx_salaries_source', table_name='salaries')
    op.drop_index('idx_salaries_date', table_name='salaries')
    op.drop_index('idx_salaries_worker_id', table_name='salaries')
    op.drop_table('salaries')
