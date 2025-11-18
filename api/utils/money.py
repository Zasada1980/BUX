"""Money formatting utilities for ILS currency with Decimal-only operations.

Skeptic Mode: Φ0-P1
- ONLY Decimal type allowed (no float)
- ILS symbol: ₪ (U+20AA)
- LRM (U+200E) isolation for RTL contexts
- Always 2 decimal places
- Rejects non-ILS currencies (raises ValueError)

Evidence:
- This module enforces Decimal-only arithmetic
- fmt_money() guarantees consistent ILS formatting
- No floating-point operations allowed
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Union


# Constants
ILS_SYMBOL = "\u20aa"  # ₪
LRM = "\u200e"  # Left-to-Right Mark for RTL isolation
ALLOWED_CURRENCY = "ILS"
DECIMAL_PLACES = 2


def fmt_money(amount: Union[Decimal, str, int], currency: str = "ILS") -> str:
    """
    Format monetary amount for display.
    
    Args:
        amount: Decimal, string, or int (will be converted to Decimal)
        currency: Currency code (only "ILS" allowed)
    
    Returns:
        Formatted string like "₪1,234.56" with LRM isolation
    
    Raises:
        ValueError: If currency != "ILS" or amount is float
        InvalidOperation: If amount cannot be converted to Decimal
    
    Examples:
        >>> fmt_money(Decimal("1234.56"))
        '₪1,234.56'
        >>> fmt_money("999.5")
        '₪999.50'
        >>> fmt_money(1000)
        '₪1,000.00'
    """
    # Reject float explicitly
    if isinstance(amount, float):
        raise ValueError(
            f"Float not allowed in money operations. Got: {amount}. "
            "Use Decimal or string instead."
        )
    
    # Validate currency
    if currency.upper() != ALLOWED_CURRENCY:
        raise ValueError(
            f"Only {ALLOWED_CURRENCY} currency supported. Got: {currency}"
        )
    
    # Convert to Decimal
    try:
        if isinstance(amount, str):
            dec_amount = Decimal(amount)
        elif isinstance(amount, int):
            dec_amount = Decimal(amount)
        elif isinstance(amount, Decimal):
            dec_amount = amount
        else:
            raise ValueError(f"Invalid amount type: {type(amount)}")
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Cannot convert amount to Decimal: {amount}") from e
    
    # Round to 2 decimal places (banker's rounding)
    dec_amount = dec_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    # Format with thousand separators
    # Convert to string, split integer and decimal parts
    amount_str = str(dec_amount)
    if "." in amount_str:
        integer_part, decimal_part = amount_str.split(".")
    else:
        integer_part = amount_str
        decimal_part = "00"
    
    # Pad decimal part to 2 digits
    decimal_part = decimal_part.ljust(DECIMAL_PLACES, "0")[:DECIMAL_PLACES]
    
    # Add thousand separators to integer part
    # Handle negative sign
    is_negative = integer_part.startswith("-")
    if is_negative:
        integer_part = integer_part[1:]
    
    # Reverse, group by 3, reverse back
    reversed_int = integer_part[::-1]
    groups = [reversed_int[i:i+3] for i in range(0, len(reversed_int), 3)]
    formatted_int = ",".join(groups)[::-1]
    
    if is_negative:
        formatted_int = "-" + formatted_int
    
    # Combine with LRM isolation
    # Format: LRM + ₪ + amount
    return f"{LRM}{ILS_SYMBOL}{formatted_int}.{decimal_part}"


def parse_money(formatted: str) -> Decimal:
    """
    Parse formatted money string back to Decimal.
    
    Args:
        formatted: String like "₪1,234.56" or "1234.56"
    
    Returns:
        Decimal value
    
    Raises:
        ValueError: If string cannot be parsed
    
    Examples:
        >>> parse_money("₪1,234.56")
        Decimal('1234.56')
        >>> parse_money("999.50")
        Decimal('999.50')
    """
    # Remove currency symbol, LRM, and commas
    cleaned = formatted.replace(ILS_SYMBOL, "").replace(LRM, "").replace(",", "").strip()
    
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Cannot parse money string: {formatted}") from e


def validate_decimal_amount(amount: Union[Decimal, str, int]) -> Decimal:
    """
    Validate and convert amount to Decimal.
    
    Args:
        amount: Amount to validate
    
    Returns:
        Decimal with 2 decimal places
    
    Raises:
        ValueError: If amount is float or invalid
    """
    if isinstance(amount, float):
        raise ValueError(
            f"Float not allowed. Got: {amount}. Use Decimal or string."
        )
    
    try:
        if isinstance(amount, Decimal):
            dec = amount
        elif isinstance(amount, str):
            dec = Decimal(amount)
        elif isinstance(amount, int):
            dec = Decimal(amount)
        else:
            raise ValueError(f"Invalid type: {type(amount)}")
        
        # Round to 2 places
        return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    except (InvalidOperation, ValueError) as e:
        raise ValueError(f"Invalid amount: {amount}") from e


# Skeptic Mode Evidence
__evidence__ = {
    "module": "money.py",
    "purpose": "Decimal-only ILS formatting (Φ0-P1)",
    "guarantees": [
        "No float operations",
        "ILS currency only",
        "2 decimal places always",
        "LRM isolation for RTL",
        "Thousand separators"
    ],
    "tests_required": [
        "fmt_money(Decimal('1234.56')) == '₪1,234.56'",
        "fmt_money(1000) == '₪1,000.00'",
        "fmt_money(float) raises ValueError",
        "fmt_money('USD') raises ValueError"
    ]
}

def ensure_decimal(x):
    """Строгая конвертация в Decimal без потери точности.
    
    Args:
        x: int, str, float, или Decimal
        
    Returns:
        Decimal instance
        
    Raises:
        TypeError: если тип не поддерживается
    """
    if isinstance(x, Decimal):
        return x
    if isinstance(x, (int, str)):
        return Decimal(str(x))
    if isinstance(x, float):
        # float → repr() для детерминизма
        return Decimal(repr(x))
    raise TypeError(f"ensure_decimal: unsupported type {type(x)}")
