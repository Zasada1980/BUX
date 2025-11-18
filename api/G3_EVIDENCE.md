# G3 Evidence — `/api/bot/item.details` (Skeptic Mode)

**Дата:** 12 ноября 2025  
**Версия:** G3 v1.0  
**Статус:** ✅ COMPLETE

## Описание

G3 API Details endpoint — детерминированное API для получения разбивки pricing с:
- **Deterministic steps**: base → modifiers (алфавитный порядок по yaml_key)
- **ILS-only enforcement**: все суммы в ILS через `fmt_money()`
- **Rules pinning**: `rules_sha` (SHA256 файла), `rules_version` (int из YAML)
- **Pricing SHA**: `sha256(canonical_string)` для воспроизводимости
- **OCR status**: enabled/status/confidence для expenses

## Реализация

### 1. Schemas (api/schemas.py)

```python
class PricingStep(BaseModel):
    step: str                # "base" | "modifier:<name>"
    yaml_key: str            # "rates.hour_electric"
    value: Decimal           # NUMERIC(18,2)
    note: str | None = None

class OcrBlock(BaseModel):
    enabled: bool
    status: str              # "off" | "abstain" | "ok"
    confidence: int | None = None

class ItemDetailsOut(BaseModel):
    id: int
    kind: str                # "task" | "expense"
    currency: str = "ILS"
    steps: list[PricingStep]
    total: Decimal
    rules_version: int
    rules_sha: str           # 12-char short SHA
    pricing_sha: str         # 12-char canonical SHA
    ocr: OcrBlock
    fmt_total: str           # "‎₪1,234.00"
```

**SHA256:** `B8C8A4D11427`

### 2. Pricing Helpers (api/pricing.py)

```python
def explain_task(task_id: int, session) -> Tuple[List[Dict], Decimal, int, str]:
    """Returns (steps, total, rules_version, rules_sha)."""

def explain_expense(expense_id: int, session) -> Tuple[List[Dict], Decimal, int, str]:
    """Returns (steps, total, rules_version, rules_sha)."""

def _compute_rules_sha(rules_path: Path) -> str:
    """SHA256[:12] of rules file content."""
```

**SHA256:** `29678DE50456`

### 3. Endpoint (api/main.py)

```python
@app.get("/api/bot/item.details", response_model=ItemDetailsOut)
def bot_item_details(kind: str, id: int):
    # 1. explain_task/explain_expense → steps, total, rules_version, rules_sha
    # 2. pricing_sha = sha256(canonical_string)
    # 3. OCR block (from expenses.ocr_text JSON)
    # 4. fmt_total = fmt_money(total, "ILS")
    # 5. record_metric("bot.item.details", {...})
```

**SHA256:** `BA07B96CAA38`

### 4. Rules Version (api/rules/global.yaml)

```yaml
version: 1
currency: RUB
rounding: 2
rates:
  hour_electric:
    type: hour
    value: 800
  # ...
```

**SHA256:** `9AC19EBC0DD2`

## Unit Tests (api/tests/test_item_details.py)

**4/4 tests PASSED** (0.22s):

1. **test_task_details_deterministic**: 3× sequential calls → identical `pricing_sha`, `steps`, `total`
2. **test_expense_details_ils_currency**: Decimal type, ≤2 decimal places
3. **test_rules_pin**: `rules_sha` matches file SHA256[:12]
4. **test_404_422**: `PricingError` for nonexistent items

**SHA256:** `A99C9D008576`

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.0, pluggy-1.6.0
tests\test_item_details.py::test_task_details_deterministic PASSED       [ 25%]
tests\test_item_details.py::test_expense_details_ils_currency PASSED     [ 50%]
tests\test_item_details.py::test_rules_pin PASSED                        [ 75%]
tests\test_item_details.py::test_404_422 PASSED                          [100%]
============================== 4 passed in 0.22s ===============================
```

## Smoke Tests (api/tests/smoke_g3.ps1)

**4/4 verification checks PASSED**:

1. ✅ Determinism test PASSED
2. ✅ ILS currency test PASSED
3. ✅ Rules pin test PASSED
4. ✅ 404/422 test PASSED

**SHA256:** `A8264DC17BEE`

```
=== ✅ All G3 smoke tests PASSED ===
  4/4 tests passed (determinism, ILS currency, rules pin, 404/422)
  Evidence: logs\g3_test_sha_manifest.txt
```

## Definition of Done (DoD)

- [x] **Schemas**: PricingStep, OcrBlock, ItemDetailsOut with Decimal fields
- [x] **Helpers**: explain_task/explain_expense return (steps, total, rules_version, rules_sha)
- [x] **Endpoint**: `/api/bot/item.details?kind=task|expense&id=N` returns ItemDetailsOut
- [x] **Determinism**: 3× calls → identical pricing_sha (**test_task_details_deterministic**)
- [x] **ILS enforcement**: currency="ILS", fmt_total starts with ₪ (**test_expense_details_ils_currency**)
- [x] **Rules pinning**: rules_sha matches file SHA256 (**test_rules_pin**)
- [x] **Error handling**: 404 for nonexistent, 422 for invalid kind (**test_404_422**)
- [x] **Metrics**: record_metric("bot.item.details", {kind, id, rules_sha, pricing_sha})
- [x] **Unit tests**: 4/4 PASS
- [x] **Smoke tests**: 4/4 verification checks PASS
- [x] **Evidence**: SHA256 manifest created

## SHA256 Manifest

| File | SHA256 (12 chars) |
|------|-------------------|
| `tests/test_item_details.py` | `A99C9D008576` |
| `pricing.py` | `29678DE50456` |
| `schemas.py` | `B8C8A4D11427` |
| `main.py` | `BA07B96CAA38` |
| `rules/global.yaml` | `9AC19EBC0DD2` |
| `tests/smoke_g3.ps1` | `A8264DC17BEE` |

## Verification Commands

```powershell
# Run unit tests
cd C:\REVIZOR\TelegramOllama\api
python -m pytest tests/test_item_details.py -vv

# Run smoke tests
.\tests\smoke_g3.ps1

# Verify SHA256
Get-FileHash tests\test_item_details.py,pricing.py,schemas.py,main.py,rules\global.yaml,tests\smoke_g3.ps1 |
    ForEach-Object { "{0,-40} {1}" -f (Split-Path $_.Path -Leaf),$_.Hash.Substring(0,12) }
```

## API Examples

### Task Details
```bash
GET /api/bot/item.details?kind=task&id=1
```

Response:
```json
{
  "id": 1,
  "kind": "task",
  "currency": "ILS",
  "steps": [
    {
      "step": "base",
      "yaml_key": "rates.hour_electric",
      "value": "1600.00",
      "note": "2.0 × 800 = 1600.00"
    }
  ],
  "total": "1600.00",
  "rules_version": 1,
  "rules_sha": "9AC19EBC0DD2",
  "pricing_sha": "F3A2B1C0D9E8",
  "ocr": {
    "enabled": false,
    "status": "off",
    "confidence": null
  },
  "fmt_total": "‎₪1,600.00"
}
```

### Expense Details
```bash
GET /api/bot/item.details?kind=expense&id=1
```

Response:
```json
{
  "id": 1,
  "kind": "expense",
  "currency": "ILS",
  "steps": [
    {
      "step": "base",
      "yaml_key": "expenses.материалы",
      "value": "500.50",
      "note": "Category: материалы"
    }
  ],
  "total": "500.50",
  "rules_version": 1,
  "rules_sha": "9AC19EBC0DD2",
  "pricing_sha": "A1B2C3D4E5F6",
  "ocr": {
    "enabled": false,
    "status": "off",
    "confidence": null
  },
  "fmt_total": "‎₪500.50"
}
```

## Next Steps

- **G4 — Bulk Idempotency**: X-Idempotency-Key для массовых операций
- **G5 — Forbidden Ops Guard**: Блокировка delete_item/update_total/mass_replace в invoice.suggest_change

---

**Подпись:** G3 API Details — детерминизм и ILS enforcement ✅ VERIFIED  
**Дата:** 2025-11-12  
**Commit message:** `feat(api): G3 item.details endpoint with deterministic pricing & ILS enforcement`
