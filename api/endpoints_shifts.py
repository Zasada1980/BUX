"""
Shifts API endpoints for admin shift review.
Provides read-only access to shift data with pagination and filtering.

RBAC: admin, foreman only (worker access denied).
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, and_, or_, desc
from sqlalchemy.orm import Session
from pydantic import BaseModel

from auth import get_current_employee, get_db
from models import Shift, Employee

router = APIRouter(prefix="/api/shifts", tags=["shifts"])


def require_admin_or_foreman(current_user: Employee = Depends(get_current_employee)):
    """Dependency to ensure user is admin or foreman."""
    if current_user.role not in ("admin", "foreman"):
        raise HTTPException(
            status_code=403,
            detail="Access denied: Shifts require admin or foreman role"
        )
    return current_user


class ShiftResponse(BaseModel):
    """Shift response schema for web UI."""
    id: int
    user_id: str
    client_id: Optional[int]
    work_address: Optional[str]
    status: str
    created_at: str
    ended_at: Optional[str]
    duration_hours: Optional[float]
    
    class Config:
        from_attributes = True


class PaginatedShiftsResponse(BaseModel):
    """Paginated response for shifts list."""
    items: list[ShiftResponse]
    total: int
    pages: int
    page: int
    limit: int


@router.get("", response_model=PaginatedShiftsResponse)
async def get_shifts(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    date_from: Optional[str] = Query(None, description="Filter by created_at >= date (ISO format YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter by created_at <= date (ISO format YYYY-MM-DD)"),
    status: Optional[str] = Query(None, description="Filter by status (open, closed)"),
    user_id: Optional[str] = Query(None, description="Filter by user_id"),
    session: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_or_foreman)
):
    """
    Get paginated list of shifts with optional filters.
    
    Filters:
        - date_from: Start date (inclusive)
        - date_to: End date (inclusive)
        - status: Shift status (open/closed)
        - user_id: Filter by specific worker
    
    Returns:
        Paginated list of shifts with metadata.
    """
    # Build base query
    query = session.query(Shift)
    
    # Apply filters
    filters = []
    
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from).replace(hour=0, minute=0, second=0, tzinfo=timezone.utc)
            filters.append(Shift.created_at >= dt_from)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date_from format: {date_from}")
    
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            filters.append(Shift.created_at <= dt_to)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date_to format: {date_to}")
    
    if status:
        filters.append(Shift.status == status)
    
    if user_id:
        filters.append(Shift.user_id == user_id)
    
    if filters:
        query = query.filter(and_(*filters))
    
    # Get total count (before pagination)
    total = query.count()
    
    # Calculate total pages
    pages = (total + limit - 1) // limit if total > 0 else 1
    
    # Apply pagination and ordering (newest first)
    offset = (page - 1) * limit
    shifts_db = query.order_by(desc(Shift.created_at)).offset(offset).limit(limit).all()
    
    # Convert to response models with duration calculation
    items = []
    for shift in shifts_db:
        # Calculate duration if shift is closed
        duration_hours = None
        if shift.ended_at and shift.created_at:
            duration_seconds = (shift.ended_at - shift.created_at).total_seconds()
            duration_hours = round(duration_seconds / 3600, 2)
        
        items.append(ShiftResponse(
            id=shift.id,
            user_id=shift.user_id,
            client_id=shift.client_id,
            work_address=shift.work_address,
            status=shift.status,
            created_at=shift.created_at.isoformat() if shift.created_at else "",
            ended_at=shift.ended_at.isoformat() if shift.ended_at else None,
            duration_hours=duration_hours
        ))
    
    return PaginatedShiftsResponse(
        items=items,
        total=total,
        pages=pages,
        page=page,
        limit=limit
    )
