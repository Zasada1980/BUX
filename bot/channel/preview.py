"""H-CHAN-1: Channel preview card implementation.

Posts expense/task/invoice preview cards to Telegram channel with edit/delete buttons.
Saves message_id to channel_messages table (INFRA-2) for S62 auto-update.

Flow:
1. User approves expense/task → Bot posts preview card to channel
2. Card shows: entity details + status + edit/delete buttons
3. Channel message stored in DB (channel_id, message_id, entity_type, entity_id, content_hash)
4. Later auto-update (S62) uses message_id to edit instead of posting new message

Dependencies:
- INFRA-2: ChannelMessage model (channel_messages table)
- bot.config: get_db_session, record_bot_metric, CHANNEL_ID env var
- aiogram: Bot, InlineKeyboardMarkup, InlineKeyboardButton
"""

import hashlib
import asyncio
import random
from typing import Optional, Dict, Any, Tuple
from aiogram import Router, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData
from bot.config import record_bot_metric, get_db_session
from bot.ui.money import fmt_amount_safe
from datetime import datetime

router = Router()

# Channel ID from env (to be added to .env.bot)
# Example: CHANNEL_ID=-1001234567890
import os
CHANNEL_ID = os.getenv("CHANNEL_ID")
CHANNEL_POST_TIMEOUT = float(os.getenv("CHANNEL_POST_TIMEOUT", "10"))

# S62: In-memory fallback for channel posts (ref_key -> (message_id, content_hash))
# In production: replace with DB lookup from channel_messages table
_MEM_STORE: Dict[str, Tuple[int, str]] = {}

# Callback data for channel card buttons
class ChannelCardCB(CallbackData, prefix="chan"):
    """Callback data for channel card buttons."""
    action: str  # edit, delete, view
    entity_type: str  # expense, task, invoice
    entity_id: int


def _generate_content_hash(data: Dict[str, Any]) -> str:
    """Generate SHA256 hash of card content for change detection (S62)."""
    # Sort keys for consistent hashing
    sorted_data = {k: str(v) for k, v in sorted(data.items())}
    content = "|".join(f"{k}={v}" for k, v in sorted_data.items())
    return hashlib.sha256(content.encode()).hexdigest()


def _content_hash_from_text(text: str) -> str:
    """Generate SHA256 hash from card text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _get_channel_post(ref_key: str) -> Optional[Tuple[int, str]]:
    """Get existing channel post by ref_key.
    
    Args:
        ref_key: Unique key like 'expense:12' or 'task:456'
    
    Returns:
        Tuple of (message_id, content_hash) if exists, None otherwise
    """
    try:
        # TODO: Replace with DB lookup when INFRA-2 is ready
        # session = get_db_session()
        # post = session.query(ChannelMessage).filter_by(ref_key=ref_key).first()
        # return (post.message_id, post.content_hash) if post else None
        return _MEM_STORE.get(ref_key)
    except Exception:
        return _MEM_STORE.get(ref_key)


def _save_channel_post(ref_key: str, message_id: int, content_hash: str) -> None:
    """Save or update channel post metadata.
    
    Args:
        ref_key: Unique key like 'expense:12'
        message_id: Telegram message ID
        content_hash: SHA256 hash of content
    """
    try:
        # TODO: Replace with DB upsert when INFRA-2 is ready
        # session = get_db_session()
        # existing = session.query(ChannelMessage).filter_by(ref_key=ref_key).first()
        # if existing:
        #     existing.message_id = message_id
        #     existing.content_hash = content_hash
        # else:
        #     session.add(ChannelMessage(ref_key=ref_key, message_id=message_id, content_hash=content_hash))
        # session.commit()
        _MEM_STORE[ref_key] = (message_id, content_hash)
    except Exception:
        _MEM_STORE[ref_key] = (message_id, content_hash)


def _format_expense_card(expense: Dict[str, Any]) -> str:
    """Format expense preview card text."""
    amount_str = fmt_amount_safe(expense.get("amount"), expense.get("currency", "ILS"))
    category = expense.get("category", "unknown")
    author = expense.get("user_id", "unknown")
    created = expense.get("created_at", "")
    
    # Truncate timestamp
    ts = created[:16] if created else ""
    
    return (
        f"💰 <b>Расход #{expense.get('id')}</b>\n"
        f"Сумма: {amount_str}\n"
        f"Категория: {category}\n"
        f"Автор: {author}\n"
        f"Создано: {ts}\n"
        f"Статус: ✅ Подтверждено"
    )


def _format_task_card(task: Dict[str, Any]) -> str:
    """Format task preview card text."""
    task_code = task.get("task_code", "unknown")
    qty = task.get("qty", 0)
    rate = task.get("rate", 0)
    author = task.get("user_id", "unknown")
    created = task.get("created_at", "")
    
    ts = created[:16] if created else ""
    total = qty * rate
    
    return (
        f"📋 <b>Задача #{task.get('id')}</b>\n"
        f"Код: {task_code}\n"
        f"Количество: {qty}\n"
        f"Ставка: ‎₪{rate}\n"
        f"Итого: ‎₪{total:.2f}\n"
        f"Автор: {author}\n"
        f"Создано: {ts}\n"
        f"Статус: ✅ Подтверждено"
    )


def _generate_card_keyboard(entity_type: str, entity_id: int) -> InlineKeyboardMarkup:
    """Generate inline keyboard for channel card."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data=ChannelCardCB(action="edit", entity_type=entity_type, entity_id=entity_id).pack()
            ),
            InlineKeyboardButton(
                text="🗑️ Удалить",
                callback_data=ChannelCardCB(action="delete", entity_type=entity_type, entity_id=entity_id).pack()
            ),
        ]
    ])


async def publish_or_update_preview(
    bot: Bot,
    channel_id: str,
    text: str,
    keyboard: InlineKeyboardMarkup,
    ref_key: str
) -> Tuple[Optional[int], str]:
    """Publish new preview or update existing (S62 auto-update).
    
    Args:
        bot: Bot instance
        channel_id: Channel ID (e.g., '-1002493712712')
        text: Formatted card text
        keyboard: Inline keyboard
        ref_key: Unique reference key (e.g., 'expense:12', 'task:456')
    
    Returns:
        Tuple of (message_id, action) where action is 'posted', 'edited', or 'noop'
    """
    if not channel_id:
        record_bot_metric("channel.skip", {"reason": "no_channel_id", "ref_key": ref_key})
        return None, "skip"
    
    # Hardening: Retry helper with timeout
    async def _try(fn, *args, **kwargs):
        """Retry API call up to 3 times with exponential backoff."""
        for attempt in range(1, 4):
            try:
                return await asyncio.wait_for(fn(*args, **kwargs), timeout=CHANNEL_POST_TIMEOUT)
            except Exception as e:
                if attempt == 3:
                    raise
                await asyncio.sleep(0.4 * attempt + random.random() * 0.2)
    
    try:
        from api.utils.metrics import log_metric
        
        new_hash = _content_hash_from_text(text)
        existing = _get_channel_post(ref_key)
        
        if existing:
            message_id, old_hash = existing
            
            if old_hash == new_hash:
                # Content unchanged — no action needed
                record_bot_metric("channel.noop", {
                    "ref_key": ref_key,
                    "message_id": message_id,
                    "reason": "content_unchanged"
                })
                log_metric("channel.noop", key=ref_key, msg_id=message_id)
                return message_id, "noop"
            
            # Content changed — edit existing message
            await _try(
                bot.edit_message_text,
                chat_id=channel_id,
                message_id=message_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            _save_channel_post(ref_key, message_id, new_hash)
            
            record_bot_metric("channel.edited", {
                "ref_key": ref_key,
                "message_id": message_id,
                "old_hash": old_hash[:8],
                "new_hash": new_hash[:8]
            })
            log_metric("channel.edited", key=ref_key, msg_id=message_id)
            return message_id, "edited"
        
        # No existing post — create new
        sent = await _try(
            bot.send_message,
            chat_id=channel_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        _save_channel_post(ref_key, sent.message_id, new_hash)
        
        record_bot_metric("channel.posted", {
            "ref_key": ref_key,
            "message_id": sent.message_id,
            "hash": new_hash[:8]
        })
        log_metric("channel.posted", key=ref_key, msg_id=sent.message_id)
        return sent.message_id, "posted"
        
    except Exception as e:
        record_bot_metric("channel.error", {
            "ref_key": ref_key,
            "error": str(e)
        })
        return None, "error"


async def post_expense_preview(bot: Bot, expense: Dict[str, Any]) -> Optional[int]:
    """
    Post expense preview card to channel (S62 auto-update enabled).
    
    Args:
        bot: Bot instance
        expense: Expense data dict (must have 'id', 'amount', 'category', 'user_id', 'created_at')
    
    Returns:
        message_id if posted/edited, None if CHANNEL_ID not configured or error
    """
    if not CHANNEL_ID:
        record_bot_metric("channel.skip", {"reason": "no_channel_id", "entity_type": "expense", "entity_id": expense.get("id")})
        return None
    
    try:
        # Format card
        card_text = _format_expense_card(expense)
        keyboard = _generate_card_keyboard("expense", expense["id"])
        ref_key = f"expense:{expense['id']}"
        
        # S62: Publish or update
        message_id, action = await publish_or_update_preview(
            bot=bot,
            channel_id=CHANNEL_ID,
            text=card_text,
            keyboard=keyboard,
            ref_key=ref_key
        )
        
        return message_id
        
        # Save to DB (INFRA-2)
        session = get_db_session()
        try:
            from api.models import ChannelMessage
            
            # Check if already exists (upsert logic)
            existing = session.query(ChannelMessage).filter_by(
                entity_type="expense",
                entity_id=expense["id"]
            ).first()
            
            if existing:
                # Update existing
                existing.channel_id = int(CHANNEL_ID)
                existing.message_id = sent.message_id
                existing.content_hash = content_hash
                existing.updated_at = datetime.utcnow()
            else:
                # Create new
                channel_msg = ChannelMessage(
                    channel_id=int(CHANNEL_ID),
                    message_id=sent.message_id,
                    entity_type="expense",
                    entity_id=expense["id"],
                    content_hash=content_hash
                )
                session.add(channel_msg)
            
            session.commit()
            record_bot_metric("channel.posted", {
                "entity_type": "expense",
                "entity_id": expense["id"],
                "message_id": sent.message_id,
                "channel_id": CHANNEL_ID
            })
            
            return sent.message_id
            
        finally:
            session.close()
            
    except Exception as e:
        record_bot_metric("channel.error", {
            "entity_type": "expense",
            "entity_id": expense.get("id"),
            "error": str(e)
        })
        return None


async def post_task_preview(bot: Bot, task: Dict[str, Any]) -> Optional[int]:
    """
    Post task preview card to channel.
    
    Args:
        bot: Bot instance
        task: Task data dict (must have 'id', 'task_code', 'qty', 'rate', 'user_id', 'created_at')
    
    Returns:
        message_id if posted, None if CHANNEL_ID not configured or error
    """
    if not CHANNEL_ID:
        record_bot_metric("channel.skip", {"reason": "no_channel_id", "entity_type": "task", "entity_id": task.get("id")})
        return None
    
    try:
        # Format card
        card_text = _format_task_card(task)
        keyboard = _generate_card_keyboard("task", task["id"])
        
        # Generate content hash
        content_hash = _generate_content_hash({
            "task_code": task.get("task_code"),
            "qty": task.get("qty"),
            "rate": task.get("rate"),
            "status": "approved"
        })
        
        # Send to channel
        sent = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=card_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Save to DB (INFRA-2)
        session = get_db_session()
        try:
            from api.models import ChannelMessage
            
            # Check if already exists
            existing = session.query(ChannelMessage).filter_by(
                entity_type="task",
                entity_id=task["id"]
            ).first()
            
            if existing:
                # Update existing
                existing.channel_id = int(CHANNEL_ID)
                existing.message_id = sent.message_id
                existing.content_hash = content_hash
                existing.updated_at = datetime.utcnow()
            else:
                # Create new
                channel_msg = ChannelMessage(
                    channel_id=int(CHANNEL_ID),
                    message_id=sent.message_id,
                    entity_type="task",
                    entity_id=task["id"],
                    content_hash=content_hash
                )
                session.add(channel_msg)
            
            session.commit()
            record_bot_metric("channel.posted", {
                "entity_type": "task",
                "entity_id": task["id"],
                "message_id": sent.message_id,
                "channel_id": CHANNEL_ID
            })
            
            return sent.message_id
            
        finally:
            session.close()
            
    except Exception as e:
        record_bot_metric("channel.error", {
            "entity_type": "task",
            "entity_id": task.get("id"),
            "error": str(e)
        })
        return None


# Callback handlers for edit/delete buttons
@router.callback_query(ChannelCardCB.filter())
async def channel_card_callback(c: CallbackQuery, callback_data: ChannelCardCB):
    """Handle edit/delete buttons from channel cards."""
    action = callback_data.action
    entity_type = callback_data.entity_type
    entity_id = callback_data.entity_id
    
    record_bot_metric(f"channel.{action}.click", {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "user_id": c.from_user.id if c.from_user else None
    })
    
    if action == "edit":
        # Redirect to bot DM with deep-link
        bot_username = (await c.bot.get_me()).username
        deep_link = f"https://t.me/{bot_username}?start=edit_{entity_type}_{entity_id}"
        await c.answer(
            f"Для редактирования перейдите в бота: {deep_link}",
            show_alert=True
        )
        
    elif action == "delete":
        # Redirect to bot DM for confirmation
        bot_username = (await c.bot.get_me()).username
        deep_link = f"https://t.me/{bot_username}?start=del_{entity_type}_{entity_id}"
        await c.answer(
            f"Для удаления перейдите в бота: {deep_link}",
            show_alert=True
        )
        
    else:
        await c.answer("Неизвестная команда", show_alert=True)
