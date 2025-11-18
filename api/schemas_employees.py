"""Employee management schemas."""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class EmployeeCreateIn(BaseModel):
    """Create employee request."""
    telegram_id: Optional[int] = None
    full_name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(..., pattern="^(admin|foreman|worker)$")
    username: Optional[str] = Field(None, min_length=3, max_length=100)  # For password auth
    password: Optional[str] = Field(None, min_length=8, max_length=255)  # For password auth
    
    @validator('password')
    def validate_password_if_username(cls, v, values):
        """Password required if username provided."""
        if values.get('username') and not v:
            raise ValueError('Password required when username provided')
        return v


class EmployeeUpdateIn(BaseModel):
    """Update employee request."""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    role: Optional[str] = Field(None, pattern="^(admin|foreman|worker)$")
    is_active: Optional[bool] = None


class EmployeeOut(BaseModel):
    """Employee response."""
    id: int
    telegram_id: Optional[int]
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    has_password: bool = False  # Indicates if password auth is configured
    
    class Config:
        from_attributes = True


class EmployeeListOut(BaseModel):
    """Employee list response with pagination."""
    employees: list[EmployeeOut]
    total: int
    page: int
    page_size: int
