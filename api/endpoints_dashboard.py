"""
Dashboard API endpoints for Work Ledger.
Provides KPIs, timeseries data, and recent activity for admin/foreman users.

RBAC: admin, foreman only (worker access denied).
"""
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, and_, Numeric
from sqlalchemy.orm import Session

from auth import get_current_employee, get_db
from models import Shift, Expense, Invoice, Task, Employee

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def require_admin_or_foreman(current_user: Employee = Depends(get_current_employee)):
    """Dependency to ensure user is admin or foreman."""
    if current_user.role not in ("admin", "foreman"):
        raise HTTPException(
            status_code=403,
            detail="Access denied: Dashboard requires admin or foreman role"
        )
    return current_user


@router.get("/summary")
async def get_dashboard_summary(
    period_days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    session: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_or_foreman)
):
    """
    Get dashboard summary KPIs for specified period.
    
    Returns:
        - period_days: requested period
        - cutoff_date: start date of analysis (UTC)
        - active_shifts: number of shifts in period
        - total_expenses: sum of expenses in period (in agorot/cents)
        - total_invoices_paid: sum of paid invoices in period
        - pending_items: always 0 (no pending_changes table yet)
        - generated_at: timestamp of response
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=period_days)
    
    # Active shifts in period
    active_shifts = session.query(func.count(Shift.id)).filter(
        Shift.created_at >= cutoff_date
    ).scalar() or 0
    
    # Total expenses in period (amount stored in agorot/cents)
    total_expenses = session.query(func.sum(Expense.amount)).filter(
        Expense.created_at >= cutoff_date
    ).scalar() or 0
    
    # Total paid invoices in period
    # Assuming Invoice.status='paid' and total is stored as string Decimal
    paid_invoices_sum = session.query(func.sum(
        func.cast(Invoice.total, Numeric(18, 2))
    )).filter(
        and_(
            Invoice.status == 'paid',
            Invoice.created_at >= cutoff_date
        )
    ).scalar() or 0
    
    return {
        "period_days": period_days,
        "cutoff_date": cutoff_date.isoformat(),
        "active_shifts": active_shifts,
        "total_expenses": int(total_expenses),
        "total_invoices_paid": float(paid_invoices_sum),
        "pending_items": 0,  # No pending_changes table in schema
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


@router.get("/timeseries")
async def get_dashboard_timeseries(
    period_days: int = Query(7, ge=1, le=365),
    metric: Literal["expenses", "invoices"] = Query("expenses", description="Metric to aggregate"),
    session: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_or_foreman)
):
    """
    Get daily timeseries data for specified metric.
    
    Returns array of { date: "YYYY-MM-DD", value: number }
    """
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=period_days)
    
    if metric == "expenses":
        # Group expenses by date
        results = session.query(
            func.date(Expense.created_at).label("date"),
            func.sum(Expense.amount).label("value")
        ).filter(
            Expense.created_at >= cutoff_date
        ).group_by(
            func.date(Expense.created_at)
        ).order_by("date").all()
        
        return [
            {"date": str(row.date), "value": int(row.value or 0)}
            for row in results
        ]
    
    elif metric == "invoices":
        # Group invoices by created_at date
        results = session.query(
            func.date(Invoice.created_at).label("date"),
            func.sum(func.cast(Invoice.total, Numeric(18, 2))).label("value")
        ).filter(
            Invoice.created_at >= cutoff_date
        ).group_by(
            func.date(Invoice.created_at)
        ).order_by("date").all()
        
        return [
            {"date": str(row.date), "value": float(row.value or 0)}
            for row in results
        ]
    
    return []


@router.get("/recent")
async def get_dashboard_recent(
    resource: Literal["expenses", "invoices", "tasks"] = Query("expenses"),
    limit: int = Query(5, ge=1, le=50),
    session: Session = Depends(get_db),
    current_user: Employee = Depends(require_admin_or_foreman)
):
    """
    Get recent items of specified resource type.
    
    Returns array of:
        - id: item ID
        - type: "expense" | "invoice" | "task"
        - summary: description or title
        - amount: monetary value (if applicable)
        - date: creation date
        - created_at: ISO timestamp
    """
    if resource == "expenses":
        items = session.query(Expense).order_by(
            Expense.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": item.id,
                "type": "expense",
                "summary": f"{item.category} expense",
                "amount": item.amount,
                "date": item.created_at.date().isoformat(),
                "created_at": item.created_at.isoformat()
            }
            for item in items
        ]
    
    elif resource == "invoices":
        items = session.query(Invoice).order_by(
            Invoice.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": item.id,
                "type": "invoice",
                "summary": f"Invoice {item.id} - {item.client_id}",
                "amount": float(item.total),
                "date": item.created_at.date().isoformat(),
                "created_at": item.created_at.isoformat()
            }
            for item in items
        ]
    
    elif resource == "tasks":
        items = session.query(Task).order_by(
            Task.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "id": item.id,
                "type": "task",
                "summary": item.description[:60] + ("..." if len(item.description) > 60 else ""),
                "amount": 0,  # Tasks don't have amount
                "date": item.created_at.date().isoformat(),
                "created_at": item.created_at.isoformat()
            }
            for item in items
        ]
    
    return []
