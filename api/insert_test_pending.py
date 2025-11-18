#!/usr/bin/env python3
"""Создание тестовой pending записи для S34 smoke-теста."""
import json
from db import SessionLocal
from sqlalchemy import text

def main():
    payload = json.dumps({"title": "test smoke E1", "amount": 100})
    
    with SessionLocal() as s:
        s.execute(text("""
            INSERT INTO pending_changes (kind, payload_json, status)
            VALUES (:kind, :payload, :status)
        """), {"kind": "task.update", "payload": payload, "status": "pending"})
        s.commit()
        print("[OK] Inserted test pending_changes record")

if __name__ == "__main__":
    main()
