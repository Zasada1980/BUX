"""Pytest helpers for deterministic integration tests."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
import bcrypt

ROOT_DIR = Path(__file__).resolve().parent
API_DIR = ROOT_DIR / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

TEST_DB_PATH = Path("/data/workledger.db")
APP_DB_PATH = Path(os.getenv("APP_DB_PATH", "/app/db/shifts.db"))

os.environ.setdefault("DB_PATH", str(TEST_DB_PATH))

from models import Base, Employee, AuthCredential, TelegramUser  # noqa: E402


def _prepare_database() -> None:
    """Create SQLite database with seed data for API tests."""
    TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        admin = session.query(Employee).filter(Employee.id == 1).first()
        if not admin:
            admin = Employee(
                full_name="Admin User",
                role="admin",
                telegram_id=8473812812,
                is_active=True,
            )
            session.add(admin)
            session.flush()
        else:
            admin.full_name = admin.full_name or "Admin User"
            admin.role = "admin"
            admin.is_active = True
            if not admin.telegram_id:
                admin.telegram_id = 8473812812

        password_hash = bcrypt.hashpw(b"admin123", bcrypt.gensalt(rounds=12)).decode("utf-8")

        cred = session.query(AuthCredential).filter_by(username="admin").first()
        if not cred:
            cred = AuthCredential(
                employee_id=admin.id,
                username="admin",
                password_hash=password_hash,
                failed_attempts=0,
            )
            session.add(cred)
        else:
            cred.employee_id = admin.id
            cred.password_hash = password_hash
            cred.failed_attempts = 0
            cred.locked_until = None

        if not session.query(TelegramUser).filter_by(telegram_id=8473812812).first():
            session.add(
                TelegramUser(
                    telegram_id=8473812812,
                    user_id="admin_8473812812",
                    role="admin",
                    display_name="Admin User",
                    is_active=1,
                )
            )

        session.commit()

    # Keep legacy path in sync for docs/scripts that still point to /app/db/shifts.db
    try:
        if APP_DB_PATH.exists() or APP_DB_PATH.is_symlink():
            APP_DB_PATH.unlink()
    except FileNotFoundError:
        pass

    try:
        APP_DB_PATH.symlink_to(TEST_DB_PATH)
    except FileExistsError:
        pass
    except OSError:
        # Fall back to copying if filesystem disallows symlinks
        import shutil

        shutil.copyfile(TEST_DB_PATH, APP_DB_PATH)


_prepare_database()
