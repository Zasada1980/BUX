"""Work records aggregation schemas."""
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class WorkRecordItem(BaseModel):
    """Single work record item (shift + tasks + expenses)."""
    shift_id: int
    user_id: str
    employee_name: Optional[str] = None
    client_id: Optional[int] = None
    client_name: Optional[str] = None
    work_address: Optional[str] = None
    shift_start: datetime
    shift_end: Optional[datetime] = None
    shift_duration_hours: Optional[Decimal] = None
    task_count: int = 0
    task_descriptions: list[str] = []
    expense_count: int = 0
    total_expenses: Decimal = Decimal("0")
    expense_breakdown: dict[str, Decimal] = {}  # {category: amount}
    
    class Config:
        from_attributes = True


class WorkRecordsOut(BaseModel):
    """Work records list response."""
    records: list[WorkRecordItem]
    total: int
    page: int
    page_size: int


class WorkRecordsExportFormat(str, Enum):
    """Export format enum."""
    CSV = "csv"
    JSON = "json"
