"""Worker shift management (start/end/view)."""
import logging
import os
from datetime import datetime, date
from zoneinfo import ZoneInfo
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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


class StartShiftStates(StatesGroup):
    """FSM states for shift start with client selection."""
    waiting_client = State()


def _get_active_clients():
    """Get all active clients for selection."""
    db = SessionLocal()
    try:
        from api.models import Client
        clients = db.query(Client).filter(Client.is_active == 1).order_by(Client.company_name).all()
        return [(c.id, c.company_name, c.nickname1) for c in clients]
    finally:
        db.close()


def _get_today_schedule(worker_id: int):
    """Get today's schedule for worker. Returns (client_id, company_name, nickname, work_address)."""
    db = SessionLocal()
    try:
        from api.models import Schedule, Client
        today = date.today().strftime('%Y-%m-%d')
        
        # Find schedules for today where worker is assigned
        schedules = db.query(Schedule, Client).join(
            Client, Schedule.client_id == Client.id
        ).filter(
            Schedule.date == today
        ).all()
        
        # Filter by worker_id in worker_ids (comma-separated string)
        result = []
        for sched, client in schedules:
            if sched.worker_ids:
                worker_ids = [int(x.strip()) for x in sched.worker_ids.split(',') if x.strip()]
                if worker_id in worker_ids:
                    # Include work_address from schedule
                    result.append((client.id, client.company_name, client.nickname1, sched.work_address))
        
        return result
    finally:
        db.close()


@router.callback_query(F.data == "wrk:shift:start")
async def start_shift_choose_client(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Show client selection for shift start."""
    user_id = callback.from_user.id
    
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.answer("❌ Вы не найдены в системе", show_alert=True)
            return
        
        # Check if already has active shift
        active = db.query(Shift).filter(
            Shift.user_id == str(worker.id),
            Shift.ended_at == None
        ).first()
        
        if active:
            await callback.answer("⚠️ У вас уже есть активная смена!", show_alert=True)
            return
        
    finally:
        db.close()
    
    # Get scheduled clients for today
    scheduled = _get_today_schedule(worker.id)
    
    # Get all active clients
    all_clients = _get_active_clients()
    
    if not all_clients:
        await callback.answer("❌ Нет активных заказчиков. Обратитесь к админу.", show_alert=True)
        return
    
    # Build client selection keyboard
    kb_rows = []
    
    # Show scheduled clients first (if any)
    if scheduled:
        kb_rows.append([InlineKeyboardButton(text="📅 ЗАПЛАНИРОВАНО НА СЕГОДНЯ:", callback_data="noop")])
        for client_id, company_name, nickname, work_address in scheduled:
            # Display address in button text if available
            addr_display = f" - {work_address}" if work_address else ""
            kb_rows.append([InlineKeyboardButton(
                text=f"⭐ {company_name} ({nickname}){addr_display}",
                callback_data=f"wrk:shift:client:{client_id}:{work_address or ''}"
            )])
        kb_rows.append([InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━━━━━━", callback_data="noop")])
    
    # Show all active clients
    kb_rows.append([InlineKeyboardButton(text="👔 ВСЕ ЗАКАЗЧИКИ:", callback_data="noop")])
    for client_id, company_name, nickname in all_clients:
        # Skip if already in scheduled (avoid duplicates)
        scheduled_ids = [s[0] for s in scheduled] if scheduled else []
        if client_id in scheduled_ids:
            continue
        kb_rows.append([InlineKeyboardButton(
            text=f"{company_name} ({nickname})",
            callback_data=f"wrk:shift:client:{client_id}:"
        )])
    
    # Option to start without client
    kb_rows.append([InlineKeyboardButton(text="━━━━━━━━━━━━━━━━━━━━━━", callback_data="noop")])
    kb_rows.append([InlineKeyboardButton(text="🚫 Без заказчика", callback_data="wrk:shift:client:0")])
    kb_rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="wrk:panel")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    text = (
        f"🏢 <b>Выбор заказчика</b>\n\n"
        f"Выберите заказчика для смены:\n"
    )
    
    if scheduled:
        text += f"\n⭐ <b>Запланировано на сегодня:</b> {len(scheduled)} клиент(ов)\n"
    
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()
    await state.set_state(StartShiftStates.waiting_client)


@router.callback_query(F.data.startswith("wrk:shift:client:"))
async def start_shift_with_client(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Start shift with selected client."""
    user_id = callback.from_user.id
    parts = callback.data.split(":")
    client_id_str = parts[3] if len(parts) > 3 else "0"
    work_address = parts[4] if len(parts) > 4 and parts[4] else None
    
    # Handle noop (section headers)
    if client_id_str == "noop":
        await callback.answer()
        return
    
    client_id = int(client_id_str) if client_id_str != "0" else None
    
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift, Client
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.answer("❌ Вы не найдены в системе", show_alert=True)
            return
        
        # Get client info if selected
        client_name = "Не указан"
        if client_id:
            client = db.query(Client).filter(Client.id == client_id).first()
            if client:
                client_name = f"{client.company_name} ({client.nickname1})"
        
        # Create new shift with work_address
        new_shift = Shift(
            user_id=str(worker.id),
            client_id=client_id,
            work_address=work_address,  # Automatically filled from schedule
            status="open"
        )
        db.add(new_shift)
        db.commit()
        db.refresh(new_shift)
        
        logger.info(f"✅ Shift started: user={worker.name}, shift_id={new_shift.id}, client_id={client_id}, work_address={work_address}")
        
        # Convert UTC to Israel time for display
        created_at_utc = new_shift.created_at.replace(tzinfo=ZoneInfo("UTC"))
        created_at_il = created_at_utc.astimezone(ZoneInfo("Asia/Jerusalem"))
        
        address_line = f"\n📍 Адрес: {work_address}" if work_address else ""
        
        text = (
            f"✅ <b>Смена начата!</b>\n\n"
            f"⏱️ Время начала: {created_at_il.strftime('%H:%M')}\n"
            f"👤 Рабочий: {worker.name}\n"
            f"🏢 Заказчик: {client_name}{address_line}\n"
            f"💰 Дневная ставка: ₪{worker.daily_salary:.2f}\n\n"
            f"Удачной работы! 👷"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Добавить задачу", callback_data="wrk:task:new")],
            [InlineKeyboardButton(text="💸 Добавить расход", callback_data="wrk:expense:new")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer("✅ Смена начата!")
        await state.clear()
        
    finally:
        db.close()


@router.callback_query(F.data == "wrk:shift:end")
async def end_shift(callback: CallbackQuery, bot: Bot):
    """End active shift."""
    user_id = callback.from_user.id
    
    db = SessionLocal()
    try:
        from api.models_users import User
        from api.models import Shift, Task, Expense
        from sqlalchemy import func
        
        worker = db.query(User).filter(User.telegram_id == user_id).first()
        if not worker:
            await callback.answer("❌ Вы не найдены в системе", show_alert=True)
            return
        
        # Find active shift
        shift = db.query(Shift).filter(
            Shift.user_id == str(worker.id),
            Shift.ended_at == None
        ).first()
        
        if not shift:
            await callback.answer("⚠️ Нет активной смены!", show_alert=True)
            return
        
        # End shift (store in UTC like created_at)
        from datetime import timezone
        from bot.ui.formatters import fmt_duration, fmt_money
        from decimal import Decimal
        
        shift.ended_at = datetime.now(timezone.utc)
        shift.status = "closed"
        db.commit()
        
        # Calculate duration
        duration = shift.ended_at - shift.created_at
        duration_seconds = duration.total_seconds()
        
        # Get stats
        tasks_count = db.query(func.count(Task.id)).filter(Task.shift_id == shift.id).scalar() or 0
        expenses_total_agorot = db.query(func.sum(Expense.amount)).filter(Expense.shift_id == shift.id).scalar() or 0
        expenses_total = Decimal(expenses_total_agorot or 0) / 100  # Convert agorot to ILS
        
        logger.info(f"✅ Shift ended: user={worker.name}, shift_id={shift.id}, duration={duration_seconds/3600:.2f}h")
        
        text = (
            f"🏁 <b>Смена завершена!</b>\n\n"
            f"⏱️ Длительность: {fmt_duration(duration_seconds)}\n"
            f"📝 Задач выполнено: {tasks_count}\n"
            f"💸 Расходов: {fmt_money(expenses_total)}\n\n"
            f"Спасибо за работу! 👍"
        )
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Детали смены", callback_data=f"wrk:shift:view:{shift.id}")],
            [InlineKeyboardButton(text="◀️ Главное меню", callback_data="wrk:panel")]
        ])
        
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer("✅ Смена завершена!")
        
    finally:
        db.close()


@router.callback_query(F.data.startswith("wrk:shift:view:"))
async def view_shift(callback: CallbackQuery, bot: Bot):
    """View shift details."""
    shift_id = int(callback.data.split(":")[-1])
    
    db = SessionLocal()
    try:
        from api.models import Shift, Task, Expense
        from sqlalchemy import func
        from bot.ui.formatters import fmt_duration, fmt_money
        from decimal import Decimal
        
        shift = db.query(Shift).filter(Shift.id == shift_id).first()
        if not shift:
            await callback.answer("❌ Смена не найдена", show_alert=True)
            return
        
        # Get tasks and expenses
        tasks = db.query(Task).filter(Task.shift_id == shift_id).all()
        expenses = db.query(Expense).filter(Expense.shift_id == shift_id).all()
        
        # Calculate totals (convert agorot to ILS)
        expenses_total_agorot = sum(e.amount for e in expenses)
        expenses_total = Decimal(expenses_total_agorot) / 100
        
        # Build message
        lines = [f"📊 <b>Детали смены #{shift_id}</b>", ""]
        
        # Duration (convert UTC from DB to Israel time)
        if shift.ended_at:
            created_at_utc = shift.created_at.replace(tzinfo=ZoneInfo("UTC"))
            ended_at_utc = shift.ended_at.replace(tzinfo=ZoneInfo("UTC"))
            created_at_il = created_at_utc.astimezone(ZoneInfo("Asia/Jerusalem"))
            ended_at_il = ended_at_utc.astimezone(ZoneInfo("Asia/Jerusalem"))
            
            duration = ended_at_il - created_at_il
            duration_seconds = duration.total_seconds()
            lines.append(f"⏱️ Длительность: {fmt_duration(duration_seconds)}")
            lines.append(f"🕐 Начало: {created_at_il.strftime('%d.%m %H:%M')}")
            lines.append(f"🕐 Конец: {ended_at_il.strftime('%d.%m %H:%M')}")
            lines.append(f"✅ Статус: Завершена")
        else:
            # Active shift - calculate duration
            now_il = datetime.now(ZoneInfo("Asia/Jerusalem"))
            created_at_utc = shift.created_at.replace(tzinfo=ZoneInfo("UTC"))
            created_at_il = created_at_utc.astimezone(ZoneInfo("Asia/Jerusalem"))
            
            duration = now_il - created_at_il
            duration_seconds = duration.total_seconds()
            lines.append(f"⏱️ Длительность: {fmt_duration(duration_seconds)}")
            lines.append(f"🕐 Начало: {created_at_il.strftime('%d.%m %H:%M')}")
            lines.append(f"🟢 Статус: Активна")
        
        lines.append("")
        
        # Tasks
        lines.append(f"<b>📝 Задачи ({len(tasks)}):</b>")
        if tasks:
            for t in tasks[:5]:  # Show max 5
                lines.append(f"  • {t.description[:40]}...")
            if len(tasks) > 5:
                lines.append(f"  ... и еще {len(tasks) - 5}")
        else:
            lines.append("  Нет задач")
        
        lines.append("")
        
        # Expenses
        lines.append(f"<b>💸 Расходы ({len(expenses)}):</b>")
        if expenses:
            for e in expenses[:5]:  # Show max 5
                amount_ils = Decimal(e.amount) / 100
                lines.append(f"  • {fmt_money(amount_ils)} - {e.category}")
            if len(expenses) > 5:
                lines.append(f"  ... и еще {len(expenses) - 5}")
            lines.append(f"")
            lines.append(f"💰 <b>Итого расходов: {fmt_money(expenses_total)}</b>")
        else:
            lines.append("  Нет расходов")
        
        text = "\n".join(lines)
        
        kb_rows = []
        if not shift.ended_at:
            # Active shift - can add tasks/expenses or end
            kb_rows.append([
                InlineKeyboardButton(text="📝 Добавить задачу", callback_data="wrk:task:new"),
                InlineKeyboardButton(text="💸 Добавить расход", callback_data="wrk:expense:new")
            ])
            kb_rows.append([
                InlineKeyboardButton(text="🏁 Завершить смену", callback_data="wrk:shift:end")
            ])
        
        kb_rows.append([
            InlineKeyboardButton(text="◀️ Назад", callback_data="wrk:panel")
        ])
        
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        
    finally:
        db.close()
