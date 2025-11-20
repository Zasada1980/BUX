#!/usr/bin/env python3
"""
CI-11: Fix admin role to 'admin' (from 'foreman').
Runs before each E2E test to ensure admin user has correct role.
"""
import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "db/shifts.db")

def fix_admin_role():
    """Set user id=1 role to 'admin' and active=1."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("UPDATE users SET role='admin', active=1 WHERE id=1")
    conn.commit()
    
    # Verify
    cur.execute("SELECT id, role, active FROM users WHERE id=1")
    result = cur.fetchone()
    conn.close()
    
    print(f"✅ Admin fixed: id={result[0]}, role={result[1]}, active={result[2]}")

if __name__ == "__main__":
    fix_admin_role()
