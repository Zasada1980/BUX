"""fix_bot_commands_schema

Revision ID: e2e001
Revises: d6a4c8bd97ee
Create Date: 2025-11-19 19:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e2e001'
down_revision: Union[str, Sequence[str], None] = 'abc123456789'  # After channel_messages index
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Recreate bot_commands table with full schema (command_key, telegram_command, label, etc.)
    SQLite doesn't support multiple ADD COLUMN, so we recreate the table.
    """
    # 1. Rename old table
    op.execute("ALTER TABLE bot_commands RENAME TO bot_commands_old")
    
    # 2. Create new table with full schema
    op.execute("""
        CREATE TABLE bot_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            command_key TEXT NOT NULL UNIQUE,
            telegram_command TEXT NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            is_core INTEGER NOT NULL DEFAULT 0,
            position INTEGER NOT NULL DEFAULT 0,
            command_type TEXT DEFAULT 'action',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    # 3. Migrate existing data (if any)
    op.execute("""
        INSERT INTO bot_commands (id, role, command_key, telegram_command, label, description, enabled, is_core, position, command_type)
        SELECT 
            id,
            role,
            command AS command_key,
            '/' || command AS telegram_command,
            UPPER(SUBSTR(command, 1, 1)) || SUBSTR(command, 2) AS label,
            description,
            enabled,
            0 AS is_core,
            0 AS position,
            'action' AS command_type
        FROM bot_commands_old
    """)
    
    # 4. Drop old table
    op.execute("DROP TABLE bot_commands_old")


def downgrade() -> None:
    """Downgrade schema (recreate simple bot_commands)."""
    op.execute("ALTER TABLE bot_commands RENAME TO bot_commands_new")
    
    op.execute("""
        CREATE TABLE bot_commands (
            id INTEGER PRIMARY KEY,
            command TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            enabled INTEGER DEFAULT 1 NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    op.execute("""
        INSERT INTO bot_commands (id, command, role, enabled, description)
        SELECT id, command_key, role, enabled, description
        FROM bot_commands_new
    """)
    
    op.execute("DROP TABLE bot_commands_new")
