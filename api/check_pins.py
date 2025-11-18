#!/usr/bin/env python3
"""Check invite_pins and users tables."""
import sqlite3

conn = sqlite3.connect('/data/workledger.db')
cursor = conn.cursor()

print("=== INVITE_PINS TABLE ===")
pins = cursor.execute("SELECT id, code, role, expires_at, used_by, used_at FROM invite_pins").fetchall()
for row in pins:
    print(f"ID={row[0]}, Code={row[1]}, Role={row[2]}, Expires={row[3]}, UsedBy={row[4]}, UsedAt={row[5]}")

print("\n=== USERS TABLE ===")
users = cursor.execute("SELECT id, telegram_id, role, created_at FROM users").fetchall()
if users:
    for row in users:
        print(f"ID={row[0]}, TelegramID={row[1]}, Role={row[2]}, Created={row[3]}")
else:
    print("(empty)")

conn.close()
