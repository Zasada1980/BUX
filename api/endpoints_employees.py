"""Employee management endpoints (CRUD + RBAC)."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from typing import Optional
from models import Employee, AuthCredential
from schemas_employees import (
    EmployeeCreateIn,
    EmployeeUpdateIn,
    EmployeeOut,
    EmployeeListOut
)
from auth import (
    get_db,
    get_current_employee,
    require_admin,
    require_foreman,
    hash_password
)

router = APIRouter(prefix="/api/employees", tags=["employees"])


@router.get("", response_model=EmployeeListOut)
async def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    role: Optional[str] = Query(None, pattern="^(admin|foreman|worker)$"),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, max_length=100),
    employee: Employee = Depends(require_foreman),  # Foreman+ can list
    db: Session = Depends(get_db)
):
    """
    List employees with pagination and filtering.
    
    RBAC:
    - Admin: sees all employees
    - Foreman: sees only assigned workers (row-level security)
    - Worker: forbidden
    """
    query = db.query(Employee).filter(Employee.deleted_at.is_(None))
    
    # RBAC row-level filtering
    if employee.role == "foreman":
        # Foreman sees only workers (not other foremen/admins)
        # TODO: Implement assignment logic (foreman → workers mapping)
        query = query.filter(Employee.role == "worker")
    
    # Apply filters
    if role:
        query = query.filter(Employee.role == role)
    
    if is_active is not None:
        query = query.filter(Employee.is_active == is_active)
    
    if search:
        query = query.filter(
            func.lower(Employee.full_name).contains(search.lower())
        )
    
    # Count total
    total = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    employees_list = query.order_by(Employee.created_at.desc()).offset(offset).limit(page_size).all()
    
    # Add has_password flag
    employees_out = []
    for emp in employees_list:
        emp_out = EmployeeOut.from_orm(emp)
        emp_out.has_password = db.query(AuthCredential).filter(
            AuthCredential.employee_id == emp.id
        ).first() is not None
        employees_out.append(emp_out)
    
    return EmployeeListOut(
        employees=employees_out,
        total=total,
        page=page,
        page_size=page_size
    )


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreateIn,
    admin: Employee = Depends(require_admin),  # Admin only
    db: Session = Depends(get_db)
):
    """
    Create new employee.
    
    Optionally creates password credentials if username/password provided.
    """
    # Check telegram_id uniqueness
    if data.telegram_id:
        existing = db.query(Employee).filter(
            Employee.telegram_id == data.telegram_id,
            Employee.deleted_at.is_(None)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee with telegram_id {data.telegram_id} already exists"
            )
    
    # Check username uniqueness
    if data.username:
        existing_cred = db.query(AuthCredential).filter(
            AuthCredential.username == data.username
        ).first()
        if existing_cred:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Username '{data.username}' already taken"
            )
    
    # Create employee
    employee = Employee(
        telegram_id=data.telegram_id,
        full_name=data.full_name,
        role=data.role,
        is_active=True
    )
    db.add(employee)
    db.flush()  # Get employee.id
    
    # Create password credentials if provided
    if data.username and data.password:
        auth_cred = AuthCredential(
            employee_id=employee.id,
            username=data.username,
            password_hash=hash_password(data.password),
            failed_attempts=0
        )
        db.add(auth_cred)
    
    db.commit()
    db.refresh(employee)
    
    emp_out = EmployeeOut.from_orm(employee)
    emp_out.has_password = data.username is not None
    
    return emp_out


@router.put("/{employee_id}", response_model=EmployeeOut)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdateIn,
    admin: Employee = Depends(require_admin),  # Admin only
    db: Session = Depends(get_db)
):
    """Update employee details (admin only)."""
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at.is_(None)
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # Update fields
    if data.full_name is not None:
        employee.full_name = data.full_name
    
    if data.role is not None:
        employee.role = data.role
    
    if data.is_active is not None:
        employee.is_active = data.is_active
    
    employee.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(employee)
    
    emp_out = EmployeeOut.from_orm(employee)
    emp_out.has_password = db.query(AuthCredential).filter(
        AuthCredential.employee_id == employee.id
    ).first() is not None
    
    return emp_out


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: int,
    admin: Employee = Depends(require_admin),  # Admin only
    db: Session = Depends(get_db)
):
    """
    Soft delete employee (sets deleted_at timestamp).
    
    Preserves data for audit trail.
    """
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at.is_(None)
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # Prevent self-deletion
    if employee.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete
    employee.deleted_at = datetime.now(timezone.utc)
    employee.is_active = False
    db.commit()
    
    return None


@router.get("/{employee_id}", response_model=EmployeeOut)
async def get_employee(
    employee_id: int,
    current_employee: Employee = Depends(require_foreman),  # Foreman+ can view
    db: Session = Depends(get_db)
):
    """Get employee details by ID."""
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at.is_(None)
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    # RBAC: foreman can only see workers
    if current_employee.role == "foreman" and employee.role != "worker":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )
    
    emp_out = EmployeeOut.from_orm(employee)
    emp_out.has_password = db.query(AuthCredential).filter(
        AuthCredential.employee_id == employee.id
    ).first() is not None
    
    return emp_out
