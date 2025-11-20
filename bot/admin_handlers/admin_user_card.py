"""User card UI with action buttons

User card shows:
- User ID, username, role, status
- Action buttons: Change Role, Toggle Active, Delete
- Back to list button
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from decimal import Decimal, InvalidOperation

from bot.config import get_db
from api import crud_users
from api.models_users import UserUpdate

router = Router()


class EditSalaryStates(StatesGroup):
    waiting_salary = State()

class EditDataStates(StatesGroup):
    choosing_field = State()  # Выбор: имя, username или телефон
    waiting_name = State()    # Ввод нового имени
    waiting_username = State() # Ввод нового username
    waiting_phone = State()   # Ввод нового телефона


def admin_only(func):
    """Decorator to restrict commands to admins only"""
    async def wrapper(event, *args, **kwargs):
        # Get user_id correctly from callback or message
        if hasattr(event, 'from_user'):
            user_id = event.from_user.id
        elif hasattr(event, 'message') and hasattr(event.message, 'from_user'):
            user_id = event.message.from_user.id
        else:
            await event.answer("❌ Не удалось определить пользователя")
            return
        
        db = next(get_db())
        user = crud_users.get_user_by_telegram_id(db, user_id)
        if not user or user.role != "admin":
            await event.answer("❌ Доступ запрещён. Требуется роль: admin")
            return
        
        return await func(event, *args, **kwargs)
    return wrapper


@router.callback_query(F.data.startswith("admin:user:"))
@admin_only
async def show_user_card(callback: CallbackQuery, bot: Bot):
    """Show user card with action buttons"""
    user_id = int(callback.data.split(":")[-1])
    db = next(get_db())
    
    user = crud_users.get_user_by_id(db, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Role emoji
    role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(user.role, "❓")
    role_name = {"worker": "Рабочий", "foreman": "Бригадир", "admin": "Админ"}.get(user.role, "Неизвестно")
    
    # Status
    status_emoji = "✅" if user.active else "🔒"
    status_text = "Активен" if user.active else "Неактивен"
    
    # Username
    username = f"@{user.telegram_username}" if user.telegram_username else "Нет username"
    
    # Salary (only for workers/foremen)
    salary_line = ""
    if user.role in ("worker", "foreman") and user.daily_salary:
        salary_line = f"\n💰 Зарплата: ₪{user.daily_salary:.2f}/день"
    
    text = (
        f"👤 **Карточка пользователя**\n\n"
        f"🆔 ID: `{user.id}`\n"
        f"📱 Telegram ID: `{user.telegram_id}`\n"
        f"👤 Username: {username}\n"
        f"🎭 Роль: {role_emoji} {role_name}\n"
        f"📊 Статус: {status_emoji} {status_text}"
        f"{salary_line}\n"
        f"📅 Создан: {user.created_at.strftime('%d.%m.%Y %H:%M')}"
    )
    
    # Action buttons
    buttons = [
        [
            InlineKeyboardButton(text="🔄 Изменить роль", callback_data=f"admin:role:{user.id}"),
            InlineKeyboardButton(
                text="🔓 Активировать" if not user.active else "🔒 Деактивировать",
                callback_data=f"admin:toggle:{user.id}"
            )
        ]
    ]
    
    # Add salary and data edit buttons only for workers/foremen
    if user.role in ("worker", "foreman"):
        buttons.append([
            InlineKeyboardButton(text="💰 Изменить зарплату", callback_data=f"admin:salary:{user.id}")
        ])
        buttons.append([
            InlineKeyboardButton(text="✏️ Изменить данные", callback_data=f"admin:editdata:{user.id}")
        ])
    
    buttons.extend([
        [
            InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"admin:delete:{user.id}:confirm")
        ],
        [
            InlineKeyboardButton(text="◀️ К списку", callback_data="admin:users:0")
        ]
    ])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:role:"))
@admin_only
async def change_role_menu(callback: CallbackQuery):
    """Show role selection menu"""
    user_id = int(callback.data.split(":")[-1])
    db = next(get_db())
    
    user = crud_users.get_user_by_id(db, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👷 Рабочий", callback_data=f"admin:setrole:{user.id}:worker"),
            InlineKeyboardButton(text="👨‍💼 Бригадир", callback_data=f"admin:setrole:{user.id}:foreman")
        ],
        [
            InlineKeyboardButton(text="🔧 Админ", callback_data=f"admin:setrole:{user.id}:admin")
        ],
        [
            InlineKeyboardButton(text="◀️ Отмена", callback_data=f"admin:user:{user.id}")
        ]
    ])
    
    await callback.message.edit_text(
        f"🔄 **Изменение роли**\n\n"
        f"Пользователь: {user.telegram_username or user.telegram_id}\n"
        f"Текущая роль: {user.role}\n\n"
        f"Выберите новую роль:",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:setrole:"))
@admin_only
async def set_role(callback: CallbackQuery):
    """Set new role for user"""
    parts = callback.data.split(":")
    user_id = int(parts[2])
    new_role = parts[3]
    
    db = next(get_db())
    user = crud_users.get_user_by_id(db, user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    old_role = user.role
    
    # Update role
    updated = crud_users.update_user(db, user_id, UserUpdate(role=new_role))
    
    if updated:
        role_emoji = {"worker": "👷", "foreman": "👨‍💼", "admin": "🔧"}.get(new_role, "❓")
        await callback.answer(f"✅ Роль изменена: {old_role} → {new_role}")
        
        # Return to user card
        await show_user_card(callback)
    else:
        await callback.answer("❌ Ошибка обновления роли")


@router.callback_query(F.data.startswith("admin:toggle:"))
@admin_only
async def toggle_active(callback: CallbackQuery):
    """Toggle user active status"""
    user_id = int(callback.data.split(":")[-1])
    db = next(get_db())
    
    user = crud_users.get_user_by_id(db, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Toggle status
    new_status = not user.active
    updated = crud_users.update_user(db, user_id, UserUpdate(active=new_status))
    
    if updated:
        status_text = "активирован ✅" if new_status else "деактивирован 🔒"
        await callback.answer(f"Пользователь {status_text}")
        
        # Return to user card
        await show_user_card(callback)
    else:
        await callback.answer("❌ Ошибка обновления статуса")


@router.callback_query(F.data.startswith("admin:delete:") & F.data.endswith(":confirm"))
@admin_only
async def confirm_delete(callback: CallbackQuery):
    """Show delete confirmation"""
    user_id = int(callback.data.split(":")[2])
    db = next(get_db())
    
    user = crud_users.get_user_by_id(db, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"admin:delete:{user.id}:execute"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:user:{user.id}")
        ]
    ])
    
    await callback.message.edit_text(
        f"⚠️ **Подтверждение удаления**\n\n"
        f"Вы уверены, что хотите удалить пользователя?\n\n"
        f"ID: {user.id}\n"
        f"Telegram ID: {user.telegram_id}\n"
        f"Username: {user.telegram_username or 'Нет'}\n"
        f"Роль: {user.role}\n\n"
        f"⚠️ Это действие необратимо!",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:delete:") & F.data.endswith(":execute"))
@admin_only
async def execute_delete(callback: CallbackQuery):
    """Execute user deletion"""
    user_id = int(callback.data.split(":")[2])
    db = next(get_db())
    
    user = crud_users.get_user_by_id(db, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Delete user
    success = crud_users.delete_user(db, user_id)
    
    if success:
        await callback.answer(f"✅ Пользователь {user.telegram_id} удалён")
        
        # Return to user list
        await callback.message.edit_text(
            "🗑️ **Пользователь удалён**\n\n"
            "Возвращаемся к списку...",
            parse_mode="Markdown"
        )
        
        # Redirect to list after 1 second
        import asyncio
        from bot.admin_handlers.admin_users import show_user_list
        await asyncio.sleep(1)
        await show_user_list(callback)
    else:
        await callback.answer("❌ Ошибка удаления пользователя")


@router.callback_query(F.data.startswith("admin:salary:"))
async def start_edit_salary(callback: CallbackQuery, state: FSMContext):
    """Start salary editing wizard"""
    user_id = int(callback.data.split(":")[-1])
    db = next(get_db())
    
    user = crud_users.get_user_by_id(db, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Store user_id in state
    await state.update_data(user_id=user_id)
    await state.set_state(EditSalaryStates.waiting_salary)
    
    current_salary = f"₪{user.daily_salary:.2f}" if user.daily_salary else "не указана"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Отмена", callback_data=f"admin:salary:cancel:{user_id}")]
    ])
    
    await callback.message.edit_text(
        f"💰 **Изменение зарплаты**\n\n"
        f"Пользователь: {user.name or user.telegram_username or user.telegram_id}\n"
        f"Текущая зарплата: {current_salary}\n\n"
        f"Введите новую дневную зарплату (только число, например: 500):",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:salary:cancel:"))
async def cancel_edit_salary(callback: CallbackQuery, state: FSMContext):
    """Cancel salary editing"""
    await state.clear()
    user_id = int(callback.data.split(":")[-1])
    
    # Return to user card
    callback.data = f"admin:user:{user_id}"
    await show_user_card(callback)


@router.message(EditSalaryStates.waiting_salary)
async def receive_new_salary(message: Message, state: FSMContext):
    """Receive and validate new salary"""
    data = await state.get_data()
    user_id = data.get("user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: пользователь не найден")
        await state.clear()
        return
    
    # Validate salary
    try:
        salary = Decimal(message.text.strip())
        if salary <= 0:
            await message.answer(
                "❌ Зарплата должна быть положительным числом.\n"
                "Попробуйте снова:"
            )
            return
    except (InvalidOperation, ValueError):
        await message.answer(
            "❌ Неверный формат. Введите число (например: 500).\n"
            "Попробуйте снова:"
        )
        return
    
    # Update salary
    db = next(get_db())
    user = crud_users.get_user_by_id(db, user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    old_salary = user.daily_salary
    updated = crud_users.update_user(db, user_id, UserUpdate(daily_salary=salary))
    
    if updated:
        old_salary_str = f"₪{old_salary:.2f}" if old_salary else "Не указано"
        await message.answer(
            f"✅ Зарплата обновлена\n\n"
            f"Было: {old_salary_str}\n"
            f"Стало: ₪{salary:.2f}\n\n"
            f"Возвращаю карточку пользователя..."
        )
        
        # Clear state
        await state.clear()
        
        # Show updated user card
        # Note: We need to send new message with callback format
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"admin:user:view:{user_id}")]
        ])
        await message.answer("Нажмите кнопку ниже для возврата:", reply_markup=kb)
    else:
        await message.answer("❌ Ошибка обновления зарплаты")
        await state.clear()


# ==================== EDIT DATA HANDLERS ====================

@router.callback_query(F.data.startswith("admin:editdata:name:"))
async def edit_name_start(callback: CallbackQuery, state: FSMContext):
    """Start editing user name"""
    user_id = int(callback.data.split(":")[-1])
    
    await state.update_data(user_id=user_id)
    await state.set_state(EditDataStates.waiting_name)
    
    text = (
        "👤 **Изменение имени**\n\n"
        "Введите новое имя пользователя:\n"
        "(например: Иван Петров)"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:editdata:cancel:{user_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:editdata:username:"))
async def edit_username_start(callback: CallbackQuery, state: FSMContext):
    """Start editing username"""
    user_id = int(callback.data.split(":")[-1])
    
    await state.update_data(user_id=user_id)
    await state.set_state(EditDataStates.waiting_username)
    
    text = (
        "📱 <b>Изменение username</b>\n\n"
        "Введите новый Telegram username:\n"
        "(без символа @, например: john_doe)\n\n"
        "⚠️ Внимание: username должен совпадать с реальным Telegram username пользователя для автоматической привязки!"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:editdata:cancel:{user_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:editdata:phone:"))
async def edit_phone_start(callback: CallbackQuery, state: FSMContext):
    """Start editing phone"""
    user_id = int(callback.data.split(":")[-1])
    
    await state.update_data(user_id=user_id)
    await state.set_state(EditDataStates.waiting_phone)
    
    text = (
        "☎️ <b>Изменение телефона</b>\n\n"
        "Введите номер телефона:\n"
        "(например: +972501234567 или 050-123-4567)\n\n"
        "⚠️ Это вспомогательное поле, не обязательное"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:editdata:cancel:{user_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.regexp(r"^admin:editdata:\d+$"))
async def start_edit_data(callback: CallbackQuery, state: FSMContext):
    """Show data edit menu: name or username"""
    user_id = int(callback.data.split(":")[-1])
    
    db = next(get_db())
    user = crud_users.get_user_by_id(db, user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Store user_id in FSM
    await state.update_data(user_id=user_id)
    await state.set_state(EditDataStates.choosing_field)
    
    # Show current data and edit options
    username = f"@{user.telegram_username}" if user.telegram_username else "Нет username"
    phone = user.phone if hasattr(user, 'phone') and user.phone else "Не указан"
    
    text = (
        f"📝 **Редактирование данных**\n\n"
        f"Текущие данные:\n"
        f"👤 Имя: {user.name or 'Не указано'}\n"
        f"📱 Username: {username}\n"
        f"☎️ Телефон: {phone}\n\n"
        f"Выберите, что хотите изменить:"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Изменить имя", callback_data=f"admin:editdata:name:{user_id}")],
        [InlineKeyboardButton(text="📱 Изменить @username", callback_data=f"admin:editdata:username:{user_id}")],
        [InlineKeyboardButton(text="☎️ Изменить телефон", callback_data=f"admin:editdata:phone:{user_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin:editdata:cancel:{user_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()


@router.message(EditDataStates.waiting_name)
async def receive_new_name(message: Message, state: FSMContext):
    """Process new name input"""
    new_name = message.text.strip()
    
    if not new_name or len(new_name) < 2:
        await message.answer("❌ Имя слишком короткое. Введите минимум 2 символа.")
        return
    
    if len(new_name) > 100:
        await message.answer("❌ Имя слишком длинное. Максимум 100 символов.")
        return
    
    # Get user_id from state
    data = await state.get_data()
    user_id = data.get("user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: ID пользователя не найден")
        await state.clear()
        return
    
    # Update name
    db = next(get_db())
    user = crud_users.get_user_by_id(db, user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    old_name = user.name
    updated = crud_users.update_user(db, user_id, UserUpdate(name=new_name))
    
    if updated:
        await message.answer(
            f"✅ Имя обновлено\n\n"
            f"Было: {old_name or 'Не указано'}\n"
            f"Стало: {new_name}"
        )
        
        await state.clear()
        
        # Return to card
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"admin:user:view:{user_id}")]
        ])
        await message.answer("Нажмите кнопку ниже для возврата:", reply_markup=kb)
    else:
        await message.answer("❌ Ошибка обновления имени")
        await state.clear()


@router.message(EditDataStates.waiting_username)
async def receive_new_username(message: Message, state: FSMContext):
    """Process new username input"""
    new_username = message.text.strip().lstrip("@")
    
    # Validate username format (Telegram rules)
    if not new_username:
        await message.answer("❌ Username не может быть пустым")
        return
    
    if len(new_username) < 5:
        await message.answer("❌ Username слишком короткий. Минимум 5 символов.")
        return
    
    if len(new_username) > 32:
        await message.answer("❌ Username слишком длинный. Максимум 32 символа.")
        return
    
    # Check allowed characters (alphanumeric + underscore)
    import re
    if not re.match(r'^[a-zA-Z0-9_]+$', new_username):
        await message.answer("❌ Username может содержать только буквы, цифры и подчеркивание")
        return
    
    # Get user_id from state
    data = await state.get_data()
    user_id = data.get("user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: ID пользователя не найден")
        await state.clear()
        return
    
    # Update username
    db = next(get_db())
    user = crud_users.get_user_by_id(db, user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    old_username = user.telegram_username
    updated = crud_users.update_user(db, user_id, UserUpdate(telegram_username=new_username))
    
    if updated:
        await message.answer(
            f"✅ Username обновлен\n\n"
            f"Было: @{old_username or 'Не указано'}\n"
            f"Стало: @{new_username}\n\n"
            f"⚠️ Telegram ID остался прежним. "
            f"Если пользователь сменил username в Telegram, он сможет переподключиться через /start"
        )
        
        await state.clear()
        
        # Return to card
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"admin:user:view:{user_id}")]
        ])
        await message.answer("Нажмите кнопку ниже для возврата:", reply_markup=kb)
    else:
        await message.answer("❌ Ошибка обновления username")
        await state.clear()


@router.message(EditDataStates.waiting_phone)
async def receive_new_phone(message: Message, state: FSMContext):
    """Process new phone input"""
    new_phone = message.text.strip()
    
    # Validate phone format (basic check)
    if not new_phone:
        await message.answer("❌ Телефон не может быть пустым")
        return
    
    if len(new_phone) < 7:
        await message.answer("❌ Телефон слишком короткий. Минимум 7 символов.")
        return
    
    if len(new_phone) > 20:
        await message.answer("❌ Телефон слишком длинный. Максимум 20 символов.")
        return
    
    # Check allowed characters (digits, +, -, spaces, parentheses)
    import re
    if not re.match(r'^[\d\s+\-()]+$', new_phone):
        await message.answer("❌ Телефон может содержать только цифры, пробелы, +, -, ()")
        return
    
    # Get user_id from state
    data = await state.get_data()
    user_id = data.get("user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: ID пользователя не найден")
        await state.clear()
        return
    
    # Update phone
    db = next(get_db())
    user = crud_users.get_user_by_id(db, user_id)
    
    if not user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
    
    old_phone = getattr(user, 'phone', None) if hasattr(user, 'phone') else None
    updated = crud_users.update_user(db, user_id, UserUpdate(phone=new_phone))
    
    if updated:
        await message.answer(
            f"✅ Телефон обновлен\n\n"
            f"Было: {old_phone or 'Не указано'}\n"
            f"Стало: {new_phone}"
        )
        
        await state.clear()
        
        # Return to card
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 К карточке", callback_data=f"admin:user:view:{user_id}")]
        ])
        await message.answer("Нажмите кнопку ниже для возврата:", reply_markup=kb)
    else:
        await message.answer("❌ Ошибка обновления телефона")
        await state.clear()


@router.callback_query(F.data.startswith("admin:editdata:cancel:"))
async def cancel_edit_data(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Cancel data editing and return to user card"""
    user_id = int(callback.data.split(":")[-1])
    
    await state.clear()
    
    # Return to user card
    db = next(get_db())
    user = crud_users.get_user_by_id(db, user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден")
        return
    
    # Reuse show_user_card logic by creating fake callback
    fake_callback = CallbackQuery(
        id=callback.id,
        from_user=callback.from_user,
        message=callback.message,
        chat_instance=callback.chat_instance,
        data=f"admin:user:{user_id}"
    )
    
    await show_user_card(fake_callback, bot)


@router.callback_query(F.data == "admin:noop")
async def noop(callback: CallbackQuery):
    """No-op for pagination counter button"""
    await callback.answer()
