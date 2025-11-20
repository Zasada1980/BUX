"""drop_legacy_tasks_expenses_tables

Revision ID: 93def92f0b7d
Revises: 459fb896f7a5
Create Date: 2025-11-20 23:25:57.293471

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93def92f0b7d'
down_revision: Union[str, Sequence[str], None] = '459fb896f7a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Drop legacy tasks and expenses tables (TD-DUAL-TABLES-1).
    
    Context:
    - Legacy tables have zero code references (verified via grep)
    - tasks: 0 rows (empty)
    - expenses: 5 test rows (exported to CSV: backups/legacy_expenses_2025-11-20.csv)
    - ORM tables (worker_tasks, worker_expenses) are canonical
    - See reports/TD_DUAL_TABLES_AUDIT_REPORT.md for full audit
    """
    # Drop legacy tables that are no longer used
    op.execute("DROP TABLE IF EXISTS tasks;")
    op.execute("DROP TABLE IF EXISTS expenses;")


def downgrade() -> None:
    """
    Recreate legacy tables for rollback (schema only, no data).
    
    WARNING: Downgrade restores table structure but NOT data.
    Legacy data is archived in backups/legacy_expenses_2025-11-20.csv
    """
    # Recreate tasks table
    op.execute("""
    CREATE TABLE tasks (
        id INTEGER PRIMARY KEY,
        shift_id INTEGER NOT NULL,
        rate_code TEXT NOT NULL,
        qty REAL NOT NULL,
        unit TEXT NOT NULL DEFAULT 'unit',
        amount REAL NOT NULL,
        note TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (shift_id) REFERENCES shifts(id) ON DELETE CASCADE
    );
    """)
    op.execute("CREATE INDEX ix_tasks_shift_id ON tasks(shift_id);")
    op.execute("CREATE INDEX ix_tasks_created_at ON tasks(created_at);")
    
    # Recreate expenses table
    op.execute("""
    CREATE TABLE expenses (
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
    );
    """)
    op.execute("CREATE INDEX ix_expenses_worker_id ON expenses(worker_id);")
    op.execute("CREATE INDEX ix_expenses_created_at ON expenses(created_at);")
