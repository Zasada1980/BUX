"""
Salary import utilities — адаптация логики из accounting-system-offline-v1.2.0
Парсит Excel-формат (Name\tAmount) и матчит с workers в БД.
"""
from typing import List, Dict, Optional
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session
from models import Salary, TelegramUser
from datetime import date


def normalize_name(name: str) -> str:
    """Нормализация имени для матчинга (lowercase, trim)."""
    return name.strip().lower() if name else ""


def parse_salary_lines(raw_text: str, session: Session) -> List[Dict]:
    """
    Парсинг TSV/Excel текста в формате:
        Name\tAmount
        Виталик\t5000
        Дима\t4500.50
    
    Returns:
        List of dicts: {
            "id": row_num,
            "raw": original_line,
            "name": parsed_name,
            "amount": Decimal or None,
            "worker": TelegramUser or None,
            "status": "matched" | "no_match" | "invalid_amount"
        }
    """
    results = []
    workers = session.query(TelegramUser).filter(TelegramUser.is_active == 1).all()
    worker_map = {normalize_name(w.display_name or w.user_id): w for w in workers}
    
    for idx, line in enumerate(raw_text.split('\n'), start=1):
        line = line.strip()
        if not line:
            continue
        
        # Парсинг по табу или точке с запятой
        cols = [c.strip() for c in line.replace('\t', ';').split(';')]
        name = cols[0] if cols else ""
        amount_str = cols[1] if len(cols) > 1 else ""
        
        # Парсинг суммы
        try:
            amount = Decimal(amount_str.replace(',', '.'))
        except (InvalidOperation, ValueError):
            amount = None
        
        # Матчинг с workers
        worker = worker_map.get(normalize_name(name))
        status = "matched" if worker and amount is not None else \
                 "no_match" if not worker else "invalid_amount"
        
        results.append({
            "id": idx,
            "raw": line,
            "name": name,
            "amount": amount,
            "worker": worker,
            "status": status
        })
    
    return results


def apply_salary_import(
    preview: List[Dict],
    payment_date: date,
    session: Session
) -> Dict[str, int]:
    """
    Применение импорта зарплат в БД.
    
    Args:
        preview: Результат parse_salary_lines()
        payment_date: Дата выплаты
        session: DB session
    
    Returns:
        {"imported": count, "skipped": count}
    """
    imported = 0
    skipped = 0
    
    for entry in preview:
        if entry["status"] != "matched" or entry["amount"] is None:
            skipped += 1
            continue
        
        salary = Salary(
            worker_id=entry["worker"].id,
            amount=entry["amount"],
            date=payment_date,
            source="import",
            notes=f"Imported from Excel: {entry['raw']}"
        )
        session.add(salary)
        imported += 1
    
    session.commit()
    return {"imported": imported, "skipped": skipped}
