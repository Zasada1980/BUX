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
    # 0. Create tables if not exist (for E2E compatibility)
    # ═══════════════════════════════════════════════════════════════════
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            telegram_username TEXT,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'worker',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS auth_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (employee_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

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
        INSERT INTO auth_credentials (employee_id, username, password_hash, failed_attempts)
        VALUES (1, "admin", "$2b$12$eDbfxvZxZrkDABJUsIXskerQYs0DtXu757Ij9nRLAydsHbmy1jkYe", 0)
    """)

    print("    ✅ Admin auth created (username=admin, password=admin123)")

    # ═══════════════════════════════════════════════════════════════════
    # 3. Bot commands (for bot-menu-config tests)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating bot commands...")

    cur.execute("DELETE FROM bot_commands")

    # New schema: command_key, telegram_command, label, role, enabled, is_core, position, command_type
    bot_commands_data = [
        ("start", "/start", "Start", "worker", 1, 0, 0, "slash", "Начать работу"),
        ("end", "/end", "End", "worker", 1, 0, 1, "slash", "Завершить смену"),
        ("status", "/status", "Status", "worker", 1, 0, 2, "slash", "Статус текущей смены"),
        ("report", "/report", "Report", "foreman", 1, 0, 0, "slash", "Сформировать отчёт"),
        ("approve", "/approve", "Approve", "admin", 1, 0, 0, "slash", "Утвердить изменения"),
    ]

    cur.executemany("""
        INSERT INTO bot_commands (command_key, telegram_command, label, role, enabled, is_core, position, command_type, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, bot_commands_data)

    print(f"    ✅ {len(bot_commands_data)} bot commands created")

    # ═══════════════════════════════════════════════════════════════════
    # 4. Shifts (for shifts-review-smoke tests)
    # ═══════════════════════════════════════════════════════════════════
    # 4. Shifts (minimal for E2E tests)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating shifts...")

    cur.execute("DELETE FROM shifts")

    # Real schema: id, user_id, status, created_at, ended_at
    shifts_data = [
        (1, "111111", "completed", "2025-11-20 08:00:00", "2025-11-20 17:00:00"),
        (2, "222222", "open", "2025-11-21 09:00:00", None),
        (3, "111111", "open", "2025-11-19 10:00:00", None),
    ]

    cur.executemany("""
        INSERT INTO shifts (id, user_id, status, created_at, ended_at)
        VALUES (?, ?, ?, ?, ?)
    """, shifts_data)

    print(f"    ✅ {len(shifts_data)} shifts created")

    # ═══════════════════════════════════════════════════════════════════
    # 5. Expenses (for expenses-filter-csv tests)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating expenses...")

    cur.execute("DELETE FROM expenses")

    expenses_data = [
        (1, "111111", 1, "transport", 50.0, "ILS", None, None, "2025-11-20 10:00:00", 1, "manual"),
        (2, "111111", 1, "food", 30.0, "ILS", None, None, "2025-11-20 12:00:00", 1, "manual"),
        (3, "222222", 2, "materials", 100.0, "ILS", None, None, "2025-11-21 11:00:00", 0, "manual"),
        (4, "111111", None, "other", 20.0, "ILS", None, None, "2025-11-19 14:00:00", 1, "manual"),
    ]

    cur.executemany("""
        INSERT INTO expenses (id, worker_id, shift_id, category, amount, currency, photo_ref, ocr_text, created_at, confirmed, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, expenses_data)

    print(f"    ✅ {len(expenses_data)} expenses created")

    # ═══════════════════════════════════════════════════════════════════
    # 6. Invoices (for invoices-review-csv tests)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating invoices...")

    cur.execute("DELETE FROM invoices")

    invoices_data = [
        (1, "client1", "2025-11-01", "2025-11-15", "1500.00", "ILS", "draft", 1, None, None, "2025-11-20 09:00:00"),
        (2, "client2", "2025-11-01", "2025-11-15", "2000.00", "ILS", "sent", 1, None, None, "2025-11-19 10:00:00"),
        (3, "client1", "2025-11-16", "2025-11-30", "1800.00", "ILS", "paid", 1, None, None, "2025-11-18 11:00:00"),
    ]

    cur.executemany("""
        INSERT INTO invoices (id, client_id, period_from, period_to, total, currency, status, version, pdf_path, xlsx_path, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, invoices_data)

    print(f"    ✅ {len(invoices_data)} invoices created")

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
    print(f"   - Shifts: {len(shifts_data)}")
    print(f"   - Expenses: {len(expenses_data)}")
    print(f"   - Invoices: {len(invoices_data)}")
    print("\n💡 Ready for E2E tests (bot-menu, user-management, auth, expenses, invoices, shifts)")


if __name__ == "__main__":
    seed_minimal()
