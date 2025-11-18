"""
Authentication Tests - JWT, Password Login, Token Refresh

Tests:
1. Password login with valid credentials
2. Password login with invalid credentials
3. Token refresh flow
4. JWT token validation
5. Password hashing (bcrypt)

CI-6: Refactored to use conftest.py fixtures (client, seed_admin, admin_token, db_session).
Removed manual DB setup, engine creation, and admin seed.
All xfail decorators removed - tests now use proper DB isolation.
"""
import pytest
import jwt
import os


def test_password_login_success(client, seed_admin):
    """Test password login with valid credentials (admin/admin123)."""
    user_id, username, password = seed_admin

    response = client.post("/api/auth/login", json={
        "username": username,
        "password": password
    })

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    assert "access_token" in data, "Missing access_token"
    assert "refresh_token" in data, "Missing refresh_token"
    assert "token_type" in data, "Missing token_type"
    assert data["token_type"] == "bearer"

    # Verify JWT structure (3 parts: header.payload.signature)
    token = data["access_token"]
    assert len(token.split(".")) == 3, "Invalid JWT format (should have 3 parts)"


def test_password_login_failure_wrong_password(client, seed_admin):
    """Test password login with wrong password."""
    user_id, username, password = seed_admin

    response = client.post("/api/auth/login", json={
        "username": username,
        "password": "wrongpassword"
    })

    assert response.status_code == 401, f"Expected 401, got {response.status_code}"
    data = response.json()
    assert "detail" in data, "Missing error detail"


def test_password_login_failure_nonexistent_user(client):
    """Test password login with non-existent user."""
    response = client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "anypassword"
    })

    assert response.status_code == 401, f"Expected 401, got {response.status_code}"


def test_token_refresh(client, seed_admin):
    """Test JWT token refresh flow."""
    user_id, username, password = seed_admin

    # Step 1: Login to get refresh token
    login_response = client.post("/api/auth/login", json={
        "username": username,
        "password": password
    })
    assert login_response.status_code == 200
    refresh_token = login_response.json()["refresh_token"]

    # Step 2: Use refresh token to get new access token
    refresh_response = client.post("/api/auth/refresh", json={
        "refresh_token": refresh_token
    })

    assert refresh_response.status_code == 200, f"Refresh failed: {refresh_response.status_code}"
    new_data = refresh_response.json()

    assert "access_token" in new_data, "Missing new access_token"
    assert len(new_data["access_token"]) > 100, "Access token too short"


def test_jwt_token_validation(admin_token):
    """Test JWT token structure and claims."""
    # Decode without verification (check structure only)
    payload = jwt.decode(admin_token, options={"verify_signature": False})
    
    assert "sub" in payload, "Missing 'sub' claim (username)"
    assert "user_id" in payload, "Missing 'user_id' claim"
    assert "role" in payload, "Missing 'role' claim"
    assert "exp" in payload, "Missing 'exp' claim (expiration)"
    
    # Verify username claim (cannot verify signature without knowing SECRET_KEY)
    assert payload["sub"] == "admin", f"Expected sub='admin', got {payload['sub']}"
def test_password_hashing(db_session, seed_admin):
    """Test bcrypt password hashing."""
    from api.models import AuthCredential  # Changed from api.models_users

    user_id, username, password = seed_admin

    # Get admin credential from DB
    cred = db_session.query(AuthCredential).filter_by(username=username).first()
    assert cred is not None, "Admin credentials not found"

    # Check hash format (bcrypt starts with $)
    assert cred.password_hash.startswith("$"), f"Not bcrypt hash: {cred.password_hash[:10]}"

    # Verify password using auth.py
    from api.auth import verify_password
    is_valid = verify_password(password, cred.password_hash)
    assert is_valid, "Password verification failed"

    # Verify wrong password fails
    is_invalid = verify_password("wrongpassword", cred.password_hash)
    assert not is_invalid, "Wrong password should not verify"


def test_protected_endpoint_without_token(client):
    """Test that protected endpoints reject requests without token."""
    response = client.get("/api/employees")
    assert response.status_code in [401, 403], f"Expected 401 or 403, got {response.status_code}"


def test_protected_endpoint_with_valid_token(client, admin_headers):
    """Test that protected endpoints accept valid tokens."""
    response = client.get("/api/employees", headers=admin_headers)

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    # Extract list from paginated response
    if isinstance(data, dict) and 'employees' in data:
        employees = data['employees']
        assert isinstance(employees, list), f"employees field should be a list, got {type(employees).__name__}"
    else:
        assert isinstance(data, list), f"Response should be a list or paginated object, got {type(data).__name__}"
