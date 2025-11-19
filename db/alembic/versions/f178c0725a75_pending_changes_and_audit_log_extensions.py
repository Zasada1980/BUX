"""pending_changes and audit_log extensions

Revision ID: f178c0725a75
Revises: 57b1d6af41af
Create Date: 2025-11-11 20:18:24.362570

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f178c0725a75'
down_revision: Union[str, Sequence[str], None] = '57b1d6af41af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # pending_changes table (two-phase buffer)
    op.execute("""
    CREATE TABLE IF NOT EXISTS pending_changes (
      id INTEGER PRIMARY KEY,
      kind TEXT NOT NULL,
      payload_json TEXT NOT NULL,
      created_at TEXT DEFAULT (datetime('now')),
      status TEXT DEFAULT 'pending',
      actor TEXT DEFAULT 'agent',
      correlation_id TEXT
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_status ON pending_changes(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pending_corr ON pending_changes(correlation_id)")
    
    # audit_log table (if not exists, create with extensions)
    op.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
      id INTEGER PRIMARY KEY,
      ts TEXT DEFAULT (datetime('now')),
      action TEXT NOT NULL,
      entity TEXT,
      entity_id INTEGER,
      tool_call_id TEXT,
      payload_hash TEXT,
      metadata TEXT
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_log(ts)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_entity ON audit_log(entity, entity_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS pending_changes")
    # Note: audit_log not dropped to preserve history
