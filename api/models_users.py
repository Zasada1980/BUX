"""User management models with DB-driven RBAC (single role per user)"""
from datetime import datetime
from typing import Optional, Any
from enum import Enum
from decimal import Decimal
from pydantic import BaseModel, Field, validator, condecimal, field_serializer
from sqlalchemy import Boolean, Column, Integer, BigInteger, String, DateTime, Numeric, func
from models import Base


# Role enum
class UserRole(str, Enum):
    worker = "worker"
    foreman = "foreman"
    admin = "admin"


# SQLAlchemy Models
class User(Base):
    """User with role-based access control (single role)"""
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}  # FIX: Allow redefinition in bot context
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, nullable=True, index=True)  # NULL for workers without Telegram
    telegram_username = Column(String, nullable=True)  # @username (optional)
    name = Column(String, nullable=False)  # Имя рабочего (обязательно для админа)
    instagram_nickname = Column(String, nullable=True)  # Instagram nickname для привязки к реальному рабочему
    phone = Column(String, nullable=True)  # Номер телефона (вспомогательное поле)
    daily_salary = Column(Numeric(10, 2), nullable=True)  # Дневная зарплата в ₪
    role = Column(String, nullable=False, default="worker")  # Single role: worker/foreman/admin
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())


# Pydantic Schemas
class UserCreate(BaseModel):
    """Schema for creating new user"""
    telegram_id: Optional[int] = Field(None, gt=0, description="Telegram user ID (optional)")
    telegram_username: Optional[str] = Field(None, max_length=64)
    name: str = Field(..., min_length=1, max_length=100, description="Имя рабочего")
    instagram_nickname: Optional[str] = Field(None, max_length=64, description="Instagram nickname")
    phone: Optional[str] = Field(None, max_length=20, description="Номер телефона")
    daily_salary: Optional[Decimal] = Field(None, description="Дневная зарплата в ₪")
    role: UserRole = Field(default=UserRole.worker, description="User role")
    
    @validator('telegram_id')
    def validate_telegram_id(cls, v):
        if v is not None and v <= 0:
            raise ValueError("telegram_id must be positive")
        return v
    
    @validator('daily_salary')
    def validate_salary(cls, v):
        if v is not None and v <= 0:
            raise ValueError("daily_salary must be positive")
        return v


class UserUpdate(BaseModel):
    """Schema for updating user (partial updates)"""
    telegram_username: Optional[str] = Field(None, max_length=64)
    name: Optional[str] = Field(None, max_length=100)
    instagram_nickname: Optional[str] = Field(None, max_length=64)
    phone: Optional[str] = Field(None, max_length=20)
    daily_salary: Optional[Decimal] = None
    role: Optional[UserRole] = None
    active: Optional[bool] = None


class UserResponse(BaseModel):
    """Schema for user API response"""
    id: int
    telegram_id: Optional[int]
    telegram_username: Optional[str]
    name: str
    instagram_nickname: Optional[str]
    daily_salary: Optional[Decimal]
    role: str
    active: bool
    status: Optional[str] = None  # Computed field for frontend compatibility
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True  # Enable ORM mode
    
    @validator('status', pre=True, always=True)
    def compute_status(cls, v, values):
        """Compute status from active field"""
        if v is not None:
            return v
        active = values.get('active', True)
        return 'active' if active else 'inactive'


class UserStats(BaseModel):
    """User statistics schema"""
    total_users: int
    active_users: int
    inactive_users: int
    workers: int
    foremen: int
    admins: int


class PaginatedUsersResponse(BaseModel):
    """Paginated response for user list"""
    items: list[UserResponse]
    total: int
    page: int
    pages: int
    limit: int

# 2025-11-13 21:48:41 - Run polling for bot @Ollama_axon_bot
