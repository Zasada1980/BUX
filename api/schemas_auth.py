"""Authentication schemas for web interface."""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class TelegramLoginData(BaseModel):
    """Telegram OAuth widget data."""
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str
    
    @validator('auth_date')
    def validate_auth_date(cls, v):
        """Validate auth_date is within 24 hours."""
        now = int(datetime.now().timestamp())
        if now - v > 86400:  # 24 hours
            raise ValueError('Auth data expired (>24h)')
        return v


class PasswordLoginIn(BaseModel):
    """Password-based login request."""
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, max_length=255)


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    # B0.4: Add user fields for frontend AuthContext
    role: str
    user_id: int
    name: str
    telegram_id: Optional[int] = None


class TokenRefreshIn(BaseModel):
    """Refresh token request."""
    refresh_token: str


class EmployeeOut(BaseModel):
    """Employee data for authenticated user."""
    id: int
    telegram_id: Optional[int] = None
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class CurrentUserOut(BaseModel):
    """Current user info response."""
    employee: EmployeeOut
    permissions: list[str]  # List of allowed operations
