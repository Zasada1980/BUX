"""Worker tasks and expenses management."""
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from decimal import Decimal
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from bot.config import DB_PATH  # Use centralized DB_PATH from config

logger = logging.getLogger(__name__)
router = Router()

# Database connection (use DB_PATH from config.py which respects env vars)
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class AddTaskStates(StatesGroup):
    waiting_description = State()


class AddExpenseStates(StatesGroup):
    waiting_category = State()
    waiting_amount = State()
    waiting_photo = State()


@router.callback_query(F.data == "wrk:task:new")
async def start_add_task(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Start adding task wizard."""
    user_id = callback.from_user.id
    await callback.answer()  # Немедленный ответ
    
    # Check active shift
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.message.answer("❌ Вы не найдены в системе")
            return
        
        active_shift = db.query(Shift).filter(
            Shift.user_id == worker.id,
            Shift.ended_at == None
        ).first()
        
        if not active_shift:
            await callback.answer("⚠️ Сначала начните смену!", show_alert=True)
            return
        
        # Save shift_id in state
        await state.update_data(shift_id=active_shift.id, user_id=worker.id)
        await state.set_state(AddTaskStates.waiting_description)
        
        text = (
            "📝 <b>Добавление задачи</b>\n\n"
            "Опишите выполненную работу:\n"
            "(например: Уложил 20м² плитки)"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="wrk:task:cancel")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()


@router.message(AddTaskStates.waiting_description)
async def receive_task_description(message: Message, state: FSMContext):
    """Receive task description and save."""
    description = message.text.strip()
    
    if not description or len(description) < 3:
        await message.answer("⚠️ Описание слишком короткое. Попробуйте еще раз:")
        return
    
    if len(description) > 500:
        await message.answer("⚠️ Описание слишком длинное (макс 500 символов). Попробуйте короче:")
        return
    
    # Get data from state
    data = await state.get_data()
    shift_id = data.get("shift_id")
    user_id = data.get("user_id")
    
    # Save task
    db = SessionLocal()
    try:
        from api.models import Task
        
        task = Task(
            user_id=user_id,
            shift_id=shift_id,
            description=description,
            created_at=datetime.now(ZoneInfo("Asia/Jerusalem"))
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        logger.info(f"✅ Task added: shift_id={shift_id}, task_id={task.id}")
        
        text = (
            f"✅ <b>Задача добавлена!</b>\n\n"
            f"📝 {description}\n\n"
            f"Продолжайте работу! 👍"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Добавить еще задачу", callback_data="wrk:task:new")],
            [InlineKeyboardButton(text="💸 Добавить расход", callback_data="wrk:expense:new")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
        ])
        
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        await state.clear()
        
    finally:
        db.close()


@router.callback_query(F.data == "wrk:task:cancel")
async def cancel_add_task(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Cancel adding task."""
    await state.clear()
    
    text = "❌ Добавление задачи отменено"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "wrk:expense:new")
async def start_add_expense(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Start adding expense wizard (requires active shift)."""
    user_id = callback.from_user.id
    await callback.answer()  # Немедленный ответ
    
    # Check active shift
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.message.answer("❌ Вы не найдены в системе")
            return
        
        active_shift = db.query(Shift).filter(
            Shift.user_id == worker.id,
            Shift.ended_at == None
        ).first()
        
        if not active_shift:
            await callback.answer("⚠️ Сначала начните смену!", show_alert=True)
            return
        
        # Save shift_id in state
        await state.update_data(shift_id=active_shift.id, user_id=worker.id)
        await state.set_state(AddExpenseStates.waiting_category)
        
        text = (
            "💸 <b>Добавление расхода</b>\n\n"
            "Выберите категорию расхода:"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚗 Транспорт", callback_data="wrk:expense:cat:transport")],
            [InlineKeyboardButton(text="🍔 Питание", callback_data="wrk:expense:cat:food")],
            [InlineKeyboardButton(text="🔧 Материалы", callback_data="wrk:expense:cat:materials")],
            [InlineKeyboardButton(text="📦 Другое", callback_data="wrk:expense:cat:other")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="wrk:expense:cancel")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()


@router.callback_query(F.data == "wrk:expense:new:standalone")
async def start_add_expense_standalone(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Start adding expense without active shift (from expenses list)."""
    user_id = callback.from_user.id
    await callback.answer()  # Немедленный ответ
    
    db = SessionLocal()
    try:
        from api.models_users import User
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.message.answer("❌ Вы не найдены в системе")
            return
        
        # Save user_id, no shift_id (None)
        await state.update_data(shift_id=None, user_id=worker.id)
        await state.set_state(AddExpenseStates.waiting_category)
        
        text = (
            "💸 <b>Добавление расхода</b>\n\n"
            "Выберите категорию расхода:"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚗 Транспорт", callback_data="wrk:expense:cat:transport")],
            [InlineKeyboardButton(text="🍔 Питание", callback_data="wrk:expense:cat:food")],
            [InlineKeyboardButton(text="🔧 Материалы", callback_data="wrk:expense:cat:materials")],
            [InlineKeyboardButton(text="📦 Другое", callback_data="wrk:expense:cat:other")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="wrk:expense:cancel")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()


@router.callback_query(F.data.startswith("wrk:expense:cat:"))
async def receive_expense_category(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Receive expense category."""
    await callback.answer()  # Немедленный ответ
    category = callback.data.split(":")[-1]
    
    category_map = {
        "transport": "🚗 Транспорт",
        "food": "🍔 Питание",
        "materials": "🔧 Материалы",
        "other": "📦 Другое"
    }
    
    category_name = category_map.get(category, "Другое")
    
    await state.update_data(category=category)
    await state.set_state(AddExpenseStates.waiting_amount)
    
    text = (
        f"💸 <b>Добавление расхода</b>\n\n"
        f"Категория: <b>{category_name}</b>\n\n"
        f"Введите сумму расхода в шекелях:\n"
        f"(например: 50 или 12.50)"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wrk:expense:cancel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.message(AddExpenseStates.waiting_amount)
async def receive_expense_amount(message: Message, state: FSMContext):
    """Receive expense amount and request photo."""
    try:
        amount = float(message.text.strip().replace(",", "."))
        
        if amount <= 0:
            await message.answer("⚠️ Сумма должна быть больше 0. Попробуйте еще раз:")
            return
        
        if amount > 10000:
            await message.answer("⚠️ Сумма слишком большая (макс 10000 ₪). Проверьте и попробуйте еще:")
            return
        
    except ValueError:
        await message.answer("⚠️ Неверный формат суммы. Введите число (например: 50 или 12.50):")
        return
    
    # Save amount to state
    await state.update_data(amount=amount)
    await state.set_state(AddExpenseStates.waiting_photo)
    
    # Request photo
    text = (
        f"💰 Сумма: <b>₪{amount:.2f}</b>\n\n"
        f"📸 Загрузите фотографию чека или документа\n"
        f"(или нажмите Пропустить)"
    )
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="wrk:expense:skip_photo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wrk:expense:cancel")]
    ])
    
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(AddExpenseStates.waiting_photo, F.photo)
async def receive_expense_photo(message: Message, state: FSMContext):
    """Receive expense photo and save."""
    # Get largest photo
    photo = message.photo[-1]
    photo_id = photo.file_id
    
    await save_expense_to_db(message, state, photo_id)


@router.message(AddExpenseStates.waiting_photo)
async def receive_expense_text_instead_photo(message: Message, state: FSMContext):
    """Handle text message when expecting photo - remind user."""
    text = (
        "📸 Ожидается фотография чека или документа\n\n"
        "Загрузите фото или нажмите \"Пропустить\""
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="wrk:expense:skip_photo")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wrk:expense:cancel")]
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "wrk:expense:skip_photo")
async def skip_expense_photo(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Skip photo and save expense."""
    await callback.message.delete()
    
    # Create fake message for save function
    fake_msg = callback.message
    await save_expense_to_db(fake_msg, state, photo_ref=None)
    await callback.answer()


async def save_expense_to_db(message: Message, state: FSMContext, photo_ref: str = None):
    """Save expense to database."""
    # Get data from state
    data = await state.get_data()
    shift_id = data.get("shift_id")
    user_id = data.get("user_id")
    category = data.get("category", "other")
    amount = data.get("amount")
    
    # Save expense
    db = SessionLocal()
    try:
        from api.models import Expense
        
        expense = Expense(
            user_id=user_id,
            shift_id=shift_id,
            category=category,
            amount=int(amount * 100),  # Convert ILS to agorot
            created_at=datetime.now(ZoneInfo("Asia/Jerusalem"))
        )
        db.add(expense)
        db.commit()
        db.refresh(expense)
        
        logger.info(f"✅ Expense added: shift_id={shift_id}, expense_id={expense.id}, amount={amount}, photo={photo_ref}")
        
        category_map = {
            "transport": "🚗 Транспорт",
            "food": "🍔 Питание",
            "materials": "🔧 Материалы",
            "other": "📦 Другое"
        }
        
        photo_status = "📸 С фото" if photo_ref else "📝 Без фото"
        shift_status = "📊 В смене" if shift_id else "📋 Без смены"
        
        text = (
            f"✅ <b>Расход добавлен!</b>\n\n"
            f"Категория: {category_map.get(category, 'Другое')}\n"
            f"Сумма: <b>₪{amount:.2f}</b>\n"
            f"Статус: {photo_status} | {shift_status}\n\n"
            f"Расход учтен! 📝"
        )
        
        # Different buttons based on whether we're in a shift or standalone
        if shift_id:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Добавить еще расход", callback_data="wrk:expense:new")],
                [InlineKeyboardButton(text="📝 Добавить задачу", callback_data="wrk:task:new")],
                [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
            ])
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Добавить еще расход", callback_data="wrk:expense:new:standalone")],
                [InlineKeyboardButton(text="💰 К списку расходов", callback_data="wrk:expenses:list")],
                [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
            ])
        
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        await state.clear()
        
    finally:
        db.close()


@router.callback_query(F.data == "wrk:expense:cancel")
async def cancel_add_expense(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Cancel adding expense."""
    await state.clear()
    
    text = "❌ Добавление расхода отменено"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
    ])
    
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "wrk:expenses:list")
async def show_expenses_list(callback: CallbackQuery, bot: Bot):
    """Show list of all worker expenses."""
    user_id = callback.from_user.id
    
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Expense
        from sqlalchemy import desc
        
        # Get worker
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.answer("⚠️ Пользователь не найден", show_alert=True)
            return
        
        # Get expenses
        expenses = db.query(Expense).filter(
            Expense.user_id == worker.id
        ).order_by(desc(Expense.created_at)).limit(20).all()
        
        if not expenses:
            text = "📭 <b>У вас пока нет расходов</b>\n\nДобавьте первый расход!"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Добавить расход", callback_data="wrk:expense:new:standalone")],
                [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
            ])
        else:
            from bot.ui.formatters import fmt_money
            
            category_map = {
                "transport": "🚗 Транспорт",
                "food": "🍔 Питание",
                "materials": "🔧 Материалы",
                "other": "📦 Другое"
            }
            
            # Convert agorot to shekels
            total_agorot = sum(e.amount for e in expenses)
            total = Decimal(total_agorot) / 100
            
            lines = [f"💰 <b>Ваши расходы</b> (последние 20)\n"]
            for e in expenses:
                date_str = e.created_at.strftime("%d.%m %H:%M")
                cat_name = category_map.get(e.category, "Другое")
                # Convert agorot to shekels for display
                amount_ils = Decimal(e.amount) / 100
                lines.append(f"• {date_str} | {cat_name} | <b>{fmt_money(amount_ils)}</b>")
            
            lines.append(f"\n<b>Итого:</b> {fmt_money(total)}")
            text = "\n".join(lines)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💸 Добавить расход", callback_data="wrk:expense:new:standalone")],
                [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
            ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()
