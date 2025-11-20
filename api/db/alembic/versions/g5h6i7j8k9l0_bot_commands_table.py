"""bot_commands table for Telegram menu management

Revision ID: g5h6i7j8k9l0
Revises: f178c0725a75
Create Date: 2025-11-15 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g5h6i7j8k9l0'
down_revision: Union[str, Sequence[str], None] = 'f178c0725a75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Create bot_commands table and bot_menu_config."""
    
    # bot_commands table: Stores Telegram commands configuration by role
    op.execute("""
    CREATE TABLE IF NOT EXISTS bot_commands (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      role TEXT NOT NULL CHECK(role IN ('admin', 'foreman', 'worker')),
      command_key TEXT NOT NULL UNIQUE,
      telegram_command TEXT NOT NULL,
      label TEXT NOT NULL,
      description TEXT,
      enabled BOOLEAN NOT NULL DEFAULT 1,
      is_core BOOLEAN NOT NULL DEFAULT 0,
      position INTEGER NOT NULL DEFAULT 0,
      command_type TEXT NOT NULL DEFAULT 'slash' CHECK(command_type IN ('slash', 'menu')),
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT,
      UNIQUE(role, telegram_command)
    )
    """)
    
    # Indexes for performance
    op.execute("CREATE INDEX IF NOT EXISTS idx_bot_commands_role ON bot_commands(role)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_bot_commands_enabled ON bot_commands(enabled)")
    
    # bot_menu_config: Stores menu metadata (version, last updated)
    op.execute("""
    CREATE TABLE IF NOT EXISTS bot_menu_config (
      id INTEGER PRIMARY KEY CHECK(id = 1),
      version INTEGER NOT NULL DEFAULT 1,
      last_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      last_updated_by TEXT,
      last_applied_at TEXT,
      last_applied_by TEXT
    )
    """)
    
    # Insert initial config row (singleton pattern)
    op.execute("""
    INSERT OR IGNORE INTO bot_menu_config (id, version, last_updated_at)
    VALUES (1, 1, datetime('now'))
    """)


def downgrade() -> None:
    """Downgrade schema: Drop bot_commands and bot_menu_config tables."""
    op.execute("DROP TABLE IF EXISTS bot_commands")
    op.execute("DROP TABLE IF EXISTS bot_menu_config")
