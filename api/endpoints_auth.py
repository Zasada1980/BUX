"""Authentication endpoints for web interface."""
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import Field
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from models import Employee, AuthCredential, RefreshToken
from schemas_auth import (
    TelegramLoginData,
    PasswordLoginIn,
    TokenResponse,
    TokenRefreshIn,
    CurrentUserOut,
    EmployeeOut,
    CreateUserRequest,
    UserCredentialOut,
    RevokeTokensRequest
)
from auth import (
    get_db,
    verify_telegram_auth,
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_employee,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# RBAC permissions mapping
ROLE_PERMISSIONS = {
    "admin": [
        "employees.read", "employees.create", "employees.update", "employees.delete",
        "work_records.read", "work_records.create", "work_records.export",
        "salaries.read", "salaries.import", "salaries.export"
    ],
    "foreman": [
        "employees.read",  # Read only (limited to assigned workers)
        "work_records.read", "work_records.export",  # Read only (limited)
        "salaries.read"  # Read only (limited)
    ],
    "worker": [
        "work_records.read"  # Own records only
    ]
}


@router.post("/telegram-login", response_model=TokenResponse)
async def telegram_login(auth_data: TelegramLoginData, db: Session = Depends(get_db)):
    """
    Authenticate using Telegram OAuth widget.
    
    Validates HMAC-SHA256 signature and creates/retrieves employee record.
    """
    # Verify Telegram auth data
    auth_dict = auth_data.dict(exclude={'hash'})
    auth_dict['hash'] = auth_data.hash
    
    if not verify_telegram_auth(auth_dict):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram authentication"
        )
    
    # Find or create employee
    employee = db.query(Employee).filter(
        Employee.telegram_id == auth_data.id
    ).first()
    
    if not employee:
        # Auto-register new employee with default role
        full_name = f"{auth_data.first_name} {auth_data.last_name or ''}".strip()
        employee = Employee(
            telegram_id=auth_data.id,
            full_name=full_name,
            role="worker",  # Default role (admin must upgrade)
            is_active=True
        )
        db.add(employee)
        db.commit()
        db.refresh(employee)
    
    if not employee.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled"
        )
    
    # Create tokens (use telegram_id as username for Telegram auth)
    username = f"tg_{employee.telegram_id}"
    access_token = create_access_token(employee.id, employee.role, username)
    refresh_token = create_refresh_token(employee.id, db)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=employee.role,
        user_id=employee.id,
        name=employee.name,
        telegram_id=employee.telegram_id
    )


@router.post("/login", response_model=TokenResponse)
async def password_login(credentials: PasswordLoginIn, db: Session = Depends(get_db)):
    """
    Authenticate using username/password (fallback).
    
    Implements brute-force protection (5 attempts → 15 min lockout).
    """
    auth_cred = db.query(AuthCredential).filter(
        AuthCredential.username == credentials.username
    ).first()
    
    if not auth_cred:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Check lockout (SQLite may return timezone-naive datetime, make it aware)
    locked_until = auth_cred.locked_until
    if locked_until and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    
    if locked_until and locked_until > datetime.now(timezone.utc):
        remaining = (locked_until - datetime.now(timezone.utc)).total_seconds()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account locked for {int(remaining / 60)} more minutes"
        )
    
    # Verify password
    if not verify_password(credentials.password, auth_cred.password_hash):
        # Increment failed attempts
        auth_cred.failed_attempts += 1
        
        if auth_cred.failed_attempts >= 5:
            auth_cred.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account locked due to too many failed attempts (15 min)"
            )
        
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid credentials ({5 - auth_cred.failed_attempts} attempts remaining)"
        )
    
    # Reset failed attempts on success
    auth_cred.failed_attempts = 0
    auth_cred.locked_until = None
    db.commit()
    
    # Get employee
    employee = db.query(Employee).filter(
        Employee.id == auth_cred.employee_id
    ).first()
    
    if not employee or not employee.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled"
        )
    
    # Create tokens (use auth_cred.username for password login)
    access_token = create_access_token(employee.id, employee.role, auth_cred.username)
    refresh_token = create_refresh_token(employee.id, db)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=employee.role,
        user_id=employee.id,
        name=employee.name,
        telegram_id=employee.telegram_id
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(data: TokenRefreshIn, db: Session = Depends(get_db)):
    """
    Refresh access token using refresh token.
    
    Validates refresh token and issues new access + refresh tokens.
    """
    # Verify refresh token
    payload = verify_token(data.refresh_token, token_type="refresh")
    employee_id = int(payload["sub"])
    
    # Check token exists in database and not revoked
    token_obj = db.query(RefreshToken).filter(
        RefreshToken.token == data.refresh_token,
        RefreshToken.employee_id == employee_id,
        RefreshToken.revoked == False
    ).first()
    
    if not token_obj:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token"
        )
    
    # Check expiration (DB check)
    # SQLite may return timezone-naive datetime, make it aware
    expires_at = token_obj.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired"
        )
    
    # Get employee
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee or not employee.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled"
        )
    
    # Get username from auth_credentials
    auth_cred = db.query(AuthCredential).filter(
        AuthCredential.employee_id == employee.id
    ).first()
    
    username = auth_cred.username if auth_cred else f"tg_{employee.telegram_id}"
    
    # Revoke old refresh token
    token_obj.revoked = True
    db.commit()
    
    # Create new tokens
    access_token = create_access_token(employee.id, employee.role, username)
    new_refresh_token = create_refresh_token(employee.id, db)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=employee.role,
        user_id=employee.id,
        name=employee.name,
        telegram_id=employee.telegram_id
    )


@router.get("/me", response_model=CurrentUserOut)
async def get_current_user(employee: Employee = Depends(get_current_employee)):
    """Get current authenticated user info."""
    permissions = ROLE_PERMISSIONS.get(employee.role, [])
    
    return CurrentUserOut(
        employee=EmployeeOut.from_orm(employee),
        permissions=permissions
    )


@router.post("/logout")
async def logout(
    data: TokenRefreshIn,
    employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """
    Logout user by revoking refresh token.
    
    Client should also clear access token from sessionStorage.
    """
    # Revoke refresh token
    token_obj = db.query(RefreshToken).filter(
        RefreshToken.token == data.refresh_token,
        RefreshToken.employee_id == employee.id
    ).first()
    
    if token_obj:
        token_obj.revoked = True
        db.commit()
    
    return {"status": "ok", "message": "Logged out successfully"}


@router.post("/users", response_model=UserCredentialOut, status_code=201)
async def create_user(
    request: CreateUserRequest,
    current_user: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """
    Create new user with password credentials (admin only).
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can create users"
        )
    
    # Check if username already exists
    existing = db.query(AuthCredential).filter(
        AuthCredential.username == request.username
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{request.username}' already exists"
        )
    
    # Check if telegram_id exists
    if request.telegram_id:
        existing_tg = db.query(Employee).filter(
            Employee.telegram_id == request.telegram_id
        ).first()
        
        if existing_tg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Telegram ID {request.telegram_id} already registered"
            )
    
    # Create employee
    employee = Employee(
        telegram_id=request.telegram_id,
        telegram_username=request.telegram_username,
        phone=request.phone,
        name=request.name,
        role=request.role,
        active=True
    )
    db.add(employee)
    db.flush()  # Get employee.id
    
    # Create auth credentials
    password_hash = hash_password(request.password)
    auth_cred = AuthCredential(
        employee_id=employee.id,
        username=request.username,
        password_hash=password_hash,
        failed_attempts=0
    )
    db.add(auth_cred)
    db.commit()
    db.refresh(auth_cred)
    
    return UserCredentialOut(
        id=auth_cred.id,
        employee_id=employee.id,
        username=auth_cred.username,
        name=employee.name,
        role=employee.role,
        active=employee.active,
        failed_attempts=auth_cred.failed_attempts,
        locked_until=auth_cred.locked_until,
        created_at=auth_cred.created_at
    )


@router.get("/users", response_model=list[UserCredentialOut])
async def list_users(
    current_user: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """
    List all users with credentials (admin only).
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can view users"
        )
    
    # Join AuthCredential with Employee
    results = db.query(AuthCredential, Employee).join(
        Employee, AuthCredential.employee_id == Employee.id
    ).all()
    
    return [
        UserCredentialOut(
            id=cred.id,
            employee_id=cred.employee_id,
            username=cred.username,
            name=emp.name,
            role=emp.role,
            active=emp.active,
            failed_attempts=cred.failed_attempts,
            locked_until=cred.locked_until,
            created_at=cred.created_at
        )
        for cred, emp in results
    ]


@router.delete("/users/{employee_id}")
async def delete_user(
    employee_id: int,
    current_user: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """
    Delete user and revoke all tokens (admin only).
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete users"
        )
    
    if employee_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself"
        )
    
    # Delete auth credentials
    db.query(AuthCredential).filter(
        AuthCredential.employee_id == employee_id
    ).delete()
    
    # Revoke all refresh tokens
    db.query(RefreshToken).filter(
        RefreshToken.employee_id == employee_id
    ).update({"revoked": True})
    
    # Delete employee
    deleted = db.query(Employee).filter(Employee.id == employee_id).delete()
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    db.commit()
    
    return {"status": "ok", "message": f"User {employee_id} deleted"}


@router.post("/users/{employee_id}/revoke-tokens")
async def revoke_user_tokens(
    employee_id: int,
    current_user: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """
    Revoke all refresh tokens for a user (admin only or self).
    """
    if current_user.role != "admin" and current_user.id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can revoke other users' tokens"
        )
    
    # Revoke all refresh tokens
    count = db.query(RefreshToken).filter(
        RefreshToken.employee_id == employee_id,
        RefreshToken.revoked == False
    ).update({"revoked": True})
    
    db.commit()
    
    return {"status": "ok", "message": f"Revoked {count} tokens"}


@router.post("/users/{employee_id}/reset-password")
async def reset_user_password(
    employee_id: int,
    new_password: str = Body(..., embed=True, min_length=8),
    current_user: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """
    Reset user password and revoke all tokens (admin only or self).
    """
    if current_user.role != "admin" and current_user.id != employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can reset other users' passwords"
        )
    
    # Update password
    auth_cred = db.query(AuthCredential).filter(
        AuthCredential.employee_id == employee_id
    ).first()
    
    if not auth_cred:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User credentials not found"
        )
    
    auth_cred.password_hash = hash_password(new_password)
    auth_cred.failed_attempts = 0
    auth_cred.locked_until = None
    
    # Revoke all tokens
    db.query(RefreshToken).filter(
        RefreshToken.employee_id == employee_id
    ).update({"revoked": True})
    
    db.commit()
    
    return {"status": "ok", "message": "Password reset successfully"}
