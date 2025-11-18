"""Middleware to replace hardcoded RBAC with DB-driven roles"""
from functools import wraps
from typing import Optional
from sqlalchemy.orm import Session

from bot.config import get_db
from api import crud_users
from api.models_users import User


def get_user_from_db(telegram_id: int) -> Optional[User]:
    """Get user from DB with caching (optional: add Redis)"""
    db = next(get_db())
    return crud_users.get_user_by_telegram_id(db, telegram_id)


def check_role(telegram_id: int, required_role: str) -> bool:
    """Check if user has required role (replaces .env checks)"""
    user = get_user_from_db(telegram_id)
    if not user or not user.active:
        return False
    return user.has_role(required_role)


def check_any_role(telegram_id: int, required_roles: list) -> bool:
    """Check if user has any of the required roles"""
    user = get_user_from_db(telegram_id)
    if not user or not user.active:
        return False
    return any(user.has_role(role) for role in required_roles)


# Decorators for bot handlers
def require_role(role: str):
    """Decorator to check role before handler execution"""
    def decorator(func):
        @wraps(func)
        async def wrapper(event, *args, **kwargs):
            from aiogram.types import Message, CallbackQuery
            
            # Extract user_id from event
            if isinstance(event, Message):
                user_id = event.from_user.id
            elif isinstance(event, CallbackQuery):
                user_id = event.from_user.id
            else:
                user_id = event.message.from_user.id if hasattr(event, 'message') else None
            
            if not user_id:
                return
            
            # Check role
            if not check_role(user_id, role):
                error_msg = f"❌ Доступ запрещён. Требуется роль: {role}"
                if isinstance(event, CallbackQuery):
                    await event.answer(error_msg, show_alert=True)
                else:
                    await event.reply(error_msg)
                return
            
            return await func(event, *args, **kwargs)
        return wrapper
    return decorator


def require_any_role(*roles):
    """Decorator to check if user has any of the required roles"""
    def decorator(func):
        @wraps(func)
        async def wrapper(event, *args, **kwargs):
            from aiogram.types import Message, CallbackQuery
            
            # Extract user_id
            if isinstance(event, Message):
                user_id = event.from_user.id
            elif isinstance(event, CallbackQuery):
                user_id = event.from_user.id
            else:
                user_id = event.message.from_user.id if hasattr(event, 'message') else None
            
            if not user_id:
                return
            
            # Check any role
            if not check_any_role(user_id, list(roles)):
                error_msg = f"❌ Доступ запрещён. Требуется одна из ролей: {', '.join(roles)}"
                if isinstance(event, CallbackQuery):
                    await event.answer(error_msg, show_alert=True)
                else:
                    await event.reply(error_msg)
                return
            
            return await func(event, *args, **kwargs)
        return wrapper
    return decorator


# Migration helper: Copy .env users to DB on first run
def migrate_env_to_db():
    """One-time migration from .env to DB (idempotent)"""
    from bot.config import BOT_ADMINS, BOT_FOREMEN, BOT_WORKERS
    
    db = next(get_db())
    
    env_users = {
        "admins": [int(x) for x in BOT_ADMINS.split(",") if x],
        "foremen": [int(x) for x in BOT_FOREMEN.split(",") if x],
        "workers": [int(x) for x in BOT_WORKERS.split(",") if x]
    }
    
    crud_users.migrate_env_users(db, env_users)
    print(f"✅ Migrated {len(set.union(*[set(v) for v in env_users.values()]))} users from .env to DB")


# API dependency for FastAPI endpoints
def get_current_user_db(telegram_id: int, db: Session) -> User:
    """FastAPI dependency to get current user from DB"""
    user = crud_users.get_user_by_telegram_id(db, telegram_id)
    if not user or not user.active:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found or inactive"
        )
    return user


def require_api_role(required_role: str):
    """FastAPI dependency to check role"""
    def dependency(user: User = Depends(get_current_user_db)):
        if not user.has_role(required_role):
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required"
            )
        return user
    return dependency
