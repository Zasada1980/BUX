"""H-CHAN-1: Channel preview card module.

This module provides functionality to post expense/task preview cards to a Telegram channel.
Uses INFRA-2 (ChannelMessage model) for message persistence and edit tracking.

Key Features:
- Post preview cards to public channel (expense, task, invoice)
- Edit/delete buttons with callback handlers
- ChannelMessage persistence for auto-update (S62)
- Deep-link generation for approve flow
- Content hash for change detection
"""

from bot.channel.preview import router, post_expense_preview, post_task_preview
from bot.channel.auto_update import update_expense_channel_card, update_task_channel_card

__all__ = [
    "router",
    "post_expense_preview",
    "post_task_preview",
    "update_expense_channel_card",
    "update_task_channel_card",
]
