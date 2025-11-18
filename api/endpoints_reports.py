"""Monthly reports CSV export endpoints."""
import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from db import SessionLocal
from utils.monthly_report import build_monthly_report
from utils.money import fmt_money


router = APIRouter(prefix="/api/admin/reports", tags=["reports"])


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/monthly.csv")
def export_monthly_csv(
    month: str = Query(..., description="Месяц в формате YYYY-MM"),
    worker_id: Optional[int] = Query(None, description="ID работника (опционально)"),
    db: Session = Depends(get_db)
):
    """
    Экспорт месячного отчёта в CSV формате.
    
    Args:
        month: Месяц в формате 'YYYY-MM' (например, '2024-11')
        worker_id: ID конкретного работника (None = все работники)
        
    Returns:
        CSV файл с колонками:
        - Работник
        - Дней работал
        - Часов (смены)
        - Задач (количество)
        - Задачи (сумма)
        - Расходы (количество)
        - Расходы (сумма)
        - Зарплаты (количество)
        - Зарплаты (сумма)
    """
    # Получаем агрегированные данные
    report_data = build_monthly_report(month, worker_id, db)
    
    # Создаём CSV в памяти
    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    
    # Заголовок
    writer.writerow([
        "Работник",
        "Дней работал",
        "Часов (смены)",
        "Задач (шт)",
        "Задачи (₪)",
        "Расходы (шт)",
        "Расходы (₪)",
        "Зарплаты (шт)",
        "Зарплаты (₪)"
    ])
    
    # Данные
    from decimal import Decimal
    for worker in report_data:
        writer.writerow([
            worker["worker_name"] or f"User#{worker['worker_id']}",
            worker["days_worked"],
            f"{float(worker['total_hours']):.2f}",
            worker["tasks_count"],
            fmt_money(worker["tasks_total"]),
            worker["expenses_count"],
            fmt_money(worker["expenses_total"]),
            worker["salary_count"],
            fmt_money(worker["salary_total"])
        ])
    
    # Итоговая строка
    if len(report_data) > 1:
        total_hours = sum(w["total_hours"] for w in report_data)
        total_tasks = sum(w["tasks_total"] for w in report_data)
        total_expenses = sum(w["expenses_total"] for w in report_data)
        total_salaries = sum(w["salary_total"] for w in report_data)
        
        writer.writerow([])  # Пустая строка
        writer.writerow([
            "ИТОГО",
            "",  # Дней работал (не суммируем)
            f"{float(total_hours):.2f}",
            sum(w["tasks_count"] for w in report_data),
            fmt_money(total_tasks),
            sum(w["expenses_count"] for w in report_data),
            fmt_money(total_expenses),
            sum(w["salary_count"] for w in report_data),
            fmt_money(total_salaries)
        ])
    
    # Возвращаем как StreamingResponse
    output.seek(0)
    filename = f"monthly_report_{month}"
    if worker_id:
        filename += f"_worker{worker_id}"
    filename += ".csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "text/csv; charset=utf-8"
        }
    )


@router.get("/monthly.json")
def export_monthly_json(
    month: str = Query(..., description="Месяц в формате YYYY-MM"),
    worker_id: Optional[int] = Query(None, description="ID работника (опционально)"),
    db: Session = Depends(get_db)
):
    """
    Экспорт месячного отчёта в JSON формате (для bot UI).
    
    Возвращает детальные данные с разбивкой по работникам.
    """
    report_data = build_monthly_report(month, worker_id, db)
    
    # Конвертируем Decimal в str для JSON serialization
    for worker in report_data:
        worker["total_hours"] = str(worker["total_hours"])
        worker["tasks_total"] = fmt_money(worker["tasks_total"])
        worker["expenses_total"] = fmt_money(worker["expenses_total"])
        worker["salary_total"] = fmt_money(worker["salary_total"])
    
    return {
        "month": month,
        "worker_id": worker_id,
        "workers": report_data,
        "summary": {
            "total_workers": len(report_data),
            "total_hours": sum(float(w["total_hours"]) for w in report_data),
            "total_tasks": sum(w["tasks_count"] for w in report_data),
            "total_expenses": sum(w["expenses_count"] for w in report_data),
            "total_salaries": sum(w["salary_count"] for w in report_data)
        }
    }
