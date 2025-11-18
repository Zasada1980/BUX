"""
API endpoints для управления зарплатами.
Импорт из Excel, просмотр, отчёты.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import date
from typing import List, Optional

from db import SessionLocal
from models import Salary, TelegramUser
from utils.salary_import import parse_salary_lines, apply_salary_import
from utils.money import fmt_money


router = APIRouter(prefix="/api/admin/salaries", tags=["salaries"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ========== SCHEMAS ==========

class SalaryImportPreviewIn(BaseModel):
    """Запрос на превью импорта зарплат."""
    raw_text: str = Field(..., description="TSV текст: Name\\tAmount")


class SalaryImportPreviewItem(BaseModel):
    """Элемент превью для одной строки."""
    id: int
    raw: str
    name: str
    amount: Optional[Decimal]
    worker_name: Optional[str]
    worker_id: Optional[int]
    status: str  # matched, no_match, invalid_amount


class SalaryImportPreviewOut(BaseModel):
    """Результат превью импорта."""
    preview: List[SalaryImportPreviewItem]
    matched_count: int
    total_count: int


class SalaryImportApplyIn(BaseModel):
    """Запрос на применение импорта."""
    raw_text: str
    payment_date: date = Field(..., description="Дата выплаты")


class SalaryImportApplyOut(BaseModel):
    """Результат применения импорта."""
    imported: int
    skipped: int
    message: str


class SalaryOut(BaseModel):
    """Модель зарплаты для API."""
    id: int
    worker_id: int
    worker_name: str
    amount: str  # Formatted as ₪1,234.56
    date: str  # YYYY-MM-DD
    source: str
    notes: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


# ========== ENDPOINTS ==========

@router.post("/import/preview", response_model=SalaryImportPreviewOut)
def import_preview(payload: SalaryImportPreviewIn, db: Session = Depends(get_db)):
    """
    Превью импорта зарплат из Excel.
    Парсит TSV текст и матчит имена с workers в БД.
    """
    parsed = parse_salary_lines(payload.raw_text, db)
    
    preview = []
    matched_count = 0
    
    for entry in parsed:
        worker = entry.get("worker")
        preview.append(SalaryImportPreviewItem(
            id=entry["id"],
            raw=entry["raw"],
            name=entry["name"],
            amount=entry["amount"],
            worker_name=worker.display_name if worker else None,
            worker_id=worker.id if worker else None,
            status=entry["status"]
        ))
        if entry["status"] == "matched":
            matched_count += 1
    
    return SalaryImportPreviewOut(
        preview=preview,
        matched_count=matched_count,
        total_count=len(parsed)
    )


@router.post("/import/apply", response_model=SalaryImportApplyOut)
def import_apply(payload: SalaryImportApplyIn, db: Session = Depends(get_db)):
    """
    Применение импорта зарплат в БД.
    Создаёт записи Salary для всех matched строк.
    """
    parsed = parse_salary_lines(payload.raw_text, db)
    result = apply_salary_import(parsed, payload.payment_date, db)
    
    return SalaryImportApplyOut(
        imported=result["imported"],
        skipped=result["skipped"],
        message=f"✅ Импортировано {result['imported']} зарплат, пропущено {result['skipped']}"
    )


@router.get("/list", response_model=List[SalaryOut])
def list_salaries(
    worker_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Список зарплат с фильтрацией.
    Опционально фильтр по worker_id.
    """
    query = db.query(Salary).join(TelegramUser, Salary.worker_id == TelegramUser.id)
    
    if worker_id:
        query = query.filter(Salary.worker_id == worker_id)
    
    salaries = query.order_by(Salary.date.desc()).limit(limit).all()
    
    result = []
    for s in salaries:
        worker = db.query(TelegramUser).filter(TelegramUser.id == s.worker_id).first()
        result.append(SalaryOut(
            id=s.id,
            worker_id=s.worker_id,
            worker_name=worker.display_name if worker else f"User#{s.worker_id}",
            amount=fmt_money(s.amount),
            date=s.date.isoformat(),
            source=s.source,
            notes=s.notes,
            created_at=s.created_at.isoformat()
        ))
    
    return result
