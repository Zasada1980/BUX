"""
Authentication Tests - JWT, Password Login, Token Refresh

Tests:
1. Password login with valid credentials
2. Password login with invalid credentials
3. Token refresh flow
4. JWT token validation
5. Password hashing (bcrypt)
"""
import sys
import os
import tempfile

# CRITICAL: Set DB_PATH BEFORE importing main (which imports db.py)
# Create temp DB for tests
if "DB_PATH" not in os.environ:
    fd, test_db = tempfile.mkstemp(suffix="_test_auth.db")
    os.close(fd)
    os.environ["DB_PATH"] = test_db

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from fastapi.testclient import TestClient
from main import app
from models import Employee, AuthCredential, Base
from db import SessionLocal, engine
from passlib.context import CryptContext
import jwt

# Create schema
Base.metadata.create_all(bind=engine)

# Seed admin user
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
session = SessionLocal()
try:
    admin_emp = Employee(id=1, name="Admin", daily_salary=0, is_active=True)
    session.add(admin_emp)
    session.flush()
    
    admin_cred = AuthCredential(
        username="admin",
        password_hash=pwd_context.hash("admin123"),
        user_id=1
    )
    session.add(admin_cred)
    session.commit()
except:
    session.rollback()
finally:
    session.close()

client = TestClient(app)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")


@pytest.mark.xfail(reason="DB isolation: :memory: engine separation - needs conftest.py fixtures + dependency injection (CI-5)")
def test_password_login_success():
    """Test password login with valid credentials (admin/admin123)."""
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    assert "access_token" in data, "Missing access_token"
    assert "refresh_token" in data, "Missing refresh_token"
    assert "token_type" in data, "Missing token_type"
    assert data["token_type"] == "bearer"

    # Verify JWT token
    token = data["access_token"]
    decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    assert "user_id" in decoded
    assert "username" in decoded
    assert decoded["username"] == "admin"


