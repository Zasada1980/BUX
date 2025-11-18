"""Worker shift reporting endpoint."""
from datetime import datetime
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from db import SessionLocal

router = APIRouter(prefix="/api", tags=["reports"])


def _parse_date(s: str) -> datetime:
    """Parse ISO8601 or YYYY-MM-DD date string."""
    try:
        # ISO8601 or YYYY-MM-DD
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception as e:
        raise HTTPException(400, f"bad date: {s}") from e


@router.get("/report.worker/{user_id}")
def report_worker(
    user_id: str,
    frm: str = Query(..., alias="from"),
    to: str = Query(...),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Get worker shift report with aggregates and pagination.
    
    Args:
        user_id: Worker identifier
        frm: Start date (ISO8601 or YYYY-MM-DD)
        to: End date (ISO8601 or YYYY-MM-DD)
        limit: Max items to return (1-1000)
        offset: Pagination offset
    
    Returns:
        {
            "user_id": str,
            "period": {"from": ISO, "to": ISO},
            "summary": {
                "shift_count": int,
                "first_at": ISO,
                "last_at": ISO,
                "open_count": int,
                "closed_count": int
            },
            "paging": {"limit": int, "offset": int, "count": int},
            "items": [{"id": int, "user_id": str, "status": str, "created_at": ISO}]
        }
    """
    if not user_id:
        raise HTTPException(400, "user_id required")

    dt_from = _parse_date(frm)
    dt_to = _parse_date(to)
    if dt_to < dt_from:
        raise HTTPException(400, "to < from")

    sql_meta = text("""
        SELECT
          COUNT(*) AS shift_count,
          MIN(created_at) AS first_at,
          MAX(created_at) AS last_at,
          SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) AS open_count,
          SUM(CASE WHEN status<>'open' THEN 1 ELSE 0 END) AS closed_count
        FROM shifts
        WHERE user_id=:uid AND created_at BETWEEN :f AND :t
    """)

    sql_items = text("""
        SELECT id, user_id, status, created_at
        FROM shifts
        WHERE user_id=:uid AND created_at BETWEEN :f AND :t
        ORDER BY created_at ASC
        LIMIT :lim OFFSET :off
    """)

    with SessionLocal() as s:
        meta = dict(s.execute(
            sql_meta,
            {"uid": user_id, "f": dt_from, "t": dt_to}
        ).mappings().first() or {})
        
        items = [dict(r) for r in s.execute(
            sql_items,
            {"uid": user_id, "f": dt_from, "t": dt_to, "lim": limit, "off": offset}
        ).mappings().all()]

    return {
        "user_id": user_id,
        "period": {"from": dt_from.isoformat(), "to": dt_to.isoformat()},
        "summary": meta,
        "paging": {"limit": limit, "offset": offset, "count": len(items)},
        "items": items
    }
