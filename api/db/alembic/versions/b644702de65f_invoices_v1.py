"""invoices_v1

Revision ID: b644702de65f
Revises: e30120ea945b
Create Date: 2025-11-11 21:12:13.805507

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b644702de65f'
down_revision: Union[str, Sequence[str], None] = 'e30120ea945b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS invoices(
            id INTEGER PRIMARY KEY,
            client_id TEXT NOT NULL,
            period_from TEXT NOT NULL,
            period_to TEXT NOT NULL,
            total REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'RUB',
            status TEXT NOT NULL DEFAULT 'draft',
            version INTEGER NOT NULL DEFAULT 1,
            pdf_path TEXT,
            xlsx_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_client_id ON invoices(client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_created_at ON invoices(created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS invoices")
