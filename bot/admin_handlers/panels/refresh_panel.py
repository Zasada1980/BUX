"""
Обработчик кнопки "🔄 Перезагрузка систем"

Обработчик:
- admin:refresh callback

Логика:
1. Показать уведомление "🔄 Обновляю..."
2. Удалить текущее сообщение
3. Вызвать show_main_panel() для создания нового сообщения с актуальными данными
"""
import logging
from aiogram.types import CallbackQuery

from .main_panel import show_main_panel

logger = logging.getLogger(__name__)


async def handle_refresh(callback: CallbackQuery):
    """
    Обновить главную панель (пересоздать сообщение)
    
    Шаги:
    1. callback.answer("🔄 Обновляю...")
    2. Вызов show_main_panel(callback.message)
    3. Удаление старого сообщения
    
    Args:
        callback: aiogram CallbackQuery от кнопки "🔄 Перезагрузка систем"
    """
    await callback.answer("🔄 Обновляю...")
    await show_main_panel(callback.message)
    await callback.message.delete()
