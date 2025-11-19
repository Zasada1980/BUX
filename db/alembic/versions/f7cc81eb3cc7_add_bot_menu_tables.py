"""add_bot_menu_tables

Revision ID: f7cc81eb3cc7
Revises: abc123456789
Create Date: 2025-11-19

Creates bot_menu_config and bot_commands tables for Telegram bot menu management.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "f7cc81eb3cc7"
down_revision: Union[str, Sequence[str], None] = "abc123456789"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create bot_menu_config and bot_commands tables."""
    
    # bot_menu_config: Tracks menu configuration version and metadata
    op.create_table(
        "bot_menu_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_updated_at", sa.Text(), nullable=True),
        sa.Column("last_updated_by", sa.Text(), nullable=True),
        sa.Column("last_applied_at", sa.Text(), nullable=True),
        sa.Column("last_applied_by", sa.Text(), nullable=True),
    )
    
    # bot_commands: Command configuration per role
    op.create_table(
        "bot_commands",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("command", sa.Text(), nullable=False, unique=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), server_default=sa.text("(datetime('now'))")),
        sa.Column("updated_at", sa.Text(), server_default=sa.text("(datetime('now'))")),
    )
    
    # Initialize bot_menu_config with default row
    op.execute("INSERT INTO bot_menu_config (id, version) VALUES (1, 1)")


def downgrade() -> None:
    """Drop bot_menu_config and bot_commands tables."""
    op.drop_table("bot_commands")
    op.drop_table("bot_menu_config")
