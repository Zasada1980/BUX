"""Idempotency utilities for TelegramOllama API."""
import hashlib
from sqlalchemy import text


TABLE_SQL = """
CREATE TABLE IF NOT EXISTS idempotency_keys(
  key TEXT PRIMARY KEY,
  created_at TEXT DEFAULT (datetime('now'))
);
"""


def ensure_table(session_factory):
    """Ensure idempotency_keys table exists."""
    with session_factory() as s:
        s.execute(text(TABLE_SQL))
        s.commit()


def remember(key: str, session_factory) -> bool:
    """
    Check and record idempotency key.
    
    Returns:
        True if key is new (inserted successfully)
        False if key already exists (duplicate request)
    """
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()
    
    with session_factory() as s:
        s.execute(text("INSERT OR IGNORE INTO idempotency_keys(key) VALUES (:k)"), {"k": h})
        s.commit()
        
        # Check if insertion occurred: changes() returns number of rows modified
        r = s.execute(text("SELECT changes()")).scalar()
        return bool(r)
