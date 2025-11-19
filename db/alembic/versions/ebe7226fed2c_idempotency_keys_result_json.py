"""idempotency_keys_result_json

Revision ID: ebe7226fed2c
Revises: ca96fdaef90e
Create Date: 2025-11-13 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'ebe7226fed2c'
down_revision: Union[str, None] = 'ca96fdaef90e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _has_col(conn, table, col):
    res = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == col for row in res)

def upgrade() -> None:
    conn = op.get_bind()
    if not _has_col(conn, 'idempotency_keys', 'result_json'):
        with op.batch_alter_table('idempotency_keys') as b:
            b.add_column(sa.Column('result_json', sa.Text(), nullable=True))

def downgrade() -> None:
    conn = op.get_bind()
    if _has_col(conn, 'idempotency_keys', 'result_json'):
        with op.batch_alter_table('idempotency_keys') as b:
            b.drop_column('result_json')
