"""expenses_and_shift_end

Revision ID: e30120ea945b
Revises: f178c0725a75
Create Date: 2025-11-11 20:28:57.562495

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e30120ea945b'
down_revision: Union[str, Sequence[str], None] = 'f178c0725a75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # expenses table
    op.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
      id INTEGER PRIMARY KEY,
      worker_id TEXT NOT NULL,
      shift_id INTEGER,
      category TEXT NOT NULL,
      amount REAL NOT NULL,
      currency TEXT NOT NULL DEFAULT 'RUB',
      photo_ref TEXT,
      ocr_text TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      confirmed INTEGER NOT NULL DEFAULT 0,
      source TEXT DEFAULT 'manual',
      FOREIGN KEY (shift_id) REFERENCES shifts(id) ON DELETE SET NULL
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_expenses_worker_id ON expenses(worker_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_expenses_created_at ON expenses(created_at)")
    
    # shifts: ended_at column
    op.execute("ALTER TABLE shifts ADD COLUMN ended_at TEXT")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS expenses")
    # Note: SQLite doesn't support DROP COLUMN easily, ended_at remains
