#!/usr/bin/env python3
"""
Minimal E2E seed script for TelegramOllama E2E tests.

Creates minimal test data for:
- Users (table `users`, NOT `employees`)
- Auth credentials (admin/admin123)
- Bot commands (for bot-menu-config tests)

Usage:
    export DB_PATH="db/shifts.e2e.db"
    python -m api.seeds.seed_e2e_minimal
"""
import os
import sqlite3
from datetime import datetime

# Use DB_PATH from env, fallback to default
DB_PATH = os.getenv("DB_PATH", "db/shifts.e2e.db")

def seed_minimal():
    """Seed minimal data for E2E Group A tests."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print(f"🌱 Seeding minimal E2E data to {DB_PATH}...")

    # ═══════════════════════════════════════════════════════════════════
    # 1. Users (table: users, NOT employees!)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating users...")

    # Clear existing
    cur.execute("DELETE FROM users")
    cur.execute("DELETE FROM auth_credentials")

    # Insert users (schema: id, telegram_id, telegram_username, name, role, active)
    users_data = [
        (1, 999999, "admin", "Admin User", "admin", 1),
        (2, 111111, "user1", "User One", "worker", 1),
        (3, 222222, "user2", "User Two", "foreman", 1),
        (4, 333333, "user3", "User Inactive", "worker", 0),
    ]

    cur.executemany("""
        INSERT INTO users (id, telegram_id, telegram_username, name, role, active)
        VALUES (?, ?, ?, ?, ?, ?)
    """, users_data)

    print(f"    ✅ {len(users_data)} users created")

    # ═══════════════════════════════════════════════════════════════════
    # 2. Auth credentials for admin (id=1)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating admin auth credentials...")

    # Password hash for "admin123" (bcrypt)
    cur.execute("""
        INSERT INTO auth_credentials (employee_id, username, password_hash)
        VALUES (1, "admin", "$2b$12$eDbfxvZxZrkDABJUsIXskerQYs0DtXu757Ij9nRLAydsHbmy1jkYe")
    """)

    print("    ✅ Admin auth created (username=admin, password=admin123)")

    # ═══════════════════════════════════════════════════════════════════
    # 3. Bot commands (for bot-menu-config tests)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating bot commands...")

    cur.execute("DELETE FROM bot_commands")

    # New schema: command_key, telegram_command, label, role, enabled, is_core, position, command_type
    bot_commands_data = [
        ("start", "/start", "Start", "worker", 1, 0, 0, "action", "Начать работу"),
        ("end", "/end", "End", "worker", 1, 0, 1, "action", "Завершить смену"),
        ("status", "/status", "Status", "worker", 1, 0, 2, "action", "Статус текущей смены"),
        ("report", "/report", "Report", "foreman", 1, 0, 0, "action", "Сформировать отчёт"),
        ("approve", "/approve", "Approve", "admin", 1, 0, 0, "action", "Утвердить изменения"),
    ]

    cur.executemany("""
        INSERT INTO bot_commands (command_key, telegram_command, label, role, enabled, is_core, position, command_type, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, bot_commands_data)

    print(f"    ✅ {len(bot_commands_data)} bot commands created")

    # ═══════════════════════════════════════════════════════════════════
    # Commit and close
    # ═══════════════════════════════════════════════════════════════════
    conn.commit()
    conn.close()

    print("\n✅ E2E minimal seed completed!")
    print(f"   - DB: {DB_PATH}")
    print(f"   - Users: {len(users_data)} (3 active, 1 inactive)")
    print(f"   - Admin: username=admin, password=admin123")
    print(f"   - Bot commands: {len(bot_commands_data)}")
    print("\n💡 Ready for E2E tests (bot-menu, user-management, auth)")


if __name__ == "__main__":
    seed_minimal()
