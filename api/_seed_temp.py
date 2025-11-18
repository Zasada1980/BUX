import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, TelegramUser
from dotenv import load_dotenv

# Load .env.bot
load_dotenv(".env.bot")

# DB connection
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./data/shifts.db")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(bind=engine)

def parse_telegram_ids(env_var):
    value = os.getenv(env_var, "")
    return {int(x.strip()) for x in value.split(",") if x.strip().isdigit()}

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
    print(f"\n📋 Existing users in DB: {len(existing_ids)}")
    
    # Seed admins
    for telegram_id in admins:
        if telegram_id in existing_ids:
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
    
    # Seed foremen (skip if already admin)
    for telegram_id in foremen:
        if telegram_id in existing_ids or telegram_id in admins:
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
    
    # Seed workers (skip if already admin or foreman)
    for telegram_id in workers:
        if telegram_id in existing_ids or telegram_id in admins or telegram_id in foremen:
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
    print(f"\n✅ SEED COMPLETE - Total users: {total}")
    
    # Show all users
    all_users = session.query(TelegramUser).all()
    for u in all_users:
        print(f"  • {u.role.upper()}: TG ID {u.telegram_id} → User ID {u.user_id}")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    session.rollback()
finally:
    session.close()
