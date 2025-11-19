"""invoice_suggestions_table

Revision ID: ca96fdaef90e
Revises: 2b1eb4a7e4c8
Create Date: 2025-11-13 12:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'ca96fdaef90e'
down_revision: Union[str, None] = '2b1eb4a7e4c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _table_exists(conn, table_name):
    res = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table_name})
    return res.fetchone() is not None

def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, 'invoice_suggestions'):
        op.create_table(
            'invoice_suggestions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('invoice_id', sa.Integer(), nullable=False),
            sa.Column('source', sa.Text(), nullable=True),
            sa.Column('kind', sa.Text(), nullable=False),
            sa.Column('payload_json', sa.Text(), nullable=False),
            sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        op.create_index('idx_invoice_sugg_lookup', 'invoice_suggestions', ['invoice_id', 'status'])

def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, 'invoice_suggestions'):
        op.drop_index('idx_invoice_sugg_lookup', table_name='invoice_suggestions')
        op.drop_table('invoice_suggestions')
