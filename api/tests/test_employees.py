"""
Employee CRUD Tests - Create, Read, Update, Delete, RBAC

Tests:
1. List all employees
2. Get employee by ID
3. Create new employee
4. Update employee
5. Soft delete employee (is_active=False)
6. RBAC: Admin can create, foreman can read only

CI-6: Refactored to use conftest.py fixtures (client, admin_headers).
Removed manual DB setup, engine creation, get_admin_token() helper.
All xfail decorators removed - tests now use proper DB isolation.
"""
import pytest
import random


def test_list_employees(client, admin_headers):
    """Test GET /api/employees - List all employees."""
    response = client.get("/api/employees", headers=admin_headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    
    # Handle paginated response
    if isinstance(data, dict) and 'employees' in data:
        employees = data['employees']
    else:
        employees = data
    
    assert isinstance(employees, list), "Response should be list"
    assert len(employees) >= 1, "Should have at least admin user"
    
    # Check structure
    admin = employees[0]
    assert "id" in admin, "Missing 'id' field"
    assert "name" in admin, "Missing 'name' field (F14 schema)"  # Changed from full_name
    assert "role" in admin, "Missing 'role' field"
    assert "active" in admin, "Missing 'active' field (F14 schema)"  # Changed from is_active


def test_get_employee_by_id(client, admin_headers):
    """Test GET /api/employees/{id} - Get employee by ID."""
    # Get admin user (ID=1)
    response = client.get("/api/employees/1", headers=admin_headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    employee = response.json()
    
    assert employee["id"] == 1, f"Expected id=1, got {employee['id']}"
    assert employee["role"] == "admin", f"Expected role='admin', got {employee['role']}"


def test_get_nonexistent_employee(client, admin_headers):
    """Test GET /api/employees/{id} - Non-existent employee returns 404."""
    response = client.get("/api/employees/99999", headers=admin_headers)
    
    assert response.status_code == 404, f"Expected 404, got {response.status_code}"


def test_create_employee(client, admin_headers):
    """Test POST /api/employees - Create new employee."""
    # Use random telegram_id to avoid conflicts between test runs
    telegram_id = random.randint(100000000, 999999999)
    
    new_employee = {
        "name": "Test Worker",  # F14: Changed from full_name
        "role": "worker",
        "telegram_id": telegram_id,
        "password": "worker123"
    }
    
    response = client.post("/api/employees", json=new_employee, headers=admin_headers)
    
    assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
    created = response.json()
    
    assert "id" in created, "Missing 'id' in response"
    assert created["name"] == "Test Worker"  # F14: Changed from full_name
    assert created["role"] == "worker"
    assert created["active"] is True  # F14: Changed from is_active


def test_update_employee(client, admin_headers):
    """Test PUT /api/employees/{id} - Update employee."""
    # Create employee first (with unique telegram_id)
    telegram_id = random.randint(100000000, 999999999)
    new_employee = {
        "name": "Update Test Worker",  # F14: Changed from full_name
        "role": "worker",
        "telegram_id": telegram_id,
        "password": "worker123"
    }
    
    create_response = client.post("/api/employees", json=new_employee, headers=admin_headers)
    assert create_response.status_code in [200, 201], f"Create failed: {create_response.text}"
    employee_id = create_response.json()["id"]
    
    # Update
    updates = {
        "name": "Updated Worker",  # F14: Changed from full_name
        "role": "foreman"
    }
    
    response = client.put(f"/api/employees/{employee_id}", json=updates, headers=admin_headers)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    updated = response.json()
    
    assert updated["name"] == "Updated Worker"  # F14: Changed from full_name
    assert updated["role"] == "foreman"


def test_soft_delete_employee(client, admin_headers):
    """Test DELETE /api/employees/{id} - Soft delete (sets active=False)."""
    # Create employee first (with unique telegram_id)
    telegram_id = random.randint(100000000, 999999999)
    new_employee = {
        "name": "Delete Test Worker",  # F14: Changed from full_name
        "role": "worker",
        "telegram_id": telegram_id,
        "password": "worker123"
    }
    
    create_response = client.post("/api/employees", json=new_employee, headers=admin_headers)
    assert create_response.status_code in [200, 201], f"Create failed: {create_response.text}"
    employee_id = create_response.json()["id"]
    
    # Soft delete
    response = client.delete(f"/api/employees/{employee_id}", headers=admin_headers)
    
    assert response.status_code in [200, 204], f"Expected 200/204, got {response.status_code}"
    
    # Verify deleted (should return 404 since active=False filters out deleted)
    get_response = client.get(f"/api/employees/{employee_id}", headers=admin_headers)
    
    assert get_response.status_code == 404, "Deleted employee should return 404 (active=False filtered out)"


def test_rbac_admin_can_create(client, admin_headers):
    """Test RBAC: Admin can create employees."""
    telegram_id = random.randint(100000000, 999999999)
    new_employee = {
        "name": "RBAC Test Worker",  # F14: Changed from full_name
        "role": "worker",
        "telegram_id": telegram_id,
        "password": "test12345"
    }
    
    response = client.post("/api/employees", json=new_employee, headers=admin_headers)
    
    assert response.status_code in [200, 201], f"Admin should be able to create employee, got {response.status_code}: {response.text}"


def test_duplicate_username(client, admin_headers):
    """Test POST /api/employees - Duplicate username/telegram_id should fail."""
    # Create first employee
    telegram_id = random.randint(100000000, 999999999)
    first = {
        "name": "First Employee",  # F14: Changed from full_name
        "role": "worker",
        "telegram_id": telegram_id,
        "password": "test12345"
    }
    
    create_response = client.post("/api/employees", json=first, headers=admin_headers)
    assert create_response.status_code in [200, 201], f"First create failed: {create_response.text}"
    
    # Try to create duplicate with same telegram_id
    duplicate = {
        "name": "Duplicate Employee",  # F14: Changed from full_name
        "role": "worker",
        "telegram_id": telegram_id,  # Same telegram_id
        "password": "test12345"
    }
    
    response = client.post("/api/employees", json=duplicate, headers=admin_headers)
    
    # Should fail with 400, 409, or 422 (conflict/validation error)
    assert response.status_code in [400, 409, 422], \
        f"Duplicate telegram_id should fail, got {response.status_code}"


def test_invalid_role(client, admin_headers):
    """Test POST /api/employees - Invalid role should fail."""
    telegram_id = random.randint(100000000, 999999999)
    invalid_employee = {
        "name": "Invalid Role User",  # F14: Changed from full_name
        "role": "superuser",  # Not a valid role
        "telegram_id": telegram_id,
        "password": "test12345"
    }
    
    response = client.post("/api/employees", json=invalid_employee, headers=admin_headers)
    
    # Should fail with 400 or 422 (validation error)
    assert response.status_code in [400, 422], \
        f"Invalid role should fail, got {response.status_code}"
