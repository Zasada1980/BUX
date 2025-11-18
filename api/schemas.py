"""Pydantic schemas for TelegramOllama API."""
from pydantic import BaseModel, Field, condecimal, validator
from decimal import Decimal
from enum import Enum

# Φ0-P2: Money type - Decimal only, 18 digits max, 2 decimal places
Money = condecimal(max_digits=18, decimal_places=2, gt=0)

# Φ0-P2: Currency enum - ILS only
class Currency(str, Enum):
    """Allowed currencies (ILS only for Skeptic Mode)."""
    ILS = "ILS"


class ShiftStartIn(BaseModel):
    """Input schema for shift start request."""
    
    user_id: str = Field(min_length=1, description="User identifier")
    meta: dict | None = Field(default=None, description="Optional metadata")


class ShiftOut(BaseModel):
    """Output schema for shift response."""
    
    id: int
    user_id: str
    status: str


class TaskAddIn(BaseModel):
    """Input schema for task add request."""
    
    shift_id: int = Field(description="Shift ID to attach task to")
    rate_code: str = Field(min_length=1, description="Rate code from YAML rules")
    qty: Decimal = Field(gt=0, description="Quantity (hours, pieces, etc.)")
    note: str | None = Field(default=None, description="Optional note")


class TaskOut(BaseModel):
    """Output schema for task response."""
    
    id: int
    shift_id: int
    rate_code: str
    qty: Decimal
    unit: str
    amount: Decimal  # Φ0-P2: Changed from float to Decimal


class ExpenseAddIn(BaseModel):
    """Input schema for expense add request."""
    
    worker_id: str = Field(min_length=1, description="Worker identifier")
    shift_id: int | None = Field(default=None, description="Optional shift ID (auto-attach if None)")
    category: str = Field(min_length=1, description="Expense category (must be in allow_categories)")
    amount: Money = Field(description="Expense amount (Decimal only, 2 decimal places)")
    currency: Currency = Field(default=Currency.ILS, description="Currency code (ILS only)")
    photo_ref: str | None = Field(default=None, description="Optional photo reference for OCR")
    
    @validator("currency")
    def validate_ils_only(cls, v):
        """Φ0-P2: Enforce ILS-only currency."""
        if v != Currency.ILS:
            raise ValueError(f"Only ILS currency supported. Got: {v}")
        return v


class ExpenseOut(BaseModel):
    """Output schema for expense response."""
    
    id: int
    worker_id: str
    shift_id: int | None
    category: str
    amount: Decimal  # Φ0-P2: Changed from float to Decimal
    currency: str
    photo_ref: str | None
    ocr_text: str | None
    confirmed: int
    review_required: bool | None = None
    review_reason: str | None = None
    ocr_meta: dict | None = None


class ShiftEndIn(BaseModel):
    """Input schema for shift end request."""
    
    shift_id: int = Field(description="Shift ID to close")
    ended_at: str | None = Field(default=None, description="Optional ISO8601 timestamp (defaults to now)")


class ShiftEndOut(BaseModel):
    """Output schema for shift end response."""
    
    id: int
    status: str
    ended_at: str
    breakdown: list[dict]  # [{"step": "base|modifier", "yaml_key": "...", "value": float}]
    total: float


class InvoiceBuildIn(BaseModel):
    """Input schema for invoice build request."""
    
    client_id: str = Field(min_length=1, description="Client identifier")
    period_from: str = Field(description="Start date (ISO8601)")
    period_to: str = Field(description="End date (ISO8601)")
    currency: Currency = Field(default=Currency.ILS, description="Currency code (ILS only)")
    
    @validator("currency")
    def validate_ils_only(cls, v):
        """Φ0-P2: Enforce ILS-only currency."""
        if v != Currency.ILS:
            raise ValueError(f"Only ILS currency supported. Got: {v}")
        return v


class InvoiceOut(BaseModel):
    """Output schema for invoice response."""
    
    id: int
    client_id: str
    period_from: str
    period_to: str
    total: Decimal  # Φ0-P2: Changed from float to Decimal
    currency: str
    status: str
    version: int
    pdf_path: str | None
    xlsx_path: str | None


# --- G3 API Details schemas (Skeptic Mode) ---

class PricingStep(BaseModel):
    """Deterministic pricing step for G3 item details."""
    
    step: str = Field(description="Step type: base | modifier:<name>")
    yaml_key: str = Field(description="Exact YAML path (e.g. rates.hour_electric)")
    value: Decimal = Field(description="+/− contribution (NUMERIC(18,2))")
    note: str | None = Field(default=None, description="Optional explanation")


class OcrBlock(BaseModel):
    """OCR status block for G3 item details."""
    
    enabled: bool = Field(description="Whether OCR is enabled for this item")
    status: str = Field(description="OCR status: off | abstain | ok")
    confidence: int | None = Field(default=None, description="OCR confidence % (0-100)")


class ItemDetailsOut(BaseModel):
    """G3 deterministic item details output with pricing breakdown."""
    
    id: int = Field(description="Item ID (task or expense)")
    kind: str = Field(description="Item kind: task | expense")
    currency: str = Field(default="ILS", description="Currency (ILS only)")
    steps: list[PricingStep] = Field(description="Deterministic pricing steps (ordered)")
    total: Decimal = Field(description="Total amount (NUMERIC(18,2))")
    rules_version: int = Field(description="Integer rules version from YAML")
    rules_sha: str = Field(description="Short SHA of rules/global.yaml")
    pricing_sha: str = Field(description="SHA of canonical pricing string")
    ocr: OcrBlock = Field(description="OCR status block")
    fmt_total: str = Field(description="Formatted total via fmt_money() e.g. ‎₪1,234.00")

