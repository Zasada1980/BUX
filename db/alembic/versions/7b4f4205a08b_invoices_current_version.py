from alembic import op
import sqlalchemy as sa

revision = '7b4f4205a08b'
down_revision = '451404d8dad7'
branch_labels = None
depends_on = None

def _has_col(conn, table, col):
    res = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == col for row in res)

def upgrade():
    conn = op.get_bind()
    if not _has_col(conn, 'invoices', 'current_version'):
        op.add_column('invoices', sa.Column('current_version', sa.Integer(), nullable=True, server_default='1'))
        with op.batch_alter_table('invoices') as b:
            b.alter_column('current_version', existing_type=sa.Integer(), nullable=False, server_default=None)

def downgrade():
    conn = op.get_bind()
    if _has_col(conn, 'invoices', 'current_version'):
        op.drop_column('invoices', 'current_version')
