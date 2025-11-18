"""Database connection for TelegramOllama API."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings

# SQLite engine with connection pooling disabled for thread safety
# Absolute path needs 4 slashes: sqlite:////data/workledger.db
if settings.DB_PATH.startswith('/'):
    db_url = f"sqlite:///{settings.DB_PATH}"  # Absolute: 3 prefix + leading / in path = 4
else:
    db_url = f"sqlite:///./{settings.DB_PATH}"  # Relative: ensure ./

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False}
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
