"""Work records aggregation endpoints."""
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime
from typing import Optional
from decimal import Decimal
import csv
import json
import io
from models import Employee
from schemas_work_records import WorkRecordItem, WorkRecordsOut, WorkRecordsExportFormat
from auth import get_db, require_foreman

router = APIRouter(prefix="/api/work-records", tags=["work-records"])


@router.get("", response_model=WorkRecordsOut)
async def get_work_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    user_id: Optional[str] = None,
    client_id: Optional[int] = None,
    employee: Employee = Depends(require_foreman),  # Foreman+ can view
    db: Session = Depends(get_db)
):
    """
    Get aggregated work records (shifts + tasks + expenses).
    
    Uses complex 3-CTE SQL query for efficient aggregation.
    
    RBAC:
    - Admin: sees all records
    - Foreman: sees only assigned workers (TODO: implement assignment logic)
    - Worker: forbidden (use /api/v1/shifts for own records)
    """
    # Build WHERE conditions
    conditions = ["s.status = 'closed'"]  # Only completed shifts
    params = {}
    
    if date_from:
        conditions.append("DATE(s.created_at) >= :date_from")
        params["date_from"] = date_from
    
    if date_to:
        conditions.append("DATE(s.created_at) <= :date_to")
        params["date_to"] = date_to
    
    if user_id:
        conditions.append("s.user_id = :user_id")
        params["user_id"] = user_id
    
    if client_id:
        conditions.append("s.client_id = :client_id")
        params["client_id"] = client_id
    
    # RBAC: Foreman sees only workers
    # TODO: Add foreman → workers assignment table
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    # Complex 3-CTE query (from INTEGRATION_SPEC.md Section 4.3)
    query = f"""
    WITH shift_data AS (
        SELECT
            s.id AS shift_id,
            s.user_id,
            s.client_id,
            s.work_address,
            s.created_at AS shift_start,
            s.ended_at AS shift_end,
            CASE
                WHEN s.ended_at IS NOT NULL
                THEN ROUND(CAST((julianday(s.ended_at) - julianday(s.created_at)) * 24 AS NUMERIC), 2)
                ELSE NULL
            END AS shift_duration_hours
        FROM shifts s
        WHERE {where_clause}
    ),
    tasks_agg AS (
        SELECT
            t.shift_id,
            COUNT(*) AS task_count,
            GROUP_CONCAT(t.description, '; ') AS task_descriptions
        FROM worker_tasks t
        GROUP BY t.shift_id
    ),
    expenses_agg AS (
        SELECT
            e.shift_id,
            COUNT(*) AS expense_count,
            SUM(e.amount) AS total_expenses,
            GROUP_CONCAT(e.category || ':' || CAST(e.amount AS TEXT), ', ') AS expense_breakdown
        FROM worker_expenses e
        GROUP BY e.shift_id
    )
    SELECT
        sd.*,
        COALESCE(ta.task_count, 0) AS task_count,
        COALESCE(ta.task_descriptions, '') AS task_descriptions,
        COALESCE(ea.expense_count, 0) AS expense_count,
        COALESCE(ea.total_expenses, 0) AS total_expenses,
        COALESCE(ea.expense_breakdown, '') AS expense_breakdown,
        c.company_name AS client_name,
        u.name AS employee_name
    FROM shift_data sd
    LEFT JOIN tasks_agg ta ON sd.shift_id = ta.shift_id
    LEFT JOIN expenses_agg ea ON sd.shift_id = ea.shift_id
    LEFT JOIN clients c ON sd.client_id = c.id
    LEFT JOIN users u ON sd.user_id = CAST(u.telegram_id AS TEXT)
    ORDER BY sd.shift_start DESC
    LIMIT :limit OFFSET :offset
    """
    
    # Count query
    count_query = f"""
    SELECT COUNT(*) FROM shifts s WHERE {where_clause}
    """
    
    # Execute count
    total = db.execute(text(count_query), params).scalar()
    
    # Execute main query
    limit_val = page_size
    offset_val = (page - 1) * page_size
    
    # Use f-string for LIMIT/OFFSET as they don't work with :param binding
    query_with_limit = query.replace(":limit", str(limit_val)).replace(":offset", str(offset_val))
    
    rows = db.execute(text(query_with_limit), params).fetchall()
    
    # Parse results
    records = []
    for row in rows:
        # Parse expense breakdown
        expense_breakdown = {}
        if row.expense_breakdown:
            for item in row.expense_breakdown.split(', '):
                if ':' in item:
                    category, amount_str = item.split(':', 1)
                    expense_breakdown[category] = Decimal(amount_str) / 100  # Convert agorot → ILS
        
        # Parse task descriptions
        task_descriptions = []
        if row.task_descriptions:
            task_descriptions = [desc.strip() for desc in row.task_descriptions.split('; ') if desc.strip()]
        
        records.append(WorkRecordItem(
            shift_id=row.shift_id,
            user_id=row.user_id,
            employee_name=row.employee_name,
            client_id=row.client_id,
            client_name=row.client_name,
            work_address=row.work_address,
            shift_start=row.shift_start,
            shift_end=row.shift_end,
            shift_duration_hours=Decimal(str(row.shift_duration_hours)) if row.shift_duration_hours else None,
            task_count=row.task_count,
            task_descriptions=task_descriptions,
            expense_count=row.expense_count,
            total_expenses=Decimal(row.total_expenses) / 100,  # Convert agorot → ILS
            expense_breakdown=expense_breakdown
        ))
    
    return WorkRecordsOut(
        records=records,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/export", response_model=None)
async def export_work_records(
    format: WorkRecordsExportFormat = Query(WorkRecordsExportFormat.CSV),
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    user_id: Optional[str] = None,
    client_id: Optional[int] = None,
    employee: Employee = Depends(require_foreman),  # Foreman+ can export
    db: Session = Depends(get_db)
):
    """
    Export work records as CSV or JSON.
    
    Returns downloadable file.
    """
    # Get all records (no pagination for export)
    conditions = ["s.status = 'closed'"]
    params = {}
    
    if date_from:
        conditions.append("DATE(s.created_at) >= :date_from")
        params["date_from"] = date_from
    
    if date_to:
        conditions.append("DATE(s.created_at) <= :date_to")
        params["date_to"] = date_to
    
    if user_id:
        conditions.append("s.user_id = :user_id")
        params["user_id"] = user_id
    
    if client_id:
        conditions.append("s.client_id = :client_id")
        params["client_id"] = client_id
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    # Query (no LIMIT for export)
    query = f"""
    WITH shift_data AS (
        SELECT
            s.id AS shift_id,
            s.user_id,
            s.client_id,
            s.work_address,
            s.created_at AS shift_start,
            s.ended_at AS shift_end,
            CASE
                WHEN s.ended_at IS NOT NULL
                THEN ROUND(CAST((julianday(s.ended_at) - julianday(s.created_at)) * 24 AS NUMERIC), 2)
                ELSE NULL
            END AS shift_duration_hours
        FROM shifts s
        WHERE {where_clause}
    ),
    tasks_agg AS (
        SELECT
            t.shift_id,
            COUNT(*) AS task_count,
            GROUP_CONCAT(t.description, '; ') AS task_descriptions
        FROM worker_tasks t
        GROUP BY t.shift_id
    ),
    expenses_agg AS (
        SELECT
            e.shift_id,
            COUNT(*) AS expense_count,
            SUM(e.amount) AS total_expenses
        FROM worker_expenses e
        GROUP BY e.shift_id
    )
    SELECT
        sd.shift_id,
        sd.user_id,
        u.name AS employee_name,
        c.company_name AS client_name,
        sd.work_address,
        sd.shift_start,
        sd.shift_end,
        sd.shift_duration_hours,
        COALESCE(ta.task_count, 0) AS task_count,
        COALESCE(ta.task_descriptions, '') AS task_descriptions,
        COALESCE(ea.expense_count, 0) AS expense_count,
        COALESCE(ea.total_expenses, 0) / 100.0 AS total_expenses_ils
    FROM shift_data sd
    LEFT JOIN tasks_agg ta ON sd.shift_id = ta.shift_id
    LEFT JOIN expenses_agg ea ON sd.shift_id = ea.shift_id
    LEFT JOIN clients c ON sd.client_id = c.id
    LEFT JOIN users u ON sd.user_id = CAST(u.telegram_id AS TEXT)
    ORDER BY sd.shift_start DESC
    """
    
    rows = db.execute(text(query), params).fetchall()
    
    if format == WorkRecordsExportFormat.CSV:
        # Generate CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "Shift ID", "User ID", "Employee Name", "Client Name",
            "Work Address", "Shift Start", "Shift End", "Duration (hours)",
            "Task Count", "Task Descriptions", "Expense Count", "Total Expenses (ILS)"
        ])
        
        # Rows
        for row in rows:
            writer.writerow([
                row.shift_id,
                row.user_id,
                row.employee_name or "",
                row.client_name or "",
                row.work_address or "",
                row.shift_start.isoformat() if row.shift_start else "",
                row.shift_end.isoformat() if row.shift_end else "",
                float(row.shift_duration_hours) if row.shift_duration_hours else "",
                row.task_count,
                row.task_descriptions,
                row.expense_count,
                float(row.total_expenses_ils)
            ])
        
        # Return as download
        output.seek(0)
        filename = f"work_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),  # BOM for Excel
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    else:  # JSON
        # Convert rows to dicts
        data = []
        for row in rows:
            data.append({
                "shift_id": row.shift_id,
                "user_id": row.user_id,
                "employee_name": row.employee_name,
                "client_name": row.client_name,
                "work_address": row.work_address,
                "shift_start": row.shift_start.isoformat() if row.shift_start else None,
                "shift_end": row.shift_end.isoformat() if row.shift_end else None,
                "shift_duration_hours": float(row.shift_duration_hours) if row.shift_duration_hours else None,
                "task_count": row.task_count,
                "task_descriptions": row.task_descriptions.split('; ') if row.task_descriptions else [],
                "expense_count": row.expense_count,
                "total_expenses_ils": float(row.total_expenses_ils)
            })
        
        filename = f"work_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        return Response(
            content=json.dumps(data, indent=2, ensure_ascii=False),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
