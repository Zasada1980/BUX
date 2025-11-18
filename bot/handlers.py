"""Sprint D Bot - Handlers (D2-D6)."""
import json, base64, hashlib, time
from typing import Optional, Dict, Tuple
import aiohttp
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ForceReply
from aiogram.filters import Command
from bot.config import API_BASE_URL, is_foreman, is_admin, record_bot_metric, throttle_check, DEV_MODE
from bot.ui.money import fmt_amount_safe  # BK-8: Money formatter
from bot.ui.indicators import render_banner  # BK-3: Post-result banners

router = Router()

# BK-2B: In-memory debounce cache for click events
# Key: (chat_id, message_id) -> expiry epoch seconds
_DEBOUNCE: Dict[Tuple[int, int], float] = {}

def _debounce_key(c: CallbackQuery) -> Optional[Tuple[int, int]]:
    try:
        if c.message and c.message.chat and c.message.message_id:
            return (c.message.chat.id, c.message.message_id)
    except Exception:
        return None
    return None

def _debounce_gc(now: Optional[float] = None) -> None:
    """Cleanup expired debounce entries."""
    if not _DEBOUNCE:
        return
    now = now if now is not None else time.time()
    expired = [k for k, exp in _DEBOUNCE.items() if exp <= now]
    for k in expired:
        _DEBOUNCE.pop(k, None)

def _debounce_check_and_mark(c: CallbackQuery, window: float = 1.5) -> bool:
    """Returns True if hit (should debounce and block), False otherwise (marked)."""
    key = _debounce_key(c)
    now = time.time()
    _debounce_gc(now)
    if not key:
        return False
    exp = _DEBOUNCE.get(key)
    if exp and exp > now:
        # Debounce HIT
        record_bot_metric("bot.ui.debounce.hit", {
            "chat_id": getattr(c.message.chat, "id", None) if c.message else None,
            "message_id": getattr(c.message, "message_id", None) if c.message else None,
            "window_s": window,
        })
        return True
    # Mark MISS (allow and set expiry)
    _DEBOUNCE[key] = now + window
    record_bot_metric("bot.ui.debounce.miss", {
        "chat_id": getattr(c.message.chat, "id", None) if c.message else None,
        "message_id": getattr(c.message, "message_id", None) if c.message else None,
        "window_s": window,
    })
    return False

def _debounce_check_and_mark_ids(chat_id: int, message_id: int, ttl: float = 1.5, now: Optional[float] = None) -> bool:
    """ID-based variant for tests: True if debounce HIT, False if MISS (and mark)."""
    now = now if now is not None else time.time()
    _debounce_gc(now)
    key = (int(chat_id), int(message_id))
    exp = _DEBOUNCE.get(key)
    if exp and exp > now:
        record_bot_metric("bot.ui.debounce.hit", {"chat_id": chat_id, "message_id": message_id, "window_s": ttl})
        return True
    _DEBOUNCE[key] = now + ttl
    record_bot_metric("bot.ui.debounce.miss", {"chat_id": chat_id, "message_id": message_id, "window_s": ttl})
    return False

async def _show_spinner(c: CallbackQuery, action: Optional[str] = None) -> bool:
    """BK-2A: Replace keyboard with spinner button before API call.
    Returns True when spinner markup was shown, False otherwise."""
    try:
        spinner_kb = _kb_rows([[InlineKeyboardButton(text="⌛ Обрабатываю…", callback_data="noop")]])
        if c.message and hasattr(c.message, "edit_reply_markup"):
            await c.message.edit_reply_markup(reply_markup=spinner_kb)
            record_bot_metric("bot.ui.spinner.show", {
                "chat_id": getattr(c.message.chat, "id", None),
                "message_id": getattr(c.message, "message_id", None),
                "action": action,
            })
            return True
    except Exception as e:
        # Non-fatal: continue without spinner
        record_bot_metric("bot.ui.spinner.error", {"error": str(e), "action": action})
    return False

def _b64(obj: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(obj, separators=(",",":")).encode()).decode()

def _unb64(s: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(s + "==").decode())

def _kb_rows(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def api_get(session, path, **params):
    t0 = time.time()
    async with session.get(f"{API_BASE_URL}{path}", params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
        result = await r.json()
        latency_ms = round((time.time() - t0) * 1000, 2)
        return result, latency_ms

async def api_post(session, path, data: dict):
    t0 = time.time()
    async with session.post(f"{API_BASE_URL}{path}", json=data, timeout=aiohttp.ClientTimeout(total=10)) as r:
        result = await r.json()
        latency_ms = round((time.time() - t0) * 1000, 2)
        return result, latency_ms

def _render_inbox(items, limit, offset, next_offset, total_pending=None):
    """Render inbox items with buttons + pagination.
    BK-4: Compact resume lines ≤60 chars: [#E12] ‎₪123.45 · author · timestamp
    BK-5: Pagination counters: X/Y · N pend"""
    rows = []
    for it in items:
        kind_short = it["kind"][0]  # 'e'/'p'/'t'
        # BK-4: Compact resume format
        # BK-8: Use fmt_amount_safe for money display (ILS only, RTL-safe)
        amount_fmt = fmt_amount_safe(it.get('amount'), it.get('currency', 'ILS'))
        author = (it.get('author') or 'unknown')[:12]  # Limit author to 12 chars
        # Extract short timestamp (MM-DD HH:MM)
        created = it.get('created_at', '')
        if created and len(created) >= 16:
            # "2025-11-12T09:31:00Z" -> "11-12 09:31"
            ts_short = f"{created[5:10]} {created[11:16]}"
        else:
            ts_short = "—"
        
        # BK-4: Resume line format: [#E12] ‎₪123.45 · author · timestamp
        title = f"[#{kind_short.upper()}{it['id']}] {amount_fmt} · {author} · {ts_short}"
        
        # Ensure ≤60 chars
        if len(title) > 60:
            title = title[:57] + "..."
        
        record_bot_metric("bot.ui.inbox.row.rendered", {
            "kind": it["kind"],
            "id": it['id'],
            "length": len(title)
        })
        
        rows.append([InlineKeyboardButton(text=title, callback_data=f"det|{_b64({'k':kind_short,'i':it['id']})}")])
        rows.append([
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"app|{_b64({'k':kind_short,'i':it['id']})}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej|{_b64({'k':kind_short,'i':it['id']})}")
        ])
    # H-BOT-1: Bulk mode button (if items > 1)
    if len(items) > 1:
        rows.append([
            InlineKeyboardButton(text="☑ Массовый выбор", callback_data="bulk_mode_on")
        ])
    
    # BK-5: Pagination nav with metrics
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"pg|{_b64({'l':limit,'o':max(0,offset-limit)})}"))
        record_bot_metric("bot.ui.page.prev_enabled", {"offset": offset, "limit": limit})
    if next_offset is not None:
        next_start = offset + limit + 1
        next_end = min(offset + 2*limit, total_pending) if total_pending else offset + 2*limit
        nav.append(InlineKeyboardButton(text=f"▶ След ({next_start}–{next_end})", callback_data=f"pg|{_b64({'l':limit,'o':next_offset})}"))
        record_bot_metric("bot.ui.page.next_enabled", {"next_offset": next_offset, "limit": limit})
    if nav:
        rows.append(nav)
    return _kb_rows(rows) if rows else None

@router.callback_query(F.data == "noop")
async def noop_cb(c: CallbackQuery):
    # BK-2A: Spinner's disabled button handler — do nothing, just inform
    await c.answer("⏱ Уже обрабатывается…")

@router.message(Command("inbox"))
async def inbox_cmd(m: Message):
    uid = m.from_user.id if m.from_user else 0
    
    # RBAC check
    if not is_foreman(uid):
        record_bot_metric("access_denied", {"user_id": uid, "command": "inbox", "reason": "not_foreman"})
        return await m.answer("🚫 Команда доступна только бригадирам.")
    
    # Throttle check
    if throttle_check(uid, "inbox", window=2.0):
        return await m.answer("⏱ Попробуйте через пару секунд")
    
    limit, offset = 5, 0
    async with aiohttp.ClientSession() as s:
        data, latency = await api_get(s, "/bot/inbox", role="foreman", state="pending", limit=limit, offset=offset, telegram_id=uid)
    
    items = data.get("items", [])
    total_pending = data.get("total", len(items))  # BK-5: total pending count
    items_hash = hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()[:16]
    record_bot_metric("inbox.open", {"count": len(items), "next_offset": data.get("next_offset"), "hash": items_hash, "latency_ms": latency})
    
    # BK-5: Header with counters
    current_page = (offset // limit) + 1
    total_pages = ((total_pending - 1) // limit) + 1 if total_pending > 0 else 1
    start_idx = offset + 1
    end_idx = min(offset + len(items), total_pending)
    header = f"📥 {start_idx}–{end_idx} из {total_pending} · стр. {current_page}/{total_pages}"
    
    kb = _render_inbox(items, limit, offset, data.get("next_offset"), total_pending)
    await m.answer(header, reply_markup=kb)

@router.callback_query(F.data.startswith("pg|"))
async def page_cb(c: CallbackQuery):
    if _debounce_check_and_mark(c):
        return await c.answer("⏱ Подождите…")
    if not c.data:
        return await c.answer("⚠️ Нет данных", show_alert=True)
    payload = _unb64(c.data.split("|", 1)[1])
    limit = int(payload.get("l") or payload.get("limit") or 5)
    offset = int(payload.get("o") or payload.get("offset") or 0)
    
    async with aiohttp.ClientSession() as s:
        data, latency = await api_get(s, "/bot/inbox", role="foreman", state="pending", limit=limit, offset=offset, telegram_id=c.from_user.id)
    
    items = data.get("items", [])
    total_pending = data.get("total", len(items))  # BK-5
    items_hash = hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()[:16]
    record_bot_metric("inbox.page", {"limit": limit, "offset": offset, "count": len(items), "hash": items_hash, "latency_ms": latency})
    
    # BK-5: Header with counters
    current_page = (offset // limit) + 1
    total_pages = ((total_pending - 1) // limit) + 1 if total_pending > 0 else 1
    start_idx = offset + 1
    end_idx = min(offset + len(items), total_pending)
    header = f"📥 {start_idx}–{end_idx} из {total_pending} · стр. {current_page}/{total_pages}"
    
    kb = _render_inbox(items, limit, offset, data.get("next_offset"), total_pending)
    if c.message and hasattr(c.message, "edit_text"):
        await c.message.edit_text(header, reply_markup=kb)
    else:
        await c.answer(f"📥 {len(items)} шт.")
    await c.answer()

@router.callback_query(F.data.startswith("det|"))
async def details_cb(c: CallbackQuery):
    if _debounce_check_and_mark(c):
        return await c.answer("⏱ Подождите…")
    if not c.data:
        return await c.answer("⚠️ Нет данных", show_alert=True)
    payload = _unb64(c.data.split("|", 1)[1])
    kind_map = {'e': 'expense', 'p': 'pending_change', 't': 'task'}
    k = str(payload.get('k') or '')
    kind = kind_map.get(k, payload.get('kind', 'expense')) or 'expense'
    kind = str(kind)
    item_id = payload.get('i') or payload.get('id') or 0
    
    async with aiohttp.ClientSession() as s:
        item, latency = await api_get(s, "/bot/item.details", kind=kind, id=item_id)
    
    record_bot_metric("item.details", {"kind": kind, "id": item_id, "latency_ms": latency})
    
    # Build details text (D3)
    text_parts = [f"📋 {kind.upper()} #{item_id}"]
    # BK-8: Use fmt_amount_safe for money display
    amount_fmt = fmt_amount_safe(item.get('amount'), item.get('currency', 'ILS'))
    text_parts.append(f"💰 Сумма: {amount_fmt}")
    text_parts.append(f"👤 Автор: {item.get('author', 'неизвестен')}")
    text_parts.append(f"📅 Создано: {item.get('created_at', 'N/A')}")
    
    # YAML breakdown (D-G4: show unknown when no coverage)
    yaml_steps = item.get("yaml_breakdown", [])
    if yaml_steps:
        text_parts.append("\n💰 Расчёт стоимости:")
        for step in yaml_steps:
            yaml_key = step.get("yaml_key", "unknown")
            value = step.get("value", "N/A")
            text_parts.append(f"  • {yaml_key} → {value}")
    else:
        text_parts.append("\n💰 Расчёт: unknown (нет данных)")
    
    # OCR (D3: show explicitly if disabled)
    ocr = item.get("ocr", {})
    if ocr and ocr.get("enabled"):
        # BK-8: Format OCR amount with fmt_amount_safe
        ocr_amount_fmt = fmt_amount_safe(ocr.get('amount'), 'ILS', '?')
        text_parts.append(f"\n🔍 OCR: сумма={ocr_amount_fmt} (уверенность: {ocr.get('amount_confidence','?')})")
        text_parts.append(f"  дата={ocr.get('date','?')} (уверенность: {ocr.get('date_confidence','?')})")
        text_parts.append(f"  продавец={ocr.get('merchant','?')} (уверенность: {ocr.get('merchant_confidence','?')})")
    else:
        text_parts.append("\n🔍 OCR: отключён")
    
    text = "\n".join(text_parts)
    
    kb = _kb_rows([
        [
            InlineKeyboardButton(text="✅ Одобрить", callback_data=f"app|{_b64({'k':(kind or 'e')[0],'i':item_id})}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej|{_b64({'k':(kind or 'e')[0],'i':item_id})}")
        ],
        [InlineKeyboardButton(text="⬅ Назад к списку", callback_data=f"pg|{_b64({'l':5,'o':0})}")]
    ])
    
    if c.message and hasattr(c.message, "edit_text"):
        await c.message.edit_text(text, reply_markup=kb)
    else:
        await c.answer("ℹ️ Детали", show_alert=True)
    await c.answer()

@router.callback_query(F.data.startswith("app|"))
async def approve_cb(c: CallbackQuery):
    if _debounce_check_and_mark(c):
        record_bot_metric("bot.ui.debounce.block", {"action": "approve"})
        return await c.answer("⏱ Уже обрабатывается…")
    await _show_spinner(c)
    uid = c.from_user.id if c.from_user else 0
    
    # DEV_MODE protection
    if DEV_MODE:
        record_bot_metric("dev_block", {"action": "approve", "user_id": uid})
        return await c.answer("⏸ DEV_MODE: действие не выполнено (тестовый режим)", show_alert=True)
    
    if not c.data:
        return await c.answer("⚠️ Нет данных", show_alert=True)
    payload = _unb64(c.data.split("|", 1)[1])
    kind_map = {'e': 'expense', 'p': 'pending_change', 't': 'task'}
    k = str(payload.get('k') or '')
    kind = kind_map.get(k, payload.get('kind', 'expense')) or 'expense'
    kind = str(kind)
    item_id = payload.get('i') or (payload.get('ids', [0])[0])
    
    async with aiohttp.ClientSession() as s:
        res, latency = await api_post(s, "/bot/approve", {
            "items": [{"kind": kind, "id": item_id}],
            "telegram_id": uid
        })
    
    # D-G2: track noop/ok/fail
    summary = res.get("summary", "")
    results = res.get("results", [])
    
    # Determine outcome from results or summary
    if results and len(results) > 0:
        item_status = results[0].get("status", "")
        outcome = "ok" if item_status == "ok" else ("noop" if item_status == "noop" else "fail")
    else:
        outcome = "ok" if "approved" in summary.lower() else ("noop" if "already" in summary.lower() or "noop" in summary.lower() else "fail")
    
    record_bot_metric("approve.click", {"count": 1, "outcome": outcome, "latency_ms": latency})
    
    # D6: Send DM to worker (if approved)
    if outcome == "ok" and res.get("worker_telegram_id"):
        try:
            bot = c.bot
            worker_msg = f"✅ Ваш {kind} #{item_id} подтверждён"
            sent = await bot.send_message(res["worker_telegram_id"], worker_msg)
            record_bot_metric("dm.sent", {"worker_id": res["worker_telegram_id"], "message_id": sent.message_id, "action": "approve"})
        except Exception as e:
            record_bot_metric("dm.fail", {"worker_id": res.get("worker_telegram_id"), "error": str(e)})
    elif outcome == "ok" and not res.get("worker_telegram_id"):
        record_bot_metric("dm.skip", {"reason": "no_telegram_id"})
    
    # H-CHAN-1: Post preview card to channel (if approved and data available)
    if outcome == "ok" and results:
        try:
            from bot.channel.preview import post_expense_preview, post_task_preview
            bot = c.bot
            item_data = results[0]  # First approved item
            
            if kind == "expense" and all(k in item_data for k in ["id", "amount", "category", "user_id", "created_at"]):
                await post_expense_preview(bot, item_data)
            elif kind == "task" and all(k in item_data for k in ["id", "task_code", "qty", "rate", "user_id", "created_at"]):
                await post_task_preview(bot, item_data)
        except Exception as e:
            # Non-blocking: channel post failure doesn't affect approve
            record_bot_metric("channel.post.error", {"kind": kind, "item_id": item_id, "error": str(e)})
    
    # BK-3: Post-result banner with editMessageText
    amount_value = res.get("amount") or (results[0].get("amount") if results else None)
    amount_str = fmt_amount_safe(amount_value) if amount_value is not None else None
    banner = render_banner("approve", outcome, kind, item_id, amount_str)
    
    # BK-3: Updated keyboard with navigation buttons
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data=f"pg|{_b64({'l':5,'o':0})}")],
        [InlineKeyboardButton(text="🔁 Обновить список", callback_data=f"pg|{_b64({'l':5,'o':0})}")]
    ])
    
    try:
        if c.message and hasattr(c.message, "edit_text"):
            await c.message.edit_text(banner, reply_markup=kb)
        else:
            await c.answer(banner, show_alert=True)
    finally:
        record_bot_metric("bot.ui.spinner.hide", {
            "chat_id": getattr(c.message.chat, "id", None) if c.message else None,
            "message_id": getattr(c.message, "message_id", None) if c.message else None,
        })

@router.callback_query(F.data.startswith("rej|"))
async def rej_ask_cb(c: CallbackQuery):
    if _debounce_check_and_mark(c):
        return await c.answer("⏱ Уже обрабатывается…")
    payload = _unb64(c.data.split("|", 1)[1])
    k = payload.get('k', payload.get('kind', ['e'])[0])  # 'e'/'p'/'t'
    i = payload.get('i', payload.get('ids', [0])[0])   # id number
    
    kb = _kb_rows([
        [InlineKeyboardButton(text="📷 Нет фото", callback_data=f"reject|{_b64({'k':k,'i':i,'r':'no_photo'})}")],
        [InlineKeyboardButton(text="💵 Неверная сумма", callback_data=f"reject|{_b64({'k':k,'i':i,'r':'bad_amount'})}")],
        [InlineKeyboardButton(text="📝 Другое...", callback_data=f"reject|{_b64({'k':k,'i':i,'r':'other'})}")],
        [InlineKeyboardButton(text="⬅ Отмена", callback_data=f"page|{_b64({'l':5,'o':0})}")]
    ])
    
    if c.message and hasattr(c.message, "reply"):
        await c.message.reply("❓ Причина отклонения:", reply_markup=kb)
    else:
        await c.answer("❓ Причина", show_alert=True)
    await c.answer()

@router.callback_query(F.data.startswith("reject|"))
async def reject_cb(c: CallbackQuery):
    if _debounce_check_and_mark(c):
        record_bot_metric("bot.ui.debounce.block", {"action": "reject"})
        return await c.answer("⏱ Уже обрабатывается…")
    await _show_spinner(c)
    uid = c.from_user.id if c.from_user else 0
    
    # DEV_MODE protection
    if DEV_MODE:
        record_bot_metric("dev_block", {"action": "reject", "user_id": uid})
        return await c.answer("⏸ DEV_MODE: действие не выполнено (тестовый режим)", show_alert=True)
    
    if not c.data:
        return await c.answer("⚠️ Нет данных", show_alert=True)
    payload = _unb64(c.data.split("|", 1)[1])
    
    # Decode short keys: k=kind_first_char, i=id, r=reason
    kind_map = {'e': 'expense', 'p': 'pending_change', 't': 'task'}
    k = str(payload.get('k') or '')
    kind = kind_map.get(k, payload.get('kind', 'expense')) or 'expense'
    kind = str(kind)
    item_id = payload.get('i') or (payload.get('ids', [0])[0])
    reason = payload.get('r', payload.get('reason', 'unspecified'))
    
    # TODO: ForceReply for "other" reason (D4 - deferred to next iteration)
    
    async with aiohttp.ClientSession() as s:
        res, latency = await api_post(s, "/bot/reject", {
            "items": [{"kind": kind, "id": item_id}],
            "reason": reason,
            "telegram_id": uid
        })
    
    summary = res.get("summary", "")
    results = res.get("results", [])
    
    # Determine outcome from results or summary
    if results and len(results) > 0:
        item_status = results[0].get("status", "")
        outcome = "ok" if item_status == "ok" else ("noop" if item_status == "noop" else "fail")
    else:
        outcome = "ok" if "rejected" in summary.lower() else ("noop" if "already" in summary.lower() or "noop" in summary.lower() else "fail")
    
    record_bot_metric("reject.click", {"count": 1, "outcome": outcome, "reason": reason, "latency_ms": latency})
    
    # D6: Send DM to worker
    if outcome == "ok" and res.get("worker_telegram_id"):
        try:
            bot = c.bot
            worker_msg = f"❌ Ваш {kind} #{item_id} отклонён\n📝 Причина: {reason}"
            sent = await bot.send_message(res["worker_telegram_id"], worker_msg)
            record_bot_metric("dm.sent", {"worker_id": res["worker_telegram_id"], "message_id": sent.message_id, "action": "reject", "reason": reason})
        except Exception as e:
            record_bot_metric("dm.fail", {"worker_id": res.get("worker_telegram_id"), "error": str(e)})
    elif outcome == "ok" and not res.get("worker_telegram_id"):
        record_bot_metric("dm.skip", {"reason": "no_telegram_id"})
    
    # BK-3: Post-result banner with editMessageText
    amount_value = res.get("amount") or (results[0].get("amount") if results else None)
    amount_str = fmt_amount_safe(amount_value) if amount_value is not None else None
    banner = render_banner("reject", outcome, kind, item_id, amount_str)
    
    # BK-3: Updated keyboard with navigation buttons
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅ Назад", callback_data=f"pg|{_b64({'l':5,'o':0})}")],
        [InlineKeyboardButton(text="🔁 Обновить список", callback_data=f"pg|{_b64({'l':5,'o':0})}")]
    ])
    
    try:
        if c.message and hasattr(c.message, "edit_text"):
            await c.message.edit_text(banner, reply_markup=kb)
        else:
            await c.answer(banner, show_alert=True)
    finally:
        record_bot_metric("bot.ui.spinner.hide", {
            "chat_id": getattr(c.message.chat, "id", None) if c.message else None,
            "message_id": getattr(c.message, "message_id", None) if c.message else None,
        })

@router.message(Command("explain"))
async def explain_cmd(m: Message):
    # D5: /explain task <id>
    parts = (m.text or "").split()
    if len(parts) < 3:
        return await m.answer("❓ Использование: /explain task <id>")
    
    task_type, task_id = parts[1], parts[2]
    if task_type != "task":
        return await m.answer("❓ Сейчас поддерживается только: /explain task <id>")
    
    try:
        task_id_int = int(task_id)
    except ValueError:
        return await m.answer("❌ ID должен быть числом")
    
    async with aiohttp.ClientSession() as s:
        try:
            breakdown, latency = await api_get(s, "/bot/pricing", kind="task", id=task_id_int)
        except Exception as e:
            record_bot_metric("explain.error", {"kind": "task", "id": task_id_int, "error": str(e)})
            return await m.answer(f"❌ Ошибка получения breakdown: {e}")
    
    record_bot_metric("explain.request", {"kind": "task", "id": task_id_int, "latency_ms": latency})
    
    # Render breakdown (D-G4: yaml_key or unknown)
    text_parts = [f"💰 Задача #{task_id_int} — Pricing breakdown:"]
    steps = breakdown.get("steps", [])
    total = 0.0
    
    if not steps:
        text_parts.append("⚠️ Breakdown: unknown (no coverage)")
    else:
        for step in steps:
            yaml_key = step.get("yaml_key", "unknown")
            value = step.get("value", 0.0)
            formula = step.get("formula", "")
            text_parts.append(f"  • {yaml_key}: {formula} = {value:.2f}")
            total += value
        text_parts.append(f"\n📊 Итого: {total:.2f} ₽")
    
    await m.answer("\n".join(text_parts))
