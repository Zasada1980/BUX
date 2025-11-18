"""Sprint D Bot - Configuration and utilities."""
import os
import json
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# Load .env.bot from current directory
env_path = Path(__file__).parent.parent / ".env.bot"
load_dotenv(env_path)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
BOT_ADMINS = {int(x.strip()) for x in os.getenv("BOT_ADMINS", "").split(",") if x.strip().isdigit()}
BOT_FOREMEN = {int(x.strip()) for x in os.getenv("BOT_FOREMEN", "").split(",") if x.strip().isdigit()}
BOT_WORKERS = {int(x.strip()) for x in os.getenv("BOT_WORKERS", "").split(",") if x.strip().isdigit()}
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8088/api")
AGENT_URL = os.getenv("AGENT_URL", "http://127.0.0.1:8081")
INTERNAL_API_TOKEN = os.getenv("INTERNAL_API_TOKEN", "dev-token-placeholder")  # For APIClient auth
BOT_FLOOD_LIMIT = int(os.getenv("BOT_FLOOD_LIMIT", "3"))
DEV_MODE = os.getenv("DEV_MODE", "true").lower() == "true"
BOT_METRICS_DIR = Path("logs/bot/metrics")
BOT_METRICS_DIR.mkdir(parents=True, exist_ok=True)

# AI Categorization
AI_AGENT_BASE = os.getenv("AI_AGENT_BASE", "")
AI_EXPENSE_CONF = float(os.getenv("AI_EXPENSE_CONF", "0.75"))

# INFRA-1: Database connection for dynamic RBAC
DB_PATH = os.getenv("DB_PATH", "/app/db/shifts.db")  # Single unified DB path (DEMO: /app/db/shifts.db)
_db_engine = None
_SessionLocal = None

def get_db():
    """Generator for database sessions (for bot handlers)"""
    db = get_db_session()
    try:
        yield db
    finally:
        db.close()

def get_db_session() -> Session:
    """Get database session for RBAC lookups."""
    global _db_engine, _SessionLocal
    if _db_engine is None:
        _db_engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
        _SessionLocal = sessionmaker(bind=_db_engine, autoflush=False, autocommit=False)
    return _SessionLocal()

# Throttling state (in-memory for dev)
_throttle_state = {}


def throttle_check(user_id: int, action: str, window: float = 2.0) -> bool:
    """Check if user is sending requests too fast. Returns True if should throttle."""
    now = time.monotonic()
    key = (user_id, action)
    if key in _throttle_state and now - _throttle_state[key] < window:
        return True
    _throttle_state[key] = now
    return False


def record_bot_metric(event_name: str, fields: dict):
    """Record bot metric to JSONL."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    metric_file = BOT_METRICS_DIR / f"{today}.jsonl"
    
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": f"bot.{event_name}",
        **fields
    }
    
    with open(metric_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def generate_request_id() -> str:
    return f"BOT-{uuid.uuid4().hex[:12]}"


def is_admin(telegram_id: int) -> bool:
    """
    INFRA-1: Check if user is admin (DB-first with env fallback).
    Returns True if telegram_id has 'admin' role in DB or is in BOT_ADMINS env var.
    """
    # First try DB
    try:
        session = get_db_session()
        try:
            from api.crud_users import User
            user = session.query(User).filter_by(
                telegram_id=telegram_id,
                active=True
            ).first()
            if user and user.role == "admin":
                return True
        finally:
            session.close()
    except Exception:
        pass  # Fallback to env vars
    
    # Fallback to env vars (backward compatibility)
    return telegram_id in BOT_ADMINS


def is_foreman(telegram_id: int) -> bool:
    """
    INFRA-1: Check if user is foreman (DB-first with env fallback).
    Admins are also foremen.
    """
    if is_admin(telegram_id):
        return True
    
    # Try DB
    try:
        session = get_db_session()
        try:
            from api.crud_users import User
            user = session.query(User).filter_by(
                telegram_id=telegram_id,
                active=True
            ).first()
            if user and user.role in ("foreman", "admin"):
                return True
        finally:
            session.close()
    except Exception:
        pass
    
    # Fallback to env vars
    return telegram_id in BOT_FOREMEN


def is_worker(telegram_id: int) -> bool:
    """
    INFRA-1: Check if user is worker (DB-first with env fallback).
    Foremen and admins are also workers.
    """
    if is_foreman(telegram_id):
        return True
    
    # Try DB
    try:
        session = get_db_session()
        try:
            from api.crud_users import User
            user = session.query(User).filter_by(
                telegram_id=telegram_id,
                active=True
            ).first()
            if user:  # Any active user with telegram_id is a worker
                return True
        finally:
            session.close()
    except Exception:
        pass
    
    # Fallback to env vars
    return telegram_id in BOT_WORKERS
