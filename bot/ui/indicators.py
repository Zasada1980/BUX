# -*- coding: utf-8 -*-
"""
UI indicators for bot actions.
Единая точка: outcome/состояние -> emoji + человекочитаемый префикс.
Используется в алертах, заголовках карточек, кнопках и логах.

BK-1: Словарь статусов и эмодзи
"""

from dataclasses import dataclass
from typing import Dict, Optional

# Базовая мапа (расширяемая). Ключи — стабильные outcome/состояния из API/бота.
INDICATOR_MAP: Dict[str, str] = {
    # Core states
    "in_progress": "⏳",
    "accepted": "✅",
    "ok": "✅",
    "noop": "↩️",
    "rejected": "❌",
    "failed": "❌",
    "fail": "❌",  # Alias for failed
    "forbidden": "🚫",
    "rate_limited": "🐢",
    "throttled": "🐢",
    "pending_review": "🟡",
    "needs_photo": "📷",
    
    # Hash/sync states
    "hash_match": "🟢",
    "hash_mismatch": "🟠",
    
    # General states
    "info": "ℹ️",
    "warning": "⚠️",
    "error": "❌",
    
    # Action-specific
    "approve": "✅",
    "reject": "❌",
    "retry": "🔁",
    "refresh": "🔄",
    "disabled": "▫",
    
    # Invoice/document states
    "invoice_ready": "🧾",
    "invoice_draft": "📝",
    
    # Shift states
    "shift_open": "🟢",
    "shift_closed": "🔴",
    
    # Network states
    "timeout": "⏱️",
    "server_error": "❌",
}

DEFAULT_ICON = "ℹ️"


@dataclass(frozen=True)
class UiIndicator:
    """Typed indicator with icon and optional label."""
    key: str
    icon: str
    label: str = ""


def get_icon(key: str) -> str:
    """
    Возвращает иконку по ключу (с дефолтом).
    
    Args:
        key: Outcome/state key (e.g., 'ok', 'noop', 'forbidden')
    
    Returns:
        Emoji string (single character/grapheme cluster)
    
    Examples:
        >>> get_icon("ok")
        '✅'
        >>> get_icon("noop")
        '↩️'
        >>> get_icon("unknown")
        'ℹ️'
    """
    return INDICATOR_MAP.get(key, DEFAULT_ICON)


def indicator(key: str, label: Optional[str] = None) -> UiIndicator:
    """
    Typed-обёртка для удобства.
    
    Args:
        key: State key from INDICATOR_MAP
        label: Optional human-readable label
    
    Returns:
        UiIndicator dataclass instance
    """
    return UiIndicator(key=key, icon=get_icon(key), label=label or "")


def prefix_text(key: str, text: str, label: Optional[str] = None) -> str:
    """
    Добавляет префикс 'ICON [LABEL] ' к тексту.
    
    Args:
        key: Indicator key
        text: Main text to prefix
        label: Optional label to insert between icon and text
    
    Returns:
        Formatted string with emoji prefix
    
    Examples:
        >>> prefix_text("ok", "Операция завершена")
        '✅ Операция завершена'
        >>> prefix_text("ok", "Операция завершена", "OK")
        '✅ OK · Операция завершена'
    """
    ic = get_icon(key)
    if label:
        return f"{ic} {label} · {text}"
    return f"{ic} {text}"


def render_outcome(outcome: str, summary: str) -> str:
    """
    Унификация для answerCallbackQuery(show_alert=True):
    outcome ("ok" | "noop" | "failed" | "forbidden" | ...) + короткий summary.
    
    Args:
        outcome: State key (ok, noop, failed, etc.)
        summary: Brief description text
    
    Returns:
        Formatted alert string with emoji
    
    Examples:
        >>> render_outcome("ok", "Expense approved")
        '✅ Expense approved'
        >>> render_outcome("noop", "Already processed")
        '↩️ Already processed'
    """
    return prefix_text(outcome, summary)


def render_banner(
    action: str,
    outcome: str,
    kind: str,
    item_id: int,
    amount: Optional[str] = None
) -> str:
    """
    Render post-result banner for approve/reject/detail actions.
    Combines action+outcome into a compound key, extracts icon, adds item info and optional amount.
    
    BK-3: Унифицированный post-result баннер для editMessageText.
    
    Args:
        action: "approve", "reject", "detail"
        outcome: "ok", "noop", "fail"
        kind: "expense", "pending_change", "task" (or short: 'e', 'p', 't')
        item_id: Item ID number
        amount: Optional formatted money string (from fmt_amount)
        
    Returns:
        Compact banner ≤30 chars text (excluding ID/amount): "✅ Подтверждён · #E12 · ‎₪123.45"
        
    Examples:
        >>> render_banner("approve", "ok", "expense", 12)
        '✅ Подтверждён · #E12'
        >>> render_banner("approve", "noop", "expense", 12)
        '↩️ Уже подтверждён · #E12'
        >>> render_banner("reject", "ok", "expense", 12, "‎₪123.45")
        '❌ Отклонён · #E12 · ‎₪123.45'
        >>> render_banner("approve", "fail", "expense", 12)
        '❌ Ошибка · #E12'
    """
    from bot.ui.messages import MSG
    
    # Map kind to short letter for compact display
    kind_map = {
        'expense': 'E', 'e': 'E',
        'pending_change': 'P', 'p': 'P',
        'task': 'T', 't': 'T'
    }
    kind_letter = kind_map.get(kind, kind[0].upper() if kind else 'X')
    
    # Construct compound key for message lookup
    compound_key = f"{action}_{outcome}"
    
    # Get message text (fallback to outcome-only if compound key missing)
    text = MSG.get(compound_key, MSG.get(outcome, "Выполнено"))
    
    # Icon logic: for action_ok use action icon, otherwise use outcome icon
    if outcome == "ok" and action in INDICATOR_MAP:
        icon = get_icon(action)
    else:
        icon = get_icon(outcome)
    
    # Build compact banner
    parts = [icon, text, f"#{kind_letter}{item_id}"]
    if amount:
        parts.append(amount)
    
    return " · ".join(parts)



# Evidence metadata for Skeptic Mode
__evidence__ = {
    "total_indicators": len(INDICATOR_MAP),
    "required_keys": [
        "ok", "accepted", "noop", "rejected", "failed",
        "forbidden", "in_progress", "pending_review", "needs_photo"
    ],
    "version": "1.0.0-bk1",
}
