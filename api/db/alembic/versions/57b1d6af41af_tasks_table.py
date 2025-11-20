"""tasks table

Revision ID: 57b1d6af41af
Revises: 656fcda14923
Create Date: 2025-11-11 19:55:28.646047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57b1d6af41af'
down_revision: Union[str, Sequence[str], None] = '656fcda14923'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
      id INTEGER PRIMARY KEY,
      shift_id INTEGER NOT NULL,
      rate_code TEXT NOT NULL,
      qty REAL NOT NULL,
      unit TEXT NOT NULL DEFAULT 'unit',
      amount REAL NOT NULL,
      note TEXT,
      created_at TEXT DEFAULT (datetime('now')),
      FOREIGN KEY (shift_id) REFERENCES shifts(id) ON DELETE CASCADE
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_shift_id ON tasks(shift_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tasks_created_at ON tasks(created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS tasks")
