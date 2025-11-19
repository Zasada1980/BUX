"""invoice_versions_table

Revision ID: 2b1eb4a7e4c8
Revises: 7b4f4205a08b
Create Date: 2025-11-13 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2b1eb4a7e4c8'
down_revision: Union[str, None] = '7b4f4205a08b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _table_exists(conn, table_name):
    res = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"), {"t": table_name})
    return res.fetchone() is not None

def upgrade() -> None:
    conn = op.get_bind()
    if not _table_exists(conn, 'invoice_versions'):
        op.create_table(
            'invoice_versions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('invoice_id', sa.Integer(), nullable=False),
            sa.Column('version', sa.Integer(), nullable=False),
            sa.Column('payload_json', sa.Text(), nullable=False),
            sa.Column('pdf_path', sa.Text(), nullable=True),
            sa.Column('html_path', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        )
        op.create_index('idx_invoice_versions_lookup', 'invoice_versions', ['invoice_id', 'version'], unique=True)

def downgrade() -> None:
    conn = op.get_bind()
    if _table_exists(conn, 'invoice_versions'):
        op.drop_index('idx_invoice_versions_lookup', table_name='invoice_versions')
        op.drop_table('invoice_versions')
