"""add_clients_and_schedules

Revision ID: f8a4b9c12d3e
Revises: d58e9dd783f7
Create Date: 2025-11-14 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8a4b9c12d3e'
down_revision = '9341e21b5d18'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create clients table
    op.create_table(
        'clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('nickname1', sa.String(length=100), nullable=False),
        sa.Column('nickname2', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('daily_rate', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create schedules table
    op.create_table(
        'schedules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.String(length=10), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('worker_ids', sa.String(length=500), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_schedules_date', 'schedules', ['date'])
    op.create_index('ix_schedules_client_id', 'schedules', ['client_id'])
    
    # Add client_id to shifts table
    op.add_column('shifts', sa.Column('client_id', sa.Integer(), nullable=True))
    op.create_index('ix_shifts_client_id', 'shifts', ['client_id'])


def downgrade() -> None:
    # Remove client_id from shifts
    op.drop_index('ix_shifts_client_id', table_name='shifts')
    op.drop_column('shifts', 'client_id')
    
    # Drop indexes from schedules
    op.drop_index('ix_schedules_client_id', table_name='schedules')
    op.drop_index('ix_schedules_date', table_name='schedules')
    
    # Drop tables
    op.drop_table('schedules')
    op.drop_table('clients')
