"""preview_tokens_ttl_once

Revision ID: e2fb58c4fcc2
Revises: b644702de65f
Create Date: 2025-11-11 22:02:56.638804

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2fb58c4fcc2'
down_revision: Union[str, Sequence[str], None] = 'b644702de65f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        CREATE TABLE IF NOT EXISTS invoice_review_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            token TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL,
            consumed_at DATETIME,
            ttl_seconds INTEGER NOT NULL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_review_tokens_token ON invoice_review_tokens(token)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_review_tokens_invoice_id ON invoice_review_tokens(invoice_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS invoice_review_tokens")
