"""Telegram Bot Menu Management Endpoints (Admin only)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, List
import json

from db import SessionLocal
from schemas_bot_menu import (
    BotCommandConfig,
    BotMenuResponse,
    UpdateBotMenuRequest,
    UpdateBotCommandPayload,
    ApplyBotMenuResponse,
)
from models_users import UserRole
from utils.audit import record_metric


router = APIRouter(prefix="/api/admin", tags=["Bot Menu Management"])


# --- Dependency: Admin Guard ---
def admin_guard():
    """Placeholder admin guard (integrate with existing auth)."""
    # TODO: Replace with actual admin auth dependency from main.py
    # For now, assume caller is admin
    pass


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Helper Functions ---

def _get_menu_config(db: Session):
    """Fetch current menu config metadata (version, timestamps)."""
    row = db.execute(text("SELECT version, last_updated_at, last_updated_by, last_applied_at, last_applied_by FROM bot_menu_config WHERE id = 1")).fetchone()
    if not row:
        # Initialize if missing
        db.execute(text("INSERT OR IGNORE INTO bot_menu_config (id, version) VALUES (1, 1)"))
        db.commit()
        return {"version": 1, "last_updated_at": None, "last_updated_by": None, "last_applied_at": None, "last_applied_by": None}
    
    return {
        "version": row[0],
        "last_updated_at": datetime.fromisoformat(row[1]) if row[1] else None,
        "last_updated_by": row[2],
        "last_applied_at": datetime.fromisoformat(row[3]) if row[3] else None,
        "last_applied_by": row[4],
    }


def _get_commands_by_role(db: Session) -> Dict[str, List[BotCommandConfig]]:
    """Fetch all commands grouped by role."""
    rows = db.execute(text("""
        SELECT id, role, command_key, telegram_command, label, description,
               enabled, is_core, position, command_type
        FROM bot_commands
        ORDER BY role, position, id
    """)).fetchall()
    
    commands_by_role: Dict[str, List[BotCommandConfig]] = {
        "admin": [],
        "foreman": [],
        "worker": [],
    }
    
    for row in rows:
        cmd = BotCommandConfig(
            id=row[0],
            role=row[1],
            command_key=row[2],
            telegram_command=row[3],
            label=row[4],
            description=row[5],
            enabled=bool(row[6]),
            is_core=bool(row[7]),
            position=row[8],
            command_type=row[9],
        )
        commands_by_role[cmd.role].append(cmd)
    
    return commands_by_role


def _increment_version(db: Session, updated_by: str):
    """Increment version and update metadata."""
    db.execute(text("""
        UPDATE bot_menu_config
        SET version = version + 1,
            last_updated_at = datetime('now'),
            last_updated_by = :user
        WHERE id = 1
    """), {"user": updated_by})


def _validate_and_update_command(db: Session, payload: UpdateBotCommandPayload, admin_username: str):
    """Validate and update a single command. Raises HTTPException on error."""
    # Fetch current command
    row = db.execute(text("SELECT is_core, enabled, label, position FROM bot_commands WHERE id = :id"), {"id": payload.id}).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "command_not_found", "command_id": payload.id}
        )
    
    is_core, current_enabled, current_label, current_position = row
    
    # Validation: Core commands cannot be disabled
    if is_core and not payload.enabled:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "cannot_disable_core",
                "field": f"commands[{payload.id}].enabled",
                "message": "Core commands cannot be disabled"
            }
        )
    
    # Check if any changes
    if (payload.label == current_label and
        payload.enabled == current_enabled and
        payload.position == current_position):
        return  # No changes, skip update
    
    # Update command
    db.execute(text("""
        UPDATE bot_commands
        SET label = :label,
            enabled = :enabled,
            position = :position,
            updated_at = datetime('now')
        WHERE id = :id
    """), {
        "id": payload.id,
        "label": payload.label,
        "enabled": payload.enabled,
        "position": payload.position,
    })


# --- Endpoints ---

@router.get("/bot-menu", response_model=BotMenuResponse, dependencies=[Depends(admin_guard)])
def get_bot_menu(db: Session = Depends(get_db)):
    """
    GET /api/admin/bot-menu
    
    Returns current Telegram bot menu configuration by role.
    
    **RBAC**: Admin only
    
    **Response**:
    - `version`: Config version (increments on each save)
    - `last_updated_at`: Last save timestamp
    - `last_updated_by`: Admin username who saved
    - `last_applied_at`: Last apply to bot timestamp (None if never applied)
    - `last_applied_by`: Admin who applied
    - `roles`: Commands grouped by role (admin/foreman/worker)
    """
    try:
        config = _get_menu_config(db)
        commands_by_role = _get_commands_by_role(db)
        
        return BotMenuResponse(
            version=config["version"],
            last_updated_at=config["last_updated_at"] or datetime.utcnow(),
            last_updated_by=config["last_updated_by"],
            last_applied_at=config["last_applied_at"],
            last_applied_by=config["last_applied_by"],
            roles=commands_by_role,
        )
    except Exception as e:
        record_metric("bot_menu.get.error", {"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "failed_to_fetch_menu", "message": str(e)}
        )


@router.put("/bot-menu", response_model=BotMenuResponse, dependencies=[Depends(admin_guard)])
def update_bot_menu(
    request: UpdateBotMenuRequest,
    db: Session = Depends(get_db),
    admin_username: str = "admin"  # TODO: Extract from auth token
):
    """
    PUT /api/admin/bot-menu
    
    Updates Telegram bot menu configuration.
    
    **RBAC**: Admin only
    
    **Request**:
    - `version`: Current version client is editing (optimistic locking)
    - `roles`: Commands to update, grouped by role
    
    **Validations**:
    - Version must match current DB version (409 Conflict if stale)
    - Core commands cannot be disabled (422 if attempted)
    - Label min/max length (422 if invalid)
    
    **Side Effects**:
    - Increments version
    - Updates `last_updated_at` and `last_updated_by`
    - **Does NOT apply to Telegram bot** (use POST /bot-menu/apply for that)
    
    **Response**: Updated menu configuration
    """
    try:
        # Step 1: Check version (optimistic locking)
        current_config = _get_menu_config(db)
        if request.version != current_config["version"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "version_conflict",
                    "message": "Menu was updated by another admin. Please reload.",
                    "current_version": current_config["version"],
                    "your_version": request.version,
                }
            )
        
        # Step 2: Validate and update each command
        updated_count = 0
        for role, commands in request.roles.items():
            for payload in commands:
                _validate_and_update_command(db, payload, admin_username)
                updated_count += 1
        
        # Step 3: Increment version
        _increment_version(db, admin_username)
        db.commit()
        
        # Step 4: Return updated menu
        record_metric("bot_menu.update.success", {"updated_count": updated_count, "admin": admin_username})
        
        config = _get_menu_config(db)
        commands_by_role = _get_commands_by_role(db)
        
        return BotMenuResponse(
            version=config["version"],
            last_updated_at=config["last_updated_at"] or datetime.utcnow(),
            last_updated_by=config["last_updated_by"],
            last_applied_at=config["last_applied_at"],
            last_applied_by=config["last_applied_by"],
            roles=commands_by_role,
        )
    
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        record_metric("bot_menu.update.error", {"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "failed_to_update_menu", "message": str(e)}
        )


@router.post("/bot-menu/apply", response_model=ApplyBotMenuResponse, dependencies=[Depends(admin_guard)])
def apply_bot_menu(
    db: Session = Depends(get_db),
    admin_username: str = "admin"  # TODO: Extract from auth token
):
    """
    POST /api/admin/bot-menu/apply
    
    Applies current bot menu configuration to Telegram bot.
    
    **RBAC**: Admin only
    
    **Side Effects**:
    - Calls `bot.menu_sync.apply_bot_menu()` to update Telegram commands
    - Updates `last_applied_at` and `last_applied_by` on success
    
    **Response**:
    - `success`: True if commands applied successfully
    - `applied_at`: Timestamp of apply
    - `details`: Success/error message
    """
    try:
        # Import bot integration module
        try:
            from bot.menu_sync import apply_bot_menu as sync_apply_bot_menu
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail={
                    "error": "bot_sync_not_available",
                    "message": "Bot menu sync module not found. Ensure bot is running."
                }
            )
        
        # Apply menu to Telegram bot
        result = sync_apply_bot_menu(db)
        
        if result["success"]:
            # Update last_applied metadata
            db.execute(text("""
                UPDATE bot_menu_config
                SET last_applied_at = datetime('now'),
                    last_applied_by = :user
                WHERE id = 1
            """), {"user": admin_username})
            db.commit()
            
            record_metric("bot_menu.apply.success", {"admin": admin_username})
            
            return ApplyBotMenuResponse(
                success=True,
                applied_at=datetime.utcnow(),
                details=result.get("details", "Bot menu updated successfully")
            )
        else:
            record_metric("bot_menu.apply.error", {"error": result.get("details", "Unknown error")})
            return ApplyBotMenuResponse(
                success=False,
                applied_at=None,
                details=result.get("details", "Failed to apply menu to bot")
            )
    
    except HTTPException:
        raise
    except Exception as e:
        record_metric("bot_menu.apply.exception", {"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "apply_failed", "message": str(e)}
        )
