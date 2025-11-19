"""Employee management schemas."""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class EmployeeCreateIn(BaseModel):
    """Create employee request."""
    telegram_id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=255)  # Changed from full_name (F14)
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
    name: Optional[str] = Field(None, min_length=1, max_length=255)  # Changed from full_name (F14)
    role: Optional[str] = Field(None, pattern="^(admin|foreman|worker)$")
    active: Optional[bool] = None  # Changed from is_active (F14)


class EmployeeOut(BaseModel):
    """Employee response."""
    id: int
    telegram_id: Optional[int]
    name: str  # Changed from full_name (F14 schema alignment)
    role: str
    active: bool  # Changed from is_active (F14 schema alignment)
    created_at: datetime
    updated_at: datetime
    has_password: bool = False  # Indicates if password auth is configured
    
    class Config:
        from_attributes = True


class EmployeeListOut(BaseModel):
    """Employee list response with pagination."""
    employees: list[EmployeeOut]
    total: int
    page: int
    page_size: int
