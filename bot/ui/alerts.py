# -*- coding: utf-8 -*-
"""
Bot UI alerts — унифицированные алерты для callback_query.answer().

BK-1 + BK-3: Алерты с индикаторами
"""

from bot.ui.indicators import get_icon
from bot.ui.messages import MSG


def alert(key: str, summary: str | None = None) -> str:
    """
    Возвращает короткий alert-текст с иконкой для answerCallbackQuery(show_alert=True).
    
    Args:
        key: Message key from MSG dict (e.g., 'approve_ok', 'reject_noop', 'forbidden')
        summary: Optional override summary (if None, uses MSG[key])
    
    Returns:
        Formatted alert string with emoji prefix
    
    Examples:
        >>> alert("approve_ok", "Expense #123")
        '✅ Expense #123'
        >>> alert("noop")
        '↩️ Уже обработано'
        >>> alert("forbidden")
        '🚫 Нет прав'
    """
    base = MSG.get(key, MSG.get("warning", "Внимание"))
    
    # Extract indicator key from compound keys (approve_ok -> approve)
    # Fallback to full key if no underscore
    parts = key.split("_", 1)
    indicator_key = parts[0] if len(parts) > 1 else key
    
    icon = get_icon(indicator_key)
    
    # If icon is default and we have compound key, try second part
    if icon == "ℹ️" and len(parts) > 1:
        icon = get_icon(parts[1])  # 'approve_ok' -> try 'ok'
    
    return f"{icon} {summary or base}"


def alert_with_id(key: str, kind: str, item_id: int) -> str:
    """
    Convenience wrapper для алертов с ID объекта.
    
    Args:
        key: Message key (approve_ok, reject_noop, etc.)
        kind: Item kind (expense, task, etc.)
        item_id: Item ID
    
    Returns:
        Formatted alert with ID
    
    Examples:
        >>> alert_with_id("approve_ok", "expense", 123)
        '✅ Подтверждено: expense #123'
    """
    base = MSG.get(key, "Готово")
    icon = get_icon(key.split("_", 1)[0])
    return f"{icon} {base}: {kind} #{item_id}"


def alert_outcome(outcome: str, summary: str) -> str:
    """
    Простой алерт по outcome (ok|noop|failed|forbidden) без составных ключей.
    
    Args:
        outcome: Simple outcome key (ok, noop, failed, forbidden)
        summary: Summary text
    
    Returns:
        Formatted alert string
    
    Examples:
        >>> alert_outcome("ok", "Операция завершена")
        '✅ Операция завершена'
        >>> alert_outcome("forbidden", "Нет прав на действие")
        '🚫 Нет прав на действие'
    """
    icon = get_icon(outcome)
    return f"{icon} {summary}"


# Evidence metadata
__evidence__ = {
    "functions": ["alert", "alert_with_id", "alert_outcome"],
    "dependencies": ["indicators.get_icon", "messages.MSG"],
    "version": "1.0.0-bk1",
}
