"""Monthly report aggregation for TelegramOllama."""
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from models import Shift, Task, Expense, Salary, TelegramUser


def build_monthly_report(
    month: str,
    worker_id: Optional[int],
    session: Session
) -> List[Dict]:
    """
    Агрегация данных по работникам за месяц.
    
    Args:
        month: Месяц в формате 'YYYY-MM' (например, '2024-11')
        worker_id: ID конкретного работника (None = все работники)
        session: SQLAlchemy session
        
    Returns:
        List[Dict]: Список работников с агрегированными данными
        [
            {
                "worker_id": int,
                "worker_name": str,
                "total_hours": Decimal,
                "tasks_count": int,
                "tasks_total": Decimal,  # Сумма по задачам
                "expenses_count": int,
                "expenses_total": Decimal,  # Сумма расходов
                "salary_count": int,
                "salary_total": Decimal,  # Сумма зарплат
                "days_worked": int,  # Количество уникальных дней
                "details": {
                    "shifts": [...],  # Детали смен
                    "tasks": [...],   # Детали задач
                    "expenses": [...], # Детали расходов
                    "salaries": [...] # Детали зарплат
                }
            }
        ]
    """
    # Фильтры для месяца (YYYY-MM)
    month_start = f"{month}-01"
    # Следующий месяц для верхней границы
    year, m = map(int, month.split('-'))
    next_month = f"{year if m < 12 else year+1}-{m+1 if m < 12 else 1:02d}-01"
    
    # Запросы с фильтрацией по месяцу
    # ПРИМЕЧАНИЕ: tasks/expenses не имеют прямого date, только через shift.created_at
    # Упрощённая версия: используем только shifts и salaries
    shifts_query = session.query(Shift).filter(
        Shift.created_at >= month_start,
        Shift.created_at < next_month
    )
    
    salaries_query = session.query(Salary).filter(
        Salary.date >= month_start,
        Salary.date < next_month
    )
    
    # Фильтр по конкретному работнику
    if worker_id:
        # Получаем user_id по worker_id
        worker = session.query(TelegramUser).filter(TelegramUser.id == worker_id).first()
        if worker:
            shifts_query = shifts_query.filter(Shift.user_id == worker.user_id)
        salaries_query = salaries_query.filter(Salary.worker_id == worker_id)
    
    # Получаем данные
    shifts = shifts_query.all()
    salaries = salaries_query.all()
    
    # Агрегация по работникам
    workers_data = defaultdict(lambda: {
        "worker_id": None,
        "worker_name": None,
        "total_hours": Decimal('0'),
        "tasks_count": 0,
        "tasks_total": Decimal('0'),
        "expenses_count": 0,
        "expenses_total": Decimal('0'),
        "salary_count": 0,
        "salary_total": Decimal('0'),
        "days_worked": set(),  # Множество уникальных дат
        "details": {
            "shifts": [],
            "tasks": [],
            "expenses": [],
            "salaries": []
        }
    })
    
    # Агрегация смен
    for shift in shifts:
        # Получаем worker_id по user_id (telegram_users.user_id → id)
        worker = session.query(TelegramUser).filter(TelegramUser.user_id == shift.user_id).first()
        if not worker:
            continue  # Пропускаем смены без привязки к работнику
        
        wid = worker.id
        workers_data[wid]["worker_id"] = wid
        workers_data[wid]["worker_name"] = worker.display_name if worker.display_name else f"User#{wid}"
        
        # Расчёт часов
        if shift.created_at and shift.ended_at:
            start = shift.created_at
            end = shift.ended_at
            hours = Decimal(str((end - start).total_seconds() / 3600))
            workers_data[wid]["total_hours"] += hours
            
            # Добавляем день
            shift_date = start.strftime("%Y-%m-%d")
            workers_data[wid]["days_worked"].add(shift_date)
            
            workers_data[wid]["details"]["shifts"].append({
                "id": shift.id,
                "date": shift_date,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "hours": float(hours)
            })
    
    # Агрегация зарплат
    for salary in salaries:
        wid = salary.worker_id
        if wid not in workers_data:
            worker = session.query(TelegramUser).filter(TelegramUser.id == wid).first()
            workers_data[wid]["worker_id"] = wid
            workers_data[wid]["worker_name"] = worker.display_name if worker else f"User#{wid}"
        
        workers_data[wid]["salary_count"] += 1
        workers_data[wid]["salary_total"] += salary.amount or Decimal('0')
        workers_data[wid]["details"]["salaries"].append({
            "id": salary.id,
            "date": str(salary.date),
            "amount": str(salary.amount or 0),
            "source": salary.source
        })
    
    # Конвертируем set в int для days_worked
    result = []
    for wid, data in workers_data.items():
        data["days_worked"] = len(data["days_worked"])
        result.append(data)
    
    # Сортируем по имени работника
    result.sort(key=lambda x: x["worker_name"] or "")
    
    return result
