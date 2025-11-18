"""Database connection for TelegramOllama API."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings

# SQLite engine with connection pooling disabled for thread safety
# Handle different DB_PATH formats:
# - ":memory:" → sqlite:///:memory: (in-memory test DB)
# - Absolute path (/app/db/shifts.db) → sqlite:////app/db/shifts.db
# - Relative path (db/shifts.db) → sqlite:///./db/shifts.db
if settings.DB_PATH == ":memory:":
    db_url = "sqlite:///:memory:"
elif settings.DB_PATH.startswith('/'):
    db_url = f"sqlite:///{settings.DB_PATH}"  # Absolute: 3 prefix + leading / in path = 4
else:
    db_url = f"sqlite:///./{settings.DB_PATH}"  # Relative: ensure ./

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False}
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
