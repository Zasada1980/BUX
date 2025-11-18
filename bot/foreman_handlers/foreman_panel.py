"""
Foreman Panel - Бригадир UI
Модуль для управления панелью бригадира.

Основной функционал:
- Просмотр активных смен команды
- Одобрение/отклонение задач и расходов рабочих
- Просмотр расписания
- Управление заказчиками (ограниченное)
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
router = Router()


# ======================== FOREMAN MENU ========================

def _get_foreman_menu() -> InlineKeyboardMarkup:
    """Главное меню бригадира."""
    buttons = [
        [InlineKeyboardButton(text="👥 Активные смены", callback_data="frm:shifts")],
        [InlineKeyboardButton(text="✅ Модерация задач", callback_data="frm:moderate_tasks")],
        [InlineKeyboardButton(text="💰 Модерация расходов", callback_data="frm:moderate_expenses")],
        [InlineKeyboardButton(text="📅 Расписание", callback_data="frm:schedule")],
        [InlineKeyboardButton(text="👔 Заказчики", callback_data="frm:clients")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="frm:stats")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("foreman"))
async def show_foreman_menu(message: Message):
    """Показать главное меню бригадира."""
    logger.info(f"Foreman menu requested by user {message.from_user.id}")
    
    await message.answer(
        "🔧 <b>Панель бригадира</b>\n\n"
        "Управление командой и модерация работ.",
        reply_markup=_get_foreman_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "frm:menu")
async def foreman_menu_callback(callback: CallbackQuery):
    """Вернуться в главное меню бригадира."""
    await callback.message.edit_text(
        "🔧 <b>Панель бригадира</b>\n\n"
        "Управление командой и модерация работ.",
        reply_markup=_get_foreman_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


# ======================== ACTIVE SHIFTS ========================

@router.callback_query(F.data == "frm:shifts")
async def show_active_shifts(callback: CallbackQuery):
    """Показать активные смены команды."""
    logger.info(f"Foreman viewing active shifts: user_id={callback.from_user.id}")
    
    # TODO: Запрос к БД для получения активных смен
    # SELECT s.*, u.name, c.company_name 
    # FROM shifts s 
    # JOIN users u ON s.user_id = u.id 
    # LEFT JOIN clients c ON s.client_id = c.id
    # WHERE s.end_time IS NULL
    
    await callback.message.edit_text(
        "👥 <b>Активные смены</b>\n\n"
        "🚧 <i>Функционал в разработке</i>\n\n"
        "Здесь будет отображаться:\n"
        "• Список работающих сотрудников\n"
        "• Текущие заказчики\n"
        "• Время начала смен\n"
        "• Количество задач/расходов",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="frm:menu")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# ======================== MODERATION ========================

@router.callback_query(F.data == "frm:moderate_tasks")
async def show_task_moderation(callback: CallbackQuery):
    """Показать задачи на модерацию."""
    logger.info(f"Foreman viewing task moderation: user_id={callback.from_user.id}")
    
    # TODO: Запрос к БД для получения задач на модерацию
    # SELECT wt.*, u.name, s.start_time
    # FROM worker_tasks wt
    # JOIN shifts s ON wt.shift_id = s.id
    # JOIN users u ON s.user_id = u.id
    # WHERE wt.approved_by IS NULL
    # ORDER BY wt.created_at DESC
    
    await callback.message.edit_text(
        "✅ <b>Модерация задач</b>\n\n"
        "🚧 <i>Функционал в разработке</i>\n\n"
        "Здесь будет отображаться:\n"
        "• Задачи ожидающие одобрения\n"
        "• Кнопки [✅ Одобрить] [❌ Отклонить]\n"
        "• Фильтры по работникам\n"
        "• История модерации",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="frm:menu")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "frm:moderate_expenses")
async def show_expense_moderation(callback: CallbackQuery):
    """Показать расходы на модерацию."""
    logger.info(f"Foreman viewing expense moderation: user_id={callback.from_user.id}")
    
    # TODO: Запрос к БД для получения расходов на модерацию
    # SELECT we.*, u.name, s.start_time
    # FROM worker_expenses we
    # JOIN shifts s ON we.shift_id = s.id
    # JOIN users u ON s.user_id = u.id
    # WHERE we.approved_by IS NULL
    # ORDER BY we.created_at DESC
    
    await callback.message.edit_text(
        "💰 <b>Модерация расходов</b>\n\n"
        "🚧 <i>Функционал в разработке</i>\n\n"
        "Здесь будет отображаться:\n"
        "• Расходы ожидающие одобрения\n"
        "• Фото чеков (если есть)\n"
        "• Кнопки [✅ Одобрить] [❌ Отклонить]\n"
        "• Фильтры по категориям\n"
        "• История модерации",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="frm:menu")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# ======================== SCHEDULE ========================

@router.callback_query(F.data == "frm:schedule")
async def show_foreman_schedule(callback: CallbackQuery):
    """Показать расписание команды."""
    logger.info(f"Foreman viewing schedule: user_id={callback.from_user.id}")
    
    # TODO: Запрос к БД для получения расписания
    # SELECT s.*, c.company_name, u.name
    # FROM schedules s
    # JOIN clients c ON s.client_id = c.id
    # WHERE s.date >= date('now')
    # ORDER BY s.date ASC
    
    await callback.message.edit_text(
        "📅 <b>Расписание команды</b>\n\n"
        "🚧 <i>Функционал в разработке</i>\n\n"
        "Здесь будет отображаться:\n"
        "• Расписание на неделю\n"
        "• Назначения работников на объекты\n"
        "• Кнопки навигации по датам\n"
        "• Статистика загруженности",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="frm:menu")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# ======================== CLIENTS ========================

@router.callback_query(F.data == "frm:clients")
async def show_foreman_clients(callback: CallbackQuery):
    """Показать список заказчиков (просмотр)."""
    logger.info(f"Foreman viewing clients: user_id={callback.from_user.id}")
    
    # TODO: Запрос к БД для получения заказчиков
    # SELECT id, company_name, nickname1, nickname2, is_active
    # FROM clients
    # ORDER BY is_active DESC, company_name ASC
    
    await callback.message.edit_text(
        "👔 <b>Заказчики</b>\n\n"
        "🚧 <i>Функционал в разработке</i>\n\n"
        "Здесь будет отображаться:\n"
        "• Список активных заказчиков\n"
        "• Контактная информация (ограниченная)\n"
        "• История работ с заказчиками\n"
        "• Фильтры и поиск\n\n"
        "<i>Примечание: Бригадир может только просматривать.\n"
        "Редактирование доступно только администратору.</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="frm:menu")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()


# ======================== STATISTICS ========================

@router.callback_query(F.data == "frm:stats")
async def show_foreman_stats(callback: CallbackQuery):
    """Показать статистику команды."""
    logger.info(f"Foreman viewing stats: user_id={callback.from_user.id}")
    
    # TODO: Запросы к БД для получения статистики
    # 1. Количество активных смен
    # 2. Задачи на модерацию
    # 3. Расходы на модерацию
    # 4. Статистика за неделю/месяц
    
    await callback.message.edit_text(
        "📊 <b>Статистика команды</b>\n\n"
        "🚧 <i>Функционал в разработке</i>\n\n"
        "Здесь будет отображаться:\n"
        "• Текущие активные смены: -\n"
        "• На модерации задач: -\n"
        "• На модерации расходов: -\n"
        "• Выполнено задач за неделю: -\n"
        "• Общие расходы за неделю: -\n"
        "• Графики и диаграммы",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад", callback_data="frm:menu")]
        ]),
        parse_mode="HTML"
    )
    await callback.answer()
