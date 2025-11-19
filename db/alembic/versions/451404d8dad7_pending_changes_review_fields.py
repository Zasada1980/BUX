from alembic import op
import sqlalchemy as sa

revision = '451404d8dad7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def _has_col(conn, table: str, col: str) -> bool:
    res = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == col for row in res)

def upgrade():
    conn = op.get_bind()
    if not _has_col(conn, 'pending_changes', 'reviewed_by'):
        op.add_column('pending_changes', sa.Column('reviewed_by', sa.String(80), nullable=True))
    if not _has_col(conn, 'pending_changes', 'reviewed_at'):
        op.add_column('pending_changes', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    if not _has_col(conn, 'pending_changes', 'review_reason'):
        op.add_column('pending_changes', sa.Column('review_reason', sa.Text(), nullable=True))

def downgrade():
    conn = op.get_bind()
    if _has_col(conn, 'pending_changes', 'review_reason'):
        op.drop_column('pending_changes', 'review_reason')
    if _has_col(conn, 'pending_changes', 'reviewed_at'):
        op.drop_column('pending_changes', 'reviewed_at')
    if _has_col(conn, 'pending_changes', 'reviewed_by'):
        op.drop_column('pending_changes', 'reviewed_by')
