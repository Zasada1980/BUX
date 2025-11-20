"""Add worker wizard with FSM - НОВАЯ ВЕРСИЯ

Flow:
1. /admin → ➕ Добавить рабочего
2. Enter worker name (Имя Фамилия)
3. Enter daily salary (Дневная зарплата в ₪)
4. Confirmation → Create user (role=worker by default, NO telegram_id)
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging
from decimal import Decimal

from bot.config import get_db, is_admin
from api import crud_users
from api.models_users import UserCreate

router = Router()
logger = logging.getLogger(__name__)


class AddUserStates(StatesGroup):
    waiting_name = State()
    waiting_salary = State()


def admin_only(func):
    """Decorator to restrict commands to admins only (uses is_admin with BOT_ADMINS fallback)"""
    from functools import wraps
    import inspect

    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id if hasattr(event, 'from_user') else (
            event.message.from_user.id if hasattr(event, 'message') else 0
        )

        if not is_admin(user_id):
            msg = "❌ Доступ запрещён. Требуется роль: admin"
            if isinstance(event, CallbackQuery):
                await event.answer(msg, show_alert=True)
            else:
                await event.reply(msg)
            return

        # Filter kwargs to only include parameters that func accepts
        sig = inspect.signature(func)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return await func(event, *args, **filtered_kwargs)
    return wrapper
@router.callback_query(F.data == "admin:add:start")
@admin_only
async def start_add_worker(callback: CallbackQuery, state: FSMContext):
    """Start add worker wizard"""
    logger.info(f"Starting add worker wizard for admin {callback.from_user.id}")
    await state.set_state(AddUserStates.waiting_name)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:add:cancel")]
    ])
    
    await callback.message.edit_text(
        "➕ **Добавление рабочего**\n\n"
        "Шаг 1/2: Введите имя рабочего\n\n"
        "Например: `Иван Петров` или `Моше Коэн`\n\n"
        "💡 Это имя будет видно только вам для учёта",
        reply_markup=kb,
        parse_mode="Markdown"
    )
    await callback.answer()


@router.message(AddUserStates.waiting_name)
async def receive_worker_name(message: Message, state: FSMContext):
    """Receive worker name"""
    logger.info(f"Received name from {message.from_user.id}: {message.text}")
    
    # Check admin permission using is_admin() from bot.config
    if not is_admin(message.from_user.id):
        logger.warning(f"Non-admin {message.from_user.id} tried to add user")
        await message.reply("❌ Доступ запрещён. Требуется роль: admin")
        await state.clear()
        return
    
    name = message.text.strip()
    
    if len(name) < 2:
        await message.reply("❌ Имя слишком короткое (минимум 2 символа)")
        return
    
    if len(name) > 100:
        await message.reply("❌ Имя слишком длинное (максимум 100 символов)")
        return
    
    # Save to state
    await state.update_data(name=name)
    await state.set_state(AddUserStates.waiting_salary)
    logger.info(f"Moving to waiting_salary state")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➡️ Пропустить", callback_data="admin:add:skip_salary")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="admin:add:cancel")]
    ])
    
    await message.reply(
        "✅ Имя принято\n\n"
        "Шаг 2/2: Введите дневную зарплату в ₪\n\n"
        "Например: `250` или `300.50`\n\n"
        "Или нажмите 'Пропустить', если зарплата пока неизвестна",
        reply_markup=kb,
        parse_mode="Markdown"
    )


@router.message(AddUserStates.waiting_salary)
async def receive_salary(message: Message, state: FSMContext):
    """Receive daily salary"""
    logger.info(f"Received salary from {message.from_user.id}: {message.text}")
    
    try:
        salary = Decimal(message.text.strip())
        
        if salary <= 0:
            await message.reply("❌ Зарплата должна быть положительным числом")
            return
        
        if salary > 10000:
            await message.reply("❌ Зарплата слишком большая (максимум 10,000 ₪/день)")
            return
        
        await state.update_data(daily_salary=salary)
        await create_worker(message, state)
        
    except Exception as e:
        logger.error(f"Error parsing salary: {e}")
        await message.reply("❌ Введите корректную сумму (число с точкой или без)")


@router.callback_query(F.data == "admin:add:skip_salary", AddUserStates.waiting_salary)
async def skip_salary(callback: CallbackQuery, state: FSMContext):
    """Skip salary input"""
    logger.info(f"Skipping salary for user {callback.from_user.id}")
    await state.update_data(daily_salary=None)
    await create_worker(callback.message, state)
    await callback.answer()


async def create_worker(message: Message, state: FSMContext):
    """Create worker in database"""
    data = await state.get_data()
    name = data.get("name")
    daily_salary = data.get("daily_salary")
    
    logger.info(f"Creating worker: name={name}, salary={daily_salary}")
    
    db = next(get_db())
    
    try:
        user = crud_users.create_user(
            db,
            UserCreate(
                name=name,
                daily_salary=daily_salary,
                role="worker",
                telegram_id=None,  # Рабочий БЕЗ Telegram
                telegram_username=None
            )
        )
        
        logger.info(f"Worker created successfully: {user.id}")
        
        salary_text = f"{daily_salary} ₪/день" if daily_salary else "Не указана"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Показать карточку", callback_data=f"admin:user:view:{user.id}")],
            [InlineKeyboardButton(text="➕ Добавить ещё", callback_data="admin:add:start")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="admin:panel")]
        ])
        
        await message.answer(
            f"✅ **Рабочий добавлен**\n\n"
            f"🆔 ID: `{user.id}`\n"
            f"👤 Имя: {name}\n"
            f"💰 Дневная зарплата: {salary_text}\n"
            f"🎭 Роль: 👷 Рабочий\n"
            f"📊 Статус: ✅ Активен",
            reply_markup=kb,
            parse_mode="Markdown"
        )
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Error creating worker: {e}", exc_info=True)
        await message.answer(f"❌ Ошибка создания: {str(e)}")
        await state.clear()


@router.callback_query(F.data == "admin:add:cancel")
async def cancel_add_worker(callback: CallbackQuery, state: FSMContext):
    """Cancel add worker wizard"""
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="admin:panel")]
    ])
    
    await callback.message.edit_text(
        "❌ Добавление рабочего отменено",
        reply_markup=kb
    )
    await callback.answer()
