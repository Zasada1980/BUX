"""API endpoints for user management (admin only)"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from db import SessionLocal  # FIX: No api.database in API container
import crud_users
from models_users import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserStats,
    PaginatedUsersResponse
)
from deps_auth import get_current_admin  # F4.4 A2: Unified JWT + X-Admin-Secret auth

# get_db dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/users", tags=["users"])  # Will become /api/users via main.py registration


@router.get("/stats", response_model=UserStats)
def get_stats(
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Get user statistics (admin only)"""
    return crud_users.get_user_stats(db)


@router.get("/", response_model=PaginatedUsersResponse)
def list_users(
    page: int = 1,
    limit: int = 20,
    active_only: bool = True,
    role: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """List all users with pagination and filters (admin only)
    
    Args:
        page: Page number (1-based)
        limit: Items per page
        active_only: DEPRECATED - use status filter instead
        role: Filter by role (worker, foreman, admin)
        status: Filter by status (active, inactive, all)
    """
    skip = (page - 1) * limit
    
    from models_users import User
    
    # Build query with filters
    query = db.query(User)
    
    # Status filter (new preferred way)
    if status == 'active':
        query = query.filter(User.active == True)
    elif status == 'inactive':
        query = query.filter(User.active == False)
    elif active_only and status is None:  # Legacy fallback
        query = query.filter(User.active == True)
    
    # Role filter
    if role and role != 'all':
        query = query.filter(User.role == role)
    
    # Get total count with filters
    total = query.count()
    
    # Get paginated results
    users = query.offset(skip).limit(limit).all()
    
    # Calculate pages
    pages = (total + limit - 1) // limit if total > 0 else 1
    
    return PaginatedUsersResponse(
        items=users,
        total=total,
        page=page,
        pages=pages,
        limit=limit
    )


@router.get("/role/{role}", response_model=List[UserResponse])
def list_users_by_role(
    role: str,
    active_only: bool = True,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """List users by role (admin only)"""
    return crud_users.get_users_by_role(db, role, active_only=active_only)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Get user by ID (admin only)"""
    user = crud_users.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Create new user (admin only)"""
    from models_users import User
    
    # Check uniqueness: telegram_id, telegram_username, phone (any can be None)
    # F14-3: Updated to check all contact methods (not just telegram_id)
    if user.telegram_id:
        existing = crud_users.get_user_by_telegram_id(db, user.telegram_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with telegram_id {user.telegram_id} already exists"
            )
    
    if user.telegram_username:
        existing_username = db.query(User).filter(User.telegram_username == user.telegram_username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with telegram_username {user.telegram_username} already exists"
            )
    
    if user.phone:
        existing_phone = db.query(User).filter(User.phone == user.phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with phone {user.phone} already exists"
            )
    
    # Set created_by from admin (if field exists)
    if hasattr(user, 'created_by'):
        user.created_by = admin.get('telegram_id') or admin.get('user_id')
    
    return crud_users.create_user(db, user)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Update user (admin only)"""
    updated = crud_users.update_user(db, user_id, user_update)
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.patch("/{user_id}/roles")
def update_user_roles(
    user_id: int,
    new_roles: str,
    reason: str = None,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Update user roles with audit logging (admin only)"""
    updated = crud_users.update_user_roles(
        db,
        user_id=user_id,
        new_roles=new_roles,
        changed_by=admin.telegram_id,
        reason=reason
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found")
    return updated


@router.post("/{user_id}/activate", response_model=UserResponse)
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Activate user (admin only)"""
    user = crud_users.activate_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/{user_id}/deactivate", response_model=UserResponse)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Deactivate user (admin only)"""
    user = crud_users.deactivate_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: dict = Depends(get_current_admin)
):
    """Delete user permanently (admin only)"""
    success = crud_users.delete_user(db, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
