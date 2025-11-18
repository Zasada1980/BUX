"""Telegram Bot Menu Synchronization Module.

This module provides functions to build and apply Telegram bot commands
based on database configuration (bot_commands table).

Usage from Web UI (via POST /api/admin/bot-menu/apply):
1. Fetch commands from DB (grouped by role)
2. Build BotCommand objects for each role
3. Call bot.set_my_commands() with appropriate scopes

**IMPORTANT**: This module requires bot to be running and accessible.
"""
import asyncio
import logging
from typing import Dict, List, Optional
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat
from sqlalchemy import text
from sqlalchemy.orm import Session

from bot.config import TELEGRAM_BOT_TOKEN, BOT_ADMINS  # Existing bot config

logger = logging.getLogger(__name__)


def build_bot_commands(db: Session, role: str) -> List[BotCommand]:
    """
    Build list of BotCommand objects for a given role.
    
    Args:
        db: Database session
        role: User role ('admin', 'foreman', 'worker')
    
    Returns:
        List of BotCommand(command=..., description=...) for Telegram API
    """
    rows = db.execute(text("""
        SELECT telegram_command, label
        FROM bot_commands
        WHERE role = :role AND enabled = 1
        ORDER BY position, id
    """), {"role": role}).fetchall()
    
    commands = []
    for row in rows:
        telegram_command = row[0].lstrip('/')  # Remove leading slash if present
        label = row[1]
        commands.append(BotCommand(command=telegram_command, description=label))
    
    logger.info(f"Built {len(commands)} commands for role '{role}'")
    return commands


def apply_bot_menu(db: Session) -> Dict[str, any]:
    """
    Apply current bot menu configuration to Telegram bot.
    
    **Implementation Strategy**:
    - Admin commands: Set per-chat scope for each admin in BOT_ADMINS
    - Worker/Foreman commands: Set default scope (all users see same menu)
      - Bot handlers on receiving messages should filter commands by user role
    
    **Limitations**:
    - Telegram API has no per-user scopes (only per-chat)
    - All workers see same menu; bot must validate role server-side
    
    Returns:
        {
            "success": bool,
            "details": str (success/error message),
            "commands_applied": {role: int} (command counts)
        }
    """
    if not TELEGRAM_BOT_TOKEN:
        return {
            "success": False,
            "details": "TELEGRAM_BOT_TOKEN not configured in bot/config.py"
        }
    
    try:
        # Run async operation in new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_apply_bot_menu_async(db))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Failed to apply bot menu: {e}", exc_info=True)
        return {
            "success": False,
            "details": f"Exception during apply: {str(e)}"
        }


async def _apply_bot_menu_async(db: Session) -> Dict[str, any]:
    """Async implementation of apply_bot_menu."""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    
    try:
        # Build commands for each role
        admin_commands = build_bot_commands(db, "admin")
        foreman_commands = build_bot_commands(db, "foreman")
        worker_commands = build_bot_commands(db, "worker")
        
        # Apply admin commands to each admin chat
        admin_count = 0
        for admin_id in BOT_ADMINS:
            try:
                await bot.set_my_commands(
                    admin_commands,
                    scope=BotCommandScopeChat(chat_id=admin_id)
                )
                admin_count += 1
                logger.info(f"✅ Admin menu set for {admin_id}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to set admin menu for {admin_id}: {e}")
        
        # Apply default menu (worker commands for now)
        # NOTE: Foreman/worker distinction handled by bot handlers (role check)
        await bot.set_my_commands(worker_commands)  # Default scope = all users
        logger.info(f"✅ Default menu set (worker commands)")
        
        return {
            "success": True,
            "details": f"Commands applied: {admin_count} admins, default menu set",
            "commands_applied": {
                "admin": len(admin_commands),
                "foreman": len(foreman_commands),
                "worker": len(worker_commands),
            }
        }
    
    finally:
        await bot.session.close()


# --- Integration Notes for Bot Handlers ---
# 
# After applying menu via Web UI, bot handlers (in bot/handlers.py, bot/agent_handlers.py, etc.)
# should validate user role before executing commands:
#
# @router.message(Command("admin"))
# async def cmd_admin(message: Message):
#     user_id = message.from_user.id
#     if not is_admin(user_id):
#         await message.answer("⛔ Access denied. Admin only.")
#         return
#     # ... admin panel logic
#
# This ensures that even if a worker sees admin commands in menu (due to Telegram scope limitations),
# they cannot execute them.
