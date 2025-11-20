"""Admin UI for user management with inline buttons

UI Flow:
1. /admin → Main panel (👥 Users, 📊 Stats, ➕ Add)
2. Users list → Paginated (10 per page)
3. User card → [Change Role] [Toggle] [Delete]
4. Add user → Step-by-step wizard
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.orm import Session
import json
from datetime import datetime
import base64
import logging

from bot.config import get_db, is_admin
from api import crud_users

logger = logging.getLogger(__name__)
from api.models_users import UserCreate, UserUpdate

router = Router()

# FSM States for add user wizard
class AddUserStates(StatesGroup):
    waiting_telegram_id = State()
    waiting_username = State()
    waiting_role = State()

# FSM States for linking Telegram
class LinkTelegramStates(StatesGroup):
    waiting_username = State()
    waiting_confirmation = State()


# Helpers
def _b64(data: dict) -> str:
    """Encode callback data to base64 (compact)"""
    return base64.b64encode(json.dumps(data).encode()).decode()


def _unb64(data: str) -> dict:
    """Decode callback data from base64"""
    try:
        return json.loads(base64.b64decode(data.encode()).decode())
    except:
        return {}


def admin_only(func):
    """Decorator to restrict commands to admins only (uses is_admin with BOT_ADMINS fallback)"""
    from functools import wraps
    
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id if hasattr(event, 'from_user') else event.message.from_user.id
        
        if not is_admin(user_id):
            msg = "❌ Доступ запрещён. Требуется роль: admin"
            if isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            else:
                await event.reply(msg)
            return
        
        # Filter out framework-injected kwargs
        import inspect
        sig = inspect.signature(func)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        
        return await func(event, *args, **filtered_kwargs)
    return wrapper


@router.message(Command("admin"))
@admin_only
async def admin_panel(message: Message):
    """Admin panel — main menu with inline buttons"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users:0"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats")
        ],
        [
            InlineKeyboardButton(text="👔 Заказчики", callback_data="adm:clients"),
            InlineKeyboardButton(text="📅 Расписание", callback_data="adm:schedule:view")
        ],
        [
            InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="adm:add:start")
        ],
        [
            InlineKeyboardButton(text="👷 Только рабочие", callback_data="adm:filter:worker"),
            InlineKeyboardButton(text="👨‍💼 Только бригадиры", callback_data="adm:filter:foreman")
        ],
        [
            InlineKeyboardButton(text="🔧 Только админы", callback_data="adm:filter:admin"),
            InlineKeyboardButton(text="❌ Неактивные", callback_data="adm:filter:inactive")
        ]
    ])
    
    await message.reply(
        "🔧 **Админ-панель: Управление пользователями**\n\n"
        "📋 Доступные действия:\n"
        "• Просмотр и редактирование пользователей\n"
        "• Управление заказчиками\n"
        "• Просмотр расписания на завтра\n"
        "• Статистика по ролям\n"
        "• Добавление новых пользователей\n"
        "• Фильтрация по роли/статусу",
        reply_markup=kb,
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "adm:panel")
@admin_only
async def back_to_panel(callback: CallbackQuery):
    """Return to main admin panel"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users:0"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats")
        ],
        [
            InlineKeyboardButton(text="👔 Заказчики", callback_data="adm:clients"),
            InlineKeyboardButton(text="📅 Расписание", callback_data="adm:schedule:view")
        ],
        [
            InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="adm:add:start")
        ],
        [
            InlineKeyboardButton(text="👷 Только рабочие", callback_data="adm:filter:worker"),
            InlineKeyboardButton(text="👨‍💼 Только бригадиры", callback_data="adm:filter:foreman")
        ],
        [
            InlineKeyboardButton(text="🔧 Только админы", callback_data="adm:filter:admin"),
            InlineKeyboardButton(text="❌ Неактивные", callback_data="adm:filter:inactive")
        ]
    ])
    
    await callback.message.edit_text(
        "🔧 **Админ-панель: Управление пользователями**\n\n"
        "📋 Доступные действия:\n"
        "• Просмотр и редактирование пользователей\n"
        "• Управление заказчиками\n"
        "• Просмотр расписания на завтра\n"
        "• Статистика по ролям\n"
        "• Добавление новых пользователей\n"
        "• Фильтрация по роли/статусу",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()


# Alias для back_to_admin (используется в других модулях)
@router.callback_query(F.data == "back_to_admin")
@admin_only
async def back_to_admin_alias(callback: CallbackQuery):
    """Alias for back_to_panel (used by admin_clients.py)"""
    await back_to_panel(callback)


@router.callback_query(F.data == "adm:stats")
@admin_only
async def show_stats(callback: CallbackQuery):
    """Show user statistics with back button"""
    db = next(get_db())
    
    # Count users by role and status
    all_users = crud_users.list_users(db, role_filter=None, active_only=False)
    active_users = [u for u in all_users if u.active]
    inactive_users = [u for u in all_users if not u.active]
    
    workers = len([u for u in active_users if u.role == "worker"])
    foremen = len([u for u in active_users if u.role == "foreman"])
    admins = len([u for u in active_users if u.role == "admin"])
    
    text = (
        f"📊 **Статистика пользователей**\n\n"
        f"👥 Всего: {len(all_users)}\n"
        f"✅ Активных: {len(active_users)}\n"
        f"❌ Неактивных: {len(inactive_users)}\n\n"
        f"**По ролям (активные):**\n"
        f"👷 Рабочих: {workers}\n"
        f"👨‍💼 Бригадиров: {foremen}\n"
        f"🔧 Админов: {admins}"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Показать всех", callback_data="adm:users:0")],
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="adm:panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:users:"))
@admin_only
async def list_users(callback: CallbackQuery):
    """List all users with pagination (10 per page)"""
    page = int(callback.data.split(":")[-1])
    db = next(get_db())
    try:
        users = crud_users.list_users(db, role_filter=None, active_only=False, skip=page*10, limit=10)
        total = len(crud_users.list_users(db, role_filter=None, active_only=False))
        total_pages = (total + 9) // 10
        
        if not users:
            await callback.answer("Нет пользователей")
            return
        
        # Build user list with inline buttons
        kb_rows = []
        for user in users:
            role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(user.role, "❓")
            status_emoji = "✅" if user.active else "❌"
            
            # Display: имя (главное) или username/telegram_id (fallback)
            if user.name:
                display_name = user.name
            elif user.telegram_username:
                display_name = f"@{user.telegram_username}"
            elif user.telegram_id:
                display_name = f"ID {user.telegram_id}"
            else:
                display_name = f"User #{user.id}"
            
            # Main button: open user card
            kb_rows.append([
                InlineKeyboardButton(
                    text=f"{role_emoji} {status_emoji} {display_name}",
                    callback_data=f"admin:user:view:{user.id}"
                )
            ])
        
        # Pagination controls
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="◀️ Пред", callback_data=f"adm:users:{page-1}"))
        nav_row.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="adm:noop"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(text="След ▶️", callback_data=f"adm:users:{page+1}"))
        
        kb_rows.append(nav_row)
        kb_rows.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="adm:panel")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        await callback.message.edit_text(
            f"👥 **Пользователи** ({total} всего)\n"
            f"Страница {page+1}/{total_pages}\n\n"
            f"Нажмите на пользователя для редактирования",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin:filter:"))
@admin_only
async def filter_users(callback: CallbackQuery):
    """Filter users by role or status"""
    filter_type = callback.data.split(":")[-1]
    db = next(get_db())
    
    if filter_type == "inactive":
        users = crud_users.list_users(db, role_filter=None, active_only=False)
        users = [u for u in users if not u.active]
        title = "❌ Неактивные пользователи"
    else:
        users = crud_users.list_users(db, role_filter=filter_type, active_only=True)
        role_names = {"worker": "👷 Рабочие", "foreman": "👨‍💼 Бригадиры", "admin": "🔧 Админы"}
        title = role_names.get(filter_type, "Пользователи")
    
    if not users:
        await callback.answer(f"Нет пользователей в категории: {title}")
        return
    
    # Build user list
    kb_rows = []
    for user in users[:10]:  # First 10
        role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(user.role, "❓")
        status_emoji = "✅" if user.active else "❌"
        username = f"@{user.telegram_username}" if user.telegram_username else f"ID:{user.telegram_id}"
        
        kb_rows.append([
            InlineKeyboardButton(
                text=f"{role_emoji} {status_emoji} {username}",
                callback_data=f"adm:user:{user.id}"
            )
        ])
    
    kb_rows.append([InlineKeyboardButton(text="◀️ Главное меню", callback_data="adm:panel")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await callback.message.edit_text(
        f"{title}\n"
        f"Найдено: {len(users)}\n\n"
        f"Нажмите на пользователя для редактирования",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()
    
    if not users:
        await callback.answer("Нет зарегистрированных пользователей", show_alert=True)
        return
    
    text = "👥 **Пользователи (активные):**\n\n"
    kb_rows = []
    
    for user in users:
        status = "✅" if user.active else "❌"
        role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(user.role, "❓")
        
        # Display: имя (главное) или username/telegram_id (fallback)
        if user.name:
            display_name = user.name
        elif user.telegram_username:
            display_name = f"@{user.telegram_username}"
        elif user.telegram_id:
            display_name = f"ID {user.telegram_id}"
        else:
            display_name = f"User #{user.id}"
        
        text += f"{status} **{display_name}**\n"
        text += f"   Роль: {role_emoji} {user.role}\n"
        if user.daily_salary:
            text += f"   💰 {user.daily_salary} ₪/день\n"
        text += "\n"
        
        # Button for each user
        kb_rows.append([
            InlineKeyboardButton(
                text=f"👤 {display_name}",
                callback_data=f"admin:user:view:{user.id}"
            )
        ])
    
    kb_rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data="adm:panel")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:view:"))
async def view_user(callback: CallbackQuery):
    """View user details with action buttons"""
    user_id = int(callback.data.split(":")[-1])
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        status_emoji = "✅ Активен" if user.active else "❌ Неактивен"
        role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(user.role, "❓")
        
        text = f"👤 **{user.name or 'Пользователь'} #{user.id}**\n\n"
        
        if user.name:
            text += f"📝 Имя: {user.name}\n"
        if user.instagram_nickname:
            text += f"📸 Instagram: @{user.instagram_nickname}\n"
        if user.telegram_id:
            text += f"📱 Telegram ID: `{user.telegram_id}`\n"
            # Add clickable mention link
            text += f"💬 Связаться: [Открыть чат](tg://user?id={user.telegram_id})\n"
        if user.telegram_username:
            text += f"👤 Username: @{user.telegram_username}\n"
        if user.daily_salary:
            text += f"💰 Дневная зарплата: {user.daily_salary} ₪\n"
        
        text += (
            f"🎭 Роль: {role_emoji} {user.role}\n"
            f"📊 Статус: {status_emoji}\n"
            f"📅 Создан: {user.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
        
        # Action buttons
        kb_rows = [
            [InlineKeyboardButton(text="🎭 Изменить роли", callback_data=f"admin:user:roles:{user.id}")],
            [InlineKeyboardButton(text="📱 Привязать Telegram", callback_data=f"admin:user:link:telegram:{user.id}")],
            [InlineKeyboardButton(text="🔗 Пригласить в Telegram", callback_data=f"admin:user:invite:{user.id}")],
            [
                InlineKeyboardButton(
                    text="✅ Активировать" if not user.active else "❌ Деактивировать",
                    callback_data=f"admin:user:toggle:{user.id}"
                )
            ]
        ]
        
        # Add salary and data edit buttons only for workers/foremen
        if user.role in ("worker", "foreman"):
            kb_rows.append([InlineKeyboardButton(text="💰 Изменить зарплату", callback_data=f"adm:salary:{user.id}")])
            kb_rows.append([InlineKeyboardButton(text="✏️ Изменить данные", callback_data=f"adm:editdata:{user.id}")])
        
        kb_rows.extend([
            [InlineKeyboardButton(text="📋 История изменений", callback_data=f"admin:user:history:{user.id}")],
            [InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data=f"admin:user:delete:confirm:{user.id}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data="adm:users:0")]
        ])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin:user:roles:"))
@admin_only
async def edit_user_roles(callback: CallbackQuery):
    """Edit user role (single role selection)"""
    user_id = int(callback.data.split(":")[-1])
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Role buttons
        kb_rows = []
        for role in ["worker", "foreman", "admin"]:
            is_current = role == user.role
            emoji = "✅" if is_current else "⬜️"
            role_display = {"worker": "👷 Рабочий", "foreman": "👨‍💼 Бригадир", "admin": "🔧 Админ"}[role]
            
            kb_rows.append([
                InlineKeyboardButton(
                    text=f"{emoji} {role_display}",
                    callback_data=f"admin:user:setrole:{user.id}:{role}"
                )
            ])
        
        kb_rows.append([InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:user:view:{user.id}")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(user.role, "❓")
        text = (
            f"🎭 **Изменение роли**\n\n"
            f"Пользователь: @{user.telegram_username or user.telegram_id}\n"
            f"Текущая роль: {role_emoji} {user.role}\n\n"
            f"Выберите новую роль:"
        )
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin:user:setrole:"))
@admin_only
async def set_user_role(callback: CallbackQuery):
    """Set user role (immediate save)"""
    parts = callback.data.split(":")
    user_id = int(parts[3])
    new_role = parts[4]
    
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        if user.role == new_role:
            await callback.answer("Эта роль уже установлена", show_alert=True)
            return
        
        # Update role
        from api.models_users import UserUpdate
        crud_users.update_user(db, user.id, UserUpdate(role=new_role))
        
        role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(new_role, "❓")
        role_name = {"worker": "Рабочий", "foreman": "Бригадир", "admin": "Админ"}.get(new_role, new_role)
        
        await callback.answer(f"✅ Роль изменена на: {role_name}", show_alert=True)
    finally:
        db.close()
    
    # Return to user view
    await view_user(callback)  # Reuse view function
    

@router.callback_query(F.data.startswith("admin:user:toggle:"))
@admin_only
async def toggle_user_status(callback: CallbackQuery):
    """Activate/deactivate user"""
    user_id = int(callback.data.split(":")[-1])
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        from api.models_users import UserUpdate
        new_active = not user.active
        crud_users.update_user(db, user_id, UserUpdate(active=new_active))
        
        if new_active:
            await callback.answer("✅ Пользователь активирован", show_alert=True)
        else:
            await callback.answer("✅ Пользователь деактивирован", show_alert=True)
    finally:
        db.close()
    
    # Refresh view
    await view_user(callback)


@router.callback_query(F.data.startswith("admin:user:delete:confirm:"))
@admin_only
async def confirm_delete_user(callback: CallbackQuery):
    """Confirm user deletion"""
    user_id = int(callback.data.split(":")[-1])
    
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        # Prevent self-deletion
        if user.telegram_id and user.telegram_id == callback.from_user.id:
            await callback.answer("❌ Нельзя удалить самого себя", show_alert=True)
            return
    
        display_name = user.name or user.telegram_username or f"ID {user_id}"
        
        text = (
            f"⚠️ **ВНИМАНИЕ: УДАЛЕНИЕ ПОЛЬЗОВАТЕЛЯ**\n\n"
            f"👤 Пользователь: {display_name}\n"
            f"🎭 Роль: {user.role}\n\n"
            f"❗ Это действие **необратимо**!\n"
            f"Будут удалены:\n"
            f"• Профиль пользователя\n"
            f"• Все связанные данные\n\n"
            f"Вы уверены?"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin:user:delete:execute:{user_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:user:view:{user_id}")
            ]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin:user:delete:execute:"))
@admin_only
async def execute_delete_user(callback: CallbackQuery):
    """Execute user deletion"""
    user_id = int(callback.data.split(":")[-1])
    
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        user_name = user.name if user else f"ID {user_id}"
        
        success = crud_users.delete_user(db, user_id)
        
        if success:
            text = (
                f"✅ **Пользователь удалён**\n\n"
                f"👤 {user_name}\n\n"
                f"Все данные успешно удалены из системы."
            )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ К списку пользователей", callback_data="adm:users:0")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="adm:panel")]
            ])
            
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        else:
            await callback.answer("❌ Ошибка удаления: пользователь не найден", show_alert=True)
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin:user:history:"))
@admin_only
async def view_user_history(callback: CallbackQuery):
    """View user change history"""
    user_id = int(callback.data.split(":")[-1])
    
    text = (
        f"📜 **История изменений пользователя #{user_id}**\n\n"
        f"⚠️ Функция в разработке\n\n"
        f"Будет отображать:\n"
        f"• Изменения роли\n"
        f"• Активация/деактивация\n"
        f"• Изменения данных"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin:user:view:{user_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:user:invite:"))
@admin_only
async def generate_invite_link(callback: CallbackQuery):
    """Generate invite link for worker registration"""
    user_id = int(callback.data.split(":")[-1])
    
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        # Generate unique invite token (base64 encoded user_id + timestamp)
        import base64
        import time
        invite_token = base64.urlsafe_b64encode(f"{user.id}:{int(time.time())}".encode()).decode().rstrip('=')
        
        # Get bot username
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username
        
        # Generate deep link
        invite_link = f"https://t.me/{bot_username}?start=invite_{invite_token}"
        
        user_display_name = user.name or f"ID {user.id}"
        
        # Send instruction message first
        instruction_text = (
            f"🔗 <b>Ссылка-приглашение создана!</b>\n\n"
            f"👤 Сотрудник: {user_display_name}\n\n"
            f"📋 <b>Инструкция:</b>\n"
            f"1. Скопируйте ссылку из следующего сообщения\n"
            f"2. Отправьте сотруднику (WhatsApp/SMS/Email)\n"
            f"3. Сотрудник кликает по ссылке\n"
            f"4. Автоматически откроется бот\n"
            f"5. Регистрация завершена! ✅\n\n"
            f"💡 Ссылка действительна бессрочно"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад к карточке", callback_data=f"admin:user:view:{user_id}")],
            [InlineKeyboardButton(text="◀️ К списку", callback_data="adm:users:0")]
        ])
        
        await callback.message.edit_text(instruction_text, reply_markup=kb, parse_mode="HTML")
        
        # Send link as separate message for easy copying
        link_message = (
            f"🔗 <b>Ссылка для {user_display_name}:</b>\n\n"
            f"{invite_link}\n\n"
            f"👆 <i>Нажмите на ссылку для копирования</i>"
        )
        
        await callback.message.answer(link_message, parse_mode="HTML")
        await callback.answer("✅ Ссылка создана! Отправьте её сотруднику")
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin:user:link:telegram:"))
@admin_only
async def start_link_telegram(callback: CallbackQuery, state: FSMContext):
    """Start linking Telegram username to worker"""
    user_id = int(callback.data.split(":")[-1])
    
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        await state.set_state(LinkTelegramStates.waiting_username)
        user_display_name = user.name or f"ID {user.id}"
        await state.update_data(user_id=user_id, user_name=user_display_name)
        
        current_link = ""
        if user.telegram_username:
            current_link = f"\n📱 Текущая привязка: @{user.telegram_username}"
        elif user.telegram_id:
            current_link = f"\n📱 Telegram ID: {user.telegram_id}"
        
        text = (
            f"📱 **Привязка Telegram аккаунта**\n\n"
            f"👤 Рабочий: {user_display_name}{current_link}\n\n"
            f"Введите **username** или **номер телефона** рабочего:\n\n"
            f"**Вариант 1: Username**\n"
            f"• Формат: `@username` или `username`\n"
            f"• Пример: `@worker123` или `worker123`\n\n"
            f"**Вариант 2: Номер телефона (ID)**\n"
            f"• Формат: только цифры\n"
            f"• Пример: `1234567890`\n"
            f"• Узнать ID: попросить рабочего написать боту /start\n\n"
            f"💡 После привязки рабочий сможет:\n"
            f"• Использовать команды бота\n"
            f"• Просматривать свою карточку\n"
            f"• Работать со сменами и расходами"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:user:link:cancel:{user_id}")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer()
    finally:
        db.close()


@router.callback_query(F.data.startswith("admin:user:link:cancel:"))
@admin_only
async def cancel_link_telegram(callback: CallbackQuery, state: FSMContext):
    """Cancel Telegram linking"""
    await state.clear()
    user_id = int(callback.data.split(":")[-1])
    
    # Return to user card
    db = next(get_db())
    try:
        user = crud_users.get_user_by_id(db, user_id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return
        
        # Build user card text
        user_display_name = user.name or f"ID {user.id}"
        instagram_info = f"📷 Instagram: @{user.instagram_nickname}" if user.instagram_nickname else "📷 Instagram: не указан"
        telegram_info = f"📱 Telegram: @{user.telegram_username}" if user.telegram_username else (f"📱 Telegram ID: {user.telegram_id}" if user.telegram_id else "📱 Telegram: не привязан")
        salary_info = f"💰 Зарплата: {user.daily_salary} ₪/день" if user.daily_salary else "💰 Зарплата: не указана"
        role_emoji = "👑" if user.role == "admin" else "👷" if user.role == "worker" else "👨‍💼"
        status_emoji = "✅" if user.active else "❌"
        
        text = (
            f"👤 **{user_display_name}**\n\n"
            f"{instagram_info}\n"
            f"{telegram_info}\n"
            f"{salary_info}\n"
            f"🎭 Роль: {role_emoji} {user.role}\n"
            f"📊 Статус: {status_emoji} {'Активен' if user.active else 'Неактивен'}"
        )
        
        # Build buttons
        kb_rows = []
        kb_rows.append([InlineKeyboardButton(text="🎭 Изменить роль", callback_data=f"admin:user:role:{user.id}")])
        kb_rows.append([InlineKeyboardButton(text="📱 Привязать Telegram", callback_data=f"admin:user:link:telegram:{user.id}")])
        
        if user.active:
            kb_rows.append([InlineKeyboardButton(text="❌ Деактивировать", callback_data=f"admin:user:toggle:{user.id}")])
        else:
            kb_rows.append([InlineKeyboardButton(text="✅ Активировать", callback_data=f"admin:user:toggle:{user.id}")])
        
        kb_rows.append([InlineKeyboardButton(text="📜 История изменений", callback_data=f"admin:user:history:{user.id}")])
        kb_rows.append([InlineKeyboardButton(text="🗑️ Удалить пользователя", callback_data=f"admin:user:delete:{user.id}")])
        kb_rows.append([InlineKeyboardButton(text="◀️ К списку", callback_data="adm:users:0")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        await callback.answer("❌ Привязка отменена")
    finally:
        db.close()


@router.message(LinkTelegramStates.waiting_username)
async def receive_telegram_username(message: Message, state: FSMContext):
    """Receive and validate Telegram username or phone number (ID)"""
    input_text = message.text.strip()
    
    # Determine if input is phone number (ID) or username
    is_phone = input_text.isdigit()
    
    if is_phone:
        # Phone number (Telegram ID) mode
        telegram_id = int(input_text)
        
        if telegram_id < 1000000:  # Telegram IDs are typically 9-10 digits
            await message.reply(
                "❌ Неверный формат Telegram ID\n\n"
                "ID должен быть:\n"
                "• Только цифры\n"
                "• Минимум 7 цифр\n\n"
                "💡 Попросите рабочего написать боту /start\n"
                "и скопируйте его ID из логов.\n\n"
                "Попробуйте снова:"
            )
            return
        
        # Process as telegram_id
        link_type = "telegram_id"
        link_value = telegram_id
        link_display = f"ID {telegram_id}"
    else:
        # Username mode
        username = input_text.lstrip("@")
        
        # Validate username format
        if not username or len(username) < 5 or len(username) > 32:
            await message.reply(
                "❌ Неверный формат username\n\n"
                "Username должен быть:\n"
                "• От 5 до 32 символов\n"
                "• Только латиница, цифры и подчёркивания\n\n"
                "Попробуйте снова:"
            )
            return
        
        if not username.replace("_", "").isalnum():
            await message.reply(
                "❌ Username может содержать только:\n"
                "• Латинские буквы (a-z, A-Z)\n"
                "• Цифры (0-9)\n"
                "• Подчёркивания (_)\n\n"
                "Попробуйте снова:"
            )
            return
        
        # Process as username
        link_type = "telegram_username"
        link_value = username
        link_display = f"@{username}"
    
    data = await state.get_data()
    user_id = data.get("user_id")
    user_name = data.get("user_name", "Рабочий")
    
    # Try to find Telegram user by username or ID
    db = next(get_db())
    try:
        # Check if already linked to another user
        if link_type == "telegram_username":
            existing = db.query(crud_users.User).filter(
                crud_users.User.telegram_username == link_value,
                crud_users.User.id != user_id
            ).first()
        else:  # telegram_id
            existing = db.query(crud_users.User).filter(
                crud_users.User.telegram_id == link_value,
                crud_users.User.id != user_id
            ).first()
        
        if existing:
            await message.reply(
                f"⚠️ {link_display} уже привязан к:\n"
                f"• {existing.name or 'ID ' + str(existing.id)}\n\n"
                f"Введите другие данные или отмените:"
            )
            return
        
        # Update user with Telegram data
        from api.models_users import UserUpdate
        update_data = {}
        if link_type == "telegram_username":
            update_data["telegram_username"] = link_value
        else:  # telegram_id
            update_data["telegram_id"] = link_value
        
        updated_user = crud_users.update_user(
            db, 
            user_id, 
            UserUpdate(**update_data)
        )
        
        if updated_user:
            await state.clear()
            
            # Получаем информацию о зарплате для сообщения
            user = db.query(crud_users.User).filter(crud_users.User.id == user_id).first()
            salary_info = f"💰 Дневная зарплата: {user.daily_salary} ₪" if user and user.daily_salary else ""
            
            # Отправляем приветственное сообщение рабочему
            try:
                worker_message = (
                    f"✅ **Добро пожаловать на работу!**\n\n"
                    f"👤 Ваше имя: {user_name}\n"
                    f"{salary_info}\n\n"
                    f"📱 Ваш Telegram успешно привязан к системе учёта.\n\n"
                    f"**Доступные команды:**\n"
                    f"• /me — посмотреть свою карточку\n"
                    f"• /in — начать смену\n"
                    f"• /out — закончить смену\n"
                    f"• /expense — добавить расход\n\n"
                    f"Удачной работы! 👷"
                )
                
                # Пытаемся отправить сообщение по @username или ID
                if link_type == "telegram_username":
                    chat_target = f"@{link_value}"
                else:
                    chat_target = link_value
                
                await message.bot.send_message(
                    chat_id=chat_target,
                    text=worker_message,
                    parse_mode="Markdown"
                )
                logger.info(f"Welcome message sent to {link_display}")
                message_sent = True
            except Exception as e:
                logger.warning(f"Failed to send welcome message to {link_display}: {e}")
                message_sent = False
            
            # Сообщение админу
            if message_sent:
                text = (
                    f"✅ **Telegram успешно привязан!**\n\n"
                    f"👤 Рабочий: {user_name}\n"
                    f"📱 {link_display}\n\n"
                    f"✉️ Рабочему отправлено приветственное сообщение с инструкциями."
                )
            else:
                text = (
                    f"✅ **Telegram привязан**\n\n"
                    f"👤 Рабочий: {user_name}\n"
                    f"📱 {link_display}\n\n"
                    f"⚠️ Не удалось отправить сообщение рабочему.\n"
                    f"Возможно, он ещё не запустил бота.\n\n"
                    f"**Попросите его:**\n"
                    f"1. Найти бота: @Ollama_axon_bot\n"
                    f"2. Нажать /start"
                )
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Показать карточку", callback_data=f"admin:user:view:{user_id}")],
                [InlineKeyboardButton(text="◀️ К списку", callback_data="adm:users:0")]
            ])
            
            await message.answer(text, reply_markup=kb, parse_mode="Markdown")
        else:
            await message.reply("❌ Ошибка обновления. Попробуйте позже.")
            await state.clear()
    finally:
        db.close()


@router.callback_query(F.data == "admin:panel")
@admin_only
async def back_to_panel(callback: CallbackQuery):
    """Return to admin panel"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data="adm:users:0"),
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm:stats")
        ],
        [
            InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="adm:add:start")
        ]
    ])
    
    await callback.message.edit_text(
        "🔧 **Админ-панель**\n\nВыберите действие:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()

