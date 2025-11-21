"""TelegramOllama API."""
from fastapi import FastAPI, Header, HTTPException, Query, Depends, Request, status, BackgroundTasks, Body
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse  # E2: HTMX invoice views; CSV export; SPA fallback
from fastapi.staticfiles import StaticFiles  # E1: static assets
from fastapi.middleware.cors import CORSMiddleware
import platform
import httpx
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.orm import Session
from decimal import Decimal
import time
import os
import threading
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from pathlib import Path
import sqlite3  # CI-24: Raw DB access for test endpoints

from config import settings
from db import SessionLocal
from models import Shift, Invoice, Client, Task, Expense, Employee  # CRITICAL FIX: Added Task, Expense for CRUD endpoints, Employee for auth
from schemas import ShiftStartIn, ShiftOut, TaskAddIn, TaskOut, ExpenseAddIn, ExpenseOut, ShiftEndIn, ShiftEndOut, InvoiceBuildIn, InvoiceOut, PricingStep, OcrBlock, ItemDetailsOut
# NOTE: ensure_table removed - idempotency_keys now managed by Alembic (a1b2c3d4e5f6)
from utils.idempotency import remember
from utils.idempotency_guard import scope_hash, ensure_idempotent  # G4
from report import router as report_router
from admin_ui import router as admin_ui_router  # E1: HTMX Inbox
from endpoints_users import router as users_router  # UI-3: User management API (FIX: no 'api.' prefix)
from endpoints_salaries import router as salaries_router  # Salary management API
from endpoints_reports import router as reports_router  # Monthly reports CSV/JSON export
from endpoints_bot_menu import router as bot_menu_router  # Settings → Telegram Bot menu management
from endpoints_settings import router as settings_router  # F5.1: Settings (General, Backup, System)
from endpoints_shifts import router as shifts_router  # F5.2: Shifts read-only API (admin/foreman only)
from endpoints_profile import router as profile_router  # F1.3: Profile management
from endpoints_dashboard import router as dashboard_router  # B0: Dashboard KPIs and timeseries
from pricing import calc_amount, PricingError, expense_policy, load_rules, apply_modifiers, explain_task, explain_expense
from ocr_stub import ocr_extract_description
# TEMPORARY: OCR disabled due to missing Pillow dependency
# from ocr import run_ocr
from docgen import collect_invoice_data, render_docx
from docgen_html import render_html, html_to_pdf
from utils.audit import record_metric, _logs_dir  # metrics JSONL helper + logs path
from utils.money import fmt_money, ensure_decimal  # G3 money formatting + D1 hotfix
from deps_auth import get_current_admin  # F4.4 A2: Unified admin auth (JWT + X-Admin-Secret)
import uuid
import json
from datetime import timedelta
from jinja2 import Template  # E2: HTMX templates

# G5: Forbidden operations (runtime guard)
FORBIDDEN_OPS: set[str] = {"delete_item", "update_total", "mass_replace"}

# Hardening: Rate-limit config
RATE_RPS = float(os.getenv("RATE_LIMIT_RPS", "5"))
RATE_BURST = int(os.getenv("RATE_LIMIT_BURST", "10"))
_rl_store: dict = defaultdict(lambda: deque(maxlen=RATE_BURST))
_rl_lock = threading.Lock()
_started_at = time.time()

# --- Utility functions Phase 12 ---
def _audit(action: str, entity: str | None, entity_id: int | None, payload: dict | None, s):
    import hashlib
    ph = hashlib.sha256(json.dumps(payload or {}, ensure_ascii=False).encode('utf-8')).hexdigest() if payload is not None else None
    s.execute(text("""
        INSERT INTO audit_log(action, entity, entity_id, payload_hash, metadata)
        VALUES(:a, :e, :eid, :ph, :meta)
    """), {
        "a": action, "e": entity, "eid": entity_id, "ph": ph, "meta": json.dumps({"ts": datetime.utcnow().isoformat()})
    })

def _fetch_invoice_version(s, invoice_id: int, version: int):
    row = s.execute(text("SELECT payload_json FROM invoice_versions WHERE invoice_id=:i AND version=:v"), {"i": invoice_id, "v": version}).fetchone()
    return json.loads(row[0]) if row else None

def _diff_payload(old: dict, new: dict):
    changes = []
    # total change
    if old.get("total") != new.get("total"):
        pass  # handled separately in response
    # items diff
    old_items = old.get("items", [])
    new_items = new.get("items", [])
    max_len = max(len(old_items), len(new_items))
    for i in range(max_len):
        if i >= len(old_items):
            changes.append({"path": f"items[{i}]", "old": None, "new": new_items[i]})
            continue
        if i >= len(new_items):
            changes.append({"path": f"items[{i}]", "old": old_items[i], "new": None})
            continue
        # compare fields
        for field in ["qty", "unit", "amount", "task", "worker", "site"]:
            ov = old_items[i].get(field)
            nv = new_items[i].get(field)
            if ov != nv:
                changes.append({"path": f"items[{i}].{field}", "old": ov, "new": nv})
    return changes

def _apply_suggestion(payload: dict, suggestion: dict):
    kind = suggestion.get("kind")
    data = suggestion.get("payload_json") or {}
    items = payload.get("items", [])
    if kind == "edit_item":
        # data: { path: 'items[0].qty', new: 3 }
        path = data.get("path")
        new_val = data.get("new")
        if path and path.startswith("items[") and "." in path:
            idx_part, field = path.split(".", 1)
            try:
                idx = int(idx_part[idx_part.find("[")+1: idx_part.find("]")])
            except ValueError:
                return payload
            if 0 <= idx < len(items):
                # proportional amount recalculation if qty changes
                if field == "qty":
                    old_qty = items[idx].get("qty") or 0
                    if old_qty and isinstance(old_qty, (int, float)) and isinstance(new_val, (int, float)) and old_qty > 0:
                        factor = new_val / old_qty
                        amt = items[idx].get("amount")
                        if isinstance(amt, (int, float)):
                            items[idx]["amount"] = round(amt * factor, 2)
                items[idx][field] = new_val
    elif kind == "add_item":
        # data: full item dict
        new_item = data.get("item")
        if isinstance(new_item, dict):
            items.append(new_item)
    # comments do not change payload
    # recompute total
    total = sum((row.get("amount") or 0) for row in items)
    payload["total"] = round(float(total), 2)
    return payload


# --- I1: Admin Authentication Guard ---
async def admin_guard(
    request: Request,
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
):
    """
    Dependency for admin routes requiring authentication.
    
    Validates X-Admin-Secret header against INTERNAL_ADMIN_SECRET.
    Logs authentication attempts to metrics.
    
    Raises:
        HTTPException: 401 if header missing, 403 if secret invalid
    """
    import time
    t0 = time.perf_counter()
    
    # Check if secret provided and matches
    ok = (
        x_admin_secret is not None 
        and settings.INTERNAL_ADMIN_SECRET is not None 
        and x_admin_secret == settings.INTERNAL_ADMIN_SECRET
    )
    
    # Determine outcome for metrics
    outcome = "accepted" if ok else ("unauthorized" if x_admin_secret is None else "forbidden")
    
    # Record authentication attempt
    record_metric(
        "auth.admin",
        fields={
            "path": request.url.path,
            "method": request.method,
        },
        outcome=outcome,
        latency_ms=int((time.perf_counter() - t0) * 1000)
    )
    
    # Reject if no header
    if x_admin_secret is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Admin-Secret header"
        )
    
    # Reject if wrong secret
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret"
        )
    
    return True


# Session dependency for FastAPI
def get_session():
    """Provide database session for dependency injection."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


app = FastAPI(title="TelegramOllama API", version="0.2.0")

# CORS: allow local testing from file:// and other origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hardening: Rate-limit middleware
class RateLimitMW(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "local"
        now = time.time()
        with _rl_lock:
            q = _rl_store[ip]
            # Clean windows older than 1 second
            while q and now - q[0] > 1.0:
                q.popleft()
            if len(q) >= max(1, int(RATE_RPS * 1.0) + (RATE_BURST - 1)):
                return JSONResponse({"detail": "rate_limited"}, status_code=429)
            q.append(now)
        return await call_next(request)

app.add_middleware(RateLimitMW)

# Latency middleware (Fix 2: p50/p95 metrics)
ROUTE_KIND_OVERRIDES = {
    "/api/invoice.build": "invoice.build",
    "/api/expense.add": "expense.add",
    "/admin/pending": "admin.pending",
    "/api/bot/item.details": "bot.item.details",
    "/api/ocr.health": "ocr.health",
    "/health": "health",
}

@app.middleware("http")
async def latency_metrics(request: Request, call_next):
    t0 = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        dt_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        path = request.url.path
        kind = ROUTE_KIND_OVERRIDES.get(path, "http.other")
        status_code = getattr(response, "status_code", 0) if response else 500
        record_metric(kind, {"path": path, "latency_ms": dt_ms, "status": status_code})

# Include routers
app.include_router(report_router)
# LEGACY HTMX UI router (disabled for React SPA — causes /admin/pending collision with /api/admin/pending)
# app.include_router(admin_ui_router)  # E1: HTMX Inbox (moderation UI)
app.include_router(users_router, prefix="/api", tags=["users"])  # UI-3: User management → /api/users
app.include_router(salaries_router)  # Salary management
app.include_router(reports_router)  # Monthly reports CSV/JSON export
app.include_router(bot_menu_router)  # Settings → Telegram Bot menu (admin only)
app.include_router(settings_router)  # F5.1: Settings (General/Backup/System tabs) - admin only
app.include_router(shifts_router)  # F5.2: Shifts read-only API (admin/foreman only)
app.include_router(profile_router)  # F1.3: Profile management (all roles)
app.include_router(dashboard_router)  # B0: Dashboard API (admin/foreman only)

# Chat router
from routers.chat import router as chat_router
app.include_router(chat_router)

# Internal API for bot (no auth) - Simple user listing
@app.get("/api/internal/users")
def internal_get_users(db: Session = Depends(lambda: SessionLocal())):
    """Internal endpoint for bot to get all users (no auth check)"""
    import crud_users
    try:
        users = crud_users.list_users(db, role_filter=None, active_only=False)
        return [
            {
                "id": u.id,
                "name": u.name,
                "telegram_username": u.telegram_username,
                "telegram_id": u.telegram_id,
                "role": u.role,
                "active": u.active,
                "daily_salary": float(u.daily_salary) if u.daily_salary else None
            }
            for u in users
        ]
    finally:
        db.close()

# Webhook для вызова агента при сохранении данных
@app.post("/api/webhook/sync-agent")
async def webhook_sync_agent(background_tasks: BackgroundTasks):
    """
    Webhook для автоматического обновления данных через Ollama агента.
    Вызывается при сохранении данных в веб-интерфейсе.
    """
    async def trigger_agent_sync():
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post("http://agent:8080/v1/agent/sync-users")
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ Webhook sync: {result.get('synced', 0)} users synced")
                else:
                    print(f"⚠️ Webhook sync failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Webhook sync error: {e}")
    
    background_tasks.add_task(trigger_agent_sync)
    return {"status": "triggered", "message": "Agent sync scheduled"}

# Integration: Auth and Employee management routers
from endpoints_auth import router as auth_router
from endpoints_employees import router as employees_router
from endpoints_work_records import router as work_records_router
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(work_records_router)

# Static files (offline mode: htmx.min.js, etc.)
# Use absolute path from api/ directory for pytest compatibility
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)  # Create if doesn't exist (for tests)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Web interface (SPA) — mounted at / (MUST be LAST to avoid blocking API routes)
# All API routes are under /api prefix, so this should not conflict
# MOVED TO END OF FILE (after all @app.get() decorators) to prevent route collision
# app.mount("/", StaticFiles(directory="web", html=True), name="web")


# === AI Chat Endpoint (Stub - Ollama integration pending) ===
from pydantic import BaseModel as PydanticBaseModel
from auth import get_current_employee, get_db

class ChatMessage(PydanticBaseModel):
    role: str
    content: str

class ChatRequest(PydanticBaseModel):
    message: str
    history: list[ChatMessage] = []

class ChatResponse(PydanticBaseModel):
    response: str
    error: str | None = None

@app.post("/api/chat", response_model=ChatResponse, tags=["ai"])
async def chat_endpoint(
    request: ChatRequest,
    current_employee: Employee = Depends(get_current_employee),
    db: Session = Depends(get_db)
):
    """
    AI Chat endpoint (currently stub - returns helpful error message).
    
    TODO (TD-AI-CHAT-1):
    - Integrate with Ollama service (agent:8080 or ollama:11434)
    - Implement conversation history management
    - Add streaming response support
    - Add rate limiting (P2)
    """
    return ChatResponse(
        response="",
        error="AI Chat временно недоступен. Ollama интеграция в разработке (TD-AI-CHAT-1). "
              "Попробуйте позже или обратитесь к администратору для настройки Ollama."
    )


# TD-C1: Pricing explanation endpoint
@app.get("/api/pricing/explain", tags=["pricing"])
def pricing_explain(yaml_key: str):
    """
    Explain pricing calculation for a given YAML key.
    
    Returns step-by-step breakdown of the pricing formula.
    """
    import yaml
    from pathlib import Path
    
    rules_path = Path(__file__).parent / "rules" / "global.yaml"
    with open(rules_path, 'r', encoding='utf-8') as f:
        rules = yaml.safe_load(f)
    
    # Navigate nested YAML keys (e.g., "rates.hour_electric")
    parts = yaml_key.split('.')
    value = rules
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise HTTPException(404, detail=f"YAML key not found: {yaml_key}")
    
    # Build explanation
    if isinstance(value, dict):
        desc = value.get('description', f'Configuration for {yaml_key}')
        amount = value.get('value', 0)
        steps = [{"key": k, "value": v} for k, v in value.items()]
    else:
        desc = f"Value for {yaml_key}: {value}"
        amount = value if isinstance(value, (int, float)) else 0
        steps = []
    
    return {
        "yaml_key": yaml_key,
        "explanation": desc,
        "steps": steps,
        "total": amount,
        "calculation": desc
    }


@app.on_event("startup")
def startup():
    """Initialize resources on application startup."""
    # NOTE: idempotency_keys table is now managed by Alembic migrations (a1b2c3d4e5f6)
    # Removed ensure_table() to prevent conflicts with migration schema
    
    # Create symlink for backward compatibility
    # Links /app/logs/api.jsonl → latest dated metrics file
    _create_metrics_symlink()


def _create_metrics_symlink():
    """Create symlink to latest metrics file for backward compatibility."""
    try:
        import os
        import re
        from pathlib import Path
        
        # Inline resolver to avoid circular import during startup
        base = Path(os.getenv("LOGS_DIR", "/app/logs"))
        metrics_root = base / "metrics"
        target = None
        
        if metrics_root.exists():
            # Find dated directories (YYYY-MM-DD format)
            dated_dirs = sorted(
                [p for p in metrics_root.iterdir() 
                 if p.is_dir() and re.match(r"^\d{4}-\d{2}-\d{2}$", p.name)],
                key=lambda p: p.name,
                reverse=True  # Newest first
            )
            
            # Find first existing api.jsonl
            for dated_dir in dated_dirs:
                candidate = dated_dir / "api.jsonl"
                if candidate.exists():
                    target = candidate
                    break
            
            # Fallback to flat structure
            if target is None:
                flat_metrics = metrics_root / "api.jsonl"
                if flat_metrics.exists():
                    target = flat_metrics
        
        # Final fallback
        if target is None:
            target = base / "api.jsonl"
        
        # Create symlink
        link = Path("/app/logs/api.jsonl")
        link.parent.mkdir(parents=True, exist_ok=True)
        
        # Remove existing link/file
        if link.is_symlink() or link.exists():
            try:
                link.unlink()
            except FileNotFoundError:
                pass
        
        # Create symlink if target exists
        if target.exists():
            link.symlink_to(target)
            print(f"[metrics] Symlink created: {link} → {target}")
        else:
            print(f"[metrics] Warning: Target does not exist: {target}")
    except Exception as e:
        # Non-critical - log and continue
        print(f"[metrics] Symlink creation warning: {e}")


@app.get("/health")
def health():
    """Health check endpoint with uptime tracking."""
    return {
        "service": "api",
        "status": "ok",
        "ok": True,
        "uptime_s": round(time.time() - _started_at, 3),
        "version": app.version,
        "ts": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "env": {
            "DB_PATH": settings.DB_PATH,
            "AGENT_URL": settings.AGENT_URL,
        },
    }


@app.get("/api/ocr.health")
def ocr_health():
    """
    OCR health check endpoint.
    
    Returns:
        Tesseract installation status, version, and available languages
    """
    from ocr import _detect_tesseract
    info = _detect_tesseract()
    return {
        "tesseract": info.version,
        "langs": info.langs,
        "status": "ok" if info.ok else "fail"
    }


@app.post("/api/test/reset-admin-role")
def test_reset_admin_role(
    admin_secret: str = Header(None, alias="X-Admin-Secret")
):
    """
    E2E test endpoint: Reset admin user (id=1) role to 'admin'.
    
    CI-24: Replaces docker exec fix_admin_role.py (works in both CI and local).
    Protected by IS_TEST_MODE flag and admin secret.
    Uses raw sqlite3 to bypass SQLAlchemy metadata (users table not in migrations).
    
    Returns:
        User details after reset
    
    Raises:
        HTTPException: 403 if not in test mode or invalid secret
    """
    if not settings.IS_TEST_MODE:
        raise HTTPException(
            status_code=403,
            detail="Test endpoints only available when IS_TEST_MODE=true"
        )
    
    if admin_secret != settings.INTERNAL_ADMIN_SECRET:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin secret"
        )
    
    # Use raw SQLite connection (bypasses ORM metadata expectations)
    # NOTE: users table exists from seed, but NOT in Alembic migrations (TD-AUTH-SCHEMA-1)
    db_path = settings.DB_PATH.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        # Reset admin user to known state
        cur.execute("UPDATE users SET role='admin', active=1 WHERE id=1")
        conn.commit()
        
        # Verify and return result
        cur.execute("SELECT id, name, role, active FROM users WHERE id=1")
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(status_code=500, detail="Admin user not found after reset")
        
        return {
            "status": "ok",
            "message": "Admin role reset successfully",
            "user": {
                "id": result[0],
                "name": result[1],
                "role": result[2],
                "active": bool(result[3])
            }
        }
    finally:
        conn.close()


@app.post("/api/v1/shift/start", response_model=ShiftOut, status_code=201)
def shift_start(
    payload: ShiftStartIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    """
    Start a new shift.
    
    Args:
        payload: Shift start request with user_id and optional metadata
        idempotency_key: Optional idempotency key to prevent duplicate requests
        
    Returns:
        ShiftOut: Created shift with id, user_id, and status
        
    Raises:
        HTTPException: 400 if user_id is empty, 409 if duplicate idempotency key
    """
    if not payload.user_id:
        raise HTTPException(400, "user_id required")
    
    # Check idempotency
    if idempotency_key and not remember(idempotency_key, SessionLocal):
        raise HTTPException(409, "duplicate request")
    
    # Create shift using ORM
    with SessionLocal() as s:
        shift = Shift(user_id=payload.user_id, status="open")
        s.add(shift)
        s.commit()
        s.refresh(shift)
        
        return ShiftOut(id=shift.id, user_id=shift.user_id, status=shift.status)  # type: ignore[arg-type]


@app.get("/api/v1/shift/active")
def get_active_shift(user_id: str = Query(..., description="User ID to search active shift for")):
    """
    Find active (open) shift for user.
    
    Args:
        user_id: User identifier
        
    Returns:
        dict: {"shift_id": int | None, "status": str | None, "created_at": str | None}
        
    Raises:
        HTTPException: 400 if user_id is empty
    """
    if not user_id:
        raise HTTPException(400, "user_id required")
    
    with SessionLocal() as s:
        # Find open shift (ended_at IS NULL)
        shift_row = s.execute(
            text("SELECT id, status, created_at FROM shifts WHERE user_id=:uid AND status='open' AND ended_at IS NULL ORDER BY created_at DESC LIMIT 1"),
            {"uid": user_id}
        ).fetchone()
        
        if not shift_row:
            return {"shift_id": None, "status": None, "created_at": None}
        
        # FIX: created_at might be string (from SQLite) or datetime
        created_at = shift_row[2]
        created_at_str = created_at.isoformat() if hasattr(created_at, 'isoformat') else str(created_at) if created_at else None
        
        return {
            "shift_id": shift_row[0],
            "status": shift_row[1],
            "created_at": created_at_str
        }


@app.post("/api/task.add", response_model=TaskOut, status_code=201)
def task_add(
    payload: TaskAddIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    """
    Add a task to a shift with pricing calculation.
    
    Args:
        payload: Task add request with shift_id, rate_code, qty, and optional note
        idempotency_key: Optional idempotency key to prevent duplicate requests
        
    Returns:
        TaskOut: Created task with calculated amount
        
    Raises:
        HTTPException: 404 if shift not found, 400 if rate_code unknown, 409 if duplicate
    """
    # Check idempotency
    if idempotency_key and not remember(idempotency_key, SessionLocal):
        raise HTTPException(409, "duplicate request")
    
    with SessionLocal() as s:
        # Verify shift exists
        shift = s.execute(text("SELECT id FROM shifts WHERE id=:i"), {"i": payload.shift_id}).first()
        if not shift:
            raise HTTPException(404, "shift not found")
        
        # Calculate amount using pricing rules
        try:
            amount = calc_amount(payload.rate_code, payload.qty)
        except PricingError as e:
            raise HTTPException(400, str(e)) from e
        
        # Insert task
        r = s.execute(
            text("""INSERT INTO tasks(shift_id, rate_code, qty, unit, amount, note)
                    VALUES(:sid, :rc, :qty, 'unit', :amt, :note)"""),
            {"sid": payload.shift_id, "rc": payload.rate_code, "qty": float(payload.qty), "amt": amount, "note": payload.note}
        )
        s.commit()
        
        # Get last inserted ID
        new_id = s.execute(text("SELECT last_insert_rowid()")).scalar()
        
        return TaskOut(
            id=int(new_id) if new_id else 0,
            shift_id=payload.shift_id,
            rate_code=payload.rate_code,
            qty=payload.qty,
            unit="unit",
            amount=amount
        )


@app.post("/api/expense.add", response_model=ExpenseOut, status_code=201)
def expense_add(
    payload: ExpenseAddIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    """
    Add an expense with category validation, photo requirements, and auto-attach.
    
    Args:
        payload: Expense add request with worker_id, category, amount, etc.
        idempotency_key: Optional idempotency key to prevent duplicate requests
        
    Returns:
        ExpenseOut: Created expense with OCR text
        
    Raises:
        HTTPException: 409 if duplicate, 422 if validation fails
    """
    # Check idempotency
    if idempotency_key and not remember(idempotency_key, SessionLocal):
        raise HTTPException(409, "duplicate request")
    
    # Get expense policy from YAML
    rules, _ = expense_policy()
    allow = set((rules.get("allow_categories") or []))
    
    # Validate category
    if allow and payload.category not in allow:
        raise HTTPException(422, f"category '{payload.category}' not allowed (must be one of {list(allow)})")
    
    # Validate photo requirement
    req_photo_over = float(rules.get("require_photo_over", 1e18))
    if payload.amount > req_photo_over and not payload.photo_ref:
        raise HTTPException(422, f"photo required for expenses over {req_photo_over}")
    
    # OCR processing (Phase 13 Task 4)
    ocr_payload = None
    review_required = False
    review_reason = None
    
    if settings.OCR_ENABLED:
        # Enforce photo requirement for amounts over threshold
        if payload.amount > settings.REQUIRE_PHOTO_OVER and not payload.photo_ref:
            record_metric("ocr.policy", {"reason": "photo_required_over_limit", "limit": settings.REQUIRE_PHOTO_OVER}, outcome="rejected")
            raise HTTPException(422, f"photo required for expenses over {settings.REQUIRE_PHOTO_OVER}")
        
        # Run OCR if photo provided (TEMPORARY: disabled until Pillow/tesseract added)
        ocr_payload = {"abstain": True, "error": "OCR disabled (missing dependencies)"}
        # if payload.photo_ref and settings.OCR_ENABLED:
        #     try:
        #         ocr_result = run_ocr(
        #             path=str(payload.photo_ref),
        #             langs=settings.OCR_LANGS,
        #             min_conf=settings.OCR_MIN_CONF,
        #             tesseract_path=settings.OCR_TESSERACT_PATH
        #         )
        #         record_metric("ocr.run", {
        #             "duration_ms": ocr_result["duration_ms"],
        #             "confidence": ocr_result["confidence"],
        #             "amount_conf": ocr_result["amount_conf"],
        #             "date_conf": ocr_result["date_conf"],
        #             "merchant_conf": ocr_result["merchant_conf"],
        #         }, outcome=("abstained" if ocr_result["abstain"] else "accepted"))
        #         ocr_payload = ocr_result
        #         
        #         # Verify amount match (soft gate)
        #         if not ocr_result["abstain"] and ocr_result["amount"]:
        #             try:
        #                 ocr_amount = Decimal(str(ocr_result["amount"]))
        #                 req_amount = Decimal(str(payload.amount))
        #                 if abs(ocr_amount - req_amount) > Decimal("0.01"):
        #                     review_required = True
        #                     review_reason = "amount_mismatch_ocr"
        #                     record_metric("ocr.mismatch", {
        #                         "ocr_amount": str(ocr_amount),
        #                         "req_amount": str(req_amount),
        #                         "diff": str(abs(ocr_amount - req_amount))
        #                     }, outcome="review_required")
        #             except Exception:
        #                 pass  # Skip amount verification on parse errors
        #     except Exception as e:
        #         record_metric("ocr.run", {"error": type(e).__name__}, outcome="abstained")
        #         ocr_payload = {"abstain": True, "error": str(e)}
    
    # Auto-attach to same-day open shift if shift_id not provided
    attach_id = payload.shift_id
    if attach_id is None and rules.get("auto_attach_same_day"):
        today = datetime.now(timezone.utc).date().isoformat()
        with SessionLocal() as s:
            row = s.execute(text("""
                SELECT id FROM shifts
                WHERE user_id=:uid AND date(created_at)=:d AND status='open'
                ORDER BY id DESC LIMIT 1
            """), {"uid": payload.worker_id, "d": today}).first()
            if row:
                attach_id = int(row[0])
    
    # Extract OCR text from photo
    ocr_text = ocr_extract_description(payload.photo_ref)
    
    # Example agent observability integration (future: real categorization)
    # For now, just track the call without changing behavior
    if payload.photo_ref:
        from utils.audit import track_agent_call
        with track_agent_call("expense.categorize", model="ocr-stub") as tracker:
            # Stub: in real implementation, would call LLM for category suggestion
            # result = agent.categorize(ocr_text, allowed_categories=list(allow))
            tracker.set_tokens(in_tokens=0, out_tokens=0)  # Stub values
            tracker.set_confidence(0.0)  # No real confidence yet
            tracker.set_outcome("abstained")  # Stub doesn't make suggestions

    
    # Insert expense
    # NOTE: Status expected by moderation/inbox flow is 'needs_approval'.
    #       Previously we omitted status causing inbox to be empty (status filter = 'needs_approval').
    #       We now persist status explicitly to enable D-G2 (idempotency) & inbox population.
    # CRITICAL: Convert amount from ILS (Decimal) to agorot (Integer) before storing
    amount_agorot = int(payload.amount * 100)
    
    with SessionLocal() as s:
        try:
            r = s.execute(text("""
                INSERT INTO expenses(
                    worker_id, shift_id, category, amount, currency, photo_ref, ocr_text, confirmed, source, status
                ) VALUES(
                    :w, :sid, :cat, :amt, :cur, :ph, :ocr, 0, 'manual', 'needs_approval'
                )
            """), {
                "w": payload.worker_id,
                "sid": attach_id,
                "cat": payload.category,
                "amt": amount_agorot,
                "cur": payload.currency,
                "ph": payload.photo_ref,
                "ocr": ocr_text
            })
            new_id = r.lastrowid  # type: ignore[attr-defined]
            s.commit()
        except Exception as e:
            # Fallback: if column "status" does not exist (legacy schema) retry without it
            s.rollback()
            try:
                r = s.execute(text("""
                    INSERT INTO expenses(worker_id, shift_id, category, amount, currency, photo_ref, ocr_text, confirmed, source)
                    VALUES(:w, :sid, :cat, :amt, :cur, :ph, :ocr, 0, 'manual')
                """), {
                    "w": payload.worker_id,
                    "sid": attach_id,
                    "cat": payload.category,
                    "amt": amount_agorot,
                    "cur": payload.currency,
                    "ph": payload.photo_ref,
                    "ocr": ocr_text
                })
                new_id = r.lastrowid  # type: ignore[attr-defined]
                s.commit()
            except Exception:
                raise e
        
        return ExpenseOut(
            id=int(new_id) if new_id else 0,
            worker_id=payload.worker_id,
            shift_id=attach_id,
            category=payload.category,
            amount=payload.amount,
            currency=payload.currency,
            photo_ref=payload.photo_ref,
            ocr_text=ocr_text,
            confirmed=0,
            review_required=review_required if review_required else None,
            review_reason=review_reason,
            ocr_meta=ocr_payload if ocr_payload else None
        )


@app.post("/api/v1/shift/end", response_model=ShiftEndOut)
def shift_end(
    payload: ShiftEndIn,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")
):
    """
    End a shift with breakdown calculation including modifiers.
    
    Args:
        payload: Shift end request with shift_id and optional ended_at timestamp
        idempotency_key: Optional idempotency key to prevent duplicate requests
        
    Returns:
        ShiftEndOut: Closed shift with breakdown and total
        
    Raises:
        HTTPException: 404 if shift not found, 409 if already closed or duplicate
    """
    # Check idempotency
    if idempotency_key and not remember(idempotency_key, SessionLocal):
        raise HTTPException(409, "duplicate request")
    
    with SessionLocal() as s:
        # Get shift details
        sh = s.execute(
            text("SELECT id, user_id, status, created_at FROM shifts WHERE id=:i"),
            {"i": payload.shift_id}
        ).mappings().first()
        
        if not sh:
            raise HTTPException(404, "shift not found")
        if sh["status"] != "open":
            raise HTTPException(409, "shift already closed")
        
        # Calculate base amount (sum of all tasks)
        base = s.execute(
            text("SELECT COALESCE(SUM(amount), 0) FROM tasks WHERE shift_id=:sid"),
            {"sid": payload.shift_id}
        ).scalar() or 0.0
        
        # Get rules for modifiers
        rules = load_rules()
        
        # Determine end timestamp (ensure string for type safety)
        ended_at_raw = payload.ended_at
        if not ended_at_raw:
            ended_at_raw = s.execute(text("SELECT datetime('now')")).scalar()
        ended_at_str = str(ended_at_raw)
        
        # Parse timestamp safely
        try:
            if "T" in ended_at_str:
                ended_at_str = ended_at_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(ended_at_str)
        except Exception:
            # Fallback to current UTC time on parse issues
            dt = datetime.now(timezone.utc)
        
        # Apply modifiers (weekend, night_shift)
        total, modifier_steps = apply_modifiers(float(base), dt, rules)
        
        # Update shift status
        s.execute(
            text("UPDATE shifts SET status='closed', ended_at=:e WHERE id=:sid"),
            {"e": dt.isoformat(), "sid": payload.shift_id}
        )
        s.commit()
        
        # Build breakdown
        breakdown = [
            {"step": "base", "yaml_key": "rates", "value": round(float(base), 2)}
        ] + modifier_steps
        
        return ShiftEndOut(
            id=payload.shift_id,
            status="closed",
            ended_at=dt.isoformat(),
            breakdown=breakdown,
            total=round(float(total), 2)
        )


@app.post("/api/invoice.build", response_model=InvoiceOut)
def invoice_build(
    payload: InvoiceBuildIn,
    request: Request,
    x_idempotency_key: str | None = Header(default=None, alias="X-Idempotency-Key"),
    s: Session = Depends(get_session)
):
    """
    Build invoice from database data for specified period.
    
    Args:
        payload: Invoice build request with client_id and period
        request: FastAPI request object
        x_idempotency_key: Optional idempotency key for G4 gate (NOOP ≤100ms)
        s: Database session
        
    Returns:
        InvoiceOut: Created invoice with paths to generated artifacts
        
    Raises:
        HTTPException: 409 if duplicate idempotency key with different payload
    """
    # G4: Idempotency check - return cached result if key exists (NOOP ≤100ms)
    if x_idempotency_key:
        payload_hash = scope_hash(payload.dict())
        
        # Check existing key
        existing = s.execute(
            text("SELECT scope_hash, result_json FROM idempotency_keys WHERE key=:k"),
            {"k": x_idempotency_key}
        ).fetchone()
        
        if existing:
            stored_hash, result_json = existing
            
            # Validate payload matches (409 if different)
            if stored_hash != payload_hash:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "idempotency_key_conflict",
                        "message": f"Key exists with different payload"
                    }
                )
            
            # Return cached result (NOOP path ≤100ms)
            if result_json:
                cached = json.loads(result_json)
                return InvoiceOut(**cached)
    
    # Collect invoice data from database
    ctx = collect_invoice_data(
        payload.client_id,
        payload.period_from,
        payload.period_to,
        payload.currency
    )
    
    # Render DOCX (optional - stub for MVP)
    _docx = None
    try:
        _docx = render_docx(ctx)
    except Exception:
        _docx = None
    
    # Render HTML (always succeeds)
    html_path = render_html(ctx)
    
    # Convert to PDF if weasyprint available
    pdf_path = html_to_pdf(html_path)
    
    # Save invoice to database and create initial version (v1)
    # D1: ensure_decimal to prevent float in fmt_money
    total = ensure_decimal(ctx["total"])
    
    # D1: Convert Decimal amounts to strings for JSON serialization
    items_json = []
    for item in ctx.get("items", []):
        item_copy = item.copy()
        if isinstance(item_copy.get("amount"), Decimal):
            item_copy["amount"] = str(item_copy["amount"])
        items_json.append(item_copy)
    
    payload_json = {
        "client_id": payload.client_id,
        "period_from": payload.period_from,
        "period_to": payload.period_to,
        "currency": payload.currency,
        "items": items_json,
        "total": str(total)  # D1: serialize as string for JSON
    }
    
    # Create Invoice ORM object (Fix 1: ensures proper ID with s.refresh)
    import hashlib
    inv = Invoice(
        client_id=payload.client_id,
        period_from=payload.period_from,
        period_to=payload.period_to,
        total=str(total),  # D1: store as string to preserve precision
        currency=payload.currency,
        status="draft",
        version=1,
        pdf_path=pdf_path,
        xlsx_path=None,
        current_version=1
    )
    s.add(inv)
    s.commit()
    s.refresh(inv)  # Fix 1: guarantees inv.id is populated
    
    inv_id = inv.id
    
    # Insert initial version
    s.execute(text("""
        INSERT INTO invoice_versions(invoice_id, version, payload_json, pdf_path, html_path)
        VALUES(:iid, 1, :pjson, :pdf, :html)
    """), {
        "iid": inv_id,
        "pjson": json.dumps(payload_json, ensure_ascii=False),
        "pdf": pdf_path,
        "html": html_path
    })
    
    # Audit log record for version.create
    h = hashlib.sha256(json.dumps(payload_json, ensure_ascii=False).encode("utf-8")).hexdigest()
    s.execute(text("""
        INSERT INTO audit_log(action, entity, entity_id, payload_hash, metadata)
        VALUES('version.create', 'invoice', :iid, :ph, :meta)
    """), {"iid": inv_id, "ph": h, "meta": json.dumps({"version":1})})
    s.commit()
    
    # Record metric (no longer async - already in middleware)
    # Note: middleware records latency, this records business event
    record_metric("invoice.build", {"invoice_id": inv_id, "version": 1, "total": float(total)})
    
    # Build response
    result = InvoiceOut(
        id=inv_id,
        client_id=payload.client_id,
        period_from=payload.period_from,
        period_to=payload.period_to,
        total=total,
        currency=payload.currency,
        status="draft",
        version=1,
        pdf_path=pdf_path,
        xlsx_path=None
    )
    
    # G4: Cache result for idempotency (if key provided)
    if x_idempotency_key:
        payload_hash = scope_hash(payload.dict())
        s.execute(text("""
            INSERT OR REPLACE INTO idempotency_keys(key, scope_hash, status, result_json)
            VALUES(:k, :h, 'applied', :res)
        """), {
            "k": x_idempotency_key,
            "h": payload_hash,
            "res": json.dumps(result.dict(), ensure_ascii=False, default=str)
        })
        s.commit()
    
    return result


@app.post("/api/invoice.preview/{invoice_id}/issue")
def invoice_preview_issue(invoice_id: int):
    """Issue a 48-hour preview token for the invoice."""
    tok = uuid.uuid4().hex
    expires = (datetime.utcnow() + timedelta(hours=48)).isoformat()
    with SessionLocal() as s:
        # ensure invoice exists
        row = s.execute(text("SELECT id FROM invoices WHERE id=:i"), {"i": invoice_id}).fetchone()
        if not row:
            raise HTTPException(404, "invoice not found")
        s.execute(text("""
            INSERT INTO invoice_review_tokens(invoice_id, token, expires_at, ttl_seconds)
            VALUES(:i, :t, :e, :ttl)
        """), {"i": invoice_id, "t": tok, "e": expires, "ttl": 172800})
        _audit("preview.issue", "invoice", invoice_id, {"token": tok, "expires": expires}, s)
        s.commit()
    record_metric("preview.issue", {"invoice_id": invoice_id})
    return {"token": tok, "expires_at": expires, "url": f"http://127.0.0.1:8088/api/invoice.preview/{invoice_id}?token={tok}"}


def _validate_token(s, invoice_id: int, token: str) -> tuple[bool, str]:
    """Validate token: check TTL and one-time use. Returns (valid, reason)."""
    row = s.execute(text("""
        SELECT token, created_at, consumed_at, ttl_seconds FROM invoice_review_tokens
        WHERE invoice_id=:i AND token=:t
    """), {"i": invoice_id, "t": token}).fetchone()
    if not row:
        return (False, "not_found")
    
    created_at = row[1]
    consumed_at = row[2]
    ttl_seconds = row[3] or 172800
    
    # Check if already consumed (one-time use)
    if consumed_at is not None:
        return (False, "already_consumed")
    
    # Check TTL expiration
    try:
        if isinstance(created_at, str):
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            created = created_at
        expires_at = created + timedelta(seconds=ttl_seconds)
        if datetime.utcnow() > expires_at:
            return (False, "expired")
    except Exception:
        return (False, "invalid_timestamp")
    
    # Valid and not consumed - mark as consumed
    s.execute(text("""
        UPDATE invoice_review_tokens SET consumed_at=:now
        WHERE invoice_id=:i AND token=:t
    """), {"now": datetime.utcnow(), "i": invoice_id, "t": token})
    
    return (True, "accepted")


@app.get("/api/invoice.preview/{invoice_id}")
def invoice_preview_view(invoice_id: int, token: str):
    """Return single-file HTML preview for the current version using a valid token."""
    with SessionLocal() as s:
        valid, reason = _validate_token(s, invoice_id, token)
        if not valid:
            _audit("preview.view", "invoice", invoice_id, {"valid": False, "reason": reason}, s)
            record_metric("preview.view", {"invoice_id": invoice_id, "valid": False}, outcome=reason)
            s.commit()
            raise HTTPException(403, f"Token {reason}")
        # fetch current version payload
        cur_v = s.execute(text("SELECT current_version FROM invoices WHERE id=:i"), {"i": invoice_id}).scalar()
        if not cur_v:
            raise HTTPException(404, "invoice has no version")
        payload = _fetch_invoice_version(s, invoice_id, int(cur_v))
        _audit("preview.view", "invoice", invoice_id, {"valid": True, "version": int(cur_v)}, s)
        s.commit()
    record_metric("preview.view", {"invoice_id": invoice_id, "valid": True, "version": int(cur_v)})
    # Build single-file HTML (avoid Python formatting conflicts)
    payload_json = json.dumps(payload, ensure_ascii=False)
    html_tpl = """<!doctype html>
<html><head>
<meta charset='utf-8'>
<title>Invoice Preview #__INVOICE_ID__</title>
<style>
body{font-family:Arial,sans-serif;margin:24px;}
table{border-collapse:collapse;width:100%;margin-top:16px;}
th,td{border:1px solid #ddd;padding:6px;text-align:left;}
.total{font-weight:bold;margin-top:12px;}
.error{color:#b00}
</style>
</head><body>
<h2>Invoice Preview #__INVOICE_ID__</h2>
<script type="application/json" id="invoice">__PAYLOAD_JSON__</script>
<div id="content"></div>
<h3>Предложить правку</h3>
<div>
    <label>Тип: <select id="kind"><option value="edit_item">edit_item</option><option value="add_item">add_item</option><option value="comment">comment</option></select></label>
    <br>
    <textarea id="payload" rows="6" style="width:100%" placeholder='{"path":"items[0].qty","new":3}'></textarea>
    <br>
    <button id="send">Отправить</button>
    <div id="msg" class="error"></div>
</div>
<script>
const data = JSON.parse(document.getElementById('invoice').textContent);
function esc(x){ return x==null? '' : x }
function render(){
    let rows = '';
    (data.items||[]).forEach(function(it,i){
        rows += '<tr><td>'+i+'</td><td>'+esc(it.date)+'</td><td>'+esc(it.worker)+'</td><td>'+esc(it.task)+'</td><td>'+esc(it.qty)+'</td><td>'+esc(it.unit)+'</td><td>'+esc(it.amount)+'</td></tr>';
    });
    document.getElementById('content').innerHTML = 
        '<p><strong>Клиент:</strong> '+esc(data.client_id)+'</p>'+
        '<p><strong>Период:</strong> '+esc(data.period_from)+' — '+esc(data.period_to)+'</p>'+
        '<table><tr><th>#</th><th>Date</th><th>Worker</th><th>Task</th><th>Qty</th><th>Unit</th><th>Amount</th></tr>'+rows+'</table>'+
        '<div class=\'total\'>Total: '+esc(data.total)+' '+esc(data.currency)+'</div>';
}
render();
document.getElementById('send').onclick = async function(){
    try{
        const body = { invoice_id: __INVOICE_ID__, token: '__TOKEN__', kind: document.getElementById('kind').value, payload: JSON.parse(document.getElementById('payload').value||'{}') };
        const res = await fetch('http://127.0.0.1:8088/api/invoice.suggest_change', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
        const j = await res.json();
        document.getElementById('msg').textContent = 'OK: id=' + (j.id||'?');
    }catch(e){ document.getElementById('msg').textContent = 'Ошибка: ' + e; }
};
</script>
</body></html>"""
    html = html_tpl.replace("__INVOICE_ID__", str(invoice_id)).replace("__TOKEN__", token).replace("__PAYLOAD_JSON__", payload_json)
    return html


@app.post("/api/invoice.suggest_change", status_code=201)
def invoice_suggest_change(payload: dict):
    """Accept a suggestion from customer (requires valid token)."""
    invoice_id = int((payload.get("invoice_id") or 0))
    token = str(payload.get("token") or "")
    kind = str(payload.get("kind") or "comment")
    sug_payload = payload.get("payload") or {}
    
    # G5: Block forbidden operations (check both kind and payload.operation)
    operation = sug_payload.get("operation") if isinstance(sug_payload, dict) else None
    if kind in FORBIDDEN_OPS or operation in FORBIDDEN_OPS:
        with SessionLocal() as s:
            _audit("suggest.create", "invoice", invoice_id, {
                "kind": kind,
                "operation": operation,
                "outcome": "rejected",
                "reason": "forbidden_op"
            }, s)
            s.commit()
        record_metric("suggest.forbidden", {"invoice_id": invoice_id, "kind": kind, "operation": operation}, outcome="rejected")
        raise HTTPException(status_code=403, detail=f"Operation forbidden: {operation or kind}")
    
    with SessionLocal() as s:
        if not _validate_token(s, invoice_id, token):
            raise HTTPException(401, "invalid or expired token")
        r = s.execute(text("""
            INSERT INTO invoice_suggestions(invoice_id, source, kind, payload_json, status)
            VALUES(:i, 'customer', :k, :p, 'pending')
        """), {"i": invoice_id, "k": kind, "p": json.dumps(sug_payload, ensure_ascii=False)})
        sug_id = s.execute(text("SELECT last_insert_rowid()")).scalar()
        
        # Create pending_changes record for moderation
        s.execute(text("""
            INSERT INTO pending_changes(kind, payload_json, status, actor, correlation_id)
            VALUES(:k, :p, 'pending', 'customer', :corr)
        """), {"k": f"invoice_suggestion.{kind}", "p": json.dumps({"suggestion_id": int(sug_id) if sug_id else 0, "invoice_id": invoice_id, "payload": sug_payload}, ensure_ascii=False), "corr": f"sug-{sug_id}"})
        
        _audit("suggest.create", "invoice", invoice_id, {"id": sug_id, "kind": kind}, s)
        s.commit()
    record_metric("suggest.create", {"invoice_id": invoice_id, "suggestion_id": int(sug_id) if sug_id else None, "kind": kind})
    record_metric("mod.pending.create", {"entity": "invoice_suggestion", "suggestion_id": int(sug_id) if sug_id else None, "invoice_id": invoice_id}, outcome="pending")
    return {"id": int(sug_id) if sug_id else 0, "status": "pending"}


@app.get("/api/invoice.suggestions/{invoice_id}")
def invoice_list_suggestions(invoice_id: int, status: str = "pending"):
    with SessionLocal() as s:
        if status == "all":
            rows = s.execute(text("SELECT id, source, kind, payload_json, status, created_at FROM invoice_suggestions WHERE invoice_id=:i ORDER BY id"), {"i": invoice_id}).fetchall()
        else:
            rows = s.execute(text("SELECT id, source, kind, payload_json, status, created_at FROM invoice_suggestions WHERE invoice_id=:i AND status=:st ORDER BY id"), {"i": invoice_id, "st": status}).fetchall()
    return [
        {"id": r[0], "source": r[1], "kind": r[2], "payload": json.loads(r[3]), "status": r[4], "created_at": r[5]}
        for r in rows
    ]


@app.post("/api/invoice.apply_suggestions")
def invoice_apply_suggestions(payload: dict):
    invoice_id = int((payload.get("invoice_id") or 0))
    ids = payload.get("suggestion_ids") or []
    if not isinstance(ids, list):
        raise HTTPException(400, "suggestion_ids must be a list")
    with SessionLocal() as s:
        # G5: Second line of defense - check for forbidden ops in suggestions
        rows_preview = s.execute(text(
            "SELECT id, kind FROM invoice_suggestions WHERE invoice_id=:i AND id IN (%s)" 
            % (",".join(str(int(x)) for x in ids) or "0")
        ), {"i": invoice_id}).fetchall()
        
        blocked = [r for r in rows_preview if r[1] in FORBIDDEN_OPS]
        if blocked:
            bad_kinds = sorted({r[1] for r in blocked})
            record_metric("suggest.apply_blocked", {"invoice_id": invoice_id, "kinds": bad_kinds}, outcome="rejected")
            raise HTTPException(status_code=403, detail=f"Forbidden suggestions present: {', '.join(bad_kinds)}")
        
        # Check if all suggestions are approved in pending_changes
        for sug_id in ids:
            pending = s.execute(text("""
                SELECT status FROM pending_changes 
                WHERE correlation_id=:corr AND kind LIKE 'invoice_suggestion.%'
            """), {"corr": f"sug-{sug_id}"}).fetchone()
            if not pending or pending[0] != "approved":
                _audit("suggest.apply.blocked", "invoice", invoice_id, {"reason": "moderation_required", "suggestion_id": int(sug_id)}, s)
                record_metric("mod.apply.blocked", {"invoice_id": invoice_id, "suggestion_id": int(sug_id)}, outcome="moderation_required")
                s.commit()
                raise HTTPException(403, f"Suggestion {sug_id} requires moderation approval")
        
        cur_v = int(s.execute(text("SELECT current_version FROM invoices WHERE id=:i"), {"i": invoice_id}).scalar() or 1)
        old_payload = _fetch_invoice_version(s, invoice_id, cur_v) or {}
        # fetch pending suggestions
        rows = s.execute(text("SELECT id, kind, payload_json FROM invoice_suggestions WHERE invoice_id=:i AND id IN (%s) AND status='pending'" % (",".join(str(int(x)) for x in ids) or "0")), {"i": invoice_id}).fetchall()
        new_payload = json.loads(json.dumps(old_payload))  # deep copy
        for r in rows:
            sug = {"id": r[0], "kind": r[1], "payload_json": json.loads(r[2])}
            new_payload = _apply_suggestion(new_payload, sug)
        # render artifacts
        html_path = render_html(new_payload)
        pdf_path = html_to_pdf(html_path)
        new_v = cur_v + 1
        s.execute(text("""
            INSERT INTO invoice_versions(invoice_id, version, payload_json, pdf_path, html_path)
            VALUES(:i, :v, :p, :pdf, :html)
        """), {"i": invoice_id, "v": new_v, "p": json.dumps(new_payload, ensure_ascii=False), "pdf": pdf_path, "html": html_path})
        s.execute(text("UPDATE invoices SET current_version=:v WHERE id=:i"), {"v": new_v, "i": invoice_id})
        if rows:
            s.execute(text("UPDATE invoice_suggestions SET status='accepted' WHERE id IN (%s)" % (",".join(str(int(x[0])) for x in rows))))
            # Mark pending_changes as consumed
            for r in rows:
                s.execute(text("UPDATE pending_changes SET status='consumed' WHERE correlation_id=:corr"), {"corr": f"sug-{r[0]}"})
        _audit("version.create", "invoice", invoice_id, {"version": new_v}, s)
        # diff
        changes = _diff_payload(old_payload, new_payload)
        _audit("suggest.apply", "invoice", invoice_id, {"applied": [int(r[0]) for r in rows]}, s)
        s.commit()
    record_metric("suggest.apply", {"invoice_id": invoice_id, "new_version": new_v, "applied": [int(r[0]) for r in rows] if rows else []})
    record_metric("mod.apply", {"invoice_id": invoice_id, "new_version": new_v, "count": len(rows)})
    return {"new_version": new_v, "diff": {"from": cur_v, "to": new_v, "changes": changes, "total": {"old": old_payload.get("total"), "new": new_payload.get("total")}}}


@app.get("/api/invoice/{invoice_id}/diff")
def invoice_diff(invoice_id: int, from_: str = "v1", to: str = "v2"):
    # parse versions like v1, v2
    try:
        v_from = int(from_.lstrip("v"))
        v_to = int(to.lstrip("v"))
    except Exception:
        raise HTTPException(400, "invalid version format")
    with SessionLocal() as s:
        p_from = _fetch_invoice_version(s, invoice_id, v_from)
        p_to = _fetch_invoice_version(s, invoice_id, v_to)
        if not p_from or not p_to:
            raise HTTPException(404, "version not found")
        changes = _diff_payload(p_from, p_to)
        _audit("diff.view", "invoice", invoice_id, {"from": v_from, "to": v_to}, s)
        s.commit()
    record_metric("diff.view", {"invoice_id": invoice_id, "from": v_from, "to": v_to})
    return {"from": v_from, "to": v_to, "changes": changes, "total": {"old": p_from.get("total"), "new": p_to.get("total")}}


@app.get("/api/admin/pending")
def admin_list_pending(
    admin: dict = Depends(get_current_admin),  # F4.4 A3: JWT + X-Admin-Secret support
    status: str = "pending",
    limit: int = 50,
    offset: int = 0,
    # API CHANGE: Added filters for MVP P0 (Inbox Bulk Approve scenario)
    kind: str = Query(None, description="Filter by item type (task/expense)"),
    worker: str = Query(None, description="Filter by worker/actor"),
    date_from: str = Query(None, description="Filter by created_at >= date (ISO8601)"),
    date_to: str = Query(None, description="Filter by created_at <= date (ISO8601)")
):
    """List pending moderation items with optional filters.
    
    MVP P0 Enhancement: Added kind, worker, date_from, date_to filters
    to support Inbox Bulk Approve scenario (Step 1).
    """
    with SessionLocal() as s:
        # Build dynamic WHERE clause
        where_clauses = []
        params = {"lim": limit, "off": offset}
        
        if status != "all":
            where_clauses.append("status = :status")
            params["status"] = status
        
        if kind:
            where_clauses.append("kind = :kind")
            params["kind"] = kind
        
        if worker:
            where_clauses.append("actor = :worker")
            params["worker"] = worker
        
        if date_from:
            where_clauses.append("created_at >= :date_from")
            params["date_from"] = date_from
        
        if date_to:
            where_clauses.append("created_at <= :date_to")
            params["date_to"] = date_to
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Count total items (for pagination)
        count_query = f"""
            SELECT COUNT(*) 
            FROM pending_changes 
            WHERE {where_sql}
        """
        total_count = s.execute(text(count_query), params).scalar() or 0
        
        # Fetch items
        query = f"""
            SELECT id, kind, payload_json, status, actor, created_at, reviewed_by, reviewed_at, review_reason
            FROM pending_changes 
            WHERE {where_sql}
            ORDER BY id DESC 
            LIMIT :lim OFFSET :off
        """
        
        rows = s.execute(text(query), params).fetchall()
    
    items = [
        {"id": r[0], "kind": r[1], "payload_preview": str(json.loads(r[2]))[:100] if r[2] else None, "status": r[3], "actor": r[4], "created_at": r[5], "reviewed_by": r[6], "reviewed_at": r[7], "review_reason": r[8]}
        for r in rows
    ]
    
    # F4.4: Return PaginatedResponse format for frontend compatibility
    total_pages = (total_count + limit - 1) // limit if limit > 0 else 1
    return {"items": items, "total": total_count, "pages": total_pages}


@app.post("/api/admin/pending/{id}/approve", dependencies=[Depends(admin_guard)])
def admin_approve_pending(id: int, payload: dict):
    """Approve a pending moderation item."""
    by = str(payload.get("by") or "admin")
    with SessionLocal() as s:
        row = s.execute(text("SELECT status FROM pending_changes WHERE id=:i"), {"i": id}).fetchone()
        if not row:
            raise HTTPException(404, "pending item not found")
        if row[0] != "pending":
            raise HTTPException(409, f"already reviewed with status: {row[0]}")
        s.execute(text("""
            UPDATE pending_changes SET status='approved', reviewed_by=:by, reviewed_at=:at
            WHERE id=:i
        """), {"by": by, "at": datetime.utcnow(), "i": id})
        _audit("mod.approve", "pending_changes", id, {"by": by}, s)
        s.commit()
    record_metric("mod.approve", {"id": id, "by": by})
    return {"id": id, "status": "approved", "by": by}


@app.post("/api/admin/pending/{id}/reject", dependencies=[Depends(admin_guard)])
def admin_reject_pending(id: int, payload: dict):
    """Reject a pending moderation item."""
    by = str(payload.get("by") or "admin")
    reason = str(payload.get("reason") or "")
    if len(reason) < 5:
        raise HTTPException(400, "reason must be at least 5 characters")
    with SessionLocal() as s:
        row = s.execute(text("SELECT status FROM pending_changes WHERE id=:i"), {"i": id}).fetchone()
        if not row:
            raise HTTPException(404, "pending item not found")
        if row[0] != "pending":
            raise HTTPException(409, f"already reviewed with status: {row[0]}")
        s.execute(text("""
            UPDATE pending_changes SET status='rejected', reviewed_by=:by, reviewed_at=:at, review_reason=:reason
            WHERE id=:i
        """), {"by": by, "at": datetime.utcnow(), "reason": reason, "i": id})
        _audit("mod.reject", "pending_changes", id, {"by": by, "reason": reason}, s)
        s.commit()
    record_metric("mod.reject", {"id": id, "by": by, "reason": reason})
    return {"id": id, "status": "rejected", "by": by}


@app.post("/api/admin/pending/bulk.approve", dependencies=[Depends(admin_guard)])
def admin_bulk_approve_pending(
    payload: dict,
    x_idempotency_key: str = Header(None, alias="X-Idempotency-Key")
):
    """G4: Bulk approve pending items with idempotency guard (≤100ms repeat detection).
    
    Request:
        POST /api/admin/pending/bulk.approve
        Headers: X-Idempotency-Key: <unique-key>
        Body: {"ids": [1, 2, 3], "by": "admin"}
    
    Response (200 first):
        {"approved_count": 3, "ids": [1, 2, 3], "by": "admin"}
    
    Response (409 repeat):
        {"error": "duplicate_idempotency_key", "message": "...", "scope_hash": "..."}
    """
    if not x_idempotency_key:
        raise HTTPException(400, "X-Idempotency-Key header required")
    
    ids = payload.get("ids", [])
    by = str(payload.get("by", "admin"))
    
    if not isinstance(ids, list) or not ids:
        raise HTTPException(400, "ids must be non-empty list")
    
    # Idempotency guard
    scope = scope_hash(payload)
    with SessionLocal() as s:
        ensure_idempotent(s, x_idempotency_key, scope)
        
        # Approve all IDs
        approved = []
        for id in ids:
            row = s.execute(text("SELECT status FROM pending_changes WHERE id=:i"), {"i": id}).fetchone()
            if row and row[0] == "pending":
                s.execute(text("""
                    UPDATE pending_changes SET status='approved', reviewed_by=:by, reviewed_at=:at
                    WHERE id=:i
                """), {"by": by, "at": datetime.utcnow(), "i": id})
                _audit("mod.bulk_approve", "pending_changes", id, {"by": by, "bulk": True}, s)
                approved.append(id)
        
        s.commit()
    
    record_metric("mod.bulk_approve", {"count": len(approved), "by": by, "idempotent": False})
    return {"approved_count": len(approved), "ids": approved, "by": by}


# ════════════════════════════════════════════════════════════════════════════
# MVP P0: Clients & Invoices API (for Web UI)
# ════════════════════════════════════════════════════════════════════════════

@app.get("/api/clients")
def list_clients(
    admin: dict = Depends(get_current_admin),  # F4.5: JWT auth support (like other admin endpoints)
    s: Session = Depends(get_session),
):
    """List all clients for invoice filter dropdown (MVP P0 - Step 3)."""
    clients = s.query(Client).filter(Client.is_active == 1).all()
    return {
        "items": [
            {
                "id": c.id,
                "name": c.company_name,
                "nickname1": c.nickname1,
                "nickname2": c.nickname2,
            }
            for c in clients
        ]
    }


@app.post("/api/clients", status_code=status.HTTP_201_CREATED)
def create_client(
    request: Request,
    admin: dict = Depends(get_current_admin),
    s: Session = Depends(get_session),
):
    """Create new client."""
    from pydantic import BaseModel
    
    class ClientCreate(BaseModel):
        name: str
        contact: str | None = None
        default_pricing_rule: str | None = None
    
    # Parse JSON body
    import asyncio
    body_bytes = asyncio.run(request.body())
    client_data = ClientCreate.model_validate_json(body_bytes)
    
    new_client = Client(
        company_name=client_data.name,
        nickname1=client_data.name,  # Use name as nickname1 for now
        nickname2=None,
        phone=client_data.contact,
        daily_rate=None,  # Not in form
        is_active=1
    )
    s.add(new_client)
    s.commit()
    s.refresh(new_client)
    return {
        "id": new_client.id,
        "name": new_client.company_name,
        "nickname1": new_client.nickname1,
        "nickname2": new_client.nickname2,
    }


# F4.5: CSV Export for Invoices (MUST be before /api/invoices/{invoice_id} to avoid route conflict)
@app.get("/api/invoices/export")
def export_invoices_csv(
    admin: dict = Depends(get_current_admin),
    s: Session = Depends(get_session),
    invoice_status: str | None = Query(None, alias="status"),
    client_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """
    Export invoices to CSV with filters (max 10,000 rows).
    Format: ID, client, date_from, date_to, total_amount, status, items_count, created_at
    Returns: StreamingResponse with CSV file (UTF-8 BOM for Excel)
    Filename: invoices_YYYYMMDD_HHMMSS.csv
    """
    import csv
    from io import StringIO
    from datetime import datetime, timezone
    
    # Build WHERE clause with same logic as list_invoices
    where_clauses = ["1=1"]
    params = {}
    
    if invoice_status and invoice_status != "all":
        where_clauses.append("i.status = :status")
        params["status"] = invoice_status
    
    if client_id:
        where_clauses.append("i.client_id = :client_id")
        params["client_id"] = client_id
    
    if date_from:
        where_clauses.append("i.period_from >= :date_from")
        params["date_from"] = date_from
    
    if date_to:
        where_clauses.append("i.period_to <= :date_to")
        params["date_to"] = date_to
    
    where_sql = " AND ".join(where_clauses)
    
    # Row limit protection (10K max)
    count_sql = f"SELECT COUNT(*) FROM invoices i WHERE {where_sql}"
    total = s.execute(text(count_sql), params).scalar()
    if total > 10000:
        raise HTTPException(422, detail={
            "code": "export_too_large",
            "message": f"Export limited to 10,000 rows (found {total}). Please narrow filters.",
            "total": total
        })
    
    # Fetch data
    query_sql = f"""
        SELECT 
            i.id,
            i.client_id,
            i.period_from,
            i.period_to,
            i.total,
            i.status,
            i.created_at
        FROM invoices i
        WHERE {where_sql}
        ORDER BY i.period_from DESC, i.id DESC
    """
    rows = s.execute(text(query_sql), params).fetchall()
    
    # Generate CSV with UTF-8 BOM
    output = StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Client', 'Date From', 'Date To', 'Total Amount', 'Status', 'Created At'])
    
    # Data rows (items_count not in schema, omit from CSV)
    for r in rows:
        writer.writerow([
            r.id,
            r.client_id or '',
            r.period_from or '',
            r.period_to or '',
            r.total or 0,
            r.status or 'draft',
            r.created_at or ''
        ])
    
    # Return as downloadable file
    csv_content = output.getvalue()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"invoices_{timestamp}.csv"
    
    return StreamingResponse(
        iter([csv_content.encode('utf-8')]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/invoices/{invoice_id}", dependencies=[Depends(admin_guard)])
def get_invoice_details(invoice_id: int):
    """Get invoice details with line items (MVP P0 - Step 3).
    
    Returns:
        {
            "id": 1,
            "client_name": "ABC Corp",
            "date_from": "2025-01-01",
            "date_to": "2025-01-31",
            "status": "draft",
            "total_amount": 15000.00,
            "subtotal": 14000.00,
            "tax": 1000.00,
            "items": [
                {"type": "task", "description": "Work on site", "quantity": 10, "unit_price": 1000, "amount": 10000},
                {"type": "expense", "description": "Materials", "quantity": 1, "unit_price": 4000, "amount": 4000}
            ]
        }
    """
    with SessionLocal() as s:
        invoice = s.query(Invoice).filter(Invoice.id == invoice_id).first()
        if not invoice:
            raise HTTPException(404, "Invoice not found")
        
        # Fetch line items from invoice_items table
        items_rows = s.execute(text("""
            SELECT type, description, quantity, unit_price, amount
            FROM invoice_items
            WHERE invoice_id = :inv_id
            ORDER BY id
        """), {"inv_id": invoice_id}).fetchall()
        
        items = [
            {
                "type": r[0],
                "description": r[1],
                "quantity": float(r[2]) if r[2] else 0,
                "unit_price": float(r[3]) if r[3] else 0,
                "amount": float(r[4]) if r[4] else 0,
            }
            for r in items_rows
        ]
        
        # Calculate totals (simple version - tax assumed 0 for MVP)
        subtotal = sum(item["amount"] for item in items)
        tax = 0.0  # Tax calculation logic can be added later
        total = subtotal + tax
        
        # Get client name
        client_row = s.execute(text("SELECT company_name FROM clients WHERE id = :cid"), {"cid": invoice.client_id}).fetchone()
        client_name = client_row[0] if client_row else "Unknown Client"
        
        return {
            "id": invoice.id,
            "client_name": client_name,
            "date_from": invoice.date_from.isoformat() if invoice.date_from else None,
            "date_to": invoice.date_to.isoformat() if invoice.date_to else None,
            "status": invoice.status,
            "total_amount": float(invoice.total_amount) if invoice.total_amount else total,
            "subtotal": subtotal,
            "tax": tax,
            "items": items,
        }


    return {"id": id, "status": "rejected", "by": by, "reason": reason}


# ════════════════════════════════════════════════════════════════════════════
# CRITICAL FIX: Basic CRUD endpoints for Web UI
# ════════════════════════════════════════════════════════════════════════════
# These endpoints were MISSING but used by frontend (ClientsPage, ExpensesPage, InvoicesPage)
# // API CHANGE: Added critical missing endpoints for list operations

@app.get("/api/tasks")
def list_tasks(
    admin: dict = Depends(get_current_admin),  # F4.5: JWT auth support
    s: Session = Depends(get_session),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    worker: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """List tasks with pagination and filters (Web UI CRUD).
    
    NOTE: Tasks feature not yet fully implemented in backend.
    Returns empty list until full data model is ready.
    Frontend expects: worker_id, client_id, description, pricing_rule, quantity, amount, date, status
    Database has: shift_id, rate_code, qty, amount, note (different structure)
    TODO: Implement proper work tasks data model or create VIEW joining shifts+tasks+users+clients
    """
    # Return empty list for now (prevents 500 errors)
    return {"items": [], "total": 0, "pages": 0, "page": page}


@app.get("/api/expenses")
def list_expenses(
    admin: dict = Depends(get_current_admin),  # F4.4 A3: JWT + X-Admin-Secret support
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    category: str | None = Query(None),
    worker: str | None = Query(None),
    date_from: str | None = Query(None),  # Filter: created_at >= date_from (inclusive)
    date_to: str | None = Query(None),    # Filter: created_at <= date_to (inclusive)
):
    """
    List expenses with pagination and filters (Web UI CRUD).
    
    Date range filter model:
    - date_from/date_to apply to 'created_at' field (expense timestamp)
    - Both boundaries are INCLUSIVE (>= and <=)
    - Dates expected in ISO8601 format (YYYY-MM-DD)
    - No timezone handling (dates stored as TEXT in SQLite)
    
    Schema note: expenses table has worker_id (TEXT), category, amount, 
    currency, created_at, confirmed (INTEGER 0/1), no 'date' or 'status' fields.
    """
    with SessionLocal() as s:
        # Build dynamic WHERE clause
        where_clauses = []
        params = {}
        
        # Note: 'status' filter maps to 'confirmed' field (0=pending, 1=confirmed)
        if status and status != "all":
            if status == "confirmed":
                where_clauses.append("confirmed = 1")
            elif status == "pending":
                where_clauses.append("confirmed = 0")
        
        if category and category != "all":
            where_clauses.append("category = :category")
            params["category"] = category
        
        if worker:
            where_clauses.append("worker_id LIKE :worker")
            params["worker"] = f"%{worker}%"
        
        if date_from:
            # INCLUSIVE lower bound (created_at >= date_from)
            where_clauses.append("created_at >= :date_from")
            params["date_from"] = date_from
        
        if date_to:
            # INCLUSIVE upper bound (created_at <= date_to + 1 day for full day coverage)
            where_clauses.append("created_at < :date_to_excl")
            params["date_to_excl"] = f"{date_to}T23:59:59"  # End of day
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Count total
        count_sql = f"SELECT COUNT(*) FROM expenses WHERE {where_sql}"
        total = s.execute(text(count_sql), params).scalar()
        
        # Fetch page
        offset = (page - 1) * limit
        query_sql = f"""
            SELECT 
                id,
                worker_id,
                shift_id,
                category,
                amount,
                currency,
                photo_ref,
                ocr_text,
                created_at,
                confirmed,
                source
            FROM expenses
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = limit
        params["offset"] = offset
        rows = s.execute(text(query_sql), params).fetchall()
        
        items = [
            {
                "id": r.id,
                "worker": r.worker_id,
                "worker_name": r.worker_id,  # For frontend compatibility
                "category": r.category,
                "amount": float(r.amount) if r.amount else 0,
                "currency": r.currency or "ILS",
                "date": r.created_at,  # UI expects 'date' field
                "description": r.ocr_text or "",  # Use OCR text as description
                "photo_ref": r.photo_ref,
                "status": "confirmed" if r.confirmed else "pending",
                "created_at": r.created_at,
            }
            for r in rows
        ]
        
        pages = (total + limit - 1) // limit
        return {"items": items, "total": total, "pages": pages, "page": page}


@app.get("/api/expenses/export")
def export_expenses_csv(
    admin: dict = Depends(get_current_admin),
    s: Session = Depends(get_session),
    status: str | None = Query(None),
    category: str | None = Query(None),
    worker: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """
    Export expenses to CSV with filters (max 10,000 rows).
    Format: ID, date, amount, category, worker, status, photo_ref, confirmed
    Returns: StreamingResponse with CSV file (UTF-8 BOM for Excel)
    Filename: expenses_YYYYMMDD_HHMMSS.csv
    """
    import csv
    from io import StringIO
    from datetime import datetime, timezone
    
    # Build WHERE clause with same logic as list_expenses
    where_clauses = ["1=1"]
    params = {}
    
    if status and status != "all":
        if status == "confirmed":
            where_clauses.append("e.confirmed = 1")
        elif status == "pending":
            where_clauses.append("e.confirmed = 0")
    
    if category and category != "all":
        where_clauses.append("e.category = :category")
        params["category"] = category
    
    if worker and worker != "all":
        where_clauses.append("e.worker_id = :worker")
        params["worker"] = worker
    
    if date_from:
        where_clauses.append("e.created_at >= :date_from")
        params["date_from"] = date_from
    
    if date_to:
        where_clauses.append("e.created_at <= :date_to")
        params["date_to"] = date_to
    
    where_sql = " AND ".join(where_clauses)
    
    # Row limit protection (10K max)
    count_sql = f"SELECT COUNT(*) FROM expenses e WHERE {where_sql}"
    total = s.execute(text(count_sql), params).scalar()
    if total > 10000:
        raise HTTPException(422, detail={
            "code": "export_too_large",
            "message": f"Export limited to 10,000 rows (found {total}). Please narrow filters.",
            "total": total
        })
    
    # Fetch data
    query_sql = f"""
        SELECT 
            e.id,
            e.created_at,
            e.amount,
            e.category,
            e.worker_id,
            e.confirmed,
            e.photo_ref,
            e.ocr_text
        FROM expenses e
        WHERE {where_sql}
        ORDER BY e.created_at DESC, e.id DESC
    """
    rows = s.execute(text(query_sql), params).fetchall()
    
    # Generate CSV with UTF-8 BOM
    output = StringIO()
    output.write('\ufeff')  # UTF-8 BOM for Excel
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Date', 'Amount', 'Category', 'Worker', 'Status', 'Photo Ref', 'Confirmed'])
    
    # Data rows
    for r in rows:
        writer.writerow([
            r.id,
            r.created_at or '',
            r.amount or 0,
            r.category or '',
            r.worker_id or '',
            'confirmed' if r.confirmed else 'pending',
            r.photo_ref or '',
            'Yes' if r.confirmed else 'No'
        ])
    
    # Return as downloadable file
    csv_content = output.getvalue()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"expenses_{timestamp}.csv"
    
    return StreamingResponse(
        iter([csv_content.encode('utf-8')]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/invoices")
def list_invoices(
    admin: dict = Depends(get_current_admin),  # F4.4 A3: JWT + X-Admin-Secret support
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    client_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """List invoices with pagination and filters (Web UI CRUD)."""
    with SessionLocal() as s:
        # Build dynamic WHERE clause
        where_clauses = []
        params = {}
        
        if status and status != "all":
            where_clauses.append("i.status = :status")
            params["status"] = status
        if client_id:
            where_clauses.append("i.client_id = :client_id")
            params["client_id"] = client_id
        if date_from:
            where_clauses.append("i.period_from >= :date_from")
            params["date_from"] = date_from
        if date_to:
            where_clauses.append("i.period_to <= :date_to")
            params["date_to"] = date_to
        
        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        
        # Count total
        count_sql = f"SELECT COUNT(*) FROM invoices i WHERE {where_sql}"
        total = s.execute(text(count_sql), params).scalar()
        
        # Fetch page (note: no clients table join - client_id is TEXT)
        offset = (page - 1) * limit
        query_sql = f"""
            SELECT 
                i.id,
                i.client_id,
                i.period_from,
                i.period_to,
                i.total,
                i.currency,
                i.status,
                i.version,
                i.created_at
            FROM invoices i
            WHERE {where_sql}
            ORDER BY i.period_from DESC, i.id DESC
            LIMIT :limit OFFSET :offset
        """
        params["limit"] = limit
        params["offset"] = offset
        rows = s.execute(text(query_sql), params).fetchall()
        
        items = [
            {
                "id": r.id,
                "client_id": r.client_id,
                "client_name": r.client_id,  # client_id IS the name (TEXT field)
                "date_from": r.period_from,
                "date_to": r.period_to,
                "total_amount": float(r.total) if r.total else 0,
                "status": r.status or "draft",
                "items_count": 0,  # Not in schema, placeholder for UI compat
                "created_at": r.created_at,
            }
            for r in rows
        ]
        
        pages = (total + limit - 1) // limit
        return {"items": items, "total": total, "pages": pages, "page": page}


# ════════════════════════════════════════════════════════════════════════════
# MVP P0: CSV Export Endpoints (ШАГ 4) — LEGACY (use /api/expenses/export and /api/invoices/export instead)
# ════════════════════════════════════════════════════════════════════════════

# API CHANGE: Server-side CSV export for Expenses (replaces client-side export)
@app.get("/api/admin/expenses/export", dependencies=[Depends(admin_guard)])
async def export_expenses_csv(
    db: Session = Depends(get_session),
    worker: str | None = Query(None),
    category: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """
    Export expenses to CSV with optional filtering.
    
    MVP P0 ШАГ 4: Server-side export prevents browser memory issues.
    Row limit: 10,000 to prevent abuse.
    """
    import csv
    from io import StringIO
    
    # Build dynamic WHERE clause (same as Expenses page filtering)
    where_clauses = []
    params = {}
    
    if worker:
        where_clauses.append("worker = :worker")
        params["worker"] = worker
    if category and category != "all":
        where_clauses.append("category = :category")
        params["category"] = category
    if date_from:
        where_clauses.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("date <= :date_to")
        params["date_to"] = date_to
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Row limit protection
    count_sql = f"SELECT COUNT(*) FROM expenses WHERE {where_sql}"
    total = db.execute(text(count_sql), params).scalar()
    if total > 10000:
        raise HTTPException(422, detail={
            "code": "export_too_large",
            "message": f"Export limited to 10,000 rows (found {total}). Please narrow filters.",
            "total": total
        })
    
    # Fetch data
    query_sql = f"""
        SELECT id, worker, category, amount, currency, date, description, photo_ref, created_at
        FROM expenses
        WHERE {where_sql}
        ORDER BY date DESC, id DESC
    """
    rows = db.execute(text(query_sql), params).fetchall()
    
    # Generate CSV with UTF-8 BOM (Excel compatibility)
    output = StringIO()
    output.write('\ufeff')  # UTF-8 BOM
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Worker', 'Category', 'Amount', 'Currency', 'Date', 'Description', 'Photo Ref', 'Created At'])
    
    # Data rows
    for row in rows:
        writer.writerow([
            row.id,
            row.worker or '',
            row.category or '',
            row.amount,
            row.currency or 'ILS',
            row.date or '',
            row.description or '',
            row.photo_ref or '',
            row.created_at or ''
        ])
    
    # Return as downloadable file
    csv_content = output.getvalue()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"expenses_{timestamp}.csv"
    
    return StreamingResponse(
        iter([csv_content.encode('utf-8')]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# API CHANGE: Server-side CSV export for Invoices (replaces client-side export)
@app.get("/api/admin/invoices/export", dependencies=[Depends(admin_guard)])
async def export_invoices_csv(
    db: Session = Depends(get_session),
    client_id: int | None = Query(None),
    status: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
):
    """
    Export invoices to CSV with optional filtering.
    
    MVP P0 ШАГ 4: Server-side export prevents browser memory issues.
    Row limit: 10,000 to prevent abuse.
    """
    import csv
    from io import StringIO
    
    # Build dynamic WHERE clause (same as Invoices page filtering)
    where_clauses = []
    params = {}
    
    if client_id:
        where_clauses.append("i.client_id = :client_id")
        params["client_id"] = client_id
    if status and status != "all":
        where_clauses.append("i.status = :status")
        params["status"] = status
    if date_from:
        where_clauses.append("i.date_from >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("i.date_to <= :date_to")
        params["date_to"] = date_to
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Row limit protection
    count_sql = f"SELECT COUNT(*) FROM invoices i WHERE {where_sql}"
    total = db.execute(text(count_sql), params).scalar()
    if total > 10000:
        raise HTTPException(422, detail={
            "code": "export_too_large",
            "message": f"Export limited to 10,000 rows (found {total}). Please narrow filters.",
            "total": total
        })
    
    # Fetch data with client name
    query_sql = f"""
        SELECT 
            i.id,
            c.company_name AS client_name,
            i.date_from,
            i.date_to,
            i.total_amount,
            i.status,
            i.items_count,
            i.created_at
        FROM invoices i
        LEFT JOIN clients c ON i.client_id = c.id
        WHERE {where_sql}
        ORDER BY i.date_from DESC, i.id DESC
    """
    rows = db.execute(text(query_sql), params).fetchall()
    
    # Generate CSV with UTF-8 BOM (Excel compatibility)
    output = StringIO()
    output.write('\ufeff')  # UTF-8 BOM
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Client', 'Date From', 'Date To', 'Total Amount', 'Status', 'Items Count', 'Created At'])
    
    # Data rows
    for row in rows:
        writer.writerow([
            row.id,
            row.client_name or '',
            row.date_from or '',
            row.date_to or '',
            row.total_amount,
            row.status or '',
            row.items_count or 0,
            row.created_at or ''
        ])
    
    # Return as downloadable file
    csv_content = output.getvalue()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    filename = f"invoices_{timestamp}.csv"
    
    return StreamingResponse(
        iter([csv_content.encode('utf-8')]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ════════════════════════════════════════════════════════════════════════════
# Sprint A: PIN Onboarding Endpoints
# ════════════════════════════════════════════════════════════════════════════

@app.post("/api/admin/pin/create", status_code=201, dependencies=[Depends(admin_guard)])
def pin_create(payload: dict, x_internal_admin: str | None = Header(None)):
    """
    Create invite PIN for role-based onboarding.
    
    TD-A2: Requires X-Internal-Admin header for security.
    """
    # TD-A2: Admin auth check
    if settings.INTERNAL_ADMIN_SECRET:
        if x_internal_admin != settings.INTERNAL_ADMIN_SECRET:
            record_metric("pin.create", {"outcome": "rejected", "reason": "admin_required"})
            raise HTTPException(status_code=403, detail={
                "code": "admin_required",
                "message": "X-Internal-Admin header required"
            })
    
    code = payload.get("code")
    role = payload.get("role")
    expires_at = payload.get("expires_at")
    
    if not code or not role or not expires_at:
        raise HTTPException(422, "code, role, expires_at required")
    
    if role not in ["worker", "foreman", "admin"]:
        raise HTTPException(422, f"invalid role: {role}")
    
    with SessionLocal() as s:
        # Проверка уникальности кода
        existing = s.execute(text("SELECT id FROM invite_pins WHERE code=:c"), {"c": code}).fetchone()
        if existing:
            raise HTTPException(409, "code already exists")
        
        # Создание PIN
        s.execute(text("""
            INSERT INTO invite_pins (code, role, expires_at)
            VALUES (:code, :role, :expires_at)
        """), {"code": code, "role": role, "expires_at": expires_at})
        
        pin_id = s.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
        
        # Аудит
        _audit("pin.create", "invite_pins", pin_id, {"role": role, "ttl_h": 48}, s)
        s.commit()
    
    record_metric("pin.create", {"role": role, "code_prefix": code[:4]})
    return {"id": pin_id, "code": code, "role": role, "expires_at": expires_at}


@app.post("/api/admin/pin/bind", dependencies=[Depends(admin_guard)])
def pin_bind(payload: dict, x_internal_admin: str | None = Header(None)):
    """
    Bind Telegram account to role using invite PIN.
    
    TD-A2: Requires X-Internal-Admin header for security.
    """
    # TD-A2: Admin auth check
    if settings.INTERNAL_ADMIN_SECRET:
        if x_internal_admin != settings.INTERNAL_ADMIN_SECRET:
            record_metric("pin.bind", {"outcome": "rejected", "reason": "admin_required"})
            raise HTTPException(status_code=403, detail={
                "code": "admin_required",
                "message": "X-Internal-Admin header required"
            })
    
    code = payload.get("code")
    telegram_id = payload.get("telegram_id")
    
    if not code or not telegram_id:
        raise HTTPException(422, "code, telegram_id required")
    
    with SessionLocal() as s:
        # Проверка PIN
        pin_row = s.execute(text("""
            SELECT id, role, expires_at, used_by, used_at
            FROM invite_pins
            WHERE code=:c
        """), {"c": code}).fetchone()
        
        if not pin_row:
            raise HTTPException(403, "PIN не найден")
        
        pin_id, role, expires_at, used_by, used_at = pin_row
        
        # Проверка истечения
        if datetime.fromisoformat(expires_at) < datetime.now(timezone.utc):
            record_metric("bind.reject", {"telegram_id": telegram_id, "reason": "expired"})
            raise HTTPException(403, "PIN просрочен")
        
        # Проверка использования
        if used_by is not None:
            record_metric("bind.reject", {"telegram_id": telegram_id, "reason": "already_used"})
            raise HTTPException(403, "PIN уже использован")
        
        # Проверка существующей привязки
        existing_user = s.execute(text("""
            SELECT id, role FROM users WHERE telegram_id=:tid
        """), {"tid": str(telegram_id)}).fetchone()
        
        if existing_user:
            record_metric("bind.reject", {"telegram_id": telegram_id, "reason": "already_bound", "existing_role": existing_user[1]})
            raise HTTPException(403, f"У вас уже есть роль: {existing_user[1]}")
        
        # Создание пользователя
        s.execute(text("""
            INSERT INTO users (telegram_id, role, created_at)
            VALUES (:tid, :role, :now)
        """), {"tid": str(telegram_id), "role": role, "now": datetime.now(timezone.utc)})
        
        user_id = s.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
        
        # Отметка PIN как использованного
        s.execute(text("""
            UPDATE invite_pins
            SET used_by=:uid, used_at=:now
            WHERE id=:pid
        """), {"uid": user_id, "now": datetime.now(timezone.utc), "pid": pin_id})
        
        # Аудит
        _audit("bind.success", "users", user_id, {"telegram_id": telegram_id, "role": role, "pin_id": pin_id}, s)
        s.commit()
    
    record_metric("bind.success", {"telegram_id": telegram_id, "role": role})
    return {"user_id": user_id, "telegram_id": telegram_id, "role": role}


# ============================================================================
# Sprint B: Worker Shift Commands (Bot API)
# ============================================================================

@app.post("/api/bot/shift.in", status_code=201)
def bot_shift_in(payload: dict):
    """
    Start shift for worker (bot command /in).
    
    B2: Thin wrapper over /api/v1/shift/start with bot metrics.
    B4: Returns 409 if shift already open, 403 if not bound.
    B5: Always logs to bot_worker.jsonl (accepted/rejected).
    """
    telegram_id = payload.get("telegram_id")
    site = payload.get("site")
    location = payload.get("location")
    
    if not telegram_id:
        record_metric("bot.shift.in", {"outcome": "rejected", "reason": "missing_telegram_id"})
        raise HTTPException(status_code=400, detail="telegram_id required")
    
    # B4: Check user is bound (exists in users table)
    with SessionLocal() as s:
        user_row = s.execute(
            text("SELECT id FROM users WHERE telegram_id=:tid"),
            {"tid": str(telegram_id)}
        ).fetchone()
        
        if not user_row:
            record_metric("bot.shift.in", {
                "telegram_id": telegram_id,
                "outcome": "rejected",
                "reason": "not_bound"
            })
            raise HTTPException(status_code=403, detail={"code": "not_bound", "message": "Use /bind <PIN> first"})
        
        user_id = user_row[0]
        
        # B1 + B4: Check no open shift exists (DB constraint will also catch this)
        open_shift = s.execute(
            text("SELECT 1 FROM shifts WHERE user_id=:uid AND status='open' AND ended_at IS NULL LIMIT 1"),
            {"uid": user_id}
        ).fetchone()
        
        if open_shift:
            record_metric("bot.shift.in", {
                "telegram_id": telegram_id,
                "user_id": user_id,
                "outcome": "rejected",
                "reason": "shift_already_open"
            })
            raise HTTPException(status_code=409, detail={"code": "shift_already_open"})
        
        # Create shift
        now = datetime.now(timezone.utc)
        s.execute(text("""
            INSERT INTO shifts (user_id, status, created_at, site, location)
            VALUES (:uid, 'open', :now, :site, :location)
        """), {"uid": user_id, "now": now, "site": site, "location": location})
        
        shift_id = s.execute(text("SELECT last_insert_rowid()")).scalar()
        s.commit()
    
    record_metric("bot.shift.in", {
        "telegram_id": telegram_id,
        "user_id": user_id,
        "shift_id": shift_id,
        "outcome": "accepted"
    })
    
    # FIX: Always return JSON (not text/plain)
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True, "shift_id": shift_id, "status": "open", "created_at": now.isoformat()}, status_code=201)


@app.post("/api/bot/shift.out")
def bot_shift_out(payload: dict):
    """
    End shift for worker (bot command /out).
    
    B2: Returns breakdown with duration + pricing steps.
    B3: Transparent formula (yaml_key per step).
    B4: Returns 404 if no open shift, 422 if too short.
    B5: Always logs to bot_worker.jsonl.
    """
    telegram_id = payload.get("telegram_id")
    confirm = payload.get("confirm", True)  # FIX: Default to True (auto-confirm)
    
    if not telegram_id:
        record_metric("bot.shift.out", {"outcome": "rejected", "reason": "missing_telegram_id"})
        raise HTTPException(status_code=400, detail="telegram_id required")
    
    # FIX: Removed confirm=true requirement (always confirm by default)
    
    with SessionLocal() as s:
        # Find user
        user_row = s.execute(
            text("SELECT id FROM users WHERE telegram_id=:tid"),
            {"tid": str(telegram_id)}
        ).fetchone()
        
        if not user_row:
            record_metric("bot.shift.out", {"telegram_id": telegram_id, "outcome": "rejected", "reason": "not_bound"})
            raise HTTPException(status_code=403, detail={"code": "not_bound"})
        
        user_id = user_row[0]
        
        # B4: Find open shift
        shift_row = s.execute(text("""
            SELECT id, created_at, site, location
            FROM shifts
            WHERE user_id=:uid AND status='open' AND ended_at IS NULL
            LIMIT 1
        """), {"uid": user_id}).fetchone()
        
        if not shift_row:
            record_metric("bot.shift.out", {
                "telegram_id": telegram_id,
                "user_id": user_id,
                "outcome": "rejected",
                "reason": "shift_not_found"
            })
            raise HTTPException(status_code=404, detail={"code": "shift_not_found"})
        
        shift_id, created_at_str, site, location = shift_row
        created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        ended_at = datetime.now(timezone.utc)
        
        # B3 + B4: Duration check (min 1 minute to avoid misclicks)
        # TD-B2: Use configurable threshold from settings
        duration_seconds = (ended_at - created_at).total_seconds()
        if duration_seconds < settings.MIN_SHIFT_DURATION_S:
            record_metric("bot.shift.out", {
                "telegram_id": telegram_id,
                "user_id": user_id,
                "shift_id": shift_id,
                "duration_s": duration_seconds,
                "threshold_s": settings.MIN_SHIFT_DURATION_S,  # TD-B2: log threshold
                "outcome": "rejected",
                "reason": "shift_too_short"
            })
            raise HTTPException(status_code=422, detail={
                "code": "shift_too_short",
                "message": f"Shift must be at least {settings.MIN_SHIFT_DURATION_S}s (got {duration_seconds:.0f}s)"
            })
        
        # TD-B1: Use Decimal for money calculations
        from decimal import Decimal, ROUND_HALF_UP
        
        duration_h_decimal = Decimal(str(duration_seconds)) / Decimal('3600')
        
        # B3: Load pricing rules and calculate breakdown
        # TD-B3: Require base_rate_hour in YAML (no magic fallback)
        rules = load_rules()
        base_rate_config = rules.get("rates", {}).get("base_rate_hour")
        
        if base_rate_config is None:
            record_metric("bot.shift.out", {
                "telegram_id": telegram_id,
                "user_id": user_id,
                "shift_id": shift_id,
                "outcome": "rejected",
                "reason": "yaml_rate_missing"
            })
            raise HTTPException(status_code=500, detail={
                "code": "yaml_rate_missing",
                "message": "base_rate_hour not configured in rules/global.yaml"
            })
        
        base_rate = base_rate_config.get("value", 0)
        if base_rate <= 0:
            record_metric("bot.shift.out", {
                "telegram_id": telegram_id,
                "user_id": user_id,
                "shift_id": shift_id,
                "outcome": "rejected",
                "reason": "yaml_rate_invalid"
            })
            raise HTTPException(status_code=500, detail={
                "code": "yaml_rate_invalid",
                "message": f"base_rate_hour value invalid: {base_rate}"
            })
        
        base_rate_decimal = Decimal(str(base_rate))
        
        # Calculate total with Decimal precision
        total_decimal = (base_rate_decimal * duration_h_decimal).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        
        # Simple breakdown for now (Phase 10 logic can be integrated later)
        steps = [
            {
                "yaml_key": "base_rate_hour", 
                "description": "Base rate", 
                "value": float(base_rate_decimal), 
                "hours": float(duration_h_decimal.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP))
            }
        ]
        
        total = float(total_decimal)
        
        # Update shift
        s.execute(text("""
            UPDATE shifts
            SET status='closed', ended_at=:ended, duration_hours=:dur
            WHERE id=:sid
        """), {"ended": ended_at, "dur": float(duration_h_decimal), "sid": shift_id})
        s.commit()
    
    record_metric("bot.shift.out", {
        "telegram_id": telegram_id,
        "user_id": user_id,
        "shift_id": shift_id,
        "duration_s": duration_seconds,
        "total": total,
        "pricing_precision": "decimal",  # TD-B1: audit transition
        "outcome": "accepted"
    })
    
    return {
        "shift_id": shift_id,
        "status": "closed",
        "duration_h": float(duration_h_decimal.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
        "steps": steps,
        "total": total
    }


@app.get("/api/bot/shift.status")
def bot_shift_status(telegram_id: int):
    """
    Get current shift status (bot command /status).
    
    B2: Returns status=open|closed with live duration.
    B5: Logs every request.
    """
    with SessionLocal() as s:
        user_row = s.execute(
            text("SELECT id FROM users WHERE telegram_id=:tid"),
            {"tid": str(telegram_id)}
        ).fetchone()
        
        if not user_row:
            record_metric("bot.shift.status", {"telegram_id": telegram_id, "outcome": "not_bound"})
            return {"status": "not_bound", "message": "Use /bind <PIN> first"}
        
        user_id = user_row[0]
        
        # Check for open shift
        shift_row = s.execute(text("""
            SELECT id, created_at, site, location
            FROM shifts
            WHERE user_id=:uid AND status='open' AND ended_at IS NULL
            LIMIT 1
        """), {"uid": user_id}).fetchone()
        
        if shift_row:
            shift_id, created_at_str, site, location = shift_row
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            duration_live = (datetime.now(timezone.utc) - created_at).total_seconds()
            
            record_metric("bot.shift.status", {
                "telegram_id": telegram_id,
                "user_id": user_id,
                "shift_id": shift_id,
                "status": "open"
            })
            
            return {
                "status": "open",
                "shift_id": shift_id,
                "created_at": created_at.isoformat(),
                "duration_live_s": round(duration_live, 0),
                "site": site,
                "location": location
            }
        
        # Check last closed shift
        last_shift = s.execute(text("""
            SELECT id, created_at, ended_at
            FROM shifts
            WHERE user_id=:uid AND status='closed'
            ORDER BY ended_at DESC
            LIMIT 1
        """), {"uid": user_id}).fetchone()
        
        if last_shift:
            shift_id, created_at_str, ended_at_str = last_shift
            record_metric("bot.shift.status", {
                "telegram_id": telegram_id,
                "user_id": user_id,
                "status": "closed"
            })
            
            return {
                "status": "closed",
                "last_shift_id": shift_id,
                "ended_at": ended_at_str
            }
        
        record_metric("bot.shift.status", {"telegram_id": telegram_id, "user_id": user_id, "status": "no_shifts"})
        return {"status": "no_shifts"}


# ============================================================================
# Sprint C: Foreman Inbox (moderation)
# ============================================================================

def _check_foreman_role(s, telegram_id: int):
    """Check if telegram_id has foreman role. Raises 403 if not."""
    row = s.execute(text("""
        SELECT role FROM users WHERE telegram_id=:tid
    """), {"tid": telegram_id}).fetchone()
    
    if not row or row[0] != 'foreman':
        raise HTTPException(403, {"code": "forbidden_role", "message": "foreman role required"})


@app.get("/api/bot/inbox")
def bot_inbox(telegram_id: int, state: str = "pending", limit: int = 50, offset: int = 0):
    """
    Get mixed moderation inbox for foreman.
    Returns: expenses(needs_approval) + pending_changes(pending).
    
    G1: Requires foreman role → 403 forbidden_role.
    G6: Metrics logged (bot.inbox.fetch).
    TD-C2: Pagination with next_offset, limit≤1000, offset≤1e6.
    """
    # TD-C2: Validate pagination parameters
    if state != "pending":
        raise HTTPException(422, {"code": "invalid_state", "message": "Only state='pending' supported"})
    
    if limit <= 0 or limit > 1000:
        raise HTTPException(422, {"code": "invalid_limit", "message": "limit must be 1-1000"})
    
    if offset < 0 or offset > 1_000_000:
        raise HTTPException(422, {"code": "invalid_offset", "message": "offset must be 0-1000000"})
    
    s = SessionLocal()
    try:
        _check_foreman_role(s, telegram_id)
        
        items = []
        
        # 1. Fetch expenses(needs_approval)
        # NOTE: Filter ONLY by status='needs_approval' to avoid returning legacy confirmed=0 records
        expenses_rows = s.execute(text("""
            SELECT id, worker_id, shift_id, category, amount, currency, 
                   photo_ref, ocr_text, created_at, status, source
            FROM expenses
            WHERE status='needs_approval'
            ORDER BY created_at DESC, id DESC
            LIMIT :lim OFFSET :off
        """), {"lim": limit, "off": offset}).fetchall()
        
        for row in expenses_rows:
            exp_id, worker_id, shift_id, category, amount, currency, photo_ref, ocr_text, created_at, status, source = row
            
            # Parse OCR metadata if available
            ocr_meta = None
            if ocr_text:
                try:
                    ocr_meta = json.loads(ocr_text)
                except:
                    ocr_meta = {"raw": ocr_text}
            
            # Determine reason (simplified logic)
            reason = "over_limit" if amount > 500 else "manual_review"
            if not photo_ref:
                reason = "over_limit_no_photo"
            
            items.append({
                "kind": "expense",
                "id": exp_id,
                "created_at": created_at,
                "amount": float(amount),
                "currency": currency,
                "category": category,
                "status": status,
                "ocr_meta": ocr_meta,
                "reason": reason
            })
        
        # 2. Fetch pending_changes(pending)
        pc_rows = s.execute(text("""
            SELECT id, kind, payload_json, created_at, status
            FROM pending_changes
            WHERE status='pending'
            ORDER BY created_at ASC, id ASC
            LIMIT :lim OFFSET :off
        """), {"lim": limit, "off": offset}).fetchall()
        
        for row in pc_rows:
            pc_id, kind, payload_json, created_at, status = row
            payload = json.loads(payload_json) if payload_json else {}
            
            # Generate summary from diff
            diff = payload.get("diff", {})
            summary = f"Changes: {len(diff.get('add', []))} add, {len(diff.get('update', []))} update, {len(diff.get('remove', []))} remove"
            
            items.append({
                "kind": "pending_change",
                "id": pc_id,
                "created_at": created_at,
                "summary": summary,
                "diff": diff,
                "status": status
            })
        
        # TD-C1: Enhanced metrics with counts breakdown
        expense_count = sum(1 for item in items if item["kind"] == "expense")
        pc_count = sum(1 for item in items if item["kind"] == "pending_change")
        
        record_metric("bot.inbox.fetch", {
            "telegram_id": telegram_id,
            "state": state,
            "count": len(items),
            "counts": {
                "total": len(items),
                "expenses": expense_count,
                "pending_changes": pc_count
            },
            "outcome": "success"
        })
        
        # Calculate next_offset for pagination (TD-C2)
        next_offset = offset + len(items) if len(items) == limit else None
        
        return {
            "count": len(items),
            "items": items,
            "next_offset": next_offset
        }
    
    except HTTPException:
        raise
    except Exception as e:
        record_metric("bot.inbox.fetch", {"telegram_id": telegram_id, "outcome": "error", "error": str(e)})
        raise HTTPException(500, str(e))
    finally:
        s.close()


@app.post("/api/bot/approve")
def bot_approve(payload: dict):
    """
    Bulk approve items (expenses or pending_changes).
    
    Request: {"telegram_id": 111, "items": [{"kind":"expense","id":123},...]}
    Response: {"ok": N, "failed": M, "results": [{...}]}
    
    G1: Requires foreman role → 403 forbidden_role.
    G2: Stale state (already approved/rejected) → status="noop" or error.
    G3: Idempotent (repeat approve → noop).
    G5: Audit log for each approval.
    G6: Metrics logged (bot.inbox.approve).
    TD-C3: WHERE-guard with rowcount check.
    TD-C4: JSON validation (kind, id, limits).
    """
    telegram_id = payload.get("telegram_id")
    items = payload.get("items", [])
    
    # TD-C4: JSON validation
    if not telegram_id:
        raise HTTPException(422, {"code": "missing_telegram_id", "message": "telegram_id required"})
    
    if not items:
        raise HTTPException(400, {"code": "empty_items", "message": "items list cannot be empty"})
    
    if len(items) > 100:
        raise HTTPException(422, {"code": "too_many_items", "message": "items limit is 100"})
    
    # Validate each item kind/id upfront
    for item in items:
        kind = item.get("kind")
        item_id = item.get("id")
        
        if kind not in ["expense", "pending_change"]:
            raise HTTPException(422, {"code": "invalid_kind", "message": f"kind must be expense or pending_change, got {kind}"})
        
        if not item_id or item_id <= 0:
            raise HTTPException(422, {"code": "invalid_id", "message": "id must be positive integer"})
    
    s = SessionLocal()
    try:
        _check_foreman_role(s, telegram_id)
        
        # Get user_id for reviewed_by
        user_row = s.execute(text("SELECT id FROM users WHERE telegram_id=:tid"), {"tid": telegram_id}).fetchone()
        if not user_row:
            raise HTTPException(404, "user_not_found")
        
        reviewer_id = user_row[0]
        
        results = []
        ok_count = 0
        noop_count = 0
        failed_count = 0
        
        for item in items:
            kind = item.get("kind")
            item_id = item.get("id")
            
            if not kind or not item_id:
                results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "invalid_item"}})
                failed_count += 1
                continue
            
            try:
                if kind == "expense":
                    # Check current status
                    exp_row = s.execute(text("SELECT status FROM expenses WHERE id=:id"), {"id": item_id}).fetchone()
                    if not exp_row:
                        results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "not_found"}})
                        failed_count += 1
                        continue
                    
                    current_status = exp_row[0]
                    
                    if current_status == "approved":
                        # Idempotent: already approved → noop (G3)
                        results.append({"kind": kind, "id": item_id, "status": "noop"})
                        ok_count += 1
                        continue
                    
                    if current_status != "needs_approval":
                        # Stale state (G2)
                        results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "stale_state", "current": current_status}})
                        failed_count += 1
                        continue
                    
                    # TD-C3: WHERE-guard for race protection
                    result = s.execute(text("""
                        UPDATE expenses
                        SET status='approved', reviewed_by=:rev_by, reviewed_at=:rev_at
                        WHERE id=:id AND status='needs_approval'
                    """), {"id": item_id, "rev_by": reviewer_id, "rev_at": datetime.now(timezone.utc)})
                    
                    # Check rowcount for idempotency
                    if result.rowcount == 0:
                        # Already approved/rejected → noop (not stale_state)
                        results.append({"kind": kind, "id": item_id, "status": "noop"})
                        noop_count += 1
                        ok_count += 1
                        continue
                    
                    # TD-C5: Enhanced audit with payload_hash + actor
                    import hashlib
                    import json
                    
                    # Get current state for hash_before
                    exp_after = s.execute(text("SELECT status, reviewed_by FROM expenses WHERE id=:id"), {"id": item_id}).fetchone()
                    payload_before = {"status": current_status, "reviewed_by": None}
                    payload_after = {"status": exp_after[0], "reviewed_by": exp_after[1]}
                    
                    hash_before = hashlib.sha256(json.dumps(payload_before, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    hash_after = hashlib.sha256(json.dumps(payload_after, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    
                    _audit("approve_expense", "expense", item_id, {
                        "status": "approved",
                        "payload_hash_before": hash_before,
                        "payload_hash_after": hash_after,
                        "actor_telegram_id": telegram_id,
                        "actor_role": "foreman"
                    }, s)
                    
                    results.append({"kind": kind, "id": item_id, "status": "approved"})
                    ok_count += 1
                
                elif kind == "pending_change":
                    # Check current status
                    pc_row = s.execute(text("SELECT status FROM pending_changes WHERE id=:id"), {"id": item_id}).fetchone()
                    if not pc_row:
                        results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "not_found"}})
                        failed_count += 1
                        continue
                    
                    current_status = pc_row[0]
                    
                    if current_status == "approved":
                        # Idempotent (G3)
                        results.append({"kind": kind, "id": item_id, "status": "noop"})
                        ok_count += 1
                        continue
                    
                    if current_status != "pending":
                        # Stale state (G2)
                        results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "stale_state", "current": current_status}})
                        failed_count += 1
                        continue
                    
                    # TD-C3: WHERE-guard for race protection
                    result = s.execute(text("""
                        UPDATE pending_changes
                        SET status='approved', reviewed_by=:rev_by, reviewed_at=:rev_at
                        WHERE id=:id AND status='pending'
                    """), {"id": item_id, "rev_by": reviewer_id, "rev_at": datetime.now(timezone.utc)})
                    
                    # Check rowcount for idempotency
                    if result.rowcount == 0:
                        # Already approved/rejected → noop
                        results.append({"kind": kind, "id": item_id, "status": "noop"})
                        ok_count += 1
                        continue
                    
                    # TD-C5: Enhanced audit with payload_hash + actor
                    pc_after = s.execute(text("SELECT status, reviewed_by FROM pending_changes WHERE id=:id"), {"id": item_id}).fetchone()
                    payload_before = {"status": current_status, "reviewed_by": None}
                    payload_after = {"status": pc_after[0], "reviewed_by": pc_after[1]}
                    
                    hash_before = hashlib.sha256(json.dumps(payload_before, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    hash_after = hashlib.sha256(json.dumps(payload_after, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    
                    _audit("approve_pending_change", "pending_change", item_id, {
                        "status": "approved",
                        "payload_hash_before": hash_before,
                        "payload_hash_after": hash_after,
                        "actor_telegram_id": telegram_id,
                        "actor_role": "foreman"
                    }, s)
                    
                    results.append({"kind": kind, "id": item_id, "status": "approved"})
                    ok_count += 1
                
                else:
                    results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "unknown_kind"}})
                    failed_count += 1
            
            except Exception as e:
                results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "exception", "msg": str(e)}})
                failed_count += 1
        
        s.commit()
        
        # TD-C1: Enhanced metrics with counts breakdown
        record_metric("bot.inbox.approve", {
            "telegram_id": telegram_id,
            "items_count": len(items),
            "counts": {
                "ok": ok_count,
                "failed": failed_count,
                "noop": noop_count
            },
            "outcome": "success"
        })
        
        # Enrich response for bot DM logic (first expense only when single-item approval)
        enrich = {}
        try:
            if len(items) == 1 and items[0].get("kind") == "expense" and ok_count >= 1:
                exp_id = items[0]["id"]
                # Map expense.worker_id -> users.telegram_id (if any)
                row = s.execute(text("SELECT worker_id FROM expenses WHERE id=:id"), {"id": exp_id}).fetchone()
                if row and row[0]:
                    worker_id = row[0]
                    # Primary: map via users.id -> telegram_id (structured DB linkage)
                    trow = s.execute(text("SELECT telegram_id FROM users WHERE id=:uid"), {"uid": worker_id}).fetchone()
                    if trow and trow[0]:
                        enrich["worker_telegram_id"] = trow[0]
                    else:
                        # Fallback: heuristic mapping for worker_id like 'w<telegram_id>'
                        try:
                            if isinstance(worker_id, str) and worker_id.startswith(('w','W')):
                                cand = int(''.join(ch for ch in worker_id if ch.isdigit()))
                                if cand > 0:
                                    enrich["worker_telegram_id"] = cand
                        except Exception:
                            pass
        except Exception:
            pass
        resp = {"ok": ok_count, "failed": failed_count, "results": results}
        if enrich:
            resp.update(enrich)
        return resp
    
    except HTTPException:
        raise
    except Exception as e:
        s.rollback()
        record_metric("bot.inbox.approve", {"telegram_id": telegram_id, "outcome": "error", "error": str(e)})
        raise HTTPException(500, str(e))
    finally:
        s.close()


@app.post("/api/bot/reject")
def bot_reject(payload: dict):
    """
    Bulk reject items with reason.
    
    Request: {"telegram_id": 111, "items": [...], "reason": "photo missing"}
    Response: {"ok": N, "failed": M, "results": [{...}]}
    
    G1: Requires foreman role → 403 forbidden_role.
    G5: Audit log with review_reason.
    G6: Metrics logged (bot.inbox.reject).
    G7: Reason text stored in review_reason (not business logic).
    TD-C3: WHERE-guard with rowcount check.
    TD-C4: JSON validation (kind, id, limits).
    """
    telegram_id = payload.get("telegram_id")
    items = payload.get("items", [])
    reason = payload.get("reason", "rejected by foreman")
    
    # TD-C4: JSON validation
    if not telegram_id:
        raise HTTPException(422, {"code": "missing_telegram_id", "message": "telegram_id required"})
    
    if not items:
        raise HTTPException(400, {"code": "empty_items", "message": "items list cannot be empty"})
    
    if len(items) > 100:
        raise HTTPException(422, {"code": "too_many_items", "message": "items limit is 100"})
    
    # Validate each item kind/id upfront
    for item in items:
        kind = item.get("kind")
        item_id = item.get("id")
        
        if kind not in ["expense", "pending_change"]:
            raise HTTPException(422, {"code": "invalid_kind", "message": f"kind must be expense or pending_change, got {kind}"})
        
        if not item_id or item_id <= 0:
            raise HTTPException(422, {"code": "invalid_id", "message": "id must be positive integer"})
    
    s = SessionLocal()
    try:
        _check_foreman_role(s, telegram_id)
        
        # Get user_id for reviewed_by
        user_row = s.execute(text("SELECT id FROM users WHERE telegram_id=:tid"), {"tid": telegram_id}).fetchone()
        if not user_row:
            raise HTTPException(404, "user_not_found")
        
        reviewer_id = user_row[0]
        
        results = []
        ok_count = 0
        failed_count = 0
        noop_count = 0
        
        for item in items:
            kind = item.get("kind")
            item_id = item.get("id")
            
            if not kind or not item_id:
                results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "invalid_item"}})
                failed_count += 1
                continue
            
            try:
                if kind == "expense":
                    exp_row = s.execute(text("SELECT status FROM expenses WHERE id=:id"), {"id": item_id}).fetchone()
                    if not exp_row:
                        results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "not_found"}})
                        failed_count += 1
                        continue
                    
                    current_status = exp_row[0]
                    
                    if current_status == "rejected":
                        # Idempotent
                        results.append({"kind": kind, "id": item_id, "status": "noop"})
                        ok_count += 1
                        continue
                    
                    if current_status != "needs_approval":
                        results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "stale_state", "current": current_status}})
                        failed_count += 1
                        continue
                    
                    # TD-C3: WHERE-guard for race protection
                    result = s.execute(text("""
                        UPDATE expenses
                        SET status='rejected', reviewed_by=:rev_by, reviewed_at=:rev_at, review_reason=:reason
                        WHERE id=:id AND status='needs_approval'
                    """), {"id": item_id, "rev_by": reviewer_id, "rev_at": datetime.now(timezone.utc), "reason": reason})
                    
                    # Check rowcount for idempotency
                    if result.rowcount == 0:
                        # Already approved/rejected → noop
                        results.append({"kind": kind, "id": item_id, "status": "noop"})
                        noop_count += 1
                        ok_count += 1
                        continue
                    
                    # TD-C5: Enhanced audit with payload_hash + actor
                    exp_after = s.execute(text("SELECT status, reviewed_by, review_reason FROM expenses WHERE id=:id"), {"id": item_id}).fetchone()
                    payload_before = {"status": current_status, "reviewed_by": None, "review_reason": None}
                    payload_after = {"status": exp_after[0], "reviewed_by": exp_after[1], "review_reason": exp_after[2]}
                    
                    hash_before = hashlib.sha256(json.dumps(payload_before, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    hash_after = hashlib.sha256(json.dumps(payload_after, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    
                    _audit("reject_expense", "expense", item_id, {
                        "status": "rejected",
                        "reason": reason,
                        "payload_hash_before": hash_before,
                        "payload_hash_after": hash_after,
                        "actor_telegram_id": telegram_id,
                        "actor_role": "foreman"
                    }, s)
                    
                    results.append({"kind": kind, "id": item_id, "status": "rejected"})
                    ok_count += 1
                
                elif kind == "pending_change":
                    pc_row = s.execute(text("SELECT status FROM pending_changes WHERE id=:id"), {"id": item_id}).fetchone()
                    if not pc_row:
                        results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "not_found"}})
                        failed_count += 1
                        continue
                    
                    current_status = pc_row[0]
                    
                    if current_status == "rejected":
                        # Idempotent
                        results.append({"kind": kind, "id": item_id, "status": "noop"})
                        ok_count += 1
                        continue
                    
                    if current_status != "pending":
                        results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "stale_state", "current": current_status}})
                        failed_count += 1
                        continue
                    
                    # TD-C3: WHERE-guard for race protection
                    result = s.execute(text("""
                        UPDATE pending_changes
                        SET status='rejected', reviewed_by=:rev_by, reviewed_at=:rev_at, review_reason=:reason
                        WHERE id=:id AND status='pending'
                    """), {"id": item_id, "rev_by": reviewer_id, "rev_at": datetime.now(timezone.utc), "reason": reason})
                    
                    # Check rowcount for idempotency
                    if result.rowcount == 0:
                        # Already approved/rejected → noop
                        results.append({"kind": kind, "id": item_id, "status": "noop"})
                        noop_count += 1
                        ok_count += 1
                        continue
                    
                    # TD-C5: Enhanced audit with payload_hash + actor
                    pc_after = s.execute(text("SELECT status, reviewed_by, review_reason FROM pending_changes WHERE id=:id"), {"id": item_id}).fetchone()
                    payload_before = {"status": current_status, "reviewed_by": None, "review_reason": None}
                    payload_after = {"status": pc_after[0], "reviewed_by": pc_after[1], "review_reason": pc_after[2]}
                    
                    hash_before = hashlib.sha256(json.dumps(payload_before, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    hash_after = hashlib.sha256(json.dumps(payload_after, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    
                    _audit("reject_pending_change", "pending_change", item_id, {
                        "status": "rejected",
                        "reason": reason,
                        "payload_hash_before": hash_before,
                        "payload_hash_after": hash_after,
                        "actor_telegram_id": telegram_id,
                        "actor_role": "foreman"
                    }, s)
                    
                    results.append({"kind": kind, "id": item_id, "status": "rejected"})
                    ok_count += 1
                
                else:
                    results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "unknown_kind"}})
                    failed_count += 1
            
            except Exception as e:
                results.append({"kind": kind, "id": item_id, "status": "error", "error": {"code": "exception", "msg": str(e)}})
                failed_count += 1
        
        s.commit()
        
        # TD-C1: Enhanced metrics with counts breakdown
        record_metric("bot.inbox.reject", {
            "telegram_id": telegram_id,
            "items_count": len(items),
            "counts": {
                "ok": ok_count,
                "failed": failed_count,
                "noop": noop_count
            },
            "reason": reason,
            "outcome": "success"
        })
        
        return {"ok": ok_count, "failed": failed_count, "results": results}
    
    except HTTPException:
        raise
    except Exception as e:
        s.rollback()
        record_metric("bot.inbox.reject", {"telegram_id": telegram_id, "outcome": "error", "error": str(e)})
        raise HTTPException(500, str(e))
    finally:
        s.close()


@app.get("/api/bot/item.details", response_model=ItemDetailsOut)
def bot_item_details(kind: str, id: int):
    """
    G3 API Details: Get deterministic item details with pricing breakdown.
    
    Skeptic Mode endpoint with:
    - Deterministic pricing steps (base → modifiers in alphabetical order)
    - ILS-only currency enforcement
    - Rules version and SHA pinning
    - Pricing SHA for reproducibility verification
    - OCR status block
    
    Query params:
        kind: "task" or "expense"
        id: Item ID
    
    Returns:
        ItemDetailsOut with steps, total, rules metadata, OCR block, formatted total
    
    Raises:
        HTTPException: 404 if not found, 422 if kind invalid
    """
    import hashlib
    
    if kind not in ["task", "expense"]:
        record_metric("bot.item.details", {"kind": kind, "id": id, "outcome": "invalid_kind"})
        raise HTTPException(422, f"kind must be task or expense, got {kind}")
    
    s = SessionLocal()
    try:
        # Get pricing breakdown from explain_* helpers
        if kind == "task":
            steps_raw, total, rules_version, rules_sha = explain_task(id, s)
        else:  # expense
            steps_raw, total, rules_version, rules_sha = explain_expense(id, s)
        
        # Convert raw steps to PricingStep schema
        steps = [
            PricingStep(
                step=st["step"],
                yaml_key=st["yaml_key"],
                value=st["value"],
                note=st.get("note")
            )
            for st in steps_raw
        ]
        
        # Compute pricing_sha (canonical string)
        step_parts = [f"{s.yaml_key}:{s.value:.2f}" for s in steps]
        canonical = f"{rules_sha}|{rules_version}|{kind}|{id}|{','.join(step_parts)}|{total:.2f}"
        pricing_sha = hashlib.sha256(canonical.encode()).hexdigest()[:12]
        
        # Build OCR block
        # For tasks: OCR always disabled
        # For expenses: check if OCR was run (from expenses.ocr_text)
        ocr_enabled = False
        ocr_status = "off"
        ocr_confidence = None
        
        if kind == "expense":
            ocr_row = s.execute(
                text("SELECT ocr_text FROM expenses WHERE id=:id"),
                {"id": id}
            ).fetchone()
            
            if ocr_row and ocr_row[0]:
                # Try to parse OCR metadata
                try:
                    ocr_data = json.loads(ocr_row[0])
                    if isinstance(ocr_data, dict):
                        ocr_enabled = True
                        if ocr_data.get("abstain"):
                            ocr_status = "abstain"
                        else:
                            ocr_status = "ok"
                        ocr_confidence = ocr_data.get("confidence")
                except:
                    pass
        
        ocr_block = OcrBlock(
            enabled=ocr_enabled,
            status=ocr_status,
            confidence=ocr_confidence
        )
        
        # Format total via fmt_money - D1: wrap in ensure_decimal
        fmt_total = fmt_money(ensure_decimal(total), "ILS")
        
        # Record metric
        record_metric("bot.item.details", {
            "kind": kind,
            "id": id,
            "rules_sha": rules_sha,
            "pricing_sha": pricing_sha,
            "outcome": "success"
        })
        
        return ItemDetailsOut(
            id=id,
            kind=kind,
            currency="ILS",
            steps=steps,
            total=total,
            rules_version=rules_version,
            rules_sha=rules_sha,
            pricing_sha=pricing_sha,
            ocr=ocr_block,
            fmt_total=fmt_total
        )
    
    except PricingError as e:
        record_metric("bot.item.details", {"kind": kind, "id": id, "outcome": "not_found"})
        raise HTTPException(404, str(e))
    except HTTPException:
        raise
    except Exception as e:
        record_metric("bot.item.details", {"kind": kind, "id": id, "outcome": "error", "error": str(e)})
        raise HTTPException(500, str(e))
    finally:
        s.close()


# --- E2: HTMX Admin Invoice Views ---

# Jinja2 template for invoice page
INVOICE_PAGE = Template("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Invoice #{{ id }}</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #333; }
        hr { margin: 30px 0; border: 1px solid #ddd; }
        form { margin: 20px 0; }
        input { padding: 8px; margin: 0 5px; border: 1px solid #ccc; border-radius: 4px; }
        button { padding: 8px 16px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #0056b3; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 10px; text-align: left; border: 1px solid #ddd; }
        th { background: #f4f4f4; font-weight: bold; }
        .preview { background: #f9f9f9; padding: 20px; border-radius: 4px; margin: 20px 0; }
        .loading { color: #666; font-style: italic; }
    </style>
</head>
<body>
<div class="container">
  <h1>Invoice #{{ id }}</h1>
  
  <div class="preview" hx-get="/admin/invoices/{{ id }}/preview" hx-trigger="load" hx-swap="innerHTML">
    <div class="loading">Loading preview…</div>
  </div>
  
  <hr/>
  
  <h2>Version Diff</h2>
  <form hx-get="/admin/invoices/{{ id }}/diff" hx-target="#diff" hx-swap="innerHTML">
    <label>From version: <input name="from" value="v1" placeholder="v1"/></label>
    <label>To version: <input name="to" value="v2" placeholder="v2"/></label>
    <button type="submit">Show Diff</button>
  </form>
  
  <div id="diff" style="margin-top: 20px;">
    <p class="loading">Diff will appear here after form submission…</p>
  </div>
</div>
</body>
</html>
""")


@app.get("/admin/invoices/{invoice_id}", response_class=HTMLResponse, dependencies=[Depends(admin_guard)])
def admin_invoice_page(invoice_id: int):
    """
    Admin invoice page with HTMX-based preview and diff.
    
    Args:
        invoice_id: Invoice ID to display
        
    Returns:
        HTML page with embedded HTMX components
    """
    return INVOICE_PAGE.render(id=invoice_id)


@app.get("/admin/invoices/{invoice_id}/preview", response_class=HTMLResponse, dependencies=[Depends(admin_guard)])
def admin_invoice_preview(invoice_id: int, session = Depends(lambda: SessionLocal())):
    """
    Invoice preview fragment (HTMX partial).
    
    Args:
        invoice_id: Invoice ID
        session: Database session (dependency injection)
        
    Returns:
        HTML fragment with invoice preview
    """
    try:
        # Collect invoice data
        context = collect_invoice_data(session, invoice_id)
        
        # Render HTML preview (reuse docgen_html)
        html = render_html(context, out_dir="exports")
        
        # Read generated HTML file
        import os
        html_path = os.path.join("exports", f"invoice_{invoice_id}.html")
        if os.path.exists(html_path):
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            return html_content
        else:
            # Fallback: inline minimal HTML
            return f"<div><strong>Invoice #{invoice_id}</strong><br/>Preview generation in progress…</div>"
            
    except Exception as e:
        return f"<div style='color: red;'>Error loading preview: {str(e)}</div>"
    finally:
        session.close()


@app.get("/admin/invoices/{invoice_id}/diff", response_class=HTMLResponse, dependencies=[Depends(admin_guard)])
def admin_invoice_diff_html(
    invoice_id: int,
    from_: str = Query("v1", alias="from"),
    to: str = Query("v2", alias="to"),
    session = Depends(lambda: SessionLocal())
):
    """
    Invoice diff fragment (HTMX partial).
    
    Args:
        invoice_id: Invoice ID
        from_: Source version (e.g., 'v1')
        to: Target version (e.g., 'v2')
        session: Database session
        
    Returns:
        HTML table with changes
    """
    try:
        # Parse versions
        try:
            v_from = int(from_.lstrip("v"))
            v_to = int(to.lstrip("v"))
        except Exception:
            return "<div style='color: red;'>Invalid version format. Use v1, v2, etc.</div>"
        
        # Fetch versions
        p_from = _fetch_invoice_version(session, invoice_id, v_from)
        p_to = _fetch_invoice_version(session, invoice_id, v_to)
        
        if not p_from or not p_to:
            return f"<div style='color: red;'>Version not found (from={from_}, to={to})</div>"
        
        # Generate diff
        changes = _diff_payload(p_from, p_to)
        
        # Audit
        _audit("diff.view.html", "invoice", invoice_id, {"from": v_from, "to": v_to}, session)
        session.commit()
        
        # Record metric
        record_metric("diff.view.html", {"invoice_id": invoice_id, "from": v_from, "to": v_to})
        
        # Build HTML table
        if not changes:
            return "<p><em>No changes detected between versions.</em></p>"
        
        rows_html = ""
        for change in changes:
            path = change.get("path", "")
            old = change.get("old", "")
            new = change.get("new", "")
            rows_html += f"<tr><td>{path}</td><td>{old}</td><td>{new}</td></tr>"
        
        total_old = p_from.get("total", "")
        total_new = p_to.get("total", "")
        
        html = f"""
        <table>
            <thead>
                <tr>
                    <th>Field</th>
                    <th>Old ({from_})</th>
                    <th>New ({to})</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
                <tr style="font-weight: bold; background: #f0f0f0;">
                    <td>Total</td>
                    <td>{total_old}</td>
                    <td>{total_new}</td>
                </tr>
            </tbody>
        </table>
        <p style="color: #666; font-size: 0.9em;">
            {len(changes)} change(s) detected.
        </p>
        """
        
        return html
        
    except Exception as e:
        return f"<div style='color: red;'>Error generating diff: {str(e)}</div>"
    finally:
        session.close()


# ========== E3: Admin Metrics Dashboard ==========
from pathlib import Path
from fastapi.templating import Jinja2Templates
from metrics_rollup import compute_rollup

templates = Jinja2Templates(directory="templates")


@app.get("/admin/metrics", response_class=HTMLResponse, dependencies=[Depends(admin_guard)])
async def admin_metrics_page(request: Request):
    """
    Admin Metrics Dashboard (E3).
    
    Protected: Requires X-Admin-Secret header.
    
    Returns:
        HTML page with HTMX auto-refresh table (every 5s).
    """
    return templates.TemplateResponse("admin_metrics.html", {"request": request})


@app.get("/admin/metrics/table", response_class=HTMLResponse, dependencies=[Depends(admin_guard)])
async def admin_metrics_table(window: str = Query("1h", regex="^(15m|1h|24h)$")):
    """
    Metrics table fragment (HTMX partial).
    
    Args:
        window: Time window (15m, 1h, 24h)
        
    Returns:
        HTML <table> fragment with metrics rollup.
    """
    start = datetime.now(timezone.utc)
    
    try:
        metrics_file = _logs_dir() / "api.jsonl"
        
        # Compute rollup
        rollup = compute_rollup(metrics_file, window=window, max_tail_lines=20000)
        
        # Render template
        template = templates.get_template("metrics_table.html")
        html = template.render(rows=rollup["rows"])
        
        # Record metric
        latency_ms = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        record_metric(
            kind="admin.metrics.render",
            fields={"window": window, "row_count": len(rollup["rows"])},
            latency_ms=latency_ms
        )
        
        return html
        
    except FileNotFoundError:
        # No metrics file yet
        template = templates.get_template("metrics_table.html")
        return template.render(rows=[])
    except Exception as e:
        return f'<div class="no-data" style="color: red;">Error: {str(e)}</div>'


@app.get("/api/admin/metrics.rollup", dependencies=[Depends(admin_guard)])
async def admin_metrics_rollup_json(window: str = Query("1h", regex="^(15m|1h|24h)$")):
    """
    JSON metrics rollup API (optional E3 endpoint).
    
    Args:
        window: Time window (15m, 1h, 24h)
        
    Returns:
        JSON rollup data.
    """
    try:
        metrics_file = _logs_dir() / "api.jsonl"
        rollup = compute_rollup(metrics_file, window=window, max_tail_lines=20000)
        return rollup
    except FileNotFoundError:
        return {"window": window, "generated_at": datetime.now(timezone.utc).isoformat(), "rows": []}


# ========================================
# Settings API (F1 v1.0 addition)
# ========================================

@app.get("/api/settings/general")
def settings_general(
    admin: dict = Depends(get_current_admin),  # F4.5: JWT auth for Settings (like Expenses/Invoices)
):
    """
    // API CHANGE: Added for F1 Settings (v1.0).
    // F4.5 FIX: Replaced admin_guard with get_current_admin for JWT support.
    
    Returns general system settings (read-only for MVP).
    
    Future enhancement: Add PUT endpoint for editing.
    
    Returns:
        General settings (company name, timezone, contact email)
    """
    # For MVP: hardcoded/env-based values (no DB table yet)
    return {
        "company_name": os.getenv("COMPANY_NAME", "TelegramOllama Work Ledger"),
        "timezone": os.getenv("TIMEZONE", "Asia/Jerusalem"),
        "contact_email": os.getenv("CONTACT_EMAIL", "admin@example.com"),
        "editable": False,  # Flag for frontend
        "note": "Edit via environment variables (v1.0 limitation)"
    }


@app.get("/api/settings/backup")
def settings_backup_status(
    admin: dict = Depends(get_current_admin),  # F4.5: JWT auth
):
    """
    // API CHANGE: Added for F1 Settings (v1.0).
    
    Returns backup status (last backup timestamp).
    
    Returns:
        Backup metadata (last_backup_at or null if never)
    """
    # For MVP: check if backup directory exists and find latest file
    backup_dir = Path("./backups")
    
    if not backup_dir.exists():
        return {
            "last_backup_at": None,
            "backup_count": 0,
            "note": "No backups directory found"
        }
    
    backup_files = list(backup_dir.glob("*.db"))
    
    if not backup_files:
        return {
            "last_backup_at": None,
            "backup_count": 0,
            "note": "No backup files found"
        }
    
    # Get most recent backup by modification time
    latest_backup = max(backup_files, key=lambda f: f.stat().st_mtime)
    last_modified = datetime.fromtimestamp(latest_backup.stat().st_mtime, tz=timezone.utc)
    
    return {
        "last_backup_at": last_modified.isoformat(),
        "backup_count": len(backup_files),
        "latest_file": latest_backup.name
    }


@app.post("/api/settings/backup/create")
def settings_backup_create(
    admin: dict = Depends(get_current_admin),  # F4.5: JWT auth
):
    """
    // API CHANGE: Added for F1 Settings (v1.0).
    
    Creates a new database backup.
    
    Returns:
        Backup creation result with timestamp and filename
    """
    import shutil
    
    # Ensure backup directory exists
    backup_dir = Path("./backups")
    backup_dir.mkdir(exist_ok=True)
    
    # Generate timestamp-based filename
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.db"
    backup_path = backup_dir / backup_filename
    
    # Source database path
    db_path = Path("./api/data/shifts.db")
    
    if not db_path.exists():
        raise HTTPException(404, {"error": "db_not_found", "message": "Database file not found"})
    
    try:
        # Copy database file
        shutil.copy2(db_path, backup_path)
        
        # Verify backup
        if not backup_path.exists():
            raise HTTPException(500, {"error": "backup_failed", "message": "Backup file was not created"})
        
        backup_size = backup_path.stat().st_size
        
        return {
            "success": True,
            "filename": backup_filename,
            "size_bytes": backup_size,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    
    except Exception as e:
        raise HTTPException(500, {"error": "backup_error", "message": f"Backup failed: {str(e)}"})


@app.get("/api/settings/system")
def settings_system_info(
    admin: dict = Depends(get_current_admin),  # F4.5: JWT auth
):
    """
    // API CHANGE: Added for F1 Settings (v1.0).
    // F4.5 FIX: Replaced admin_guard with get_current_admin for JWT support.
    
    Returns system information (versions, integrations status).
    
    Returns:
        System metadata (API version, bot status, DB info)
    """
    # API version (from git or hardcoded)
    api_version = os.getenv("API_VERSION", "1.2.0")
    
    # Bot version (from bot code if available)
    bot_version = os.getenv("BOT_VERSION", "1.2.0")
    
    # Web UI version (from package.json if accessible)
    web_version = "1.0.0"  # Hardcoded for MVP
    
    # Database info
    db_path = Path("./api/data/shifts.db")
    db_exists = db_path.exists()
    db_size = db_path.stat().st_size if db_exists else 0
    
    # Telegram bot status (basic check: try to import bot config)
    bot_status = "unknown"
    try:
        bot_token = os.getenv("BOT_TOKEN")
        bot_status = "configured" if bot_token else "not_configured"
    except Exception:
        bot_status = "error"
    
    return {
        "versions": {
            "api": api_version,
            "bot": bot_version,
            "web_ui": web_version
        },
        "database": {
            "exists": db_exists,
            "size_bytes": db_size,
            "size_mb": round(db_size / (1024 * 1024), 2) if db_exists else 0,
            "path": "./api/data/shifts.db"
        },
        "integrations": {
            "telegram_bot": {
                "status": bot_status,
                "note": "Check BOT_TOKEN env variable"
            },
            "sqlite": {
                "status": "active" if db_exists else "missing",
                "note": "Local-first architecture"
            }
        },
        "platform": {
            "os": platform.system(),
            "python": platform.python_version()
        },
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


# ========================================
# Dashboard API (F1 v1.0 addition)
# ========================================

@app.get("/api/dashboard/summary", dependencies=[Depends(admin_guard)])
def dashboard_summary(period_days: int = Query(7, ge=1, le=365)):
    """
    // API CHANGE: Added for F1 Dashboard (v1.0).
    
    Returns aggregated KPIs for Dashboard:
    - Active shifts (currently open)
    - Total expenses (sum for period)
    - Total invoices paid (sum for period)
    - Pending moderation items count
    
    Args:
        period_days: Number of days to aggregate (default: 7, max: 365)
        
    Returns:
        DashboardSummary with KPIs and period metadata
    """
    with SessionLocal() as s:
        # Calculate cutoff date for period
        cutoff = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()
        
        # KPI 1: Active shifts (open status, no ended_at)
        active_shifts = s.execute(
            text("SELECT COUNT(*) FROM shifts WHERE status='open' AND ended_at IS NULL")
        ).scalar() or 0
        
        # KPI 2: Total expenses (sum amount for period)
        total_expenses = s.execute(
            text("SELECT SUM(amount) FROM expenses WHERE date >= :cutoff"),
            {"cutoff": cutoff}
        ).scalar() or Decimal("0")
        
        # KPI 3: Total invoices paid (sum total for paid invoices in period)
        total_invoices_paid = s.execute(
            text("""
                SELECT SUM(total) FROM invoices 
                WHERE status='paid' AND date_from >= :cutoff
            """),
            {"cutoff": cutoff}
        ).scalar() or Decimal("0")
        
        # KPI 4: Pending moderation items
        pending_count = s.execute(
            text("SELECT COUNT(*) FROM pending_changes WHERE status='pending'")
        ).scalar() or 0
        
        # Return structured response
        return {
            "period_days": period_days,
            "cutoff_date": cutoff[:10],  # ISO date only
            "active_shifts": active_shifts,
            "total_expenses": float(total_expenses),  # Convert Decimal for JSON
            "total_invoices_paid": float(total_invoices_paid),
            "pending_items": pending_count,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }


@app.get("/api/dashboard/timeseries", dependencies=[Depends(admin_guard)])
def dashboard_timeseries(
    period_days: int = Query(30, ge=7, le=365),
    metric: str = Query("expenses", regex="^(expenses|invoices)$")
):
    """
    // API CHANGE: Added for F1 Dashboard (v1.0).
    
    Returns time-series data for Dashboard charts.
    
    Args:
        period_days: Number of days to show (default: 30, max: 365)
        metric: Which metric to return ("expenses" or "invoices")
        
    Returns:
        Array of {date: "YYYY-MM-DD", value: number} objects
    """
    with SessionLocal() as s:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=period_days)).date().isoformat()
        
        if metric == "expenses":
            # Aggregate expenses by date
            rows = s.execute(
                text("""
                    SELECT DATE(date) as d, SUM(amount) as total
                    FROM expenses
                    WHERE date >= :cutoff
                    GROUP BY DATE(date)
                    ORDER BY d ASC
                """),
                {"cutoff": cutoff}
            ).fetchall()
            
            return [{"date": str(row[0]), "value": float(row[1] or 0)} for row in rows]
        
        else:  # invoices
            # Aggregate invoices by date_from
            rows = s.execute(
                text("""
                    SELECT DATE(date_from) as d, SUM(total) as total
                    FROM invoices
                    WHERE date_from >= :cutoff
                    GROUP BY DATE(date_from)
                    ORDER BY d ASC
                """),
                {"cutoff": cutoff}
            ).fetchall()
            
            return [{"date": str(row[0]), "value": float(row[1] or 0)} for row in rows]


@app.get("/api/dashboard/recent", dependencies=[Depends(admin_guard)])
def dashboard_recent(
    resource: str = Query("expenses", regex="^(expenses|invoices|tasks)$"),
    limit: int = Query(5, ge=1, le=20)
):
    """
    // API CHANGE: Added for F1 Dashboard (v1.0).
    
    Returns recent items for Dashboard "Recent Activity" block.
    
    Args:
        resource: Which resource ("expenses", "invoices", "tasks")
        limit: Max items to return (default: 5, max: 20)
        
    Returns:
        Array of recent items with id, summary, date, amount
    """
    with SessionLocal() as s:
        if resource == "expenses":
            rows = s.execute(
                text("""
                    SELECT id, worker, category, amount, date, created_at
                    FROM expenses
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"lim": limit}
            ).fetchall()
            
            return [{
                "id": row[0],
                "type": "expense",
                "summary": f"{row[1]} - {row[2]}",  # worker - category
                "amount": float(row[3]),
                "date": str(row[4]),
                "created_at": str(row[5])
            } for row in rows]
        
        elif resource == "invoices":
            rows = s.execute(
                text("""
                    SELECT i.id, c.name, i.total, i.status, i.date_from, i.created_at
                    FROM invoices i
                    LEFT JOIN clients c ON i.client_id = c.id
                    ORDER BY i.created_at DESC
                    LIMIT :lim
                """),
                {"lim": limit}
            ).fetchall()
            
            return [{
                "id": row[0],
                "type": "invoice",
                "summary": f"{row[1] or 'Unknown Client'} - {row[3]}",  # client - status
                "amount": float(row[2] or 0),
                "date": str(row[4]),
                "created_at": str(row[5])
            } for row in rows]
        
        else:  # tasks
            rows = s.execute(
                text("""
                    SELECT id, worker, description, amount, date, created_at
                    FROM tasks
                    ORDER BY created_at DESC
                    LIMIT :lim
                """),
                {"lim": limit}
            ).fetchall()
            
            return [{
                "id": row[0],
                "type": "task",
                "summary": f"{row[1]} - {row[2][:30]}...",  # worker - truncated description
                "amount": float(row[3]),
                "date": str(row[4]),
                "created_at": str(row[5])
            } for row in rows]


# ══════════════════════════════════════════════════════════════════════════════
# SPA MOUNT (MUST BE LAST!)
# ══════════════════════════════════════════════════════════════════════════════
# Web interface (SPA) — mounted at "/" to serve React app
# CRITICAL: API routes (/api/*) are registered BEFORE this section
WEB_DIR = Path(__file__).parent / "web" / "dist"  # Production build directory
WEB_DIR.mkdir(exist_ok=True, parents=True)  # Create if doesn't exist (for tests)

# SPA fallback function (will be registered manually AFTER all routers)
async def serve_spa(request: Request):
    """
    Catch-all for SPA routing.
    - Serves static files from dist/ if they exist
    - Falls back to index.html for client-side routes
    """
    # Extract path from request
    full_path = request.path_params.get("full_path", "")
    
    # Try to serve file if it exists
    file_path = WEB_DIR / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    
    # Fallback to index.html for SPA routing
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    
    # If index.html missing, return error
    raise HTTPException(status_code=404, detail="SPA not built")

# Register SPA catch-all route AFTER all API routers
from starlette.routing import Route
app.router.routes.append(
    Route("/{full_path:path}", endpoint=serve_spa, methods=["GET"], include_in_schema=False)
)












