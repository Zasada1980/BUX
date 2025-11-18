"""Rich card formatters for Telegram bot UI.

This module provides centralized formatting for:
- Task preview cards with emoji and inline edit buttons
- Expense preview cards with OCR indicators
- Shift detail cards with statistics
- Profile cards with monthly statistics

All formatters support Sprint UI-1 rich interface requirements.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from zoneinfo import ZoneInfo
from decimal import Decimal


def fmt_money(amount: Decimal, currency: str = "ILS") -> str:
    """Format money with proper symbol and separators.
    
    Args:
        amount: Decimal amount
        currency: Currency code (ILS/USD)
    
    Returns:
        Formatted string like "1,234.56₪"
    """
    symbol = "₪" if currency == "ILS" else "$"
    # Symbol at the end for Israeli shekel
    return f"{amount:,.2f}{symbol}"


def fmt_datetime(dt: datetime, tz: str = "Asia/Jerusalem") -> str:
    """Format datetime in Israel timezone.
    
    Args:
        dt: UTC datetime from database
        tz: Target timezone
    
    Returns:
        Formatted string like "12 ноября 2025, 09:31"
    """
    if dt.tzinfo is None:
        # Assume UTC if no timezone
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    
    local_dt = dt.astimezone(ZoneInfo(tz))
    
    # Russian month names
    months = [
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    
    month_name = months[local_dt.month - 1]
    return f"{local_dt.day} {month_name} {local_dt.year}, {local_dt.strftime('%H:%M')}"


def fmt_duration(seconds: float) -> str:
    """Format duration in hours and minutes.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted string like "8ч 30м"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    return f"{hours}ч {minutes}м"


def fmt_task_card(task: Dict[str, Any], show_buttons: bool = True) -> tuple[str, Optional[List]]:
    """Format task card with rich UI.
    
    Args:
        task: Task dict with keys: id, description, created_at, status
        show_buttons: Whether to include inline buttons
    
    Returns:
        Tuple of (formatted_text, keyboard_rows or None)
    """
    # Status emoji
    status_emoji = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌"
    }.get(task.get("status", "pending"), "⏳")
    
    status_text = {
        "pending": "На модерации",
        "approved": "Подтверждено",
        "rejected": "Отклонено"
    }.get(task.get("status", "pending"), "Неизвестно")
    
    lines = [
        f"📋 <b>ЗАДАЧА #{task['id']}</b>",
        "",
        f"📝 <b>Описание:</b>",
        f"├─ {task['description'][:100]}{'...' if len(task['description']) > 100 else ''}",
        "",
        f"📊 <b>Статус:</b> {status_emoji} {status_text}",
        f"⏰ <b>Создано:</b> {fmt_datetime(task['created_at'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    text = "\n".join(lines)
    
    keyboard_rows = None
    if show_buttons:
        from aiogram.types import InlineKeyboardButton
        
        keyboard_rows = [
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"wrk:task:edit:{task['id']}"),
                InlineKeyboardButton(text="👁️ Детали", callback_data=f"wrk:task:view:{task['id']}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="wrk:panel")
            ]
        ]
    
    return text, keyboard_rows


def fmt_expense_card(expense: Dict[str, Any], show_buttons: bool = True) -> tuple[str, Optional[List]]:
    """Format expense card with rich UI.
    
    Args:
        expense: Expense dict with keys: id, category, amount, created_at, status, ocr_metadata
        show_buttons: Whether to include inline buttons
    
    Returns:
        Tuple of (formatted_text, keyboard_rows or None)
    """
    # Category emoji
    category_emoji = {
        "transport": "🚗",
        "food": "🍽️",
        "materials": "🔨",
        "tools": "🔧",
        "other": "📦"
    }.get(expense.get("category", "other"), "📦")
    
    # Status emoji
    status_emoji = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌"
    }.get(expense.get("status", "pending"), "⏳")
    
    status_text = {
        "pending": "На модерации",
        "approved": "Подтверждено",
        "rejected": "Отклонено"
    }.get(expense.get("status", "pending"), "Неизвестно")
    
    # Convert amount from agorot to ILS
    amount_ils = Decimal(expense['amount']) / 100
    
    lines = [
        f"💰 <b>РАСХОД #{expense['id']}</b>",
        "",
        f"📊 <b>Детали:</b>",
        f"├─ Сумма: {fmt_money(amount_ils)}",
        f"├─ Категория: {category_emoji} {expense.get('category', 'other').title()}",
        f"└─ Статус: {status_emoji} {status_text}",
        ""
    ]
    
    # OCR metadata if present
    ocr_meta = expense.get("ocr_metadata", {})
    if isinstance(ocr_meta, dict) and ocr_meta.get("enabled"):
        ocr_status = ocr_meta.get("status", "off")
        if ocr_status == "ok":
            confidence = ocr_meta.get("confidence", 0)
            lines.append(f"📸 <b>OCR:</b> ✅ Проверено (confidence: {confidence}%)")
        elif ocr_status == "abstain":
            lines.append(f"📸 <b>OCR:</b> ⚠️ Требуется проверка")
        else:
            lines.append(f"📸 <b>OCR:</b> ❌ Не проверено")
        lines.append("")
    
    lines.extend([
        f"⏰ <b>Создано:</b> {fmt_datetime(expense['created_at'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ])
    
    text = "\n".join(lines)
    
    keyboard_rows = None
    if show_buttons:
        from aiogram.types import InlineKeyboardButton
        
        keyboard_rows = [
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"wrk:expense:edit:{expense['id']}"),
                InlineKeyboardButton(text="👁️ Детали", callback_data=f"wrk:expense:view:{expense['id']}")
            ],
            [
                InlineKeyboardButton(text="🔙 Назад", callback_data="wrk:panel")
            ]
        ]
    
    return text, keyboard_rows


def fmt_task_preview_short(task: Dict[str, Any]) -> str:
    """Format short task preview for list view.
    
    Args:
        task: Task dict
    
    Returns:
        Single-line formatted preview
    """
    status_emoji = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌"
    }.get(task.get("status", "pending"), "⏳")
    
    desc = task['description'][:40] + "..." if len(task['description']) > 40 else task['description']
    return f"📋 #{task['id']} {status_emoji} {desc}"


def fmt_expense_preview_short(expense: Dict[str, Any]) -> str:
    """Format short expense preview for list view.
    
    Args:
        expense: Expense dict
    
    Returns:
        Single-line formatted preview
    """
    status_emoji = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌"
    }.get(expense.get("status", "pending"), "⏳")
    
    category_emoji = {
        "transport": "🚗",
        "food": "🍽️",
        "materials": "🔨",
        "tools": "🔧",
        "other": "📦"
    }.get(expense.get("category", "other"), "📦")
    
    amount_ils = Decimal(expense['amount']) / 100
    return f"💰 #{expense['id']} {status_emoji} {category_emoji} {fmt_money(amount_ils)}"


def fmt_shift_detail(shift: Dict[str, Any], tasks: List[Dict], expenses: List[Dict]) -> str:
    """Format shift detail view with statistics.
    
    Args:
        shift: Shift dict with keys: id, created_at, ended_at
        tasks: List of task dicts
        expenses: List of expense dicts
    
    Returns:
        Formatted shift detail text
    """
    # Calculate duration
    if shift.get("ended_at"):
        duration = (shift["ended_at"] - shift["created_at"]).total_seconds()
    else:
        # Active shift - calculate from now
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc)
        duration = (now_utc - shift["created_at"]).total_seconds()
    
    # Status
    is_active = shift.get("ended_at") is None
    status_emoji = "🟢" if is_active else "⚪"
    status_text = "АКТИВНА" if is_active else "ЗАВЕРШЕНА"
    
    # Calculate totals
    tasks_total = len(tasks)
    expenses_total = sum(Decimal(e['amount']) / 100 for e in expenses)
    
    lines = [
        f"{status_emoji} <b>СМЕНА #{shift['id']}</b>",
        f"📅 {fmt_datetime(shift['created_at'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"⏰ <b>Время работы:</b>",
        f"├─ Начало: {shift['created_at'].strftime('%H:%M')}",
    ]
    
    if shift.get("ended_at"):
        lines.append(f"├─ Конец: {shift['ended_at'].strftime('%H:%M')}")
    else:
        lines.append(f"├─ Конец: (смена активна)")
    
    lines.extend([
        f"└─ Длительность: {fmt_duration(duration)}",
        "",
        f"📊 <b>Статистика:</b>",
        f"├─ Задач выполнено: {tasks_total}",
        f"└─ Расходов: {fmt_money(expenses_total)}",
        "",
    ])
    
    # Tasks list
    if tasks:
        lines.append(f"📋 <b>Выполненные задачи:</b>")
        for task in tasks[:5]:  # Show max 5
            lines.append(f"├─ {fmt_task_preview_short(task)}")
        if len(tasks) > 5:
            lines.append(f"└─ ... еще {len(tasks) - 5}")
        lines.append("")
    
    # Expenses list
    if expenses:
        lines.append(f"💸 <b>Расходы:</b>")
        for expense in expenses[:5]:  # Show max 5
            lines.append(f"├─ {fmt_expense_preview_short(expense)}")
        if len(expenses) > 5:
            lines.append(f"└─ ... еще {len(expenses) - 5}")
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


def fmt_worker_profile_rich(worker: Dict[str, Any], stats: Dict[str, Any]) -> str:
    """Format rich worker profile with statistics.
    
    Args:
        worker: Worker dict with keys: name, telegram_username, daily_salary, role
        stats: Statistics dict with keys: total_shifts, total_tasks, total_expenses, 
               monthly_shifts, monthly_hours, monthly_earnings
    
    Returns:
        Formatted profile text
    """
    lines = [
        f"👤 <b>МОЯ КАРТОЧКА</b>",
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
        f"📋 <b>Личная информация:</b>",
        f"├─ Имя: <b>{worker['name']}</b>",
        f"├─ Username: @{worker.get('telegram_username', 'не указано')}",
    ]
    
    if worker.get('phone'):
        lines.append(f"├─ Телефон: {worker['phone']}")
    
    lines.append(f"└─ Дневная ставка: {fmt_money(Decimal(worker['daily_salary']))}")
    lines.append("")
    
    # Monthly statistics
    lines.extend([
        f"📊 <b>Статистика за месяц:</b>",
        f"├─ Смен отработано: {stats.get('monthly_shifts', 0)}",
        f"├─ Часов отработано: {fmt_duration(stats.get('monthly_hours', 0) * 3600)}",
        f"├─ Задач выполнено: {stats.get('monthly_tasks', 0)}",
        f"└─ Расходов подано: {stats.get('monthly_expenses', 0)}",
        "",
        f"💰 <b>Заработок за месяц:</b>",
        f"└─ {fmt_money(Decimal(stats.get('monthly_earnings', 0)))}",
        "",
    ])
    
    # Current status
    if stats.get('active_shift'):
        shift_duration = stats.get('active_shift_duration', 0)
        lines.append(f"🔔 <b>Текущий статус:</b>")
        lines.append(f"🟢 Смена активна ({fmt_duration(shift_duration)})")
    else:
        lines.append(f"🔔 <b>Текущий статус:</b>")
        lines.append(f"⚪ Не на смене")
    
    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ])
    
    return "\n".join(lines)
