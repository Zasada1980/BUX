"""create_invoice_review_tokens_table

Revision ID: ab7302c58b43
Revises: 5c8e9f2a1b3d
Create Date: 2025-11-14 13:12:37.211402

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab7302c58b43'
down_revision: Union[str, Sequence[str], None] = '5c8e9f2a1b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create invoice_review_tokens table for one-time preview tokens (S3 Skeptic gate)
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
    
    # Add indexes for fast token lookup and invoice filtering
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_review_tokens_token ON invoice_review_tokens(token)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoice_review_tokens_invoice_id ON invoice_review_tokens(invoice_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TABLE IF EXISTS invoice_review_tokens")
