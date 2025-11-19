"""Profile management endpoints — F1.3 Profile v1.0.

// API CHANGE: F1.3 Profile v1.0
New endpoints for user profile view and password change.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from models import Employee, AuthCredential
from schemas_auth import CurrentUserOut
from auth import get_db, get_current_employee, verify_password, hash_password
from pydantic import BaseModel, Field, validator

router = APIRouter(prefix="/api/profile", tags=["profile"])


# Schemas
class ProfileOut(BaseModel):
    """User profile response."""
    id: int
    name: str
    email: str | None
    role: str
    created_at: datetime
    last_login: datetime | None

    class Config:
        from_attributes = True


class PasswordChangeIn(BaseModel):
    """Password change request."""
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (min 6 chars)")
    confirm_password: str = Field(..., min_length=6, description="Confirm new password")

    @validator("confirm_password")
    def passwords_match(cls, v, values):
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("New password and confirmation do not match")
        return v


class PasswordChangeOut(BaseModel):
    """Password change response."""
    message: str
    changed_at: datetime


# Endpoints
@router.get("", response_model=ProfileOut)
async def get_profile(
    current_user: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """Get current user profile.
    
    Returns:
        ProfileOut: User profile data (id, name, email, role, created_at, last_login)
    
    // API CHANGE: F1.3 Profile v1.0
    """
    employee = current_user  # get_current_employee already returns Employee object
    
    # F4.4: last_login not available in current schema (AuthCredential doesn't have this field)
    # Using None for now - can be added via migration if needed for Profile v1.1
    last_login = None
    
    return ProfileOut(
        id=employee.id,
        name=employee.name,  # F4.4: Employee model uses full_name, not name
        email=employee.email if hasattr(employee, 'email') else None,  # email may not exist in current schema
        role=employee.role,
        created_at=employee.created_at,
        last_login=last_login
    )


@router.put("/password", response_model=PasswordChangeOut)
async def change_password(
    password_data: PasswordChangeIn,
    current_user: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """Change user password.
    
    Args:
        password_data: Current password, new password, confirmation
    
    Returns:
        PasswordChangeOut: Success message and timestamp
    
    Raises:
        HTTPException 400: Validation errors (passwords don't match)
        HTTPException 401: Current password is incorrect
        HTTPException 404: Employee or credentials not found
        HTTPException 422: Validation errors (min length, etc.)
    
    // API CHANGE: F1.3 Profile v1.0
    """
    employee = current_user  # get_current_employee already returns Employee object
    
    # Get auth credentials
    cred = db.query(AuthCredential).filter(AuthCredential.employee_id == employee.id).first()
    if not cred or not cred.password_hash:
        raise HTTPException(
            status_code=404,
            detail="Password authentication not set up for this user"
        )
    
    # Verify current password
    if not verify_password(password_data.current_password, cred.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect"
        )
    
    # Update password
    cred.password_hash = hash_password(password_data.new_password)
    cred.updated_at = datetime.now(timezone.utc)
    db.commit()
    
    return PasswordChangeOut(
        message="Password changed successfully",
        changed_at=datetime.now(timezone.utc)
    )
