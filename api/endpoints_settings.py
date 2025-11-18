"""Settings endpoints (General, Backup, System Info).

F5.1: Created as stub to support Web UI Settings page (General/Backup/System tabs).
Bot Menu removed from SettingsPage → will be separate page/endpoint.
"""
from fastapi import APIRouter, Depends
from deps_auth import get_current_admin
from config import settings
import platform
import sys
import os
from datetime import datetime
from glob import glob

router = APIRouter()


@router.get("/api/settings/general")
async def get_general_settings(_=Depends(get_current_admin)):
    """General settings (read-only)."""
    return {
        "company_name": getattr(settings, 'COMPANY_NAME', 'TelegramOllama'),
        "timezone": "Asia/Jerusalem",  # ILS default
        "contact_email": getattr(settings, 'ADMIN_EMAIL', 'admin@example.com'),
        "editable": False,
        "note": "Для изменения настроек отредактируйте переменные окружения (config.py или .env)",
    }


@router.get("/api/settings/backup")
async def get_backup_status(_=Depends(get_current_admin)):
    """Backup status (count, last backup timestamp, latest file)."""
    backups_dir = os.path.join(os.path.dirname(__file__), "backups")
    os.makedirs(backups_dir, exist_ok=True)
    
    # Find all backup files (pattern: shifts_backup_*.db)
    backup_files = sorted(glob(os.path.join(backups_dir, "shifts_backup_*.db")), reverse=True)
    
    last_backup_at = None
    latest_file = None
    if backup_files:
        latest_file = os.path.basename(backup_files[0])
        # Extract timestamp from filename (shifts_backup_20251117_143022.db)
        try:
            timestamp_str = latest_file.replace("shifts_backup_", "").replace(".db", "")
            last_backup_at = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S").isoformat() + "Z"
        except:
            last_backup_at = datetime.fromtimestamp(os.path.getmtime(backup_files[0])).isoformat() + "Z"
    
    return {
        "last_backup_at": last_backup_at,
        "backup_count": len(backup_files),
        "latest_file": latest_file,
        "note": "Backups создаются в директории ./backups (копии shifts.db)",
    }


@router.post("/api/settings/backup/create")
async def create_backup(_=Depends(get_current_admin)):
    """Create backup copy of shifts.db."""
    import shutil
    
    db_path = os.path.join(os.path.dirname(__file__), "db", "shifts.db")
    backups_dir = os.path.join(os.path.dirname(__file__), "backups")
    os.makedirs(backups_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"shifts_backup_{timestamp}.db"
    backup_path = os.path.join(backups_dir, backup_filename)
    
    # Copy database file
    shutil.copy2(db_path, backup_path)
    
    # Get file size
    size_bytes = os.path.getsize(backup_path)
    size_mb = size_bytes / (1024 * 1024)
    
    return {
        "filename": backup_filename,
        "size_bytes": size_bytes,
        "size_mb": size_mb,
        "created_at": datetime.now().isoformat() + "Z",
    }


@router.get("/api/settings/system")
async def get_system_info(_=Depends(get_current_admin)):
    """System information (versions, database status, integrations, platform)."""
    db_path = os.path.join(os.path.dirname(__file__), "db", "shifts.db")
    db_exists = os.path.exists(db_path)
    
    db_info = {
        "exists": db_exists,
        "size_bytes": 0,
        "size_mb": 0.0,
        "path": db_path,
    }
    
    if db_exists:
        size_bytes = os.path.getsize(db_path)
        db_info["size_bytes"] = size_bytes
        db_info["size_mb"] = size_bytes / (1024 * 1024)
    
    telegram_bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    telegram_bot_status = "configured" if telegram_bot_token else "not_configured"
    
    return {
        "versions": {
            "api": "Phase 14 (F5.1 Settings stub)",
            "bot": "Phase 14 (Telegram bot)",
            "web_ui": "Phase 14 (F5.1 Settings refactor)",
        },
        "database": db_info,
        "integrations": {
            "telegram_bot": {
                "status": telegram_bot_status,
                "note": "Проверено наличие BOT_TOKEN в config",
            },
            "sqlite": {
                "status": "active",
                "note": f"База данных: {db_path}",
            },
        },
        "platform": {
            "os": platform.system() + " " + platform.release(),
            "python": platform.python_version(),
        },
        "generated_at": datetime.now().isoformat() + "Z",
    }
