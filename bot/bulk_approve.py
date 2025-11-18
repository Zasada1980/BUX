"""
H-BOT-1: Bulk Approve для Foreman.

Features:
- Checkbox-based multi-select в inbox
- Select All / Deselect All кнопки
- Bulk approve одним действием (API call с идемпотентностью)
- Batch DM notifications для worker'ов
- Metrics: bulk_approve.count, bulk_approve.latency
"""
import hashlib
import json
import time
import uuid
from typing import List, Dict, Set
import aiohttp
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import API_BASE_URL, is_foreman, record_bot_metric, DEV_MODE
from bot.ui.money import fmt_amount_safe

router = Router()

# ============================================================================
# Bulk Selection State (in-memory per chat)
# ============================================================================
# Key: chat_id -> Set of selected item tuples (kind, id)
_BULK_SELECTIONS: Dict[int, Set[tuple]] = {}


def _get_selection(chat_id: int) -> Set[tuple]:
    """Get current selection for chat."""
    return _BULK_SELECTIONS.get(chat_id, set())


def _set_selection(chat_id: int, selection: Set[tuple]):
    """Set selection for chat."""
    _BULK_SELECTIONS[chat_id] = selection


def _clear_selection(chat_id: int):
    """Clear selection for chat."""
    _BULK_SELECTIONS.pop(chat_id, None)


def _toggle_item(chat_id: int, kind: str, item_id: int) -> bool:
    """Toggle item selection. Returns True if now selected, False if deselected."""
    selection = _get_selection(chat_id)
    item_key = (kind, item_id)
    
    if item_key in selection:
        selection.remove(item_key)
        _set_selection(chat_id, selection)
        return False
    else:
        selection.add(item_key)
        _set_selection(chat_id, selection)
        return True


def _is_selected(chat_id: int, kind: str, item_id: int) -> bool:
    """Check if item is selected."""
    selection = _get_selection(chat_id)
    return (kind, item_id) in selection


# ============================================================================
# Rendering
# ============================================================================

def _render_bulk_inbox(items: List[dict], chat_id: int, limit: int, offset: int, 
                       next_offset: int, total_pending: int = None) -> InlineKeyboardMarkup:
    """Render inbox with checkboxes for bulk selection.
    
    Layout per item:
    [☐/☑ Title line (compact)]
    [Details] [Approve (single)]
    
    Footer:
    [Select All] [Deselect All]
    [✅ Approve Selected (N)] (if N > 0)
    [Pagination]
    """
    from bot.handlers import _b64, _kb_rows
    
    rows = []
    selection = _get_selection(chat_id)
    
    for item in items:
        kind = item["kind"]
        item_id = item["id"]
        kind_short = kind[0]  # 'e'/'t'/'p'
        
        # Checkbox state
        is_sel = _is_selected(chat_id, kind, item_id)
        checkbox = "☑" if is_sel else "☐"
        
        # Compact resume (BK-4 format)
        amount_fmt = fmt_amount_safe(item.get('amount'), item.get('currency', 'ILS'))
        author = (item.get('author') or 'unknown')[:12]
        created = item.get('created_at', '')
        if created and len(created) >= 16:
            ts_short = f"{created[5:10]} {created[11:16]}"
        else:
            ts_short = "—"
        
        title = f"{checkbox} [#{kind_short.upper()}{item_id}] {amount_fmt} · {author} · {ts_short}"
        if len(title) > 60:
            title = title[:57] + "..."
        
        # Row 1: Checkbox toggle button
        rows.append([
            InlineKeyboardButton(
                text=title,
                callback_data=f"bulk_toggle|{_b64({'k': kind_short, 'i': item_id})}"
            )
        ])
        
        # Row 2: Details + Single approve
        rows.append([
            InlineKeyboardButton(
                text="📋 Детали",
                callback_data=f"det|{_b64({'k': kind_short, 'i': item_id})}"
            ),
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"app|{_b64({'k': kind_short, 'i': item_id})}"
            )
        ])
    
    # Footer: Bulk actions
    bulk_actions = []
    
    # Select All / Deselect All
    if len(selection) < len(items):
        # Show Select All if not all selected
        all_items_payload = _b64({
            'items': [{'k': it['kind'][0], 'i': it['id']} for it in items]
        })
        bulk_actions.append([
            InlineKeyboardButton(
                text="☑ Выбрать все",
                callback_data=f"bulk_select_all|{all_items_payload}"
            )
        ])
    
    if len(selection) > 0:
        # Show Deselect All if something selected
        bulk_actions.append([
            InlineKeyboardButton(
                text="☐ Снять выбор",
                callback_data="bulk_deselect_all"
            )
        ])
        
        # Approve Selected (N)
        bulk_actions.append([
            InlineKeyboardButton(
                text=f"✅ Одобрить выбранное ({len(selection)})",
                callback_data="bulk_approve_selected"
            )
        ])
    
    rows.extend(bulk_actions)
    
    # Pagination (same as inbox)
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(
            text="◀ Назад",
            callback_data=f"bulk_pg|{_b64({'l': limit, 'o': max(0, offset - limit)})}"
        ))
    if next_offset is not None:
        next_start = offset + limit + 1
        next_end = min(offset + 2 * limit, total_pending) if total_pending else offset + 2 * limit
        nav.append(InlineKeyboardButton(
            text=f"▶ След ({next_start}–{next_end})",
            callback_data=f"bulk_pg|{_b64({'l': limit, 'o': next_offset})}"
        ))
    if nav:
        rows.append(nav)
    
    return _kb_rows(rows) if rows else None


# ============================================================================
# Handlers
# ============================================================================

@router.callback_query(F.data == "bulk_mode_on")
async def bulk_mode_on_cb(c: CallbackQuery):
    """Enable bulk mode for inbox."""
    uid = c.from_user.id if c.from_user else 0
    chat_id = c.message.chat.id if c.message else uid
    
    if not is_foreman(uid):
        return await c.answer("🚫 Только для бригадиров", show_alert=True)
    
    # Clear any previous selection
    _clear_selection(chat_id)
    
    # Reload inbox in bulk mode
    limit, offset = 5, 0
    async with aiohttp.ClientSession() as s:
        t0 = time.time()
        async with s.get(
            f"{API_BASE_URL}/bot/inbox",
            params={"role": "foreman", "state": "pending", "limit": limit, "offset": offset, "telegram_id": uid},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            data = await r.json()
            latency = round((time.time() - t0) * 1000, 2)
    
    items = data.get("items", [])
    total_pending = data.get("total", len(items))
    
    record_bot_metric("bulk_mode.enabled", {"count": len(items), "latency_ms": latency})
    
    # Render with checkboxes
    current_page = (offset // limit) + 1
    total_pages = ((total_pending - 1) // limit) + 1 if total_pending > 0 else 1
    start_idx = offset + 1
    end_idx = min(offset + len(items), total_pending)
    header = f"📥 Массовый выбор: {start_idx}–{end_idx} из {total_pending} · стр. {current_page}/{total_pages}"
    
    kb = _render_bulk_inbox(items, chat_id, limit, offset, data.get("next_offset"), total_pending)
    
    if c.message and hasattr(c.message, "edit_text"):
        await c.message.edit_text(header, reply_markup=kb)
    await c.answer("✅ Режим массового выбора включён")


@router.callback_query(F.data.startswith("bulk_toggle|"))
async def bulk_toggle_cb(c: CallbackQuery):
    """Toggle item selection."""
    from bot.handlers import _unb64
    
    uid = c.from_user.id if c.from_user else 0
    chat_id = c.message.chat.id if c.message else uid
    
    if not is_foreman(uid):
        return await c.answer("🚫 Только для бригадиров", show_alert=True)
    
    payload = _unb64(c.data.split("|", 1)[1])
    kind_map = {'e': 'expense', 't': 'task', 'p': 'pending_change'}
    k = str(payload.get('k', ''))
    kind = kind_map.get(k, 'expense')
    item_id = int(payload.get('i', 0))
    
    is_now_selected = _toggle_item(chat_id, kind, item_id)
    
    record_bot_metric("bulk.toggle", {
        "kind": kind,
        "id": item_id,
        "selected": is_now_selected,
        "total_selected": len(_get_selection(chat_id))
    })
    
    # Re-render inbox with updated checkboxes
    # Extract current offset/limit from message or default
    limit, offset = 5, 0
    
    async with aiohttp.ClientSession() as s:
        t0 = time.time()
        async with s.get(
            f"{API_BASE_URL}/bot/inbox",
            params={"role": "foreman", "state": "pending", "limit": limit, "offset": offset, "telegram_id": uid},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            data = await r.json()
            latency = round((time.time() - t0) * 1000, 2)
    
    items = data.get("items", [])
    total_pending = data.get("total", len(items))
    
    current_page = (offset // limit) + 1
    total_pages = ((total_pending - 1) // limit) + 1 if total_pending > 0 else 1
    start_idx = offset + 1
    end_idx = min(offset + len(items), total_pending)
    header = f"📥 Массовый выбор: {start_idx}–{end_idx} из {total_pending} · стр. {current_page}/{total_pages}"
    
    kb = _render_bulk_inbox(items, chat_id, limit, offset, data.get("next_offset"), total_pending)
    
    if c.message and hasattr(c.message, "edit_text"):
        await c.message.edit_text(header, reply_markup=kb)
    
    emoji = "☑" if is_now_selected else "☐"
    await c.answer(f"{emoji} {kind} #{item_id}")


@router.callback_query(F.data.startswith("bulk_select_all|"))
async def bulk_select_all_cb(c: CallbackQuery):
    """Select all items on current page."""
    from bot.handlers import _unb64
    
    uid = c.from_user.id if c.from_user else 0
    chat_id = c.message.chat.id if c.message else uid
    
    if not is_foreman(uid):
        return await c.answer("🚫 Только для бригадиров", show_alert=True)
    
    payload = _unb64(c.data.split("|", 1)[1])
    items_data = payload.get('items', [])
    
    selection = _get_selection(chat_id)
    kind_map = {'e': 'expense', 't': 'task', 'p': 'pending_change'}
    
    for item_data in items_data:
        k = str(item_data.get('k', ''))
        kind = kind_map.get(k, 'expense')
        item_id = int(item_data.get('i', 0))
        selection.add((kind, item_id))
    
    _set_selection(chat_id, selection)
    
    record_bot_metric("bulk.select_all", {"count": len(items_data), "total_selected": len(selection)})
    
    # Re-render
    limit, offset = 5, 0
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"{API_BASE_URL}/bot/inbox",
            params={"role": "foreman", "state": "pending", "limit": limit, "offset": offset, "telegram_id": uid},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            data = await r.json()
    
    items = data.get("items", [])
    total_pending = data.get("total", len(items))
    
    current_page = (offset // limit) + 1
    total_pages = ((total_pending - 1) // limit) + 1 if total_pending > 0 else 1
    start_idx = offset + 1
    end_idx = min(offset + len(items), total_pending)
    header = f"📥 Массовый выбор: {start_idx}–{end_idx} из {total_pending} · стр. {current_page}/{total_pages}"
    
    kb = _render_bulk_inbox(items, chat_id, limit, offset, data.get("next_offset"), total_pending)
    
    if c.message and hasattr(c.message, "edit_text"):
        await c.message.edit_text(header, reply_markup=kb)
    
    await c.answer(f"☑ Выбрано: {len(selection)}")


@router.callback_query(F.data == "bulk_deselect_all")
async def bulk_deselect_all_cb(c: CallbackQuery):
    """Deselect all items."""
    uid = c.from_user.id if c.from_user else 0
    chat_id = c.message.chat.id if c.message else uid
    
    if not is_foreman(uid):
        return await c.answer("🚫 Только для бригадиров", show_alert=True)
    
    _clear_selection(chat_id)
    
    record_bot_metric("bulk.deselect_all", {})
    
    # Re-render
    limit, offset = 5, 0
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"{API_BASE_URL}/bot/inbox",
            params={"role": "foreman", "state": "pending", "limit": limit, "offset": offset, "telegram_id": uid},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            data = await r.json()
    
    items = data.get("items", [])
    total_pending = data.get("total", len(items))
    
    current_page = (offset // limit) + 1
    total_pages = ((total_pending - 1) // limit) + 1 if total_pending > 0 else 1
    start_idx = offset + 1
    end_idx = min(offset + len(items), total_pending)
    header = f"📥 Массовый выбор: {start_idx}–{end_idx} из {total_pending} · стр. {current_page}/{total_pages}"
    
    kb = _render_bulk_inbox(items, chat_id, limit, offset, data.get("next_offset"), total_pending)
    
    if c.message and hasattr(c.message, "edit_text"):
        await c.message.edit_text(header, reply_markup=kb)
    
    await c.answer("☐ Выбор снят")


@router.callback_query(F.data == "bulk_approve_selected")
async def bulk_approve_selected_cb(c: CallbackQuery):
    """Approve all selected items in bulk."""
    uid = c.from_user.id if c.from_user else 0
    chat_id = c.message.chat.id if c.message else uid
    
    if not is_foreman(uid):
        return await c.answer("🚫 Только для бригадиров", show_alert=True)
    
    # DEV_MODE protection
    if DEV_MODE:
        record_bot_metric("dev_block", {"action": "bulk_approve", "user_id": uid})
        return await c.answer("⏸ DEV_MODE: действие не выполнено (тестовый режим)", show_alert=True)
    
    selection = _get_selection(chat_id)
    
    if not selection:
        return await c.answer("⚠️ Нет выбранных элементов", show_alert=True)
    
    # Show spinner
    try:
        from bot.handlers import _kb_rows
        spinner_kb = _kb_rows([[InlineKeyboardButton(text="⌛ Обрабатываю…", callback_data="noop")]])
        if c.message and hasattr(c.message, "edit_reply_markup"):
            await c.message.edit_reply_markup(reply_markup=spinner_kb)
    except Exception:
        pass
    
    # Prepare bulk request
    items_payload = []
    for kind, item_id in selection:
        items_payload.append({"kind": kind, "id": item_id})
    
    # Generate idempotency key
    idempotency_key = f"BULK-{uuid.uuid4().hex[:16]}"
    
    # API call
    async with aiohttp.ClientSession() as s:
        t0 = time.time()
        headers = {
            "Content-Type": "application/json",
            "X-Idempotency-Key": idempotency_key
        }
        async with s.post(
            f"{API_BASE_URL}/bot/approve",
            json={"items": items_payload, "telegram_id": uid},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as r:
            res = await r.json()
            latency = round((time.time() - t0) * 1000, 2)
    
    approved_count = res.get("approved_count", 0)
    results = res.get("results", [])
    
    record_bot_metric("bulk_approve.complete", {
        "count": approved_count,
        "selected": len(selection),
        "latency_ms": latency
    })
    
    # Send batch DM notifications to workers
    worker_notifications = {}  # worker_telegram_id -> list of approved items
    
    for result in results:
        if result.get("status") == "ok" and result.get("worker_telegram_id"):
            worker_id = result["worker_telegram_id"]
            if worker_id not in worker_notifications:
                worker_notifications[worker_id] = []
            worker_notifications[worker_id].append({
                "kind": result.get("kind"),
                "id": result.get("id")
            })
    
    # Send DMs
    bot = c.bot
    dm_sent = 0
    dm_failed = 0
    
    for worker_id, approved_items in worker_notifications.items():
        try:
            # Batch message format
            items_text = "\n".join([f"• {item['kind']} #{item['id']}" for item in approved_items[:10]])
            if len(approved_items) > 10:
                items_text += f"\n• ... и ещё {len(approved_items) - 10}"
            
            worker_msg = f"✅ Подтверждено ({len(approved_items)}):\n{items_text}"
            
            sent = await bot.send_message(worker_id, worker_msg)
            dm_sent += 1
            
            record_bot_metric("dm.batch_sent", {
                "worker_id": worker_id,
                "count": len(approved_items),
                "message_id": sent.message_id
            })
        except Exception as e:
            dm_failed += 1
            record_bot_metric("dm.batch_fail", {
                "worker_id": worker_id,
                "error": str(e)
            })
    
    # Clear selection
    _clear_selection(chat_id)
    
    # Show result
    result_text = (
        f"✅ <b>Массовое одобрение завершено</b>\n\n"
        f"Одобрено: {approved_count}/{len(selection)}\n"
        f"Уведомлений отправлено: {dm_sent}\n"
        f"Ошибок отправки: {dm_failed}"
    )
    
    # Reload inbox
    limit, offset = 5, 0
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"{API_BASE_URL}/bot/inbox",
            params={"role": "foreman", "state": "pending", "limit": limit, "offset": offset, "telegram_id": uid},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            data = await r.json()
    
    items = data.get("items", [])
    total_pending = data.get("total", len(items))
    
    current_page = (offset // limit) + 1
    total_pages = ((total_pending - 1) // limit) + 1 if total_pending > 0 else 1
    start_idx = offset + 1
    end_idx = min(offset + len(items), total_pending)
    header = f"📥 Массовый выбор: {start_idx}–{end_idx} из {total_pending} · стр. {current_page}/{total_pages}\n\n{result_text}"
    
    kb = _render_bulk_inbox(items, chat_id, limit, offset, data.get("next_offset"), total_pending)
    
    if c.message and hasattr(c.message, "edit_text"):
        await c.message.edit_text(header, reply_markup=kb)
    
    await c.answer(f"✅ Одобрено: {approved_count}")


@router.callback_query(F.data.startswith("bulk_pg|"))
async def bulk_page_cb(c: CallbackQuery):
    """Pagination in bulk mode."""
    from bot.handlers import _unb64
    
    uid = c.from_user.id if c.from_user else 0
    chat_id = c.message.chat.id if c.message else uid
    
    if not is_foreman(uid):
        return await c.answer("🚫 Только для бригадиров", show_alert=True)
    
    payload = _unb64(c.data.split("|", 1)[1])
    limit = int(payload.get("l", 5))
    offset = int(payload.get("o", 0))
    
    async with aiohttp.ClientSession() as s:
        t0 = time.time()
        async with s.get(
            f"{API_BASE_URL}/bot/inbox",
            params={"role": "foreman", "state": "pending", "limit": limit, "offset": offset, "telegram_id": uid},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            data = await r.json()
            latency = round((time.time() - t0) * 1000, 2)
    
    items = data.get("items", [])
    total_pending = data.get("total", len(items))
    
    record_bot_metric("bulk.page", {"offset": offset, "limit": limit, "latency_ms": latency})
    
    current_page = (offset // limit) + 1
    total_pages = ((total_pending - 1) // limit) + 1 if total_pending > 0 else 1
    start_idx = offset + 1
    end_idx = min(offset + len(items), total_pending)
    header = f"📥 Массовый выбор: {start_idx}–{end_idx} из {total_pending} · стр. {current_page}/{total_pages}"
    
    kb = _render_bulk_inbox(items, chat_id, limit, offset, data.get("next_offset"), total_pending)
    
    if c.message and hasattr(c.message, "edit_text"):
        await c.message.edit_text(header, reply_markup=kb)
    
    await c.answer()

