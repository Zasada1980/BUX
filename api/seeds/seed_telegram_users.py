"""
Seed script for INFRA-1: Migrate existing users from env vars to telegram_users table.

Usage:
    docker compose exec api python seeds/seed_telegram_users.py

This script:
1. Reads BOT_ADMINS, BOT_FOREMEN, BOT_WORKERS from .env.bot
2. Creates telegram_users entries for existing users
3. Maintains backward compatibility (bot will check DB first, then env vars)
"""
import os
import sys
from pathlib import Path

# Import from api directory (works in container)
sys.path.insert(0, "/app")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from api.models import Base, TelegramUser
from dotenv import load_dotenv

# Load .env.bot
env_path = "/app/.env.bot"
load_dotenv(env_path)

# DB connection
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./data/shifts.db")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)


def parse_telegram_ids(env_var: str) -> set:
    """Parse comma-separated Telegram IDs from env var."""
    value = os.getenv(env_var, "")
    return {int(x.strip()) for x in value.split(",") if x.strip().isdigit()}


def seed_telegram_users():
    """Seed telegram_users table from env vars."""
    
    # Parse env vars
    admins = parse_telegram_ids("BOT_ADMINS")
    foremen = parse_telegram_ids("BOT_FOREMEN")
    workers = parse_telegram_ids("BOT_WORKERS")
    
    print(f"📊 Found in env vars:")
    print(f"  • Admins: {len(admins)} ({admins})")
    print(f"  • Foremen: {len(foremen)} ({foremen})")
    print(f"  • Workers: {len(workers)} ({workers})")
    
    session = SessionLocal()
    try:
        # Check existing users
        existing = session.query(TelegramUser.telegram_id).all()
        existing_ids = {row[0] for row in existing}
        print(f"\n📋 Existing users in DB: {len(existing_ids)} ({existing_ids})")
        
        # Seed admins
        for telegram_id in admins:
            if telegram_id in existing_ids:
                print(f"  ⏭️  Admin {telegram_id} already exists, skipping")
                continue
            
            user = TelegramUser(
                telegram_id=telegram_id,
                user_id=f"admin_{telegram_id}",
                role="admin",
                display_name=f"Admin {telegram_id}",
                is_active=1
            )
            session.add(user)
            print(f"  ✅ Created admin: {telegram_id}")
        
        # Seed foremen
        for telegram_id in foremen:
            if telegram_id in existing_ids or telegram_id in admins:
                print(f"  ⏭️  Foreman {telegram_id} already exists or is admin, skipping")
                continue
            
            user = TelegramUser(
                telegram_id=telegram_id,
                user_id=f"foreman_{telegram_id}",
                role="foreman",
                display_name=f"Foreman {telegram_id}",
                is_active=1
            )
            session.add(user)
            print(f"  ✅ Created foreman: {telegram_id}")
        
        # Seed workers
        for telegram_id in workers:
            if telegram_id in existing_ids or telegram_id in admins or telegram_id in foremen:
                print(f"  ⏭️  Worker {telegram_id} already exists or has higher role, skipping")
                continue
            
            user = TelegramUser(
                telegram_id=telegram_id,
                user_id=f"worker_{telegram_id}",
                role="worker",
                display_name=f"Worker {telegram_id}",
                is_active=1
            )
            session.add(user)
            print(f"  ✅ Created worker: {telegram_id}")
        
        session.commit()
        
        # Verify
        total = session.query(TelegramUser).count()
        print(f"\n✅ SEED COMPLETE")
        print(f"  • Total users in DB: {total}")
        
        # Show all users
        all_users = session.query(TelegramUser).all()
        print(f"\n📋 All users:")
        for u in all_users:
            print(f"  • {u.role.upper()}: Telegram ID {u.telegram_id} → User ID {u.user_id}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("🌱 INFRA-1: Seeding telegram_users from env vars...\n")
    seed_telegram_users()
