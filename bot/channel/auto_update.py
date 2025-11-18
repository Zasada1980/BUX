"""S62: Channel Auto-Update Module

Automatically updates channel preview cards when expense/task status changes.
Uses INFRA-2 (ChannelMessage) to find existing message → edit instead of posting new.

Key Features:
- Edit existing message if content changed (compare content_hash)
- Skip edit if content unchanged (idempotent)
- Fall back to new post if message_id not found
- No personal data in channel (worker names anonymized)

Flow:
1. Expense/task status changes (approve/reject/edit)
2. Lookup channel_message by entity_type + entity_id
3. Calculate new content_hash
4. Compare with stored hash:
   - If different → edit_message_text
   - If same → skip (idempotent)
5. Update content_hash in DB
"""

from typing import Optional, Dict, Any
from aiogram import Bot
from bot.config import get_db_session, record_bot_metric
from bot.channel.preview import (
    _format_expense_card,
    _format_task_card,
    _generate_content_hash,
    _generate_card_keyboard,
    CHANNEL_ID,
    post_expense_preview,
    post_task_preview,
)
from datetime import datetime


async def update_expense_channel_card(bot: Bot, expense: Dict[str, Any]) -> bool:
    """
    Update existing expense channel card or post new if not exists.
    
    Args:
        bot: Bot instance
        expense: Expense data dict
    
    Returns:
        True if updated/posted, False if skipped (unchanged) or error
    """
    if not CHANNEL_ID:
        record_bot_metric("channel.update.skip", {"reason": "no_channel_id", "entity_type": "expense", "entity_id": expense.get("id")})
        return False
    
    entity_id = expense.get("id")
    if not entity_id:
        record_bot_metric("channel.update.error", {"reason": "no_entity_id", "entity_type": "expense"})
        return False
    
    session = get_db_session()
    try:
        from api.models import ChannelMessage
        
        # Find existing channel message
        channel_msg = session.query(ChannelMessage).filter_by(
            entity_type="expense",
            entity_id=entity_id
        ).first()
        
        # Calculate new content hash
        new_hash = _generate_content_hash({
            "amount": expense.get("amount"),
            "category": expense.get("category"),
            "status": expense.get("status", "approved")
        })
        
        if not channel_msg:
            # No existing message → post new (fallback)
            record_bot_metric("channel.update.fallback_new_post", {"entity_type": "expense", "entity_id": entity_id})
            message_id = await post_expense_preview(bot, expense)
            return message_id is not None
        
        # Compare hashes
        if channel_msg.content_hash == new_hash:
            # Content unchanged → skip (idempotent)
            record_bot_metric("channel.update.skip", {
                "reason": "unchanged",
                "entity_type": "expense",
                "entity_id": entity_id,
                "hash": new_hash[:16]
            })
            return False
        
        # Content changed → edit existing message
        try:
            card_text = _format_expense_card(expense)
            keyboard = _generate_card_keyboard("expense", entity_id)
            
            await bot.edit_message_text(
                chat_id=channel_msg.channel_id,
                message_id=channel_msg.message_id,
                text=card_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Update hash in DB
            channel_msg.content_hash = new_hash
            channel_msg.updated_at = datetime.utcnow()
            session.commit()
            
            record_bot_metric("channel.update.edited", {
                "entity_type": "expense",
                "entity_id": entity_id,
                "message_id": channel_msg.message_id,
                "old_hash": channel_msg.content_hash[:16] if channel_msg.content_hash else None,
                "new_hash": new_hash[:16]
            })
            
            return True
            
        except Exception as e:
            # Edit failed → try posting new (fallback)
            record_bot_metric("channel.update.edit_failed", {
                "entity_type": "expense",
                "entity_id": entity_id,
                "error": str(e)
            })
            message_id = await post_expense_preview(bot, expense)
            return message_id is not None
            
    finally:
        session.close()


async def update_task_channel_card(bot: Bot, task: Dict[str, Any]) -> bool:
    """
    Update existing task channel card or post new if not exists.
    
    Args:
        bot: Bot instance
        task: Task data dict
    
    Returns:
        True if updated/posted, False if skipped (unchanged) or error
    """
    if not CHANNEL_ID:
        record_bot_metric("channel.update.skip", {"reason": "no_channel_id", "entity_type": "task", "entity_id": task.get("id")})
        return False
    
    entity_id = task.get("id")
    if not entity_id:
        record_bot_metric("channel.update.error", {"reason": "no_entity_id", "entity_type": "task"})
        return False
    
    session = get_db_session()
    try:
        from api.models import ChannelMessage
        
        # Find existing channel message
        channel_msg = session.query(ChannelMessage).filter_by(
            entity_type="task",
            entity_id=entity_id
        ).first()
        
        # Calculate new content hash
        new_hash = _generate_content_hash({
            "task_code": task.get("task_code"),
            "qty": task.get("qty"),
            "rate": task.get("rate"),
            "status": task.get("status", "approved")
        })
        
        if not channel_msg:
            # No existing message → post new (fallback)
            record_bot_metric("channel.update.fallback_new_post", {"entity_type": "task", "entity_id": entity_id})
            message_id = await post_task_preview(bot, task)
            return message_id is not None
        
        # Compare hashes
        if channel_msg.content_hash == new_hash:
            # Content unchanged → skip (idempotent)
            record_bot_metric("channel.update.skip", {
                "reason": "unchanged",
                "entity_type": "task",
                "entity_id": entity_id,
                "hash": new_hash[:16]
            })
            return False
        
        # Content changed → edit existing message
        try:
            card_text = _format_task_card(task)
            keyboard = _generate_card_keyboard("task", entity_id)
            
            await bot.edit_message_text(
                chat_id=channel_msg.channel_id,
                message_id=channel_msg.message_id,
                text=card_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            # Update hash in DB
            channel_msg.content_hash = new_hash
            channel_msg.updated_at = datetime.utcnow()
            session.commit()
            
            record_bot_metric("channel.update.edited", {
                "entity_type": "task",
                "entity_id": entity_id,
                "message_id": channel_msg.message_id,
                "old_hash": channel_msg.content_hash[:16] if channel_msg.content_hash else None,
                "new_hash": new_hash[:16]
            })
            
            return True
            
        except Exception as e:
            # Edit failed → try posting new (fallback)
            record_bot_metric("channel.update.edit_failed", {
                "entity_type": "task",
                "entity_id": entity_id,
                "error": str(e)
            })
            message_id = await post_task_preview(bot, task)
            return message_id is not None
            
    finally:
        session.close()
