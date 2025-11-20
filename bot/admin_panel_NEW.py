"""
Упрощённая Admin панель через APIClient (без прямых импортов из api/)

Архитектура (рефакторинг):
- admin_panel.py — роутер, регистрация обработчиков
- admin_handlers/panels/ — модули по кнопкам:
  * main_panel.py — главная панель
  * stats_panel.py — аналитика
  * refresh_panel.py — перезагрузка
  * filters_panel.py — фильтры

Использует: bot.api_client.APIClient для всех операций с данными
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
import logging

from bot.config import is_admin
from bot.admin_handlers.panels import (
    show_main_panel,
    show_stats_panel,
    handle_refresh,
    handle_filter,
)

logger = logging.getLogger(__name__)
router = Router()


# ============================================================
# КОМАНДЫ
# ============================================================

@router.message(Command("admin"))
async def admin_panel(message: Message):
    """
    Главная панель администратора (команда /admin)
    
    Делегирует отображение в show_main_panel() из panels/main_panel.py
    """
    await show_main_panel(message)


# ============================================================
# CALLBACKS — НАВИГАЦИЯ
# ============================================================

@router.callback_query(F.data == "admin:main")
async def admin_main(callback: CallbackQuery):
    """
    Возврат на главную панель (кнопка "🚀 На мостик")
    
    Шаги:
    1. Удалить текущее сообщение
    2. Создать новое через show_main_panel()
    """
    await callback.answer("🏠 Главная панель")
    await callback.message.delete()
    
    # Подменяем message для вызова show_main_panel
    class FakeMessage:
        def __init__(self, original):
            self.from_user = original.from_user
            self.chat = original.chat
            self._original = original
        
        async def answer(self, text, **kwargs):
            await self._original.answer(text, **kwargs)
    
    fake_msg = FakeMessage(callback.message)
    await show_main_panel(fake_msg)


@router.callback_query(F.data == "admin:refresh")
async def admin_refresh(callback: CallbackQuery):
    """
    Обновить главную панель (кнопка "🔄 Перезагрузка систем")
    
    Делегирует в handle_refresh() из panels/refresh_panel.py
    """
    await handle_refresh(callback)


# ============================================================
# CALLBACKS — ПАНЕЛИ
# ============================================================

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    """
    Панель аналитики (кнопка "📊 Аналитика")
    
    Делегирует в show_stats_panel() из panels/stats_panel.py
    """
    await show_stats_panel(callback)


# ============================================================
# CALLBACKS — ФИЛЬТРЫ
# ============================================================

@router.callback_query(F.data.startswith("admin:filter:"))
async def admin_filter_users(callback: CallbackQuery):
    """
    Фильтры пользователей (кнопки фильтрации по ролям/статусу)
    
    Обрабатывает:
    - admin:filter:worker
    - admin:filter:foreman
    - admin:filter:admin
    - admin:filter:inactive
    
    Делегирует в handle_filter() из panels/filters_panel.py
    """
    await handle_filter(callback)


# ============================================================
# CALLBACKS — ЗАГЛУШКИ (TODO: создать модули)
# ============================================================

@router.callback_query(F.data.startswith("admin:users:page:"))
async def admin_users_list(callback: CallbackQuery):
    """
    Список пользователей с пагинацией (кнопка "👥 Экипаж")
    
    TODO: Перенести в panels/users_panel.py
    Обработчик находится в bot/admin_handlers/admin_users.py
    """
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    await callback.answer("⚠️ Модуль 'Экипаж' — см. admin_users.py", show_alert=True)


@router.callback_query(F.data == "admin:clients")
async def admin_clients_stub(callback: CallbackQuery):
    """
    Контрагенты (кнопка "👔 Контрагенты")
    
    TODO: Создать panels/clients_panel.py
    """
    await callback.answer("⚠️ Модуль 'Контрагенты' в разработке", show_alert=True)


@router.callback_query(F.data == "admin:schedule:view")
async def admin_schedule_stub(callback: CallbackQuery):
    """
    Полетный план (кнопка "📅 Полетный план")
    
    TODO: Создать panels/schedule_panel.py
    """
    await callback.answer("⚠️ Модуль 'Полетный план' в разработке", show_alert=True)


# ============================================================
# ПРИМЕЧАНИЕ: Остальные обработчики в отдельных модулях:
# - bot/admin_handlers/admin_users.py — список пользователей
# - bot/admin_handlers/admin_add_user.py — добавление пользователя
# - bot/admin_handlers/admin_reports.py — отчёты
# - bot/admin_handlers/admin_salaries.py — зарплаты
# ============================================================
