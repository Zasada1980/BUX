"""Pricing module with deterministic calculation from YAML rules."""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from datetime import datetime
from typing import Tuple, List, Dict
import yaml


BASE_RULES_PATH = Path(__file__).parent / "rules"
RULES_PATHS = [BASE_RULES_PATH / "global.yaml"]  # priority from left to right


class PricingError(Exception):
    """Raised when pricing calculation fails."""
    pass


def _load_rules():
    """Load and merge YAML rules from all configured paths."""
    data = {}
    for p in RULES_PATHS:
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                d = yaml.safe_load(f) or {}
                data.update(d)
    if "rates" not in data:
        raise PricingError("rates missing in YAML")
    return data


def calc_amount(rate_code: str, qty: float) -> float:
    """
    Calculate amount = rate_value * qty with ROUND_HALF_UP.
    
    Args:
        rate_code: Rate code from YAML (e.g. 'hour_electric', 'piece_demo')
        qty: Quantity (hours, pieces, etc.)
        
    Returns:
        Calculated amount rounded to 2 decimal places
        
    Raises:
        PricingError: If rate_code not found in YAML
    """
    rules = _load_rules()
    rate = (rules.get("rates") or {}).get(rate_code)
    if not rate:
        raise PricingError(f"unknown rate_code={rate_code}")
    
    value = Decimal(str(rate.get("value", 0)))
    amount = value * Decimal(str(qty))
    rounding = int(rules.get("rounding", 2))
    
    return float(amount.quantize(Decimal(10) ** -rounding, rounding=ROUND_HALF_UP))


def load_rules() -> dict:
    """
    Public version of _load_rules() for external use.
    
    Returns:
        Merged YAML rules dictionary
    """
    return _load_rules()


def expense_policy() -> Tuple[dict, int]:
    """
    Get expense rules and rounding precision.
    
    Returns:
        Tuple of (expenses_config_dict, rounding_precision)
    """
    r = load_rules()
    return (r.get("expenses") or {}), int(r.get("rounding", 2))


def is_weekend(dt: datetime) -> bool:
    """
    Check if datetime falls on weekend (Saturday/Sunday).
    
    Args:
        dt: Datetime to check
        
    Returns:
        True if weekend (weekday >= 5), False otherwise
    """
    return dt.weekday() >= 5


def apply_modifiers(base_amount: float, shift_dt: datetime, rules: dict) -> Tuple[float, List[Dict]]:
    """
    Apply weekend/night_shift modifiers to base amount.
    
    Args:
        base_amount: Base amount before modifiers
        shift_dt: Shift datetime for modifier conditions
        rules: YAML rules dictionary
        
    Returns:
        Tuple of (total_amount, modifier_steps_list)
        where each step is {"step": "modifier", "yaml_key": "...", "value": float}
    """
    steps: List[Dict] = []
    total = float(base_amount)
    mods = (rules.get("modifiers") or {})
    
    # Weekend modifier
    w = mods.get("weekend")
    if w and is_weekend(shift_dt):
        p = float(w.get("add_percent", 0))
        add = round(total * p / 100.0, 2)
        total += add
        steps.append({"step": "modifier", "yaml_key": "modifiers.weekend", "value": add})
    
    # Night shift modifier (simplified: 22:00-06:00 by hour)
    n = mods.get("night_shift")
    if n and (shift_dt.hour >= 22 or shift_dt.hour < 6):
        p = float(n.get("add_percent", 0))
        add = round(total * p / 100.0, 2)
        total += add
        steps.append({"step": "modifier", "yaml_key": "modifiers.night_shift", "value": add})
    
    return round(total, 2), steps


# --- G3 API Details helpers (Skeptic Mode) ---

def _compute_rules_sha(rules_path: Path) -> str:
    """Compute short SHA256 of rules file content."""
    import hashlib
    content = rules_path.read_bytes()
    return hashlib.sha256(content).hexdigest()[:12]


def explain_task(task_id: int, session) -> Tuple[List[Dict], Decimal, int, str]:
    """
    Explain task pricing with deterministic step breakdown.
    
    Args:
        task_id: Task ID to explain
        session: SQLAlchemy session
        
    Returns:
        Tuple of (steps, total, rules_version, rules_sha)
        
    Raises:
        PricingError: If task not found or pricing fails
    """
    from sqlalchemy import text
    
    # Fetch task
    row = session.execute(
        text("SELECT rate_code, qty, amount FROM tasks WHERE id=:id"),
        {"id": task_id}
    ).fetchone()
    
    if not row:
        raise PricingError(f"task_id={task_id} not found")
    
    rate_code, qty, amount = row
    
    # Load rules
    rules = load_rules()
    rules_path = RULES_PATHS[0]
    rules_version = int(rules.get("version", 1))
    rules_sha = _compute_rules_sha(rules_path)
    
    # Build deterministic steps (base only for tasks, no modifiers)
    rate_config = (rules.get("rates") or {}).get(rate_code)
    if not rate_config:
        raise PricingError(f"unknown rate_code={rate_code}")
    
    rate_value = Decimal(str(rate_config.get("value", 0)))
    base_amount = (rate_value * Decimal(str(qty))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    steps = [
        {
            "step": "base",
            "yaml_key": f"rates.{rate_code}",
            "value": base_amount,
            "note": f"{qty} × {rate_value} = {base_amount}"
        }
    ]
    
    # Total (for tasks, base = total)
    total = base_amount
    
    return steps, total, rules_version, rules_sha


def explain_expense(expense_id: int, session) -> Tuple[List[Dict], Decimal, int, str]:
    """
    Explain expense pricing with deterministic step breakdown.
    
    Args:
        expense_id: Expense ID to explain
        session: SQLAlchemy session
        
    Returns:
        Tuple of (steps, total, rules_version, rules_sha)
        
    Raises:
        PricingError: If expense not found
    """
    from sqlalchemy import text
    
    # Fetch expense
    row = session.execute(
        text("SELECT category, amount FROM expenses WHERE id=:id"),
        {"id": expense_id}
    ).fetchone()
    
    if not row:
        raise PricingError(f"expense_id={expense_id} not found")
    
    category, amount = row
    
    # Load rules
    rules = load_rules()
    rules_path = RULES_PATHS[0]
    rules_version = int(rules.get("version", 1))
    rules_sha = _compute_rules_sha(rules_path)
    
    # Build deterministic steps (expenses are flat amounts)
    amount_decimal = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    steps = [
        {
            "step": "base",
            "yaml_key": f"expenses.{category}",
            "value": amount_decimal,
            "note": f"Category: {category}"
        }
    ]
    
    total = amount_decimal
    
    return steps, total, rules_version, rules_sha

