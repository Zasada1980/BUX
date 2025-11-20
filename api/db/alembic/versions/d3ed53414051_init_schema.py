"""init schema

Revision ID: d3ed53414051
Revises: 
Create Date: 2025-11-11 20:55:29.697948

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3ed53414051'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "shifts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("started_at", sa.Text, nullable=False),
        sa.Column("meta", sa.Text),
    )
    op.create_index("idx_shifts_user_id", "shifts", ["user_id"])

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("shift_id", sa.Integer, nullable=False),
        sa.Column("ts", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("payload", sa.Text),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_ledger_shift_id", "ledger_entries", ["shift_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_ledger_shift_id", "ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("idx_shifts_user_id", "shifts")
    op.drop_table("shifts")
