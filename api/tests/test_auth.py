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
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from main import app
from models import Employee, AuthCredential
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
import jwt
import os

from ._client import build_test_client

client = build_test_client(app)

DB_PATH = "/data/workledger.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key-change-in-production")


def test_password_login_success():
    """Test password login with valid credentials (admin/admin123)."""
    print("🧪 Test 1: Password login SUCCESS...")
    
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    
    assert response.status_code == 200, f"❌ Expected 200, got {response.status_code}"
    data = response.json()
    
    assert "access_token" in data, "❌ Missing access_token"
    assert "refresh_token" in data, "❌ Missing refresh_token"
    assert "token_type" in data, "❌ Missing token_type"
    assert data["token_type"] == "bearer", f"❌ Expected bearer, got {data['token_type']}"
    
    # Validate JWT structure
    token = data["access_token"]
    assert len(token.split(".")) == 3, "❌ Invalid JWT format (should have 3 parts)"
    
    print(f"  ✅ Login successful, token length: {len(token)}")


def test_password_login_failure_wrong_password():
    """Test password login with wrong password."""
    print("🧪 Test 2: Password login FAILURE (wrong password)...")
    
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "wrongpassword"
    })
    
    assert response.status_code == 401, f"❌ Expected 401, got {response.status_code}"
    data = response.json()
    assert "detail" in data, "❌ Missing error detail"
    
    print(f"  ✅ Correctly rejected: {data['detail']}")


def test_password_login_failure_nonexistent_user():
    """Test password login with non-existent user."""
    print("🧪 Test 3: Password login FAILURE (non-existent user)...")
    
    response = client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "anypassword"
    })
    
    assert response.status_code == 401, f"❌ Expected 401, got {response.status_code}"
    print("  ✅ Correctly rejected non-existent user")


def test_token_refresh():
    """Test JWT token refresh flow."""
    print("🧪 Test 4: Token refresh...")
    
    # Step 1: Login to get refresh token
    login_response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]
    
    # Step 2: Use refresh token to get new access token
    refresh_response = client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token
    })
    
    assert refresh_response.status_code == 200, f"❌ Refresh failed: {refresh_response.status_code}"
    new_data = refresh_response.json()
    
    assert "access_token" in new_data, "❌ Missing new access_token"
    assert len(new_data["access_token"]) > 100, "❌ Access token too short"
    
    print("  ✅ Token refresh successful")


def test_jwt_token_validation():
    """Test JWT token structure and claims."""
    print("🧪 Test 5: JWT token validation...")
    
    # Get token
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    token = response.json()["access_token"]
    
    # Decode without verification (just to check structure)
    payload = jwt.decode(token, options={"verify_signature": False})
    
    assert "sub" in payload, "❌ Missing 'sub' claim (username)"
    assert "user_id" in payload, "❌ Missing 'user_id' claim"
    assert "role" in payload, "❌ Missing 'role' claim"
    assert "exp" in payload, "❌ Missing 'exp' claim (expiration)"
    
    assert payload["sub"] == "admin", f"❌ Expected sub='admin', got {payload['sub']}"
    assert payload["role"] == "admin", f"❌ Expected role='admin', got {payload['role']}"
    
    print(f"  ✅ JWT claims valid: sub={payload['sub']}, role={payload['role']}, user_id={payload['user_id']}")


def test_password_hashing():
    """Test bcrypt password hashing."""
    print("🧪 Test 6: Password hashing (bcrypt)...")
    
    session = SessionLocal()
    try:
        # Get admin user's password hash
        creds = session.query(AuthCredential).filter_by(username="admin").first()
        assert creds is not None, "❌ Admin credentials not found"
        
        # Check hash format (bcrypt starts with $2b$)
        assert creds.password_hash.startswith("$2b$"), f"❌ Not bcrypt hash: {creds.password_hash[:10]}"
        
        # Verify password using auth.py function (avoid passlib direct usage)
        from auth import verify_password
        is_valid = verify_password("admin123", creds.password_hash)
        assert is_valid, "❌ Password verification failed"
        
        # Verify wrong password fails
        is_invalid = verify_password("wrongpassword", creds.password_hash)
        assert not is_invalid, "❌ Wrong password should not verify"
        
        print(f"  ✅ Bcrypt hashing works, hash length: {len(creds.password_hash)}")
    finally:
        session.close()


def test_protected_endpoint_without_token():
    """Test that protected endpoints reject requests without token."""
    print("🧪 Test 7: Protected endpoint without token...")
    
    response = client.get("/api/employees")
    assert response.status_code in [401, 403], f"❌ Expected 401 or 403, got {response.status_code}"
    
    print(f"  ✅ Correctly blocked unauthenticated request (HTTP {response.status_code})")


def test_protected_endpoint_with_valid_token():
    """Test that protected endpoints accept valid tokens."""
    print("🧪 Test 8: Protected endpoint with valid token...")
    
    # Login
    login_response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    token = login_response.json()["access_token"]
    
    # Access protected endpoint
    response = client.get("/api/employees", headers={
        "Authorization": f"Bearer {token}"
    })
    
    assert response.status_code == 200, f"❌ Expected 200, got {response.status_code}"
    data = response.json()
    
    # Extract list from paginated response
    if isinstance(data, dict) and 'employees' in data:
        employees = data['employees']
        assert isinstance(employees, list), f"❌ employees field should be a list, got {type(employees).__name__}"
        print(f"  ✅ Protected endpoint accessible with token, returned {len(employees)} employees")
    else:
        assert isinstance(data, list), f"❌ Response should be a list or paginated object, got {type(data).__name__}"
        print(f"  ✅ Protected endpoint accessible with token, returned {len(data)} employees")
    
    print(f"  ✅ Protected endpoint accessible with token, returned {len(data)} employees")


if __name__ == "__main__":
    print("=" * 60)
    print("AUTHENTICATION TESTS")
    print("=" * 60)
    
    test_password_login_success()
    test_password_login_failure_wrong_password()
    test_password_login_failure_nonexistent_user()
    test_token_refresh()
    test_jwt_token_validation()
    test_password_hashing()
    test_protected_endpoint_without_token()
    test_protected_endpoint_with_valid_token()
    
    print("\n" + "=" * 60)
    print("✅ ALL AUTHENTICATION TESTS PASSED")
    print("=" * 60)
