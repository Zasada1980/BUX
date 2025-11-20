# -*- coding: utf-8 -*-
"""
Bot money formatter — автономная реализация (TD-BOT-ISO-1 hotfix).

BK-8: Денежный рендер (ILS, RTL-safe)

ПРИМЕЧАНИЕ: Встроенная копия fmt_money из api/utils/money.py для изоляции сервисов.
Полное исправление TD-BOT-ISO-1 (HTTP API вместо импортов) — P2 приоритет, Phase 6+.
"""

from decimal import Decimal
from typing import Union


def _fmt_money(amount: Decimal, currency: str = "ILS") -> str:
    """
    Форматирует денежную сумму с валютным символом и тысячами.
    
    Встроенная копия из api/utils/money.py для изоляции bot-сервиса.
    
    Args:
        amount: Decimal сумма
        currency: Валюта (только ILS)
    
    Returns:
        Formatted string: LRM + ₪ + amount с тысячами
    
    Examples:
        >>> _fmt_money(Decimal("123.45"))
        '\\u200e₪123.45'
        >>> _fmt_money(Decimal("1234567.8"))
        '\\u200e₪1,234,567.80'
    """
    LRM = "\u200e"  # Left-to-Right Mark для RTL isolation
    
    if currency != "ILS":
        raise ValueError(f"Unsupported currency: {currency}")
    
    # Format with 2 decimals and thousand separators
    formatted = f"{amount:,.2f}"
    
    return f"{LRM}₪{formatted}"


def fmt_amount(amount: Union[str, int, float, Decimal], currency: str = "ILS") -> str:
    """
    Форматирует денежную сумму для бота.
    
    Args:
        amount: Сумма (str, int, float, Decimal)
        currency: Валюта (только ILS поддерживается)
    
    Returns:
        Formatted string with LRM + ₪ symbol + amount
    
    Examples:
        >>> fmt_amount(123.45)
        '\\u200e₪123.45'
        >>> fmt_amount("0")
        '\\u200e₪0.00'
        >>> fmt_amount(1234567.8)
        '\\u200e₪1,234,567.80'
    
    Notes:
        - Всегда 2 decimal places
        - Thousand separators
        - LRM (U+200E) для RTL isolation
        - Только ILS (₪) поддерживается
    """
    # Convert to Decimal if needed
    if isinstance(amount, (int, float)):
        amount = Decimal(str(amount))
    elif isinstance(amount, str):
        amount = Decimal(amount) if amount else Decimal("0")
    
    return _fmt_money(amount, currency)


def fmt_amount_safe(amount_data: Union[str, int, float, Decimal, None], 
                     currency: str = "ILS", 
                     fallback: str = "N/A") -> str:
    """
    Safe wrapper для fmt_amount с fallback для None/invalid данных.
    
    Args:
        amount_data: Сумма или None
        currency: Валюта (ILS)
        fallback: Fallback текст при ошибке/None
    
    Returns:
        Formatted amount или fallback
    
    Examples:
        >>> fmt_amount_safe(None)
        'N/A'
        >>> fmt_amount_safe("")
        'N/A'
        >>> fmt_amount_safe(123.45)
        '\\u200e₪123.45'
    """
    if amount_data is None or amount_data == "":
        return fallback
    
    try:
        return fmt_amount(amount_data, currency)
    except (ValueError, TypeError, Exception):
        return fallback


# Evidence metadata
__evidence__ = {
    "functions": ["fmt_amount", "fmt_amount_safe"],
    "depends_on": "NONE (embedded copy of api/utils/money.py)",
    "currency": "ILS only",
    "version": "1.0.1-td-bot-iso-hotfix",
    "tech_debt": "TD-BOT-ISO-1 (use HTTP API instead of code sharing)",
}
