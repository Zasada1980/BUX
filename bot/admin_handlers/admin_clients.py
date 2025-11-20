"""Admin client management handlers."""
import sqlite3
from datetime import datetime
from aiogram import F, Router, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from bot.config import DB_PATH, BOT_ADMINS

router = Router()


class AddClientStates(StatesGroup):
    """FSM states for adding client."""
    waiting_company_name = State()
    waiting_nickname1 = State()
    waiting_nickname2 = State()
    waiting_phone = State()
    waiting_daily_rate = State()


def _is_admin(telegram_id: int) -> bool:
    """Check if user is admin."""
    return telegram_id in BOT_ADMINS


def _get_clients(page: int = 0, per_page: int = 10, active_only: bool = True):
    """Get paginated clients list."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    offset = page * per_page
    where = "WHERE is_active=1" if active_only else ""
    
    cur.execute(f"""
        SELECT id, company_name, nickname1, nickname2, phone, daily_rate, is_active
        FROM clients
        {where}
        ORDER BY company_name
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    
    clients = [dict(row) for row in cur.fetchall()]
    
    # Get total count
    cur.execute(f"SELECT COUNT(*) as cnt FROM clients {where}")
    total = cur.fetchone()["cnt"]
    
    conn.close()
    return clients, total


def _get_client_by_id(client_id: int):
    """Get client by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM clients WHERE id=?", (client_id,))
    client = cur.fetchone()
    conn.close()
    return dict(client) if client else None


def _create_client(company_name: str, nickname1: str, nickname2: str, phone: str, daily_rate: int):
    """Create new client."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO clients (company_name, nickname1, nickname2, phone, daily_rate, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
    """, (company_name, nickname1, nickname2 or None, phone or None, daily_rate or None))
    client_id = cur.lastrowid
    conn.commit()
    conn.close()
    return client_id


def _update_client(client_id: int, **kwargs):
    """Update client fields."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    set_parts = []
    values = []
    for k, v in kwargs.items():
        if k in ["company_name", "nickname1", "nickname2", "phone", "daily_rate", "is_active"]:
            set_parts.append(f"{k}=?")
            values.append(v)
    
    if not set_parts:
        conn.close()
        return
    
    set_parts.append("updated_at=CURRENT_TIMESTAMP")
    values.append(client_id)
    
    sql = f"UPDATE clients SET {', '.join(set_parts)} WHERE id=?"
    cur.execute(sql, values)
    conn.commit()
    conn.close()


def _delete_client(client_id: int):
    """Soft delete client (set is_active=0)."""
    _update_client(client_id, is_active=0)


@router.callback_query(F.data == "admin:clients")
async def show_clients_list(callback: CallbackQuery, bot: Bot):
    """Show clients list (page 0)."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.answer()
    await _render_clients_page(callback, bot, page=0)


async def _render_clients_page(callback: CallbackQuery, bot: Bot, page: int):
    """Render clients page with pagination."""
    clients, total = _get_clients(page=page, per_page=10)
    
    if not clients and page == 0:
        # No clients
        text = "📋 <b>Список заказчиков</b>\n\n❌ Заказчиков пока нет"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить заказчика", callback_data="admin:client:new")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="admin:panel")]
        ])
        await bot.edit_message_text(
            text,
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            reply_markup=kb,
            parse_mode="HTML"
        )
        return
    
    # Build list
    lines = ["📋 <b>Список заказчиков</b>\n"]
    for cl in clients:
        name = cl["company_name"]
        nick = cl["nickname1"]
        rate = f"₪{cl['daily_rate']}" if cl["daily_rate"] else "—"
        lines.append(f"• <b>{name}</b> ({nick}) — {rate}")
    
    # Pagination info
    total_pages = (total + 9) // 10
    lines.append(f"\n📄 Страница {page+1}/{total_pages} • Всего: {total}")
    
    text = "\n".join(lines)
    
    # Buttons
    kb_rows = []
    
    # Client buttons (edit)
    for cl in clients:
        kb_rows.append([InlineKeyboardButton(
            text=f"✏️ {cl['company_name']}",
            callback_data=f"admin:client:edit:{cl['id']}"
        )])
    
    # Pagination
    pag_row = []
    if page > 0:
        pag_row.append(InlineKeyboardButton(text="◀ Назад", callback_data=f"admin:clients:page:{page-1}"))
    if (page + 1) * 10 < total:
        pag_row.append(InlineKeyboardButton(text="Вперёд ▶", callback_data=f"admin:clients:page:{page+1}"))
    if pag_row:
        kb_rows.append(pag_row)
    
    # Add new
    kb_rows.append([InlineKeyboardButton(text="➕ Добавить заказчика", callback_data="admin:client:new")])
    kb_rows.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="admin:panel")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await bot.edit_message_text(
        text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin:clients:page:"))
async def clients_page_handler(callback: CallbackQuery, bot: Bot):
    """Handle pagination."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    page = int(callback.data.split(":")[-1])
    await callback.answer()
    await _render_clients_page(callback, bot, page)


@router.callback_query(F.data == "admin:client:new")
async def start_add_client(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Start wizard for adding client."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(AddClientStates.waiting_company_name)
    
    text = (
        "➕ <b>Добавление заказчика</b>\n\n"
        "Шаг 1/5: Введите название фирмы или имя заказчика\n"
        "(это будет видно всем рабочим)"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:client:cancel")]
    ])
    
    await bot.edit_message_text(
        text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.message(AddClientStates.waiting_company_name)
async def receive_company_name(message: Message, state: FSMContext):
    """Receive company name."""
    company_name = message.text.strip()
    if not company_name or len(company_name) > 200:
        await message.answer("❌ Название должно быть от 1 до 200 символов. Попробуйте ещё раз:")
        return
    
    await state.update_data(company_name=company_name)
    await state.set_state(AddClientStates.waiting_nickname1)
    
    text = (
        f"✅ Название: <b>{company_name}</b>\n\n"
        f"Шаг 2/5: Введите основной никнейм заказчика\n"
        f"(короткое имя для быстрой идентификации, макс 100 символов)"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(AddClientStates.waiting_nickname1)
async def receive_nickname1(message: Message, state: FSMContext):
    """Receive primary nickname."""
    nickname1 = message.text.strip()
    if not nickname1 or len(nickname1) > 100:
        await message.answer("❌ Никнейм должен быть от 1 до 100 символов. Попробуйте ещё раз:")
        return
    
    await state.update_data(nickname1=nickname1)
    await state.set_state(AddClientStates.waiting_nickname2)
    
    text = (
        f"✅ Никнейм 1: <b>{nickname1}</b>\n\n"
        f"Шаг 3/5: Введите альтернативный никнейм (или 'пропустить')\n"
        f"(опционально, макс 100 символов)"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(AddClientStates.waiting_nickname2)
async def receive_nickname2(message: Message, state: FSMContext):
    """Receive secondary nickname."""
    nickname2 = message.text.strip()
    if nickname2.lower() in ["пропустить", "skip", "-", ""]:
        nickname2 = None
    elif len(nickname2) > 100:
        await message.answer("❌ Никнейм слишком длинный (макс 100 символов). Попробуйте ещё раз:")
        return
    
    await state.update_data(nickname2=nickname2)
    await state.set_state(AddClientStates.waiting_phone)
    
    text = (
        f"Шаг 4/5: Введите номер телефона (или 'пропустить')\n"
        f"(только для админов, макс 20 символов)"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(AddClientStates.waiting_phone)
async def receive_phone(message: Message, state: FSMContext):
    """Receive phone."""
    phone = message.text.strip()
    if phone.lower() in ["пропустить", "skip", "-", ""]:
        phone = None
    elif len(phone) > 20:
        await message.answer("❌ Телефон слишком длинный (макс 20 символов). Попробуйте ещё раз:")
        return
    
    await state.update_data(phone=phone)
    await state.set_state(AddClientStates.waiting_daily_rate)
    
    text = (
        f"Шаг 5/5: Введите цену за рабочий день в шекелях (число) или 'пропустить'\n"
        f"(только для админов)"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(AddClientStates.waiting_daily_rate)
async def receive_daily_rate(message: Message, state: FSMContext, bot: Bot):
    """Receive daily rate and create client."""
    daily_rate_str = message.text.strip()
    daily_rate = None
    
    if daily_rate_str.lower() not in ["пропустить", "skip", "-", ""]:
        try:
            daily_rate = int(daily_rate_str)
            if daily_rate <= 0:
                await message.answer("❌ Цена должна быть положительным числом. Попробуйте ещё раз:")
                return
        except ValueError:
            await message.answer("❌ Введите число (например: 300) или 'пропустить'")
            return
    
    # Get all data
    data = await state.get_data()
    company_name = data["company_name"]
    nickname1 = data["nickname1"]
    nickname2 = data.get("nickname2")
    phone = data.get("phone")
    
    # Create client
    client_id = _create_client(company_name, nickname1, nickname2, phone, daily_rate)
    await state.clear()
    
    text = (
        f"✅ <b>Заказчик создан!</b>\n\n"
        f"ID: {client_id}\n"
        f"Название: {company_name}\n"
        f"Никнейм 1: {nickname1}\n"
        f"Никнейм 2: {nickname2 or '—'}\n"
        f"Телефон: {phone or '—'}\n"
        f"Цена/день: {f'₪{daily_rate}' if daily_rate else '—'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 К списку заказчиков", callback_data="admin:clients")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="admin:panel")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "admin:client:cancel")
async def cancel_add_client(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Cancel wizard."""
    await state.clear()
    await callback.answer("Отменено")
    await show_clients_list(callback, bot)


@router.callback_query(F.data.startswith("admin:client:edit:"))
async def edit_client_menu(callback: CallbackQuery, bot: Bot):
    """Show edit menu for client."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    client_id = int(callback.data.split(":")[-1])
    client = _get_client_by_id(client_id)
    
    if not client:
        await callback.answer("Заказчик не найден", show_alert=True)
        return
    
    await callback.answer()
    
    text = (
        f"✏️ <b>Редактирование заказчика</b>\n\n"
        f"ID: {client['id']}\n"
        f"Название: <b>{client['company_name']}</b>\n"
        f"Никнейм 1: {client['nickname1']}\n"
        f"Никнейм 2: {client['nickname2'] or '—'}\n"
        f"Телефон: {client['phone'] or '—'}\n"
        f"Цена/день: {'₪' + str(client['daily_rate']) if client['daily_rate'] else '—'}\n"
        f"Статус: {'🟢 Активен' if client['is_active'] else '🔴 Отключён'}"
    )
    
    kb_rows = []
    
    # Toggle active status
    if client['is_active']:
        kb_rows.append([InlineKeyboardButton(
            text="🔴 Отключить заказчика",
            callback_data=f"admin:client:disable:{client_id}"
        )])
    else:
        kb_rows.append([InlineKeyboardButton(
            text="🟢 Активировать заказчика",
            callback_data=f"admin:client:enable:{client_id}"
        )])
    
    kb_rows.append([InlineKeyboardButton(text="◀ К списку заказчиков", callback_data="admin:clients")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await bot.edit_message_text(
        text,
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("admin:client:disable:"))
async def disable_client(callback: CallbackQuery, bot: Bot):
    """Disable client."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    client_id = int(callback.data.split(":")[-1])
    _update_client(client_id, is_active=0)
    
    await callback.answer("✅ Заказчик отключён")
    await edit_client_menu(callback, bot)


@router.callback_query(F.data.startswith("admin:client:enable:"))
async def enable_client(callback: CallbackQuery, bot: Bot):
    """Enable client."""
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа", show_alert=True)
        return
    
    client_id = int(callback.data.split(":")[-1])
    _update_client(client_id, is_active=1)
    
    await callback.answer("✅ Заказчик активирован")
    await edit_client_menu(callback, bot)
