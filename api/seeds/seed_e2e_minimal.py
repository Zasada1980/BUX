#!/usr/bin/env python3
"""
Minimal E2E seed script for F4.3.2+ Group A scenarios.

Creates minimal test data for:
- Scenario 1: Inbox Bulk Approve (pending_changes)
- Scenario 3: Expense Filtering (expenses)
- Scenario 4: Invoice Review (invoices)
- Scenario 9: Profile Password Change (employees with auth_credentials)

Usage:
    cd TelegramOllama/api
    docker compose exec api python /app/seeds/seed_e2e_minimal.py
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = "/app/db/shifts.db"


def seed_minimal():
    """Seed minimal data for E2E Group A tests."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("🌱 Seeding minimal E2E data...")
    
    # ═══════════════════════════════════════════════════════════════════
    # 1. Admin user for Profile scenario (Scenario 9)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating admin user...")
    
    # Check if admin exists (telegram_id=999999 as placeholder for web-only admin)
    cur.execute("SELECT id FROM employees WHERE telegram_id = ?", (999999,))
    admin = cur.fetchone()
    
    if not admin:
        cur.execute("""
            INSERT INTO employees (telegram_id, full_name, role, is_active, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (999999, "Admin User", "admin", 1, datetime.now().isoformat()))
        admin_id = cur.lastrowid
    else:
        admin_id = admin[0]
    
    # Add auth credentials (password: admin123)
    # Generated via: bcrypt.hashpw(b'admin123', bcrypt.gensalt())
    cur.execute("DELETE FROM auth_credentials WHERE employee_id = ?", (admin_id,))
    cur.execute("""
        INSERT INTO auth_credentials (employee_id, username, password_hash, failed_attempts, locked_until)
        VALUES (?, ?, ?, ?, ?)
    """, (
        admin_id,
        "admin",
        "$2b$12$eDbfxvZxZrkDABJUsIXskerQYs0DtXu757Ij9nRLAydsHbmy1jkYe",  # admin123
        0,  # Reset failed attempts
        None  # Unlock account
    ))
    
    print(f"    ✅ Admin user created (id={admin_id}, username=admin, password=admin123)")
    
    # ═══════════════════════════════════════════════════════════════════
    # 1B. Users for User Management scenario (Scenario 2) — F13 E2E Seed Fix
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating test users for User Management E2E...")
    
    users_data = [
        {
            "telegram_id": 111111,
            "telegram_username": "admin_user",
            "name": "Admin User",
            "instagram_nickname": None,
            "phone": "+972501111111",
            "daily_salary": 500.0,
            "role": "admin",
            "active": True
        },
        {
            "telegram_id": 222222,
            "telegram_username": "foreman_user",
            "name": "Foreman User",
            "instagram_nickname": "@foreman_insta",
            "phone": "+972502222222",
            "daily_salary": 400.0,
            "role": "foreman",
            "active": True
        },
        {
            "telegram_id": 333333,
            "telegram_username": "worker_one",
            "name": "Worker One",
            "instagram_nickname": "@worker1_insta",
            "phone": "+972503333333",
            "daily_salary": 300.0,
            "role": "worker",
            "active": True
        },
        {
            "telegram_id": 444444,
            "telegram_username": "worker_two",
            "name": "Worker Two",
            "instagram_nickname": None,
            "phone": None,
            "daily_salary": 280.0,
            "role": "worker",
            "active": False  # Inactive user for toggle test
        }
    ]
    
    user_ids = []
    for user_data in users_data:
        cur.execute("""
            INSERT INTO users (
                telegram_id, telegram_username, name, instagram_nickname,
                phone, daily_salary, role, active, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_data["telegram_id"],
            user_data["telegram_username"],
            user_data["name"],
            user_data["instagram_nickname"],
            user_data["phone"],
            user_data["daily_salary"],
            user_data["role"],
            1 if user_data["active"] else 0,  # Convert boolean to SQLite int (1/0)
            datetime.now().isoformat()
        ))
        user_ids.append(cur.lastrowid)
    
    print(f"    ✅ 4 test users created (ids={user_ids}, roles: admin/foreman/worker/worker)")
    
    # ═══════════════════════════════════════════════════════════════════
    # 2. Pending items for Inbox scenario (Scenario 1)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating pending items...")
    
    # Pending task
    cur.execute("""
        INSERT INTO pending_changes (kind, payload_json, status, actor, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "task",
        json.dumps({
            "description": "E2E Test Task - Paint fence",
            "hours": 8,
            "shift_id": 1
        }),
        "pending",
        "worker1",
        datetime.now().isoformat()
    ))
    task_id = cur.lastrowid
    
    # Pending expense
    cur.execute("""
        INSERT INTO pending_changes (kind, payload_json, status, actor, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "expense",
        json.dumps({
            "amount": 150.0,
            "category": "materials",
            "description": "E2E Test Expense - Wood planks"
        }),
        "pending",
        "worker2",
        datetime.now().isoformat()
    ))
    expense_pending_id = cur.lastrowid
    
    # Pending shift extension
    cur.execute("""
        INSERT INTO pending_changes (kind, payload_json, status, actor, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        "shift_extension",
        json.dumps({
            "shift_id": 1,
            "extra_hours": 2,
            "reason": "E2E Test - Overtime for urgent repair"
        }),
        "pending",
        "worker1",
        (datetime.now() - timedelta(hours=2)).isoformat()
    ))
    shift_pending_id = cur.lastrowid
    
    print(f"    ✅ 3 pending items created (task={task_id}, expense={expense_pending_id}, shift={shift_pending_id})")
    
    # ═══════════════════════════════════════════════════════════════════
    # 3. Expenses for filtering scenario (Scenario 3)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating expenses...")
    
    expenses_data = [
        {
            "worker_id": "worker1",
            "category": "transport",
            "amount": 45.0,
            "currency": "ILS",
            "photo_ref": "/uploads/receipt1.jpg",
            "ocr_text": "E2E Taxi receipt - Airport to site",
            "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
            "confirmed": 1,
            "source": "telegram"
        },
        {
            "worker_id": "worker2",
            "category": "materials",
            "amount": 320.0,
            "currency": "ILS",
            "photo_ref": "/uploads/receipt2.jpg",
            "ocr_text": "E2E Hardware store - Screws and nails",
            "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
            "confirmed": 1,
            "source": "telegram"
        },
        {
            "worker_id": "worker3",
            "category": "food",
            "amount": 65.0,
            "currency": "ILS",
            "photo_ref": None,
            "ocr_text": None,
            "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "confirmed": 0,
            "source": "web"
        },
        {
            "worker_id": "worker1",
            "category": "tools",
            "amount": 180.0,
            "currency": "ILS",
            "photo_ref": "/uploads/receipt3.jpg",
            "ocr_text": "E2E Drill rental - 3 days",
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
            "confirmed": 1,
            "source": "telegram"
        },
        {
            "worker_id": "worker2",
            "category": "transport",
            "amount": 25.0,
            "currency": "ILS",
            "photo_ref": None,
            "ocr_text": None,
            "created_at": datetime.now().isoformat(),
            "confirmed": 0,
            "source": "web"
        }
    ]
    
    expense_ids = []
    for exp in expenses_data:
        cur.execute("""
            INSERT INTO expenses (
                worker_id, shift_id, category, amount, currency,
                photo_ref, ocr_text, created_at, confirmed, source
            )
            VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            exp["worker_id"], exp["category"], exp["amount"], exp["currency"],
            exp["photo_ref"], exp["ocr_text"], exp["created_at"],
            exp["confirmed"], exp["source"]
        ))
        expense_ids.append(cur.lastrowid)
    
    print(f"    ✅ 5 expenses created (ids={expense_ids})")
    
    # ═══════════════════════════════════════════════════════════════════
    # 4. Invoices for review scenario (Scenario 4)
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating invoices...")
    
    invoices_data = [
        {
            "client_id": "ABC Construction Ltd",
            "period_from": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
            "period_to": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "total": 12500.0,
            "currency": "ILS",
            "status": "paid",
            "version": 1,
            "created_at": (datetime.now() - timedelta(days=25)).isoformat()
        },
        {
            "client_id": "XYZ Developers",
            "period_from": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            "period_to": (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"),
            "total": 8750.0,
            "currency": "ILS",
            "status": "pending",
            "version": 1,
            "created_at": (datetime.now() - timedelta(days=12)).isoformat()
        },
        {
            "client_id": "BuildPro Inc",
            "period_from": (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"),
            "period_to": (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d"),
            "total": 15600.0,
            "currency": "ILS",
            "status": "issued",
            "version": 2,
            "created_at": (datetime.now() - timedelta(days=18)).isoformat()
        },
        {
            "client_id": "ABC Construction Ltd",
            "period_from": (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d"),
            "period_to": datetime.now().strftime("%Y-%m-%d"),
            "total": 9200.0,
            "currency": "ILS",
            "status": "draft",
            "version": 1,
            "created_at": (datetime.now() - timedelta(days=2)).isoformat()
        }
    ]
    
    invoice_ids = []
    for inv in invoices_data:
        cur.execute("""
            INSERT INTO invoices (
                client_id, period_from, period_to, total, currency,
                status, version, pdf_path, xlsx_path, created_at, current_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
        """, (
            inv["client_id"], inv["period_from"], inv["period_to"],
            inv["total"], inv["currency"], inv["status"], inv["version"],
            inv["created_at"], inv["version"]
        ))
        invoice_ids.append(cur.lastrowid)
    
    print(f"    ✅ 4 invoices created (ids={invoice_ids})")
    
    # ═══════════════════════════════════════════════════════════════════
    # 5. Shifts for Shift Review scenario (Scenario 5 - F5.2)
    #    Uses first user (Admin User) for shifts
    # ═══════════════════════════════════════════════════════════════════
    print("  📝 Creating completed shifts...")
    
    # Use first user (telegram_id=111111) for shifts
    worker_user_telegram_id = "111111"
    shifts_data = [
        {"user_id": worker_user_telegram_id, "status": "completed", "created_at": (datetime.now() - timedelta(days=3)).isoformat(), "ended_at": (datetime.now() - timedelta(days=3, hours=-8)).isoformat()},
        {"user_id": worker_user_telegram_id, "status": "completed", "created_at": (datetime.now() - timedelta(days=2)).isoformat(), "ended_at": (datetime.now() - timedelta(days=2, hours=-7)).isoformat()},
        {"user_id": worker_user_telegram_id, "status": "open", "created_at": (datetime.now() - timedelta(hours=2)).isoformat(), "ended_at": None},
    ]
    
    shift_ids = []
    for s in shifts_data:
        cur.execute("""
            INSERT INTO shifts (user_id, status, created_at, ended_at)
            VALUES (?, ?, ?, ?)
        """, (s["user_id"], s["status"], s["created_at"], s["ended_at"]))
        shift_ids.append(cur.lastrowid)
    
    print(f"    ✅ {len(shift_ids)} shifts created ({len([s for s in shifts_data if s['status'] == 'completed'])} completed, 1 open)")
    
    # ═══════════════════════════════════════════════════════════════════
    # Commit and close
    # ═══════════════════════════════════════════════════════════════════
    conn.commit()
    conn.close()
    
    print("\n✅ E2E minimal seed completed!")
    print(f"   - Admin: username=admin, password=admin123")
    print(f"   - Test users: {len(user_ids)} users (3 active, 1 inactive) — telegram_ids: 111111-444444")
    print(f"   - Pending items: {task_id}, {expense_pending_id}, {shift_pending_id}")
    print(f"   - Expenses: {len(expense_ids)} items")
    print(f"   - Invoices: {len(invoice_ids)} items")
    print(f"   - Shifts: {len(shift_ids)} shifts (2 completed, 1 open)")
    print("\n💡 Ready for E2E tests (Scenarios 1/2/3/4/5/9)")


if __name__ == "__main__":
    seed_minimal()
