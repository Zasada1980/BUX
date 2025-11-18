"""CRUD operations for user management (single role per user)"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from models_users import User, UserCreate, UserUpdate, UserStats


# User CRUD
def get_user_by_telegram_id(db: Session, telegram_id: int) -> Optional[User]:
    """Get user by telegram_id"""
    return db.query(User).filter(User.telegram_id == telegram_id).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by primary key"""
    return db.query(User).filter(User.id == user_id).first()


def get_active_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """Get active users with pagination"""
    return db.query(User).filter(User.active == True).offset(skip).limit(limit).all()


def list_users(
    db: Session,
    role_filter: Optional[str] = None,
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100
) -> List[User]:
    """List users with optional filters
    
    Args:
        db: Database session
        role_filter: Filter by role (worker/foreman/admin), None for all
        active_only: If True, return only active users
        skip: Pagination offset
        limit: Max results
    """
    query = db.query(User)
    
    if active_only:
        query = query.filter(User.active == True)
    
    if role_filter:
        query = query.filter(User.role == role_filter)
    
    return query.offset(skip).limit(limit).all()


def create_user(db: Session, user: UserCreate) -> User:
    """Create new user"""
    db_user = User(
        telegram_id=user.telegram_id,
        telegram_username=user.telegram_username,
        name=user.name,
        instagram_nickname=user.instagram_nickname,
        phone=user.phone,
        daily_salary=user.daily_salary,
        role=user.role.value,  # Enum to string
        active=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update: UserUpdate) -> Optional[User]:
    """Update user (partial update)"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        if field == "role" and value:
            setattr(db_user, field, value.value)  # Enum to string
        else:
            setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int) -> bool:
    """Hard delete user"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return False
    
    db.delete(db_user)
    db.commit()
    return True


def get_user_role(db: Session, telegram_id: int) -> Optional[str]:
    """Get user role by telegram_id (for RBAC middleware)"""
    user = get_user_by_telegram_id(db, telegram_id)
    if not user or not user.active:
        return None
    return str(user.role)  # Ensure string return


# Statistics
def activate_user(db: Session, user_id: int) -> Optional[User]:
    """Activate user (set active=True)"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    db_user.active = True
    db.commit()
    db.refresh(db_user)
    return db_user


def deactivate_user(db: Session, user_id: int) -> Optional[User]:
    """Deactivate user (set active=False, soft delete)"""
    db_user = get_user_by_id(db, user_id)
    if not db_user:
        return None
    
    db_user.active = False
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user_stats(db: Session) -> UserStats:
    """Get user statistics for admin dashboard"""
    total = db.query(func.count(User.id)).scalar() or 0
    active = db.query(func.count(User.id)).filter(User.active == True).scalar() or 0
    inactive = total - active
    
    # Role counts (active users only)
    workers = db.query(func.count(User.id)).filter(
        User.active == True, User.role == "worker"
    ).scalar() or 0
    
    foremen = db.query(func.count(User.id)).filter(
        User.active == True, User.role == "foreman"
    ).scalar() or 0
    
    admins = db.query(func.count(User.id)).filter(
        User.active == True, User.role == "admin"
    ).scalar() or 0
    
    return UserStats(
        total_users=total,
        active_users=active,
        workers=workers,
        foremen=foremen,
        admins=admins,
        inactive_users=inactive
    )
