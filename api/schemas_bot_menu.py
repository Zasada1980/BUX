"""Pydantic models for Telegram Bot menu management."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, validator
from models_users import UserRole  # Reuse existing enum


# --- Read Models (для фронта) ---

class BotCommandConfig(BaseModel):
    """Single Telegram command configuration."""
    id: int
    role: UserRole
    command_key: str = Field(..., description="Unique key (e.g., 'shift_in')")
    telegram_command: str = Field(..., description="Slash command (e.g., '/in')")
    label: str = Field(..., min_length=1, max_length=50, description="Menu label")
    description: Optional[str] = Field(None, max_length=200)
    enabled: bool = Field(True, description="Whether command is enabled")
    is_core: bool = Field(False, description="Core commands cannot be disabled")
    position: int = Field(0, ge=0, description="Display order in menu")
    command_type: str = Field("slash", description="Command type (slash/menu)")
    
    class Config:
        orm_mode = True


class BotMenuResponse(BaseModel):
    """Complete bot menu configuration with metadata."""
    version: int = Field(..., description="Config version, incremented on each save")
    last_updated_at: datetime = Field(..., description="Last save timestamp")
    last_updated_by: Optional[str] = Field(None, description="Admin username who saved")
    last_applied_at: Optional[datetime] = Field(None, description="Last apply to bot timestamp")
    last_applied_by: Optional[str] = Field(None, description="Admin who applied to bot")
    roles: Dict[str, List[BotCommandConfig]] = Field(
        ...,
        description="Commands grouped by role: {'admin': [...], 'foreman': [...], 'worker': [...]}"
    )


# --- Update Models (DTO для фронта → бэк) ---

class UpdateBotCommandPayload(BaseModel):
    """DTO for updating a single command (only editable fields)."""
    id: int = Field(..., description="Command ID")
    label: str = Field(..., min_length=1, max_length=50, description="New label")
    enabled: bool = Field(..., description="Enabled state")
    position: int = Field(..., ge=0, description="Display order")
    
    @validator('label')
    def label_no_newlines(cls, v):
        if '\n' in v or '\r' in v:
            raise ValueError('Label cannot contain newlines')
        return v.strip()


class UpdateBotMenuRequest(BaseModel):
    """Request to update bot menu configuration."""
    version: int = Field(..., description="Current version client is editing (for optimistic locking)")
    roles: Dict[str, List[UpdateBotCommandPayload]] = Field(
        ...,
        description="Commands to update, grouped by role"
    )
    
    @validator('roles')
    def validate_roles(cls, v):
        allowed_roles = {'admin', 'foreman', 'worker'}
        if not set(v.keys()).issubset(allowed_roles):
            raise ValueError(f'Invalid roles. Allowed: {allowed_roles}')
        return v


# --- Apply Response ---

class ApplyBotMenuResponse(BaseModel):
    """Response from applying bot menu to Telegram."""
    success: bool = Field(..., description="Whether apply succeeded")
    applied_at: Optional[datetime] = Field(None, description="Apply timestamp")
    details: Optional[str] = Field(None, description="Success/error details")
