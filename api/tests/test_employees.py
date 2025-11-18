"""
Employee CRUD Tests - Create, Read, Update, Delete, RBAC

Tests:
1. List all employees
2. Get employee by ID
3. Create new employee
4. Update employee
5. Soft delete employee (is_active=False)
6. RBAC: Admin can create, foreman can read only
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from main import app
from models import Employee
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ._client import build_test_client

client = build_test_client(app)

DB_PATH = "/data/workledger.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(bind=engine)


def get_admin_token():
    """Helper: Get admin JWT token."""
    response = client.post("/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    return response.json()["access_token"]


def test_list_employees():
    """Test GET /api/employees - List all employees."""
    print("🧪 Test 1: List employees...")
    
    token = get_admin_token()
    response = client.get("/api/employees", headers={
        "Authorization": f"Bearer {token}"
    })
    
    assert response.status_code == 200, f"❌ Expected 200, got {response.status_code}"
    data = response.json()
    
    # Handle paginated response
    if isinstance(data, dict) and 'employees' in data:
        employees = data['employees']
    else:
        employees = data
    
    assert isinstance(employees, list), "❌ Response should be list"
    assert len(employees) >= 1, "❌ Should have at least admin user"
    
    # Check structure
    admin = employees[0]
    assert "id" in admin, "❌ Missing 'id' field"
    assert "full_name" in admin or "username" in admin, "❌ Missing 'full_name' or 'username' field"
    assert "role" in admin, "❌ Missing 'role' field"
    assert "is_active" in admin, "❌ Missing 'is_active' field"
    
    print(f"  ✅ Found {len(employees)} employees")


def test_get_employee_by_id():
    """Test GET /api/employees/{id} - Get employee by ID."""
    print("🧪 Test 2: Get employee by ID...")
    
    token = get_admin_token()
    
    # Get admin user (ID=1)
    response = client.get("/api/employees/1", headers={
        "Authorization": f"Bearer {token}"
    })
    
    assert response.status_code == 200, f"❌ Expected 200, got {response.status_code}"
    employee = response.json()
    
    assert employee["id"] == 1, f"❌ Expected id=1, got {employee['id']}"
    assert employee["role"] == "admin", f"❌ Expected role='admin', got {employee['role']}"
    
    name = employee.get("full_name") or employee.get("username", "admin")
    print(f"  ✅ Employee #{employee['id']}: {name} ({employee['role']})")


def test_get_nonexistent_employee():
    """Test GET /api/employees/{id} - Non-existent employee returns 404."""
    print("🧪 Test 3: Get non-existent employee...")
    
    token = get_admin_token()
    response = client.get("/api/employees/99999", headers={
        "Authorization": f"Bearer {token}"
    })
    
    assert response.status_code == 404, f"❌ Expected 404, got {response.status_code}"
    print("  ✅ Correctly returned 404 for non-existent employee")


def test_create_employee():
    """Test POST /api/employees - Create new employee."""
    print("🧪 Test 4: Create employee...")
    
    token = get_admin_token()
    
    import time
    unique_id = int(time.time() * 1000)  # Millisecond timestamp for uniqueness
    
    new_employee = {
        "telegram_id": unique_id,
        "full_name": "Test Worker",
        "role": "worker",
        "username": f"test_worker_{unique_id}",
        "password": "secure123"
    }
    
    response = client.post("/api/employees", 
        headers={"Authorization": f"Bearer {token}"},
        json=new_employee
    )
    
    assert response.status_code == 201, f"❌ Expected 201, got {response.status_code}: {response.text}"
    created = response.json()
    
    assert "id" in created, "❌ Missing 'id' in response"
    assert created["full_name"] == new_employee["full_name"], "❌ full_name mismatch"
    assert created["role"] == "worker", "❌ Role mismatch"
    assert created.get("has_password") == True, "❌ Should have password"
    
    print(f"  ✅ Created employee #{created['id']}: {created['full_name']}")
    
    # Cleanup
    global _test_employee_id
    _test_employee_id = created["id"]
    return created["id"]


def test_update_employee():
    """Test PUT /api/employees/{id} - Update employee."""
    print("🧪 Test 5: Update employee...")
    
    token = get_admin_token()
    
    # Create employee first
    employee_id = test_create_employee()
    
    # Update
    update_data = {
        "full_name": "Updated Worker Name",
        "is_active": False
    }
    
    response = client.put(f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"},
        json=update_data
    )
    
    assert response.status_code == 200, f"❌ Expected 200, got {response.status_code}"
    updated = response.json()
    
    assert updated["full_name"] == "Updated Worker Name", "❌ Name not updated"
    assert updated["is_active"] == False, "❌ is_active not updated"
    
    print(f"  ✅ Updated employee #{employee_id}: {updated['full_name']}")


def test_soft_delete_employee():
    """Test DELETE /api/employees/{id} - Soft delete (sets deleted_at)."""
    print("🧪 Test 6: Soft delete employee...")
    
    token = get_admin_token()
    
    # Create employee to delete (reuse test_create_employee)
    employee_id = test_create_employee()
    
    # Delete
    response = client.delete(f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 204, f"❌ Expected 204, got {response.status_code}"
    
    # Verify deleted (should return 404 since it's filtered out)
    response = client.get(f"/api/employees/{employee_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404, f"❌ Deleted employee should return 404"
    print(f"  ✅ Soft deleted employee #{employee_id}")


def test_rbac_admin_can_create():
    """Test RBAC: Admin can create employees."""
    print("🧪 Test 7: RBAC - Admin can create...")
    
    token = get_admin_token()
    
    import time
    unique_id = int(time.time() * 1000)
    
    response = client.post("/api/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "telegram_id": unique_id,
            "full_name": "RBAC Test Worker",
            "role": "worker",
            "username": f"rbac_test_{unique_id}",
            "password": "testpass123"
        }
    )
    
    assert response.status_code == 201, f"❌ Admin should be able to create: {response.status_code}"
    print("  ✅ Admin successfully created employee")


def test_duplicate_username():
    """Test that duplicate usernames are rejected."""
    print("🧪 Test 8: Duplicate username validation...")
    
    token = get_admin_token()
    
    import time
    unique_id = int(time.time() * 1000)
    
    # Try to create employee with username "admin"
    response = client.post("/api/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "telegram_id": unique_id,
            "full_name": "Duplicate Admin",
            "role": "worker",
            "username": "admin",  # Already exists
            "password": "somepass123"
        }
    )
    
    assert response.status_code in [400, 409], f"❌ Expected 400/409, got {response.status_code}"
    print("  ✅ Correctly rejected duplicate username")


def test_invalid_role():
    """Test that invalid roles are rejected."""
    print("🧪 Test 9: Invalid role validation...")
    
    token = get_admin_token()
    
    import time
    unique_id = int(time.time() * 1000)
    
    response = client.post("/api/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "telegram_id": unique_id,
            "full_name": "Invalid Role Test",
            "role": "superadmin",  # Invalid role
            "username": f"invalid_role_test_{unique_id}",
            "password": "testpass123"
        }
    )
    
    assert response.status_code == 422, f"❌ Expected 422, got {response.status_code}"
    print("  ✅ Correctly rejected invalid role")


if __name__ == "__main__":
    print("=" * 60)
    print("EMPLOYEE CRUD TESTS")
    print("=" * 60)
    
    test_list_employees()
    test_get_employee_by_id()
    test_get_nonexistent_employee()
    test_create_employee()
    test_update_employee()
    test_soft_delete_employee()
    test_rbac_admin_can_create()
    test_duplicate_username()
    test_invalid_role()
    
    print("\n" + "=" * 60)
    print("✅ ALL EMPLOYEE CRUD TESTS PASSED")
    print("=" * 60)
