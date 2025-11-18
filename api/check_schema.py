#!/usr/bin/env python3
"""Check invite_pins schema."""
import sqlite3

conn = sqlite3.connect('/data/workledger.db')
cursor = conn.cursor()

# Get table DDL
schema = cursor.execute("SELECT sql FROM sqlite_master WHERE name='invite_pins'").fetchone()
if schema:
    print("=== TABLE SCHEMA ===")
    print(schema[0])
    print()

# Get indexes
indexes = cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='invite_pins'").fetchall()
if indexes:
    print("=== INDEXES ===")
    for idx_name, idx_sql in indexes:
        print(f"{idx_name}: {idx_sql}")
    print()

# Test UNIQUE constraint on code
print("=== UNIQUE CONSTRAINT TEST ===")
try:
    cursor.execute("INSERT INTO invite_pins (code, role, expires_at) VALUES ('TEST001', 'worker', datetime('now', '+48 hours'))")
    cursor.execute("INSERT INTO invite_pins (code, role, expires_at) VALUES ('TEST001', 'admin', datetime('now', '+48 hours'))")
    print("FAIL: Duplicate code allowed")
except sqlite3.IntegrityError as e:
    print(f"PASS: Duplicate rejected - {e}")
    conn.rollback()

# Test CHECK constraint on role
print("\n=== CHECK CONSTRAINT TEST ===")
try:
    cursor.execute("INSERT INTO invite_pins (code, role, expires_at) VALUES ('TEST002', 'invalid_role', datetime('now', '+48 hours'))")
    print("FAIL: Invalid role allowed")
except sqlite3.IntegrityError as e:
    print(f"PASS: Invalid role rejected - {e}")
    conn.rollback()

conn.close()
