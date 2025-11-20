"""Worker main panel with buttons."""
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from bot.config import is_worker, DB_PATH  # Use centralized DB_PATH from config

logger = logging.getLogger(__name__)
router = Router()

# Database connection (use DB_PATH from config.py which respects env vars)
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _build_worker_panel_message(worker, active_shift, recent_tasks, recent_expenses):
    """Build worker panel message with rich preview cards (Sprint UI-1).
    
    Args:
        worker: User model instance
        active_shift: Active Shift or None
        recent_tasks: List of recent Task models
        recent_expenses: List of recent Expense models
    
    Returns:
        Formatted message text
    """
    from bot.ui.formatters import fmt_task_preview_short, fmt_expense_preview_short
    
    status_lines = [
        f"👷 <b>Панель рабочего</b>",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"📋 <b>Личная информация:</b>",
        f"👤 Имя: <b>{worker.name}</b>",
        f"💰 Дневная ставка: <b>₪{worker.daily_salary:.2f}</b>",
        f"",
        f"⏰ <b>Статус смены:</b>"
    ]
    
    # Active shift - calculate current duration
    if active_shift:
        now_il = datetime.now(ZoneInfo("Asia/Jerusalem"))
        created_at_utc = active_shift.created_at.replace(tzinfo=ZoneInfo("UTC"))
        created_at_il = created_at_utc.astimezone(ZoneInfo("Asia/Jerusalem"))
        
        duration = now_il - created_at_il
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        status_lines.append(f"🟢 Смена <b>АКТИВНА</b>")
        status_lines.append(f"⏱️ Длительность: <b>{hours}ч {minutes}м</b>")
        status_lines.append(f"📅 Начало: <b>{created_at_il.strftime('%d.%m.%Y %H:%M')}</b>")
    else:
        status_lines.append(f"⚪ Смена <b>не начата</b>")
        status_lines.append(f"💡 Начните смену для учета работы")
    
    status_lines.extend([
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ])
    
    # Add recent tasks preview (Sprint UI-1)
    if recent_tasks:
        status_lines.append("")
        status_lines.append(f"📋 <b>Последние задачи ({len(recent_tasks)}):</b>")
        for task in recent_tasks:
            task_dict = {
                'id': task.id,
                'description': task.description,
                'status': 'pending',
                'created_at': task.created_at
            }
            status_lines.append(f"├─ {fmt_task_preview_short(task_dict)}")
        status_lines.append("")
    
    # Add recent expenses preview (Sprint UI-1)
    if recent_expenses:
        status_lines.append(f"💰 <b>Последние расходы ({len(recent_expenses)}):</b>")
        for expense in recent_expenses:
            expense_dict = {
                'id': expense.id,
                'category': expense.category,
                'amount': expense.amount,
                'status': 'pending',
                'created_at': expense.created_at
            }
            status_lines.append(f"├─ {fmt_expense_preview_short(expense_dict)}")
        status_lines.append("")
    
    status_lines.extend([
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📱 <b>Доступные действия:</b>"
    ])
    
    return "\n".join(status_lines)


def worker_only(func):
    """Decorator to allow only workers."""
    from functools import wraps
    
    @wraps(func)
    async def wrapper(event, **kwargs):
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else 0
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else 0
        
        if not is_worker(user_id):
            if isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещен", show_alert=True)
            else:
                await event.answer("⛔ Эта команда доступна только рабочим")
            return
        
        return await func(event, **kwargs)
    return wrapper


@router.message(Command("worker"))
@worker_only
async def cmd_worker_panel(message: Message):
    """Main worker panel."""
    user_id = message.from_user.id
    
    # Get worker info from DB
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift, Task, Expense
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await message.answer("❌ Вы не найдены в системе")
            return
        
        # Check active shift
        active_shift = db.query(Shift).filter(
            Shift.user_id == worker.id,
            Shift.ended_at == None
        ).first()
        
        # Get recent tasks and expenses for preview (Sprint UI-1)
        recent_tasks = db.query(Task).filter(
            Task.user_id == worker.id
        ).order_by(Task.created_at.desc()).limit(3).all()
        
        recent_expenses = db.query(Expense).filter(
            Expense.user_id == worker.id
        ).order_by(Expense.created_at.desc()).limit(3).all()
        
        # Build message using helper
        message_text = _build_worker_panel_message(worker, active_shift, recent_tasks, recent_expenses)
        
        # Build keyboard
        kb_rows = []
        
        if active_shift:
            # Active shift - show task/expense/end buttons
            kb_rows.append([
                InlineKeyboardButton(text="📝 Добавить задачу", callback_data="wrk:task:new")
            ])
            kb_rows.append([
                InlineKeyboardButton(text="💸 Добавить расход", callback_data="wrk:expense:new")
            ])
            kb_rows.append([
                InlineKeyboardButton(text="📊 Текущая смена", callback_data=f"wrk:shift:view:{active_shift.id}")
            ])
            kb_rows.append([
                InlineKeyboardButton(text="🏁 Завершить смену", callback_data="wrk:shift:end")
            ])
        else:
            # No active shift - show start button
            kb_rows.append([
                InlineKeyboardButton(text="▶️ Начать смену", callback_data="wrk:shift:start")
            ])
        
        # Common buttons - full width
        kb_rows.append([
            InlineKeyboardButton(text="📜 История смен", callback_data="wrk:shifts:history:0")
        ])
        kb_rows.append([
            InlineKeyboardButton(text="💰 Все расходы", callback_data="wrk:expenses:list")
        ])
        kb_rows.append([
            InlineKeyboardButton(text="👤 Моя карточка", callback_data="wrk:profile")
        ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await message.answer(message_text, reply_markup=kb, parse_mode="HTML")
        
    finally:
        db.close()


@router.callback_query(F.data == "wrk:shifts:month_select")
async def show_month_selector(callback: CallbackQuery, bot: Bot):
    """Show month selector (up to 3 months back with shifts)."""
    user_id = callback.from_user.id
    await callback.answer()  # Немедленный ответ
    
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift
        from sqlalchemy import func, distinct
        from datetime import datetime as dt, timedelta
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.message.answer("❌ Вы не найдены в системе")
            return
        
        # Get distinct months with shifts (up to 3 months back, excluding current)
        current_month = dt.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        three_months_ago = current_month - timedelta(days=90)
        
        # Query for months with shifts
        months_with_shifts = db.execute(
            text("""
            SELECT DISTINCT strftime('%Y-%m', created_at) as month
            FROM shifts
            WHERE user_id = :uid
              AND ended_at IS NOT NULL
              AND created_at >= :start
              AND strftime('%Y-%m', created_at) < strftime('%Y-%m', 'now')
            ORDER BY month DESC
            LIMIT 3
            """),
            {"uid": worker.id, "start": three_months_ago.isoformat()}
        ).fetchall()
        
        if not months_with_shifts:
            message_text = (
                "📅 <b>Выбор месяца</b>\n\n"
                "За последние 3 месяца смен не найдено.\n"
                "Все ваши смены в текущем месяце."
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="wrk:shifts:history:0")]
            ])
            await callback.message.edit_text(message_text, reply_markup=kb, parse_mode="HTML")
            await callback.answer()
            return
        
        # Russian month names
        MONTHS_RU = {
            1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
            5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
            9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
        }
        
        message_text = "📅 <b>Выберите месяц:</b>\n\nДоступны месяцы со сменами:"
        
        # Build month buttons
        kb_rows = []
        for row in months_with_shifts:
            month_str = row[0]  # Format: 'YYYY-MM'
            year, month = month_str.split('-')
            month_name = MONTHS_RU[int(month)]
            
            kb_rows.append([
                InlineKeyboardButton(
                    text=f"{month_name} {year}",
                    callback_data=f"wrk:shifts:history_month:{month_str}:0"
                )
            ])
        
        kb_rows.append([
            InlineKeyboardButton(text="◀️ Текущий месяц", callback_data="wrk:shifts:history:0")
        ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await callback.message.edit_text(message_text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()


@router.callback_query(F.data.startswith("wrk:shifts:history_month:"))
@router.callback_query(F.data.startswith("wrk:shifts:history:"))
async def show_shifts_history(callback: CallbackQuery, bot: Bot):
    """Show worker's shifts history with pagination (optionally filtered by month)."""
    user_id = callback.from_user.id
    await callback.answer()  # Немедленный ответ
    
    # Parse callback data
    parts = callback.data.split(":")
    if parts[2] == "history_month":
        # Format: wrk:shifts:history_month:YYYY-MM:offset
        selected_month = parts[3]
        offset = int(parts[4])
    else:
        # Format: wrk:shifts:history:offset
        selected_month = None
        offset = int(parts[-1])
    
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift, Task, Expense
        from sqlalchemy import func, desc
        from bot.ui.formatters import fmt_duration, fmt_money
        from decimal import Decimal
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.message.answer("❌ Вы не найдены в системе")
            return
        
        # Get shifts (only completed, newest first) with optional month filter
        per_page = 5
        shift_query = db.query(Shift).filter(
            Shift.user_id == worker.id,
            Shift.ended_at != None
        )
        
        # Apply month filter if specified
        if selected_month:
            shift_query = shift_query.filter(
                text(f"strftime('%Y-%m', created_at) = '{selected_month}'")
            )
        
        shifts = shift_query.order_by(desc(Shift.created_at)).offset(offset).limit(per_page).all()
        
        # Count total with same filter
        count_query = db.query(func.count(Shift.id)).filter(
            Shift.user_id == worker.id,
            Shift.ended_at != None
        )
        if selected_month:
            count_query = count_query.filter(
                text(f"strftime('%Y-%m', created_at) = '{selected_month}'")
            )
        
        total_shifts = count_query.scalar() or 0
        
        if not shifts and offset == 0:
            message_text = (
                "📜 <b>История смен</b>\n\n"
                "У вас пока нет завершенных смен.\n"
                "Начните смену и работайте! 💪"
            )
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="wrk:panel")]
            ])
            await callback.message.edit_text(message_text, reply_markup=kb, parse_mode="HTML")
            await callback.answer()
            return
        
        # Build message with month name if filtered
        month_title = "текущий месяц"
        if selected_month:
            MONTHS_RU = {
                1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
                5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
                9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь"
            }
            year, month = selected_month.split('-')
            month_title = f"{MONTHS_RU[int(month)]} {year}"
        
        lines = [
            f"📜 <b>История смен</b>",
            f"Показано {offset + 1}-{min(offset + len(shifts), total_shifts)} из {total_shifts}",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            ""
        ]
        
        # Calculate totals for completed shifts (with month filter if applicable)
        from api.models import Salary
        from datetime import datetime as dt
        
        # Apply same month filter to expenses
        expense_query = db.query(func.sum(Expense.amount)).join(
            Shift, Expense.shift_id == Shift.id
        ).filter(
            Shift.user_id == worker.id,
            Shift.ended_at != None
        )
        if selected_month:
            expense_query = expense_query.filter(
                text(f"strftime('%Y-%m', shifts.created_at) = '{selected_month}'")
            )
        
        all_completed_expenses = expense_query.scalar() or 0
        total_expenses_all = Decimal(all_completed_expenses) / 100
        
        # Get total hours worked (with month filter)
        all_shifts_query = db.query(Shift).filter(
            Shift.user_id == worker.id,
            Shift.ended_at != None
        )
        if selected_month:
            all_shifts_query = all_shifts_query.filter(
                text(f"strftime('%Y-%m', created_at) = '{selected_month}'")
            )
        
        all_shifts = all_shifts_query.all()
        total_duration_seconds = 0
        
        for s in all_shifts:
            if s.ended_at and s.created_at:
                duration = s.ended_at - s.created_at
                total_duration_seconds += duration.total_seconds()
        
        # Calculate salary: shifts count × daily_salary
        calculated_salary = Decimal('0')
        if worker.daily_salary and worker.daily_salary > 0:
            calculated_salary = Decimal(worker.daily_salary) * total_shifts
        
        # Get recorded salary from table (if exists) for current month
        current_month = dt.now().month
        current_year = dt.now().year
        recorded_salary = db.query(func.sum(Salary.amount)).filter(
            Salary.worker_id == worker.id,
            func.extract('month', Salary.date) == current_month,
            func.extract('year', Salary.date) == current_year
        ).scalar()
        
        # Use recorded salary if exists, otherwise use calculated
        monthly_salary = Decimal(recorded_salary) if recorded_salary else calculated_salary
        
        for shift in shifts:
            # Calculate duration (convert UTC to IST)
            created_at_utc = shift.created_at.replace(tzinfo=ZoneInfo("UTC"))
            ended_at_utc = shift.ended_at.replace(tzinfo=ZoneInfo("UTC"))
            created_at_il = created_at_utc.astimezone(ZoneInfo("Asia/Jerusalem"))
            ended_at_il = ended_at_utc.astimezone(ZoneInfo("Asia/Jerusalem"))
            
            duration = ended_at_il - created_at_il
            duration_seconds = duration.total_seconds()
            
            # Get tasks and expenses for this shift
            tasks_count = db.query(func.count(Task.id)).filter(Task.shift_id == shift.id).scalar() or 0
            expenses_total_agorot = db.query(func.sum(Expense.amount)).filter(Expense.shift_id == shift.id).scalar() or 0
            expenses_total = Decimal(expenses_total_agorot) / 100
            
            date_str = created_at_il.strftime('%d.%m.%Y')
            
            lines.append(f"📅 <b>{date_str}</b>")
            
            # Show tasks only if > 0
            if tasks_count > 0:
                lines.append(f"⏱️ {fmt_duration(duration_seconds)} • 📝 {tasks_count} задач")
            else:
                lines.append(f"⏱️ {fmt_duration(duration_seconds)}")
            
            # Calculate shift components
            shift_salary = Decimal(worker.daily_salary) if worker.daily_salary else Decimal('0')
            # TODO: Get bonuses from bonuses table when implemented
            shift_bonuses = Decimal('0')
            shift_total = shift_salary + shift_bonuses - expenses_total
            
            # Show details only if there are expenses or bonuses
            if expenses_total > 0 or shift_bonuses > 0:
                lines.append(f"💰 Зарплата: {fmt_money(shift_salary)}")
                if expenses_total > 0:
                    lines.append(f"💸 Расходы: {fmt_money(expenses_total)}")
                if shift_bonuses > 0:
                    lines.append(f"🎁 Бонус: {fmt_money(shift_bonuses)}")
                lines.append(f"💰 Общая сумма: {fmt_money(shift_total)}")
            else:
                lines.append(f"💰 Сумма: {fmt_money(shift_total)}")
            
            lines.append("─" * 30)
            lines.append("")
        
        # Add total summary at the bottom with month name
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📊 <b>Итого ({month_title}):</b>")
        lines.append(f"📅 Смен: {total_shifts}")
        lines.append(f"⏱️ Отработано: {fmt_duration(total_duration_seconds)}")
        
        # Show salary only if there are actual salary records
        if monthly_salary > 0:
            lines.append(f"💰 Зарплата ({month_title}): {fmt_money(monthly_salary)}")
        
        lines.append(f"💸 Расходов: {fmt_money(total_expenses_all)}")
        
        # Calculate and show grand total: salary - expenses
        grand_total = monthly_salary - total_expenses_all
        lines.append(f"💵 <b>Всего: {fmt_money(grand_total)}</b>")
        
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("")
        
        message_text = "\n".join(lines)
        
        # Build callback prefix based on mode
        if selected_month:
            callback_prefix = f"wrk:shifts:history_month:{selected_month}"
        else:
            callback_prefix = "wrk:shifts:history"
        
        # Pagination buttons
        kb_rows = []
        
        # Add "Other dates" button at the top (only if viewing current month)
        if not selected_month:
            kb_rows.append([
                InlineKeyboardButton(text="📅 Другие даты", callback_data="wrk:shifts:month_select")
            ])
        
        # Build navigation row
        nav_row = []
        
        if offset > 0:
            nav_row.append(InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=f"{callback_prefix}:{max(0, offset - per_page)}"
            ))
        
        if offset + per_page < total_shifts:
            nav_row.append(InlineKeyboardButton(
                text="Вперёд ▶️",
                callback_data=f"{callback_prefix}:{offset + per_page}"
            ))
        
        # Back button
        back_button = InlineKeyboardButton(
            text="◀️ Текущий месяц" if selected_month else "◀️ Главное меню",
            callback_data="wrk:shifts:history:0" if selected_month else "wrk:panel"
        )
        
        # Always combine navigation with back button for full width
        if len(nav_row) == 0:
            # No navigation - just back button full width
            kb_rows.append([back_button])
        elif len(nav_row) == 1:
            # One nav button - combine with back
            nav_row.append(back_button)
            kb_rows.append(nav_row)
        else:
            # Both nav buttons - put them together, back button separate
            kb_rows.append(nav_row)
            kb_rows.append([back_button])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await callback.message.edit_text(message_text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()


@router.callback_query(F.data == "wrk:panel")
async def back_to_worker_panel(callback: CallbackQuery, bot: Bot):
    """Return to worker panel."""
    user_id = callback.from_user.id
    await callback.answer()  # Немедленный ответ
    
    # Get worker info
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift, Task, Expense
        from bot.ui.formatters import fmt_task_preview_short, fmt_expense_preview_short
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.message.answer("❌ Вы не найдены в системе")
            return
        
        # Check active shift
        active_shift = db.query(Shift).filter(
            Shift.user_id == worker.id,
            Shift.ended_at == None
        ).first()
        
        # Get recent tasks and expenses for preview (Sprint UI-1)
        recent_tasks = db.query(Task).filter(
            Task.user_id == worker.id
        ).order_by(Task.created_at.desc()).limit(3).all()
        
        recent_expenses = db.query(Expense).filter(
            Expense.user_id == worker.id
        ).order_by(Expense.created_at.desc()).limit(3).all()
        
        # Build message using helper
        message_text = _build_worker_panel_message(worker, active_shift, recent_tasks, recent_expenses)
        
        # Build keyboard
        kb_rows = []
        
        if active_shift:
            kb_rows.append([
                InlineKeyboardButton(text="🏁 Завершить смену", callback_data="wrk:shift:end")
            ])
            kb_rows.append([
                InlineKeyboardButton(text="💸 Добавить расход", callback_data="wrk:expense:new")
            ])
            kb_rows.append([
                InlineKeyboardButton(text="📊 Текущая смена", callback_data=f"wrk:shift:view:{active_shift.id}")
            ])
            kb_rows.append([
                InlineKeyboardButton(text="🏁 Завершить смену", callback_data="wrk:shift:end")
            ])
        else:
            kb_rows.append([
                InlineKeyboardButton(text="▶️ Начать смену", callback_data="wrk:shift:start")
            ])
        
        kb_rows.append([
            InlineKeyboardButton(text="📜 История смен", callback_data="wrk:shifts:history:0")
        ])
        kb_rows.append([
            InlineKeyboardButton(text="💰 Все расходы", callback_data="wrk:expenses:list")
        ])
        kb_rows.append([
            InlineKeyboardButton(text="👤 Моя карточка", callback_data="wrk:profile")
        ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await callback.message.edit_text(message_text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()


@router.callback_query(F.data == "wrk:profile")
async def show_worker_profile(callback: CallbackQuery, bot: Bot):
    """Show worker profile card."""
    user_id = callback.from_user.id
    await callback.answer()  # Немедленный ответ
    
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift, Task, Expense
        from sqlalchemy import func
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.message.answer("❌ Вы не найдены в системе")
            return
        
        # Statistics
        total_shifts = db.query(func.count(Shift.id)).filter(Shift.user_id == worker.id).scalar() or 0
        total_tasks = db.query(func.count(Task.id)).filter(Task.user_id == worker.id).scalar() or 0
        total_expenses = db.query(func.count(Expense.id)).filter(Expense.user_id == worker.id).scalar() or 0
        
        # Active shift
        active_shift = db.query(Shift).filter(
            Shift.user_id == worker.id,
            Shift.ended_at == None
        ).first()
        
        lines = [
            f"👤 <b>Моя карточка</b>",
            f"",
            f"<b>Персональные данные:</b>",
            f"👤 Имя: {worker.name}",
            f"@{worker.telegram_username or 'не указано'}",
        ]
        
        if worker.phone:
            lines.append(f"☎️ Телефон: {worker.phone}")
        
        if worker.instagram_nickname:
            lines.append(f"📸 Instagram: @{worker.instagram_nickname}")
        
        lines.extend([
            f"",
            f"<b>Работа:</b>",
            f"💰 Зарплата: ₪{worker.daily_salary:.2f}/день",
            f"📊 Роль: {worker.role}",
        ])
        
        if active_shift:
            lines.append(f"🟢 Статус: смена активна")
        else:
            lines.append(f"⚪ Статус: не на смене")
        
        lines.extend([
            "",
            f"<b>Статистика:</b>",
            f"📅 Всего смен: {total_shifts}",
            f"✅ Всего задач: {total_tasks}",
            f"💸 Всего расходов: {total_expenses}",
        ])
        
        message_text = "\n".join(lines)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="wrk:panel")]
        ])
        
        await callback.message.edit_text(message_text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()
