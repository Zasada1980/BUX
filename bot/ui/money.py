# -*- coding: utf-8 -*-
"""
Bot money formatter — интеграция api/utils/money.py для UI бота.

BK-8: Денежный рендер (ILS, RTL-safe)
"""

from decimal import Decimal
from typing import Union

# Import from API utils (api/utils/money.py from Φ0-P1)
import sys
from pathlib import Path

# Add root directory to path for api.utils.money import
root_path = Path(__file__).parent.parent.parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

from api.utils.money import fmt_money as _fmt_money


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
    "depends_on": "api/utils/money.py (Φ0-P1)",
    "currency": "ILS only",
    "version": "1.0.0-bk8",
}
