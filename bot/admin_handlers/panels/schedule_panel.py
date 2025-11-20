"""
Панель полётного плана (📅 ПОЛЁТНЫЙ ПЛАН)

Обработчик:
- admin:schedule:view callback

Логика:
1. Проверка прав доступа (is_admin)
2. Уведомление о разработке (пока заглушка)
3. Кнопка возврата

TODO: После уточнения endpoint для графика смен:
- GET /api/admin/shifts или /api/admin/schedule
- Отображение календаря смен
- Фильтры по датам/пользователям
- Управление расписанием
"""
import logging
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.config import is_admin

logger = logging.getLogger(__name__)


async def show_schedule_panel(callback: CallbackQuery):
    """
    Отобразить панель полётного плана (график смен)
    
    Текущая реализация: ЗАГЛУШКА (в разработке)
    
    Будущий функционал:
    1. GET /api/admin/shifts или /api/admin/schedule
    2. Календарь смен с космическим дизайном
    3. Кнопки управления:
       - Добавить смену
       - Редактировать расписание
       - Просмотр истории
    4. Фильтры:
       - По датам
       - По пользователям
       - По статусу
    5. Статистика:
       - Количество смен
       - Общее время работы
       - Распределение по работникам
    
    Args:
        callback: aiogram CallbackQuery от кнопки "📅 Полетный план"
    """
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("❌ Доступ запрещён", show_alert=True)
        return
    
    # callback.answer() вызывается в роутере admin_panel.py
    
    # Заглушка с космическим дизайном
    text = """
✨📅 **ПОЛЁТНЫЙ ПЛАН** 📅✨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ **МОДУЛЬ В РАЗРАБОТКЕ**

🚧 Функционал в стадии подготовки:
│
├─ 📆 Календарь смен
├─ ➕ Планирование новых заданий
├─ ✏️ Редактирование расписания
├─ 👥 Распределение экипажа
├─ 📊 Статистика выполнения
└─ 🔍 Фильтры по датам/персоналу

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Скоро будет доступно!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 На мостик", callback_data="admin:main")]
    ])
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Schedule panel error: {e}", exc_info=True)
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
